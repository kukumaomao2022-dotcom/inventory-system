# 任务列表

> **最后更新**: 2026-02-17
> **状态**: 活跃任务追踪中

---

## 🔴 P0 紧急任务

### P0-15: 寻找真正的商品列表 API ✅ 已完成

**状态**: ✅ 已完成（使用 CSV 导入方案）
**优先级**: P0
**描述**: 当前 SKU 同步使用库存范围 API，只能获取有库存的 SKU，无法获取库存为 0 的新商品

**解决方案**: CSV 导入功能（按需导入关键商品）

**CSV 导入功能已实现**:
- ✅ 支持乐天 CSV 格式（全部.csv 和 平时.csv）
- ✅ Shift-JIS 编码支持
- ✅ API 端点: `POST /api/import/rakuten-csv`
- ✅ 支持按需导入，无需导入全部 18,355 行

**使用方法**:
```bash
# 导入关键商品到指定店铺
curl -X POST http://localhost:8000/api/import/rakuten-csv?store_id={store_id} \
  -F "file=@平时.csv"
```

**说明**: 只需导入关键的几个商品即可

**影响文件**:
- `app/services/sku_sync.py` - 需要更新同步逻辑
- `app/services/rakuten_api.py` - 添加新的 API 方法

**可能的解决方案**:
1. 查找并使用真正的商品列表 API
2. 使用乐天管理后台的 CSV 导出功能
3. 从订单历史中提取 SKU 列表（作为补充）

---

### P0-08: 实现订单确认重试队列 ✅ 已完成

**状态**: ✅ 已完成
**优先级**: P0
**描述**: 订单确认可能失败，需要实现重试队列机制

**影响文件**:
- `app/services/order_polling.py`

**已完成的修改**:
- ✅ 重试队列表结构已存在 (`OrderConfirmRetry` model)
- ✅ 实现重试逻辑（指数退避）
- ✅ 记录重试次数
- ✅ 最大重试次数后标记失败
- ✅ 修复代码中的语法错误（缺少 for 循环）
- ✅ 修正字段名（`retry_metadata`）
- ✅ 统一使用 `RetryConfig` 配置类

**验收标准**:
- [x] 创建重试队列表结构
- [x] 实现重试逻辑（指数退避）
- [x] 记录重试次数
- [x] 最大重试次数后标记失败

**功能说明**:
1. 订单确认失败时自动加入重试队列
2. 指数退避：5分钟 → 10分钟 → 20分钟
3. 最多重试 3 次
4. 达到最大重试次数后标记为失败

**相关方法**:
- `_add_order_to_retry_queue()` - 加入重试队列
- `process_retry_queue()` - 处理重试队列

---

### P0-09: 记录同步失败到事件表 ✅ 已完成

**状态**: ✅ 已完成
**优先级**: P0
**描述**: API 调用失败时记录到 inventory_events 表

**影响文件**:
- `app/db/models.py` - 添加 API_ERROR 和 SYNC_FAILURE 事件类型
- `app/db/schemas.py` - 添加对应的 Schema
- `app/services/inventory.py` - 添加 log_api_error 方法
- `app/services/order_polling.py` - 更新错误处理
- `app/services/sku_sync.py` - 更新错误处理

**已完成的修改**:
- ✅ 添加 API_ERROR 事件类型
- ✅ 添加 SYNC_FAILURE 事件类型
- ✅ 实现 log_api_error() 辅助方法
- ✅ 在 search_order 失败时记录
- ✅ 在 get_order 失败时记录
- ✅ 在 confirm_order 失败时记录
- ✅ 在 confirm_order 重试失败时记录
- ✅ 在 get_items 失败时记录

**验收标准**:
- [x] 所有 API 失败记录事件
- [x] 包含错误信息和原始请求数据
- [x] 用于后续重试和分析

**功能说明**:
1. 所有 API 调用失败都会记录到 inventory_events 表
2. 记录内容包括：
   - 错误消息
   - 操作类型（search_order, get_order, confirm_order, get_items 等）
   - 店铺 ID
   - SKU ID（如果适用）
   - 错误详情（错误码、HTTP 状态等）
   - 原始请求数据
3. 不会影响库存快照（update_snapshot=False）

---

### P0-11: 添加环境变量验证 ✅ 已完成

**状态**: ✅ 已完成
**优先级**: P0
**描述**: 启动时验证必要的环境变量

**影响文件**:
- `app/core/validate.py` - 新建验证模块
- `app/main.py` - 添加启动验证
- `.env.example` - 更新文档说明

**已完成的修改**:
- ✅ 创建 `app/core/validate.py` 验证模块
- ✅ 实现 `validate_environment()` 函数
- ✅ 实现 `print_env_info()` 函数
- ✅ 在 `main.py` 中添加启动验证
- ✅ 更新 `.env.example` 文档

**验证内容**:
| 环境变量 | 类型 | 验证说明 |
|---------|------|----------|
| DATABASE_URL | 必需 | 格式检查，必须以 `postgresql+asyncpg://` 开头 |
| DATABASE_URL_SYNC | 必需 | 格式检查，必须以 `postgresql://` 开头 |
| REDIS_URL | 必需 | 格式检查，必须以 `redis://` 开头 |
| ENVIRONMENT | 必需 | 值检查，必须是 prod/test/dev 之一 |
| RAKUTEN_DEFAULT_SERVICE_SECRET | 可选 | 格式检查，长度验证 |
| RAKUTEN_DEFAULT_LICENSE_KEY | 可选 | 格式检查，长度验证 |
| RAKUTEN_PROXY | 可选 | 格式检查，必须是 http:// 或 https:// |

**验收标准**:
- [x] 启动时检查所有必要变量
- [x] 缺失时给出明确错误信息
- [x] 包含变量名和格式说明

**错误输出示例**:
```
======================================================================
❌ 环境变量验证失败！
======================================================================

缺少或格式不正确的环境变量：

1. DATABASE_URL
   原因: 数据库连接 URL 未设置
   示例: postgresql+asyncpg://user:password@localhost:5432/inventory_db
   格式: postgresql+asyncpg://[user]:[password]@[host]:[port]/[database]

2. REDIS_URL
   原因: Redis 连接 URL 未设置
   示例: redis://localhost:6379/0
   格式: redis://[host]:[port]/[db]

======================================================================
```

**使用方法**:
```bash
# 单独测试环境变量验证
python3 app/core/validate.py

# 启动应用时会自动验证
python app/main.py
```

---

### P0-12: 修复 API 客户端 - Content-Type 问题 ✅ 已确认正确

**状态**: ✅ 已确认代码正确
**优先级**: P0
**描述**: Content-Type 格式检查

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

**注意**: 格式是 `application/json; charset=utf-8`（有空格也是可以工作的）
- 测试显示这个格式可以正常工作
- 乐天 API 可能接受多种变体格式

---

### P0-13: 实现 SKU 列表获取 ✅ 已完成

**状态**: ✅ 已完成
**优先级**: P0
**描述**: 实现从 Rakuten API 获取所有 SKU 列表

**问题分析**:
- ❌ `/es/2.0/item/getItems` 端点不存在 (404)
- ❌ 其他可能的商品列表端点也不存在

**解决方案**:
使用 `GET /es/2.0/inventories/bulk-get/range` 按库存数量范围获取 SKU，然后获取每个商品详细信息。

**影响文件**:
- `app/services/rakuten_api.py` - 添加新方法
- `app/services/sku_sync.py` - 重写同步逻辑

**已完成的修改**:
- ✅ 添加 `get_inventory_range()` 方法
- ✅ 添加 `get_item_details()` 方法
- ✅ 重写 `sync_store_skus()` 使用新 API
- ✅ 添加 `_process_inventory()` 处理库存记录
- ✅ 添加 `_get_item_with_details()` 获取商品详情
- ✅ 去重机制防止重复处理

**实现方案**:
1. 遍历库存范围 (0-1000, 1000-2000, ..., 9000-10000)
2. 每个范围使用 `get_inventory_range()` 获取有库存的 SKU
3. 对每个 SKU 使用 `get_item_details()` 获取完整商品信息
4. 记录所有处理和错误

**优缺点**:
- ✅ 优点: 可获取所有有库存的 SKU 和完整商品信息
- ⚠️ 缺点: 无法获取库存为 0 的新商品
- ⚠️ 需要多次 API 调用（约10次范围查询 + N次商品详情查询）

**新增方法**:
| 方法 | 端点 | 说明 |
|------|------|------|
| `get_inventory_range(min, max)` | GET /es/2.0/inventories/bulk-get/range | 按库存范围获取 |
| `get_item_details(manage_number)` | GET /es/2.0/items/manage-numbers/{id} | 获取商品详情 |

---

### P0-14: 添加代理支持 ✅ 已完成

**状态**: ✅ 已完成
**优先级**: P0
**描述**: 网络无法直接访问 Rakuten API，需要通过代理

**测试结果**:
```
无代理: ConnectTimeout (无法连接 api.rms.rakuten.co.jp)
代理 10808: 成功连接
```

**已完成的修改**:
- ✅ 添加代理环境变量 `RAKUTEN_PROXY` 到 `app/core/config.py`
- ✅ 在 AsyncClient 中配置代理 `app/services/rakuten_api.py`
- ✅ 更新 `.env.example` 文档说明

**使用方法**:
```bash
# 国内使用代理
export RAKUTEN_PROXY="http://127.0.0.1:10808"

# 日本不需要代理（留空或不设置）
export RAKUTEN_PROXY=""
```

---

## 🟡 P1 中等优先级

### P1-01: 更新 API 文档 ✅ 已完成

**状态**: ✅ 已完成
**描述**: 根据实际测试结果更新 API 知识库

**已完成的更新**:
- ✅ 修正 Content-Type 说明
- ✅ 添加代理配置说明
- ✅ 记录已测试的端点和结果
- ✅ 标记不存在的端点
- ✅ 更新错误码说明

---

### P1-02: 实现完整的 SKU 同步

**状态**: 部分完成（有模拟模式）
**描述**: 实现从 Rakuten API 自动同步所有 SKU 到数据库

**需要实现**:
- [ ] 使用库存 API 遍历获取所有 SKU
- [ ] 获取商品详细信息（如果找到正确的 API）
- [ ] 更新或插入数据库记录
- [ ] 处理分页
- [ ] 错误处理和重试

---

### P1-03: API 响应数据完善

**状态**: 待实现
**描述**: 库存 API 只返回 manageNumber 和 variantId，需要获取完整商品信息

**缺失数据**:
- 商品名称 (itemName)
- 商品 URL (itemUrl)
- 商品图片 (imageUrl)
- 商品价格 (itemPrice)

**可能的解决方案**:
1. 使用 `GET /es/2.0/items/manage-numbers/{manageNumber}` 获取单个商品详情
2. 查找商品批量获取 API
3. 使用前端爬虫（不推荐）

---

## 📊 问题追踪

### 已解决的问题

- ✅ P0-06: 完成 RAKUTEN_PAY_ORDER_API.md 文档
- ✅ P0-07: 更新 RAKUTEN_API_KNOWLEDGE_BASE.md
- ✅ P0-08: 实现订单确认重试队列
- ✅ P0-09: 记录同步失败到事件表
- ✅ P0-11: 添加环境变量验证
- ✅ P0-12: 确认 Content-Type 格式正确
- ✅ P0-13: 实现 SKU 列表获取
- ✅ P0-14: 添加代理支持

### 当前阻塞

1. **商品列表 API**: 端点不存在，需要使用替代方案

---

## 📁 相关文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `TASKS.md` | ✅ 本文件 | 任务列表 |
| `SKU_SYNC_ISSUES.md` | 🟡 部分解决 | SKU 同步问题详细分析 |
| `RAKUTEN_API_KNOWLEDGE_BASE.md` | ✅ 已更新 | API 知识库 |
| `app/services/rakuten_api.py` | ✅ 已添加代理 | API 客户端实现 |
| `app/services/sku_sync.py` | 🟡 需修改 | SKU 同步服务 (get_items 方法需替换) |
| `app/core/config.py` | ✅ 已更新 | 添加 RAKUTEN_PROXY 配置 |
| `.env.example` | ✅ 已更新 | 添加代理文档说明 |

---

## 🔄 最近更新

### 2026-02-17

**API 测试结果**:
- ✅ 发现正确的 Content-Type 格式: `application/json;charset=utf-8`
- ✅ 订单搜索 API 工作正常: `POST /es/2.0/order/searchOrder/`
- ✅ 库存范围获取 API 工作正常: `GET /es/2.0/inventories/bulk-get/range`
- ❌ 商品列表端点不存在: `/es/2.0/item/getItems` 返回 404
- ✅ 网络问题已解决: 通过代理可以正常访问 API

**已完成的任务**:
- ✅ P0-08: 实现订单确认重试队列 (修复语法错误和字段名)
- ✅ P0-09: 记录同步失败到事件表 (添加 API_ERROR 事件类型和 log_api_error 方法)
- ✅ P0-11: 添加环境变量验证 (创建 validate.py 模块)
- ✅ P0-13: 实现 SKU 列表获取 (使用库存范围 API 遍历)
- ✅ P0-12: 确认 Content-Type 格式正确
- ✅ P0-14: 添加代理支持
- ✅ P1-01: 更新 API 文档

**已删除的任务**:
- ~~P0-10: 添加测试商品 ce1111 数据库保护~~ (不合理 - ce1111 是用于 API 测试的真实商品)

**待办事项**:
1. 无 P0 紧急任务！
2. 可选的 P1 任务: SKU 同步完善、API 响应数据完善

**已删除的任务**:
- ~~P0-10: 添加测试商品 ce1111 数据库保护~~ (不合理 - ce1111 是用于 API 测试的真实商品)
