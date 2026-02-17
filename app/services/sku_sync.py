import csv
import codecs
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Store, StoreSku, SkuMaster
from app.db.schemas import SourceEnumSchema
from app.services.inventory import InventoryService
from app.services.rakuten_api import get_rakuten_client, RakutenAPIError
from app.utils.helpers import normalize_sku, utcnow

logger = logging.getLogger(__name__)

# 模拟模式设置 - 从环境变量读取，默认为False（使用真实API）
# 设置MOCK_MODE=true使用模拟数据进行开发测试
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes")

# 库存范围查询的批次大小
INVENTORY_BATCH_SIZE = 1000

# CSV 文件编码
CSV_ENCODING = "shift_jis"

# CSV 字段映射（全部.csv）
CSV_FIELDS_FULL = {
    "manage_number": 0,      # 商品管理番号（商品URL）
    "item_number": 1,         # 商品番号
    "item_name": 2,           # 商品名
    "sku_id": 5,             # SKU管理番号
    "price": 6,               # 通常購入販売価格
    "display_price": 7,        # 表示価格
}

# CSV 字段映射（平时.csv）
CSV_FIELDS_DAILY = {
    "manage_number": 0,      # 商品管理番号（商品URL）
    "item_number": 1,         # 商品番号
    "item_name": 2,           # 商品名
    "catch_copy": 3,          # キャッチコピー
    "price": None,             # 需要找到
}


class SkuSyncService:
    """SKU同步服务 - 从乐天获取店铺SKU"""

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

        # 模拟模式：使用模拟数据
        if MOCK_MODE:
            logger.info(f"模拟模式：为店铺 {store_id} 生成模拟SKU数据")
            return await self._sync_with_mock_data(store_id)

        # 真实模式：使用乐天 API
        try:
            client = get_rakuten_client(store.api_config)
        except ValueError as e:
            return {"error": str(e), "synced": 0}

        synced = 0
        errors = []
        processed_skus = set()  # 用于去重

        # 使用库存范围 API 遍历获取所有 SKU
        # 从 0 到 10000，分批查询
        for min_q in range(0, 10001, INVENTORY_BATCH_SIZE):
            max_q = min(min_q + INVENTORY_BATCH_SIZE - 1, 10000)

            logger.info(f"查询库存范围: {min_q}-{max_q}")

            try:
                response = await client.get_inventory_range(min_q, max_q)
            except RakutenAPIError as e:
                error_msg = f"Failed to get inventory range {min_q}-{max_q}: {e}"
                logger.error(error_msg)
                # 记录 API 错误到事件表
                inv_service = InventoryService(self.session)
                await inv_service.log_api_error(
                    error_message=str(e),
                    store_id=store_id,
                    operation="get_inventory_range",
                    error_details={
                        "min_quantity": min_q,
                        "max_quantity": max_q,
                        "error_code": e.code if hasattr(e, 'code') else None,
                    }
                )
                await self.session.commit()
                continue

            inventories = response.get("inventories", [])

            if not inventories:
                logger.info(f"库存范围 {min_q}-{max_q} 为空，继续下一个范围")
                continue

            for inv in inventories:
                manage_number = inv.get("manageNumber", "")
                variant_id = inv.get("variantId", "")

                if not manage_number:
                    continue

                # SKU ID 使用 variantId（实际 SKU 编号）
                # manageNumber 用作 original_sku
                sku_id = normalize_sku(variant_id)
                original_sku = variant_id

                # 去重检查
                if sku_id in processed_skus:
                    continue
                processed_skus.add(sku_id)

                try:
                    # 获取商品详细信息
                    success = await self._process_inventory(
                        inv, store_id, sku_id, original_sku, client
                    )
                    if success:
                        synced += 1
                except Exception as e:
                    errors.append({
                        "sku_id": sku_id,
                        "manage_number": manage_number,
                        "error": str(e)
                    })

        # 更新最后同步时间
        await self.session.execute(
            update(Store)
            .where(Store.store_id == store_id)
            .values(last_sku_sync_at=utcnow())
        )
        await self.session.commit()

        logger.info(f"为店铺 {store_id} 同步了 {synced} 个 SKU，{len(errors)} 个错误")

        return {
            "synced": synced,
            "errors": errors,
            "last_sync_at": utcnow().isoformat(),
        }

    async def _process_inventory(
        self,
        inv: dict[str, Any],
        store_id: str,
        sku_id: str,
        original_sku: str,
        client,
    ) -> bool:
        """处理单个库存记录"""
        manage_number = inv.get("manageNumber", "")

        try:
            # 获取商品详细信息
            item_details = await self._get_item_with_details(
                client, store_id, manage_number, sku_id
            )

            if item_details:
                # SKU 已创建
                return True

        except RakutenAPIError as e:
            # API 调用失败，记录错误但继续处理下一个
            logger.warning(f"获取商品 {manage_number} 详情失败: {e}")
            inv_service = InventoryService(self.session)
            await inv_service.log_api_error(
                error_message=str(e),
                store_id=store_id,
                sku_id=sku_id,
                operation="get_item_details",
                error_details={
                    "manage_number": manage_number,
                    "error_code": e.code if hasattr(e, 'code') else None,
                }
            )
            await self.session.commit()
            return False

        return False

    async def _get_item_with_details(
        self,
        client,
        store_id: str,
        manage_number: str,
        sku_id: str,
    ) -> bool:
        """获取商品详情并处理"""
        try:
            item_response = await client.get_item_details(manage_number)

            if not item_response:
                return False

            # 解析商品数据
            item_data = item_response.get("item", item_response)

            if not item_data:
                return False

            item_name = item_data.get("itemName", "")
            item_url = item_data.get("itemUrl", "")
            image_url = item_data.get("imageUrl", item_data.get("mediumImageUrl", ""))
            item_price = item_data.get("itemPrice", 0)

            # 创建或更新 SKU
            inv_service = InventoryService(self.session)
            sku = await inv_service.get_or_create_sku(
                sku_id=sku_id,
                original_sku=sku_id,
                sku_name=item_name,
                environment="prod"
            )

            # 更新 SKU 名称和元数据
            if sku.sku_name != item_name:
                sku.sku_name = item_name

            extra_data = sku.extra_data or {}
            extra_data.update({
                "item_name": item_name,
                "item_url": item_url,
                "image_url": image_url,
                "item_price": item_price,
                "manage_number": manage_number,
            })
            sku.extra_data = extra_data

            # 更新别名（包含原始 sku_id）
            aliases = sku.aliases or {}
            aliases["rakuten"] = sku_id
            sku.aliases = aliases

            await self.session.flush()

            # 检查是否已注册到店铺
            existing_store_sku = await self.session.execute(
                select(StoreSku).where(
                    StoreSku.sku_id == sku_id,
                    StoreSku.store_id == store_id,
                )
            )

            if not existing_store_sku.scalar_one_or_none():
                # 注册到店铺
                store_sku = StoreSku(
                    sku_id=sku_id,
                    store_id=store_id,
                )
                self.session.add(store_sku)

            await self.session.flush()
            logger.info(f"成功同步 SKU: {sku_id} - {item_name}")
            return True

        except RakutenAPIError as e:
            # API 调用失败
            logger.error(f"获取商品 {manage_number} 详情失败: {e}")
            inv_service = InventoryService(self.session)
            await inv_service.log_api_error(
                error_message=str(e),
                store_id=store_id,
                sku_id=sku_id,
                operation="get_item_details",
                error_details={
                    "manage_number": manage_number,
                    "error_code": e.code if hasattr(e, 'code') else None,
                }
            )
            await self.session.commit()
            return False

    async def _sync_with_mock_data(self, store_id: str) -> dict[str, Any]:
        """使用模拟数据同步SKU"""
        import random

        # 生成模拟商品数据
        mock_items = []
        for i in range(1, random.randint(5, 15)):
            mock_items.append({
                "skuNumber": f"MOCK-SKU-{i:03d}",
                "itemName": f"模拟商品 {i}",
                "itemUrl": f"https://example.com/mock{i}",
                "imageUrl": f"https://example.com/mock{i}.jpg" if i % 2 == 0 else None,
                "itemManagementNumber": f"MANAGEMENT-{i:03d}" if i % 3 == 0 else None,
                "itemPrice": random.randint(100, 10000),
            })

        synced = 0
        errors = []

        for item in mock_items:
            try:
                await self._process_item(item, store_id)
                synced += 1
            except Exception as e:
                errors.append({"item": item.get("itemName", "unknown"), "error": str(e)})

        # 更新最后同步时间
        from sqlalchemy import update
        await self.session.execute(
            update(Store)
            .where(Store.store_id == store_id)
            .values(last_sku_sync_at=utcnow())
        )
        await self.session.commit()

        logger.info(f"模拟模式：为店铺 {store_id} 同步了 {synced} 个SKU")

        return {
            "synced": synced,
            "errors": errors,
            "last_sync_at": utcnow().isoformat(),
        }

    async def _process_item(self, item: dict[str, Any], store_id: str):
        """处理单个商品项（仅用于模拟模式）"""
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

    async def import_from_csv(
        self,
        store_id: str,
        csv_path: str,
        csv_type: str = "full"
    ) -> dict[str, Any]:
        """从 CSV 文件导入 SKU

        Args:
            store_id: 店铺 ID
            csv_path: CSV 文件路径
            csv_type: CSV 类型 ("full" 或 "daily")

        Returns:
            导入结果统计
        """
        result = await self.session.execute(
            select(Store).where(Store.store_id == store_id)
        )
        store = result.scalar_one_or_none()

        if not store:
            return {"error": "Store not found", "imported": 0}

        # 检查文件是否存在
        if not os.path.exists(csv_path):
            return {"error": f"CSV file not found: {csv_path}", "imported": 0}

        synced = 0
        updated = 0
        errors = []
        processed_skus = set()

        logger.info(f"开始从 CSV 导入 SKU: {csv_path} (类型: {csv_type})")

        try:
            with codecs.open(csv_path, 'r', CSV_ENCODING, errors='ignore') as f:
                reader = csv.reader(f)
                header = next(reader)  # 跳过表头

                logger.info(f"CSV 表头列数: {len(header)}")

                for row_num, row in enumerate(reader, start=2):  # 从第2行开始计数
                    try:
                        # 根据 CSV 类型提取数据
                        if csv_type == "full":
                            item_data = self._parse_csv_row_full(row)
                        else:
                            item_data = self._parse_csv_row_daily(row, header, row_num)

                        if not item_data:
                            continue

                        sku_id = item_data.get("sku_id")
                        if not sku_id:
                            continue

                        # 去重
                        if sku_id in processed_skus:
                            continue
                        processed_skus.add(sku_id)

                        # 创建或更新 SKU
                        result = await self._import_sku_from_csv(
                            store_id,
                            sku_id,
                            item_data
                        )

                        if result == "created":
                            synced += 1
                        elif result == "updated":
                            updated += 1

                    except Exception as e:
                        logger.warning(f"处理 CSV 行 {row_num} 时出错: {e}")
                        errors.append({
                            "row": row_num,
                            "error": str(e)
                        })

            # 更新最后同步时间
            await self.session.execute(
                update(Store)
                .where(Store.store_id == store_id)
                .values(last_sku_sync_at=utcnow())
            )
            await self.session.commit()

            logger.info(
                f"CSV 导入完成: 新增 {synced} 个, 更新 {updated} 个, "
                f"错误 {len(errors)} 个"
            )

            return {
                "imported": synced,
                "updated": updated,
                "errors": errors,
                "total": synced + updated,
                "last_sync_at": utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"CSV 导入失败: {e}")
            await self.session.rollback()
            return {"error": str(e), "imported": 0}

    def _parse_csv_row_full(self, row: list[str]) -> dict[str, Any] | None:
        """解析 全部.csv 的行"""
        if len(row) <= 5:
            return None

        manage_number = row[CSV_FIELDS_FULL["manage_number"]]
        item_name = row[CSV_FIELDS_FULL["item_name"]]
        sku_id = row[CSV_FIELDS_FULL["sku_id"]]
        price = row[CSV_FIELDS_FULL["price"]] if len(row) > CSV_FIELDS_FULL["price"] else None

        # 跳过没有 SKU ID 的行
        if not sku_id:
            return None

        return {
            "manage_number": manage_number,
            "item_name": item_name,
            "sku_id": sku_id,
            "price": int(price) if price else None,
        }

    def _parse_csv_row_daily(self, row: list[str], header: list[str], row_num: int) -> dict[str, Any] | None:
        """解析 平时.csv 的行

        平时.csv 的结构不同：
        - 第 1 行: 商品信息（管理编号、商品名等）
        - 第 2+ 行: SKU 信息（SKU 编号等）
        """
        # SKU 编号列的列索引需要查找
        # 通常在较后的列，可能是第 6 列或更后
        if len(row) <= 5:
            return None

        manage_number = row[CSV_FIELDS_DAILY["manage_number"]]
        item_name = row[CSV_FIELDS_DAILY["item_name"]]

        # 查找 SKU 管理编号列
        sku_id = None
        for i, col in enumerate(header):
            if "SKU" in col and "管理番号" in col:
                if i < len(row):
                    sku_id = row[i]
                    break

        if not sku_id:
            return None

        return {
            "manage_number": manage_number,
            "item_name": item_name,
            "sku_id": sku_id,
            "price": None,
        }

    async def _import_sku_from_csv(
        self,
        store_id: str,
        sku_id: str,
        item_data: dict[str, Any]
    ) -> str:
        """从 CSV 数据导入单个 SKU

        Returns:
            "created" - 新创建
            "updated" - 已更新
            "skipped" - 跳过
        """
        sku_id_normalized = normalize_sku(item_data["sku_id"])
        manage_number = item_data.get("manage_number", "")
        item_name = item_data.get("item_name", "")
        price = item_data.get("price")

        inv_service = InventoryService(self.session)

        # 创建或获取 SKU
        sku = await inv_service.get_or_create_sku(
            sku_id=sku_id_normalized,
            original_sku=item_data["sku_id"],
            sku_name=item_name or sku_id_normalized,
            environment="prod"
        )

        # 检查是否是新创建的
        is_new = (sku.sku_name == sku_id_normalized and not item_name)

        # 更新 SKU 名称
        if item_name and sku.sku_name != item_name:
            sku.sku_name = item_name

        # 更新额外数据
        extra_data = sku.extra_data or {}
        extra_data.update({
            "item_name": item_name,
            "manage_number": manage_number,
            "import_source": "csv",
            "imported_at": utcnow().isoformat(),
        })
        if price:
            extra_data["item_price"] = price

        sku.extra_data = extra_data

        # 更新别名
        aliases = sku.aliases or {}
        aliases["rakuten"] = item_data["sku_id"]
        if manage_number:
            aliases["manage_number"] = manage_number
        sku.aliases = aliases

        await self.session.flush()

        # 检查是否已注册到店铺
        existing_store_sku = await self.session.execute(
            select(StoreSku).where(
                StoreSku.sku_id == sku_id_normalized,
                StoreSku.store_id == store_id,
            )
        )

        if not existing_store_sku.scalar_one_or_none():
            # 注册到店铺
            store_sku = StoreSku(
                sku_id=sku_id_normalized,
                store_id=store_id,
            )
            self.session.add(store_sku)
            await self.session.flush()

        if is_new:
            return "created"
        else:
            return "updated"
