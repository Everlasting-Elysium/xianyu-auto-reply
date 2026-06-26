"""
流量代下单记录模型

功能：
1. 记录每一笔由闲鱼订单触发的第三方平台代下单流程
2. 维护状态机：pending → collecting → ready → ordering → success/failed/cancelled
3. 支持失败重试：retry_count、next_retry_at、max_retries
4. 关联闲鱼订单（xy_order_no），便于追溯
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base_class import Base, TimestampMixin


class ChargeOrder(TimestampMixin, Base):
    """流量代下单记录表"""

    __tablename__ = "charge_orders"
    __table_args__ = (
        Index("idx_charge_order_xy", "xy_order_no"),
        Index("idx_charge_order_owner_status", "owner_id", "status"),
        Index("idx_charge_order_next_retry", "status", "next_retry_at"),
        Index("idx_charge_order_chat", "chat_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="所属用户ID（闲鱼账号 owner）"
    )
    xy_account_id: Mapped[str | None] = mapped_column(
        String(80), nullable=True,
        comment="触发该订单的闲鱼账号ID"
    )
    xy_order_no: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="关联闲鱼订单号（xy_orders.order_no）"
    )
    chat_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="闲鱼会话ID，用于向买家发送状态消息"
    )
    buyer_id: Mapped[str | None] = mapped_column(
        String(80), nullable=True,
        comment="买家ID，用于消息匹配（信息收集阶段）"
    )
    platform_config_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="使用的平台账号配置ID"
    )
    sku_mapping_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="命中的套餐映射ID（用于追溯映射规则）"
    )
    item_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="闲鱼商品ID"
    )
    spec_value: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
        comment="闲鱼商品规格值"
    )
    platform_sku_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="平台套餐ID（下单时使用）"
    )
    buyer_phone: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="充值手机号，可从订单收货信息或对话中收集"
    )
    platform_order_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="平台返回的订单号（下单成功后填充）"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending",
        comment="状态：pending/collecting/ready/ordering/success/failed/cancelled"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="已重试次数"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3",
        comment="最大重试次数"
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="下次重试时间（指数退避：30s/2min/10min）"
    )
    ordered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="平台下单成功时间"
    )
    fail_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="最近一次失败原因"
    )
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="平台返回原始数据，便于排查"
    )
