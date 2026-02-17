import base64
import json
import logging
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RAKUTEN_BASE_URL = "https://api.rms.rakuten.co.jp"

# 乐天图片 URL 基础地址
RAKUTEN_CABINET_IMAGE_BASE = "https://image.rakuten.co.jp"
RAKUTEN_GOLD_IMAGE_BASE = "https://www.rakuten.ne.jp/gold"


class RakutenAPIError(Exception):
    def __init__(self, message: str, code: int | None = None, response: str | dict | None = None):
        super().__init__(message)
        self.code = code
        self.response = response


class RakutenAPIClient:
    def __init__(self, service_secret: str, license_key: str, shop_url: str = None):
        self.service_secret = service_secret
        self.license_key = license_key
        self.shop_url = shop_url
        self._auth_header = self._generate_auth_header()

    def _generate_auth_header(self) -> str:
        auth_str = f"{self.service_secret}:{self.license_key}"
        encoded = base64.b64encode(auth_str.encode()).decode()
        return f"ESA {encoded}"

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": self._auth_header,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                # 使用代理（如果配置了）
                proxy = settings.RAKUTEN_PROXY if settings.RAKUTEN_PROXY else None
                if proxy:
                    logger.info(f"使用代理: {proxy}")

                async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
                    if method == "GET":
                        response = await client.request(
                            method=method,
                            url=url,
                            headers=self._get_headers(),
                            params=params,
                        )
                    else:
                        response = await client.request(
                            method=method,
                            url=url,
                            headers=self._get_headers(),
                            json=data,
                        )

                    if response.status_code == 200:
                        try:
                            return response.json()
                        except:
                            return {"raw": response.text}
                    elif response.status_code == 401:
                        raise RakutenAPIError(
                            "License key may be expired",
                            code=401,
                            response=response.text
                        )
                    elif response.status_code == 429:
                        wait_time = 2 ** retry_count
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                        import asyncio
                        asyncio.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        raise RakutenAPIError(
                            f"API request failed: {response.status_code}",
                            code=response.status_code,
                            response=response.text
                        )

            except RakutenAPIError:
                raise
            except Exception as e:
                last_error = e
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(f"Request failed: {e}, retrying in {wait_time}s")
                    import asyncio
                    asyncio.sleep(wait_time)
                    retry_count += 1
                else:
                    raise RakutenAPIError(f"Request failed after {max_retries} retries: {e}")

        return {}

    async def search_order(
        self,
        start_datetime,
        end_datetime,
        order_status: list | None = None,
    ) -> list[str]:
        """Search orders by date range. Returns order numbers."""
        url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/order/searchOrder/")

        if isinstance(start_datetime, str):
            start_dt = start_datetime
        else:
            start_dt = start_datetime.strftime("%Y-%m-%dT%H:%M:%S+0900")

        if isinstance(end_datetime, str):
            end_dt = end_datetime
        else:
            end_dt = end_datetime.strftime("%Y-%m-%dT%H:%M:%S+0900")

        request_body = {
            "dateType": 1,
            "startDatetime": start_dt,
            "endDatetime": end_dt,
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

        if order_status:
            request_body["orderProgressList"] = order_status

        if self.shop_url:
            request_body["shopUrl"] = self.shop_url

        logger.info(f"Rakuten API: Searching orders with body: {request_body}")
        
        response = await self._request("POST", url, data=request_body)
        
        logger.info(f"Rakuten API: Search response: {response}")

        order_numbers = []
        if "orderNumberList" in response:
            order_list = response["orderNumberList"]
            if isinstance(order_list, dict):
                order_numbers.append(order_list.get("orderNumber", ""))
            elif isinstance(order_list, list):
                for item in order_list:
                    order_numbers.append(item.get("orderNumber", ""))

        return [o for o in order_numbers if o]

    async def get_order(self, order_numbers: list[str]) -> list[dict[str, Any]]:
        """Get order details by order numbers."""
        url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/order/getOrder")

        request_body = {
            "orderNumberList": order_numbers
        }
        
        if self.shop_url:
            request_body["shopUrl"] = self.shop_url

        logger.info(f"Rakuten API: Getting orders: {order_numbers}")
        
        response = await self._request("POST", url, data=request_body)
        
        logger.info(f"Rakuten API: Get order response: {response}")

        orders = []
        if "orderList" in response:
            order_data = response["orderList"]
            if isinstance(order_data, dict):
                orders = [order_data]
            elif isinstance(order_data, list):
                orders = order_data

        return orders

    async def confirm_order(self, order_number: str) -> dict[str, Any]:
        """Confirm an order (status 100 -> 300)."""
        url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/order/confirmOrder")

        request_body = {
            "orderNumber": order_number
        }
        
        if self.shop_url:
            request_body["shopUrl"] = self.shop_url

        return await self._request("POST", url, data=request_body)

    async def set_inventory(
        self,
        sku: str,
        inventory: int,
        inventory_type: str = "0",
    ) -> dict[str, Any]:
        """Update inventory using 在庫API 2.0."""
        url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/inventory/set")

        request_body = {
            "inventoryInfoList": {
                "inventoryInfo": {
                    "sku": sku,
                    "inventory": inventory,
                    "inventoryType": inventory_type
                }
            }
        }
        
        if self.shop_url:
            request_body["shopUrl"] = self.shop_url

        return await self._request("POST", url, data=request_body)

    async def get_items(
        self,
        limit: int = 100,
        page: int = 1,
    ) -> dict[str, Any]:
        """Get store items using 楽天商品API."""
        url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/item/getItems")

        request_body = {
            "hits": limit,
            "page": page,
        }
        
        if self.shop_url:
            request_body["shopUrl"] = self.shop_url

        logger.info(f"Rakuten API: Getting items with body: {request_body}")
        
        try:
            response = await self._request("POST", url, data=request_body)
            logger.info(f"Rakuten API: Items response: {response}")
            return response
        except Exception as e:
            logger.error(f"Rakuten API get_items failed: {e}")
            raise

    async def test_auth(self) -> tuple[bool, int | None]:
        """Test if credentials are valid. Returns (is_valid, days_remaining)."""
        try:
            await self.search_order(
                "2020-01-01T00:00:00",
                "2020-01-01T01:00:00"
            )
            return True, None
        except RakutenAPIError as e:
            if e.code == 401:
                return False, 0
        return False, None

    def build_image_url(self, image_type: str, location: str, shop_url: str | None = None) -> str | None:
        """构建乐天图片完整 URL

        Args:
            image_type: 图片类型（CABINET 或 GOLD）
            location: 图片路径部分（从 API 返回的 location 字段）
            shop_url: 店铺 URL（如果未提供则使用实例的 shop_url）

        Returns:
            完整的图片 URL，如果参数无效则返回 None

        规则：
            CABINET: https://image.rakuten.co.jp/[SHOP_URL]/cabinet/[LOCATION]
            GOLD: https://www.rakuten.ne.jp/gold/[SHOP_URL]/[LOCATION]
        """
        if not image_type or not location:
            return None

        shop = shop_url or self.shop_url
        if not shop:
            return None

        # 去除路径前后的斜杠
        location = location.strip("/")

        if image_type.upper() == "CABINET":
            return f"{RAKUTEN_CABINET_IMAGE_BASE}/{shop}/cabinet/{location}"
        elif image_type.upper() == "GOLD":
            return f"{RAKUTEN_GOLD_IMAGE_BASE}/{shop}/{location}"
        else:
            logger.warning(f"Unknown image type: {image_type}")
            return None

    def extract_main_image(self, item_data: dict[str, Any]) -> str | None:
        """从商品 API 响应中提取主图 URL

        优先级：
        1. images 列表中的第一张图片（通常是主图）
        2. whiteBgImage 中的图片（白背景图，如果存在）

        Args:
            item_data: 商品 API 返回的数据

        Returns:
            主图的完整 URL，如果没有图片则返回 None
        """
        # 优先从 images 列表获取
        images = item_data.get("images", {})
        if images and isinstance(images, dict):
            image_list = images.get("images", [])
            if image_list and isinstance(image_list, list) and len(image_list) > 0:
                first_image = image_list[0]
                if isinstance(first_image, dict):
                    image_type = first_image.get("type")
                    location = first_image.get("location")
                    url = self.build_image_url(image_type, location)
                    if url:
                        return url

        # 其次从 whiteBgImage 获取
        white_bg = item_data.get("whiteBgImage", {})
        if white_bg and isinstance(white_bg, dict):
            image_type = white_bg.get("type")
            location = white_bg.get("location")
            url = self.build_image_url(image_type, location)
            if url:
                return url

        return None

    def extract_all_images(self, item_data: dict[str, Any], max_count: int = 5) -> list[str]:
        """从商品 API 响应中提取所有图片 URL

        Args:
            item_data: 商品 API 返回的数据
            max_count: 最大返回图片数量

        Returns:
            图片 URL 列表（主图在前）
        """
        urls = []

        # 获取主图
        main_image = self.extract_main_image(item_data)
        if main_image:
            urls.append(main_image)

        # 获取其他图片
        images = item_data.get("images", {})
        if images and isinstance(images, dict):
            image_list = images.get("images", [])
            if image_list and isinstance(image_list, list):
                for i, image in enumerate(image_list):
                    if i >= max_count:
                        break
                    # 跳过主图（已经添加过了）
                    if i == 0:
                        continue
                    if isinstance(image, dict):
                        image_type = image.get("type")
                        location = image.get("location")
                        url = self.build_image_url(image_type, location)
                        if url:
                            urls.append(url)

        return urls

    async def get_inventory_range(
        self,
        min_quantity: int = 0,
        max_quantity: int = 10000,
    ) -> dict[str, Any]:
        """Get inventories by quantity range.

        使用库存范围 API 获取 SKU 列表。

        Args:
            min_quantity: 最小库存数量
            max_quantity: 最大库存数量

        Returns:
            API 响应，包含 inventories 数组

        Raises:
            RakutenAPIError: API 调用失败
        """
        url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/inventories/bulk-get/range")
        params = {
            "minQuantity": min_quantity,
            "maxQuantity": max_quantity,
        }

        if self.shop_url:
            params["shopUrl"] = self.shop_url

        logger.info(f"Rakuten API: Getting inventory range {min_quantity}-{max_quantity}")

        try:
            response = await self._request("GET", url, params=params)
            logger.info(f"Rakuten API: Inventory range response: {response}")
            return response
        except Exception as e:
            logger.error(f"Rakuten API get_inventory_range failed: {e}")
            raise

    async def get_item_details(self, manage_number: str) -> dict[str, Any]:
        """Get item details by management number.

        根据商品管理编号获取单个商品详情。

        Args:
            manage_number: 商品管理编号

        Returns:
            商品详情

        Raises:
            RakutenAPIError: API 调用失败
        """
        url = urljoin(RAKUTEN_BASE_URL, f"/es/2.0/items/manage-numbers/{manage_number}")

        logger.info(f"Rakuten API: Getting item details for {manage_number}")

        try:
            response = await self._request("GET", url)
            logger.info(f"Rakuten API: Item details response: {response}")
            return response
        except Exception as e:
            logger.error(f"Rakuten API get_item_details failed: {e}")
            raise


def get_rakuten_client(api_config: dict[str, str]) -> RakutenAPIClient:
    """Create Rakuten API client from store config."""
    service_secret = api_config.get("serviceSecret", settings.RAKUTEN_DEFAULT_SERVICE_SECRET)
    license_key = api_config.get("licenseKey", settings.RAKUTEN_DEFAULT_LICENSE_KEY)
    shop_url = api_config.get("shopUrl", None)

    if not service_secret or not license_key:
        raise ValueError("Missing Rakuten API credentials")

    return RakutenAPIClient(service_secret, license_key, shop_url)
