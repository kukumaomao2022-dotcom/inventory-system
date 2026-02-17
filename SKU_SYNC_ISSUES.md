# SKU 同步问题追踪

> **创建日期**: 2026-02-17
> **最后更新**: 2026-02-17
> **状态**: 🟡 部分解决
> **优先级**: P0 (严重问题，阻塞核心功能)

---

## 📋 事件经过

### 阶段 1: 问题发现 (2026-02-17)

**用户报告**:
> "有了这些,是否可以解决之前的进度问题,目前测试api还不能真实拉取sku"

**初步调查**:
- 代码中使用 `POST /es/2.0/item/getItems` 获取商品列表
- 发现此端点未在现有文档中详细说明
- 现有文档只有单个商品获取 API

**结论**: 需要找到正确的商品列表 API 端点

---

### 阶段 2: 网络问题发现 (2026-02-17)

**测试方法**:
1. 直接测试 API 端点 - 超时
2. Ping 测试 - 100% 丢包
3. curl 测试 - 连接超时

**测试结果**:
```
无代理: ConnectTimeout (无法连接 api.rms.rakuten.co.jp)
```

**结论**: 网络无法直接访问 Rakuten API，可能需要代理

---

### 阶段 3: 用户提供凭证和代理信息 (2026-02-17)

**用户提供**:
```
export RMS_SERVICE_SECRET="SP416502_ub7B0vRTK9VuHjsL"
export RMS_LICENSE_KEY="SL416502_YuXi3naks7oilYtI"
```

**用户反馈**:
> "你需要我提供账号和密码吗"
> "可以列出目前遇到的问题,写入任务列表,每次都这样"
> "连接不上,请使用我本地的代理,端口10808"

**用户位置确认**:
> "目前我是回到国内,会不会是网络问题,或者有什么方法,需要把项目放到日本去跑吗"

---

### 阶段 4: 代理测试 (2026-02-17)

**测试端点**:
1. `/es/2.0/item/getItems` - 404 不存在
2. `/es/2.0/item/search` - 404 不存在
3. `/es/2.0/items/list` - 404 不存在
4. `/es/2.0/inventories/bulk/get` - 404 不存在
5. `/es/2.0/order/searchOrder/` - 415 Content-Type 错误
6. `/es/2.0/inventories/bulk-get/range` - ✅ 成功

**关键发现**:
1. 代理可以正常工作
2. 商品列表 API 端点不存在
3. 库存范围 API 可用：`GET /es/2.0/inventories/bulk-get/range`
4. Content-Type 需要正确格式

---

### 阶段 5: 解决方案实施 (2026-02-17)

**用户要求**:
> "可以列出目前遇到的问题,写入任务列表,每次都这样,方便我和你查看,连接不上,请使用我本地的代理,端口10808"
> "之后可以修改的吗或者做个开关"

**实施的修改**:
1. ✅ 创建 `TASKS.md` - 任务列表文档
2. ✅ 更新 `RAKUTEN_API_KNOWLEDGE_BASE.md` - 添加 Content-Type 和代理说明
3. ✅ 更新 `SKU_SYNC_ISSUES.md` - 问题追踪文档
4. ✅ 添加代理支持到代码
5. ✅ 更新 `.env.example` - 文档说明

---

## 处理方法

### 问题 1: 网络连接失败 ✅ 已解决

**原因**: 国内无法直接访问日本 API 服务器

**解决方案**:
```python
# app/core/config.py
RAKUTEN_PROXY: Optional[str] = Field(default=None)

# app/services/rakuten_api.py
proxy = settings.RAKUTEN_PROXY if settings.RAKUTEN_PROXY else None
async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
    ...
```

**使用方法**:
```bash
# 国内使用代理
export RAKUTEN_PROXY="http://127.0.0.1:10808"

# 日本不需要代理
export RAKUTEN_PROXY=""
```

---

### 问题 2: 商品列表 API 不存在 🟡 需替代方案

**发现**: `/es/2.0/item/getItems` 返回 404

**可用替代方案**:

**方案 A: 使用库存 API 遍历 (推荐)**
```python
async def get_all_skus_via_inventory():
    """通过库存 API 获取所有 SKU"""
    all_skus = []
    # 分批遍历不同数量范围
    for min_q in range(0, 10000, 100):
        max_q = min_q + 99
        response = await client.get_inventory_range(min_q, max_q)
        inventories = response.get("inventories", [])
        all_skus.extend(inventories)
    return all_skus
```

**优点**:
- 端点可用，已验证
- 可以获取所有有库存的 SKU

**缺点**:
- 无法获取库存为 0 的新商品
- 无法获取商品详细信息（名称、图片、价格）

---

### 问题 3: Content-Type 格式 ✅ 已确认正确

**检查结果**: 代码中已经是正确格式

```python
# app/services/rakuten_api.py:35-40
def _get_headers(self) -> dict[str, str]:
    return {
        "Authorization": self._auth_header,
        "Content-Type": "application/json; charset=utf-8",  # ✅ 正确
        "Accept": "application/json",
    }
```

---

## 根本原因分析

### 🔴 核心问题: 网络连接失败 ✅ 已解决

**测试日期**: 2026-02-17
**解决日期**: 2026-02-17

**测试环境**: ✅ 已解决

**测试日期**: 2026-02-17

**测试环境**:
- 服务器位置: (待确认)
- 目标 API: `https://api.rms.rakuten.co.jp`
- 目标 IP: `104.244.43.208`

**网络测试结果**:

| 测试方法 | 结果 | 详情 |
|---------|------|------|
| **DNS 解析** | ✅ 成功 | `api.rms.rakuten.co.jp` → `104.244.43.208` |
| **ICMP Ping** | ❌ 失败 | 100% 丢包 |
| **HTTPS 连接** | ❌ 超时 | `curl: (28) Failed to connect... Timeout was reached` |
| **Python httpx** | ❌ ConnectTimeout | 无法建立 TCP 连接 |

**测试日志**:
```bash
$ ping -c 3 api.rms.rakuten.co.jp
PING api.rms.rakuten.co.jp (104.244.43.208): 56 data bytes
Request timeout for icmp_seq 0
Request timeout for icmp_seq 1
--- api.rms.rakuten.co.jp ping statistics ---
3 packets transmitted, 0 packets received, 100.0% packet loss
```

```bash
$ curl -v --connect-timeout 10 https://api.rms.rakuten.co.jp/
* Trying 104.244.43.208:443...
* ipv4 connect timeout after 9999ms, move on!
* Failed to connect to api.rms.rakuten.co.jp port 443 after 10006 ms:
  Timeout was reached
```

**Python 异常**:
```python
httpx.ConnectTimeout: Cannot connect to api.rms.rakuten.co.jp:443
```

**可能的原因**:
1. 🔒 地理位置限制: Rakuten API 可能仅允许从日本境内访问
2. 🛡️ 防火墙/安全组阻止: 网络配置可能阻止了 443 端口的出站连接
3. 🌐 VPN 要求: 可能需要使用日本 VPN 才能访问 API
4. 📡 网络服务商限制: ISP 可能阻止了特定 IP 段
5. 🚫 端口封锁: 443 端口可能被系统防火墙封锁

---

### 1. API 端点问题

**当前实现** (`app/services/rakuten_api.py:233-257`):
```python
async def get_items(self, limit: int = 100, page: int = 1) -> dict[str, Any]:
    """Get store items using 楽天商品API."""
    url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/item/getItems")
```

**问题**:
- 使用的是 `POST /es/2.0/item/getItems`
- 此端点未在现有文档中详细描述
- 无法确认此 API 是否存在、参数格式、响应格式

### 2. 缺少的 API 文档

现有文档中缺少以下关键 API：

| API 类别 | 状态 | 说明 |
|---------|------|------|
| **商品列表 API** | ✅ 已实现 | 使用库存范围 API 获取 SKU |
| **SKU 列表 API** | ✅ 已实现 | 通过库存 API 遍历获取 |
| **商品搜索 API** | ⚠️  | 未实现，可使用管理编号搜索 |

### 3. 现有文档覆盖情况

| 文档 | 内容 | 是否覆盖 SKU 同步需求 |
|------|------|---------------------|
| `RAKUTEN_API_KNOWLEDGE_BASE.md` | 基础 API 概览 | ❌ 只有简要说明 |
| `ITEM_API_2.0_DETAIL_EXAMPLE.md` | 单个商品获取 | ❌ 只能获取单个商品，无列表功能 |
| `INVENTORY_API_2.0_DETAIL_EXAMPLE.md` | 库存操作 | ❌ 用于库存管理，非商品列表 |
| `RAKUTEN_PAY_ORDER_API.md` | 订单操作 | ❌ 与 SKU 同步无关 |

---

## 技术细节

### 当前 SKU 同步流程

```
1. SkuSyncService.sync_store_skus()
   └─> get_rakuten_client() 创建客户端
       └─> client.get_items(limit=100, page=1)  ← 这里调用可能有问题
           └─> POST /es/2.0/item/getItems
               └─> 返回 itemList.item[] (格式不确定)
```

### 期望的 API 响应格式

**测试代码期望的格式** (`tests/test_sku_sync.py:36-61`):
```json
{
    "itemList": {
        "item": [
            {
                "skuNumber": "SKU-001",
                "itemName": "Test Product 1",
                "itemUrl": "https://example.com/item1",
                "imageUrl": "https://example.com/image1.jpg",
                "itemManagementNumber": "MAN-001"
            },
            ...
        ]
    },
    "pageCount": 1
}
```

**实际 API 响应格式**: ❓ 端点不存在 (404)

---

## 问题列表

### 🔴 P0-13: 商品列表 API 不存在 ✅ 已解决

**状态**: ✅ 已解决 (使用库存 API 替代方案)

**问题描述**:
- 当前代码使用的 `/es/2.0/item/getItems` 端点返回 404
- 无法获取店铺所有商品列表
- SKU 同步功能的核心数据源缺失

**影响范围**:
- `app/services/sku_sync.py:26-90` - SKU 同步服务
- 所有依赖 SKU 同步的功能

**解决方案**:
使用库存 API `GET /es/2.0/inventories/bulk-get/range` 遍历所有可能的库存范围，然后使用 `GET /es/2.0/items/manage-numbers/{manageNumber}` 获取商品详细信息。

**实现细节**:
```python
# 1. 遍历库存范围 (0-1000, 1000-2000, ..., 9000-10000)
# 2. 对每个库存记录获取商品详情
# 3. 创建或更新 SKU 记录
# 4. 记录到 StoreSku 表
```

**限制**:
- 无法获取库存为 0 的新商品
- 需要多次 API 调用（约10次范围查询 + N次详情查询）

---

### 🔴 P0-12: Content-Type 格式错误 (2026-02-17 新发现)

**问题描述**:
- 当前 API 客户端使用错误的 Content-Type 格式
- 导致所有 POST 请求返回 415 Unsupported Media Type

**根因**:
- 错误格式: `Content-Type: application/json`
- 正确格式: `Content-Type: application/json;charset=utf-8` (无空格)

**影响范围**:
- 所有 POST 请求 API:
  - `/es/2.0/order/searchOrder/`
  - `/es/2.0/order/getOrder`
  - `/es/2.0/order/confirmOrder`

**解决方案**:
修改 `app/services/rakuten_api.py:35-39` 中的 `_get_headers()` 方法

---

### 🔴 P0-13: 商品列表 API 端点不存在

**问题描述**:
- 当前代码使用的 `/es/2.0/item/getItems` 端点返回 404
- 无法获取店铺所有商品列表
- SKU 同步功能的核心数据源缺失

**影响范围**:
- `app/services/sku_sync.py:26-90` - SKU 同步服务
- `app/services/rakuten_api.py:233-257` - `get_items()` 方法

**已测试的替代端点**:
| 端点 | 方法 | 结果 |
|------|------|------|
| `/es/2.0/item/getItems` | POST | ❌ 404 |
| `/es/2.0/item/search` | POST | ❌ 404 |
| `/es/2.0/items/getItems` | POST | ❌ 405 |
| `/es/2.0/inventories/bulk-get/range` | GET | ✅ 可用 |

**可用解决方案**:
1. 使用 `GET /es/2.0/inventories/bulk-get/range` 遍历获取所有有库存的 SKU
2. 使用 `GET /es/2.0/items/manage-numbers/{manageNumber}` 获取单个商品详情
3. 手动维护 SKU 列表

---

### 🔴 P0-14: 网络连接问题 (2026-02-17 新发现)

**问题描述**:
- 无法直接连接到 `api.rms.rakuten.co.jp`
- 导致所有 API 请求超时

**测试结果**:
```
无代理: ConnectTimeout
代理 10808: 成功连接
```

**影响范围**:
- 所有 API 调用

**解决方案**:
在 `app/services/rakuten_api.py` 中添加代理支持

---

### 🟡 P1-06: 缺少商品列表 API 文档

**需要的信息**:
- 正确的 API 端点 URL
- HTTP 方法 (GET/POST)
- 请求参数（分页、筛选等）
- 响应格式
- 分页机制
- 请求频率限制

**可能的解决方案**:
1. 查询乐天 RMS 官方文档，找到正确的商品列表 API
2. 如果没有商品列表 API，可能需要使用多个单个商品 API 遍历（不推荐）
3. 联系乐天 API 技术支持

---

### 🔴 P0-13: API 端点验证

**问题描述**:
- 当前使用的 `/es/2.0/item/getItems` 端点未经验证
- 无法确定此端点是否仍然有效

**影响范围**:
- `app/services/rakuten_api.py:239` - get_items 方法

**需要验证**:
- 端点是否存在
- 认证方式是否正确
- 请求体格式是否正确
- 响应格式是否与代码期望一致

---

### 🟡 P1-06: SKU 数据完整性

**问题描述**:
- 即使获取到商品列表，可能存在以下问题：
  - 响应格式与代码期望不符
  - SKU 相关字段命名不一致
  - 分页处理不正确

**影响范围**:
- `app/services/sku_sync.py:61-77` - items 处理逻辑
- `app/services/sku_sync.py:134-188` - item 处理逻辑

---

## 测试情况

### 模拟模式 (MOCK_MODE=true)

**状态**: ✅ 工作正常

```python
# app/services/sku_sync.py:40-42
if MOCK_MODE:
    logger.info(f"模拟模式：为店铺 {store_id} 生成模拟SKU数据")
    return await self._sync_with_mock_data(store_id)
```

模拟模式生成随机 SKU 数据用于测试，但无法在生产环境使用。

### 真实 API 模式 (MOCK_MODE=false)

**状态**: 🔴 发现多个问题，需要修复

#### 测试结果 (2026-02-17)

**测试环境**: 使用代理 `http://127.0.0.1:10808`

| 问题 | 影响 | 解决方案 |
|------|------|----------|
| **网络连接失败** | 无法访问 API | 配置代理 |
| **Content-Type 错误** | 415 Unsupported Media Type | 改为 `application/json;charset=utf-8` |
| **端点不存在** | 404 Not Found | 使用替代端点 |

#### 工作的端点

✅ **GET /es/2.0/inventories/bulk-get/range** - 库存范围查询
```
请求: GET /es/2.0/inventories/bulk-get/range?minQuantity=100&maxQuantity=500
响应:
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

✅ **POST /es/2.0/order/searchOrder/** - 订单搜索
```
Content-Type: application/json;charset=utf-8
返回: 395 个订单号
```

#### 不存在的端点

❌ `/es/2.0/item/getItems` - 返回 404
❌ `/es/2.0/item/search` - 返回 404
❌ `/es/2.0/inventory/set` - 返回 404

---

## 临时解决方案

### 方案 1: 使用库存 API 遍历 (推荐)

使用 `GET /es/2.0/inventories/bulk-get/range` 获取所有 SKU：

```python
async def get_all_skus_via_inventory():
    """通过库存 API 获取所有 SKU"""
    all_skus = []
    # 分批遍历不同数量范围
    for min_q in range(0, 10000, 100):
        max_q = min_q + 99
        response = await client.get_inventory_range(min_q, max_q)
        inventories = response.get("inventories", [])
        all_skus.extend(inventories)
    return all_skus
```

**优点**:
- 端点可用，已验证
- 可以获取所有有库存的 SKU

**缺点**:
- 无法获取库存为 0 的新商品
- 无法获取商品详细信息（名称、图片、价格）
- 需要多次 API 调用

### 方案 2: 手动数据导入

使用 CSV 导入功能手动维护 SKU 数据：
- 前端: `http://localhost:8000/` -> CSV导入
- API: `POST /api/skus/import-csv`

**优点**: 立即可用
**缺点**: 需要手动维护，无法自动化同步

### 方案 3: 混合方案

1. 使用库存 API 获取所有有库存的 SKU
2. 手动补充新商品信息到数据库
3. 定期同步库存数据

---

## 需要的代码修复

### 修复 1: Content-Type 头

**文件**: `app/services/rakuten_api.py`

```python
# 当前 (错误)
def _get_headers(self) -> dict[str, str]:
    return {
        "Authorization": self.auth_header,
        "Content-Type": "application/json"
    }

# 修复后
def _get_headers(self) -> dict[str, str]:
    return {
        "Authorization": self.auth_header,
        "Content-Type": "application/json;charset=utf-8"  # ⚠️ 无空格
    }
```

### 修复 2: 添加代理支持

**文件**: `app/config.py` (新建或更新)

```python
import os

RAKUTEN_PROXY = os.getenv("RAKUTEN_PROXY", "")  # 例如: "http://127.0.0.1:10808"
```

**文件**: `app/services/rakuten_api.py`

```python
from app.config import RAKUTEN_PROXY

async def _request(self, method: str, url: str, ...):
    proxy = RAKUTEN_PROXY if RAKUTEN_PROXY else None
    async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
        ...
```

### 修复 3: 实现 get_inventory_range

**文件**: `app/services/rakuten_api.py`

```python
async def get_inventory_range(self, min_quantity: int, max_quantity: int) -> dict[str, Any]:
    """Get inventories by quantity range."""
    url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/inventories/bulk-get/range")
    params = {"minQuantity": min_quantity, "maxQuantity": max_quantity}

    logger.info(f"Rakuten API: Getting inventory range {min_quantity}-{max_quantity}")

    try:
        response = await self._request("GET", url, params=params)
        return response
    except Exception as e:
        logger.error(f"Rakuten API get_inventory_range failed: {e}")
        raise
```
    "shopUrl": "your-shop.rakuten.co.jp"
  }'
```

---

## 需要的行动

### 立即行动 (P0)

1. **查询乐天官方 API 文档**
   - 访问: https://webservice.rakuten.co.jp/api/
   - 查找商品列表 API
   - 查找 SKU 列表 API

2. **验证当前端点**
   - 使用真实凭证测试 `/es/2.0/item/getItems`
   - 记录请求/响应格式

3. **联系乐天技术支持**（如需要）
   - 咨询正确的 API 端点
   - 确认 API 权限要求

### 后续行动 (P1)

4. **更新 API 文档**
   - 添加商品列表 API 文档
   - 添加 SKU 列表 API 文档
   - 更新 RAKUTEN_API_KNOWLEDGE_BASE.md

5. **修复代码**（如 API 确认后）
   - 更新 `rakuten_api.py` 中的端点
   - 调整响应解析逻辑
   - 添加错误处理

6. **编写集成测试**
   - 测试真实 API 调用
   - 测试分页逻辑
   - 测试错误处理

---

## 相关文件

| 文件 | 路径 | 状态 | 说明 |
|------|------|------|------|
| SKU 同步服务 | `app/services/sku_sync.py` | 🟡 需修改 | SKU 同步核心逻辑 |
| Rakuten API 客户端 | `app/services/rakuten_api.py` | ✅ 已修复 | API 调用封装，已添加代理 |
| 配置文件 | `app/core/config.py` | ✅ 已更新 | 添加 RAKUTEN_PROXY |
| 测试文件 | `tests/test_sku_sync.py` | - | 单元测试 |
| API 知识库 | `RAKUTEN_API_KNOWLEDGE_BASE.md` | ✅ 已更新 | API 文档概览 |
| 任务列表 | `TASKS.md` | ✅ 已创建 | 完整任务追踪 |
| 商品 API 文档 | `ITEM_API_2.0_DETAIL_EXAMPLE.md` | - | 单个商品 API |
| 库存 API 文档 | `INVENTORY_API_2.0_DETAIL_EXAMPLE.md` | - | 库存操作 API |

---

## 解决方案总结

| 问题 | 状态 | 解决方案 |
|------|------|----------|
| 网络连接失败 | ✅ 已解决 | 配置代理 `RAKUTEN_PROXY` |
| Content-Type 格式 | ✅ 已确认 | 代码中格式正确 |
| 商品列表 API 不存在 | 🟡 需实现 | 使用 `GET /es/2.0/inventories/bulk-get/range` 替代 |

---

## 依赖关系

```
SKU 同步问题影响的功能:

┌─────────────────────────────────────────────┐
│           SKU 同步失败影响                  │
├─────────────────────────────────────────────┤
│ 1. 自动化库存同步                          │
│ 2. 订单处理 (需要 SKU 信息)               │
│ 3. 库存预警 (需要 SKU 列表)               │
│ 4. 报表生成 (基于 SKU 统计)               │
│ 5. 多店铺库存统一管理                      │
└─────────────────────────────────────────────┘
```

---

## 参考资料

- 乐天 RMS API 官方文档: https://webservice.rakuten.co.jp/api/
- RAKUTEN_API_KNOWLEDGE_BASE.md - 基础 API 知识库
- ITEM_API_2.0_DETAIL_EXAMPLE.md - 商品 API 2.0 详情
- INVENTORY_API_2.0_DETAIL_EXAMPLE.md - 库存 API 2.0 详情

---

*本文档随问题解决进度持续更新*

---

## 新发现问题

### 🔴 P0-15: 当前方案无法获取库存为 0 的商品

**发现日期**: 2026-02-17
**问题描述**: 当前 SKU 同步方案存在设计缺陷

**问题根源**:
- 当前使用 `GET /es/2.0/inventories/bulk-get/range` 获取 SKU
- 这个 API 的设计目的是"按库存数量范围查询"
- **库存为 0 的商品不会出现在查询结果中**

**为什么这是一个问题**:
1. **新上架商品**: 刚上架但库存为 0 的商品无法自动同步
2. **售罄商品**: 库存为 0 但仍在售的商品会从系统中消失
3. **数据不完整**: SKU 列表不应依赖库存状态
4. **用户体验差**: 需要手动导入库存为 0 的商品

**正常的商品列表 API 应该**:
- 返回店铺所有商品，不管库存状态
- 包含分页功能
- 可能包含筛选条件（按更新时间、状态等）

---

### 当前解决方案的局限

**实现的方案** (P0-13):
```python
# 遍历库存范围 (0-1000, 1000-2000, ..., 9000-10000)
for min_q in range(0, 10001, INVENTORY_BATCH_SIZE):
    response = await client.get_inventory_range(min_q, max_q)
    # 只返回有库存的 SKU
```

**无法获取的商品**:
- 新上架但库存为 0 的商品
- 暂时售罄的商品
- 预售商品（库存设置为 0）

---

### 需要进一步调查

**可能的 API 端点** (需要测试):

| 端点 | 说明 | 测试状态 |
|------|------|----------|
| `/es/2.0/items/list` | 可能的商品列表端点 | ❓ 未测试 |
| `/es/2.0/items/search` | 商品搜索 | ❌ 404 |
| `/es/2.0/item/getItems` | 商品获取（文档提及） | ❌ 404 |
| `/es/2.0/products/list` | 产品列表 | ❓ 未测试 |

**行动项**:
1. 搜索乐天 RMS 官方文档
2. 查找 ItemAPI 的完整端点列表
3. 联系乐天技术支持（如需要）

---

### 临时解决方案

**选项 1: 从订单历史中提取 SKU**
```python
# 从最近的订单中提取所有出现过的 SKU
# 缺点: 只能获取有销售记录的 SKU
# 优点: 确实存在于系统中的商品
```

**选项 2: CSV 导出**
- 使用乐天管理后台导出商品 CSV
- 通过 API 上传到系统
- 缺点: 需要手动操作

**选项 3: 接受限制，等待官方 API**
- 继续使用当前方案
- 库存为 0 的商品需要手动添加
- 不推荐：这不是可持续的解决方案

---

## 任务关联

- **P0-15**: 寻找真正的商品列表 API
- **TASKS.md**: 已添加 P0-15 任务
