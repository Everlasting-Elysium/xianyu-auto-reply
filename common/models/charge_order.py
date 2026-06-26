"""
代刷主单表（一个闲鱼订单 → 一个主单 → N 个子单）

P3 重大调整：
- 旧字段 buyer_phone (str) 已弃用，改用 buyer_input_params (JSON) 存动态参数
- 新增 recipe_id 关联配方，新增 sub_orders 关联子单
- 状态机：pending → ordering → success / partial_success / failed / cancelled
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base_class import Base, TimestampMixin


class ChargeOrder(TimestampMixin, Base):
    """代刷主单"""

    __tablename__ = "charge_orders"
    __table_args__ = (
        Index("idx_charge_order_xy", "xy_order_no"),
        Index("idx_charge_order_owner_status", "owner_id", "status"),
        Index("idx_charge_order_next_retry", "status", "next_retry_at"),
        Index("idx_charge_order_chat", "chat_id"),
        Index("idx_charge_order_recipe", "recipe_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="所属用户ID")
    xy_account_id: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="触发该订单的闲鱼账号ID"
    )
    xy_order_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="关联闲鱼订单号"
    )
    chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    buyer_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    platform_config_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recipe_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="命中的代刷配方 id（用于追溯）"
    )
    item_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spec_value: Mapped[str | None] = mapped_column(String(120), nullable=True)
    buyer_input_params: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment='从买家备注中提取的输入参数，如 {"作品链接": "https://..."}'
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending",
        comment="pending/ordering/success/partial_success/failed/cancelled"
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
