import asyncio
import httpx
import base64
import json
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_rakuten_api_direct():
    """直接测试乐天API，绕过客户端"""
    
    service_secret = "SP416502_ub7B0vRTK9VuHjsL"
    license_key = "SL416502_YuXi3naks7oilYtI"
    shop_url = "coucou-doma.rakuten.co.jp"
    
    # 创建认证头
    auth_string = f"{service_secret}:{license_key}"
    auth_b64 = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        "Authorization": f"ESA {auth_b64}",
        "Content-Type": "application/json; charset=utf-8",
    }
    
    # 测试不同的API端点
    base_url = "https://api.rms.rakuten.co.jp"
    endpoints = [
        ("/es/1.0/", "API版本1.0根目录"),
        ("/es/2.0/", "API版本2.0根目录"),
        ("/es/2.0/item/getItems", "获取商品列表"),
        ("/es/2.0/order/searchOrder/", "搜索订单"),
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint, description in endpoints:
            print(f"\n测试: {description}")
            print(f"URL: {base_url}{endpoint}")
            
            try:
                # 对于GET端点
                if endpoint.endswith("/"):
                    response = await client.get(
                        f"{base_url}{endpoint}",
                        headers=headers
                    )
                # 对于POST端点
                else:
                    request_body = {}
                    if "getItems" in endpoint:
                        request_body = {"hits": 10, "page": 1}
                        if shop_url:
                            request_body["shopUrl"] = shop_url
                    elif "searchOrder" in endpoint:
                        request_body = {
                            "dateType": 1,
                            "startDatetime": "2025-01-01T00:00:00",
                            "endDatetime": "2025-01-02T00:00:00",
                            "PaginationRequestModel": {
                                "requestRecordsAmount": 10,
                                "requestPage": 1,
                                "sortModelList": [{"sortColumn": 1, "sortDirection": 2}]
                            }
                        }
                        if shop_url:
                            request_body["shopUrl"] = shop_url
                    
                    response = await client.post(
                        f"{base_url}{endpoint}",
                        headers=headers,
                        json=request_body
                    )
                
                print(f"状态码: {response.status_code}")
                print(f"响应头: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"✅ 成功: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
                    except:
                        print(f"响应文本: {response.text[:500]}...")
                else:
                    print(f"❌ 错误: {response.text[:500]}...")
                    
            except Exception as e:
                print(f"❌ 请求失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_rakuten_api_direct())
