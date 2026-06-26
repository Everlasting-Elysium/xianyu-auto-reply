"""
xckj9 平台分类缓存表

定时同步 xckj9 的 GoodsClassList 到本地，供后台 SKU 选择器和"按 tag 选最便宜"使用。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base_class import Base, TimestampMixin


class ChargePlatformCategory(TimestampMixin, Base):
    """平台分类缓存"""

    __tablename__ = "charge_platform_categories"
    __table_args__ = (
        Index("idx_charge_cat_platform", "platform_config_id"),
        Index("idx_charge_cat_parent", "platform_config_id", "parent_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform_config_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="关联 charge_platform_configs.id"
    )
    platform_category_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="xckj9 的分类 Id"
    )
    parent_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="父分类 Id，0 表示顶级"
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    thumb: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1",
        comment="平台 Status=1 表示启用"
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="本地同步时间"
    )
