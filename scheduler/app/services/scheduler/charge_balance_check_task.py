"""代刷平台账号余额定时检查任务（默认每 15min，余额低于阈值时触发告警通知）"""
from __future__ import annotations

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import async_session_maker
from common.models.charge_platform_config import ChargePlatformConfig
from common.services.charge_platform_client import (
    ChargePlatformAuthError,
    ChargePlatformClient,
    ChargePlatformError,
)


class ChargeBalanceCheckTask:
    """定时刷新所有启用的代刷平台账号的余额（触发 client 内部的 balance_low 状态切换 + 通知）"""

    async def execute(self) -> str:
        logger.info("[charge-balance-check] 开始执行")
        try:
            async with async_session_maker() as session:
                configs = await self._list_enabled_configs(session)
                if not configs:
                    msg = "无启用的代刷平台账号，跳过"
                    logger.info(f"[charge-balance-check] {msg}")
                    return msg

                results: list[str] = []
                for cfg in configs:
                    summary = await self._check_one(cfg)
                    results.append(summary)
                msg = "; ".join(results)
                logger.info(f"[charge-balance-check] 执行完成: {msg}")
                return msg
        except Exception as e:
            logger.error(f"[charge-balance-check] 执行异常: {e}")
            return f"执行异常: {e}"

    async def _list_enabled_configs(self, session: AsyncSession) -> list[ChargePlatformConfig]:
        stmt = select(ChargePlatformConfig).where(ChargePlatformConfig.enabled.is_(True))
        return list((await session.execute(stmt)).scalars().all())

    async def _check_one(self, cfg: ChargePlatformConfig) -> str:
        client = ChargePlatformClient(cfg)
        try:
            balance = await client.get_balance()
            return f"platform={cfg.id} balance={balance}"
        except ChargePlatformAuthError as e:
            logger.warning(f"[charge-balance-check] platform={cfg.id} 鉴权失败: {e}")
            return f"platform={cfg.id} 鉴权失败"
        except ChargePlatformError as e:
            logger.warning(f"[charge-balance-check] platform={cfg.id} 业务异常: {e}")
            return f"platform={cfg.id} 业务异常"
        except Exception as e:
            logger.warning(f"[charge-balance-check] platform={cfg.id} 未知异常: {type(e).__name__}: {e}")
            return f"platform={cfg.id} 异常"
        finally:
            await client.close()


charge_balance_check_task_service = ChargeBalanceCheckTask()
