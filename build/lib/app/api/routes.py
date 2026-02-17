import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_session
from app.db import models
from app.db.models import EventTypeEnum
from app.db.schemas import (
    StoreCreate, StoreResponse, StoreUpdate,
    SkuMasterCreate, SkuMasterResponse, SkuMasterUpdate,
    StoreSkuResponse,
    InventorySnapshotResponse,
    ManualEventCreate,
    InventoryEventResponse,
    ImportPreviewRequest, ImportPreviewResponse,
    ImportConfirmRequest,
    SyncStatusResponse,
    AuditLogResponse,
    OversellResponse,
    RakutenAuthTestResponse,
    TaskResponse,
    EventTypeEnumSchema,
    SourceEnumSchema,
    ImportModeEnumSchema,
    ZeroHandlingEnumSchema,
)
from app.services import inventory as inventory_service
from app.services import sku_sync as sku_sync_service
from app.services import csv_import as csv_import_service
from app.services import inventory_sync as inventory_sync_service
from app.services import rakuten_api as rakuten_api_service
from app.utils.helpers import normalize_sku

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stores", response_model=list[StoreResponse])
async def list_stores(
    status: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    query = select(models.Store)
    if status:
        query = query.where(models.Store.status == status)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("/stores", response_model=StoreResponse)
async def create_store(
    store: StoreCreate,
    session: AsyncSession = Depends(get_async_session),
):
    db_store = models.Store(**store.model_dump())
    session.add(db_store)
    await session.commit()
    await session.refresh(db_store)
    return db_store


@router.get("/stores/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(models.Store).where(models.Store.store_id == store_id)
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.patch("/stores/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: str,
    store_update: StoreUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(models.Store).where(models.Store.store_id == store_id)
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    update_data = store_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(store, field, value)

    await session.commit()
    await session.refresh(store)
    return store


@router.get("/stores/{store_id}/skus", response_model=list[StoreSkuResponse])
async def list_store_skus(
    store_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    inv_service = inventory_service.InventoryService(session)
    return await inv_service.get_store_skus(store_id)


@router.post("/stores/{store_id}/sync-skus", response_model=TaskResponse)
async def trigger_sku_sync(
    store_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    sync_service = sku_sync_service.SkuSyncService(session)
    result = await sync_service.sync_store_skus(store_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return TaskResponse(
        task_id=f"sync-{store_id}",
        status="completed"
    )


@router.get("/stores/{store_id}/sku-sync-status", response_model=SyncStatusResponse)
async def get_sku_sync_status(
    store_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    sync_service = sku_sync_service.SkuSyncService(session)
    return await sync_service.get_sync_status(store_id)


@router.get("/skus", response_model=list[SkuMasterResponse])
async def list_skus(
    environment: str | None = None,
    store_id: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    query = select(models.SkuMaster)

    if environment:
        query = query.where(models.SkuMaster.environment == environment)

    if store_id:
        query = query.join(models.StoreSku).where(models.StoreSku.store_id == store_id)

    result = await session.execute(query)
    return result.scalars().all()


@router.post("/skus", response_model=SkuMasterResponse)
async def create_sku(
    sku: SkuMasterCreate,
    session: AsyncSession = Depends(get_async_session),
):
    sku_id = normalize_sku(sku.sku_id)
    existing = await session.execute(
        select(models.SkuMaster).where(models.SkuMaster.sku_id == sku_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="SKU already exists")

    db_sku = models.SkuMaster(
        sku_id=sku_id,
        original_sku=sku.original_sku or sku_id,
        **sku.model_dump(exclude={"sku_id", "original_sku"})
    )
    session.add(db_sku)
    await session.commit()
    await session.refresh(db_sku)
    return db_sku


@router.get("/skus/{sku_id}", response_model=SkuMasterResponse)
async def get_sku(
    sku_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    sku_id = normalize_sku(sku_id)
    result = await session.execute(
        select(models.SkuMaster).where(models.SkuMaster.sku_id == sku_id)
    )
    sku = result.scalar_one_or_none()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    return sku


@router.patch("/skus/{sku_id}", response_model=SkuMasterResponse)
async def update_sku(
    sku_id: str,
    sku_update: SkuMasterUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    sku_id = normalize_sku(sku_id)
    result = await session.execute(
        select(models.SkuMaster).where(models.SkuMaster.sku_id == sku_id)
    )
    sku = result.scalar_one_or_none()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    update_data = sku_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sku, field, value)

    await session.commit()
    await session.refresh(sku)
    return sku


@router.delete("/skus/{sku_id}")
async def delete_sku(
    sku_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    删除SKU：清空所有库存相关数据，将SKU重置为"未登录"状态
    保留SKU记录本身，但清除：
    - 所有库存事件
    - 库存快照
    - 店铺关联
    - 元数据和别名
    """
    from sqlalchemy import delete

    sku_id = normalize_sku(sku_id)
    result = await session.execute(
        select(models.SkuMaster).where(models.SkuMaster.sku_id == sku_id)
    )
    sku = result.scalar_one_or_none()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    await session.execute(
        delete(models.InventoryEvent).where(models.InventoryEvent.sku_id == sku_id)
    )
    await session.execute(
        delete(models.InventorySnapshot).where(models.InventorySnapshot.sku_id == sku_id)
    )
    await session.execute(
        delete(models.StoreSku).where(models.StoreSku.sku_id == sku_id)
    )

    sku.extra_data = {}
    sku.aliases = {}
    sku.original_sku = sku_id

    await session.commit()
    await session.refresh(sku)

    return {"message": "SKU deleted and reset to initial state", "sku_id": sku_id}


@router.get("/inventory/{sku_id}", response_model=InventorySnapshotResponse)
async def get_inventory(
    sku_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    sku_id = normalize_sku(sku_id)
    inv_service = inventory_service.InventoryService(session)

    snapshot = await inv_service.get_snapshot(sku_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="SKU not found or no inventory")

    registered_stores = await inv_service.get_registered_stores(sku_id)

    return InventorySnapshotResponse(
        sku_id=sku_id,
        internal_available=snapshot.internal_available,
        last_event_id=snapshot.last_event_id,
        updated_at=snapshot.updated_at,
        registered_stores=registered_stores,
    )


@router.post("/events/manual", response_model=InventoryEventResponse)
async def create_manual_event(
    event: ManualEventCreate,
    session: AsyncSession = Depends(get_async_session),
):
    inv_service = inventory_service.InventoryService(session)

    existing_sku = await inv_service.get_sku(event.sku_id)
    if not existing_sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    db_event = await inv_service.create_event(
        event_type=EventTypeEnumSchema.ADJUSTMENT,
        sku_id=event.sku_id,
        quantity=event.quantity,
        operator=event.operator,
        source=SourceEnumSchema.MANUAL,
        reason=event.reason,
        token=event.token,
    )

    await session.commit()
    await session.refresh(db_event)
    return db_event


@router.get("/events/{sku_id}", response_model=list[InventoryEventResponse])
async def get_sku_events(
    sku_id: str,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    inv_service = inventory_service.InventoryService(session)
    evt_type = None
    if event_type:
        try:
            evt_type = EventTypeEnum[EventTypeEnumSchema(event_type).name]
        except (ValueError, KeyError):
            pass

    return await inv_service.get_events(sku_id, limit, offset, evt_type)


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    store_id: str | None = None,
    import_mode: str = "metadata_only",
    zero_handling: str = "ignore",
    session: AsyncSession = Depends(get_async_session),
):
    content = await file.read()
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        encoding = "shift_jis"
        content_str = content.decode(encoding)

    import_mode_enum = ImportModeEnumSchema(import_mode)
    zero_handling_enum = ZeroHandlingEnumSchema(zero_handling)

    csv_service = csv_import_service.CsvImportService(session)
    return await csv_service.preview_import(
        content_str, store_id, import_mode_enum, zero_handling_enum
    )


@router.post("/import/confirm")
async def confirm_import(
    request: ImportConfirmRequest,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
):
    content = await file.read()
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        content_str = content.decode("shift_jis")

    csv_service = csv_import_service.CsvImportService(session)
    result = await csv_service.execute_import(
        content_str,
        request.store_id,
        request.import_mode,
        request.zero_handling,
        request.operator or "system",
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/sync/{store_id}")
async def trigger_sync(
    store_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    sync_service = inventory_sync_service.InventorySyncService(session)
    return await sync_service.sync_all_to_store(store_id)


@router.get("/audit/logs", response_model=list[AuditLogResponse])
async def get_audit_logs(
    user: str | None = None,
    action: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
):
    query = select(models.AuditLog)

    if user:
        query = query.where(models.AuditLog.user == user)
    if action:
        query = query.where(models.AuditLog.action.like(f"%{action}%"))

    query = query.order_by(models.AuditLog.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/audit/oversell", response_model=list[OversellResponse])
async def get_oversell(
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(models.InventorySnapshot, models.SkuMaster)
        .join(models.SkuMaster, models.InventorySnapshot.sku_id == models.SkuMaster.sku_id)
        .where(models.InventorySnapshot.internal_available < 0)
    )

    return [
        OversellResponse(
            sku_id=snapshot.sku_id,
            original_sku=sku.original_sku,
            sku_name=sku.sku_name,
            internal_available=snapshot.internal_available,
        )
        for snapshot, sku in result.all()
    ]


@router.get("/rakuten/auth-test", response_model=list[RakutenAuthTestResponse])
async def test_rakuten_auth(
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(models.Store).where(
            models.Store.platform_type == "rakuten",
            models.Store.status == "active",
        )
    )
    stores = result.scalars().all()

    responses = []
    for store in stores:
        if not store.api_config:
            responses.append(RakutenAuthTestResponse(
                valid=False,
                license_key_days_remaining=None,
                store_id=store.store_id,
            ))
            continue

        try:
            client = rakuten_api_service.get_rakuten_client(store.api_config)
            valid, days = await client.test_auth()
            responses.append(RakutenAuthTestResponse(
                valid=valid,
                license_key_days_remaining=days,
                store_id=store.store_id,
            ))
        except Exception as e:
            responses.append(RakutenAuthTestResponse(
                valid=False,
                license_key_days_remaining=None,
                store_id=store.store_id,
            ))

    return responses


@router.post("/test/reset")
async def reset_test_data(
    session: AsyncSession = Depends(get_async_session),
):
    from sqlalchemy import delete

    await session.execute(delete(models.InventoryEvent))
    await session.execute(delete(models.InventorySnapshot))
    await session.execute(delete(models.StoreSku))
    await session.execute(delete(models.UploadedFile))

    result = await session.execute(
        select(models.SkuMaster).where(models.SkuMaster.sku_id == "ce1111")
    )
    if not result.scalar_one_or_none():
        test_sku = models.SkuMaster(
            sku_id="ce1111",
            original_sku="ce1111",
            sku_name="测试商品",
            environment="test",
            status="active",
        )
        session.add(test_sku)

    await session.commit()
    return {"status": "reset completed", "test_sku": "ce1111"}
