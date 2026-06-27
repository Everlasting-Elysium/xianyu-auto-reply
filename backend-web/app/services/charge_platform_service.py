"""流量充值平台管理服务（账号配置、套餐映射、订单查询）"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.charge_order import ChargeOrder
from common.models.charge_platform_config import ChargePlatformConfig
from common.models.charge_sku_mapping import ChargeSkuMapping


class ChargePlatformService:
    """流量充值平台管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_configs(
        self,
        owner_id: int | None,
        is_admin: bool,
        page: int = 1,
        page_size: int = 20,
        search: str = "",
    ) -> dict[str, Any]:
        stmt = select(ChargePlatformConfig)
        count_stmt = select(func.count()).select_from(ChargePlatformConfig)

        if not is_admin:
            stmt = stmt.where(
                (ChargePlatformConfig.owner_id == owner_id)
                | (ChargePlatformConfig.owner_id.is_(None))
            )
            count_stmt = count_stmt.where(
                (ChargePlatformConfig.owner_id == owner_id)
                | (ChargePlatformConfig.owner_id.is_(None))
            )

        if search:
            stmt = stmt.where(ChargePlatformConfig.name.contains(search))
            count_stmt = count_stmt.where(ChargePlatformConfig.name.contains(search))

        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(ChargePlatformConfig.id.desc()).offset((page - 1) * page_size).limit(page_size)
        items = (await self.session.execute(stmt)).scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def get_config(self, config_id: int, owner_id: int | None, is_admin: bool) -> ChargePlatformConfig | None:
        stmt = select(ChargePlatformConfig).where(ChargePlatformConfig.id == config_id)
        if not is_admin:
            stmt = stmt.where(
                (ChargePlatformConfig.owner_id == owner_id)
                | (ChargePlatformConfig.owner_id.is_(None))
            )
        return (await self.session.execute(stmt)).scalars().first()

    async def create_config(
        self,
        owner_id: int | None,
        name: str,
        platform_url: str,
        username: str,
        password: str,
        balance_alert_threshold: Any,
        max_orders_per_hour: int,
        enabled: bool,
        remark: str | None,
        extra_config: dict[str, Any] | None,
    ) -> ChargePlatformConfig:
        config = ChargePlatformConfig(
            owner_id=owner_id,
            name=name,
            platform_url=platform_url,
            username=username,
            password=password,
            balance_alert_threshold=balance_alert_threshold,
            max_orders_per_hour=max_orders_per_hour,
            enabled=enabled,
            remark=remark,
            extra_config=extra_config,
        )
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def update_config(
        self,
        config_id: int,
        owner_id: int | None,
        is_admin: bool,
        **fields: Any,
    ) -> ChargePlatformConfig | None:
        config = await self.get_config(config_id, owner_id, is_admin)
        if not config:
            return None
        # 此处依赖路由层用 model_dump(exclude_unset=True) 过滤出"显式传过的字段"
        # 凡进入 fields 的就是用户意图修改的，None 也是合法值（用于清空 nullable 字段）
        # 唯一例外：password 字段如果是 None/空字符串，不应该清空登录密码
        for key, value in fields.items():
            if key == "password" and not value:
                continue
            if hasattr(config, key):
                setattr(config, key, value)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def delete_config(self, config_id: int, owner_id: int | None, is_admin: bool) -> bool:
        config = await self.get_config(config_id, owner_id, is_admin)
        if not config:
            return False
        await self.session.delete(config)
        await self.session.commit()
        return True

    async def list_sku_mappings(
        self,
        owner_id: int | None,
        is_admin: bool = False,
        page: int = 1,
        page_size: int = 50,
        item_id: str = "",
        platform_config_id: int | None = None,
    ) -> dict[str, Any]:
        stmt = select(ChargeSkuMapping)
        count_stmt = select(func.count()).select_from(ChargeSkuMapping)

        if not is_admin:
            stmt = stmt.where(ChargeSkuMapping.owner_id == owner_id)
            count_stmt = count_stmt.where(ChargeSkuMapping.owner_id == owner_id)

        if item_id:
            stmt = stmt.where(ChargeSkuMapping.item_id == item_id)
            count_stmt = count_stmt.where(ChargeSkuMapping.item_id == item_id)
        if platform_config_id is not None:
            stmt = stmt.where(ChargeSkuMapping.platform_config_id == platform_config_id)
            count_stmt = count_stmt.where(ChargeSkuMapping.platform_config_id == platform_config_id)

        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(ChargeSkuMapping.id.desc()).offset((page - 1) * page_size).limit(page_size)
        items = (await self.session.execute(stmt)).scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def get_sku_mapping(self, mapping_id: int, owner_id: int) -> ChargeSkuMapping | None:
        stmt = select(ChargeSkuMapping).where(
            ChargeSkuMapping.id == mapping_id,
            ChargeSkuMapping.owner_id == owner_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def create_sku_mapping(
        self,
        owner_id: int,
        platform_config_id: int,
        item_id: str,
        spec_value: str | None,
        platform_sku_id: str,
        platform_sku_name: str | None,
        is_active: bool,
        remark: str | None,
    ) -> ChargeSkuMapping:
        platform_cfg_stmt = select(ChargePlatformConfig).where(ChargePlatformConfig.id == platform_config_id)
        platform_cfg = (await self.session.execute(platform_cfg_stmt)).scalars().first()
        if not platform_cfg:
            raise ValueError("指定的平台账号配置不存在")
        if platform_cfg.owner_id is not None and platform_cfg.owner_id != owner_id:
            raise ValueError("无权使用该平台账号配置")

        existing_stmt = select(ChargeSkuMapping).where(
            ChargeSkuMapping.owner_id == owner_id,
            ChargeSkuMapping.item_id == item_id,
            ChargeSkuMapping.spec_value.is_(None) if spec_value is None
            else ChargeSkuMapping.spec_value == spec_value,
        )
        existing = (await self.session.execute(existing_stmt)).scalars().first()
        if existing:
            raise ValueError("该商品 + 规格的映射已存在")

        mapping = ChargeSkuMapping(
            owner_id=owner_id,
            platform_config_id=platform_config_id,
            item_id=item_id,
            spec_value=spec_value,
            platform_sku_id=platform_sku_id,
            platform_sku_name=platform_sku_name,
            is_active=is_active,
            remark=remark,
        )
        self.session.add(mapping)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def update_sku_mapping(
        self,
        mapping_id: int,
        owner_id: int,
        **fields: Any,
    ) -> ChargeSkuMapping | None:
        mapping = await self.get_sku_mapping(mapping_id, owner_id)
        if not mapping:
            return None
        for key, value in fields.items():
            if hasattr(mapping, key):
                setattr(mapping, key, value)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def delete_sku_mapping(self, mapping_id: int, owner_id: int) -> bool:
        result = await self.session.execute(
            delete(ChargeSkuMapping).where(
                ChargeSkuMapping.id == mapping_id,
                ChargeSkuMapping.owner_id == owner_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def list_orders(
        self,
        owner_id: int | None,
        is_admin: bool = False,
        page: int = 1,
        page_size: int = 20,
        status: str = "",
        xy_order_no: str = "",
    ) -> dict[str, Any]:
        stmt = select(ChargeOrder)
        count_stmt = select(func.count()).select_from(ChargeOrder)

        if not is_admin:
            stmt = stmt.where(ChargeOrder.owner_id == owner_id)
            count_stmt = count_stmt.where(ChargeOrder.owner_id == owner_id)

        if status:
            stmt = stmt.where(ChargeOrder.status == status)
            count_stmt = count_stmt.where(ChargeOrder.status == status)
        if xy_order_no:
            stmt = stmt.where(ChargeOrder.xy_order_no == xy_order_no)
            count_stmt = count_stmt.where(ChargeOrder.xy_order_no == xy_order_no)

        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(ChargeOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)
        items = (await self.session.execute(stmt)).scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def get_order(self, order_id: int, owner_id: int) -> ChargeOrder | None:
        stmt = select(ChargeOrder).where(
            ChargeOrder.id == order_id,
            ChargeOrder.owner_id == owner_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def retry_order(self, order_id: int, owner_id: int, reset_retry_count: bool) -> ChargeOrder | None:
        order = await self.get_order(order_id, owner_id)
        if not order:
            return None
        if order.status not in ("failed", "partial_success", "needs_review"):
            raise ValueError(f"当前状态 {order.status} 不允许重试")
        order.status = "pending"
        order.next_retry_at = None
        order.fail_reason = None
        if reset_retry_count:
            order.retry_count = 0
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def cancel_order(self, order_id: int, owner_id: int) -> ChargeOrder | None:
        order = await self.get_order(order_id, owner_id)
        if not order:
            return None
        if order.status in ("success", "cancelled"):
            raise ValueError(f"当前状态 {order.status} 不允许取消")
        order.status = "cancelled"
        await self.session.commit()
        await self.session.refresh(order)
        return order
