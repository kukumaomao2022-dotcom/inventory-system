import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class EventTypeEnum(PyEnum):
    ORDER_RECEIVED = "ORDER_RECEIVED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    ORDER_SHIPPED = "ORDER_SHIPPED"
    STOCK_IN = "STOCK_IN"
    ADJUSTMENT = "ADJUSTMENT"
    INIT_RESET = "INIT_RESET"


class SourceEnum(PyEnum):
    API = "api"
    MANUAL = "manual"
    IMPORT = "import"
    SYSTEM = "system"


class ImportModeEnum(PyEnum):
    METADATA_ONLY = "metadata_only"
    RESET_STOCK = "reset_stock"


class ZeroHandlingEnum(PyEnum):
    IGNORE = "ignore"
    SET_ZERO = "set_zero"
    ZERO_NEGATIVE = "zero_negative"


class SkuMaster(Base):
    __tablename__ = "sku_master"

    sku_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    original_sku: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sku_name: Mapped[str] = mapped_column(String(200), nullable=False)
    allow_oversell: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    environment: Mapped[str] = mapped_column(
        String(10), nullable=False, default="prod"
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="active"
    )
    extra_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    aliases: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_sku_master_environment", "environment"),
    )


class Store(Base):
    __tablename__ = "stores"

    store_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    store_name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform_type: Mapped[str] = mapped_column(String(20), nullable=False)
    api_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="active"
    )
    last_sku_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    store_skus: Mapped[list["StoreSku"]] = relationship(
        "StoreSku", back_populates="store", cascade="all, delete-orphan"
    )
    inventory_events: Mapped[list["InventoryEvent"]] = relationship(
        "InventoryEvent", back_populates="store"
    )


class StoreSku(Base):
    __tablename__ = "store_sku"

    store_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("stores.store_id", ondelete="CASCADE"), primary_key=True
    )
    sku_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sku_master.sku_id", ondelete="CASCADE"), primary_key=True
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    store: Mapped["Store"] = relationship("Store", back_populates="store_skus")
    sku: Mapped["SkuMaster"] = relationship("SkuMaster", back_populates="store_skus")


class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[EventTypeEnum] = mapped_column(
        SAEnum(EventTypeEnum, name="event_type_enum"), nullable=False
    )
    sku_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sku_master.sku_id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    store_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("stores.store_id"), nullable=True
    )
    platform_status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[SourceEnum] = mapped_column(
        SAEnum(SourceEnum, name="source_enum"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(64), nullable=True, unique=True)
    event_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sku: Mapped["SkuMaster"] = relationship("SkuMaster", back_populates="inventory_events")
    store: Mapped["Store"] = relationship("Store", back_populates="inventory_events")
    snapshot: Mapped["InventorySnapshot"] = relationship(
        "InventorySnapshot", back_populates="last_event"
    )

    __table_args__ = (
        Index("idx_events_sku_id", "sku_id"),
        Index("idx_events_created_at", "created_at"),
    )


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    sku_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sku_master.sku_id"), primary_key=True
    )
    internal_available: Mapped[int] = mapped_column(Integer, nullable=False)
    last_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_events.event_id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    sku: Mapped["SkuMaster"] = relationship(
        "SkuMaster", back_populates="snapshot", foreign_keys=[sku_id]
    )
    last_event: Mapped["InventoryEvent"] = relationship(
        "InventoryEvent", back_populates="snapshot", foreign_keys=[last_event_id]
    )


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    store_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("stores.store_id"), nullable=True
    )
    import_mode: Mapped[ImportModeEnum] = mapped_column(
        SAEnum(ImportModeEnum, name="import_mode_enum"), nullable=False
    )
    zero_handling: Mapped[ZeroHandlingEnum] = mapped_column(
        SAEnum(ZeroHandlingEnum, name="zero_handling_enum"), nullable=False
    )
    operator: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_audit_log_created_at", "created_at"),
    )


SkuMaster.store_skus = relationship(
    "StoreSku", back_populates="sku", cascade="all, delete-orphan"
)
SkuMaster.inventory_events = relationship(
    "InventoryEvent", back_populates="sku", cascade="all, delete-orphan"
)
SkuMaster.snapshot = relationship(
    "InventorySnapshot", back_populates="sku", uselist=False, cascade="all, delete-orphan"
)
