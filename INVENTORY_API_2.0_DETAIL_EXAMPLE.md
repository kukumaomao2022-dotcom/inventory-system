# Inventory API 2.0 详细文档

> **API 版本**: 2.3
> **最后更新**: 2026-02-17
> **用途**: 获取和更新库存信息

---

## 概述

InventoryAPI 2.0 是用于获取和更新库存信息的API。

**SKU移行前可用的功能**:
- `inventories.variants.get`
- `inventories.bulk.get.range`

---

## 功能列表

| 功能 | 说明 | 请求限制 | HTTP方法 |
|------|------|----------|----------|
| **inventories.variants.get** | 获取库存数（单个SKU） | 秒间 1 请求 | GET |
| **inventories.variants.upsert** | 注册/更新库存数（单个SKU） | 秒间 1 请求 | PUT |
| **inventories.variants.delete** | 删除库存信息（单个SKU） | 秒间 1 请求 | DELETE |
| **inventories.bulk.get.range** | 批量获取库存（按范围，最多1000件） | 秒间 5 请求 | GET |
| **inventories.bulk.get** | 批量获取库存（指定SKU，最多1000件） | 秒间 5 请求 | POST |
| **inventories.bulk.upsert** | 批量注册/更新库存（最多400件） | 秒间 1 请求 | POST |

---

## 1. inventories.variants.upsert - 注册/更新库存数

### 概述

根据商品管理番号和SKU管理番号注册或更新库存数。

### ⚠️ 注意事项

- 存在不存在的商品管理番号或不存在的SKU时，**不会报错**
- 但库存信息只处于存在状态（无法确认）
- 这种孤立的库存信息会在最后更新日期24小时后被删除
- 新规注册时必须指定 "ABSOLUTE" 模式

### 基本信息

| 项目 | 值 |
|------|-----|
| 功能名称 | 注册/更新库存数 |
| 端点 | `PUT /es/2.0/inventories/manage-numbers/{manageNumber}/variants/{variantId}` |
| 认证 | ESA 认证 |
| 请求限制 | 秒间 1 请求 |

---

## 请求

### HTTP Header

| No | Key | Value |
|----|-----|-------|
| 1 | Authorization | ESA Base64(serviceSecret:licenseKey) |
| 2 | Content-Type | application/json |

### Path Parameter

| No | Parameter Name | Logical Name | Required | Type | Max Byte | Multiplicity | Description |
|----|---------------|--------------|----------|-------|----------|--------------|-------------|
| 1 | manageNumber | 商品管理番号 | yes | string | 32 | 1 | 商品管理番号が存在する場合、更新。<br>商品管理番号が存在しない場合、存在しない商品管理番号を指定したことでエラーにはなりませんが、在庫情報として設定される商品がないため、確認することはできません。また、定期的に削除されます。<br>以下の英数字、記号が使用可能。<br>・"a~z"・"A~Z"・"0-9"・"-", "_"。<br>大文字は小文字に自動変換。 |
| 2 | variantId | SKU管理番号 | yes | string | 32 | 1 | SKU管理番号が存在する場合、更新。<br>SKU管理番号が存在しない場合、存在しないSKU管理番号を指定したことでエラーにはなりませんが、在庫情報として設定される商品がないため、確認することはできません。また、定期的に削除されます。<br>以下の英数字、記号が使用可能。<br>・"a~z"・"A~Z"・"0-9"・"-", "_"。<br>大文字・小文字は、異なる文字として扱う。 |

### HTTP Body

#### Level 1: base - 请求参数

| No | Parameter Name | Logical Name | Required | Type | Max Value | Multiplicity | Description |
|----|---------------|--------------|----------|-------|-----------|--------------|-------------|
| 1 | mode | 更新モード | yes | enum | - | 1 | ・ABSOLUTE: 絶対値指定<br>・RELATIVE: 相対値指定<br><br>新規登録時は必ず「ABSOLUTE」を指定。 |
| 2 | quantity | 在庫数 | yes | number | 99999 | 1 | 商品の在庫数 |

---

## 响应

### HTTP Header

| No | Key | Value |
|----|-----|-------|
| 1 | Content-Type | application/json |

---

### 成功响应 (204 No Content)

HTTP Body: None

---

### 失败响应

#### 失敗した場合 (400 Bad Request / 404 Not Found)

##### Level 1: base

| No | Parameter Name | Logical Name | Not Null | Type | Multiplicity | Description |
|----|---------------|--------------|----------|-------|--------------|-------------|
| 1 | errors | エラー | yes | List<error> | 1..n | エラーのリスト |

##### Level 2: error

| No | Parameter Name | Logical Name | Not Null | Type | Multiplicity | Description |
|----|---------------|--------------|----------|-------|--------------|-------------|
| 1 | code | コード | yes | string | 1 | メッセージコードの一覧はこちら |
| 2 | message | メッセージ | yes | string | 1 | |
| 3 | metadata | メタデータ | yes | object | 1 | エラーの補足情報 |

##### Level 3: metadata

| No | Parameter Name | Logical Name | Not Null | Type | Multiplicity | Description |
|----|---------------|--------------|----------|-------|--------------|-------------|
| 1 | propertyPath | 属性パス | no | string | 1 | 発生したエラーの位置 |

#### 失败响应示例

```json
{
    "errors": [
        {
            "code": "IE0002",
            "message": "quantity has an invalid value : a.",
            "metadata": {
                "propertyPath": "quantity"
            }
        }
    ]
}
```

---

## curl 请求示例

### 成功请求

```bash
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/inventories/manage-numbers/mng1234/variants/sku1' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "mode": "ABSOLUTE",
    "quantity": 3
}'
```

### 失败请求

```bash
curl --location --request PUT 'https://api.rms.rakuten.co.jp/es/2.0/inventories/manage-numbers/mng1234/variants/sku1' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
    "mode": "ABSOLUTE",
    "quantity": "a"
}'
```

---

## 2. inventories.variants.delete - 删除库存信息

### 概述

根据商品管理番号和SKU管理番号删除库存信息。

### 基本信息

| 项目 | 值 |
|------|-----|
| 功能名称 | 删除库存信息 |
| 端点 | `DELETE /es/2.0/inventories/manage-numbers/{manageNumber}/variants/{variantId}` |
| 认证 | ESA 认证 |
| 请求限制 | 秒间 1 请求 |

---

## 请求

### HTTP Header

| No | Key | Value |
|----|-----|-------|
| 1 | Authorization | ESA Base64(serviceSecret:licenseKey) |

### Path Parameter

| No | Parameter Name | Logical Name | Required | Type | Max Byte | Multiplicity | Description |
|----|---------------|--------------|----------|-------|----------|--------------|-------------|
| 1 | manageNumber | 商品管理番号 | yes | string | 32 | 1 | 以下の英数字、記号が使用可能。<br>・"a~z"・"A~Z"・"0-9"・"-", "_"。<br>大文字は小文字に自動変換。 |
| 2 | variantId | SKU管理番号 | yes | string | 32 | 1 | 以下の英数字、記号が使用可能。<br>・"a~z"・"A~Z"・"0-9"・"-", "_"。<br>大文字・小文字は、異なる文字として扱う。 |

### HTTP Body

なし

---

## 响应

### 成功响应 (204 No Content)

HTTP Body: None

---

### 失败响应 (404 Not Found)

```json
{
    "errors": [
        {
            "code": "GE0014",
            "message": "Not found for inputs; manageNumber=mng123, variantId=sku2"
        }
    ]
}
```

---

## curl 请求示例

### 成功请求

```bash
curl --location --request DELETE 'https://api.rms.rakuten.co.jp/es/2.0/inventories/manage-numbers/mng1234/variants/sku1' \
--header 'Authorization: ESA xxx' --header 'Content-Type: application/json'
```

### 失败请求

```bash
curl --location --request DELETE 'https://api.rms.rakuten.co.jp/es/2.0/inventories/manage-numbers/mng1234/variants/sku2' \
--header 'Authorization: ESA xxx' --header 'Content-Type: application/json'
```

---

## 3. inventories.bulk.get.range - 批量获取库存（按范围）

### 概述

根据库存数的上下限，批量获取商品管理番号、SKU管理番号、库存数、注册日时、更新日时（最多1000件）。

按更新日期降序输出。

### 基本信息

| 项目 | 值 |
|------|-----|
| 功能名称 | 批量获取库存（按范围） |
| 端点 | `GET /es/2.0/inventories/bulk-get/range` |
| 认证 | ESA 认证 |
| 请求限制 | 秒间 5 请求 |

---

## 请求

### HTTP Header

| No | Key | Value |
|----|-----|-------|
| 1 | Authorization | ESA Base64(serviceSecret:licenseKey) |

### Query Parameter

| No | Parameter Name | Logical Name | Required | Type | Multiplicity | Description |
|----|---------------|--------------|----------|-------|--------------|-------------|
| 1 | minQuantity | 最小在庫数 | いずれかが必須 | number | 0..1 | ※店舗内の商品情報が1000SKUを超える場合はエラー（上限エラー）。 |
| 2 | maxQuantity | 最大在庫数 | number | 0..1 | |

### HTTP Body

None

---

## 响应

### 成功响应 (200 OK)

#### Level 1: base - 响应字段说明

| No | Parameter Name | Logical Name | Not Null | Type | Multiplicity | Description |
|----|---------------|--------------|----------|-------|--------------|-------------|
| 1 | inventories | 在庫情報 | yes | List<inventories> | 0..1000 | 在庫情報リスト |

#### Level 2: inventories

| No | Parameter Name | Logical Name | Not Null | Type | Multiplicity | Description |
|----|---------------|--------------|----------|-------|--------------|-------------|
| 1 | manageNumber | 商品管理番号 | yes | string | 1 | 以下の英数字、記号。<br>・"a~z"・"0~9"・"-", "_" |
| 2 | variantId | SKU管理番号 | yes | string | 1 | 以下の英数字、記号。<br>・"a~z"・"A~Z"・"0~9"・"-", "_" |
| 3 | quantity | 在庫数 | yes | number | 1 | 商品の在庫数 |
| 4 | created | 登録日時 | yes | string | 1 | 在庫数の初回登録日時。<br>フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。 |
| 5 | updated | 更新日時 | yes | string | 1 | 在庫数の更新日時。<br>フォーマットはISO 8601、タイムゾーンは日本標準時(JST)。 |

#### 响应示例

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
        },
        {
            "manageNumber": "mng1234",
            "variantId": "sku2",
            "quantity": 2,
            "created": "2022-01-03T19:00:00+09:00",
            "updated": "2022-02-10T19:30:00+09:00"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5",
            "quantity": 4,
            "created": "2022-01-04T19:00:00+09:00",
            "updated": "2022-02-08T19:30:00+09:00"
        },
        {
            "manageNumber": "mng9012",
            "variantId": "sku6",
            "quantity": 3,
            "created": "2022-01-03T19:00:00+09:00",
            "updated": "2022-02-04T19:30:00+09:00"
        }
    ]
}
```

---

### 失败响应 (400 Bad Request)

```json
{
    "errors": [
        {
            "code": "IE0003",
            "message": "minQuantity must be between 0 and 99999."
        }
    ]
}
```

---

## curl 请求示例

```bash
curl --location --request GET 'https://api.rms.rakuten.co.jp/es/2.0/inventories/bulk-get/range?minQuantity=1&maxQuantity=5' \
--header 'Authorization: ESA xxx'
```

---

## 4. inventories.bulk.get - 批量获取库存（指定SKU）

### 概述

根据商品管理番号和SKU管理番号批量获取库存数（最多1000件）。

### 基本信息

| 项目 | 值 |
|------|-----|
| 功能名称 | 批量获取库存（指定SKU） |
| 端点 | `POST /es/2.0/inventories/bulk-get` |
| 认证 | ESA 认证 |
| 请求限制 | 秒间 5 请求 |

---

## 请求

### HTTP Header

| No | Key | Value |
|----|-----|-------|
| 1 | Authorization | ESA Base64(serviceSecret:licenseKey) |
| 2 | Content-Type | application/json |

### HTTP Body

#### Level 1: base - 请求参数

| No | Parameter Name | Logical Name | Required | Type | Max Byte | Multiplicity | Description |
|----|---------------|--------------|----------|-------|----------|--------------|-------------|
| 1 | inventories | 在庫情報 | yes | List<inventory> | - | 1..1000 | 在庫情報リスト |

#### Level 2: inventory

| No | Parameter Name | Logical Name | Required | Type | Max Byte | Multiplicity | Description |
|----|---------------|--------------|----------|-------|----------|--------------|-------------|
| 1 | manageNumber | 商品管理番号 | yes | string | 32 | 1 | 以下の英数字、記号が使用可能。<br>・"a~z"・"A~Z"・"0~9"・"-", "_"。<br>大文字は小文字に自動変換。 |
| 2 | variantId | SKU管理番号 | yes | string | 32 | 1 | 以下の英数字、記号が使用可能。<br>・"a~z"・"A~Z"・"0~9"・"-", "_"。<br>大文字・小文字は、異なる文字として扱う。 |

---

## 响应

### 成功响应 (200 OK)

```json
{
    "inventories": [
        {
            "manageNumber": "mng1234",
            "variantId": "sku1",
            "quantity": 1,
            "created": "2022-01-01T19:00:00+09:00",
            "updated": "2022-02-01T19:30:00+09:00"
        },
        {
            "manageNumber": "mng5678",
            "variantId": "sku5",
            "quantity": 5,
            "created": "2022-01-03T19:00:00+09:00",
            "updated": "2022-02-04T19:30:00+09:00"
        }
    ]
}
```

---

### 失败响应 (400 Bad Request)

```json
{
    "errors": [
        {
            "code": "IE0004",
            "message": "Max length of manageNumber must be within 32 bytes.",
            "metadata": {
                "propertyPath": "inventories[0].manageNumber"
            }
        }
    ]
}
```

---

## curl 请求示例

```bash
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/inventories/bulk-get' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
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
}'
```

---

## 5. inventories.bulk.upsert - 批量注册/更新库存

### 概述

根据商品管理番号和SKU管理番号批量注册或更新库存数（最多400件）。

### ⚠️ 注意事项

- 存在不存在的商品管理番号或不存在的SKU时，**不会报错**
- 但库存信息只处于存在状态（无法确认）
- 这种孤立的库存信息会在最后更新日期24小时后被删除
- 新规注册时必须指定 "ABSOLUTE" 模式

### 基本信息

| 项目 | 值 |
|------|-----|
| 功能名称 | 批量注册/更新库存 |
| 端点 | `POST /es/2.0/inventories/bulk-upsert` |
| 认证 | ESA 认证 |
| 请求限制 | 秒间 1 请求 |
| 最大数量 | 400件 |

---

## 请求

### HTTP Header

| No | Key | Value |
|----|-----|-------|
| 1 | Authorization | ESA Base64(serviceSecret:licenseKey) |
| 2 | Content-Type | application/json |

### HTTP Body

#### Level 1: base - 请求参数

| No | Parameter Name | Logical Name | Required | Type | Max Byte | Multiplicity | Description |
|----|---------------|--------------|----------|-------|----------|--------------|-------------|
| 1 | inventories | 在庫情報 | yes | List<inventory> | - | 1..400 | 在庫情報リスト |

#### Level 2: inventory

| No | Parameter Name | Logical Name | Required | Type | Max Byte | Multiplicity | Description |
|----|---------------|--------------|----------|-------|----------|--------------|-------------|
| 1 | manageNumber | 商品管理番号 | yes | string | 32 | 1 | 商品管理番号が存在する場合、更新。<br>商品管理番号が存在しない場合、存在しない商品管理番号を指定したことでエラーにはなりませんが、在庫情報として設定される商品がないため、確認することはできません。また、定期的に削除されます。<br>以下の英数字、記号が使用可能。<br>・"a~z"・"A~Z"・"0-9"・"-", "_"。<br>大文字は小文字に自動変換。 |
| 2 | variantId | SKU管理番号 | yes | string | 32 | 1 | SKU管理番号が存在する場合、更新。<br>SKU管理番号が存在しない場合、存在しないSKU管理番号を指定したことでエラーにはなりませんが、在庫情報として設定される商品がないため、確認することはできません。また、定期的に削除されます。<br>以下の英数字、記号が使用可能。<br>・"a~z"・"A~Z"・"0-9"・"-", "_"。<br>大文字・小文字は、異なる文字として扱う。 |
| 3 | mode | 更新モード | yes | enum | - | 1 | ・ABSOLUTE：絶対値指定<br>・RELATIVE：相対値指定<br><br>新規登録時は必ず「ABSOLUTE」を指定 |
| 4 | quantity | 在庫数 | yes | number | 99999 | 1 | 商品の在庫数 |

---

## 响应

### 成功响应 (204 No Content)

HTTP Body: None

---

### 失败响应 (400 Bad Request)

```json
{
    "errors": [
        {
            "code": "IE0004",
            "message": "Max length of manageNumber must be within 32 bytes.",
            "metadata": {
                "propertyPath": "inventories[0].manageNumber"
            }
        }
    ]
}
```

---

## curl 请求示例

```bash
curl --location --request POST 'https://api.rms.rakuten.co.jp/es/2.0/inventories/bulk-upsert' \
--header 'Authorization: ESA xxx' \
--header 'Content-Type: application/json' \
--data-raw '{
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
}'
```

---

## 常见错误代码

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

## 更新模式说明

| mode | 说明 | 适用场景 |
|------|------|----------|
| **ABSOLUTE** | 絶対値指定 | 设置库存为指定值<br>新规注册时必须使用此模式 |
| **RELATIVE** | 相対値指定 | 增减库存（正数增加，负数减少） |

---

## 请求频率限制

| 功能 | 秒间最大请求数 |
|------|---------------|
| inventories.bulk.get / inventories.bulk.get.range | 5 |
| inventories.variants.get / variants.upsert / variants.delete / inventories.bulk.upsert | 1 |

**注意**: 流量集中时可能受到流量限制

---

## 注意事项

1. **大小写处理**
   - `manageNumber`: 大文字は小文字に自動変換（大写自动转为小写）
   - `variantId`: 大文字・小文字は、異なる文字として扱う（大小写视为不同字符）

2. **孤立库存信息**
   - 指定不存在的商品或SKU时不会报错
   - 孤立库存信息会在最后更新日期24小时后被删除

3. **时间格式**
   - ISO 8601 格式
   - 日本标准时 (JST)

4. **bulk.upsert**
   - 最多支持 400 件
   - 请求限制为 秒间 1 请求

5. **bulk.get**
   - 最多支持 1000 件
   - bulk.get.range 按更新日期降序输出

---

## 版本更新历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| 1.0 | 2022/07/21 | 初版 |
| 1.2 | 2022/11/30 | inventories.bulk.get.range 的查询参数修正，添加 IE0105 错误码 |
| 1.3 | 2022/12/28 | variantId 的 Max Byte 改为 32，修正端点 |
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

## 参考资源

- SKU 序列图
- SKU 数据结构说明

---

*本文档基于乐天RMS官方文档整理*
