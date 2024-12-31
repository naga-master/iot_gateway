import asyncio
from bleak import BleakClient
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class BluetoothAdapter(CommunicationAdapter):
    """
    Generic Bluetooth Low Energy (BLE) communication adapter.
    Handles BLE operations for sensor communication.
    """
    def __init__(self, address: str):
        self.address = address
        self.client = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5

    async def connect(self) -> None:
        for attempt in range(self._retry_count):
            try:
                self.client = BleakClient(self.address)
                await self.client.connect()
                self.is_connected = True
                logger.info(f"Connected to BLE device at {self.address}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to connect to BLE device failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def disconnect(self) -> None:
        if self.client:
            try:
                await self.client.disconnect()
                self.is_connected = False
                logger.info(f"Disconnected from BLE device at {self.address}")
            except Exception as e:
                logger.error(f"Error disconnecting from BLE device: {e}")
                raise

    async def read_characteristic(self, uuid: str) -> bytes:
        if not self.is_connected:
            raise RuntimeError("BLE device not connected")
            
        for attempt in range(self._retry_count):
            try:
                return await self.client.read_gatt_char(uuid)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to read BLE characteristic failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def write_characteristic(self, uuid: str, data: bytes) -> None:
        if not self.is_connected:
            raise RuntimeError("BLE device not connected")
            
        for attempt in range(self._retry_count):
            try:
                await self.client.write_gatt_char(uuid, data)
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to write BLE characteristic failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise