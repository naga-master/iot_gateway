import smbus2
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

    async def connect(self) -> None:
        try:
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # self.bus = smbus2.SMBus(self.bus_number)
            self.bus = True
            self.is_connected = True
            logger.info(f"Connected to I2C bus {self.bus_number}")
        except Exception as e:
            logger.error(f"Failed to connect to I2C bus {self.bus_number}: {e}")
            raise

    async def disconnect(self) -> None:
        if self.bus:
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # self.bus.close()
            self.is_connected = False
            logger.info(f"Disconnected from I2C bus {self.bus_number}")

    def read_data(self):
        pass

    def write_data(self, data):
        pass

    async def read_bytes(self, address: int, register: int, num_bytes: int) -> bytes:
        """Read bytes from an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # data = self.bus.read_i2c_block_data(address, register, num_bytes)
            data = "read"
            return bytes(data)
        except Exception as e:
            logger.error(f"Error reading from I2C device 0x{address:02x}: {e}")
            raise

    async def write_bytes(self, address: int, register: int, data: bytes) -> None:
        """Write bytes to an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # self.bus.write_i2c_block_data(address, register, list(data))
            pass
        except Exception as e:
            logger.error(f"Error writing to I2C device 0x{address:02x}: {e}")
            raise

    async def read_byte(self, address: int, register: int) -> int:
        """Read a single byte from an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # return self.bus.read_byte_data(address, register)
            return "read"
        except Exception as e:
            logger.error(f"Error reading from I2C device 0x{address:02x}: {e}")
            raise

    async def write_byte(self, address: int, register: int, value: int) -> None:
        """Write a single byte to an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # self.bus.write_byte_data(address, register, value)
            pass
        except Exception as e:
            logger.error(f"Error writing to I2C device 0x{address:02x}: {e}")
            raise