"""代刷配方 + 子项 + 商品/分类查询 + 同步触发 服务"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.charge_platform_category import ChargePlatformCategory
from common.models.charge_platform_config import ChargePlatformConfig
from common.models.charge_platform_goods import ChargePlatformGoods
from common.models.charge_sku_recipe import ChargeSkuRecipe, ChargeSkuRecipeItem
from common.services.charge_platform_sync_service import ChargePlatformSyncService


class ChargeRecipeService:
    """代刷配方管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_recipes(
        self,
        owner_id: int | None,
        is_admin: bool = False,
        page: int = 1,
        page_size: int = 20,
        item_id: str = "",
        platform_config_id: int | None = None,
    ) -> dict[str, Any]:
        stmt = select(ChargeSkuRecipe)
        count_stmt = select(func.count()).select_from(ChargeSkuRecipe)

        if not is_admin:
            stmt = stmt.where(ChargeSkuRecipe.owner_id == owner_id)
            count_stmt = count_stmt.where(ChargeSkuRecipe.owner_id == owner_id)

        if item_id:
            stmt = stmt.where(ChargeSkuRecipe.item_id == item_id)
            count_stmt = count_stmt.where(ChargeSkuRecipe.item_id == item_id)
        if platform_config_id is not None:
            stmt = stmt.where(ChargeSkuRecipe.platform_config_id == platform_config_id)
            count_stmt = count_stmt.where(ChargeSkuRecipe.platform_config_id == platform_config_id)

        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(ChargeSkuRecipe.id.desc()).offset((page - 1) * page_size).limit(page_size)
        recipes = list((await self.session.execute(stmt)).scalars().all())

        recipe_ids = [r.id for r in recipes]
        items_by_recipe: dict[int, list[ChargeSkuRecipeItem]] = {rid: [] for rid in recipe_ids}
        if recipe_ids:
            items_stmt = (
                select(ChargeSkuRecipeItem)
                .where(ChargeSkuRecipeItem.recipe_id.in_(recipe_ids))
                .order_by(ChargeSkuRecipeItem.recipe_id, ChargeSkuRecipeItem.sort, ChargeSkuRecipeItem.id)
            )
            for it in (await self.session.execute(items_stmt)).scalars().all():
                items_by_recipe.setdefault(it.recipe_id, []).append(it)

        result_items: list[dict[str, Any]] = []
        for r in recipes:
            result_items.append({"recipe": r, "items": items_by_recipe.get(r.id, [])})

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": result_items,
        }

    async def get_recipe(self, recipe_id: int, owner_id: int) -> tuple[ChargeSkuRecipe, list[ChargeSkuRecipeItem]] | None:
        stmt = select(ChargeSkuRecipe).where(
            ChargeSkuRecipe.id == recipe_id,
            ChargeSkuRecipe.owner_id == owner_id,
        )
        recipe = (await self.session.execute(stmt)).scalars().first()
        if not recipe:
            return None
        items_stmt = (
            select(ChargeSkuRecipeItem)
            .where(ChargeSkuRecipeItem.recipe_id == recipe_id)
            .order_by(ChargeSkuRecipeItem.sort, ChargeSkuRecipeItem.id)
        )
        items = list((await self.session.execute(items_stmt)).scalars().all())
        return recipe, items

    async def create_recipe(
        self,
        owner_id: int,
        *,
        platform_config_id: int,
        item_id: str,
        spec_value: str | None,
        name: str,
        description: str | None,
        require_input_keys: list[str] | None,
        is_active: bool,
        items: list[dict[str, Any]],
    ) -> tuple[ChargeSkuRecipe, list[ChargeSkuRecipeItem]]:
        cfg = await self.session.get(ChargePlatformConfig, platform_config_id)
        if not cfg:
            raise ValueError("指定的平台账号配置不存在")
        if cfg.owner_id is not None and cfg.owner_id != owner_id:
            raise ValueError("无权使用该平台账号配置")

        existing_stmt = select(ChargeSkuRecipe).where(
            ChargeSkuRecipe.owner_id == owner_id,
            ChargeSkuRecipe.item_id == item_id,
            ChargeSkuRecipe.spec_value.is_(None) if spec_value is None
            else ChargeSkuRecipe.spec_value == spec_value,
        )
        if (await self.session.execute(existing_stmt)).scalars().first():
            raise ValueError("该商品 + 规格的配方已存在")

        recipe = ChargeSkuRecipe(
            owner_id=owner_id,
            platform_config_id=platform_config_id,
            item_id=item_id,
            spec_value=spec_value,
            name=name,
            description=description,
            require_input_keys=require_input_keys,
            is_active=is_active,
        )
        self.session.add(recipe)
        await self.session.flush()

        item_objs: list[ChargeSkuRecipeItem] = []
        for payload in items:
            item_obj = ChargeSkuRecipeItem(recipe_id=recipe.id, **payload)
            self.session.add(item_obj)
            item_objs.append(item_obj)

        await self.session.commit()
        await self.session.refresh(recipe)
        for it in item_objs:
            await self.session.refresh(it)
        return recipe, item_objs

    async def update_recipe(
        self,
        recipe_id: int,
        owner_id: int,
        *,
        items: list[dict[str, Any]] | None = None,
        **fields: Any,
    ) -> tuple[ChargeSkuRecipe, list[ChargeSkuRecipeItem]] | None:
        loaded = await self.get_recipe(recipe_id, owner_id)
        if not loaded:
            return None
        recipe, _ = loaded

        for key, value in fields.items():
            if hasattr(recipe, key):
                setattr(recipe, key, value)

        if items is not None:
            await self.session.execute(
                delete(ChargeSkuRecipeItem).where(ChargeSkuRecipeItem.recipe_id == recipe.id)
            )
            for payload in items:
                self.session.add(ChargeSkuRecipeItem(recipe_id=recipe.id, **payload))

        await self.session.commit()
        return await self.get_recipe(recipe_id, owner_id)

    async def delete_recipe(self, recipe_id: int, owner_id: int) -> bool:
        loaded = await self.get_recipe(recipe_id, owner_id)
        if not loaded:
            return False
        await self.session.execute(
            delete(ChargeSkuRecipeItem).where(ChargeSkuRecipeItem.recipe_id == recipe_id)
        )
        await self.session.execute(
            delete(ChargeSkuRecipe).where(
                ChargeSkuRecipe.id == recipe_id,
                ChargeSkuRecipe.owner_id == owner_id,
            )
        )
        await self.session.commit()
        return True

    async def list_categories(
        self,
        platform_config_id: int,
        *,
        only_active: bool = True,
    ) -> list[ChargePlatformCategory]:
        stmt = select(ChargePlatformCategory).where(
            ChargePlatformCategory.platform_config_id == platform_config_id
        )
        if only_active:
            stmt = stmt.where(ChargePlatformCategory.is_active.is_(True))
        stmt = stmt.order_by(
            ChargePlatformCategory.level.asc(),
            ChargePlatformCategory.sort.desc(),
            ChargePlatformCategory.id.asc(),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_goods(
        self,
        platform_config_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
        keyword: str = "",
        class_name_1: str = "",
        class_name_2: str = "",
        only_active: bool = True,
        order_by: str = "price_asc",
    ) -> dict[str, Any]:
        stmt = select(ChargePlatformGoods).where(
            ChargePlatformGoods.platform_config_id == platform_config_id
        )
        count_stmt = (
            select(func.count())
            .select_from(ChargePlatformGoods)
            .where(ChargePlatformGoods.platform_config_id == platform_config_id)
        )

        if only_active:
            stmt = stmt.where(ChargePlatformGoods.is_active.is_(True))
            count_stmt = count_stmt.where(ChargePlatformGoods.is_active.is_(True))
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(ChargePlatformGoods.name.like(like))
            count_stmt = count_stmt.where(ChargePlatformGoods.name.like(like))
        if class_name_1:
            stmt = stmt.where(ChargePlatformGoods.class_name_1 == class_name_1)
            count_stmt = count_stmt.where(ChargePlatformGoods.class_name_1 == class_name_1)
        if class_name_2:
            stmt = stmt.where(ChargePlatformGoods.class_name_2 == class_name_2)
            count_stmt = count_stmt.where(ChargePlatformGoods.class_name_2 == class_name_2)

        if order_by == "price_desc":
            stmt = stmt.order_by(ChargePlatformGoods.price.desc())
        elif order_by == "name_asc":
            stmt = stmt.order_by(ChargePlatformGoods.name.asc())
        else:
            stmt = stmt.order_by(ChargePlatformGoods.price.asc())

        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list((await self.session.execute(stmt)).scalars().all())

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def assert_platform_config_accessible(
        self,
        platform_config_id: int,
        owner_id: int,
        is_admin: bool,
    ) -> ChargePlatformConfig:
        cfg = await self.session.get(ChargePlatformConfig, platform_config_id)
        if not cfg:
            raise ValueError(f"平台账号配置 {platform_config_id} 不存在")
        if not is_admin and cfg.owner_id is not None and cfg.owner_id != owner_id:
            raise ValueError("无权访问该平台账号")
        return cfg

    async def assert_can_sync(
        self,
        platform_config_id: int,
        owner_id: int,
        is_admin: bool,
    ) -> ChargePlatformConfig:
        cfg = await self.assert_platform_config_accessible(platform_config_id, owner_id, is_admin)
        if not cfg.enabled:
            raise ValueError("该平台账号已禁用")
        return cfg

    async def trigger_sync(
        self,
        platform_config_id: int,
        owner_id: int,
        is_admin: bool,
        *,
        sync_categories: bool = True,
        sync_goods: bool = True,
    ) -> dict[str, Any]:
        cfg = await self.assert_can_sync(platform_config_id, owner_id, is_admin)

        service = ChargePlatformSyncService(self.session)
        result: dict[str, Any] = {}
        if sync_categories:
            result["categories"] = await service.sync_categories(cfg)
        if sync_goods:
            result["goods"] = await service.sync_goods(cfg)
        return result
