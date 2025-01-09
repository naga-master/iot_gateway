from ..utils.logging import get_logger
from ..adapters.base import ModbusSensor
from typing import Dict, Any
from ..utils.helpers import generate_msg_id

logger = get_logger(__name__)

# Example Modbus RTU Sensor Implementation
class FlowMeter(ModbusSensor):
    """
    Implementation for a Modbus RTU flow meter sensor.
    """
    # Register addresses
    FLOW_RATE_REGISTER = 0x1000
    TOTAL_FLOW_REGISTER = 0x1002
    STATUS_REGISTER = 0x1004

    async def initialize(self) -> None:
        """Initialize flow meter."""
        try:
            # Read status register to verify communication
            status = await self.modbus.read_register(self.STATUS_REGISTER)
            if status != 0:
                raise RuntimeError(f"Flow meter initialization failed: status = {status}")
            logger.info(f"Initialized flow meter {self.sensor_id}")
        except Exception as e:
            logger.error(f"Failed to initialize flow meter {self.sensor_id}: {str(e)}")
            raise

    async def read_data(self) -> Dict[str, Any]:
        """Read flow meter data."""
        try:
            # Read flow rate (with 2 decimal places)
            flow_rate = await self.modbus.read_register(
                self.FLOW_RATE_REGISTER, 
                number_of_decimals=2
            )
            
            # Read total flow (with 3 decimal places)
            total_flow = await self.modbus.read_register(
                self.TOTAL_FLOW_REGISTER, 
                number_of_decimals=3
            )
            
            return {
                "device_id": self.sensor_id,
                "flow_rate_lpm": round(flow_rate, 2),
                "total_flow_l": round(total_flow, 3),
                "reading_id": generate_msg_id(self.sensor_id)
            }
        except Exception as e:
            logger.error(f"Error reading flow meter {self.sensor_id}: {str(e)}")
            raise

    async def reset_total(self) -> None:
        """Reset total flow counter."""
        try:
            await self.modbus.write_register(self.TOTAL_FLOW_REGISTER, 0)
            logger.info(f"Reset total flow counter for sensor {self.sensor_id}")
        except Exception as e:
            logger.error(f"Error resetting flow meter {self.sensor_id}: {str(e)}")
            raise