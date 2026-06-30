"""
xckj9 社交媒体代刷平台 HTTP 客户端

功能：
1. 账号密码登录，获取 ACCESS_TOKEN
2. Token 持久化：Redis 主存储（TTL 12h）+ DB session_json 备份
3. 业务接口：查余额、查商品分类/列表、批量下单（OrderParams 双层数组）、查订单
4. Token 失效自动重登（401 / Token 鉴权失败）
5. 兼容平台多种响应格式：{error, info} 包装 / raw payload / raw list
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from common.utils.time_utils import get_beijing_now_naive
from decimal import Decimal
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.redis_client import get_redis_client
from common.db.session import async_session_maker
from common.models.charge_platform_config import ChargePlatformConfig


REDIS_TOKEN_KEY = "charge_platform:token:{config_id}"
REDIS_TOKEN_TTL_SECONDS = 12 * 60 * 60

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class ChargePlatformError(Exception):
    """平台业务异常（与 HTTP 异常区分）"""

    def __init__(self, message: str, *, raw: dict[str, Any] | None = None):
        super().__init__(message)
        self.raw = raw or {}


class ChargePlatformAuthError(ChargePlatformError):
    """需要重新登录的异常（401/Token 过期）"""


class ChargePlatformClient:
    """xckj9 流量充值平台客户端

    Session 管理设计说明（与项目通用 service 不同）：
    本 client 的 token 持久化（_save_token / _invalidate_token）需要独立于业务事务，
    因此内部使用 async_session_maker() 自己管理短事务。
    业务事务回滚不应导致 token 状态变化（否则下次调用又会触发昂贵的重登流程）。
    所有 DB 操作都包了 try/except，DB 异常不会传播给业务层。
    """

    def __init__(self, config: ChargePlatformConfig, *, timeout: float = 15.0):
        self.config = config
        self.config_id = config.id
        self.base_url = config.platform_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/indexPc.html",
            },
            follow_redirects=True,
        )
        self._token: str | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "ChargePlatformClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def ensure_token(self, *, force_relogin: bool = False) -> str:
        if not force_relogin:
            cached = await self._load_token_from_cache()
            if cached:
                self._token = cached
                return cached

        token = await self._do_login()
        await self._save_token(token)
        self._token = token
        return token

    async def _load_token_from_cache(self) -> str | None:
        try:
            client = await get_redis_client()
            token = await client.get(REDIS_TOKEN_KEY.format(config_id=self.config_id))
            if token:
                logger.debug(f"[charge-platform:{self.config_id}] token loaded from Redis")
                return token
        except Exception as e:
            logger.warning(f"[charge-platform:{self.config_id}] Redis 读取 token 失败: {e}")

        if self.config.session_json:
            saved_token = self.config.session_json.get("access_token")
            expires_at = self.config.session_expires_at
            if saved_token and (not expires_at or expires_at > get_beijing_now_naive()):
                logger.debug(f"[charge-platform:{self.config_id}] token loaded from DB backup")
                return saved_token

        return None

    async def _save_token(self, token: str) -> None:
        try:
            client = await get_redis_client()
            await client.set(
                REDIS_TOKEN_KEY.format(config_id=self.config_id),
                token,
                ex=REDIS_TOKEN_TTL_SECONDS,
            )
        except Exception as e:
            logger.warning(f"[charge-platform:{self.config_id}] Redis 保存 token 失败: {e}")

        try:
            async with async_session_maker() as session:
                cfg = await session.get(ChargePlatformConfig, self.config_id)
                if not cfg:
                    return
                cfg.session_json = {"access_token": token, "saved_at": get_beijing_now_naive().isoformat()}
                cfg.session_expires_at = get_beijing_now_naive() + timedelta(seconds=REDIS_TOKEN_TTL_SECONDS)
                cfg.last_login_at = get_beijing_now_naive()
                cfg.last_error = None
                cfg.last_error_at = None
                await session.commit()
        except Exception as e:
            logger.warning(f"[charge-platform:{self.config_id}] token DB 备份写入失败: {e}")

    async def _invalidate_token(self, reason: str) -> None:
        self._token = None
        try:
            client = await get_redis_client()
            await client.delete(REDIS_TOKEN_KEY.format(config_id=self.config_id))
        except Exception:
            pass
        try:
            async with async_session_maker() as session:
                cfg = await session.get(ChargePlatformConfig, self.config_id)
                if cfg:
                    cfg.session_json = None
                    cfg.session_expires_at = None
                    cfg.last_error = f"token invalidated: {reason}"
                    cfg.last_error_at = get_beijing_now_naive()
                    await session.commit()
        except Exception as e:
            logger.warning(f"[charge-platform:{self.config_id}] token DB 失效标记写库异常: {e}")

    async def _do_login(self) -> str:
        logger.info(f"[charge-platform:{self.config_id}] 执行登录: {self.config.username}")
        resp = await self._client.post(
            "/api/login",
            data={"UserName": self.config.username, "Pwd": self.config.password},
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        try:
            body = resp.json()
        except Exception as e:
            raise ChargePlatformError(f"登录响应非 JSON: {resp.text[:200]}") from e

        if body.get("error") == 0 and body.get("info"):
            logger.info(f"[charge-platform:{self.config_id}] 登录成功")
            return body["info"]

        message = body.get("info") or "未知错误"
        await self._mark_login_failed(message)
        raise ChargePlatformAuthError(f"登录失败: {message}", raw=body)

    async def _mark_login_failed(self, reason: str) -> None:
        owner_id_for_notify: int | None = None
        platform_name = self.config.name
        try:
            async with async_session_maker() as session:
                cfg = await session.get(ChargePlatformConfig, self.config_id)
                if cfg:
                    cfg.status = "login_failed"
                    cfg.last_error = reason
                    cfg.last_error_at = get_beijing_now_naive()
                    await session.commit()
                    owner_id_for_notify = cfg.owner_id
        except Exception as e:
            logger.warning(f"[charge-platform:{self.config_id}] 标记登录失败状态写库异常: {e}")

        try:
            from common.services.charge_notifier import notify_owner
            await notify_owner(
                owner_id_for_notify,
                title="代刷平台账号登录失败",
                message=f"平台账号「{platform_name}」(配置 id={self.config_id}) 登录失败\n原因: {reason}",
            )
        except Exception as e:
            logger.warning(f"[charge-platform:{self.config_id}] 登录失败通知异常: {e}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        _retried: bool = False,
    ) -> Any:
        token = self._token or await self.ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }

        resp = await self._client.request(method, path, params=params, data=data, headers=headers)

        if resp.status_code in (401, 403):
            if _retried:
                raise ChargePlatformAuthError(f"重新登录后仍鉴权失败: {resp.status_code}")
            logger.warning(f"[charge-platform:{self.config_id}] {resp.status_code} 触发重登")
            await self._invalidate_token(f"http {resp.status_code}")
            await self.ensure_token(force_relogin=True)
            return await self._request(method, path, params=params, data=data, _retried=True)

        if resp.status_code >= 400:
            raise ChargePlatformError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            body = resp.json()
        except Exception as e:
            raise ChargePlatformError(f"响应非 JSON: {resp.text[:200]}") from e

        if (
            not _retried
            and isinstance(body, dict)
            and body.get("error") in (401, "401")
            and isinstance(body.get("info"), str)
            and any(kw in body["info"] for kw in ("登录", "token", "鉴权"))
        ):
            logger.warning(f"[charge-platform:{self.config_id}] 业务码识别为未登录, 重登重试")
            await self._invalidate_token("business code suggests not logged in")
            await self.ensure_token(force_relogin=True)
            return await self._request(method, path, params=params, data=data, _retried=True)

        return body

    async def get_user_info(self) -> dict[str, Any]:
        body = await self._request("POST", "/api/userInfo", data={"Switch": 4})
        if not isinstance(body, dict):
            raise ChargePlatformError(f"userInfo 响应不是对象: {type(body).__name__}")
        if body.get("error") and not body.get("Id"):
            raise ChargePlatformError(f"查询用户信息失败: {body.get('info')}", raw=body)
        return body

    async def get_balance(self) -> Decimal:
        info = await self.get_user_info()
        raw_balance = (
            info.get("Balance")
            or info.get("Money")
            or info.get("AllMoney")
            or "0"
        )
        balance = Decimal(str(raw_balance))
        await self._update_balance_cache(balance)
        return balance

    async def _update_balance_cache(self, balance: Decimal) -> None:
        should_notify_low = False
        owner_id_for_notify: int | None = None
        platform_name = self.config.name
        threshold = self.config.balance_alert_threshold
        try:
            async with async_session_maker() as session:
                cfg = await session.get(ChargePlatformConfig, self.config_id)
                if cfg:
                    cfg.balance = balance
                    cfg.balance_checked_at = get_beijing_now_naive()
                    if balance < cfg.balance_alert_threshold and cfg.status == "active":
                        cfg.status = "balance_low"
                        should_notify_low = True
                        owner_id_for_notify = cfg.owner_id
                        threshold = cfg.balance_alert_threshold
                    elif balance >= cfg.balance_alert_threshold and cfg.status == "balance_low":
                        cfg.status = "active"
                    await session.commit()
        except Exception as e:
            logger.warning(f"[charge-platform:{self.config_id}] 余额缓存写库异常: {e}")

        if should_notify_low:
            try:
                from common.services.charge_notifier import notify_owner
                await notify_owner(
                    owner_id_for_notify,
                    title="代刷平台余额告警",
                    message=(
                        f"平台账号「{platform_name}」(配置 id={self.config_id}) 余额过低\n"
                        f"当前余额: ¥{balance}\n告警阈值: ¥{threshold}\n"
                        f"请尽快充值，否则后续代刷订单将失败。"
                    ),
                )
            except Exception as e:
                logger.warning(f"[charge-platform:{self.config_id}] 余额告警通知异常: {e}")

    async def get_goods_class_list(self) -> list[dict[str, Any]]:
        body = await self._request("GET", "/api/goodsClassList")
        if isinstance(body, list):
            return body
        if isinstance(body, dict) and body.get("error") == 0 and isinstance(body.get("info"), list):
            return body["info"]
        raise ChargePlatformError(f"商品分类响应异常: {str(body)[:200]}", raw=body if isinstance(body, dict) else {"raw": body})

    async def list_goods(
        self,
        *,
        page: int = 1,
        page_count: int = 20,
        keyword: str = "",
        class_id: int | str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"Page": page, "PageCount": page_count}
        if keyword:
            params["Keyword"] = keyword
        if class_id is not None:
            params["ClassId"] = class_id
        body = await self._request("GET", "/api/goodsList", params=params)
        if isinstance(body, dict) and body.get("error") == 0:
            info = body.get("info") or []
            return info if isinstance(info, list) else []
        raise ChargePlatformError(f"查询商品列表失败: {body.get('info') if isinstance(body, dict) else body}", raw=body if isinstance(body, dict) else {"raw": body})

    async def get_goods_detail(self, goods_id: str | int) -> dict[str, Any]:
        body = await self._request("GET", "/api/goodsDetail", params={"Id": goods_id})
        if isinstance(body, dict) and "Id" in body and "GoodsName" in body:
            return body
        if isinstance(body, dict) and body.get("error") == 0 and isinstance(body.get("info"), dict):
            return body["info"]
        raise ChargePlatformError(f"查询商品详情失败: {str(body)[:200]}", raw=body if isinstance(body, dict) else {"raw": body})

    async def create_order(
        self,
        *,
        goods_id: str | int,
        quantity: int,
        params: list[dict[str, Any]],
        cf_count: int = 0,
        exp_time: datetime | None = None,
        zx_type: int = 1,
    ) -> dict[str, Any]:
        exp_time = exp_time or get_beijing_now_naive()
        order_params = [params]

        payload = {
            "GoodsIds": str(goods_id),
            "OrderNum": str(quantity),
            "CfCount": str(cf_count),
            "OrderParams": json.dumps(order_params, ensure_ascii=False),
            "ExpTime": exp_time.strftime("%Y-%m-%d %H:%M:%S"),
            "ExeTime": 0,
            "ZxType": zx_type,
        }
        body = await self._request("POST", "/api/createOrder", data=payload)
        if not isinstance(body, dict):
            raise ChargePlatformError(f"createOrder 响应异常: {body}")

        if body.get("error") != 0:
            raise ChargePlatformError(f"下单失败: {body.get('info')}", raw=body)

        try:
            inner = json.loads(body.get("info") or "[]")
        except Exception as e:
            raise ChargePlatformError(f"下单响应 info 不是 JSON: {body.get('info')}") from e

        if not isinstance(inner, list) or not inner:
            raise ChargePlatformError(f"下单结果数组为空: {inner}", raw=body)

        first = inner[0] if isinstance(inner[0], dict) else {}
        if first.get("error") != 0:
            raise ChargePlatformError(f"下单失败: {first.get('msg') or first}", raw={"outer": body, "inner": inner})

        return first

    async def get_order_detail(self, order_id: str | int) -> dict[str, Any]:
        body = await self._request("GET", "/api/orderDetail", params={"Id": order_id})
        if isinstance(body, dict) and body.get("error") == 0:
            info = body.get("info")
            return info if isinstance(info, dict) else {"raw": info}
        if isinstance(body, dict) and "Id" in body:
            return body
        raise ChargePlatformError(f"查询订单详情失败: {str(body)[:200]}", raw=body if isinstance(body, dict) else {"raw": body})

    async def list_orders(self, *, page: int = 1, page_count: int = 20) -> list[dict[str, Any]]:
        body = await self._request("GET", "/api/orderList", params={"Page": page, "PageCount": page_count})
        if isinstance(body, dict) and body.get("error") == 0:
            info = body.get("info") or []
            return info if isinstance(info, list) else []
        raise ChargePlatformError(f"查询订单列表失败: {str(body)[:200]}", raw=body if isinstance(body, dict) else {"raw": body})

    @staticmethod
    def build_order_params(template: list[dict[str, Any]] | str, values: dict[str, str]) -> list[dict[str, str]]:
        if isinstance(template, str):
            try:
                template = json.loads(template)
            except Exception as e:
                raise ChargePlatformError(f"ParamsTemplate 不是合法 JSON: {template[:100]}") from e
        if not isinstance(template, list):
            raise ChargePlatformError(f"ParamsTemplate 应为数组: {type(template).__name__}")

        result: list[dict[str, str]] = []
        for field in template:
            key = field.get("key", "")
            if not key:
                continue
            value = values.get(key)
            if value is None:
                raise ChargePlatformError(f"下单参数缺少字段 '{key}' (name={field.get('name')})")
            result.append({
                "name": field.get("name") or key,
                "alias": key,
                "value": str(value),
            })
        return result


async def _load_config(session: AsyncSession, config_id: int) -> ChargePlatformConfig:
    stmt = select(ChargePlatformConfig).where(ChargePlatformConfig.id == config_id)
    cfg = (await session.execute(stmt)).scalars().first()
    if not cfg:
        raise ChargePlatformError(f"平台账号配置 {config_id} 不存在")
    if not cfg.enabled:
        raise ChargePlatformError(f"平台账号配置 {config_id} 已禁用")
    return cfg


async def get_client_by_config_id(
    config_id: int,
    session: AsyncSession | None = None,
) -> ChargePlatformClient:
    if session is not None:
        cfg = await _load_config(session, config_id)
    else:
        async with async_session_maker() as own_session:
            cfg = await _load_config(own_session, config_id)
    return ChargePlatformClient(cfg)
