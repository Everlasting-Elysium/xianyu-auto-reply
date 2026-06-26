"""
代刷平台相关 Schema

P3 升级：
- ChargeOrderOut 对齐新模型（recipe_id / buyer_input_params 替代旧的 sku_mapping_id / buyer_phone）
- 新增 Recipe / RecipeItem / SubOrder / Category / Goods 的 CRUD Schema
- 旧的 ChargeSkuMapping Schema 保留以维持 P1 API 兼容性
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
    password: str | None = Field(default=None)
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
    platform_config_id: int
    item_id: str = Field(..., max_length=64)
    spec_value: str | None = Field(default=None, max_length=120)
    platform_sku_id: str = Field(..., max_length=128)
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


class ChargePlatformCategoryOut(BaseModel):
    id: int
    platform_config_id: int
    platform_category_id: int
    parent_id: int
    name: str
    level: int
    sort: int
    thumb: str | None
    is_active: bool
    last_synced_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargePlatformGoodsOut(BaseModel):
    id: int
    platform_config_id: int
    platform_goods_id: str
    gid: str | None
    name: str
    class_name_1: str | None
    class_name_2: str | None
    class_name_3: str | None
    price: Decimal
    stock: int
    min_order_num: int
    max_order_num: int
    unit: str | None
    goods_type: int | None
    params_template: str | None
    thumb: str | None
    is_active: bool
    last_synced_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargeSyncRequest(BaseModel):
    sync_categories: bool = Field(default=True)
    sync_goods: bool = Field(default=True)


class ChargeSyncResponse(BaseModel):
    categories: dict[str, int] | None = None
    goods: dict[str, int] | None = None


class ChargeSkuRecipeItemPayload(BaseModel):
    sort: int = Field(default=0, ge=0)
    tag: str = Field(..., max_length=64, description="业务标签，如'抖音点赞'")
    preferred_sku_ids: list[int] | None = Field(default=None)
    fallback_class_name_1: str | None = Field(default=None, max_length=128)
    fallback_class_name_2: str | None = Field(default=None, max_length=128)
    quantity: int = Field(..., ge=1)
    cf_count: int = Field(default=0, ge=0)
    input_value_overrides: dict[str, Any] | None = None
    is_active: bool = True


class ChargeSkuRecipeItemOut(ChargeSkuRecipeItemPayload):
    id: int
    recipe_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargeSkuRecipeCreate(BaseModel):
    platform_config_id: int = Field(..., description="使用哪个平台账号")
    item_id: str = Field(..., max_length=64, description="闲鱼商品 ID")
    spec_value: str | None = Field(default=None, max_length=120)
    name: str = Field(..., max_length=128, description="配方名（运营识别用）")
    description: str | None = Field(default=None, max_length=512)
    require_input_keys: list[str] | None = Field(default=None, description="买家备注必填的 key 列表")
    is_active: bool = True
    items: list[ChargeSkuRecipeItemPayload] = Field(..., min_length=1)


class ChargeSkuRecipeUpdate(BaseModel):
    platform_config_id: int | None = None
    item_id: str | None = Field(default=None, max_length=64)
    spec_value: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    require_input_keys: list[str] | None = None
    is_active: bool | None = None
    items: list[ChargeSkuRecipeItemPayload] | None = Field(
        default=None,
        description="如提供则整体替换子项（先全删旧子项再插入新子项）",
    )


class ChargeSkuRecipeOut(BaseModel):
    id: int
    owner_id: int
    platform_config_id: int
    item_id: str
    spec_value: str | None
    name: str
    description: str | None
    require_input_keys: list[str] | None
    is_active: bool
    items: list[ChargeSkuRecipeItemOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargeOrderSubOrderOut(BaseModel):
    id: int
    charge_order_id: int
    recipe_item_id: int | None
    sort: int
    tag: str
    platform_goods_id: str
    platform_goods_name: str | None
    unit_price: Decimal | None
    quantity: int
    cf_count: int
    order_params: list[dict[str, Any]] | None
    platform_order_id: str | None
    status: str
    retry_count: int
    next_retry_at: datetime | None
    fail_reason: str | None
    ordered_at: datetime | None
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
    recipe_id: int | None
    item_id: str | None
    spec_value: str | None
    buyer_input_params: dict[str, Any] | None
    status: str
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None
    ordered_at: datetime | None
    fail_reason: str | None
    extra_data: dict[str, Any] | None
    sub_orders: list[ChargeOrderSubOrderOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargeOrderRetryRequest(BaseModel):
    reset_retry_count: bool = Field(default=True)
