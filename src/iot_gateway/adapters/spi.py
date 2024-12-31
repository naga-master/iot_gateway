# adapters/spi_adapter.py
import spidev
import asyncio
from typing import List
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class SPIAdapter(CommunicationAdapter):
    """
    Generic SPI communication adapter.
    Handles low-level SPI operations independently of specific sensors.
    """
    def __init__(self, bus: int = 0, device: int = 0):
        self.bus = bus
        self.device = device
        self.spi = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5

    async def connect(self) -> None:
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.spi = spidev.SpiDev()
                # self.spi.open(self.bus, self.device)
                # self.spi.max_speed_hz = 1000000
                self.is_connected = True
                logger.info(f"Connected to SPI bus {self.bus}, device {self.device}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to connect to SPI device failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def disconnect(self) -> None:
        if self.spi:
            try:
                self.spi.close()
                self.is_connected = False
                logger.info(f"Disconnected from SPI bus {self.bus}")
            except Exception as e:
                logger.error(f"Error disconnecting from SPI: {e}")
                raise

    async def transfer(self, data: List[int]) -> List[int]:
        if not self.is_connected:
            raise RuntimeError("SPI not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # return self.spi.xfer2(data)
                return [0] * len(data)  # Dummy data
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to transfer SPI data failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise