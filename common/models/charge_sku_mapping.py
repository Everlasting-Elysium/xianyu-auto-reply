"""
流量套餐映射模型

功能：
1. 维护闲鱼商品 SKU → 第三方平台 SKU 的映射关系
2. 同一个闲鱼商品 + 规格 可以唯一映射到一个平台套餐
3. spec_value 为 NULL 表示"匹配该 item_id 下的所有规格"
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base_class import Base, TimestampMixin


class ChargeSkuMapping(TimestampMixin, Base):
    """流量套餐映射表"""

    __tablename__ = "charge_sku_mappings"
    __table_args__ = (
        Index("idx_charge_sku_owner", "owner_id"),
        Index("idx_charge_sku_item", "item_id"),
        Index("idx_charge_sku_platform_cfg", "platform_config_id"),
        UniqueConstraint("owner_id", "item_id", "spec_value", name="uq_charge_sku_owner_item_spec"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="所属用户ID（闲鱼账号 owner）"
    )
    platform_config_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="关联 charge_platform_configs.id（指定用哪个平台账号下单）"
    )
    item_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="闲鱼商品ID"
    )
    spec_value: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
        comment="闲鱼商品规格值，NULL 表示匹配该商品的所有规格"
    )
    platform_sku_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="平台套餐/商品ID"
    )
    platform_sku_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="平台套餐名称（仅用于后台展示，不参与匹配）"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1",
        comment="是否启用"
    )
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="备注")
