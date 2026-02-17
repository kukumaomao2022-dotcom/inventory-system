import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import json

from app.services.sku_sync import SkuSyncService
from app.db.models import Store, SkuMaster, StoreSku
from app.services.rakuten_api import RakutenAPIError


class TestSkuSyncService:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_store(self):
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
        return store

    @pytest.fixture
    def mock_rakuten_response(self):
        return {
            "itemList": {
                "item": [
                    {
                        "skuNumber": "SKU-001",
                        "itemName": "Test Product 1",
                        "itemUrl": "https://example.com/item1",
                        "imageUrl": "https://example.com/image1.jpg",
                        "itemManagementNumber": "MAN-001"
                    },
                    {
                        "skuNumber": "SKU-002",
                        "itemName": "Test Product 2",
                        "itemUrl": "https://example.com/item2",
                        "imageUrl": "https://example.com/image2.jpg"
                    },
                    {
                        "itemManagementNumber": "MAN-003",
                        "itemName": "Test Product 3",
                        "itemUrl": "https://example.com/item3"
                    }
                ]
            },
            "pageCount": 1
        }

    @pytest.mark.asyncio
    async def test_sync_store_skus_success(self, mock_session, mock_store, mock_rakuten_response):
        service = SkuSyncService(mock_session)
        
        call_count = 0
        
        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            mock_result = AsyncMock()
            
            if call_count == 0:
                mock_result.scalar_one_or_none = MagicMock(return_value=mock_store)
            elif call_count % 2 == 1:
                mock_result.scalar_one_or_none = MagicMock(return_value=None)
            else:
                mock_result.scalar_one_or_none = MagicMock(return_value=None)
            
            call_count += 1
            return mock_result
        
        mock_session.execute.side_effect = mock_execute_side_effect
        
        with patch('app.services.sku_sync.get_rakuten_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_items = AsyncMock(return_value=mock_rakuten_response)
            mock_get_client.return_value = mock_client
            
            result = await service.sync_store_skus("test_store_001")
            
            assert result["synced"] == 3
            assert len(result["errors"]) == 0
            assert "last_sync_at" in result
            
            mock_session.commit.assert_called_once()
            
            sku_calls = []
            for call in mock_session.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, SkuMaster):
                    sku_calls.append(obj.sku_id)
                elif isinstance(obj, StoreSku):
                    sku_calls.append(f"store_sku:{obj.sku_id}")
            
            assert "sku-001" in sku_calls
            assert "sku-002" in sku_calls
            assert "man-003" in sku_calls

    @pytest.mark.asyncio
    async def test_sync_store_skus_store_not_found(self, mock_session):
        service = SkuSyncService(mock_session)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result
        
        result = await service.sync_store_skus("non_existent_store")
        
        assert result["error"] == "Store not found"
        assert result["synced"] == 0

    @pytest.mark.asyncio
    async def test_sync_store_skus_no_api_config(self, mock_session, mock_store):
        service = SkuSyncService(mock_session)
        
        mock_store.api_config = None
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_store)
        mock_session.execute.return_value = mock_result
        
        result = await service.sync_store_skus("test_store_001")
        
        assert result["error"] == "Store has no API config"
        assert result["synced"] == 0

    @pytest.mark.asyncio
    async def test_sync_store_skus_api_error(self, mock_session, mock_store):
        service = SkuSyncService(mock_session)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_store)
        mock_session.execute.return_value = mock_result
        
        with patch('app.services.sku_sync.get_rakuten_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_items = AsyncMock(side_effect=RakutenAPIError("API Error"))
            mock_get_client.return_value = mock_client
            
            result = await service.sync_store_skus("test_store_001")
            
            assert "error" in result
            assert result["synced"] == 0

    @pytest.mark.asyncio
    async def test_sync_store_skus_empty_items(self, mock_session, mock_store):
        service = SkuSyncService(mock_session)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_store)
        mock_session.execute.return_value = mock_result
        
        with patch('app.services.sku_sync.get_rakuten_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_items = AsyncMock(return_value={"itemList": {"item": []}, "pageCount": 1})
            mock_get_client.return_value = mock_client
            
            result = await service.sync_store_skus("test_store_001")
            
            assert result["synced"] == 0
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_sync_store_skus_multiple_pages(self, mock_session, mock_store):
        service = SkuSyncService(mock_session)
        
        call_count = 0
        
        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            mock_result = AsyncMock()
            
            if call_count == 0:
                mock_result.scalar_one_or_none = MagicMock(return_value=mock_store)
            else:
                mock_result.scalar_one_or_none = MagicMock(return_value=None)
            
            call_count += 1
            return mock_result
        
        mock_session.execute.side_effect = mock_execute_side_effect
        
        with patch('app.services.sku_sync.get_rakuten_client') as mock_get_client:
            mock_client = AsyncMock()
            
            def mock_get_items(limit=100, page=1):
                if page == 1:
                    return {
                        "itemList": {
                            "item": [
                                {"skuNumber": f"SKU-{i}", "itemName": f"Product {i}"}
                                for i in range(1, 101)
                            ]
                        },
                        "pageCount": 2
                    }
                else:
                    return {
                        "itemList": {
                            "item": [
                                {"skuNumber": "SKU-101", "itemName": "Product 101"}
                            ]
                        },
                        "pageCount": 2
                    }
            
            mock_client.get_items = AsyncMock(side_effect=mock_get_items)
            mock_get_client.return_value = mock_client
            
            result = await service.sync_store_skus("test_store_001")
            
            assert result["synced"] == 101

    @pytest.mark.asyncio
    async def test_process_item_new_sku(self, mock_session):
        service = SkuSyncService(mock_session)
        
        item = {
            "skuNumber": "NEW-SKU-001",
            "itemName": "New Test Product",
            "itemUrl": "https://example.com/new",
            "imageUrl": "https://example.com/new.jpg"
        }
        
        mock_result1 = AsyncMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=None)
        
        mock_result2 = AsyncMock()
        mock_result2.scalar_one_or_none = MagicMock(return_value=None)
        
        mock_session.execute.side_effect = [mock_result1, mock_result2]
        
        await service._process_item(item, "test_store_001")
        
        sku_add_calls = [call for call in mock_session.add.call_args_list 
                         if isinstance(call[0][0], SkuMaster)]
        store_sku_add_calls = [call for call in mock_session.add.call_args_list 
                               if isinstance(call[0][0], StoreSku)]
        
        assert len(sku_add_calls) == 1
        assert len(store_sku_add_calls) == 1
        
        added_sku = sku_add_calls[0][0][0]
        assert added_sku.sku_id == "new-sku-001"
        assert added_sku.sku_name == "New Test Product"
        assert added_sku.environment == "prod"
        assert added_sku.status == "active"
        
        added_store_sku = store_sku_add_calls[0][0][0]
        assert added_store_sku.sku_id == "new-sku-001"
        assert added_store_sku.store_id == "test_store_001"

    @pytest.mark.asyncio
    async def test_process_item_existing_sku(self, mock_session):
        service = SkuSyncService(mock_session)
        
        item = {
            "skuNumber": "EXISTING-SKU",
            "itemName": "Updated Product Name",
            "itemUrl": "https://example.com/updated"
        }
        
        existing_sku = SkuMaster(
            sku_id="existing-sku",
            original_sku="EXISTING-SKU",
            sku_name="Old Product Name",
            environment="prod",
            status="active",
            extra_data={"item_name": "Old Product Name", "item_url": "https://example.com/old"}
        )
        
        mock_result1 = AsyncMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=existing_sku)
        
        mock_result2 = AsyncMock()
        mock_result2.scalar_one_or_none = MagicMock(return_value=None)
        
        mock_session.execute.side_effect = [mock_result1, mock_result2]
        
        await service._process_item(item, "test_store_001")
        
        assert existing_sku.extra_data["item_name"] == "Updated Product Name"
        assert existing_sku.extra_data["item_url"] == "https://example.com/updated"
        assert "previous_item_name" in existing_sku.extra_data
        assert existing_sku.extra_data["previous_item_name"] == "Old Product Name"

    @pytest.mark.asyncio
    async def test_process_item_no_sku_number(self, mock_session):
        service = SkuSyncService(mock_session)
        
        item = {
            "itemName": "Product Without SKU",
            "itemUrl": "https://example.com/no-sku"
        }
        
        await service._process_item(item, "test_store_001")
        
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_sync_status_store_found(self, mock_session, mock_store):
        service = SkuSyncService(mock_session)
        
        mock_store.last_sku_sync_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_store)
        mock_session.execute.return_value = mock_result
        
        result = await service.get_sync_status("test_store_001")
        
        assert "error" not in result
        assert result["last_sync_at"] == "2024-01-01T12:00:00+00:00"
        assert result["is_syncing"] is False
        assert result["progress"] is None
        assert result["last_error"] is None

    @pytest.mark.asyncio
    async def test_get_sync_status_store_not_found(self, mock_session):
        service = SkuSyncService(mock_session)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result
        
        result = await service.get_sync_status("non_existent_store")
        
        assert result["error"] == "Store not found"

    @pytest.mark.asyncio
    async def test_process_item_with_metadata(self, mock_session):
        service = SkuSyncService(mock_session)
        
        item = {
            "skuNumber": "META-SKU-001",
            "itemName": "Product with Metadata",
            "itemUrl": "https://example.com/meta",
            "imageUrl": "https://example.com/meta.jpg",
            "price": 1000,
            "category": "Electronics",
            "customField": "Custom Value"
        }
        
        mock_result1 = AsyncMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=None)
        
        mock_result2 = AsyncMock()
        mock_result2.scalar_one_or_none = MagicMock(return_value=None)
        
        mock_session.execute.side_effect = [mock_result1, mock_result2]
        
        await service._process_item(item, "test_store_001")
        
        sku_add_calls = [call for call in mock_session.add.call_args_list 
                         if isinstance(call[0][0], SkuMaster)]
        
        assert len(sku_add_calls) == 1
        added_sku = sku_add_calls[0][0][0]
        
        assert "original_data" in added_sku.extra_data
        original_data = added_sku.extra_data["original_data"]
        assert original_data["price"] == 1000
        assert original_data["category"] == "Electronics"
        assert original_data["customField"] == "Custom Value"

    def test_sku_normalization_in_sync(self):
        from app.utils.helpers import normalize_sku
        
        test_cases = [
            ("SKU-001", "sku-001"),
            ("  SKU-002  ", "sku-002"),
            ("sku-003", "sku-003"),
            ("SKU_004", "sku_004"),
            ("", ""),
            (None, ""),
            ("MixedCase-SKU", "mixedcase-sku"),
        ]
        
        for input_sku, expected in test_cases:
            assert normalize_sku(input_sku) == expected