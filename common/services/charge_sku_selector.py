"""
代刷选品引擎

策略：
1. 优先集（preferred_sku_ids）按顺序检查，第一个可用的（is_active + 数量符合 min/max）即选中
   - "优先"按列表顺序而非价格 - 运营手动排序就是优先级
2. 优先集全不可用时，从 fallback_class_name_1/2（如"小红薯区/红薯收藏"）下找价格最低的可用 SKU
3. 找不到则返回 None（执行器据此标记子单 skipped）

可用判定：
- is_active = True
- stock < 0 (不限) 或 stock >= quantity
- min_order_num <= quantity <= (max_order_num 或无穷)

为什么用 class_name 而非 class_id：
- xckj9 的 GoodsList 接口只返回 ClassName1/ClassName2，不返回分类 ID
- 分类同步表存了 platform_category_id + name，但商品 ↔ 分类只能按 name 关联
"""
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.charge_platform_goods import ChargePlatformGoods
from common.models.charge_sku_recipe import ChargeSkuRecipeItem


@dataclass(slots=True)
class SkuSelection:
    """选品结果"""

    goods: ChargePlatformGoods
    source: str  # "preferred" / "fallback"


class ChargeSkuSelector:
    """代刷选品引擎"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def select(
        self,
        recipe_item: ChargeSkuRecipeItem,
        *,
        platform_config_id: int,
        quantity: int | None = None,
    ) -> SkuSelection | None:
        qty = quantity if quantity is not None else recipe_item.quantity

        candidates = await self._load_preferred(
            recipe_item.preferred_sku_ids or [],
            platform_config_id=platform_config_id,
        )
        for goods in candidates:
            if self._is_usable(goods, qty):
                logger.debug(
                    f"[sku-selector] recipe_item={recipe_item.id} 命中优先集 "
                    f"goods={goods.platform_goods_id} price={goods.price}"
                )
                return SkuSelection(goods=goods, source="preferred")

        if recipe_item.fallback_class_name_1 or recipe_item.fallback_class_name_2:
            cheapest = await self._find_cheapest_in_category(
                class_name_1=recipe_item.fallback_class_name_1,
                class_name_2=recipe_item.fallback_class_name_2,
                platform_config_id=platform_config_id,
                quantity=qty,
            )
            if cheapest:
                logger.debug(
                    f"[sku-selector] recipe_item={recipe_item.id} 兜底分类命中 "
                    f"goods={cheapest.platform_goods_id} price={cheapest.price}"
                )
                return SkuSelection(goods=cheapest, source="fallback")

        logger.warning(
            f"[sku-selector] recipe_item={recipe_item.id} 无可用 SKU "
            f"(preferred={recipe_item.preferred_sku_ids}, "
            f"fallback={recipe_item.fallback_class_name_1}/{recipe_item.fallback_class_name_2})"
        )
        return None

    async def _load_preferred(
        self,
        preferred_ids: list[int],
        *,
        platform_config_id: int,
    ) -> list[ChargePlatformGoods]:
        if not preferred_ids:
            return []
        str_ids = [str(i) for i in preferred_ids]
        stmt = select(ChargePlatformGoods).where(
            ChargePlatformGoods.platform_config_id == platform_config_id,
            ChargePlatformGoods.platform_goods_id.in_(str_ids),
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        by_id = {g.platform_goods_id: g for g in rows}
        return [by_id[sid] for sid in str_ids if sid in by_id]

    async def _find_cheapest_in_category(
        self,
        *,
        class_name_1: str | None,
        class_name_2: str | None,
        platform_config_id: int,
        quantity: int,
    ) -> ChargePlatformGoods | None:
        conditions = [
            ChargePlatformGoods.platform_config_id == platform_config_id,
            ChargePlatformGoods.is_active.is_(True),
            ChargePlatformGoods.min_order_num <= quantity,
        ]
        if class_name_1:
            conditions.append(ChargePlatformGoods.class_name_1 == class_name_1)
        if class_name_2:
            conditions.append(ChargePlatformGoods.class_name_2 == class_name_2)

        stmt = (
            select(ChargePlatformGoods)
            .where(*conditions)
            .order_by(ChargePlatformGoods.price.asc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        for goods in rows:
            if self._is_usable(goods, quantity):
                return goods
        return None

    @staticmethod
    def _is_usable(goods: ChargePlatformGoods, quantity: int) -> bool:
        if not goods.is_active:
            return False
        if goods.stock >= 0 and goods.stock < quantity:
            return False
        if goods.min_order_num > quantity:
            return False
        if goods.max_order_num > 0 and goods.max_order_num < quantity:
            return False
        return True
