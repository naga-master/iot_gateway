from typing import Dict, Any
from ..adapters.base import I2CSensor
from ..utils.logging import get_logger
import traceback
from ..utils.helpers import generate_msg_id

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
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # await self.i2c.write_byte(self.address, self.CONFIG_REGISTER, 0x60)

            logger.info(f"Initialized TMP102 sensor {self.sensor_id}")
        except Exception as e:
            logger.error(f"Failed to initialize TMP102 sensor {self.sensor_id}: {traceback.format_exc()}")
            raise

    async def read_data(self) -> Dict[str, Any]:
        """Read and convert temperature data."""
        try:
            # Read temperature register
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # data = await self.i2c.read_bytes(self.address, self.TEMP_REGISTER, 2)

            data = "Hello".encode("UTF-8")
            
            # Convert to temperature
            temp_c = ((data[0] << 8) | data[1]) / 256.0
            temp_f = (temp_c * 9/5) + 32
            
            logger.debug(f"Sensor {self.sensor_id} read: {temp_c}°C / {temp_f}°F")
            return {
                "device_id": self.sensor_id,
                "celsius": round(temp_c, 2),
                "fahrenheit": round(temp_f, 2),
                "reading_id": generate_msg_id(self.sensor_id)
            }
        except Exception as e:
            logger.error(f"Error reading TMP102 sensor {self.sensor_id}: {traceback.format_exc()}")
            raise

    async def get_config(self) -> Dict[str, Any]:
        """Get current sensor configuration."""
        ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
        # config = await self.i2c.read_byte(self.address, self.CONFIG_REGISTER)

        config = True
        return {
            "device_id": self.sensor_id,
            "resolution": "12-bit" if config & 0x60 else "13-bit",
            "address": self.address
        }
    

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
        # Read temperature register
        ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
        # data = await self.i2c.read_bytes(self.address, self.TEMP_REGISTER, 2)

        data = "sensor2".encode("UTF-8")
        
        # Convert to temperature
        temp_c = ((data[0] << 8) | data[1]) / 256.0
        temp_f = (temp_c * 9/5) + 32
        
        logger.debug(f"Sensor {self.sensor_id} read: {temp_c}°C / {temp_f}°F")
        return {
                "device_id": self.sensor_id,
                "celsius": round(temp_c, 2),
                "fahrenheit": round(temp_f, 2),
                "reading_id": generate_msg_id(self.sensor_id)
            }

    async def get_config(self) -> Dict[str, Any]:
        # Implementation for SHT31
        pass
