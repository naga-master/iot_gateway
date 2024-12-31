# adapters/websocket_adapter.py
import websockets
import asyncio
import json
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class WebSocketAdapter(CommunicationAdapter):
    """
    Generic WebSocket communication adapter.
    Handles WebSocket operations for real-time sensor data streaming.
    """
    def __init__(self, url: str):
        self.url = url
        self.ws = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5

    async def connect(self) -> None:
        for attempt in range(self._retry_count):
            try:
                self.ws = await websockets.connect(self.url)
                self.is_connected = True
                logger.info(f"Connected to WebSocket at {self.url}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to connect to WebSocket failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def disconnect(self) -> None:
        if self.ws:
            try:
                await self.ws.close()
                self.is_connected = False
                logger.info(f"Disconnected from WebSocket at {self.url}")
            except Exception as e:
                logger.error(f"Error disconnecting from WebSocket: {e}")
                raise

    async def send_message(self, message: dict) -> None:
        if not self.is_connected:
            raise RuntimeError("WebSocket not connected")
            
        for attempt in range(self._retry_count):
            try:
                await self.ws.send(json.dumps(message))
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to send WebSocket message failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def receive_message(self) -> dict:
        if not self.is_connected:
            raise RuntimeError("WebSocket not connected")
            
        for attempt in range(self._retry_count):
            try:
                message = await self.ws.recv()
                return json.loads(message)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to receive WebSocket message failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise