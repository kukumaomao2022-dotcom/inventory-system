import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InventoryEvent, InventorySnapshot, SkuMaster, SourceEnum, Store
from app.db.schemas import EventTypeEnumSchema, SourceEnumSchema
from app.services.rakuten_api import RakutenAPIError, get_rakuten_client
from app.utils.helpers import normalize_sku, utcnow

logger = logging.getLogger(__name__)


class OrderPollingService:
    """订单轮询服务 - 从乐天获取订单并处理"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def poll_orders_for_store(
        self,
        store: Store,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """为单个店铺轮询订单"""
        if not store.api_config:
            return {"error": "Store has no API config", "processed": 0}

        try:
            client = get_rakuten_client(store.api_config)
        except ValueError as e:
            return {"error": str(e), "processed": 0}

        if not end_time:
            end_time = utcnow()
        if not start_time:
            start_time = end_time - timedelta(hours=2)

        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S")

        try:
            order_numbers = await client.search_order(start_str, end_str)
            logger.info(f"Store {store.store_id}: Found {len(order_numbers)} orders")
        except RakutenAPIError as e:
            logger.error(f"Failed to search orders for {store.store_id}: {e}")
            return {"error": str(e), "processed": 0}

        if not order_numbers:
            return {"processed": 0}

        processed = 0
        failed_confirms = []

        for batch in [order_numbers[i:i+100] for i in range(0, len(order_numbers), 100)]:
            try:
                orders = await client.get_order(batch)
            except RakutenAPIError as e:
                logger.error(f"Failed to get order details: {e}")
                continue

            for order in orders:
                result = await self._process_order(order, store.store_id, client)
                if result.get("confirm_failed"):
                    failed_confirms.append(result["order_number"])
                processed += 1

        return {
            "processed": processed,
            "failed_confirms": failed_confirms,
            "start_time": start_str,
            "end_time": end_str,
        }

    async def _process_order(
        self,
        order: dict[str, Any],
        store_id: str,
        client,
    ) -> dict[str, Any]:
        """处理单个订单"""
        order_number = order.get("orderNumber", "")
        order_status = order.get("orderStatus", "")

        order_items = order.get("orderItemList", {}).get("orderItem", [])
        if isinstance(order_items, dict):
            order_items = [order_items]

        results = {"order_number": order_number, "confirm_failed": False}

        for item in order_items:
            raw_sku = item.get("skuNumber", item.get("itemManagementNumber", ""))
            if not raw_sku:
                continue

            sku_id = normalize_sku(raw_sku)
            quantity = int(item.get("quantity", 0))

            if order_status == "100":
                await self._handle_new_order(
                    sku_id, quantity, store_id, order_number, order_status, item, client
                )
                results["confirm_failed"] = True
            elif order_status == "300":
                await self._handle_confirmed_order(
                    sku_id, store_id, order_number, order_status, item
                )
            elif order_status == "900":
                await self._handle_cancelled_order(
                    sku_id, quantity, store_id, order_number, order_status, item
                )

        return results

    async def _handle_new_order(
        self,
        sku_id: str,
        quantity: int,
        store_id: str,
        order_number: str,
        platform_status: str,
        item: dict[str, Any],
        client,
    ):
        """处理新订单 (状态100) - 减少库存并确认订单"""
        from app.services.inventory import InventoryService

        inv_service = InventoryService(self.session)

        sku = await inv_service.get_or_create_sku(sku_id, sku_id, environment="prod")

        await inv_service.create_event(
            event_type=EventTypeEnumSchema.ORDER_RECEIVED,
            sku_id=sku_id,
            quantity=-quantity,
            store_id=store_id,
            platform_status=platform_status,
            order_id=order_number,
            operator="system",
            reason="乐天新订单",
            source=SourceEnumSchema.API,
            metadata={"item": item},
        )

        try:
            await client.confirm_order(order_number)
            logger.info(f"Order {order_number} confirmed successfully")
        except RakutenAPIError as e:
            logger.error(f"Failed to confirm order {order_number}: {e}")

    async def _handle_confirmed_order(
        self,
        sku_id: str,
        store_id: str,
        order_number: str,
        platform_status: str,
        item: dict[str, Any],
    ):
        """处理已确认订单 (状态300)"""
        from app.services.inventory import InventoryService

        inv_service = InventoryService(self.session)

        await inv_service.create_event(
            event_type=EventTypeEnumSchema.ORDER_CONFIRMED,
            sku_id=sku_id,
            quantity=0,
            store_id=store_id,
            platform_status=platform_status,
            order_id=order_number,
            operator="system",
            reason="乐天订单已确认",
            source=SourceEnumSchema.API,
            metadata={"item": item},
        )

    async def _handle_cancelled_order(
        self,
        sku_id: str,
        quantity: int,
        store_id: str,
        order_number: str,
        platform_status: str,
        item: dict[str, Any],
    ):
        """处理取消订单 (状态900) - 增加库存"""
        from app.services.inventory import InventoryService

        inv_service = InventoryService(self.session)

        await inv_service.create_event(
            event_type=EventTypeEnumSchema.ORDER_CANCELLED,
            sku_id=sku_id,
            quantity=quantity,
            store_id=store_id,
            platform_status=platform_status,
            order_id=order_number,
            operator="system",
            reason="乐天订单取消",
            source=SourceEnumSchema.API,
            metadata={"item": item},
        )

    async def poll_all_stores(self) -> dict[str, Any]:
        """轮询所有活跃店铺的订单"""
        result = await self.session.execute(
            select(Store).where(
                Store.status == "active",
                Store.platform_type == "rakuten",
            )
        )
        stores = result.scalars().all()

        total_processed = 0
        errors = []

        for store in stores:
            store_result = await self.poll_orders_for_store(store)
            total_processed += store_result.get("processed", 0)
            if "error" in store_result:
                errors.append({"store_id": store.store_id, "error": store_result["error"]})

        return {
            "total_processed": total_processed,
            "stores_polled": len(stores),
            "errors": errors,
        }
