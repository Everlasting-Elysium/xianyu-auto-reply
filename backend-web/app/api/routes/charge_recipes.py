"""代刷配方管理路由（recipes + categories + goods + sync）"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.services.charge_recipe_service import ChargeRecipeService
from common.db.session import async_session_maker
from common.models.user import User
from common.schemas.charge import (
    ChargePlatformCategoryOut,
    ChargePlatformGoodsOut,
    ChargeSkuRecipeCreate,
    ChargeSkuRecipeItemOut,
    ChargeSkuRecipeOut,
    ChargeSkuRecipeUpdate,
    ChargeSyncRequest,
    ChargeSyncResponse,
)
from common.schemas.common import ApiResponse
from common.utils.auth_scope import resolve_owner_scope

router = APIRouter(prefix="/charge-platforms", tags=["代刷配方"])


async def get_recipe_service(
    session: AsyncSession = Depends(deps.get_db_session),
) -> ChargeRecipeService:
    return ChargeRecipeService(session)


def _serialize_recipe(recipe, items) -> dict:
    out = ChargeSkuRecipeOut.model_validate({
        **{c.name: getattr(recipe, c.name) for c in recipe.__table__.columns},
        "items": [ChargeSkuRecipeItemOut.model_validate(it) for it in items],
    })
    return out.model_dump(mode="json")


@router.get("/recipes")
async def list_recipes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    item_id: str = Query(default=""),
    platform_config_id: int | None = Query(default=None),
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargeRecipeService = Depends(get_recipe_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    result = await service.list_recipes(
        owner_id=current_user.id if not is_admin else None,
        is_admin=is_admin,
        page=page,
        page_size=page_size,
        item_id=item_id,
        platform_config_id=platform_config_id,
    )
    items = [_serialize_recipe(r["recipe"], r["items"]) for r in result["items"]]
    return {
        "success": True,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "items": items,
    }


@router.post("/recipes")
async def create_recipe(
    payload: ChargeSkuRecipeCreate,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargeRecipeService = Depends(get_recipe_service),
):
    try:
        recipe, items = await service.create_recipe(
            owner_id=current_user.id,
            platform_config_id=payload.platform_config_id,
            item_id=payload.item_id,
            spec_value=payload.spec_value,
            name=payload.name,
            description=payload.description,
            require_input_keys=payload.require_input_keys,
            is_active=payload.is_active,
            items=[it.model_dump() for it in payload.items],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApiResponse(success=True, message="配方创建成功", data=_serialize_recipe(recipe, items))


@router.get("/recipes/{recipe_id}")
async def get_recipe(
    recipe_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargeRecipeService = Depends(get_recipe_service),
):
    loaded = await service.get_recipe(recipe_id, current_user.id)
    if not loaded:
        raise HTTPException(status_code=404, detail="配方不存在")
    recipe, items = loaded
    return ApiResponse(success=True, data=_serialize_recipe(recipe, items))


@router.put("/recipes/{recipe_id}")
async def update_recipe(
    recipe_id: int,
    payload: ChargeSkuRecipeUpdate,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargeRecipeService = Depends(get_recipe_service),
):
    update_data = payload.model_dump(exclude_unset=True)
    items_payload = update_data.pop("items", None)
    items = [it for it in items_payload] if items_payload else None

    loaded = await service.update_recipe(
        recipe_id=recipe_id,
        owner_id=current_user.id,
        items=items,
        **update_data,
    )
    if not loaded:
        raise HTTPException(status_code=404, detail="配方不存在")
    recipe, recipe_items = loaded
    return ApiResponse(success=True, message="配方更新成功", data=_serialize_recipe(recipe, recipe_items))


@router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargeRecipeService = Depends(get_recipe_service),
):
    ok = await service.delete_recipe(recipe_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="配方不存在")
    return ApiResponse(success=True, message="配方已删除")


@router.get("/categories")
async def list_categories(
    platform_config_id: int = Query(..., description="平台账号配置 ID"),
    only_active: bool = Query(default=True),
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargeRecipeService = Depends(get_recipe_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    try:
        await service.assert_platform_config_accessible(
            platform_config_id=platform_config_id,
            owner_id=current_user.id,
            is_admin=is_admin,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    rows = await service.list_categories(platform_config_id, only_active=only_active)
    return [ChargePlatformCategoryOut.model_validate(r).model_dump(mode="json") for r in rows]


@router.get("/goods")
async def list_goods(
    platform_config_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    keyword: str = Query(default=""),
    class_name_1: str = Query(default=""),
    class_name_2: str = Query(default=""),
    only_active: bool = Query(default=True),
    order_by: str = Query(default="price_asc"),
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargeRecipeService = Depends(get_recipe_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    try:
        await service.assert_platform_config_accessible(
            platform_config_id=platform_config_id,
            owner_id=current_user.id,
            is_admin=is_admin,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    result = await service.list_goods(
        platform_config_id=platform_config_id,
        page=page,
        page_size=page_size,
        keyword=keyword,
        class_name_1=class_name_1,
        class_name_2=class_name_2,
        only_active=only_active,
        order_by=order_by,
    )
    items = [ChargePlatformGoodsOut.model_validate(it).model_dump(mode="json") for it in result["items"]]
    return {
        "success": True,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "items": items,
    }


async def _run_sync_in_background(
    platform_config_id: int,
    owner_id: int,
    is_admin: bool,
    sync_categories: bool,
    sync_goods: bool,
) -> None:
    """同步任务的后台执行入口（每次开新 session，独立事务）"""
    try:
        async with async_session_maker() as session:
            service = ChargeRecipeService(session)
            result = await service.trigger_sync(
                platform_config_id=platform_config_id,
                owner_id=owner_id,
                is_admin=is_admin,
                sync_categories=sync_categories,
                sync_goods=sync_goods,
            )
            logger.info(
                f"[charge-sync] platform={platform_config_id} 后台同步完成: {result}"
            )
    except Exception as e:
        logger.error(
            f"[charge-sync] platform={platform_config_id} 后台同步失败: {type(e).__name__}: {e}"
        )


@router.post("/configs/{platform_config_id}/sync")
async def trigger_sync(
    platform_config_id: int,
    background_tasks: BackgroundTasks,
    payload: ChargeSyncRequest = Body(default_factory=ChargeSyncRequest),
    current_user: User = Depends(deps.get_current_active_user),
    service: ChargeRecipeService = Depends(get_recipe_service),
):
    _, is_admin = resolve_owner_scope(current_user)
    try:
        await service.assert_can_sync(
            platform_config_id=platform_config_id,
            owner_id=current_user.id,
            is_admin=is_admin,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(
        _run_sync_in_background,
        platform_config_id=platform_config_id,
        owner_id=current_user.id,
        is_admin=is_admin,
        sync_categories=payload.sync_categories,
        sync_goods=payload.sync_goods,
    )
    return ApiResponse(
        success=True,
        message="同步任务已提交，正在后台执行（约 1-10 分钟），稍后请刷新页面查看商品数量",
        data={"accepted": True},
    )
