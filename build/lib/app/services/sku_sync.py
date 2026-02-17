import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Store, StoreSku, SkuMaster
from app.services.rakuten_api import get_rakuten_client, RakutenAPIError
from app.utils.helpers import normalize_sku, utcnow

logger = logging.getLogger(__name__)


class SkuSyncService:
    """SKU同步服务 - 从乐天拉取店铺SKU"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_store_skus(self, store_id: str) -> dict[str, Any]:
        """从乐天同步店铺SKU"""
        result = await self.session.execute(
            select(Store).where(Store.store_id == store_id)
        )
        store = result.scalar_one_or_none()

        if not store:
            return {"error": "Store not found", "synced": 0}

        if not store.api_config:
            return {"error": "Store has no API config", "synced": 0}

        try:
            client = get_rakuten_client(store.api_config)
        except ValueError as e:
            return {"error": str(e), "synced": 0}

        synced = 0
        errors = []
        page = 1

        while True:
            try:
                response = await client.get_items(limit=100, page=page)
            except RakutenAPIError as e:
                logger.error(f"Failed to get items for {store_id}: {e}")
                return {"error": str(e), "synced": synced}

            items = response.get("itemList", {}).get("item", [])
            if not items:
                break

            if isinstance(items, dict):
                items = [items]

            for item in items:
                try:
                    await self._process_item(item, store_id)
                    synced += 1
                except Exception as e:
                    errors.append({"item": item.get("itemName", "unknown"), "error": str(e)})

            page += 1
            if page > response.get("pageCount", 1):
                break

        await self.session.execute(
            update(Store)
            .where(Store.store_id == store_id)
            .values(last_sku_sync_at=utcnow())
        )
        await self.session.commit()

        return {
            "synced": synced,
            "errors": errors,
            "last_sync_at": utcnow().isoformat(),
        }

    async def _process_item(self, item: dict[str, Any], store_id: str):
        """处理单个商品项"""
        raw_sku = item.get("skuNumber", item.get("itemManagementNumber", ""))
        if not raw_sku:
            return

        sku_id = normalize_sku(raw_sku)
        original_sku = raw_sku

        item_name = item.get("itemName", "")
        item_url = item.get("itemUrl", "")
        image_url = item.get("imageUrl", item.get("mediumImageUrl", ""))

        metadata = {
            "item_name": item_name,
            "item_url": item_url,
            "image_url": image_url,
            "original_data": item,
        }

        existing = await self.session.execute(
            select(SkuMaster).where(SkuMaster.sku_id == sku_id)
        )
        sku = existing.scalar_one_or_none()

        if sku:
            if sku.extra_data.get("item_name") != item_name:
                metadata["previous_item_name"] = sku.extra_data.get("item_name")
            sku.extra_data = {**sku.extra_data, **metadata}
        else:
            sku = SkuMaster(
                sku_id=sku_id,
                original_sku=original_sku,
                sku_name=item_name or sku_id,
                environment="prod",
                status="active",
                extra_data=metadata,
                aliases={"rakuten": original_sku},
            )
            self.session.add(sku)

        existing_store_sku = await self.session.execute(
            select(StoreSku).where(
                StoreSku.sku_id == sku_id,
                StoreSku.store_id == store_id,
            )
        )
        if not existing_store_sku.scalar_one_or_none():
            store_sku = StoreSku(
                sku_id=sku_id,
                store_id=store_id,
            )
            self.session.add(store_sku)

        await self.session.flush()

    async def get_sync_status(self, store_id: str) -> dict[str, Any]:
        """获取店铺同步状态"""
        result = await self.session.execute(
            select(Store).where(Store.store_id == store_id)
        )
        store = result.scalar_one_or_none()

        if not store:
            return {"error": "Store not found"}

        return {
            "last_sync_at": store.last_sku_sync_at.isoformat() if store.last_sku_sync_at else None,
            "is_syncing": False,
            "progress": None,
            "last_error": None,
        }
