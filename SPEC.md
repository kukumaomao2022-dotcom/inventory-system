# Multi-Store Inventory Synchronization System (Event Sourcing Edition)

## Project Overview
- **Project Name**: Inventory Sync System
- **Type**: FastAPI + PostgreSQL Web Application
- **Core Functionality**: Multi-store inventory management using event sourcing pattern with Rakuten RMS API integration
- **Target Users**: E-commerce merchants managing inventory across multiple Rakuten stores

## Architecture

### Technology Stack
- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Task Queue**: Celery with Redis
- **API Client**: httpx for async HTTP requests
- **Testing**: pytest with unittest.mock

### Project Structure
```
inventory-system/
├── app/
│   ├── api/              # API endpoints
│   ├── core/             # Configuration, security
│   ├── db/               # Database models, migrations
│   ├── services/         # Business logic
│   ├── tasks/            # Celery tasks
│   └── utils/            # Utilities
├── alembic/              # Database migrations
├── tests/                # Unit tests
├── .env                  # Environment variables
├── pyproject.toml        # Project dependencies
└── README.md
```

## Database Schema

### Tables

#### 1. sku_master
| Column | Type | Constraints |
|--------|------|-------------|
| sku_id | VARCHAR(50) | PRIMARY KEY (lowercase) |
| original_sku | VARCHAR(50) | NULL |
| sku_name | VARCHAR(200) | NOT NULL |
| allow_oversell | BOOLEAN | DEFAULT FALSE |
| environment | VARCHAR(10) | NOT NULL, CHECK IN ('test', 'prod') |
| status | VARCHAR(10) | NOT NULL, CHECK IN ('active', 'inactive') |
| metadata | JSONB | DEFAULT '{}' |
| aliases | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

#### 2. stores
| Column | Type | Constraints |
|--------|------|-------------|
| store_id | VARCHAR(50) | PRIMARY KEY |
| store_name | VARCHAR(100) | NOT NULL |
| platform_type | VARCHAR(20) | NOT NULL (rakuten) |
| api_config | JSONB | DEFAULT '{}' |
| status | VARCHAR(10) | DEFAULT 'active' |
| last_sku_sync_at | TIMESTAMPTZ | NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### 3. store_sku
| Column | Type | Constraints |
|--------|------|-------------|
| store_id | VARCHAR(50) | FK to stores |
| sku_id | VARCHAR(50) | FK to sku_master |
| registered_at | TIMESTAMPTZ | DEFAULT NOW() |
| PRIMARY KEY | (store_id, sku_id) | |

#### 4. inventory_events
| Column | Type | Constraints |
|--------|------|-------------|
| event_id | UUID | PRIMARY KEY |
| event_type | ENUM | ORDER_RECEIVED, ORDER_CANCELLED, etc. |
| sku_id | VARCHAR(50) | FK to sku_master |
| quantity | INTEGER | NOT NULL |
| store_id | VARCHAR(50) | FK to stores |
| platform_status | VARCHAR(10) | NULL |
| order_id | VARCHAR(100) | NULL |
| operator | VARCHAR(100) | NOT NULL |
| reason | TEXT | NULL |
| source | ENUM | api, manual, import, system |
| token | VARCHAR(64) | UNIQUE |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### 5. inventory_snapshots
| Column | Type | Constraints |
|--------|------|-------------|
| sku_id | VARCHAR(50) | FK to sku_master, PRIMARY KEY |
| internal_available | INTEGER | NOT NULL |
| last_event_id | UUID | FK to inventory_events |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

#### 6. uploaded_files
| Column | Type | Constraints |
|--------|------|-------------|
| file_id | UUID | PRIMARY KEY |
| filename | VARCHAR(255) | NOT NULL |
| original_content | TEXT | NOT NULL |
| token | VARCHAR(64) | UNIQUE |
| store_id | VARCHAR(50) | FK to stores |
| import_mode | ENUM | metadata_only, reset_stock |
| zero_handling | ENUM | ignore, set_zero, zero_negative |
| operator | VARCHAR(100) | NOT NULL |
| status | VARCHAR(20) | DEFAULT 'pending' |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### 7. audit_log
| Column | Type | Constraints |
|--------|------|-------------|
| log_id | UUID | PRIMARY KEY |
| user | VARCHAR(100) | NOT NULL |
| action | VARCHAR(255) | NOT NULL |
| details | JSONB | DEFAULT '{}' |
| ip | INET | NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

## Core Design Principles

### 1. Case Normalization
- All SKUs stored in lowercase internally (sku_id)
- Original case preserved in original_sku field
- All comparisons use lowercase SKU
- External API calls use original case from aliases or original_sku

### 2. Safety Constraints
- NO physical deletion of SKU records (only status='inactive')
- NO price fields in data model
- Test product ce1111 always preserved in test environment

### 3. Event Sourcing
- All inventory changes recorded as events
- Snapshots store current state
- Full audit trail for reconciliation

## API Endpoints

### Stores
- `GET /api/stores` - List all stores
- `POST /api/stores` - Create store
- `GET /api/stores/{store_id}` - Get store details
- `GET /api/stores/{store_id}/skus` - List SKUs registered to store
- `POST /api/stores/{store_id}/sync-skus` - Trigger SKU sync from Rakuten
- `GET /api/stores/{store_id}/sku-sync-status` - Get sync status

### SKUs
- `GET /api/skus` - List SKUs (filter by environment, store)
- `POST /api/skus` - Create SKU manually
- `GET /api/skus/{sku_id}` - Get SKU details
- `PATCH /api/skus/{sku_id}` - Update SKU (no price)

### Inventory & Events
- `GET /api/inventory/{sku_id}` - Get current inventory
- `POST /api/events/manual` - Manual inventory adjustment
- `GET /api/events/{sku_id}` - Get event timeline

### Import
- `POST /api/import/preview` - Preview CSV import
- `POST /api/import/confirm` - Confirm and execute import

### Sync
- `POST /api/sync/{store_id}` - Manual sync to store
- `GET /api/sync/failed` - List failed sync tasks

### Audit
- `GET /api/audit/logs` - Operation audit logs
- `GET /api/audit/oversell` - Oversell report
- `GET /api/audit/reconcile` - Reconciliation

### Rakuten
- `GET /api/rakuten/auth-test` - Test auth validity
- `POST /api/rakuten/manual-poll` - Manual order poll

### Test
- `POST /api/test/reset` - Reset test data

## Rakuten API Integration

> **最后更新**: 2026-02-17
> **API 版本**: ES 2.0
> **基础 URL**: `https://api.rms.rakuten.co.jp`

### Authentication

#### 认证方式
```
Authorization: ESA <Base64(serviceSecret:licenseKey)>
```

#### 生成方式
```python
import base64

auth_str = f"{service_secret}:{license_key}"
encoded = base64.b64encode(auth_str.encode()).decode()
auth_header = f"ESA {encoded}"
```

#### 认证凭证
| 字段 | 说明 | 示例 |
|------|------|------|
| service_secret | 服务密钥 | `SP416502_ub7B0vRTK9VuHjsL` |
| license_key | 许可密钥 | `SL416502_YuXi3naks7oilYtI` |
| shop_url | 店铺URL (可选) | `coucou-doma.rakuten.co.jp` |

---

### API Endpoints

#### 1. 搜索订单 (searchOrder)

**端点**: `POST /es/2.0/order/searchOrder/`

**请求体**:
```json
{
  "dateType": 1,                    // 日期类型: 1=订单日期
  "startDatetime": "2026-02-01T00:00:00+0900",
  "endDatetime": "2026-02-17T23:59:59+0900",
  "orderProgressList": [100, 300],  // 可选: 订单状态列表
  "shopUrl": "coucou-doma.rakuten.co.jp",
  "PaginationRequestModel": {
    "requestRecordsAmount": 30,
    "requestPage": 1,
    "sortModelList": [
      {"sortColumn": 1, "sortDirection": 2}
    ]
  }
}
```

**响应**:
```json
{
  "orderNumberList": {
    "orderNumber": "123456789-20260217-123456789"
  }
}
```

**注意**: `orderNumberList` 可能是单个对象或数组，需要兼容处理

---

#### 2. 获取订单详情 (getOrder)

**端点**: `POST /es/2.0/order/getOrder`

**请求体**:
```json
{
  "orderNumberList": ["123456789-20260217-123456789"],
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**响应**:
```json
{
  "orderList": {
    "orderNumber": "123456789-20260217-123456789",
    "orderProgress": 100,
    "orderDate": "2026-02-17T12:00:00+0900",
    "itemsModel": {
      "itemsModel": [
        {
          "skuNumber": "ce1111",
          "itemManagementNumber": "ce1111",
          "quantity": 1
        }
      ]
    }
  }
}
```

---

#### 3. 确认订单 (confirmOrder)

**端点**: `POST /es/2.0/order/confirmOrder`

**用途**: 确认订单，将状态从 100 变更为 300

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**注意**: 此操作可能失败，需要重试机制

---

#### 4. 设置库存 (setInventory)

**端点**: `POST /es/2.0/inventory/set`

**请求体**:
```json
{
  "inventoryInfoList": {
    "inventoryInfo": {
      "sku": "ce1111",           // SKU编号
      "inventory": 10,            // 库存数量
      "inventoryType": "0"       // 库存类型: 0=普通库存
    }
  },
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**注意**: SKU 区分大小写，需要使用原始大小写

---

#### 5. 获取商品列表 (getItems)

**端点**: `POST /es/2.0/item/getItems`

**请求体**:
```json
{
  "hits": 100,                    // 每页数量
  "page": 1,                      // 页码
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**响应**:
```json
{
  "itemList": {
    "item": [
      {
        "skuNumber": "ce1111",
        "itemManagementNumber": "ce1111",
        "itemName": "测试商品",
        "itemPrice": 1000,
        "inventory": 50
      }
    ]
  }
}
```

---

### Item API 2.0 (商品API 2.0)

> **最后更新**: 2026-02-17
> **API 版本**: 4.4 (2026/01/20)
> **适用对象**: SKU移行后的店铺

#### 概述

ItemAPI 2.0 是用于获取和更新商品信息的API。

**SKU移行前可用的功能**:
- `items.get`
- `items.search`
- `items.inventory-related-settings.get`
- `items.bulk.get`

#### 功能列表

| 功能 | 说明 | 利用限制 | 权限要求 |
|------|------|----------|----------|
| **items.get** | 根据商品管理番号获取商品信息 | 秒间5请求 | 需要商品一括编辑功能 |
| **items.upsert** | 注册/更新商品信息（全字段更新） | 秒间20请求 | 需要商品一括编辑功能 |
| **items.patch** | 部分更新商品信息 | 秒间20请求 | 需要商品一括编辑功能 |
| **items.delete** | 删除商品信息 | 秒间5请求 | 需要商品一括编辑功能 |
| **items.search** | 搜索商品信息（通常/预订/分发会） | 秒间5请求 | 不需要特别申请 |
| **items.inventory-related-settings.get** | 获取库存相关设置（纳期等） | 秒间1请求 | 不需要特别申请 |
| **items.inventory-related-settings.update** | 更新库存相关设置 | 秒间1请求 | 不需要特别申请 |
| **items.bulk.get** | 批量获取商品信息（最多50件） | 秒间1请求 | 需要商品一括编辑功能 |

**重要说明**:
- `items.upsert` 是全字段更新，请求中未包含的字段会被删除或设为默认值
- `items.patch` 是部分更新，只更新指定的字段

#### items.get

**用途**: 根据商品管理番号获取商品信息

**请求**: GET `/es/2.0/item/items.get?manageNumber={商品管理番号}`

**响应**:
```json
{
  "manageNumber": "ce1111",
  "itemName": "商品名称",
  "variants": [
    {
      "variantId": "001",
      "merchantDefinedSkuId": "ce1111-001",
      "inventory": 50
    }
  ]
}
```

#### items.upsert

**用途**: 注册或更新商品信息（全字段更新）

**注意**: 部分更新功能不存在，请求中未包含的项会被删除或设为默认值

**请求**: POST `/es/2.0/item/items.upsert`

#### items.patch

**用途**: 部分更新商品信息

**注意**: 请求中未包含的项不会更新

**请求**: POST `/es/2.0/item/items.patch`

#### items.delete

**用途**: 删除商品信息

**请求**: DELETE `/es/2.0/item/items.delete?manageNumber={商品管理番号}`

#### items.search

**用途**: 搜索商品信息（通常商品/预订商品/分发会商品）

**请求**: POST `/es/2.0/item/items.search`

**查询参数**:
- `manageNumber`: 商品管理番号（部分匹配）
- `variantId`: 变体ID（部分匹配）
- `merchantDefinedSkuId`: 商户定义SKU ID（部分匹配）
- `hits`: 每页数量（默认: 10）
- `page`: 页码
- `shipFromIds`: 配送リードタイムID的列表
- `createdFrom`: 创建开始日期
- `updatedFrom`: 更新开始日期
- `sortKey`: 排序键（purchasablePeriodStart, purchasablePeriodEnd 等）

#### items.bulk.get

**用途**: 批量获取商品信息（最多50件）

**请求**: POST `/es/2.0/item/items.bulk.get`

#### items.inventory-related-settings.get

**用途**: 获取库存相关设置（纳期等）

**请求**: GET `/es/2.0/item/items.inventory-related-settings.get?manageNumber={商品管理番号}`

**响应字段**:
- `restockOnCancel`: 取消时再入库
- `backOrderFlag`: 预订标志

#### items.inventory-related-settings.update

**用途**: 更新库存相关设置

**请求**: POST `/es/2.0/item/items.inventory-related-settings.update`

#### 新增字段 (4.4版本)

| 字段 | 说明 | 添加版本 |
|------|------|----------|
| `socialGiftFlag` | 社交礼物标志 | 4.2 (2025/10/23) |
| `okihaiSetting` | 赠送设置 | 3.9 (2025/08/28) |

#### 权限要求

**需要申请"商品一括编辑功能"的功能**:
- `items.get`
- `items.upsert`
- `items.patch`
- `items.delete`
- `items.bulk.get`

未申请会返回 AuthError

**不需要申请的功能**:
- `items.search`
- `items.inventory-related-settings.get`
- `items.inventory-related-settings.update`

#### 请求频率限制

| 功能 | 秒间最大请求数 |
|------|---------------|
| items.upsert / items.patch | 20 |
| items.get / items.delete / items.search | 5 |
| items.inventory-related-settings.* / items.bulk.get | 1 |

**注意**: 流量集中时可能受到流量限制

#### 版本更新历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| 1.0 | 2022/07/21 | 初版 |
| 1.3 | 2022/11/30 | 修正 Sample、添加 selections 选项数说明 |
| 1.4 | 2022/12/28 | variantId/merchantDefinedSkuId 改为部分匹配 |
| 2.0 | 2023/04/14 | 添加 IE1105 错误码 |
| 2.9 | 2023/11/16 | 添加 items.bulk.get 功能 |
| 3.0 | 2023/12/13 | 修正 shipFromIds 的说明 |
| 3.9 | 2025/08/28 | 添加 okihaiSetting |
| 4.0 | 2025/09/25 | 删除 Common Gateway Errors 2.2 |
| 4.1 | 2025/10/15 | SKU移行后商品属性必須化猶予期结束 |
| 4.2 | 2025/10/23 | 添加 socialGiftFlag |
| 4.3 | 2025/11/28 | 更新 inventory 说明 |
| 4.4 | 2026/01/20 | attributes Multiplicity 修正为 0..100 |

#### 定期购买更新

定期购买功能已更新，详细说明请参考"定期购买更新后的规格"页面。

#### 参考资源

- SKU 序列图
- SKU 数据结构说明
- 定期购买更新后的规格

---

### Inventory API 2.0 (在庫API 2.0)

> **最后更新**: 2026-02-17
> **API 版本**: 2.3
> **适用对象**: SKU移行后的店铺

#### 概述

InventoryAPI 2.0 是用于获取和更新库存信息的API。

**SKU移行前可用的功能**:
- `inventories.variants.get`
- `inventories.bulk.get.range`

#### 功能列表

| 功能 | 说明 | 请求限制 | HTTP方法 |
|------|------|----------|----------|
| **inventories.variants.get** | 获取库存数（单个SKU） | 秒间 1 请求 | GET |
| **inventories.variants.upsert** | 注册/更新库存数（单个SKU） | 秒间 1 请求 | PUT |
| **inventories.variants.delete** | 删除库存信息（单个SKU） | 秒间 1 请求 | DELETE |
| **inventories.bulk.get.range** | 批量获取库存（按范围，最多1000件） | 秒间 5 请求 | GET |
| **inventories.bulk.get** | 批量获取库存（指定SKU，最多1000件） | 秒间 5 请求 | POST |
| **inventories.bulk.upsert** | 批量注册/更新库存（最多400件） | 秒间 1 请求 | POST |

#### ⚠️ 注意事项

**孤立库存信息处理**:
- 指定不存在的商品或SKU时**不会报错**
- 孤立库存信息会在最后更新日期**24小时后被删除**

#### 更新模式说明

| mode | 说明 | 适用场景 |
|------|------|----------|
| **ABSOLUTE** | 絶対値指定 | 设置库存为指定值（新规注册时必须使用） |
| **RELATIVE** | 相対値指定 | 增減库存（正数增加，负数减少） |

---

#### 1. inventories.variants.get - 获取库存数

**用途**: 根据商品管理番号和SKU管理番号获取库存数

**端点**: `GET /es/2.0/inventories/manage-numbers/{manageNumber}/variants/{variantId}`

**请求限制**: 秒间 1 请求

**Path Parameter**:
| 参数 | 必需 | 类型 | 最大字节 | 说明 |
|------|------|------|----------|------|
| manageNumber | 是 | string | 32 | 商品管理番号（大写自动转为小写） |
| variantId | 是 | string | 32 | SKU管理番号（大小写视为不同字符） |

**响应示例**:
```json
{
    "manageNumber": "mng1234",
    "variantId": "sku1",
    "quantity": 100,
    "created": "2022-01-01T10:00:00+09:00",
    "updated": "2022-02-01T10:30:00+09:00"
}
```

---

#### 2. inventories.variants.upsert - 注册/更新库存数

**用途**: 根据商品管理番号和SKU管理番号注册或更新库存数

**端点**: `PUT /es/2.0/inventories/manage-numbers/{manageNumber}/variants/{variantId}`

**请求限制**: 秒间 1 请求

**请求体**:
```json
{
    "mode": "ABSOLUTE",  // ABSOLUTE: 絶対値指定, RELATIVE: 相対値指定
    "quantity": 100      // 在庫数（最大99999）
}
```

**响应**: 204 No Content

**注意**: 新规注册时必须指定 "ABSOLUTE" 模式

---

#### 3. inventories.variants.delete - 删除库存信息

**用途**: 根据商品管理番号和SKU管理番号删除库存信息

**端点**: `DELETE /es/2.0/inventories/manage-numbers/{manageNumber}/variants/{variantId}`

**请求限制**: 秒间 1 请求

**响应**: 204 No Content

---

#### 4. inventories.bulk.get.range - 批量获取库存（按范围）

**用途**: 根据库存数的上下限批量获取库存（最多1000件）

**端点**: `GET /es/2.0/inventories/bulk-get/range`

**请求限制**: 秒间 5 请求

**Query Parameter**:
| 参数 | 必需 | 类型 | 说明 |
|------|------|------|------|
| minQuantity | 二选一 | number | 最小在庫数（0-99999） |
| maxQuantity | 否 | number | 最大在庫数（0-99999） |

**响应示例**:
```json
{
    "inventories": [
        {
            "manageNumber": "mng1234",
            "variantId": "sku1",
            "quantity": 1,
            "created": "2022-01-01T19:00:00+09:00",
            "updated": "2022-02-28T19:30:00+09:00"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku4",
            "quantity": 5,
            "created": "2022-01-05T19:00:00+09:00",
            "updated": "2022-02-13T19:30:00+09:00"
        }
    ]
}
```

**注意**: 按更新日期降序输出

---

#### 5. inventories.bulk.get - 批量获取库存（指定SKU）

**用途**: 根据商品管理番号和SKU管理番号批量获取库存（最多1000件）

**端点**: `POST /es/2.0/inventories/bulk-get`

**请求限制**: 秒间 5 请求

**请求体**:
```json
{
    "inventories": [
        {
            "manageNumber": "mng1234",
            "variantId": "sku1"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5"
        }
    ]
}
```

---

#### 6. inventories.bulk.upsert - 批量注册/更新库存

**用途**: 批量注册或更新库存数（最多400件）

**端点**: `POST /es/2.0/inventories/bulk-upsert`

**请求限制**: 秒间 1 请求

**请求体**:
```json
{
    "inventories": [
        {
            "manageNumber": "mng1234",
            "variantId": "sku1",
            "mode": "ABSOLUTE",
            "quantity": 70
        },
        {
            "manageNumber": "mng1234",
            "variantId": "sku2",
            "mode": "RELATIVE",
            "quantity": 3
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5",
            "mode": "RELATIVE",
            "quantity": -2
        }
    ]
}
```

**响应**: 204 No Content

---

#### 常见错误代码

| 错误码 | 说明 |
|--------|------|
| GE0014 | 未找到指定的商品或SKU |
| GE0011 | 认证错误 |
| IE0002 | 数值格式无效 |
| IE0003 | 数值范围错误（0-99999） |
| IE0004 | 字符串长度超限（manageNumber/variantId最大32字节） |
| IE0105 | 参数错误 |
| IE0121 | 选择项重复或超限 |
| IE1101 | 预订商品错误 |
| IE1102 | 定期购买错误 |
| IE1105 | 定期购买设置错误 |

---

#### 请求频率限制

| 功能 | 秒间最大请求数 |
|------|---------------|
| inventories.bulk.get / inventories.bulk.get.range | 5 |
| inventories.variants.get / variants.upsert / variants.delete / inventories.bulk.upsert | 1 |

**注意**: 流量集中时可能受到流量限制

---

#### 版本更新历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| 1.0 | 2022/07/21 | 初版 |
| 1.2 | 2022/11/30 | inventories.bulk.get.range 的查询参数修正 |
| 1.3 | 2022/12/28 | variantId 的 Max Byte 改为 32 |
| 1.4 | 2023/02/10 | 添加 GE0011 错误码 |
| 1.5 | 2023/03/17 | 添加共通认证错误 |
| 1.6 | 2023/04/14 | 添加 IE1105 错误码 |
| 1.7 | 2023/04/27 | 修正 CE0001 错误码的 HTTP 状态码 |
| 1.8 | 2023/06/30 | 修正 manageNumber, variantId 的说明文 |
| 1.9 | 2023/08/18 | 添加 IE0121 错误码 |
| 2.0 | 2023/08/31 | 修正 inventories.variants.upsert / bulk.upsert 的 Overview |
| 2.1 | 2023/09/08 | 添加 IE1101, IE1102 错误码 |
| 2.2 | 2023/12/28 | 扩充 SKU 数据结构说明 |
| 2.3 | 2025/09/25 | 删除"2.2.共通认证错误"，添加 Common Gateway Errors 链接 |

---

### Inventory API 2.1 (在庫API 2.1)

> **最后更新**: 2026-02-17
> **API 版本**: 2.1
> **适用对象**: 支持出荷リードタイム和配送リードタイム设置的店铺

#### 概述

InventoryAPI 2.1 在 Inventory API 2.0 的基础上，新增了以下功能：
- **出荷リードタイム (operationLeadTime)**: 设置发货的响应时间
- **配送リードタイム (shipFromIds)**: 选择配送仓库
- **配送時間設定 (deliveryTimeId)**: 设置配送时间段

#### 与 Inventory API 2.0 的区别

| 功能 | Inventory API 2.0 | Inventory API 2.1 |
|------|------------------|------------------|
| 库存设置 | 支持 | 支持 |
| 出荷リードタイム | 不支持 | 支持 |
| 配送リードタイム | 不支持 | 支持 |
| 配送時間設定 | 不支持 | 支持 |

#### 功能列表

| 功能 | 说明 | 请求限制 | HTTP方法 |
|------|------|----------|----------|
| **inventories.variants.get** | 获取库存数（单个SKU） | 秒间 1 请求 | GET |
| **inventories.variants.upsert** | 注册/更新库存数（单个SKU） | 秒间 1 请求 | PUT |
| **inventories.variants.delete** | 删除库存信息（单个SKU） | 秒间 1 请求 | DELETE |
| **inventories.bulk.get.range** | 批量获取库存（按范围，最多1000件） | 秒间 5 请求 | GET |
| **inventories.bulk.get** | 批量获取库存（指定SKU，最多1000件） | 秒间 5 请求 | POST |
| **inventories.bulk.upsert** | 批量注册/更新库存（最多400件） | 秒间 1 请求 | POST |
| **inventories.variants.operation-lead-time.get** | 获取出荷リードタイム | 秒间 1 请求 | GET |
| **inventories.variants.operation-lead-time.upsert** | 设置出荷リードタイム | 秒间 1 请求 | PUT |
| **inventories.variants.ship-from-ids.get** | 获取配送リードタイム | 秒间 1 请求 | GET |
| **inventories.variants.ship-from-ids.upsert** | 设置配送リードタイム | 秒间 1 请求 | PUT |
| **inventories.variants.delivery-time-ids.get** | 获取配送時間設定 | 秒间 1 请求 | GET |
| **inventories.variants.delivery-time-ids.upsert** | 设置配送時間設定 | 秒间 1 请求 | PUT |

#### 新增字段说明

| 字段 | 类型 | 说明 | 最大值 |
|------|------|------|--------|
| **operationLeadTime** | number | 出荷リードタイム（发货响应时间） | 180 |
| **shipFromIds** | array | 配送リードタイムID列表 | 10个元素 |
| **normalDeliveryTimeId** | number | 通常時の配送時間ID | - |
| **backOrderDeliveryTimeId** | number | 入荷待ち時の配送時間ID | - |

---

#### 7. inventories.variants.operation-lead-time.get - 获取出荷リードタイム

**用途**: 根据商品管理番号和SKU管理番号获取出荷リードタイム

**端点**: `GET /es/2.1/inventories/manage-numbers/{manageNumber}/variants/{variantId}/operation-lead-time`

**请求限制**: 秒间 1 请求

**Path Parameter**:
| 参数 | 必需 | 类型 | 最大字节 | 说明 |
|------|------|------|----------|------|
| manageNumber | 是 | string | 32 | 商品管理番号（大写自动转为小写） |
| variantId | 是 | string | 32 | SKU管理番号（大小写视为不同字符） |

**响应示例**:
```json
{
    "manageNumber": "mng1234",
    "variantId": "sku1",
    "operationLeadTime": 3,
    "created": "2022-01-01T10:00:00+09:00",
    "updated": "2022-02-01T10:30:00+09:00"
}
```

---

#### 8. inventories.variants.operation-lead-time.upsert - 设置出荷リードタイム

**用途**: 根据商品管理番号和SKU管理番号设置出荷リードタイム

**端点**: `PUT /es/2.1/inventories/manage-numbers/{manageNumber}/variants/{variantId}/operation-lead-time`

**请求限制**: 秒间 1 请求

**请求体**:
```json
{
    "operationLeadTime": 5
}
```

**参数说明**:
| 参数 | 必需 | 类型 | 最小值 | 最大值 | 说明 |
|------|------|------|--------|--------|------|
| operationLeadTime | 是 | number | 0 | 180 | 出荷リードタイム（0=当日発送） |

**响应**: 204 No Content

---

#### 9. inventories.variants.ship-from-ids.get - 获取配送リードタイム

**用途**: 根据商品管理番号和SKU管理番号获取配送リードタイムID列表

**端点**: `GET /es/2.1/inventories/manage-numbers/{manageNumber}/variants/{variantId}/ship-from-ids`

**请求限制**: 秒间 1 请求

**响应示例**:
```json
{
    "manageNumber": "mng1234",
    "variantId": "sku1",
    "shipFromIds": [1, 2, 3],
    "created": "2022-01-01T10:00:00+09:00",
    "updated": "2022-02-01T10:30:00+09:00"
}
```

**注意**: `shipFromIds` 为配送仓库ID列表，数量最多10个

---

#### 10. inventories.variants.ship-from-ids.upsert - 设置配送リードタイム

**用途**: 根据商品管理番号和SKU管理番号设置配送リードタイムID列表

**端点**: `PUT /es/2.1/inventories/manage-numbers/{manageNumber}/variants/{variantId}/ship-from-ids`

**请求限制**: 秒间 1 请求

**请求体**:
```json
{
    "shipFromIds": [1, 2, 3, 4, 5]
}
```

**参数说明**:
| 参数 | 必需 | 类型 | 最小值 | 最大值 | 说明 |
|------|------|------|--------|--------|------|
| shipFromIds | 是 | array | 0 | 10 | 配送仓库ID列表，0元素时删除设置 |

**响应**: 204 No Content

---

#### 11. inventories.variants.delivery-time-ids.get - 获取配送時間設定

**用途**: 根据商品管理番号和SKU管理番号获取配送時間設定

**端点**: `GET /es/2.1/inventories/manage-numbers/{manageNumber}/variants/{variantId}/delivery-time-ids`

**请求限制**: 秒间 1 请求

**响应示例**:
```json
{
    "manageNumber": "mng1234",
    "variantId": "sku1",
    "normalDeliveryTimeId": 1,
    "backOrderDeliveryTimeId": 2,
    "created": "2022-01-01T10:00:00+09:00",
    "updated": "2022-02-01T10:30:00+09:00"
}
```

**字段说明**:
| 字段 | 说明 |
|------|------|
| normalDeliveryTimeId | 通常時の配送時間ID |
| backOrderDeliveryTimeId | 入荷待ち時の配送時間ID |

---

#### 12. inventories.variants.delivery-time-ids.upsert - 设置配送時間設定

**用途**: 根据商品管理番号和SKU管理番号设置配送時間設定

**端点**: `PUT /es/2.1/inventories/manage-numbers/{manageNumber}/variants/{variantId}/delivery-time-ids`

**请求限制**: 秒间 1 请求

**请求体**:
```json
{
    "normalDeliveryTimeId": 1,
    "backOrderDeliveryTimeId": 2
}
```

**参数说明**:
| 参数 | 必需 | 类型 | 说明 |
|------|------|------|------|
| normalDeliveryTimeId | 是 | number | 通常時の配送時間ID |
| backOrderDeliveryTimeId | 是 | number | 入荷待ち時の配送時間ID |

**响应**: 204 No Content

---

#### 批量操作中的新增字段支持

在 `inventories.bulk.upsert` 中，也可以设置新增字段：

```json
{
    "inventories": [
        {
            "manageNumber": "mng1234",
            "variantId": "sku1",
            "mode": "ABSOLUTE",
            "quantity": 70,
            "operationLeadTime": 3,
            "shipFromIds": [1, 2],
            "normalDeliveryTimeId": 1,
            "backOrderDeliveryTimeId": 2
        }
    ]
}
```

---

#### 版本更新历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| 1.0 | 2024/01/25 | 初版（新增出荷リードタイム、配送リードタイム、配送時間設定） |

---

### Order Status Mapping

| Rakuten | Internal Event | Inventory Change |
|---------|----------------|------------------|
| 100 (New) | ORDER_RECEIVED | Decrease |
| 300 (Ship Wait) | ORDER_CONFIRMED | None |
| 600/700 (Shipped) | Ignored | None |
| 900 (Cancelled) | ORDER_CANCELLED | Increase |

---

### Error Handling

#### 常见错误码
| 状态码 | 说明 | 处理方式 |
|--------|------|----------|
| 200 | 成功 | 正常处理 |
| 401 | 认证失败 | License Key 可能过期 |
| 429 | 请求过于频繁 | 指数退避重试 |
| 400 | 请求参数错误 | 检查请求体格式 |
| 500 | 服务器错误 | 重试 |

#### 重试策略
```python
max_retries = 3
for retry in range(max_retries):
    try:
        response = await api_call()
        if response.status_code == 200:
            return response
        elif response.status_code == 429:
            wait_time = 2 ** retry  # 1s, 2s, 4s
            await asyncio.sleep(wait_time)
    except Exception as e:
        if retry < max_retries - 1:
            wait_time = 2 ** retry
            await asyncio.sleep(wait_time)
```

---

### Important Notes

1. **SKU 大小写处理**
   - 内部存储: 统一使用小写 (`sku_id`)
   - 原始大小写: 保留在 `original_sku` 和 `aliases` 中
   - API调用: 使用原始大小写

2. **响应格式兼容性**
   以下字段可能为**单个对象**或**数组**，需要兼容处理：
   - `orderNumberList`
   - `orderList`
   - `itemList.item`

3. **shop_url 参数**
   - 在请求体中是**可选**的
   - 格式: `shopname.rakuten.co.jp`（不包含协议和路径）

4. **时区处理**
   - 所有时间参数使用 `+0900` (日本标准时间)
   - 格式: `YYYY-MM-DDTHH:MM:SS+0900`

## Acceptance Criteria

1. All SKUs stored in lowercase internally
2. No physical deletion of SKU records
3. No price fields in any model
4. Test SKU ce1111 always exists in test mode
5. Full event history for all inventory changes
6. Rakuten order polling every 15-30 minutes
7. SKU sync from Rakuten per store
8. CSV import with preview and confirm
9. Failed sync retry with exponential backoff
10. 80%+ test coverage
