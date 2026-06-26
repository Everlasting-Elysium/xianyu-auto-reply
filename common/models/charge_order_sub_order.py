"""
代刷子单表（一个闲鱼订单 → 多次平台下单）

主单 charge_orders 表示一次"闲鱼订单触发的代刷流程"。
子单 charge_order_sub_orders 对应配方里每个子项的实际平台下单结果。

例：闲鱼订单 "抖音10赞+1000浏览套餐"
  → charge_orders id=1
    → charge_order_sub_orders id=10 (10赞)
    → charge_order_sub_orders id=11 (1000浏览)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base_class import Base, TimestampMixin


class ChargeOrderSubOrder(TimestampMixin, Base):
    """代刷子单"""

    __tablename__ = "charge_order_sub_orders"
    __table_args__ = (
        Index("idx_charge_sub_order_main", "charge_order_id"),
        Index("idx_charge_sub_order_status", "status"),
        Index("idx_charge_sub_order_platform", "platform_order_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    charge_order_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="所属主单 charge_orders.id"
    )
    recipe_item_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="对应的配方子项 id（便于追溯配方）"
    )
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tag: Mapped[str] = mapped_column(String(64), nullable=False, comment="业务标签快照")
    platform_goods_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="选中的平台商品 Id（选品成功后填充；下单前为 NULL）"
    )
    platform_goods_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="选中的平台商品名快照"
    )
    unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 10), nullable=True,
        comment="下单时单价快照"
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cf_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_params: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True,
        comment="提交给平台的 OrderParams 快照（脱密日志可用）"
    )
    platform_order_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="平台返回的订单号（下单成功后填充）"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending",
        comment="pending/ordering/success/failed/skipped/needs_review"
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="平台返回原始数据（成功+失败都存）"
    )
