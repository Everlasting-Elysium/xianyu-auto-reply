"""代刷平台分类/商品定时同步任务（默认每 6h）"""
from __future__ import annotations

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import async_session_maker
from common.models.charge_platform_config import ChargePlatformConfig
from common.services.charge_platform_sync_service import ChargePlatformSyncService


class ChargePlatformSyncTask:
    """定时同步所有启用的代刷平台账号的分类树和商品仓库"""

    async def execute(self) -> str:
        logger.info("[charge-platform-sync] 开始执行")
        try:
            async with async_session_maker() as session:
                configs = await self._list_enabled_configs(session)
                if not configs:
                    msg = "无启用的代刷平台账号，跳过"
                    logger.info(f"[charge-platform-sync] {msg}")
                    return msg

                results: list[str] = []
                for cfg in configs:
                    summary = await self._sync_one(session, cfg)
                    results.append(summary)
                msg = "; ".join(results)
                logger.info(f"[charge-platform-sync] 执行完成: {msg}")
                return msg
        except Exception as e:
            logger.error(f"[charge-platform-sync] 执行异常: {e}")
            return f"执行异常: {e}"

    async def _list_enabled_configs(self, session: AsyncSession) -> list[ChargePlatformConfig]:
        stmt = select(ChargePlatformConfig).where(
            ChargePlatformConfig.enabled.is_(True),
            ChargePlatformConfig.status.in_(("active", "balance_low")),
        )
        return list((await session.execute(stmt)).scalars().all())

    async def _sync_one(self, session: AsyncSession, cfg: ChargePlatformConfig) -> str:
        try:
            service = ChargePlatformSyncService(session)
            cat = await service.sync_categories(cfg)
            goods = await service.sync_goods(cfg)
            return (
                f"platform={cfg.id} cat=({cat['inserted']}+{cat['updated']}/{cat['total_seen']}) "
                f"goods=({goods['inserted']}+{goods['updated']}/{goods['total_seen']} "
                f"full={goods.get('fully_traversed', 0)})"
            )
        except Exception as e:
            logger.error(f"[charge-platform-sync] platform={cfg.id} 同步失败: {e}")
            return f"platform={cfg.id} 失败:{type(e).__name__}"


charge_platform_sync_task_service = ChargePlatformSyncTask()
