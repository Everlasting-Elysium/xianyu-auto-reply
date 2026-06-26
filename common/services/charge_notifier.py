"""
代刷模块通知工具

直接复用项目的 common.utils.notification_utils 多渠道发送函数。
不依赖 websocket 服务的 NotificationManager（避免反向依赖），但行为对齐：
- 按 owner_id 查 NotificationChannel
- 多渠道并发发送
- 失败不抛异常（通知是 best-effort，不能阻塞业务）

冷却策略：当前简化为每次发送，不做去重（charge 事件本身比 IM 消息低频）。
如果未来出现刷屏问题，可加内存级简单去重。
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import async_session_maker
from common.models.notification_channel import NotificationChannel
from common.utils.notification_utils import (
    parse_notification_config,
    send_bark_notification,
    send_dingtalk_notification,
    send_email_notification,
    send_feishu_notification,
    send_telegram_notification,
    send_webhook_notification,
    send_wechat_notification,
)


CHANNEL_SENDERS = {
    "dingtalk": send_dingtalk_notification,
    "feishu": send_feishu_notification,
    "bark": send_bark_notification,
    "email": send_email_notification,
    "webhook": send_webhook_notification,
    "wechat": send_wechat_notification,
    "telegram": send_telegram_notification,
}


async def _load_channels(session: AsyncSession, owner_id: int) -> list[NotificationChannel]:
    stmt = select(NotificationChannel).where(
        NotificationChannel.owner_id == owner_id,
        NotificationChannel.enabled.is_(True),
    )
    return list((await session.execute(stmt)).scalars().all())


async def _send_via_channel(channel: NotificationChannel, message: str) -> bool:
    sender = CHANNEL_SENDERS.get(channel.channel_type)
    if not sender:
        logger.warning(f"[charge-notify] 未知通知渠道类型: {channel.channel_type}")
        return False
    try:
        config_data = parse_notification_config(channel.config_payload)
        return await sender(config_data, message)
    except Exception as e:
        logger.warning(f"[charge-notify] 渠道 {channel.name} ({channel.channel_type}) 发送失败: {e}")
        return False


async def notify_owner(
    owner_id: int | None,
    title: str,
    message: str,
    *,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    if owner_id is None:
        logger.info(f"[charge-notify] owner_id 为 None（系统级配置），跳过通知: {title}")
        return {"sent": 0, "failed": 0}

    full_message = f"【{title}】\n{message}"

    async def _do_notify(s: AsyncSession) -> dict[str, Any]:
        channels = await _load_channels(s, owner_id)
        if not channels:
            logger.info(f"[charge-notify] owner={owner_id} 未配置任何通知渠道，跳过: {title}")
            return {"sent": 0, "failed": 0}

        results = await asyncio.gather(
            *[_send_via_channel(ch, full_message) for ch in channels],
            return_exceptions=True,
        )
        sent = sum(1 for r in results if r is True)
        failed = len(results) - sent
        logger.info(f"[charge-notify] owner={owner_id} 通知发送 sent={sent} failed={failed}: {title}")
        return {"sent": sent, "failed": failed}

    try:
        if session is not None:
            return await _do_notify(session)
        async with async_session_maker() as own_session:
            return await _do_notify(own_session)
    except Exception as e:
        logger.warning(f"[charge-notify] 通知整体流程异常: {e}")
        return {"sent": 0, "failed": -1}
