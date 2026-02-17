import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    InventoryEvent,
    InventorySnapshot,
    OrderConfirmRetry,
    SkuMaster,
    SourceEnum,
    Store,
)
from app.db.schemas import EventTypeEnumSchema, SourceEnumSchema
from app.services.inventory import InventoryService
from app.services.rakuten_api import RakutenAPIError, get_rakuten_client
from app.utils.helpers import normalize_sku, utcnow

logger = logging.getLogger(__name__)


class RetryConfig:
    """重试配置"""
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 5  # 初始重试延迟（分钟）


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
            error_msg = f"Failed to search orders for {store.store_id}: {e}"
            logger.error(error_msg)
            # 记录 API 错误到事件表
            inv_service = InventoryService(self.session)
            await inv_service.log_api_error(
                error_message=str(e),
                store_id=store.store_id,
                operation="search_order",
                error_details={
                    "start_time": start_str,
                    "end_time": end_str,
                    "error_code": e.code if hasattr(e, 'code') else None,
                }
            )
            await self.session.commit()
            return {"error": str(e), "processed": 0}

        if not order_numbers:
            return {"processed": 0}

        processed = 0
        failed_confirms = []

        # 使用事务处理订单批次，确保数据一致性
        for batch in [order_numbers[i:i+100] for i in range(0, len(order_numbers), 100)]:
            async with self.session.begin():
                try:
                    orders = await client.get_order(batch)
                except RakutenAPIError as e:
                    error_msg = f"Failed to get order details for {store.store_id}: {e}"
                    logger.error(error_msg)
                    # 记录 API 错误到事件表
                    inv_service = InventoryService(self.session)
                    await inv_service.log_api_error(
                        error_message=str(e),
                        store_id=store.store_id,
                        operation="get_order",
                        error_details={
                            "batch": batch[:5] if len(batch) > 5 else batch,
                            "batch_size": len(batch),
                            "error_code": e.code if hasattr(e, 'code') else None,
                        }
                    )
                    await self.session.rollback()
                    continue

                for order in orders:
                    try:
                        result = await self._process_order(order, store.store_id, client)
                        if result.get("confirm_failed"):
                            failed_confirms.append(result["order_number"])
                        processed += 1
                    except Exception as e:
                        logger.error(f"Error processing order {result.get('order_number', 'unknown')}: {e}")
                        await self.session.rollback()
                        continue

                # 提交这个批次的所有订单
                await self.session.commit()

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
        """处理单个订单

        Args:
            order: 订单数据
            store_id: 店铺ID
            client: Rakuten API 客户端

        Returns:
            处理结果字典，包含 order_number 和 confirm_failed 标志

        Raises:
            ValueError: 如果订单已处理过（重复）
        """
        order_number = order.get("orderNumber", "")
        order_status = order.get("orderStatus", "")

        # 订单去重检查 - 使用 order_number + status + store_id 组合
        dedup_token = f"{order_number}_{order_status}_{store_id}"
        existing_event = await self.session.execute(
            select(InventoryEvent).where(InventoryEvent.token == dedup_token)
        )
        if existing_event.scalar_one_or_none():
            logger.warning(
                f"重复订单已跳过: order={order_number}, status={order_status}, store={store_id}"
            )
            return {
                "order_number": order_number,
                "confirm_failed": False,
                "skipped": True,
                "reason": "duplicate_order"
            }

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

        # 生成去重 token
        dedup_token = f"{order_number}_{platform_status}_{store_id}"

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
            token=dedup_token,  # 设置去重 token
        )

        # 尝试确认订单
        try:
            await client.confirm_order(order_number)
            logger.info(f"Order {order_number} confirmed successfully")
        except RakutenAPIError as e:
            error_msg = f"Failed to confirm order {order_number}: {e}"
            logger.error(error_msg)
            # 记录 API 错误到事件表
            await inv_service.log_api_error(
                error_message=str(e),
                store_id=store_id,
                sku_id=sku_id,
                operation="confirm_order",
                error_details={
                    "order_number": order_number,
                    "sku_id": sku_id,
                    "error_code": e.code if hasattr(e, 'code') else None,
                }
            )
            # 将失败的订单加入重试队列
            await self._add_order_to_retry_queue(
                order_number, store_id, str(e), item
            )

    async def _add_order_to_retry_queue(
        self,
        order_number: str,
        store_id: str,
        error_message: str,
        item: dict[str, Any],
    ):
        """将订单加入重试队列"""
        # 检查是否已经在队列中
        existing = await self.session.execute(
            select(OrderConfirmRetry).where(
                OrderConfirmRetry.order_number == order_number,
                OrderConfirmRetry.store_id == store_id,
                OrderConfirmRetry.status == "pending"
            )
        )
        if existing.scalar_one_or_none():
            # 已存在，跳过
            return

        retry = OrderConfirmRetry(
            order_number=order_number,
            store_id=store_id,
            retry_count=0,
            max_retries=RetryConfig.MAX_RETRIES,
            last_error=error_message,
            last_attempt_at=utcnow(),
            next_attempt_at=utcnow() + timedelta(minutes=RetryConfig.INITIAL_RETRY_DELAY),
            status="pending",
            retry_metadata={"item": item},
        )
        self.session.add(retry)
        await self.session.flush()
        logger.info(f"Order {order_number} added to retry queue")

    async def process_retry_queue(self) -> dict[str, Any]:
        """处理重试队列中的订单"""
        now = utcnow()

        # 查询需要重试的订单（next_attempt_at <= now）
        result = await self.session.execute(
            select(OrderConfirmRetry).where(
                OrderConfirmRetry.status == "pending",
                OrderConfirmRetry.next_attempt_at <= now,
                OrderConfirmRetry.retry_count < RetryConfig.MAX_RETRIES,
            )
        )
        retries = result.scalars().all()

        processed = 0
        failed = []

        for retry in retries:
            store_result = await self.session.execute(
                select(Store).where(Store.store_id == retry.store_id)
            )
            store = store_result.scalar_one_or_none()

            if not store or not store.api_config:
                # 标记为失败
                retry.status = "failed"
                await self.session.flush()
                failed.append(retry.order_number)
                continue

            try:
                client = get_rakuten_client(store.api_config)
                await client.confirm_order(retry.order_number)
                logger.info(
                    f"Retry {retry.retry_count + 1} succeeded for order {retry.order_number}"
                )
                # 成功，删除重试记录
                await self.session.delete(retry)
                processed += 1
            except RakutenAPIError as e:
                retry.retry_count += 1
                retry.last_error = str(e)
                retry.last_attempt_at = now

                if retry.retry_count >= RetryConfig.MAX_RETRIES:
                    # 达到最大重试次数，标记为失败
                    retry.status = "failed"
                    failed.append(retry.order_number)
                    logger.error(
                        f"Order {retry.order_number} failed after {RetryConfig.MAX_RETRIES} retries"
                    )
                    # 记录最终失败到事件表
                    inv_service = InventoryService(self.session)
                    await inv_service.log_api_error(
                        error_message=f"Order confirm failed after {RetryConfig.MAX_RETRIES} retries: {e}",
                        store_id=retry.store_id,
                        operation="confirm_order",
                        error_details={
                            "order_number": retry.order_number,
                            "retry_count": retry.retry_count,
                            "error_code": e.code if hasattr(e, 'code') else None,
                            "last_error": retry.last_error,
                        }
                    )
                else:
                    # 指数退避：2^retry_count 分钟后重试
                    wait_minutes = 2 ** retry.retry_count
                    retry.next_attempt_at = now + timedelta(minutes=wait_minutes)
                    logger.info(
                        f"Order {retry.order_number} will retry in {wait_minutes} minutes "
                        f"(attempt {retry.retry_count}/{RetryConfig.MAX_RETRIES})"
                    )
                    # 记录重试失败到事件表
                    inv_service = InventoryService(self.session)
                    await inv_service.log_api_error(
                        error_message=str(e),
                        store_id=retry.store_id,
                        operation="confirm_order_retry",
                        error_details={
                            "order_number": retry.order_number,
                            "retry_count": retry.retry_count,
                            "error_code": e.code if hasattr(e, 'code') else None,
                        }
                    )

            await self.session.flush()

        await self.session.commit()

        return {
            "processed": processed,
            "failed": failed,
            "total": len(retries),
        }

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

        # 生成去重 token
        dedup_token = f"{order_number}_{platform_status}_{store_id}"

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
            token=dedup_token,  # 设置去重 token
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

        # 生成去重 token
        dedup_token = f"{order_number}_{platform_status}_{store_id}"

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
            token=dedup_token,  # 设置去重 token
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

        # 轮询完成后，处理重试队列
        retry_result = await self.process_retry_queue()

        return {
            "total_processed": total_processed,
            "stores_polled": len(stores),
            "errors": errors,
            "retry_processed": retry_result.get("processed", 0),
            "retry_failed": retry_result.get("failed", []),
            "retry_total": retry_result.get("total", 0),
        }
