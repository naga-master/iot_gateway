# adapters/rest_adapter.py
import aiohttp
import asyncio
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class RestAPIAdapter(CommunicationAdapter):
    """
    Generic REST API communication adapter.
    Handles HTTP operations for sensor data retrieval and configuration.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5

    async def connect(self) -> None:
        for attempt in range(self._retry_count):
            try:
                self.session = aiohttp.ClientSession()
                self.is_connected = True
                logger.info(f"Created REST API session for {self.base_url}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to create REST API session failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def disconnect(self) -> None:
        if self.session:
            try:
                await self.session.close()
                self.is_connected = False
                logger.info(f"Closed REST API session for {self.base_url}")
            except Exception as e:
                logger.error(f"Error closing REST API session: {e}")
                raise

    async def get(self, endpoint: str, params: dict = None) -> dict:
        if not self.is_connected:
            raise RuntimeError("REST API session not created")
            
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        for attempt in range(self._retry_count):
            try:
                async with self.session.get(url, params=params) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to GET from {url} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def post(self, endpoint: str, data: dict) -> dict:
        if not self.is_connected:
            raise RuntimeError("REST API session not created")
            
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        for attempt in range(self._retry_count):
            try:
                async with self.session.post(url, json=data) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to POST to {url} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise