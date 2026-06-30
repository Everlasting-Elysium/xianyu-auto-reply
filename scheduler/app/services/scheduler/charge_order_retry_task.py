"""代刷主单失败/待处理订单定时重试任务（默认每 5min）"""
from __future__ import annotations

from datetime import timedelta

from common.utils.time_utils import get_beijing_now_naive

from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import async_session_maker
from common.models.charge_order import ChargeOrder
from common.services.charge_order_executor import ChargeOrderExecutor


MAX_BATCH_PER_RUN = 20
DEFAULT_BACKOFF_FACTOR_MINUTES = 5


class ChargeOrderRetryTask:
    """扫描 failed/pending 状态的主单，按 retry_count < max_retries 批量重新执行"""

    async def execute(self) -> str:
        logger.info("[charge-order-retry] 开始执行")
        try:
            async with async_session_maker() as session:
                orders = await self._list_retryable(session)
                if not orders:
                    msg = "无可重试订单"
                    logger.info(f"[charge-order-retry] {msg}")
                    return msg

                success = failed = 0
                for order in orders[:MAX_BATCH_PER_RUN]:
                    outcome = await self._retry_one(session, order.id)
                    if outcome:
                        success += 1
                    else:
                        failed += 1

                msg = f"重试 {success + failed} 单：成功 {success} 失败 {failed}"
                logger.info(f"[charge-order-retry] 执行完成: {msg}")
                return msg
        except Exception as e:
            logger.error(f"[charge-order-retry] 执行异常: {e}")
            return f"执行异常: {e}"

    async def _list_retryable(self, session: AsyncSession) -> list[ChargeOrder]:
        now = get_beijing_now_naive()
        stmt = (
            select(ChargeOrder)
            .where(
                ChargeOrder.status.in_(("failed", "partial_success", "pending")),
                ChargeOrder.retry_count < ChargeOrder.max_retries,
                or_(
                    ChargeOrder.next_retry_at.is_(None),
                    ChargeOrder.next_retry_at <= now,
                ),
            )
            .order_by(ChargeOrder.id.asc())
            .limit(MAX_BATCH_PER_RUN)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def _retry_one(self, session: AsyncSession, order_id: int) -> bool:
        order = await session.get(ChargeOrder, order_id)
        if not order:
            return False

        if order.status in ("failed", "partial_success"):
            order.status = "pending"
        order.retry_count = (order.retry_count or 0) + 1
        backoff_minutes = DEFAULT_BACKOFF_FACTOR_MINUTES * (2 ** order.retry_count)
        order.next_retry_at = get_beijing_now_naive() + timedelta(minutes=backoff_minutes)
        await session.commit()

        try:
            result = await ChargeOrderExecutor(session).execute(order_id)
            logger.info(
                f"[charge-order-retry] order={order_id} retry={order.retry_count} → {result.final_status}"
            )
            return result.final_status in ("success", "partial_success")
        except Exception as e:
            logger.warning(f"[charge-order-retry] order={order_id} 重试异常: {e}")
            return False


charge_order_retry_task_service = ChargeOrderRetryTask()
