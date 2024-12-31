import smbus2
import asyncio
from typing import List
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class I2CAdapter(CommunicationAdapter):
    """
    Generic I2C communication adapter.
    Handles low-level I2C operations independently of specific sensors.
    """
    def __init__(self, bus_number: int):
        self.bus_number = bus_number
        self.bus = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5  # seconds

    async def connect(self) -> None:
        """Connect to I2C bus with retry mechanism"""
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.bus = smbus2.SMBus(self.bus_number)
                self.is_connected = True
                logger.info(f"Connected to I2C bus {self.bus_number}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to connect to I2C bus {self.bus_number} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to connect to I2C bus {self.bus_number} after {self._retry_count} attempts")
                    raise

    async def disconnect(self) -> None:
        """Safely disconnect from I2C bus"""
        if self.bus:
            try:
                self.bus.close()
                self.is_connected = False
                logger.info(f"Disconnected from I2C bus {self.bus_number}")
            except Exception as e:
                logger.error(f"Error disconnecting from I2C bus {self.bus_number}: {e}")
                raise

    async def read_bytes(self, address: int, register: int, num_bytes: int) -> bytes:
        """Read bytes from an I2C device with retry mechanism"""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # data = self.bus.read_i2c_block_data(address, register, num_bytes)
                data = f"dummy {attempt + 1}/{self._retry_count}"
                return bytes(data)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to read from I2C device 0x{address:02x} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to read from I2C device 0x{address:02x} after {self._retry_count} attempts")
                    raise

    async def write_bytes(self, address: int, register: int, data: bytes) -> None:
        """Write bytes to an I2C device with retry mechanism"""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.bus.write_i2c_block_data(address, register, list(data))
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to write to I2C device 0x{address:02x} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to write to I2C device 0x{address:02x} after {self._retry_count} attempts")
                    raise

    async def read_byte(self, address: int, register: int) -> int:
        """Read a single byte from an I2C device with retry mechanism"""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                return self.bus.read_byte_data(address, register)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to read byte from I2C device 0x{address:02x} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to read byte from I2C device 0x{address:02x} after {self._retry_count} attempts")
                    raise

    async def write_byte(self, address: int, register: int, value: int) -> None:
        """Write a single byte to an I2C device with retry mechanism"""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.bus.write_byte_data(address, register, value)
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to write byte to I2C device 0x{address:02x} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to write byte to I2C device 0x{address:02x} after {self._retry_count} attempts")
                    raise

    def read_data(self):
        pass

    def write_data(self, data):
        pass
            