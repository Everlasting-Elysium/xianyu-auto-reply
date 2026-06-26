"""
xckj9 平台分类树与商品仓库同步服务

将远端 xckj9 数据缓存到本地三张表，供后台 UI 和选品引擎使用：
- charge_platform_categories: 分类树
- charge_platform_goods: 商品全量缓存（含 ParamsTemplate）

注意：
- 商品库可能有数千条，分页拉取（默认每页 50，最大拉取 500 页）
- 同步采用 upsert 语义（按 platform_goods_id 唯一索引）
- 长时间未出现在远端的商品会标记 is_active=False（软删除）
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import async_session_maker
from common.models.charge_platform_category import ChargePlatformCategory
from common.models.charge_platform_config import ChargePlatformConfig
from common.models.charge_platform_goods import ChargePlatformGoods
from common.services.charge_platform_client import ChargePlatformClient


DEFAULT_GOODS_PAGE_SIZE = 50
MAX_GOODS_PAGES = 500


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value)) if value is not None else Decimal(default)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


class ChargePlatformSyncService:
    """xckj9 数据同步服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_categories(self, config: ChargePlatformConfig) -> dict[str, int]:
        client = ChargePlatformClient(config)
        try:
            raw_tree = await client.get_goods_class_list()
        finally:
            await client.close()

        flat: list[dict[str, Any]] = []
        self._flatten_categories(raw_tree, flat)

        synced_at = datetime.now(timezone.utc)
        inserted = updated = 0
        seen_ids: list[int] = []

        for cat in flat:
            pcid = _to_int(cat.get("Id"))
            if not pcid:
                continue
            seen_ids.append(pcid)

            stmt = select(ChargePlatformCategory).where(
                ChargePlatformCategory.platform_config_id == config.id,
                ChargePlatformCategory.platform_category_id == pcid,
            )
            existing = (await self.session.execute(stmt)).scalars().first()

            payload: dict[str, Any] = {
                "parent_id": _to_int(cat.get("ParentId")),
                "name": str(cat.get("Name") or "")[:128],
                "level": _to_int(cat.get("Level"), 1),
                "sort": _to_int(cat.get("Sort")),
                "thumb": cat.get("CategoryThumb"),
                "is_active": _to_int(cat.get("Status")) == 1,
                "last_synced_at": synced_at,
            }

            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                self.session.add(ChargePlatformCategory(
                    platform_config_id=config.id,
                    platform_category_id=pcid,
                    **payload,
                ))
                inserted += 1

        if seen_ids:
            await self.session.execute(
                update(ChargePlatformCategory)
                .where(
                    ChargePlatformCategory.platform_config_id == config.id,
                    ChargePlatformCategory.platform_category_id.not_in(seen_ids),
                    ChargePlatformCategory.is_active.is_(True),
                )
                .values(is_active=False, last_synced_at=synced_at)
            )

        await self.session.commit()
        result = {"inserted": inserted, "updated": updated, "total_seen": len(seen_ids)}
        logger.info(f"[charge-sync] platform={config.id} categories: {result}")
        return result

    def _flatten_categories(self, tree: list[dict[str, Any]], out: list[dict[str, Any]]) -> None:
        for node in tree:
            out.append(node)
            children = node.get("Childern") or node.get("Children") or []
            if children:
                self._flatten_categories(children, out)

    async def sync_goods(
        self,
        config: ChargePlatformConfig,
        *,
        page_size: int = DEFAULT_GOODS_PAGE_SIZE,
        max_pages: int = MAX_GOODS_PAGES,
        delay_between_pages: float = 0.2,
    ) -> dict[str, int]:
        client = ChargePlatformClient(config)
        synced_at = datetime.now(timezone.utc)
        inserted = updated = total = 0
        seen_goods_ids: list[str] = []
        fully_traversed = False

        try:
            for page in range(1, max_pages + 1):
                items = await client.list_goods(page=page, page_count=page_size)
                if not items:
                    fully_traversed = True
                    break

                for item in items:
                    gid_str = str(item.get("Id") or "")
                    if not gid_str:
                        continue

                    seen_goods_ids.append(gid_str)
                    total += 1

                    stmt = select(ChargePlatformGoods).where(
                        ChargePlatformGoods.platform_config_id == config.id,
                        ChargePlatformGoods.platform_goods_id == gid_str,
                    )
                    existing = (await self.session.execute(stmt)).scalars().first()

                    payload: dict[str, Any] = {
                        "gid": item.get("Gid"),
                        "name": str(item.get("GoodsName") or "")[:256],
                        "class_name_1": item.get("ClassName1"),
                        "class_name_2": item.get("ClassName2"),
                        "class_name_3": item.get("ClassName3"),
                        "price": _to_decimal(item.get("GoodsPrice")),
                        "stock": _to_int(item.get("GoodsStock"), -1),
                        "min_order_num": _to_int(item.get("MinOrderNum"), 1),
                        "max_order_num": _to_int(item.get("MaxOrderNum"), 0),
                        "unit": item.get("GoodsUnit"),
                        "goods_type": _to_int(item.get("GoodsType")) or None,
                        "params_template": item.get("ParamsTemplate"),
                        "thumb": item.get("GoodsThumb"),
                        "is_active": _to_int(item.get("IsClose")) == 2,
                        "last_synced_at": synced_at,
                    }

                    if existing:
                        for key, value in payload.items():
                            setattr(existing, key, value)
                        updated += 1
                    else:
                        self.session.add(ChargePlatformGoods(
                            platform_config_id=config.id,
                            platform_goods_id=gid_str,
                            **payload,
                        ))
                        inserted += 1

                if len(items) < page_size:
                    fully_traversed = True
                    break

                if (page % 5) == 0:
                    await self.session.commit()
                    logger.info(f"[charge-sync] platform={config.id} synced {total} goods so far (page {page})")

                if delay_between_pages > 0:
                    await asyncio.sleep(delay_between_pages)
        finally:
            await client.close()

        if fully_traversed and seen_goods_ids:
            await self.session.execute(
                update(ChargePlatformGoods)
                .where(
                    ChargePlatformGoods.platform_config_id == config.id,
                    ChargePlatformGoods.platform_goods_id.not_in(seen_goods_ids),
                    ChargePlatformGoods.is_active.is_(True),
                )
                .values(is_active=False, last_synced_at=synced_at)
            )
        elif not fully_traversed:
            logger.warning(
                f"[charge-sync] platform={config.id} 未完整遍历商品库（max_pages={max_pages} 已到达）；"
                f"跳过软删除步骤，避免误杀超出页数的正常商品"
            )

        await self.session.commit()
        result = {
            "inserted": inserted,
            "updated": updated,
            "total_seen": len(seen_goods_ids),
            "fully_traversed": int(fully_traversed),
        }
        logger.info(f"[charge-sync] platform={config.id} goods: {result}")
        return result

    async def sync_all(self, config: ChargePlatformConfig) -> dict[str, Any]:
        categories = await self.sync_categories(config)
        goods = await self.sync_goods(config)
        return {"categories": categories, "goods": goods}


async def sync_platform_by_id(config_id: int) -> dict[str, Any]:
    async with async_session_maker() as session:
        cfg = await session.get(ChargePlatformConfig, config_id)
        if not cfg:
            raise ValueError(f"平台账号配置 {config_id} 不存在")
        if not cfg.enabled:
            raise ValueError(f"平台账号配置 {config_id} 已禁用")
        service = ChargePlatformSyncService(session)
        return await service.sync_all(cfg)
