#!/bin/bash
echo "=== 测试模拟模式SKU同步API ==="

echo "1. 启动应用..."
timeout 10 uvicorn app.main:app --host 0.0.0.0 --port 8006 > /dev/null 2>&1 &
APP_PID=$!
sleep 3

echo "2. 创建测试店铺..."
curl -s -X POST http://localhost:8006/api/stores \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": "mock-api-store",
    "store_name": "模拟API测试店铺",
    "platform_type": "rakuten",
    "api_config": {
      "serviceSecret": "mock_secret",
      "licenseKey": "mock_key",
      "shopUrl": "mock-shop.rakuten.co.jp"
    },
    "status": "active"
  }' | python3 -m json.tool

echo -e "\n3. 触发SKU同步（模拟模式）..."
curl -s -X POST http://localhost:8006/api/stores/mock-api-store/sync-skus | python3 -m json.tool

echo -e "\n4. 获取同步状态..."
curl -s http://localhost:8006/api/stores/mock-api-store/sku-sync-status | python3 -m json.tool

echo -e "\n5. 查看同步的SKU..."
curl -s "http://localhost:8006/api/skus?store_id=mock-api-store" | python3 -m json.tool

echo -e "\n6. 查看所有SKU..."
curl -s "http://localhost:8006/api/skus" | python3 -m json.tool | head -50

kill $APP_PID 2>/dev/null
