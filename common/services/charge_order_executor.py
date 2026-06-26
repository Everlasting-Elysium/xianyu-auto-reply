"""
代刷主单执行器

职责：
1. 给定一个 ChargeOrder（已带 recipe_id + buyer_input_params），完成"配方 → 多平台子单"的编排
2. 状态机：pending → ordering → success / partial_success / failed
3. 部分成功也算成功（业务约定）：N 个子项里只要 ≥1 成功就标 success/partial_success
4. 失败的子单写明 fail_reason，由重试任务后续兜底

幂等保证：
- 已经 success/failed 的子单不会重新下单
- 重跑执行器会跳过已完成子项，只处理 pending/failed 状态的
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.charge_order import ChargeOrder
from common.models.charge_order_sub_order import ChargeOrderSubOrder
from common.models.charge_platform_config import ChargePlatformConfig
from common.models.charge_sku_recipe import ChargeSkuRecipe, ChargeSkuRecipeItem
from common.services.charge_buyer_input_parser import validate_required_keys
from common.services.charge_platform_client import (
    ChargePlatformAuthError,
    ChargePlatformClient,
    ChargePlatformError,
)
from common.services.charge_sku_selector import ChargeSkuSelector, SkuSelection


@dataclass(slots=True)
class ExecutionResult:
    """主单执行结果"""

    main_order_id: int
    final_status: str
    successful_sub_orders: int
    failed_sub_orders: int
    skipped_sub_orders: int
    fail_summary: str | None


class ChargeOrderExecutor:
    """代刷主单执行器"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.selector = ChargeSkuSelector(session)

    async def execute(self, main_order_id: int) -> ExecutionResult:
        order = await self._load_main_order(main_order_id)

        try:
            recipe, items = await self._load_recipe(order)
            config = await self._load_platform_config(order.platform_config_id)
            self._validate_input_params(order, recipe)
        except ChargePlatformError as e:
            return await self._mark_failed(order, str(e))

        order.status = "ordering"
        await self.session.commit()

        existing_subs = await self._load_existing_sub_orders(order.id)
        client = ChargePlatformClient(config)
        success = failed = skipped = 0
        try:
            for item in items:
                if not item.is_active:
                    continue

                existing = existing_subs.get(item.id)
                if existing and existing.status == "success":
                    success += 1
                    continue

                sub_outcome = await self._execute_sub_item(
                    client=client,
                    main_order=order,
                    recipe_item=item,
                    existing_sub=existing,
                    platform_config_id=config.id,
                )
                if sub_outcome == "success":
                    success += 1
                elif sub_outcome == "skipped":
                    skipped += 1
                else:
                    failed += 1
        finally:
            await client.close()

        return await self._finalize(order, success=success, failed=failed, skipped=skipped)

    async def _load_main_order(self, main_order_id: int) -> ChargeOrder:
        order = await self.session.get(ChargeOrder, main_order_id)
        if not order:
            raise ChargePlatformError(f"主单 {main_order_id} 不存在")
        if order.status in ("success", "cancelled"):
            raise ChargePlatformError(f"主单 {main_order_id} 状态 {order.status} 不可执行")
        return order

    async def _load_recipe(self, order: ChargeOrder) -> tuple[ChargeSkuRecipe, list[ChargeSkuRecipeItem]]:
        if not order.recipe_id:
            raise ChargePlatformError("主单未关联配方")
        recipe = await self.session.get(ChargeSkuRecipe, order.recipe_id)
        if not recipe or not recipe.is_active:
            raise ChargePlatformError(f"配方 {order.recipe_id} 不存在或已禁用")

        stmt = (
            select(ChargeSkuRecipeItem)
            .where(ChargeSkuRecipeItem.recipe_id == recipe.id)
            .order_by(ChargeSkuRecipeItem.sort.asc(), ChargeSkuRecipeItem.id.asc())
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        if not items:
            raise ChargePlatformError(f"配方 {recipe.id} 没有任何子项")
        return recipe, items

    async def _load_platform_config(self, config_id: int) -> ChargePlatformConfig:
        cfg = await self.session.get(ChargePlatformConfig, config_id)
        if not cfg:
            raise ChargePlatformError(f"平台账号配置 {config_id} 不存在")
        if not cfg.enabled:
            raise ChargePlatformError(f"平台账号配置 {config_id} 已禁用")
        return cfg

    def _validate_input_params(self, order: ChargeOrder, recipe: ChargeSkuRecipe) -> None:
        params = order.buyer_input_params or {}
        missing = validate_required_keys(params, recipe.require_input_keys)
        if missing:
            raise ChargePlatformError(f"买家备注缺少必填项: {', '.join(missing)}")

    async def _load_existing_sub_orders(self, main_order_id: int) -> dict[int, ChargeOrderSubOrder]:
        stmt = select(ChargeOrderSubOrder).where(ChargeOrderSubOrder.charge_order_id == main_order_id)
        rows = (await self.session.execute(stmt)).scalars().all()
        return {row.recipe_item_id: row for row in rows if row.recipe_item_id is not None}

    async def _execute_sub_item(
        self,
        *,
        client: ChargePlatformClient,
        main_order: ChargeOrder,
        recipe_item: ChargeSkuRecipeItem,
        existing_sub: ChargeOrderSubOrder | None,
        platform_config_id: int,
    ) -> str:
        sub = existing_sub or ChargeOrderSubOrder(
            charge_order_id=main_order.id,
            recipe_item_id=recipe_item.id,
            sort=recipe_item.sort,
            tag=recipe_item.tag,
            platform_goods_id="",
            quantity=recipe_item.quantity,
            cf_count=recipe_item.cf_count,
            status="pending",
        )
        if not existing_sub:
            self.session.add(sub)
            await self.session.flush()

        selection = await self.selector.select(
            recipe_item, platform_config_id=platform_config_id
        )
        if not selection:
            sub.status = "skipped"
            sub.fail_reason = "无可用 SKU（优先集与兜底分类均不可用）"
            await self.session.commit()
            return "skipped"

        order_params = self._build_order_params(
            selection=selection,
            recipe_item=recipe_item,
            buyer_input=main_order.buyer_input_params or {},
        )

        sub.platform_goods_id = selection.goods.platform_goods_id
        sub.platform_goods_name = selection.goods.name
        sub.unit_price = selection.goods.price
        sub.order_params = order_params
        sub.status = "ordering"
        await self.session.commit()

        try:
            result = await client.create_order(
                goods_id=selection.goods.platform_goods_id,
                quantity=recipe_item.quantity,
                params=order_params,
                cf_count=recipe_item.cf_count,
            )
        except ChargePlatformAuthError as e:
            sub.status = "failed"
            sub.fail_reason = f"鉴权失败: {e}"
            sub.retry_count += 1
            await self.session.commit()
            return "failed"
        except ChargePlatformError as e:
            sub.status = "failed"
            sub.fail_reason = str(e)
            sub.retry_count += 1
            sub.response_raw = getattr(e, "raw", None)
            await self.session.commit()
            return "failed"
        except Exception as e:
            sub.status = "failed"
            sub.fail_reason = f"未预期异常: {type(e).__name__}: {e}"
            sub.retry_count += 1
            await self.session.commit()
            return "failed"

        sub.platform_order_id = str(result.get("id") or result.get("orderId") or "")
        sub.response_raw = result
        sub.status = "success"
        sub.ordered_at = datetime.now(timezone.utc)
        await self.session.commit()
        logger.info(
            f"[charge-exec] main={main_order.id} sub={sub.id} tag={sub.tag} "
            f"goods={sub.platform_goods_id} → success"
        )
        return "success"

    def _build_order_params(
        self,
        *,
        selection: SkuSelection,
        recipe_item: ChargeSkuRecipeItem,
        buyer_input: dict[str, Any],
    ) -> list[dict[str, str]]:
        overrides = recipe_item.input_value_overrides or {}
        merged = {**buyer_input, **overrides}
        return ChargePlatformClient.build_order_params(
            selection.goods.params_template or "[]",
            merged,
        )

    async def _mark_failed(self, order: ChargeOrder, reason: str) -> ExecutionResult:
        order.status = "failed"
        order.fail_reason = reason
        await self.session.commit()
        logger.warning(f"[charge-exec] main={order.id} 失败 (前置校验): {reason}")
        return ExecutionResult(
            main_order_id=order.id,
            final_status="failed",
            successful_sub_orders=0,
            failed_sub_orders=0,
            skipped_sub_orders=0,
            fail_summary=reason,
        )

    async def _finalize(
        self,
        order: ChargeOrder,
        *,
        success: int,
        failed: int,
        skipped: int,
    ) -> ExecutionResult:
        if success > 0 and failed == 0 and skipped == 0:
            order.status = "success"
            order.fail_reason = None
        elif success > 0:
            order.status = "partial_success"
            order.fail_reason = f"部分子项失败：成功 {success}, 失败 {failed}, 跳过 {skipped}"
        else:
            order.status = "failed"
            order.fail_reason = f"全部子项失败/跳过：失败 {failed}, 跳过 {skipped}"

        order.ordered_at = datetime.now(timezone.utc)
        await self.session.commit()

        logger.info(
            f"[charge-exec] main={order.id} 完成: status={order.status} "
            f"success={success} failed={failed} skipped={skipped}"
        )
        return ExecutionResult(
            main_order_id=order.id,
            final_status=order.status,
            successful_sub_orders=success,
            failed_sub_orders=failed,
            skipped_sub_orders=skipped,
            fail_summary=order.fail_reason,
        )
