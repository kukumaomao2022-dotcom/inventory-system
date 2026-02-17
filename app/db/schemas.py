from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventTypeEnumSchema(str, Enum):
    ORDER_RECEIVED = "ORDER_RECEIVED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    ORDER_SHIPPED = "ORDER_SHIPPED"
    STOCK_IN = "STOCK_IN"
    ADJUSTMENT = "ADJUSTMENT"
    INIT_RESET = "INIT_RESET"
    API_ERROR = "API_ERROR"
    SYNC_FAILURE = "SYNC_FAILURE"


class SourceEnumSchema(str, Enum):
    API = "api"
    MANUAL = "manual"
    IMPORT = "import"
    SYSTEM = "system"


class ImportModeEnumSchema(str, Enum):
    METADATA_ONLY = "metadata_only"
    RESET_STOCK = "reset_stock"


class InventoryModeEnumSchema(str, Enum):
    """库存导入模式"""
    REPLACE = "replace"  # 替换库存（确认为最终库存）
    ADD = "add"  # 累加库存
    SKIP_ZERO = "skip_zero"  # 跳过零库存


class ZeroHandlingEnumSchema(str, Enum):
    IGNORE = "ignore"
    SET_ZERO = "set_zero"
    ZERO_NEGATIVE = "zero_negative"


class SkuMasterBase(BaseModel):
    sku_id: str = Field(..., max_length=50)
    original_sku: str | None = Field(None, max_length=50)
    sku_name: str = Field(..., max_length=200)
    allow_oversell: bool = False
    environment: str = Field(default="prod")
    status: str = Field(default="active")
    extra_data: dict[str, Any] = {}
    aliases: dict[str, Any] = {}


class SkuMasterCreate(SkuMasterBase):
    pass


class SkuMasterUpdate(BaseModel):
    sku_name: str | None = None
    allow_oversell: bool | None = None
    status: str | None = None
    extra_data: dict[str, Any] | None = None
    aliases: dict[str, Any] | None = None


class SkuMasterResponse(SkuMasterBase):
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoreBase(BaseModel):
    store_id: str = Field(..., max_length=50)
    store_name: str = Field(..., max_length=100)
    platform_type: str = Field(default="rakuten")
    api_config: dict[str, Any] = {}
    status: str = Field(default="active")


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    store_name: str | None = None
    api_config: dict[str, Any] | None = None
    status: str | None = None


class StoreResponse(StoreBase):
    last_sku_sync_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StoreSkuResponse(BaseModel):
    store_id: str
    sku_id: str
    registered_at: datetime
    sku_name: str | None = None
    original_sku: str | None = None

    model_config = {"from_attributes": True}


class InventoryEventBase(BaseModel):
    event_type: EventTypeEnumSchema
    sku_id: str
    quantity: int
    store_id: str | None = None
    platform_status: str | None = None
    order_id: str | None = None
    operator: str
    reason: str | None = None
    source: SourceEnumSchema
    metadata: dict[str, Any] = {}


class InventoryEventCreate(InventoryEventBase):
    pass


class InventoryEventResponse(InventoryEventBase):
    event_id: UUID
    token: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InventorySnapshotResponse(BaseModel):
    sku_id: str
    internal_available: int
    last_event_id: UUID | None
    updated_at: datetime
    registered_stores: list[str] = []

    model_config = {"from_attributes": True}


class ManualEventCreate(BaseModel):
    sku_id: str
    quantity: int
    reason: str
    operator: str = "admin"
    token: str | None = None


class UploadedFileBase(BaseModel):
    filename: str
    store_id: str | None = None
    import_mode: ImportModeEnumSchema
    zero_handling: ZeroHandlingEnumSchema
    operator: str


class UploadedFileCreate(UploadedFileBase):
    original_content: str
    token: str


class UploadedFileResponse(UploadedFileBase):
    file_id: UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportPreviewRequest(BaseModel):
    import_mode: ImportModeEnumSchema
    zero_handling: ZeroHandlingEnumSchema = ZeroHandlingEnumSchema.IGNORE
    store_id: str | None = None


class ImportPreviewResponse(BaseModel):
    total_rows: int
    new_skus: int
    registered_skus: int
    reset_skus: int
    zero_negative_skus: int
    preview_rows: list[dict[str, Any]]


class ImportConfirmRequest(BaseModel):
    import_mode: ImportModeEnumSchema
    zero_handling: ZeroHandlingEnumSchema = ZeroHandlingEnumSchema.IGNORE
    store_id: str | None = None
    token: str
    operator: str | None = None


class SyncStatusResponse(BaseModel):
    last_sync_at: datetime | None
    is_syncing: bool
    progress: dict[str, int] | None
    last_error: str | None


class AuditLogResponse(BaseModel):
    log_id: UUID
    user: str
    action: str
    details: dict[str, Any]
    ip: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OversellResponse(BaseModel):
    sku_id: str
    original_sku: str | None
    sku_name: str
    internal_available: int


class RakutenAuthTestResponse(BaseModel):
    valid: bool
    license_key_days_remaining: int | None
    store_id: str


class TaskResponse(BaseModel):
    task_id: str
    status: str


class ErrorResponse(BaseModel):
    detail: str
