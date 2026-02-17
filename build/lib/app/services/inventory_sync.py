import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InventorySnapshot, SkuMaster, Store, StoreSku
from app.services.rakuten_api import RakutenAPIError, get_rakuten_client
from app.utils.helpers import normalize_sku

logger = logging.getLogger(__name__)


class InventorySyncService:
    """库存同步服务 - 将库存同步到各平台"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_to_store(self, sku_id: str, store_id: str) -> dict[str, Any]:
        """同步单个SKU到单个店铺"""
        sku_id = normalize_sku(sku_id)

        result = await self.session.execute(
            select(Store).where(Store.store_id == store_id)
        )
        store = result.scalar_one_or_none()

        if not store:
            return {"error": "Store not found", "success": False}

        if not store.api_config:
            return {"error": "Store has no API config", "success": False}

        snapshot_result = await self.session.execute(
            select(InventorySnapshot).where(InventorySnapshot.sku_id == sku_id)
        )
        snapshot = snapshot_result.scalar_one_or_none()

        if not snapshot:
            return {"error": "Snapshot not found", "success": False}

        platform_stock = max(0, snapshot.internal_available)

        if store.platform_type == "rakuten":
            return await self._sync_to_rakuten(store, sku_id, platform_stock)

        return {"error": "Unknown platform type", "success": False}

    async def _sync_to_rakuten(
        self,
        store: Store,
        sku_id: str,
        platform_stock: int,
    ) -> dict[str, Any]:
        """同步到乐天"""
        sku_result = await self.session.execute(
            select(SkuMaster).where(SkuMaster.sku_id == sku_id)
        )
        sku = sku_result.scalar_one_or_none()

        if not sku:
            return {"error": "SKU not found", "success": False}

        rakuten_sku = sku.aliases.get("rakuten") or sku.original_sku or sku_id

        try:
            client = get_rakuten_client(store.api_config)
            result = await client.set_inventory(rakuten_sku, platform_stock)
            return {
                "success": True,
                "sku_id": sku_id,
                "rakuten_sku": rakuten_sku,
                "stock": platform_stock,
                "result": result,
            }
        except RakutenAPIError as e:
            logger.error(f"Failed to sync to Rakuten: {e}")
            return {
                "success": False,
                "error": str(e),
                "sku_id": sku_id,
            }

    async def sync_all_to_store(self, store_id: str) -> dict[str, Any]:
        """同步所有SKU到店铺"""
        result = await self.session.execute(
            select(StoreSku.sku_id).where(StoreSku.store_id == store_id)
        )
        sku_ids = [row[0] for row in result.fetchall()]

        tasks = [self.sync_to_store(sku_id, store_id) for sku_id in sku_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = [
            r for r in results
            if isinstance(r, dict) and not r.get("success")
        ]

        return {
            "total": len(sku_ids),
            "success": success_count,
            "failed": len(failed),
            "errors": failed,
        }

    async def sync_sku_to_all_stores(self, sku_id: str) -> dict[str, Any]:
        """同步SKU到所有注册店铺"""
        sku_id = normalize_sku(sku_id)

        result = await self.session.execute(
            select(StoreSku.store_id).where(StoreSku.sku_id == sku_id)
        )
        store_ids = [row[0] for row in result.fetchall()]

        if not store_ids:
            return {"synced": 0, "stores": []}

        tasks = [self.sync_to_store(sku_id, store_id) for store_id in store_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        synced_stores = []
        for store_id, result in zip(store_ids, results):
            if isinstance(result, dict) and result.get("success"):
                synced_stores.append(store_id)

        return {
            "sku_id": sku_id,
            "synced": len(synced_stores),
            "total": len(store_ids),
            "stores": synced_stores,
        }
