"""
闲鱼订单 → 代刷订单触发器

职责：
1. 给定一个闲鱼订单（item_id + spec_value + chat_id），查是否有匹配的 ChargeSkuRecipe
2. 命中后从聊天历史（xy_auto_reply_message_log）提取买家提供的参数
3. 创建 ChargeOrder + 调 ChargeOrderExecutor 执行
4. 返回 TriggerResult 告诉调用方"是否拦截后续卡券发货流程"

关键设计：
- 不命中配方 → 返回 not_charge_item，调用方继续走原卡券发货
- 命中但参数不全 → 创建 ChargeOrder(failed) + 通知，调用方仍跳过原卡券发货（不发卡券避免双发）
- 命中且成功 → 创建 ChargeOrder + 平台已下单，调用方跳过原卡券发货
- 已存在该闲鱼订单的 ChargeOrder（防重复触发）→ 不再创建，仍跳过原卡券发货
"""
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.auto_reply_message_log import XYAutoReplyMessageLog
from common.models.charge_order import ChargeOrder
from common.models.charge_sku_recipe import ChargeSkuRecipe
from common.models.xy_order import XYOrder
from common.services.charge_buyer_input_parser import parse_buyer_remark, validate_required_keys
from common.services.charge_order_executor import ChargeOrderExecutor


@dataclass(slots=True)
class TriggerResult:
    """触发器执行结果"""

    matched: bool
    charge_order_id: int | None = None
    final_status: str | None = None
    skip_card_delivery: bool = False
    reason: str | None = None


class ChargeOrderTrigger:
    """闲鱼订单 → 代刷流程触发器"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def maybe_trigger(
        self,
        *,
        owner_id: int,
        xy_account_id: str,
        xy_order_no: str,
        item_id: str,
        chat_id: str | None,
        buyer_id: str | None,
    ) -> TriggerResult:
        xy_order = await self._load_xy_order(xy_order_no)
        spec_value = xy_order.spec_value if xy_order else None

        recipe = await self._match_recipe(
            owner_id=owner_id, item_id=item_id, spec_value=spec_value,
        )
        if not recipe:
            return TriggerResult(matched=False, reason="未命中代刷配方")

        existing = await self._find_existing_charge_order(xy_order_no, owner_id)
        if existing:
            logger.info(
                f"[charge-trigger] xy_order={xy_order_no} 已存在 ChargeOrder id={existing.id} "
                f"status={existing.status}，跳过重复触发"
            )
            return TriggerResult(
                matched=True,
                charge_order_id=existing.id,
                final_status=existing.status,
                skip_card_delivery=True,
                reason="该闲鱼订单已有代刷主单",
            )

        buyer_input = await self._collect_buyer_input(chat_id=chat_id, buyer_id=buyer_id)

        missing = validate_required_keys(buyer_input, recipe.require_input_keys)
        if missing:
            charge_order = await self._create_charge_order(
                owner_id=owner_id,
                xy_account_id=xy_account_id,
                xy_order_no=xy_order_no,
                chat_id=chat_id,
                buyer_id=buyer_id,
                recipe=recipe,
                item_id=item_id,
                spec_value=spec_value,
                buyer_input=buyer_input,
            )
            charge_order.status = "failed"
            charge_order.fail_reason = (
                f"买家未在对话中提供必填参数: {', '.join(missing)}。"
                f"请联系买家提供后人工处理。"
            )
            await self.session.commit()
            logger.warning(
                f"[charge-trigger] xy_order={xy_order_no} 命中配方但参数不全: missing={missing}"
            )
            return TriggerResult(
                matched=True,
                charge_order_id=charge_order.id,
                final_status="failed",
                skip_card_delivery=True,
                reason=f"参数不全: {missing}",
            )

        charge_order = await self._create_charge_order(
            owner_id=owner_id,
            xy_account_id=xy_account_id,
            xy_order_no=xy_order_no,
            chat_id=chat_id,
            buyer_id=buyer_id,
            recipe=recipe,
            item_id=item_id,
            spec_value=spec_value,
            buyer_input=buyer_input,
        )
        charge_order_id = charge_order.id

        executor = ChargeOrderExecutor(self.session)
        result = await executor.execute(charge_order_id)

        logger.info(
            f"[charge-trigger] xy_order={xy_order_no} → charge_order={charge_order_id} "
            f"final={result.final_status}"
        )
        return TriggerResult(
            matched=True,
            charge_order_id=charge_order_id,
            final_status=result.final_status,
            skip_card_delivery=True,
            reason=result.fail_summary,
        )

    async def _load_xy_order(self, xy_order_no: str) -> XYOrder | None:
        stmt = select(XYOrder).where(XYOrder.order_no == xy_order_no)
        return (await self.session.execute(stmt)).scalars().first()

    async def _match_recipe(
        self,
        *,
        owner_id: int,
        item_id: str,
        spec_value: str | None,
    ) -> ChargeSkuRecipe | None:
        conditions = [
            ChargeSkuRecipe.owner_id == owner_id,
            ChargeSkuRecipe.item_id == item_id,
            ChargeSkuRecipe.is_active.is_(True),
        ]
        if spec_value:
            spec_cond = or_(
                ChargeSkuRecipe.spec_value == spec_value,
                ChargeSkuRecipe.spec_value.is_(None),
            )
        else:
            spec_cond = ChargeSkuRecipe.spec_value.is_(None)

        stmt = select(ChargeSkuRecipe).where(and_(*conditions, spec_cond))
        recipes = list((await self.session.execute(stmt)).scalars().all())
        if not recipes:
            return None
        for r in recipes:
            if r.spec_value == spec_value:
                return r
        return recipes[0]

    async def _find_existing_charge_order(
        self, xy_order_no: str, owner_id: int,
    ) -> ChargeOrder | None:
        stmt = select(ChargeOrder).where(
            ChargeOrder.xy_order_no == xy_order_no,
            ChargeOrder.owner_id == owner_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def _collect_buyer_input(
        self, *, chat_id: str | None, buyer_id: str | None,
    ) -> dict[str, str]:
        if not chat_id:
            return {}

        stmt = (
            select(XYAutoReplyMessageLog.source_message)
            .where(XYAutoReplyMessageLog.chat_id == chat_id)
            .order_by(desc(XYAutoReplyMessageLog.source_message_time))
            .limit(30)
        )
        if buyer_id:
            stmt = stmt.where(XYAutoReplyMessageLog.sender_user_id == buyer_id)

        rows = (await self.session.execute(stmt)).all()
        merged: dict[str, str] = {}
        for (msg,) in rows:
            if not msg:
                continue
            parsed = parse_buyer_remark(msg, fallback_url_key="作品链接")
            for k, v in parsed.items():
                merged.setdefault(k, v)
        return merged

    async def _create_charge_order(
        self,
        *,
        owner_id: int,
        xy_account_id: str,
        xy_order_no: str,
        chat_id: str | None,
        buyer_id: str | None,
        recipe: ChargeSkuRecipe,
        item_id: str,
        spec_value: str | None,
        buyer_input: dict[str, str],
    ) -> ChargeOrder:
        order = ChargeOrder(
            owner_id=owner_id,
            xy_account_id=xy_account_id,
            xy_order_no=xy_order_no,
            chat_id=chat_id,
            buyer_id=buyer_id,
            platform_config_id=recipe.platform_config_id,
            recipe_id=recipe.id,
            item_id=item_id,
            spec_value=spec_value,
            buyer_input_params=buyer_input or None,
            status="pending",
        )
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order
