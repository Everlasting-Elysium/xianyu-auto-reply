"""
代刷配方表 + 配方子项表

设计动机：
- 旧的 charge_sku_mappings 是"1 个闲鱼商品 → 1 个平台 SKU"的简单映射
- 新需求：组合套餐，"1 个闲鱼商品 → 多个平台 SKU（10 赞 + 1000 浏览）"
- 配方 = 一组子项的有序集合，每个子项独立选品下单
- 子项支持"优先集 + 兜底分类"双策略，自动选最便宜的可用 SKU

关系：
  charge_sku_recipes (1) ──< (N) charge_sku_recipe_items
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Boolean, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base_class import Base, TimestampMixin


class ChargeSkuRecipe(TimestampMixin, Base):
    """代刷配方（一个闲鱼商品对应一个配方）"""

    __tablename__ = "charge_sku_recipes"
    __table_args__ = (
        Index("idx_charge_recipe_owner", "owner_id"),
        Index("idx_charge_recipe_item", "item_id"),
        UniqueConstraint("owner_id", "item_id", "spec_value", name="uq_charge_recipe_owner_item_spec"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    platform_config_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="使用哪个平台账号下单"
    )
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="闲鱼商品 ID")
    spec_value: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
        comment="闲鱼商品规格值，NULL 表示匹配该商品的所有规格"
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="配方名称（便于运营识别）")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    require_input_keys: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True,
        comment='买家备注中必须包含的 key 列表，如 ["作品链接"]'
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )


class ChargeSkuRecipeItem(TimestampMixin, Base):
    """代刷配方子项（如：10赞 / 1000浏览）"""

    __tablename__ = "charge_sku_recipe_items"
    __table_args__ = (
        Index("idx_charge_recipe_item_recipe", "recipe_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sort: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="子项执行顺序，从小到大依次下单"
    )
    tag: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="业务标签（用于日志展示，如\"抖音点赞\"\"小红书收藏\"）"
    )
    preferred_sku_ids: Mapped[list[int] | None] = mapped_column(
        JSON, nullable=True,
        comment="手动选定的优先 SKU 列表（platform_goods_id），按价格升序选第一个可用的"
    )
    fallback_class_name_1: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="兜底一级分类名（class_name_1），优先集全不可用时从该分类选最便宜"
    )
    fallback_class_name_2: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="兜底二级分类名（class_name_2），可与 fallback_class_name_1 联合限定"
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="该子项的下单数量（如 10 赞 → quantity=10）"
    )
    cf_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="重复刷的次数（xckj9 CfCount 字段）"
    )
    input_value_overrides: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="按 key 覆盖买家备注里的值；用于某子项需要不同参数的场景"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
