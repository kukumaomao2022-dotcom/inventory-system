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
from app.db.schemas import EventTypeEnumSchema, ImportModeEnumSchema, InventoryModeEnumSchema, SourceEnumSchema, ZeroHandlingEnumSchema
from app.utils.helpers import generate_file_token, generate_token, normalize_sku, utcnow

logger = logging.getLogger(__name__)


class CsvImportService:
    """CSV导入服务 - 库存管理系统专用"""

    # 标准导入格式列名（库存系统专用）
    SKU_COLUMN_NAMES = [
        "システム連携用SKU番号",  # 最优先 - 系统联动用SKU编号
        "SKU管理番号",  # 乐天 SKU 编号
        "SKU",
        "sku",
        "sku_number",
    ]

    QUANTITY_COLUMN_NAMES = [
        "在庫数",
        "数量",
        "quantity",
        "stock",
        "stock_quantity",
    ]

    # 颜色字段
    COLOR_COLUMN_NAMES = [
        "color",
        "颜色",
        "バリエーション項目選択肢1",
        "option1",
        "variation1",
        "colour",
    ]

    # 尺寸字段
    SIZE_COLUMN_NAMES = [
        "size",
        "尺寸",
        "バリエーション項目選択肢2",
        "option2",
        "variation2",
    ]

    # 店铺编号字段
    STORE_CODE_COLUMN_NAMES = [
        "store_code",
        "store_id",
        "店铺编号",
        "store",
    ]

    # 商品名称字段
    ITEM_NAME_COLUMN_NAMES = [
        "商品名",
        "item_name",
        "itemName",
    ]

    # 商品管理番号
    MANAGE_NUMBER_COLUMN_NAMES = [
        "商品管理番号（商品URL）",
        "manage_number",
        "商品管理番号",
    ]

    # 图片字段
    IMAGE_COLUMN_NAMES = [
        "image_url",
        "imageUrl",
        "商品画像パス",
        "image_path",
        "image",
    ]

    # 不导入的字段（将被忽略）
    IGNORED_FIELDS = {
        # 价格相关
        "price", "価格", "通常購入販売価格", "表示価格", "販売価格",
        "amount", "cost",
        # 描述相关
        "description", "説明", "商品説明",
        # 重量尺寸详情
        "weight", "重量", "length", "length", "width", "height",
        # 其他非库存字段
        "brand", "category", "manufacturer", "supplier",
    }

    # 乐天导出格式列名（全部.csv）
    RAKUTEN_FULL_COLUMN_NAMES = {
        "system_sku_number": ["システム連携用SKU番号"],
        "manage_number": ["商品管理番号（商品URL）"],
        "item_number": ["商品番号"],
        "item_name": ["商品名"],
        "sku_id": ["SKU管理番号"],
        "price": ["通常購入販売価格"],
        "display_price": ["表示価格"],
    }

    # 乐天导出格式列名（平时.csv）
    RAKUTEN_DAILY_COLUMN_NAMES = {
        "manage_number": ["商品管理番号（商品URL）"],
        "item_number": ["商品番号"],
        "item_name": ["商品名"],
        "sku_id": ["SKU管理番号"],
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

    def find_rakuten_sku_column(self, headers: list[str]) -> str | None:
        """查找乐天 CSV 的 SKU 列"""
        for name in self.RAKUTEN_FULL_COLUMN_NAMES["sku_id"]:
            if name in headers:
                return name
        return None

    def find_quantity_column(self, headers: list[str]) -> str | None:
        """查找数量列"""
        for name in self.QUANTITY_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    def find_color_column(self, headers: list[str]) -> str | None:
        """查找颜色列"""
        for name in self.COLOR_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    def find_size_column(self, headers: list[str]) -> str | None:
        """查找尺寸列"""
        for name in self.SIZE_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    def find_store_code_column(self, headers: list[str]) -> str | None:
        """查找店铺编号列"""
        for name in self.STORE_CODE_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    def find_item_name_column(self, headers: list[str]) -> str | None:
        """查找商品名列"""
        for name in self.ITEM_NAME_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    def find_manage_number_column(self, headers: list[str]) -> str | None:
        """查找商品管理番号列"""
        for name in self.MANAGE_NUMBER_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    def find_image_column(self, headers: list[str]) -> str | None:
        """查找图片列"""
        for name in self.IMAGE_COLUMN_NAMES:
            if name in headers:
                return name
        return None

    def generate_full_sku(self, base_sku: str, color: str | None = None, size: str | None = None) -> str:
        """生成完整SKU: 基础SKU + 颜色 + 尺寸"""
        # 规范化基础SKU
        base = normalize_sku(base_sku)

        # 如果没有颜色和尺寸，直接返回基础SKU
        if not color and not size:
            return base

        # 添加颜色编码
        color_suffix = ""
        if color:
            # 提取颜色编码（取首字母或简写）
            color_code = color.strip()
            if color_code:
                # 如果颜色是代码（如 01, 02），直接使用
                if color_code.isdigit() and len(color_code) <= 2:
                    color_suffix = f"-C{color_code}"
                else:
                    # 否则取前2个字符大写
                    color_suffix = f"-{color_code[:2].upper()}"

        # 添加尺寸编码
        size_suffix = ""
        if size:
            size_code = size.strip()
            if size_code:
                size_suffix = f"-{size_code.upper()}"

        return f"{base}{color_suffix}{size_suffix}"

    def filter_essential_fields(self, row: dict[str, str], headers: list[str]) -> dict[str, str]:
        """只保留规范中定义的字段，过滤无关字段"""
        essential = {}

        # 获取管理番号（放在最前面）
        manage_col = self.find_manage_number_column(headers)
        if manage_col and manage_col in row:
            essential["manage_number"] = row[manage_col]

        # 获取SKU
        sku_col = self.find_sku_column(headers)
        if sku_col and sku_col in row:
            essential["SKU"] = row[sku_col]

        # 获取颜色
        color_col = self.find_color_column(headers)
        if color_col and color_col in row:
            essential["color"] = row[color_col]

        # 获取尺寸
        size_col = self.find_size_column(headers)
        if size_col and size_col in row:
            essential["size"] = row[size_col]

        # 获取数量
        qty_col = self.find_quantity_column(headers)
        if qty_col and qty_col in row:
            essential["quantity"] = row[qty_col]

        # 获取店铺编号
        store_col = self.find_store_code_column(headers)
        if store_col and store_col in row:
            essential["store_code"] = row[store_col]

        # 获取图片URL
        image_col = self.find_image_column(headers)
        if image_col and image_col in row:
            essential["image_url"] = row[image_col]

        return essential

    async def preview_import(
        self,
        content: str,
        store_id: str | None,
        import_mode: ImportModeEnumSchema,
        inventory_mode: InventoryModeEnumSchema,
        zero_handling: ZeroHandlingEnumSchema,
        skip_no_sku: bool = True,
    ) -> dict[str, Any]:
        """预览导入数据

        Args:
            content: CSV 文件内容
            store_id: 店铺 ID
            import_mode: 导入模式
            inventory_mode: 库存导入模式（replace/add/skip_zero）
            zero_handling: 数量为0时的处理方式
            skip_no_sku: 是否跳过没有 SKU 的行（默认 True）
        """
        delimiter = self.detect_delimiter(content)
        rows = self.parse_csv(content, delimiter)

        if not rows:
            return {
                "total_rows": 0,
                "new_skus": 0,
                "registered_skus": 0,
                "reset_skus": 0,
                "zero_negative_skus": 0,
                "preview_rows": [],
            }

        # 分析 CSV 数据
        new_skus = 0
        registered_skus = 0
        reset_skus = 0
        zero_negative_skus = 0
        skipped_no_sku = 0

        for row in rows:
            sku_value = self.find_column(row, self.SKU_COLUMN_NAMES)
            if not sku_value:
                if skip_no_sku:
                    skipped_no_sku += 1
                continue

            sku_id = normalize_sku(sku_value)

            # 检查 SKU 是否已存在
            result = await self.session.execute(
                select(SkuMaster).where(SkuMaster.sku_id == sku_id)
            )
            existing = result.scalar_one_or_none()

            if not existing:
                new_skus += 1
            else:
                # 检查是否已注册到店铺
                if store_id:
                    result = await self.session.execute(
                        select(StoreSku).where(
                            StoreSku.store_id == store_id,
                            StoreSku.sku_id == sku_id
                        )
                    )
                    if not result.scalar_one_or_none():
                        registered_skus += 1
                    else:
                        reset_skus += 1
                else:
                    reset_skus += 1

            # 检查数量（仅在有库存导入时检查）
            quantity_value = self.find_column(row, self.QUANTITY_COLUMN_NAMES)
            quantity = int(quantity_value) if quantity_value and quantity_value.isdigit() else 0

            # 检查 skip_zero 模式
            if inventory_mode == InventoryModeEnumSchema.SKIP_ZERO:
                if quantity == 0:
                    # 需要检查当前库存
                    result = await self.session.execute(
                        select(InventorySnapshot).where(InventorySnapshot.sku_id == sku_id)
                    )
                    snapshot = result.scalar_one_or_none()
                    current_inventory = snapshot.internal_available if snapshot else 0
                    if current_inventory <= 0:
                        zero_negative_skus += 1

            # 检查 zero_handling 模式
            if quantity == 0 and zero_handling == ZeroHandlingEnumSchema.ZERO_NEGATIVE:
                zero_negative_skus += 1

        # 获取表头用于过滤
        headers = list(rows[0].keys()) if rows else []

        # 过滤预览行，只保留规范字段（跳过没有 SKU 的行）
        preview_rows = []
        for row in rows[:10]:
            sku_value = self.find_column(row, self.SKU_COLUMN_NAMES)
            if skip_no_sku and not sku_value:
                continue
            preview_rows.append(self.filter_essential_fields(row, headers))

        return {
            "total_rows": len(rows),
            "new_skus": new_skus,
            "registered_skus": registered_skus,
            "reset_skus": reset_skus,
            "zero_negative_skus": zero_negative_skus,
            "skipped_no_sku": skipped_no_sku,
            "preview_rows": preview_rows,
        }

    async def import_rakuten_csv(
        self,
        content: str,
        store_id: str,
        operator: str = "system"
    ) -> dict[str, Any]:
        """导入乐天导出的 CSV 文件

        Args:
            content: CSV 文件内容（Shift-JIS 编码）
            store_id: 店铺 ID
            operator: 操作员

        Returns:
            导入结果统计
        """
        delimiter = self.detect_delimiter(content)
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return {"error": "CSV file is empty", "imported": 0}

        headers = rows[0]

        # 检测 CSV 类型
        # 优先使用 システム連携用SKU番号（系统联动用SKU编号）
        system_sku_column = None
        sku_column = self.find_rakuten_sku_column(headers)

        # 如果有 システム連携用SKU番号 列，优先使用它
        if self.RAKUTEN_FULL_COLUMN_NAMES["system_sku_number"][0] in headers:
            system_sku_column = self.RAKUTEN_FULL_COLUMN_NAMES["system_sku_number"][0]

        if not sku_column:
            # 不是乐天 CSV 格式，尝试标准格式
            sku_column = self.find_sku_column(headers)
            if not sku_column:
                return {"error": "SKU column not found", "imported": 0}

        # 确定最终使用的 SKU 列
        final_sku_column = system_sku_column if system_sku_column else sku_column

        # 查找其他列
        manage_number_column = None
        item_name_column = None
        price_column = None

        if final_sku_column in self.RAKUTEN_FULL_COLUMN_NAMES["sku_id"]:
            # 乐天全部.csv 格式
            for name in self.RAKUTEN_FULL_COLUMN_NAMES["manage_number"]:
                if name in headers:
                    manage_number_column = name
                    break
            for name in self.RAKUTEN_FULL_COLUMN_NAMES["item_name"]:
                if name in headers:
                    item_name_column = name
                    break
            for name in self.RAKUTEN_FULL_COLUMN_NAMES["price"]:
                if name in headers:
                    price_column = name
                    break
        else:
            # 尝试平时.csv 格式
            for name in self.RAKUTEN_DAILY_COLUMN_NAMES["manage_number"]:
                if name in headers:
                    manage_number_column = name
                    break
            for name in self.RAKUTEN_DAILY_COLUMN_NAMES["item_name"]:
                if name in headers:
                    item_name_column = name
                    break

        imported = 0
        updated = 0
        skipped = 0
        errors = []

        for i, row in enumerate(rows[1:], start=2):
            try:
                # 使用最终 SKU 列
                sku_id_idx = headers.index(final_sku_column) if final_sku_column in headers else -1
                if sku_id_idx >= 0 and sku_id_idx < len(row):
                    sku_id_raw = row[sku_id_idx]
                else:
                    sku_id_raw = ""
                    
                if not sku_id_raw:
                    skipped += 1
                    continue

                sku_id = normalize_sku(sku_id_raw)

                # 获取或创建 SKU
                sku = await self._get_or_create_sku_rakuten(
                    sku_id=sku_id,
                    original_sku=sku_id_raw,
                    row=row,
                    headers=headers,
                    manage_number_column=manage_number_column,
                    item_name_column=item_name_column,
                    price_column=price_column,
                )

                if sku.extra_data.get("is_new"):
                    imported += 1
                else:
                    updated += 1

                # 注册到店铺
                if store_id:
                    await self._register_sku_to_store(sku_id, store_id)

            except Exception as e:
                sku_id_idx = headers.index(final_sku_column) if final_sku_column in headers else -1
                sku_id_for_error = row[sku_id_idx] if sku_id_idx >= 0 and sku_id_idx < len(row) else ""
                errors.append({
                    "row": i,
                    "error": str(e),
                    "sku_id": sku_id_for_error
                })

        return {
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "total": imported + updated,
        }

    async def _get_or_create_sku_rakuten(
        self,
        sku_id: str,
        original_sku: str,
        row: list[str],
        headers: list[str],
        manage_number_column: str | None = None,
        item_name_column: str | None = None,
        price_column: str | None = None,
    ) -> SkuMaster:
        """获取或创建 SKU（乐天格式）"""
        # 查找已存在的 SKU
        result = await self.session.execute(
            select(SkuMaster).where(SkuMaster.sku_id == sku_id)
        )
        sku = result.scalar_one_or_none()

        # 从 CSV 行中提取数据
        sku_name = "Unknown"
        if item_name_column and item_name_column in headers:
            idx = headers.index(item_name_column)
            if idx < len(row) and row[idx]:
                sku_name = row[idx]

        # 提取图片URL
        image_col = self.find_image_column(headers)
        image_url = None
        if image_col and image_col in headers:
            idx = headers.index(image_col)
            if idx < len(row) and row[idx]:
                image_url = row[idx]

        # 如果 SKU 不存在，创建新的
        if sku is None:
            extra_data = {"is_new": True, "source": "rakuten_import"}
            if image_url:
                extra_data["image_url"] = image_url
            sku = SkuMaster(
                sku_id=sku_id,
                original_sku=original_sku,
                sku_name=sku_name,
                allow_oversell=False,
                environment="prod",
                status="active",
                extra_data=extra_data,
                aliases={},
            )
            self.session.add(sku)
            await self.session.flush()
        else:
            # 更新现有 SKU 的 extra_data 标记
            sku.extra_data["is_new"] = False
            if "source" not in sku.extra_data:
                sku.extra_data["source"] = "rakuten_import"
            # 更新商品名（如果存在）
            if item_name_column and item_name_column in headers:
                idx = headers.index(item_name_column)
                if idx < len(row) and row[idx]:
                    sku.sku_name = row[idx]
            # 更新图片 URL（如果存在）
            if image_url:
                sku.extra_data["image_url"] = image_url
            await self.session.flush()

        return sku

    async def execute_import(
        self,
        content: str,
        store_id: str | None,
        import_mode: ImportModeEnumSchema,
        inventory_mode: InventoryModeEnumSchema,
        zero_handling: ZeroHandlingEnumSchema,
        operator: str = "system",
        skip_no_sku: bool = True,
    ) -> dict[str, Any]:
        """执行CSV导入（标准格式）

        Args:
            content: CSV 文件内容
            store_id: 店铺 ID
            import_mode: 导入模式
            inventory_mode: 库存导入模式（replace/add/skip_zero）
            zero_handling: 数量为0时的处理方式
            operator: 操作员
            skip_no_sku: 是否跳过没有 SKU 的行（默认 True）
        """
        delimiter = self.detect_delimiter(content)
        rows = self.parse_csv(content, delimiter)

        if not rows:
            return {"error": "CSV file is empty", "imported": 0}

        imported = 0
        updated = 0
        skipped = 0
        skipped_no_sku = 0
        errors = []

        for i, row in enumerate(rows, start=1):
            try:
                # 查找 SKU
                sku_value = self.find_column(row, self.SKU_COLUMN_NAMES)
                if not sku_value:
                    if skip_no_sku:
                        skipped_no_sku += 1
                        continue
                    else:
                        errors.append({"row": i, "error": "SKU not found in row"})
                        continue

                sku_id = normalize_sku(sku_value)
                quantity_value = self.find_column(row, self.QUANTITY_COLUMN_NAMES)
                quantity = int(quantity_value) if quantity_value and quantity_value.isdigit() else 0

                # 处理数量为0的情况
                if quantity == 0:
                    if zero_handling == ZeroHandlingEnumSchema.IGNORE:
                        skipped += 1
                        continue
                    elif zero_handling == ZeroHandlingEnumSchema.ZERO_NEGATIVE:
                        quantity = 0

                # 获取或创建 SKU
                sku = await self._get_or_create_sku_standard(
                    sku_id=sku_id,
                    original_sku=sku_value,
                    row=row,
                    import_mode=import_mode,
                )

                if sku.extra_data.get("is_new"):
                    imported += 1
                else:
                    updated += 1

                # 创建库存事件
                if import_mode == ImportModeEnumSchema.RESET_STOCK:
                    if inventory_mode == InventoryModeEnumSchema.SKIP_ZERO:
                        # 跳过零库存模式：数量为0且当前库存为0或负数时跳过
                        # 获取当前库存
                        result = await self.session.execute(
                            select(InventorySnapshot).where(InventorySnapshot.sku_id == sku_id)
                        )
                        snapshot = result.scalar_one_or_none()
                        current_inventory = snapshot.internal_available if snapshot else 0
                        # 只有当前库存 <= 0 时才跳过
                        if current_inventory > 0:
                            await self._reset_stock(sku_id, quantity, operator)
                        else:
                            skipped += 1
                    elif inventory_mode == InventoryModeEnumSchema.ADD:
                        # 累加库存模式
                        # 获取当前库存
                        result = await self.session.execute(
                            select(InventorySnapshot).where(InventorySnapshot.sku_id == sku_id)
                        )
                        snapshot = result.scalar_one_or_none()
                        current_inventory = snapshot.internal_available if snapshot else 0
                        # 创建累加事件
                        event = InventoryEvent(
                            event_type=EventTypeEnum.STOCK_IN,
                            sku_id=sku_id,
                            quantity=quantity,
                            operator=operator,
                            source=SourceEnum.IMPORT,
                            event_metadata={"import_mode": "add"},
                        )
                        self.session.add(event)
                        await self.session.flush()
                        # 更新快照
                        new_inventory = current_inventory + quantity
                        if snapshot is None:
                            snapshot = InventorySnapshot(
                                sku_id=sku_id,
                                internal_available=new_inventory,
                                last_event_id=event.event_id,
                            )
                            self.session.add(snapshot)
                        else:
                            snapshot.internal_available = new_inventory
                            snapshot.last_event_id = event.event_id
                        await self.session.flush()
                    else:
                        # 替换库存模式（默认）
                        await self._reset_stock(sku_id, quantity, operator)
                else:
                    # 仅导入元数据模式
                    pass

                # 注册到店铺
                if store_id:
                    await self._register_sku_to_store(sku_id, store_id)

            except Exception as e:
                errors.append({"row": i, "error": str(e), "sku_id": sku_value if 'sku_value' in locals() else "unknown"})

        return {
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "skipped_no_sku": skipped_no_sku,
            "errors": errors,
            "total": imported + updated,
        }

    async def _get_or_create_sku_standard(
        self,
        sku_id: str,
        original_sku: str,
        row: dict[str, str],
        import_mode: ImportModeEnumSchema,
    ) -> SkuMaster:
        """获取或创建 SKU（标准格式）"""
        result = await self.session.execute(
            select(SkuMaster).where(SkuMaster.sku_id == sku_id)
        )
        sku = result.scalar_one_or_none()

        # 提取元数据
        sku_name = "Unknown"
        item_name_value = self.find_column(row, self.ITEM_NAME_COLUMN_NAMES)
        if item_name_value:
            sku_name = item_name_value

        # 提取图片URL
        image_col = self.find_image_column(list(row.keys()))
        image_url = None
        if image_col and image_col in row:
            image_url = row[image_col]

        if sku is None:
            extra_data = {"is_new": True, "source": "csv_import"}
            if image_url:
                extra_data["image_url"] = image_url
            sku = SkuMaster(
                sku_id=sku_id,
                original_sku=original_sku,
                sku_name=sku_name,
                allow_oversell=False,
                environment="prod",
                status="active",
                extra_data=extra_data,
                aliases={},
            )
            self.session.add(sku)
            await self.session.flush()
        else:
            sku.extra_data["is_new"] = False
            if import_mode == ImportModeEnumSchema.METADATA_ONLY:
                # 仅导入元数据模式，更新商品名
                sku.sku_name = sku_name
                # 更新图片 URL（如果存在）
                if image_url:
                    sku.extra_data["image_url"] = image_url
            elif image_url and "image_url" not in sku.extra_data:
                # 其他模式也更新图片 URL（如果之前没有）
                sku.extra_data["image_url"] = image_url
            await self.session.flush()

        return sku

    async def _reset_stock(self, sku_id: str, quantity: int, operator: str) -> None:
        """重置库存"""
        # 创建重置事件
        event = InventoryEvent(
            event_type=EventTypeEnum.INIT_RESET,
            sku_id=sku_id,
            quantity=quantity,
            operator=operator,
            source=SourceEnum.IMPORT,
            event_metadata={"reset_type": "csv_import"},
        )
        self.session.add(event)
        await self.session.flush()

        # 更新快照
        result = await self.session.execute(
            select(InventorySnapshot).where(InventorySnapshot.sku_id == sku_id)
        )
        snapshot = result.scalar_one_or_none()

        if snapshot is None:
            snapshot = InventorySnapshot(
                sku_id=sku_id,
                internal_available=quantity,
                last_event_id=event.event_id,
            )
            self.session.add(snapshot)
        else:
            snapshot.internal_available = quantity
            snapshot.last_event_id = event.event_id

        await self.session.flush()

    async def _register_sku_to_store(self, sku_id: str, store_id: str) -> None:
        """注册 SKU 到店铺"""
        # 检查是否已经注册
        result = await self.session.execute(
            select(StoreSku).where(
                StoreSku.store_id == store_id,
                StoreSku.sku_id == sku_id
            )
        )
        existing = result.scalar_one_or_none()

        # 如果没有注册，创建新记录
        if existing is None:
            store_sku = StoreSku(store_id=store_id, sku_id=sku_id)
            self.session.add(store_sku)
            await self.session.flush()
