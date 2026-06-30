"""
xckj9 平台商品仓库缓存表

定时同步全部商品到本地，供：
1. 后台 SKU 选择器（分类树 + 搜索 + 价格排序）
2. "选最便宜"引擎过滤同 tag 下可用且价格最低的 SKU
3. 离线展示商品 ParamsTemplate（不必每次拉网）
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base_class import Base, TimestampMixin


class ChargePlatformGoods(TimestampMixin, Base):
    """平台商品仓库缓存"""

    __tablename__ = "charge_platform_goods"
    __table_args__ = (
        Index("idx_charge_goods_platform", "platform_config_id"),
        Index("idx_charge_goods_class_name", "platform_config_id", "class_name_1", "class_name_2"),
        Index("idx_charge_goods_price", "platform_config_id", "is_active", "price"),
        Index("idx_charge_goods_goods_id", "platform_config_id", "platform_goods_id", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform_config_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    platform_goods_id: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="xckj9 商品 Id"
    )
    gid: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="xckj9 商品 Gid")
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    class_name_1: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="一级分类名（平台不返回 ID 只返回 Name）")
    class_name_2: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="二级分类名")
    class_name_3: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="三级分类名（如有）")

    price: Mapped[Decimal] = mapped_column(
        Numeric(18, 10), nullable=False, default=Decimal("0"),
        comment="单价（xckj9 GoodsPrice）"
    )
    stock: Mapped[int] = mapped_column(
        Integer, nullable=False, default=-1,
        comment="库存（-1 表示不限制）"
    )
    min_order_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_order_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="0 表示不限制")
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    goods_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    params_template: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="原始 ParamsTemplate JSON 字符串"
    )
    thumb: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1",
        comment="平台 IsClose=2 表示可用（这里映射为 True）"
    )
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
