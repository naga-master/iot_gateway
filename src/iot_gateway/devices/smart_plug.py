from iot_gateway.adapters.base import BaseDevice
from iot_gateway.models.device import CommandType, CommandStatus
from typing import Dict, Any, Optional
from iot_gateway.utils.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)

class SmartPlug(BaseDevice):
    """Implementation for smart plug devices"""
    def __init__(self, device_id: str, config: Dict[str, Any], gpio_adapter):
        super().__init__(device_id, config)
        self.gpio_adapter = gpio_adapter
        self.pin = config['pin']
        self.state = {
            "power": False,
            "power_consumption": 0.0,
            "voltage": 0.0
        }

    async def initialize(self) -> None:
        self.state["power"] = self.config.get("initial", False)
        logger.info(f"Initialized smart plug {self.device_id} on pin {self.pin}")

    async def execute_command(self, command_type: CommandType, params: Optional[Dict[str, Any]] = None) -> CommandStatus:
        try:
            if command_type == CommandType.TURN_ON:
                await self.gpio_adapter.write_data({
                    'device_id': self.device_id,
                    'state': True
                })
                self.state["power"] = True
                # In a real implementation, you might start monitoring power consumption here
                status = "SUCCESS"
                message = f"Smart plug {self.device_id} turned ON"
                
            elif command_type == CommandType.TURN_OFF:
                await self.gpio_adapter.write_data({
                    'device_id': self.device_id,
                    'state': False
                })
                self.state["power"] = False
                self.state["power_consumption"] = 0.0
                status = "SUCCESS"
                message = f"Smart plug {self.device_id} turned OFF"
                
            else:
                status = "FAILED"
                message = f"Unknown command for smart plug: {command_type}"

            return CommandStatus(
                command_id="",
                status=status,
                message=message,
                executed_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error executing command on smart plug {self.device_id}: {e}")
            return CommandStatus(
                command_id="",
                status="FAILED",
                message=str(e),
                executed_at=datetime.now()
            )

    async def get_state(self) -> Dict[str, Any]:
        if self.state["power"]:
            # In a real implementation, you would read actual power consumption
            self.state["power_consumption"] = 120.5  # Example value
            self.state["voltage"] = 220.0  # Example value
        return self.state