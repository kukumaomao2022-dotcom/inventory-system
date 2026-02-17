import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    EventTypeEnum,
    InventoryEvent,
    InventorySnapshot,
    SkuMaster,
    SourceEnum,
    Store,
    StoreSku,
)
from app.db.schemas import EventTypeEnumSchema, SourceEnumSchema
from app.utils.helpers import generate_token, normalize_sku, utcnow

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_snapshot(self, sku_id: str) -> InventorySnapshot | None:
        """Get current inventory snapshot for a SKU."""
        sku_id = normalize_sku(sku_id)
        result = await self.session.execute(
            select(InventorySnapshot).where(InventorySnapshot.sku_id == sku_id)
        )
        return result.scalar_one_or_none()

    async def get_sku(self, sku_id: str) -> SkuMaster | None:
        """Get SKU master record."""
        sku_id = normalize_sku(sku_id)
        result = await self.session.execute(
            select(SkuMaster).where(SkuMaster.sku_id == sku_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_sku(
        self,
        sku_id: str,
        original_sku: str | None = None,
        sku_name: str = "",
        environment: str = "prod",
    ) -> SkuMaster:
        """Get or create a SKU master record."""
        sku_id = normalize_sku(sku_id)
        if not original_sku:
            original_sku = sku_id

        existing = await self.get_sku(sku_id)
        if existing:
            return existing

        sku = SkuMaster(
            sku_id=sku_id,
            original_sku=original_sku,
            sku_name=sku_name or sku_id,
            environment=environment,
            status="active",
            metadata={},
            aliases={},
        )
        self.session.add(sku)
        await self.session.flush()
        return sku

    async def create_event(
        self,
        event_type: EventTypeEnum | EventTypeEnumSchema,
        sku_id: str,
        quantity: int,
        operator: str,
        source: SourceEnum | SourceEnumSchema,
        store_id: str | None = None,
        platform_status: str | None = None,
        order_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        token: str | None = None,
        update_snapshot: bool = True,
    ) -> InventoryEvent:
        """Create an inventory event and optionally update snapshot."""
        sku_id = normalize_sku(sku_id)

        if not token:
            token = generate_token()

        event = InventoryEvent(
            event_type=event_type.value if isinstance(event_type, EventTypeEnumSchema) else event_type,
            sku_id=sku_id,
            quantity=quantity,
            store_id=store_id,
            platform_status=platform_status,
            order_id=order_id,
            operator=operator,
            reason=reason,
            source=source.value if isinstance(source, SourceEnumSchema) else source,
            token=token,
            event_metadata=metadata or {},
        )
        self.session.add(event)
        await self.session.flush()

        if update_snapshot:
            await self._update_snapshot(sku_id, quantity, event.event_id)

        return event

    async def _update_snapshot(
        self,
        sku_id: str,
        quantity: int,
        event_id: UUID,
        allow_oversell_check: bool = True,
    ) -> None:
        """Update inventory snapshot after an event.

        Args:
            sku_id: SKU identifier
            quantity: Quantity change (positive or negative)
            event_id: Event ID for traceability
            allow_oversell_check: If True, check oversell constraint

        Raises:
            ValueError: If allow_oversell=False and new quantity would be negative
        """
        existing = await self.get_snapshot(sku_id)

        if existing:
            new_quantity = existing.internal_available + quantity

            # 检查是否允许超卖
            if allow_oversell_check:
                sku = await self.get_sku(sku_id)
                if sku and not sku.allow_oversell and new_quantity < 0:
                    logger.warning(
                        f"SKU {sku_id}不允许超卖，当前库存: {existing.internal_available}, "
                        f"变更量: {quantity}, 新库存: {new_quantity}"
                    )
                    raise ValueError(
                        f"不允许超卖：SKU {sku_id} 库存不足 "
                        f"(当前: {existing.internal_available}, 需要: {-quantity})"
                    )

            await self.session.execute(
                update(InventorySnapshot)
                .where(InventorySnapshot.sku_id == sku_id)
                .values(
                    internal_available=new_quantity,
                    last_event_id=event_id,
                    updated_at=utcnow(),
                )
            )
        else:
            snapshot = InventorySnapshot(
                sku_id=sku_id,
                internal_available=quantity,
                last_event_id=event_id,
            )
            self.session.add(snapshot)

        await self.session.flush()

    async def register_sku_to_store(
        self,
        sku_id: str,
        store_id: str,
    ) -> StoreSku:
        """Register a SKU to a store."""
        sku_id = normalize_sku(sku_id)

        result = await self.session.execute(
            select(StoreSku).where(
                StoreSku.sku_id == sku_id,
                StoreSku.store_id == store_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        store_sku = StoreSku(
            sku_id=sku_id,
            store_id=store_id,
        )
        self.session.add(store_sku)
        await self.session.flush()
        return store_sku

    async def get_registered_stores(self, sku_id: str) -> list[str]:
        """Get list of store IDs registered for a SKU."""
        sku_id = normalize_sku(sku_id)
        result = await self.session.execute(
            select(StoreSku.store_id).where(StoreSku.sku_id == sku_id)
        )
        return [row[0] for row in result.fetchall()]

    async def get_store(self, store_id: str) -> Store | None:
        """Get store by ID."""
        result = await self.session.execute(
            select(Store).where(Store.store_id == store_id)
        )
        return result.scalar_one_or_none()

    async def get_store_skus(self, store_id: str) -> list[dict[str, Any]]:
        """Get all SKUs registered to a store."""
        result = await self.session.execute(
            select(StoreSku, SkuMaster)
            .join(SkuMaster, StoreSku.sku_id == SkuMaster.sku_id)
            .where(StoreSku.store_id == store_id)
        )
        return [
            {
                "store_id": store_sku.store_id,
                "sku_id": sku.sku_id,
                "sku_name": sku.sku_name,
                "original_sku": sku.original_sku,
                "registered_at": store_sku.registered_at,
            }
            for store_sku, sku in result.all()
        ]

    async def get_events(
        self,
        sku_id: str,
        limit: int = 50,
        offset: int = 0,
        event_type: EventTypeEnum | None = None,
    ) -> list[InventoryEvent]:
        """Get events for a SKU."""
        sku_id = normalize_sku(sku_id)

        query = select(InventoryEvent).where(InventoryEvent.sku_id == sku_id)

        if event_type:
            query = query.where(InventoryEvent.event_type == event_type)

        query = (
            query
            .order_by(InventoryEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def deactivate_sku(self, sku_id: str) -> bool:
        """Mark SKU as inactive (soft delete)."""
        sku_id = normalize_sku(sku_id)

        result = await self.session.execute(
            update(SkuMaster)
            .where(SkuMaster.sku_id == sku_id)
            .values(status="inactive")
        )
        await self.session.flush()
        return True

    async def log_api_error(
        self,
        error_message: str,
        store_id: str | None = None,
        error_details: dict[str, Any] | None = None,
        sku_id: str | None = None,
        operation: str | None = None,
    ) -> InventoryEvent:
        """Log API error to inventory events table.

        Args:
            error_message: Error message or exception description
            store_id: Store ID if applicable
            error_details: Additional error details (HTTP status, error code, etc.)
            sku_id: SKU ID if applicable
            operation: Operation being performed (e.g., "search_order", "confirm_order")

        Returns:
            Created InventoryEvent
        """
        # 使用特殊 SKU ID 用于系统级错误
        system_sku = sku_id if sku_id else "SYSTEM_ERROR"

        metadata = {
            "error_type": "api_failure",
            "operation": operation or "unknown",
            "error_details": error_details or {},
        }

        if store_id:
            metadata["store_id"] = store_id

        event = await self.create_event(
            event_type=EventTypeEnumSchema.API_ERROR,
            sku_id=system_sku,
            quantity=0,  # API 错误不影响库存
            store_id=store_id,
            operator="system",
            reason=error_message,
            source=SourceEnumSchema.SYSTEM,
            metadata=metadata,
            update_snapshot=False,  # 不更新库存快照
        )
        logger.error(f"API Error logged: {error_message} | Operation: {operation} | Store: {store_id}")
        return event
