# adapters/uart_adapter.py
import serial
import asyncio
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class UARTAdapter(CommunicationAdapter):
    """
    Generic UART communication adapter.
    Handles low-level UART operations independently of specific sensors.
    """
    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5

    async def connect(self) -> None:
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.serial = serial.Serial(
                #     port=self.port,
                #     baudrate=self.baudrate,
                #     timeout=1
                # )
                self.is_connected = True
                logger.info(f"Connected to UART port {self.port}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to connect to UART failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def disconnect(self) -> None:
        if self.serial:
            try:
                self.serial.close()
                self.is_connected = False
                logger.info(f"Disconnected from UART port {self.port}")
            except Exception as e:
                logger.error(f"Error disconnecting from UART: {e}")
                raise

    async def read_data(self, size: int = 1) -> bytes:
        if not self.is_connected:
            raise RuntimeError("UART not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # return self.serial.read(size)
                return b'dummy'
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to read UART data failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def write_data(self, data: bytes) -> None:
        if not self.is_connected:
            raise RuntimeError("UART not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.serial.write(data)
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to write UART data failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise