#!/bin/bash
echo "1. 启动应用..."
timeout 10 uvicorn app.main:app --host 0.0.0.0 --port 8005 > /dev/null 2>&1 &
APP_PID=$!
sleep 3

echo "2. 触发coucou-doma店铺的SKU同步..."
curl -s -X POST http://localhost:8005/api/stores/coucou-doma/sync-skus | python3 -m json.tool

echo "3. 获取同步状态..."
curl -s http://localhost:8005/api/stores/coucou-doma/sku-sync-status | python3 -m json.tool

echo "4. 查看同步的SKU..."
curl -s "http://localhost:8005/api/skus?store_id=coucou-doma" | python3 -m json.tool

kill $APP_PID 2>/dev/null
