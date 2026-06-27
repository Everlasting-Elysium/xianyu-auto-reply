"""流量充值平台管理路由（账号配置、套餐映射、订单查询）"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.services.charge_platform_service import ChargePlatformService
from common.models.user import User
from common.schemas.charge import (
    ChargeOrderOut,
    ChargeOrderRetryRequest,
    ChargePlatformConfigCreate,
    ChargePlatformConfigOut,
    ChargePlatformConfigUpdate,
    ChargeSkuMappingCreate,
    ChargeSkuMappingOut,
    ChargeSkuMappingUpdate,
)
from common.schemas.common import ApiResponse
from common.utils.auth_scope import resolve_owner_scope

router = APIRouter(prefix="/charge-platforms", tags=["流量充值平台"])


async def get_charge_service(
    session: AsyncSession = Depends(deps.get_db_session),
) -> ChargePlatformService:
    return ChargePlatformService(session)


@router.get("/configs")
async def list_configs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str = Query(default=""),
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    owner_id, is_admin = resolve_owner_scope(current_user)
    result = await service.list_configs(
        owner_id=current_user.id if not is_admin else None,
        is_admin=is_admin,
        page=page,
        page_size=page_size,
        search=search,
    )
    items = [ChargePlatformConfigOut.model_validate(item) for item in result["items"]]
    return {
        "success": True,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "items": [item.model_dump(mode="json") for item in items],
    }


@router.post("/configs")
async def create_config(
    payload: ChargePlatformConfigCreate,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    owner_id = None if is_admin else current_user.id
    config = await service.create_config(
        owner_id=owner_id,
        name=payload.name,
        platform_url=payload.platform_url,
        username=payload.username,
        password=payload.password,
        balance_alert_threshold=payload.balance_alert_threshold,
        max_orders_per_hour=payload.max_orders_per_hour,
        enabled=payload.enabled,
        remark=payload.remark,
        extra_config=payload.extra_config,
    )
    return ApiResponse(
        success=True,
        message="平台账号创建成功",
        data=ChargePlatformConfigOut.model_validate(config).model_dump(mode="json"),
    )


@router.get("/configs/{config_id}")
async def get_config(
    config_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    config = await service.get_config(
        config_id=config_id,
        owner_id=current_user.id if not is_admin else None,
        is_admin=is_admin,
    )
    if not config:
        raise HTTPException(status_code=404, detail="平台账号不存在")
    return ApiResponse(
        success=True,
        data=ChargePlatformConfigOut.model_validate(config).model_dump(mode="json"),
    )


@router.put("/configs/{config_id}")
async def update_config(
    config_id: int,
    payload: ChargePlatformConfigUpdate,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    config = await service.update_config(
        config_id=config_id,
        owner_id=current_user.id if not is_admin else None,
        is_admin=is_admin,
        **payload.model_dump(exclude_unset=True),
    )
    if not config:
        raise HTTPException(status_code=404, detail="平台账号不存在")
    return ApiResponse(
        success=True,
        message="平台账号更新成功",
        data=ChargePlatformConfigOut.model_validate(config).model_dump(mode="json"),
    )


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    ok = await service.delete_config(
        config_id=config_id,
        owner_id=current_user.id if not is_admin else None,
        is_admin=is_admin,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="平台账号不存在")
    return ApiResponse(success=True, message="平台账号已删除")


@router.get("/sku-mappings")
async def list_sku_mappings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    item_id: str = Query(default=""),
    platform_config_id: int | None = Query(default=None),
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    result = await service.list_sku_mappings(
        owner_id=current_user.id if not is_admin else None,
        is_admin=is_admin,
        page=page,
        page_size=page_size,
        item_id=item_id,
        platform_config_id=platform_config_id,
    )
    items = [ChargeSkuMappingOut.model_validate(item) for item in result["items"]]
    return {
        "success": True,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "items": [item.model_dump(mode="json") for item in items],
    }


@router.post("/sku-mappings")
async def create_sku_mapping(
    payload: ChargeSkuMappingCreate,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    try:
        mapping = await service.create_sku_mapping(
            owner_id=current_user.id,
            platform_config_id=payload.platform_config_id,
            item_id=payload.item_id,
            spec_value=payload.spec_value,
            platform_sku_id=payload.platform_sku_id,
            platform_sku_name=payload.platform_sku_name,
            is_active=payload.is_active,
            remark=payload.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApiResponse(
        success=True,
        message="套餐映射创建成功",
        data=ChargeSkuMappingOut.model_validate(mapping).model_dump(mode="json"),
    )


@router.put("/sku-mappings/{mapping_id}")
async def update_sku_mapping(
    mapping_id: int,
    payload: ChargeSkuMappingUpdate,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    mapping = await service.update_sku_mapping(
        mapping_id=mapping_id,
        owner_id=current_user.id,
        **payload.model_dump(exclude_unset=True),
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="套餐映射不存在")
    return ApiResponse(
        success=True,
        message="套餐映射更新成功",
        data=ChargeSkuMappingOut.model_validate(mapping).model_dump(mode="json"),
    )


@router.delete("/sku-mappings/{mapping_id}")
async def delete_sku_mapping(
    mapping_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    ok = await service.delete_sku_mapping(mapping_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="套餐映射不存在")
    return ApiResponse(success=True, message="套餐映射已删除")


@router.get("/orders")
async def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status: str = Query(default=""),
    xy_order_no: str = Query(default=""),
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    result = await service.list_orders(
        owner_id=current_user.id if not is_admin else None,
        is_admin=is_admin,
        page=page,
        page_size=page_size,
        status=status,
        xy_order_no=xy_order_no,
    )
    items = [ChargeOrderOut.model_validate(item) for item in result["items"]]
    return {
        "success": True,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "items": [item.model_dump(mode="json") for item in items],
    }


@router.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    order = await service.get_order(order_id, current_user.id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return ApiResponse(
        success=True,
        data=ChargeOrderOut.model_validate(order).model_dump(mode="json"),
    )


@router.post("/orders/{order_id}/retry")
async def retry_order(
    order_id: int,
    payload: ChargeOrderRetryRequest,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    try:
        order = await service.retry_order(
            order_id=order_id,
            owner_id=current_user.id,
            reset_retry_count=payload.reset_retry_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return ApiResponse(
        success=True,
        message="已重置为待重试状态",
        data=ChargeOrderOut.model_validate(order).model_dump(mode="json"),
    )


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargePlatformService = Depends(get_charge_service),
):
    try:
        order = await service.cancel_order(order_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return ApiResponse(
        success=True,
        message="订单已取消",
        data=ChargeOrderOut.model_validate(order).model_dump(mode="json"),
    )
