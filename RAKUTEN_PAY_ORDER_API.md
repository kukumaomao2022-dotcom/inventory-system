# Rakuten Pay Order API (楽天ペイ受注API)

> **最后更新**: 2026-02-17
> **API 版本**: ES 2.0
> **目的**: 详细的 Rakuten Pay 订单 API 参考文档

---

## 📌 基本信息

| 项目 | 值 |
|------|-----|
| API 名称 | Rakuten Pay Order API (楽天ペイ受注API) |
| 基础 URL | `https://api.rms.rakuten.co.jp` |
| API 版本 | ES 2.0 |
| 认证方式 | ESA (e-commerce Service Authentication) |
| 请求格式 | JSON |
| 响应格式 | JSON |
| 请求频率限制 | 建议 1 请求/秒 |

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

---

## 📡 API 端点 (18个函数)

### 1. searchOrder - 搜索订单

**端点**: `POST /es/2.0/order/searchOrder/`

**用途**: 按日期范围搜索订单，返回订单号列表

**请求体**:
```json
{
  "dateType": 1,
  "startDatetime": "2026-02-01T00:00:00+0900",
  "endDatetime": "2026-02-17T23:59:59+0900",
  "orderProgressList": [100, 300],
  "shopUrl": "coucou-doma.rakuten.co.jp",
  "PaginationRequestModel": {
    "requestRecordsAmount": 30,
    "requestPage": 1,
    "sortModelList": [
      {
        "sortColumn": 1,
        "sortDirection": 2
      }
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

**字段说明**:
| 字段 | 类型 | 必填 | 最大字节 | 说明 |
|------|------|------|----------|------|
| dateType | int | 是 | - | 日期类型: 1=订单日期, 2=配送日期 |
| startDatetime | string | 是 | 22 | 开始时间 (YYYY-MM-DDTHH:MM:SS+0900) |
| endDatetime | string | 是 | 22 | 结束时间 (YYYY-MM-DDTHH:MM:SS+0900) |
| orderProgressList | array | 否 | - | 订单状态列表 |
| shopUrl | string | 否 | 100 | 店铺URL |

---

### 2. getOrder - 获取订单详情

**端点**: `POST /es/2.0/order/getOrder`

**用途**: 根据订单号获取订单详情

**支持版本**: 1-10 (version 参数可选)

**请求体**:
```json
{
  "orderNumberList": ["123456789-20260217-123456789"],
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**响应示例**:
```json
{
  "orderList": {
    "orderNumber": "123456789-20260217-123456789",
    "orderProgress": 100,
    "orderDate": "2026-02-17T12:00:00+0900",
    "ordererModel": {
      "ordererName1": "山田",
      "ordererName2": "太郎"
    },
    "senderModel": {
      "senderName1": "山田",
      "senderName2": "太郎"
    },
    "paymentModel": {
      "paymentName": "楽天ペイ"
    },
    "itemsModel": {
      "itemsModel": [
        {
          "skuNumber": "ce1111",
          "itemManagementNumber": "ce1111",
          "quantity": 1,
          "itemName": "测试商品"
        }
      ]
    }
  }
}
```

**字段说明**:
| 字段 | 类型 | 必填 | 最大字节 | 说明 |
|------|------|------|----------|------|
| orderNumberList | array | 是 | - | 订单号列表 |
| shopUrl | string | 否 | 100 | 店铺URL |

**版本差异**:
| 版本 | 新增字段 |
|------|----------|
| 1 | 基础字段 |
| 2 | socialGift |
| 3 | deliveryCertPrgFlag |
| 4 | oneDayOperationFlag |
| 5-10 | 各种新增字段 |

---

### 3. confirmOrder - 确认订单

**端点**: `POST /es/2.0/order/confirmOrder`

**用途**: 确认订单，将状态从 100 变更为 300

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**响应**: 成功返回空对象

---

### 4. updateOrderShipping - 更新配送信息

**端点**: `POST /es/2.0/order/updateOrderShipping`

**用途**: 更新订单的配送信息（状态 300-800）

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "shippingStatus": 500,
  "trackingNumber": "1234567890123",
  "deliveryServiceCode": "001",
  "deliveryServiceName": "佐川急便",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**字段说明**:
| 字段 | 类型 | 必填 | 最大字节 | 说明 |
|------|------|------|----------|------|
| orderNumber | string | 是 | 22 | 订单号 |
| shippingStatus | int | 是 | - | 配送状态 |
| trackingNumber | string | 条件 | 20 | 追踪号码（状态500时必填） |
| deliveryServiceCode | string | 条件 | 10 | 配送服务代码 |
| deliveryServiceName | string | 条件 | 20 | 配送服务名称 |

---

### 5. updateOrderShippingAsync - 异步更新配送信息

**端点**: `POST /es/2.0/order/updateOrderShippingAsync`

**用途**: 异步更新配送信息，适合批量处理

**请求体**: 同 `updateOrderShipping`

**响应**: 返回处理请求ID

---

### 6. cancelOrder - 取消订单

**端点**: `POST /es/2.0/order/cancelOrder`

**用途**: 取消订单（状态 100-400）

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "cancelReason": "在庫切れ",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**字段说明**:
| 字段 | 类型 | 必填 | 最大字节 | 说明 |
|------|------|------|----------|------|
| orderNumber | string | 是 | 22 | 订单号 |
| cancelReason | string | 是 | 200 | 取消原因 |

---

### 7. cancelOrderAfterShipping - 发货后取消

**端点**: `POST /es/2.0/order/cancelOrderAfterShipping`

**用途**: 发货后取消订单（状态 500-800）

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "cancelReason": "返品",
  "returnReason": "サイズ不合",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

---

### 8. updateOrderSender - 更新收件人信息

**端点**: `POST /es/2.0/order/updateOrderSender`

**用途**: 更新收件人信息（状态 100-400）

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "senderName1": "鈴木",
  "senderName2": "花子",
  "senderZipCode1": "100",
  "senderZipCode2": "0001",
  "senderAddress1": "東京都",
  "senderAddress2": "千代田区",
  "senderAddress3": "千代田1-1",
  "senderAddress4": "ビル101",
  "senderTel1": "03",
  "senderTel2": "1234",
  "senderTel3": "5678",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

---

### 9. updateOrderSenderAfterShipping - 发货后更新收件人

**端点**: `POST /es/2.0/order/updateOrderSenderAfterShipping`

**用途**: 发货后更新收件人信息（状态 500-800）

**请求体**: 同 `updateOrderSender`

---

### 10. updateOrderMemo - 更新订单备注

**端点**: `POST /es/2.0/order/updateOrderMemo`

**用途**: 更新订单备注信息

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "orderMemo": "包装依頼あり",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**字段说明**:
| 字段 | 类型 | 必填 | 最大字节 | 说明 |
|------|------|------|----------|------|
| orderNumber | string | 是 | 22 | 订单号 |
| orderMemo | string | 否 | 2000 | 订单备注 |

---

### 11. updateOrderRemarks - 更新订单说明

**端点**: `POST /es/2.0/order/updateOrderRemarks`

**用途**: 更新订单说明（顾客可见）

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "orderRemarks": "迅速発送お願いします",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**字段说明**:
| 字段 | 类型 | 必填 | 最大字节 | 说明 |
|------|------|------|----------|------|
| orderNumber | string | 是 | 22 | 订单号 |
| orderRemarks | string | 否 | 1000 | 订单说明 |

---

### 12. updateOrderSubStatus - 更新子状态

**端点**: `POST /es/2.0/order/updateOrderSubStatus`

**用途**: 更新订单的子状态

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "subStatusId": "1",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**字段说明**:
| 字段 | 类型 | 必填 | 最大字节 | 说明 |
|------|------|------|----------|------|
| orderNumber | string | 是 | 22 | 订单号 |
| subStatusId | string | 是 | 10 | 子状态ID |

---

### 13. getSubStatusList - 获取子状态列表

**端点**: `POST /es/2.0/order/getSubStatusList`

**用途**: 获取可用的子状态列表

**请求体**:
```json
{
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**响应**:
```json
{
  "subStatusList": {
    "subStatus": [
      {
        "subStatusId": "1",
        "subStatusName": "入金待ち"
      },
      {
        "subStatusId": "2",
        "subStatusName": "検品中"
      }
    ]
  }
}
```

---

### 14. getPayment - 获取支付信息

**端点**: `POST /es/2.0/order/getPayment`

**用途**: 获取订单的支付信息

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**响应**:
```json
{
  "paymentModel": {
    "paymentId": "1",
    "paymentName": "楽天ペイ",
    "paymentPrice": 1000,
    "paymentStatus": "入金待ち"
  }
}
```

---

### 15. updateOrderOrderer - 更新订购人信息

**端点**: `POST /es/2.0/order/updateOrderOrderer`

**用途**: 更新订购人信息（状态 100-400）

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "ordererName1": "田中",
  "ordererName2": "一郎",
  "ordererZipCode1": "100",
  "ordererZipCode2": "0001",
  "ordererAddress1": "東京都",
  "ordererAddress2": "港区",
  "ordererAddress3": "港1-1",
  "ordererTel1": "03",
  "ordererTel2": "9876",
  "ordererTel3": "5432",
  "ordererMailAddress": "test@example.com",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

---

### 16. updateOrderDelivery - 更新配送方法

**端点**: `POST /es/2.0/order/updateOrderDelivery`

**用途**: 更新订单的配送方法

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "deliveryMethodId": "1",
  "deliveryDate": "2026-02-20",
  "deliveryTimeZone": "12-14",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

**字段说明**:
| 字段 | 类型 | 必填 | 最大字节 | 说明 |
|------|------|------|----------|------|
| orderNumber | string | 是 | 22 | 订单号 |
| deliveryMethodId | string | 是 | 10 | 配送方法ID |
| deliveryDate | string | 否 | 10 | 配送日期 (YYYY-MM-DD) |
| deliveryTimeZone | string | 否 | 10 | 配送时间带 |

---

### 17. getNenga - 获取年贺状信息

**端点**: `POST /es/2.0/order/getNenga`

**用途**: 获取年贺状配送信息

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

---

### 18. updateOrderNenga - 更新年贺状信息

**端点**: `POST /es/2.0/order/updateOrderNenga`

**用途**: 更新年贺状配送信息

**请求体**:
```json
{
  "orderNumber": "123456789-20260217-123456789",
  "nengaType": "1",
  "shopUrl": "coucou-doma.rakuten.co.jp"
}
```

---

## 📊 订单状态映射

| 状态码 | 状态说明 | 日文 | 内部事件 | 可用操作 |
|--------|----------|------|----------|----------|
| 100 | 新订单 | 注文受付済み | ORDER_RECEIVED | confirmOrder, cancelOrder, updateOrderSender, updateOrderOrderer, updateOrderDelivery, updateOrderMemo, updateOrderRemarks, updateOrderSubStatus |
| 200 | - | - | - | (未在文档中详细说明) |
| 300 | 等待发货 | 発送待ち | ORDER_CONFIRMED | updateOrderShipping, cancelOrder, updateOrderSender, updateOrderOrderer, updateOrderDelivery, updateOrderMemo, updateOrderRemarks, updateOrderSubStatus |
| 400 | 变更确认等待 | 変更確認待ち | - | cancelOrder, updateOrderSender, updateOrderOrderer, updateOrderDelivery, updateOrderMemo, updateOrderRemarks, updateOrderSubStatus |
| 500 | 已发货 | 発送済み | ORDER_SHIPPED | cancelOrderAfterShipping, updateOrderSenderAfterShipping, updateOrderMemo, updateOrderRemarks, updateOrderSubStatus |
| 600 | 支付处理中 | 決済処理中 | - | cancelOrderAfterShipping, updateOrderSenderAfterShipping, updateOrderMemo, updateOrderRemarks, updateOrderSubStatus |
| 700 | 支付完成 | 決済完了 | - | cancelOrderAfterShipping, updateOrderSenderAfterShipping, updateOrderMemo, updateOrderRemarks, updateOrderSubStatus |
| 800 | 取消确认等待 | キャンセル確認待ち | - | cancelOrderAfterShipping, updateOrderSenderAfterShipping, updateOrderMemo, updateOrderRemarks, updateOrderSubStatus |
| 900 | 已取消 | キャンセル済み | ORDER_CANCELLED | - |

---

## 🚨 错误处理

### 常见错误码

| 状态码 | 说明 | 处理方式 |
|--------|------|----------|
| 200 | 成功 | 正常处理 |
| 400 | 请求参数错误 | 检查请求体格式 |
| 401 | 认证失败 | 检查 License Key 和 Service Secret |
| 404 | 订单不存在 | 检查订单号是否正确 |
| 409 | 状态冲突 | 检查订单当前状态是否支持该操作 |
| 429 | 请求过于频繁 | 指数退避重试 |
| 500 | 服务器错误 | 重试 |

### 错误响应示例

```json
{
  "error": {
    "code": "ERR_001",
    "message": "注文番号が見つかりません",
    "details": {
      "orderNumber": "123456789-20260217-123456789"
    }
  }
}
```

### 重试策略

```python
import asyncio

max_retries = 5
for retry in range(max_retries):
    try:
        response = await api_call()
        if response.status_code == 200:
            return response
        elif response.status_code == 429:
            wait_time = 2 ** retry  # 1s, 2s, 4s, 8s, 16s
            await asyncio.sleep(wait_time)
    except Exception as e:
        if retry < max_retries - 1:
            wait_time = 2 ** retry
            await asyncio.sleep(wait_time)
```

---

## 📋 版本历史

### getOrder API 版本更新

| 版本 | 更新日期 | 新增内容 |
|------|----------|----------|
| 1.0 | - | 初始版本 |
| 2.0 | - | 新增 socialGift 字段 |
| 3.0 | - | 新增 deliveryCertPrgFlag 字段 |
| 4.0 | - | 新增 oneDayOperationFlag 字段 |
| 5.0 | - | 新增多个字段 |
| 6.0 | - | 新增多个字段 |
| 7.0 | - | 新增多个字段 |
| 8.0 | - | 新增多个字段 |
| 8.5 | - | 优化更新 |

---

## 📝 注意事项

### 1. 状态操作限制

- 每个操作只能对特定状态的订单执行
- 发货前和发货后的某些操作需要不同的端点
- 状态转换图：100 → 300 → 400/500 → 600/700 → 800/900

### 2. 请求频率限制

- 建议每秒不超过 1 次请求
- 批量操作时需要添加延迟

### 3. shop_url 参数

- `shopUrl` 在请求体中是**可选**的
- 但多店铺场景下应该指定
- 格式: `shopname.rakuten.co.jp`（不包含协议和路径）

### 4. 时区处理

- 所有时间参数使用 `+0900` (日本标准时间)
- 格式: `YYYY-MM-DDTHH:MM:SS+0900`

### 5. 字节限制

- 所有字符串字段都有最大字节限制
- 日文字符可能占 3 字节
- 建议截断超长输入

---

## 🔧 客户端实现示例

### Python 客户端

```python
import base64
import aiohttp

class RakutenPayOrderAPI:
    def __init__(self, service_secret: str, license_key: str, shop_url: str = None):
        self.base_url = "https://api.rms.rakuten.co.jp/es/2.0/order"
        self.service_secret = service_secret
        self.license_key = license_key
        self.shop_url = shop_url

    def _get_auth_header(self) -> str:
        auth_str = f"{self.service_secret}:{self.license_key}"
        encoded = base64.b64encode(auth_str.encode()).decode()
        return f"ESA {encoded}"

    async def search_order(self, start_datetime: str, end_datetime: str,
                          order_progress_list: list = None) -> dict:
        url = f"{self.base_url}/searchOrder/"
        payload = {
            "dateType": 1,
            "startDatetime": start_datetime,
            "endDatetime": end_datetime,
            "shopUrl": self.shop_url
        }
        if order_progress_list:
            payload["orderProgressList"] = order_progress_list

        headers = {"Authorization": self._get_auth_header()}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return await resp.json()

    async def get_order(self, order_numbers: list) -> dict:
        url = f"{self.base_url}/getOrder"
        payload = {
            "orderNumberList": order_numbers,
            "shopUrl": self.shop_url
        }
        headers = {"Authorization": self._get_auth_header()}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return await resp.json()

    async def confirm_order(self, order_number: str) -> dict:
        url = f"{self.base_url}/confirmOrder"
        payload = {
            "orderNumber": order_number,
            "shopUrl": self.shop_url
        }
        headers = {"Authorization": self._get_auth_header()}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return await resp.json()

    async def update_order_shipping(self, order_number: str, shipping_status: int,
                                   tracking_number: str = None) -> dict:
        url = f"{self.base_url}/updateOrderShipping"
        payload = {
            "orderNumber": order_number,
            "shippingStatus": shipping_status,
            "shopUrl": self.shop_url
        }
        if tracking_number:
            payload["trackingNumber"] = tracking_number
        headers = {"Authorization": self._get_auth_header()}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return await resp.json()

    async def cancel_order(self, order_number: str, cancel_reason: str) -> dict:
        url = f"{self.base_url}/cancelOrder"
        payload = {
            "orderNumber": order_number,
            "cancelReason": cancel_reason,
            "shopUrl": self.shop_url
        }
        headers = {"Authorization": self._get_auth_header()}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return await resp.json()
```

---

## 📚 参考资料

- Rakuten RMS API 官方文档: https://webservice.rakuten.co.jp/api/
- Rakuten Pay Order API 文档: https://api.rms.rakuten.co.jp/es/2.0/order/

---

*本文档基于 Rakuten Pay Order API 官方文档整理*
