import csv
import io
import logging
from typing import Any

import chardet

from sqlalchemy import select

from app.db.models import (
    EventTypeEnum,
    ImportModeEnum,
    InventoryEvent,
    InventorySnapshot,
    SkuMaster,
    SourceEnum,
    StoreSku,
    UploadedFile,
    ZeroHandlingEnum,
)
from app.db.schemas import EventTypeEnumSchema, ImportModeEnumSchema, SourceEnumSchema, ZeroHandlingEnumSchema
from app.utils.helpers import generate_file_token, generate_token, normalize_sku, utcnow

logger = logging.getLogger(__name__)


class CsvImportService:
    """CSV导入服务"""

    SKU_COLUMN_NAMES = [
        "システム連携用SKU番号",
        "SKU",
        "sku",
        "sku_number",
    ]

    QUANTITY_COLUMN_NAMES = [
        "数量",
        "在庫数",
        "quantity",
        "stock",
        "stock_quantity",
    ]

    METADATA_COLUMN_NAMES = {
        "item_name": ["商品名", "item_name", "itemName"],
        "option1": ["バリエーション項目選択肢1", "option1", "variation1"],
        "option2": ["バリエーション項目選択肢2", "option2", "variation2"],
        "image_path": ["商品画像パス1", "image_path", "imageUrl"],
    }

    def __init__(self, session):
        self.session = session

    def detect_encoding(self, content: bytes) -> str:
        """检测文件编码"""
        result = chardet.detect(content)
        encoding = result.get("encoding", "utf-8")
        if encoding.lower() in ("shift_jis", "sjis"):
            return "shift_jis"
        return encoding or "utf-8"

    def detect_delimiter(self, content: str) -> str:
        """检测分隔符"""
        first_line = content.split("\n")[0] if "\n" in content else content
        if "\t" in first_line:
            return "\t"
        if "," in first_line:
            return ","
        return ","

    def parse_csv(self, content: str, delimiter: str = ",") -> list[dict[str, Any]]:
        """解析CSV内容"""
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        return list(reader)

    def find_column(self, row: dict[str, str], possible_names: list[str]) -> str | None:
        """查找可能的列名"""
        for name in possible_names:
            if name in row:
                return row[name]
        return None

    def find_sku_column(self, headers: list[str]) -> str | None:
        """查找SKU列"""
        for name in self.SKU_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    def find_quantity_column(self, headers: list[str]) -> str | None:
        """查找数量列"""
        for name in self.QUANTITY_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    async def preview_import(
        self,
        content: str,
        store_id: str | None,
        import_mode: ImportModeEnumSchema,
        zero_handling: ZeroHandlingEnumSchema,
    ) -> dict[str, Any]:
        """预览导入数据"""
        delimiter = self.detect_delimiter(content)
        rows = self.parse_csv(content, delimiter)

        if not rows:
            return {"error": "CSV file is empty", "total_rows": 0}

        headers = list(rows[0].keys())
        sku_column = self.find_sku_column(headers)
        quantity_column = self.find_quantity_column(headers)

        if not sku_column:
            return {"error": "SKU column not found", "total_rows": 0}

        total_rows = len(rows)
        new_skus = 0
        registered_skus = 0
        reset_skus = 0
        zero_negative_skus = 0
        preview_rows = []

        for row in rows[:10]:
            raw_sku = row.get(sku_column, "").strip()
            if not raw_sku:
                continue

            sku_id = normalize_sku(raw_sku)
            quantity_str = row.get(quantity_column, "") if quantity_column else ""
            csv_quantity = int(quantity_str) if quantity_str.isdigit() else None

            existing = await self._get_sku_snapshot(sku_id)

            action = "metadata_only"
            if import_mode == ImportModeEnumSchema.RESET_STOCK:
                if csv_quantity is not None:
                    action = "set_stock"
                    reset_skus += 1
                elif zero_handling == ZeroHandlingEnumSchema.ZERO_NEGATIVE:
                    if existing and existing.internal_available < 0:
                        zero_negative_skus += 1

            if not existing:
                new_skus += 1
            else:
                registered_skus += 1

            preview_rows.append({
                "sku_id": sku_id,
                "original_sku": raw_sku,
                "current_stock": existing.internal_available if existing else 0,
                "csv_quantity": csv_quantity,
                "action": action,
            })

        return {
            "total_rows": total_rows,
            "new_skus": new_skus,
            "registered_skus": registered_skus,
            "reset_skus": reset_skus,
            "zero_negative_skus": zero_negative_skus,
            "preview_rows": preview_rows,
        }

    async def _get_sku_snapshot(self, sku_id: str):
        """获取SKU快照"""
        from sqlalchemy import select
        result = await self.session.execute(
            select(InventorySnapshot).where(InventorySnapshot.sku_id == sku_id)
        )
        return result.scalar_one_or_none()

    async def execute_import(
        self,
        content: str,
        store_id: str | None,
        import_mode: ImportModeEnumSchema,
        zero_handling: ZeroHandlingEnumSchema,
        operator: str,
    ) -> dict[str, Any]:
        """执行导入"""
        token = generate_file_token(content)

        existing = await self.session.execute(
            select(UploadedFile).where(UploadedFile.token == token)
        )
        if existing.scalar_one_or_none():
            return {"error": "This file has already been imported", "imported": 0}

        delimiter = self.detect_delimiter(content)
        rows = self.parse_csv(content, delimiter)

        if not rows:
            return {"error": "CSV file is empty", "imported": 0}

        headers = list(rows[0].keys())
        sku_column = self.find_sku_column(headers)
        quantity_column = self.find_quantity_column(headers)

        if not sku_column:
            return {"error": "SKU column not found", "imported": 0}

        imported = 0

        db_import_mode = ImportModeEnum[import_mode.name]
        db_zero_handling = ZeroHandlingEnum[zero_handling.name]

        uploaded_file = UploadedFile(
            filename="import.csv",
            original_content=content[:1000],
            token=token,
            store_id=store_id,
            import_mode=db_import_mode,
            zero_handling=db_zero_handling,
            operator=operator,
            status="processing",
        )
        self.session.add(uploaded_file)

        for row in rows:
            raw_sku = row.get(sku_column, "").strip()
            if not raw_sku:
                continue

            sku_id = normalize_sku(raw_sku)
            original_sku = raw_sku

            sku = await self._get_or_create_sku(sku_id, original_sku, row)

            if store_id:
                await self._register_sku_to_store(sku_id, store_id)

            if import_mode == ImportModeEnumSchema.RESET_STOCK:
                quantity_str = row.get(quantity_column, "") if quantity_column else ""
                csv_quantity = int(quantity_str) if quantity_str and quantity_str.isdigit() else None

                target_quantity = None
                if csv_quantity is not None:
                    target_quantity = csv_quantity
                elif zero_handling == ZeroHandlingEnumSchema.SET_ZERO:
                    target_quantity = 0
                elif zero_handling == ZeroHandlingEnumSchema.ZERO_NEGATIVE:
                    existing_snapshot = await self._get_sku_snapshot(sku_id)
                    if existing_snapshot and existing_snapshot.internal_available < 0:
                        target_quantity = 0

                if target_quantity is not None:
                    existing_snapshot = await self._get_sku_snapshot(sku_id)
                    current_stock = existing_snapshot.internal_available if existing_snapshot else 0
                    quantity_change = target_quantity - current_stock

                    event = InventoryEvent(
                        event_type=EventTypeEnum.INIT_RESET.value,
                        sku_id=sku_id,
                        quantity=quantity_change,
                        store_id=store_id,
                        operator=operator,
                        reason="CSV导入重置库存",
                        source=SourceEnum.IMPORT,
                        token=generate_token(),
                        event_metadata={"csv_original": csv_quantity, "target": target_quantity},
                    )
                    self.session.add(event)
                    await self.session.flush()

                    await self._update_snapshot(sku_id, quantity_change, event.event_id)

            imported += 1

        uploaded_file.status = "processed"
        await self.session.commit()

        return {
            "imported": imported,
            "token": token,
        }

    async def _get_or_create_sku(self, sku_id: str, original_sku: str, row: dict):
        """获取或创建SKU"""
        from sqlalchemy import select

        result = await self.session.execute(
            select(SkuMaster).where(SkuMaster.sku_id == sku_id)
        )
        sku = result.scalar_one_or_none()

        metadata = {}
        for key, names in self.METADATA_COLUMN_NAMES.items():
            value = self.find_column(row, names)
            if value:
                metadata[key] = value

        if sku:
            sku.extra_data = {**sku.extra_data, **metadata}
        else:
            sku = SkuMaster(
                sku_id=sku_id,
                original_sku=original_sku,
                sku_name=metadata.get("item_name", sku_id),
                environment="prod",
                status="active",
                extra_data=metadata,
                aliases={"rakuten": original_sku},
            )
            self.session.add(sku)

        await self.session.flush()
        return sku

    async def _register_sku_to_store(self, sku_id: str, store_id: str):
        """注册SKU到店铺"""
        from sqlalchemy import select

        result = await self.session.execute(
            select(StoreSku).where(
                StoreSku.sku_id == sku_id,
                StoreSku.store_id == store_id,
            )
        )
        if not result.scalar_one_or_none():
            store_sku = StoreSku(sku_id=sku_id, store_id=store_id)
            self.session.add(store_sku)
            await self.session.flush()

    async def _update_snapshot(self, sku_id: str, quantity_change: int, event_id):
        """更新库存快照"""
        from sqlalchemy import select, update

        result = await self.session.execute(
            select(InventorySnapshot).where(InventorySnapshot.sku_id == sku_id)
        )
        snapshot = result.scalar_one_or_none()

        if snapshot:
            new_quantity = snapshot.internal_available + quantity_change
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
                internal_available=quantity_change,
                last_event_id=event_id,
            )
            self.session.add(snapshot)

        await self.session.flush()
