# 乐天 RMS API 知识库

> **最后更新**: 2026-02-17
> **目的**: 避免在API集成时反复试错，提高开发效率

---

## ⚠️ 重要更新 (2026-02-17)

### 关键发现

| 项目 | 状态 | 说明 |
|------|------|------|
| **Content-Type 格式** | ✅ 修正 | 必须使用 `application/json;charset=utf-8` (无空格) |
| **端点命名格式** | ✅ 修正 | 使用连字符 `bulk-get` 而不是斜杠 `bulk/get` |
| **网络连接** | ⚠️ 需要代理 | 可能需要通过代理才能访问 API |
| **商品列表 API** | ❌ 不存在 | `/es/2.0/item/getItems` 返回 404 |
| **库存范围 API** | ✅ 可用 | `GET /es/2.0/inventories/bulk-get/range` |

### Content-Type 格式

**正确格式**:
```
Content-Type: application/json;charset=utf-8
```

**错误格式** (会导致 415 Unsupported Media Type):
```
Content-Type: application/json; charset=utf-8
Content-Type: application/json
```

### 工作的端点

| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/es/2.0/order/searchOrder/` | POST | ✅ | 订单搜索 |
| `/es/2.0/inventories/bulk-get/range` | GET | ✅ | 按库存范围获取 SKU |

### 不存在的端点

| 端点 | 错误 | 说明 |
|------|------|------|
| `/es/2.0/item/getItems` | 404 | 代码中使用的端点不存在 |
| `/es/2.0/item/search` | 404 | 不存在 |
| `/es/2.0/inventory/set` | 404 | 不存在 |

---

## 📌 基本信息

| 项目 | 值 |
|------|-----|
| API 名称 | Rakuten RMS (Rakuten Market Service) API |
| 基础 URL | `https://api.rms.rakuten.co.jp` |
| API 版本 | ES 2.0 |
| 认证方式 | ESA (e-commerce Service Authentication) |
| 请求格式 | JSON |
| 响应格式 | JSON |

---

## 🔐 认证

### 认证头格式

```
Authorization: ESA <Base64(serviceSecret:licenseKey)>
```

### 生成方式

```python
import base64

auth_str = f"{service_secret}:{license_key}"
encoded = base64.b64encode(auth_str.encode()).decode()
auth_header = f"ESA {encoded}"
```

### 认证凭证

| 字段 | 说明 | 示例 |
|------|------|------|
| service_secret | 服务密钥 | `SP416502_ub7B0vRTK9VuHjsL` |
| license_key | 许可密钥 | `SL416502_YuXi3naks7oilYtI` |
| shop_url | 店铺URL (可选) | `coucou-doma.rakuten.co.jp` |

---

## 📡 API 端点

### 1. 搜索订单 (searchOrder)

**端点**: `POST /es/2.0/order/searchOrder/`

**用途**: 按日期范围搜索订单，返回订单号列表

**请求头**:
```
Authorization: ESA <Base64(serviceSecret:licenseKey)>
Content-Type: application/json;charset=utf-8  // ⚠️ 必须无空格
```

**请求体**:
```json
{
  "dateType": 1,                    // 日期类型: 1=订单日期
  "startDatetime": "2026-02-01T00:00:00+0900",
  "endDatetime": "2026-02-17T23:59:59+0900",
  "orderProgressList": [100, 300],  // 可选: 订单状态列表
  "shopUrl": "coucou-doma.rakuten.co.jp",  // 可选
  "PaginationRequestModel": {
    "requestRecordsAmount": 30,     // 每页记录数
    "requestPage": 1,               // 页码
    "sortModelList": [
      {
        "sortColumn": 1,           // 排序列
        "sortDirection": 2         // 排序方向
      }
    ]
  }
}
```

**响应示例**:
```json
{
  "orderNumberList": {
    "orderNumber": "123456789-20260217-123456789"
  }
}
```

**注意**:
- `orderNumberList` 可能是单个对象或数组
- 需要兼容两种格式处理

---

### 2. 获取订单详情 (getOrder)

**端点**: `POST /es/2.0/order/getOrder`

**用途**: 根据订单号获取订单详情

**请求体**:
```json
{
  "orderNumberList": ["123456789-20260217-123456789"],
  "shopUrl": "coucou-doma.rakuten.co.jp"  // 可选
}
```

**响应示例**:
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

**注意**:
- `orderList` 可能是单个对象或数组
- 需要兼容两种格式处理

---

### 3. 确认订单 (confirmOrder)

**端点**: `POST /es/2.0/order/confirmOrder`

**用途**: 确认订单，将状态从 100 变更为 300

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "shopUrl": "coucou-doma.rakuten.co.jp"  // 可选
}
```

**响应**:
- 成功: 空对象或成功标识
- 失败: 错误信息

**注意**:
- 此操作可能失败，需要重试机制
- 失败时需要记录到重试队列

---

### 4. 获取库存范围 (inventories/bulk-get/range)

**端点**: `GET /es/2.0/inventories/bulk-get/range`

**用途**: 按库存数量范围获取 SKU 列表

**请求头**:
```
Authorization: ESA <Base64(serviceSecret:licenseKey)>
```

**请求参数**:
```
minQuantity: 最小库存数量
maxQuantity: 最大库存数量
```

**请求示例**:
```
GET /es/2.0/inventories/bulk-get/range?minQuantity=100&maxQuantity=500
```

**响应示例**:
```json
{
  "inventories": [
    {
      "manageNumber": "ff-44",
      "variantId": "r-sku00000030",
      "quantity": 114,
      "created": "2025-05-16T13:01:32+09:00",
      "updated": "2025-12-03T11:01:35+09:00"
    }
  ]
}
```

**注意**:
- ⚠️ 如果结果太多会返回 400 错误: "Too many search results"
- 需要分批查询不同范围
- 返回数据不包含商品详细信息（名称、图片、价格）
- `manageNumber` 对应商品管理编号
- `variantId` 对应 SKU 编号

---

### 5. 设置库存 (setInventory) - ⚠️ 端点不存在

**端点**: `POST /es/2.0/inventory/set`

**状态**: ❌ 404 Not Found - 此端点不存在

**需要查找**: 正确的库存更新 API 端点

---

### 6. 获取商品列表 (getItems) - ⚠️ 端点不存在

**端点**: `POST /es/2.0/item/getItems`

**状态**: ❌ 404 Not Found - 此端点不存在

**代码中使用位置**: `app/services/rakuten_api.py:233-257`

**替代方案**:
- 使用 `GET /es/2.0/inventories/bulk-get/range` 获取 SKU 列表（仅包含库存信息）
- 使用 `GET /es/2.0/items/manage-numbers/{manageNumber}` 获取单个商品详情

**请求体**:
```json
{
  "hits": 100,                    // 每页数量
  "page": 1,                      // 页码
  "shopUrl": "coucou-doma.rakuten.co.jp"  // 可选
}
```

**响应示例**:
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

**注意**:
- 用于 SKU 同步功能
- 需要分页获取所有商品

---

## 📊 订单状态映射

| 乐天状态码 | 状态说明 | 内部事件 | 库存影响 |
|------------|----------|----------|----------|
| 100 | 新订单 (New) | ORDER_RECEIVED | 减少库存 |
| 300 | 等待发货 (Ship Wait) | ORDER_CONFIRMED | 无变化 |
| 600 | 已发货 (Shipped) | - | 无变化 |
| 700 | 已发货 (Shipped) | - | 无变化 |
| 900 | 已取消 (Cancelled) | ORDER_CANCELLED | 增加库存 |

---

## 🚨 错误处理

### 常见错误码

| 状态码 | 说明 | 处理方式 |
|--------|------|----------|
| 200 | 成功 | 正常处理 |
| 401 | 认证失败 | License Key 可能过期，需要更新 |
| 404 | 端点不存在 | 检查端点路径是否正确 |
| 405 | 方法不允许 | 检查 HTTP 方法是否正确 |
| 415 | 不支持的媒体类型 | ⚠️ 检查 Content-Type 格式 (应为 `application/json;charset=utf-8`) |
| 429 | 请求过于频繁 | 指数退避重试 |
| 400 | 请求参数错误 | 检查请求体格式 |

### 特殊错误码

| 错误码 | 说明 | 响应内容 |
|--------|------|----------|
| **ES04-03** | Unsupported Media Type | Content-Type 格式错误 |
| **IE0116** | Too many search results | 库存范围查询结果过多 |
| **IE0002** | Unrecognized field | 请求体字段名错误 |

### 重试策略

```python
max_retries = 3
for retry in range(max_retries):
    try:
        # 发起请求
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

## 🧪 测试用例

### 测试凭证

```python
service_secret = "SP416502_ub7B0vRTK9VuHjsL"
license_key = "SL416502_YuXi3naks7oilYtI"
shop_url = "coucou-doma.rakuten.co.jp"
```

### 测试场景

1. **认证测试**
   - 调用 `searchOrder` 测试凭证是否有效
   - 检查是否返回 401 错误

2. **商品获取测试**
   - 调用 `getItems(page=1, hits=10)`
   - 验证返回的商品列表格式

3. **订单查询测试**
   - 调用 `searchOrder` 查询指定日期范围
   - 验证返回的订单号列表

---

## 📝 注意事项

### 1. SKU 大小写处理

- **内部存储**: 统一使用小写 (`sku_id`)
- **原始大小写**: 保留在 `original_sku` 和 `aliases` 中
- **API调用**: 使用原始大小写（从 `original_sku` 或 `aliases` 获取）

### 2. 响应格式兼容性

以下字段可能为**单个对象**或**数组**，需要兼容处理：
- `orderNumberList`
- `orderList`
- `itemList.item`

### 3. shop_url 参数

- `shop_url` 在请求体中是**可选**的
- 但多店铺场景下应该指定
- 格式: `shopname.rakuten.co.jp`（不包含协议和路径）

### 4. 时区处理

- 所有时间参数使用 `+0900` (日本标准时间)
- 格式: `YYYY-MM-DDTHH:MM:SS+0900`

### 5. Content-Type 格式 ⚠️ 重要

- **正确格式**: `application/json;charset=utf-8` (无空格)
- **错误格式**: `application/json; charset=utf-8` (有空格) - 会导致 415 错误
- **错误格式**: `application/json` - 会导致 415 错误

### 6. 代理配置

如果无法直接访问 Rakuten API，需要配置代理：

```python
# config.py
RAKUTEN_PROXY = os.getenv("RAKUTEN_PROXY", "")  # 例如: "http://127.0.0.1:10808"

# rakuten_api.py
async def _request(self, method: str, url: str, ...):
    proxy = RAKUTEN_PROXY if RAKUTEN_PROXY else None
    async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
        ...
```

---

## 🔧 客户端实现

### 核心方法

| 方法 | 状态 | 用途 |
|------|------|------|
| `search_order(start_datetime, end_datetime, order_status)` | ✅ | 搜索订单 |
| `get_order(order_numbers)` | ⚠️ | 获取订单详情 (需要正确 Content-Type) |
| `confirm_order(order_number)` | ⚠️ | 确认订单 (需要正确 Content-Type) |
| `get_inventory_range(min_quantity, max_quantity)` | ✅ | 按库存范围获取 SKU |
| `get_items(limit, page)` | ❌ | 获取商品列表 (端点不存在) |
| `set_inventory(sku, inventory, inventory_type)` | ❌ | 设置库存 (端点不存在) |
| `test_auth()` | ✅ | 测试认证有效性 |

### 工厂函数

```python
def get_rakuten_client(api_config: dict) -> RakutenAPIClient:
    service_secret = api_config.get("serviceSecret")
    license_key = api_config.get("licenseKey")
    shop_url = api_config.get("shopUrl")
    return RakutenAPIClient(service_secret, license_key, shop_url)
```

---

## 🔗 相关文档

### 详细文档

| 文档 | 说明 |
|------|------|
| **RAKUTEN_PAY_ORDER_API.md** | 乐天 Pay 订单 API 详细文档 (18个函数，完整字段定义) |
| ITEM_API_2.0_DETAIL_EXAMPLE.md | 商品 API 2.0 详细示例 |
| INVENTORY_API_2.0_DETAIL_EXAMPLE.md | 库存 API 2.0 详细示例 |

### API 分类

本知识库包含基础 API 信息。对于更详细的 API 文档，请参考：

1. **订单 API (Order API)**
   - `RAKUTEN_PAY_ORDER_API.md` - 详细的乐天 Pay 订单 API 文档
   - 包含 18 个函数：searchOrder, getOrder, confirmOrder, updateOrderShipping, cancelOrder 等

2. **库存 API (Inventory API)**
   - 见 `INVENTORY_API_2.0_DETAIL_EXAMPLE.md`

3. **商品 API (Item API)**
   - 见 `ITEM_API_2.0_DETAIL_EXAMPLE.md`

---

## 📚 参考资料

- 乐天 RMS API 官方文档: https://webservice.rakuten.co.jp/api/
- 库存 API 2.0 文档: 见 INVENTORY_API_2.0_DETAIL_EXAMPLE.md
- 订单 API 文档: 见 RAKUTEN_PAY_ORDER_API.md

---

*本知识库由项目实际使用经验整理而成，如有更新请及时同步*
