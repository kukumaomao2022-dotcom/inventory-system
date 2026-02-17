import base64
import json
import logging
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RAKUTEN_BASE_URL = "https://api.rms.rakuten.co.jp"


class RakutenAPIError(Exception):
    def __init__(self, message: str, code: int | None = None, response: str | dict | None = None):
        super().__init__(message)
        self.code = code
        self.response = response


class RakutenAPIClient:
    def __init__(self, service_secret: str, license_key: str):
        self.service_secret = service_secret
        self.license_key = license_key
        self._auth_header = self._generate_auth_header()

    def _generate_auth_header(self) -> str:
        auth_str = f"{self.service_secret}:{self.license_key}"
        encoded = base64.b64encode(auth_str.encode()).decode()
        return f"ESA {encoded}"

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": self._auth_header,
            "Content-Type": "application/xml; charset=UTF-8",
            "Accept": "application/xml",
        }

    async def _request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: str | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        retry_count = 0

        while retry_count <= max_retries:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self._get_headers(),
                        params=params,
                        content=data,
                    )

                    if response.status_code == 200:
                        return self._parse_xml_response(response.text)
                    elif response.status_code == 401:
                        raise RakutenAPIError(
                            "License key may be expired",
                            code=401,
                            response=response.text
                        )
                    elif response.status_code == 429:
                        wait_time = 2 ** retry_count
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                        time.sleep(wait_time)
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
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(f"Request failed: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    raise RakutenAPIError(f"Request failed after {max_retries} retries: {e}")

        return {}

    def _parse_xml_response(self, xml_text: str) -> dict[str, Any] | str:
        """Parse XML response to dict. For simplicity, using basic parsing."""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)
            return self._xml_to_dict(root)
        except Exception as e:
            logger.error(f"Failed to parse XML: {e}")
            return {"raw": xml_text}

    def _xml_to_dict(self, element: ET.Element) -> dict[str, Any] | str:
        """Convert XML element to dictionary."""
        result = {}
        if element.text and element.text.strip():
            return element.text.strip()

        for child in element:
            child_data = self._xml_to_dict(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data

        return result

    async def search_order(
        self,
        start_date: str,
        end_date: str,
        order_status: str | None = None,
    ) -> list[str]:
        """Search orders by date range. Returns order numbers."""
        url = urljoin(RAKUTEN_BASE_URL, "/es/1.0/order/searchOrder")

        params = {
            "startDate": start_date,
            "endDate": end_date,
        }
        if order_status:
            params["orderStatus"] = order_status

        response = await self._request("GET", url, params=params)

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
        url = urljoin(RAKUTEN_BASE_URL, "/es/1.0/order/getOrder")

        xml_body = '<?xml version="1.0" encoding="UTF-8"?>'
        xml_body += "<request>"
        for order_num in order_numbers:
            xml_body += f"<orderNumber>{order_num}</orderNumber>"
        xml_body += "</request>"

        response = await self._request("POST", url, data=xml_body)

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
        url = urljoin(RAKUTEN_BASE_URL, "/es/1.0/order/confirmOrder")

        xml_body = '<?xml version="1.0" encoding="UTF-8"?>'
        xml_body += f"<request><orderNumber>{order_number}</orderNumber></request>"

        return await self._request("POST", url, data=xml_body)

    async def set_inventory(
        self,
        sku: str,
        inventory: int,
        inventory_type: str = "0",
    ) -> dict[str, Any]:
        """Update inventory using 在庫API 2.0."""
        url = urljoin(RAKUTEN_BASE_URL, "/es/2.0/inventory/set")

        xml_body = '<?xml version="1.0" encoding="UTF-8"?>'
        xml_body += "<request>"
        xml_body += f"<inventoryInfoList><inventoryInfo>"
        xml_body += f"<sku>{sku}</sku>"
        xml_body += f"<inventory>{inventory}</inventory>"
        xml_body += f"<inventoryType>{inventory_type}</inventoryType>"
        xml_body += "</inventoryInfo></inventoryInfoList>"
        xml_body += "</request>"

        return await self._request("POST", url, data=xml_body)

    async def get_items(
        self,
        limit: int = 100,
        page: int = 1,
    ) -> dict[str, Any]:
        """Get store items using 楽天商品API."""
        url = urljoin(RAKUTEN_BASE_URL, "/es/1.0/item/getItems")

        params = {
            "hits": limit,
            "page": page,
        }

        return await self._request("GET", url, params=params)

    async def test_auth(self) -> tuple[bool, int | None]:
        """Test if credentials are valid. Returns (is_valid, days_remaining)."""
        try:
            url = urljoin(RAKUTEN_BASE_URL, "/es/1.0/order/searchOrder")
            params = {
                "startDate": "2020-01-01T00:00:00",
                "endDate": "2020-01-01T01:00:00",
            }
            response = await self._request("GET", url, params=params, max_retries=1)
            return True, None
        except RakutenAPIError as e:
            if e.code == 401:
                return False, 0
        return False, None


def get_rakuten_client(api_config: dict[str, str]) -> RakutenAPIClient:
    """Create Rakuten API client from store config."""
    service_secret = api_config.get("serviceSecret", settings.RAKUTEN_DEFAULT_SERVICE_SECRET)
    license_key = api_config.get("licenseKey", settings.RAKUTEN_DEFAULT_LICENSE_KEY)

    if not service_secret or not license_key:
        raise ValueError("Missing Rakuten API credentials")

    return RakutenAPIClient(service_secret, license_key)
