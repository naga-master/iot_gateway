from iot_gateway.adapters.base import BaseDevice
from iot_gateway.models.device import CommandType, CommandStatus
from typing import Dict, Any, Optional
from iot_gateway.utils.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)

class BulbDevice(BaseDevice):
    """Implementation for bulb devices"""
    def __init__(self, device_id: str, config: Dict[str, Any], gpio_adapter):
        super().__init__(device_id, config)
        self.gpio_adapter = gpio_adapter
        self.pin = config['pin']
        self.state = {"power": False}

    async def initialize(self) -> None:
        """Initialize GPIO pin for the bulb"""
        # GPIO setup is handled by the adapter
        self.state["power"] = self.config.get("initial", False)
        logger.info(f"Initialized bulb device {self.device_id} on pin {self.pin}")

    async def execute_command(self, command_type: CommandType, params: Optional[Dict[str, Any]] = None) -> CommandStatus:
        try:
            if command_type == CommandType.TURN_ON:
                ####### TODO: To be removed in future while cleanup (check the effects) #######
                # await self.gpio_adapter.write_data({
                #     'device_id': self.device_id,
                #     'state': True
                # })
                self.state["power"] = True
                status = "SUCCESS"
                message = f"Bulb {self.device_id} turned ON"
                
            elif command_type == CommandType.TURN_OFF:
                await self.gpio_adapter.write_data({
                    'device_id': self.device_id,
                    'state': False
                })
                self.state["power"] = False
                status = "SUCCESS"
                message = f"Bulb {self.device_id} turned OFF"
                
            else:
                status = "FAILED"
                message = f"Unknown command for bulb: {command_type}"

            return CommandStatus(
                command_id="",  # Will be set by DeviceManager
                status=status,
                message=message,
                executed_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error executing command on bulb {self.device_id}: {e}")
            return CommandStatus(
                command_id="",
                status="FAILED",
                message=str(e),
                executed_at=datetime.now()
            )

    async def get_state(self) -> Dict[str, Any]:
        return self.state