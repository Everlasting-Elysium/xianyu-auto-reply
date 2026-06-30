"""
流量充值平台账号配置模型

功能：
1. 存储第三方流量充值平台（xckj9 等）的账号配置
2. 维护登录态：cookie/token 备份（Redis miss 时兜底）
3. 维护账号健康状态：余额、风控状态、最近登录时间、最近错误
4. 多个闲鱼账号可以共享同一个平台账号，因此本表不绑定 account_id
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Index, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base_class import Base, TimestampMixin


class ChargePlatformConfig(TimestampMixin, Base):
    """流量充值平台账号配置表"""

    __tablename__ = "charge_platform_configs"
    __table_args__ = (
        Index("idx_charge_platform_owner", "owner_id"),
        Index("idx_charge_platform_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="配置归属用户ID，NULL 表示全局共享（多个闲鱼账号可共享同一个平台账号）"
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="账号别名")
    platform_url: Mapped[str] = mapped_column(
        String(256), nullable=False,
        default="https://xckj9.008e1.top",
        comment="平台基础 URL"
    )
    username: Mapped[str] = mapped_column(String(128), nullable=False, comment="登录账号")
    password: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="登录密码（与 xy_accounts.login_password 保持一致策略：明文存储）"
    )
    session_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="Cookie/Token 备份，Redis miss 时使用：{cookies: [...], tokens: {...}}"
    )
    session_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="登录态预计失效时间"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="最近一次成功登录时间"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active",
        comment="账号状态：active/disabled/risk_controlled/login_failed/balance_low"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1",
        comment="是否启用（主开关）"
    )
    balance: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True,
        comment="最近一次查询的账户余额（元）"
    )
    balance_alert_threshold: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("50.00"), server_default="50.00",
        comment="余额告警阈值（元），低于此值触发通知"
    )
    balance_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="最近一次余额查询时间"
    )
    max_orders_per_hour: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=20, server_default="20",
        comment="每小时最大下单数，超过则暂停下单（防风控）"
    )
    last_error: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        comment="最近一次错误描述"
    )
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="最近一次错误时间"
    )
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="备注")
    extra_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="扩展配置：{platform_type: 'xckj9', api_endpoints: {...}}"
    )
