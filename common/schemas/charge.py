"""
流量充值平台相关 Schema

包含：
1. 平台账号配置（ChargePlatformConfig）的 CRUD 请求/响应
2. 套餐映射（ChargeSkuMapping）的 CRUD 请求/响应
3. 代下单记录（ChargeOrder）的查询响应
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChargePlatformConfigBase(BaseModel):
    name: str = Field(..., max_length=64, description="账号别名")
    platform_url: str = Field(default="https://xckj9.008e1.top", max_length=256)
    username: str = Field(..., max_length=128)
    balance_alert_threshold: Decimal = Field(default=Decimal("50.00"), ge=0)
    max_orders_per_hour: int = Field(default=20, ge=1, le=1000)
    enabled: bool = True
    remark: str | None = Field(default=None, max_length=255)
    extra_config: dict[str, Any] | None = None


class ChargePlatformConfigCreate(ChargePlatformConfigBase):
    password: str = Field(..., min_length=1, description="登录密码")


class ChargePlatformConfigUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    platform_url: str | None = Field(default=None, max_length=256)
    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, description="如填写则更新密码")
    balance_alert_threshold: Decimal | None = Field(default=None, ge=0)
    max_orders_per_hour: int | None = Field(default=None, ge=1, le=1000)
    enabled: bool | None = None
    status: str | None = None
    remark: str | None = Field(default=None, max_length=255)
    extra_config: dict[str, Any] | None = None


class ChargePlatformConfigOut(BaseModel):
    id: int
    owner_id: int | None
    name: str
    platform_url: str
    username: str
    status: str
    enabled: bool
    balance: Decimal | None
    balance_alert_threshold: Decimal
    balance_checked_at: datetime | None
    max_orders_per_hour: int
    last_login_at: datetime | None
    session_expires_at: datetime | None
    last_error: str | None
    last_error_at: datetime | None
    remark: str | None
    extra_config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargeSkuMappingBase(BaseModel):
    platform_config_id: int = Field(..., description="关联的平台账号配置ID")
    item_id: str = Field(..., max_length=64, description="闲鱼商品ID")
    spec_value: str | None = Field(default=None, max_length=120, description="规格值，留空匹配所有规格")
    platform_sku_id: str = Field(..., max_length=128, description="平台套餐ID")
    platform_sku_name: str | None = Field(default=None, max_length=256)
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class ChargeSkuMappingCreate(ChargeSkuMappingBase):
    pass


class ChargeSkuMappingUpdate(BaseModel):
    platform_config_id: int | None = None
    item_id: str | None = Field(default=None, max_length=64)
    spec_value: str | None = Field(default=None, max_length=120)
    platform_sku_id: str | None = Field(default=None, max_length=128)
    platform_sku_name: str | None = Field(default=None, max_length=256)
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class ChargeSkuMappingOut(BaseModel):
    id: int
    owner_id: int
    platform_config_id: int
    item_id: str
    spec_value: str | None
    platform_sku_id: str
    platform_sku_name: str | None
    is_active: bool
    remark: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargeOrderOut(BaseModel):
    id: int
    owner_id: int
    xy_account_id: str | None
    xy_order_no: str
    chat_id: str | None
    buyer_id: str | None
    platform_config_id: int
    sku_mapping_id: int | None
    item_id: str | None
    spec_value: str | None
    platform_sku_id: str
    buyer_phone: str | None
    platform_order_id: str | None
    status: str
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None
    ordered_at: datetime | None
    fail_reason: str | None
    extra_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargeOrderRetryRequest(BaseModel):
    reset_retry_count: bool = Field(default=True, description="是否重置 retry_count 为 0")
