# src/iot_gateway/adapters/i2c.py
from typing import Dict, Any
import smbus2
from .base import BaseAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class I2CAdapter(BaseAdapter):
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
            self.bus = smbus2.SMBus(self.bus_number)
            self.is_connected = True
            logger.info(f"Connected to I2C bus {self.bus_number}")
        except Exception as e:
            logger.error(f"Failed to connect to I2C bus {self.bus_number}: {e}")
            raise

    async def disconnect(self) -> None:
        if self.bus:
            self.bus.close()
            self.is_connected = False
            logger.info(f"Disconnected from I2C bus {self.bus_number}")

    async def read_bytes(self, address: int, register: int, num_bytes: int) -> bytes:
        """Read bytes from an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            data = self.bus.read_i2c_block_data(address, register, num_bytes)
            return bytes(data)
        except Exception as e:
            logger.error(f"Error reading from I2C device 0x{address:02x}: {e}")
            raise

    async def write_bytes(self, address: int, register: int, data: bytes) -> None:
        """Write bytes to an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            self.bus.write_i2c_block_data(address, register, list(data))
        except Exception as e:
            logger.error(f"Error writing to I2C device 0x{address:02x}: {e}")
            raise

    async def read_byte(self, address: int, register: int) -> int:
        """Read a single byte from an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            return self.bus.read_byte_data(address, register)
        except Exception as e:
            logger.error(f"Error reading from I2C device 0x{address:02x}: {e}")
            raise

    async def write_byte(self, address: int, register: int, value: int) -> None:
        """Write a single byte to an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            self.bus.write_byte_data(address, register, value)
        except Exception as e:
            logger.error(f"Error writing to I2C device 0x{address:02x}: {e}")
            raise

# src/iot_gateway/sensors/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from ..adapters.i2c import I2CAdapter

class I2CSensor(ABC):
    """
    Base class for all I2C sensors.
    Each sensor type should implement this interface.
    """
    def __init__(self, i2c_adapter: I2CAdapter, address: int, sensor_id: str):
        self.i2c = i2c_adapter
        self.address = address
        self.sensor_id = sensor_id

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the sensor with required settings."""
        pass

    @abstractmethod
    async def read_data(self) -> Dict[str, Any]:
        """Read and return processed sensor data."""
        pass

    @abstractmethod
    async def get_config(self) -> Dict[str, Any]:
        """Get current sensor configuration."""
        pass

# src/iot_gateway/sensors/temperature.py
from typing import Dict, Any
from .base import I2CSensor
from ..utils.logging import get_logger

logger = get_logger(__name__)

class TMP102Sensor(I2CSensor):
    """
    Implementation for TMP102 temperature sensor.
    """
    # TMP102 registers
    TEMP_REGISTER = 0x00
    CONFIG_REGISTER = 0x01
    
    async def initialize(self) -> None:
        """Initialize TMP102 sensor with default settings."""
        try:
            # Set 12-bit resolution
            await self.i2c.write_byte(self.address, self.CONFIG_REGISTER, 0x60)
            logger.info(f"Initialized TMP102 sensor {self.sensor_id}")
        except Exception as e:
            logger.error(f"Failed to initialize TMP102 sensor {self.sensor_id}: {e}")
            raise

    async def read_data(self) -> Dict[str, Any]:
        """Read and convert temperature data."""
        try:
            # Read temperature register
            data = await self.i2c.read_bytes(self.address, self.TEMP_REGISTER, 2)
            
            # Convert to temperature
            temp_c = ((data[0] << 8) | data[1]) / 256.0
            temp_f = (temp_c * 9/5) + 32
            
            logger.debug(f"Sensor {self.sensor_id} read: {temp_c}°C / {temp_f}°F")
            return {
                "sensor_id": self.sensor_id,
                "celsius": round(temp_c, 2),
                "fahrenheit": round(temp_f, 2)
            }
        except Exception as e:
            logger.error(f"Error reading TMP102 sensor {self.sensor_id}: {e}")
            raise

    async def get_config(self) -> Dict[str, Any]:
        """Get current sensor configuration."""
        config = await self.i2c.read_byte(self.address, self.CONFIG_REGISTER)
        return {
            "sensor_id": self.sensor_id,
            "resolution": "12-bit" if config & 0x60 else "13-bit",
            "address": self.address
        }

# Example of how to create another sensor type
class SHT31Sensor(I2CSensor):
    """
    Implementation for SHT31 temperature and humidity sensor.
    """
    # SHT31 registers and commands
    MEASURE_HIGH_REP = bytes([0x24, 0x00])
    
    async def initialize(self) -> None:
        # Implementation for SHT31
        pass

    async def read_data(self) -> Dict[str, Any]:
        # Implementation for SHT31
        pass

    async def get_config(self) -> Dict[str, Any]:
        # Implementation for SHT31
        pass

# Modified temperature monitor to use the new structure
# src/iot_gateway/core/temperature_monitor.py
class TemperatureMonitor:
    def __init__(self, config: Dict[str, Any], event_manager):
        self.config = config
        self.event_manager = event_manager
        self.i2c_adapter = None
        self.sensors = []

    async def initialize(self) -> None:
        # Initialize I2C adapter
        self.i2c_adapter = I2CAdapter(self.config['i2c_bus'])
        await self.i2c_adapter.connect()

        # Initialize sensors
        for sensor_config in self.config['sensors']:
            sensor_class = self._get_sensor_class(sensor_config['type'])
            sensor = sensor_class(
                self.i2c_adapter,
                sensor_config['address'],
                sensor_config['id']
            )
            await sensor.initialize()
            self.sensors.append(sensor)

    def _get_sensor_class(self, sensor_type: str) -> type:
        """Get sensor class based on type."""
        sensor_classes = {
            'TMP102': TMP102Sensor,
            'SHT31': SHT31Sensor,
            # Add more sensor types here
        }
        return sensor_classes.get(sensor_type)

# Example configuration
config_example = """
temperature_monitor:
  i2c_bus: 1
  sensors:
    - id: "temp1"
      type: "TMP102"
      address: 0x48
    - id: "temp2"
      type: "SHT31"
      address: 0x44
"""
