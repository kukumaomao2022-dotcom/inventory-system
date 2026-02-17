#!/bin/bash
echo "1. 启动应用..."
timeout 10 uvicorn app.main:app --host 0.0.0.0 --port 8004 > /dev/null 2>&1 &
APP_PID=$!
sleep 3

echo "2. 测试健康检查..."
curl -s http://localhost:8004/health | python3 -m json.tool

echo "3. 查看店铺列表..."
curl -s http://localhost:8004/api/stores | python3 -m json.tool

echo "4. 创建测试店铺..."
curl -s -X POST http://localhost:8004/api/stores \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": "test-store-001",
    "store_name": "测试店铺",
    "platform_type": "rakuten",
    "api_config": {
      "service_secret": "test_secret",
      "license_key": "test_key"
    },
    "status": "active"
  }' | python3 -m json.tool

echo "5. 触发SKU同步..."
curl -s -X POST http://localhost:8004/api/stores/test-store-001/sync-skus | python3 -m json.tool

echo "6. 获取同步状态..."
curl -s http://localhost:8004/api/stores/test-store-001/sku-sync-status | python3 -m json.tool

kill $APP_PID 2>/dev/null
