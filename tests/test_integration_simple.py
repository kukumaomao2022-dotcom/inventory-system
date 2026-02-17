"""
简单的集成测试，使用内存数据库和事务回滚
"""
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.services.sku_sync import SkuSyncService
from app.db.models import Store
from app.db.database import Base


@pytest.fixture
async def integration_test_db():
    """创建内存数据库用于集成测试"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_sku_sync_integration(integration_test_db):
    """简单的SKU同步集成测试"""
    async with integration_test_db as session:
        await session.begin()

        try:
            # 创建测试店铺
            store = Store(
                store_id="test_store_001",
                store_name="Test Store",
                platform_type="rakuten",
                api_config={
                    "service_secret": "test_secret",
                    "license_key": "test_key"
                },
                status="active"
            )
            session.add(store)
            await session.flush()

            # 创建服务
            service = SkuSyncService(session)

            # 模拟API响应
            mock_response = {
                "itemList": {
                    "item": [
                        {
                            "skuNumber": "TEST-SKU-001",
                            "itemName": "Test Product 1",
                            "itemUrl": "https://example.com/test1"
                        }
                    ]
                },
                "pageCount": 1
            }

            with patch('app.services.sku_sync.get_rakuten_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get_items = AsyncMock(return_value=mock_response)
                mock_get_client.return_value = mock_client

                # 执行同步
                result = await service.sync_store_skus("test_store_001")

                # 验证结果
                assert result["synced"] == 1
                assert len(result["errors"]) == 0

                # 验证数据库状态
                sku_result = await session.execute(
                    text("SELECT sku_id FROM sku_master WHERE sku_id = 'test-sku-001'")
                )
                sku = sku_result.scalar()
                assert sku == "test-sku-001"

                store_sku_result = await session.execute(
                    text("SELECT store_id FROM store_sku WHERE store_id = 'test_store_001' AND sku_id = 'test-sku-001'")
                )
                store_sku = store_sku_result.scalar()
                assert store_sku == "test_store_001"

        finally:
            # 回滚事务，不保存更改
            await session.rollback()


@pytest.mark.asyncio
async def test_sku_normalization_integration(integration_test_db):
    """测试SKU规范化"""
    async with integration_test_db as session:
        await session.begin()

        try:
            store = Store(
                store_id="test_store_002",
                store_name="Test Store 2",
                platform_type="rakuten",
                api_config={
                    "service_secret": "test_secret",
                    "license_key": "test_key"
                },
                status="active"
            )
            session.add(store)
            await session.flush()

            service = SkuSyncService(session)

            mock_response = {
                "itemList": {
                    "item": [
                        {
                            "skuNumber": "  MIXED-CASE-SKU  ",
                            "itemName": "Mixed Case Product",
                            "itemUrl": "https://example.com/mixed"
                        }
                    ]
                },
                "pageCount": 1
            }

            with patch('app.services.sku_sync.get_rakuten_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get_items = AsyncMock(return_value=mock_response)
                mock_get_client.return_value = mock_client

                result = await service.sync_store_skus("test_store_002")
                assert result["synced"] == 1

                sku_result = await session.execute(
                    text("SELECT sku_id FROM sku_master WHERE sku_id = 'mixed-case-sku'")
                )
                sku = sku_result.scalar()
                assert sku == "mixed-case-sku"

        finally:
            await session.rollback()
