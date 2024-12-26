# src/iot_gateway/models/device_command.py
from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum

class CommandType(str, Enum):
    TURN_ON = "TURN_ON"
    TURN_OFF = "TURN_OFF"

class DeviceCommand(BaseModel):
    device_id: str
    command: CommandType
    params: Optional[Dict[str, Any]] = None
    timestamp: datetime = datetime.now()

class CommandStatus(BaseModel):
    command_id: str
    status: str
    message: Optional[str] = None
    executed_at: Optional[datetime] = None

# src/iot_gateway/adapters/gpio_controller.py
from typing import Dict, Any
import RPi.GPIO as GPIO
from .base import BaseAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class GPIOAdapter(BaseAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pins: Dict[str, int] = {}
        self.initialized = False

    async def connect(self) -> None:
        try:
            GPIO.setmode(GPIO.BCM)
            # Initialize pins from config
            for device_id, pin_config in self.config['pins'].items():
                pin = pin_config['pin']
                GPIO.setup(pin, GPIO.OUT)
                self.pins[device_id] = pin
            self.initialized = True
            logger.info("GPIO adapter initialized")
        except Exception as e:
            logger.error(f"GPIO initialization failed: {e}")
            raise

    async def disconnect(self) -> None:
        if self.initialized:
            GPIO.cleanup()
            self.initialized = False
            logger.info("GPIO adapter cleaned up")

    async def read_data(self) -> Dict[str, Any]:
        if not self.initialized:
            raise RuntimeError("GPIO not initialized")
        
        states = {}
        for device_id, pin in self.pins.items():
            states[device_id] = GPIO.input(pin)
        return states

    async def write_data(self, data: Dict[str, Any]) -> None:
        if not self.initialized:
            raise RuntimeError("GPIO not initialized")
        
        device_id = data.get('device_id')
        state = data.get('state')
        
        if device_id not in self.pins:
            raise ValueError(f"Unknown device ID: {device_id}")
        
        pin = self.pins[device_id]
        GPIO.output(pin, state)
        logger.info(f"Set {device_id} (PIN {pin}) to {state}")

# src/iot_gateway/core/device_manager.py
from typing import Dict, Any
import asyncio
import uuid
from ..models.device_command import DeviceCommand, CommandStatus
from ..utils.logging import get_logger

logger = get_logger(__name__)

class DeviceManager:
    def __init__(self, event_manager, gpio_adapter):
        self.event_manager = event_manager
        self.gpio_adapter = gpio_adapter
        self.command_queue = asyncio.Queue()
        self.command_statuses: Dict[str, CommandStatus] = {}

    async def initialize(self):
        # Subscribe to device command events
        await self.event_manager.subscribe("device.command", self._handle_command_event)
        # Start command processor
        asyncio.create_task(self._process_commands())

    async def _handle_command_event(self, command_data: Dict[str, Any]):
        command = DeviceCommand(**command_data)
        command_id = str(uuid.uuid4())
        
        # Create initial status
        status = CommandStatus(
            command_id=command_id,
            status="PENDING"
        )
        self.command_statuses[command_id] = status
        
        # Queue command for processing
        await self.command_queue.put((command_id, command))
        
        return command_id

    async def _process_commands(self):
        while True:
            command_id, command = await self.command_queue.get()
            try:
                if command.command == "TURN_ON":
                    await self.gpio_adapter.write_data({
                        'device_id': command.device_id,
                        'state': True
                    })
                    status = "SUCCESS"
                    message = f"Device {command.device_id} turned ON"
                elif command.command == "TURN_OFF":
                    await self.gpio_adapter.write_data({
                        'device_id': command.device_id,
                        'state': False
                    })
                    status = "SUCCESS"
                    message = f"Device {command.device_id} turned OFF"
                else:
                    status = "FAILED"
                    message = f"Unknown command: {command.command}"
                
            except Exception as e:
                status = "FAILED"
                message = str(e)
                logger.error(f"Command execution failed: {e}")
            
            # Update command status
            self.command_statuses[command_id] = CommandStatus(
                command_id=command_id,
                status=status,
                message=message,
                executed_at=datetime.now()
            )
            
            # Publish status update event
            await self.event_manager.publish("device.status", 
                self.command_statuses[command_id].dict())

    async def get_command_status(self, command_id: str) -> CommandStatus:
        return self.command_statuses.get(command_id)

# src/iot_gateway/api/endpoints/devices.py
from fastapi import APIRouter, HTTPException
from typing import Dict
from ...models.device_command import DeviceCommand, CommandStatus
from ...core.device_manager import DeviceManager

router = APIRouter()

@router.post("/devices/{device_id}/control")
async def control_device(device_id: str, command: DeviceCommand) -> Dict[str, str]:
    try:
        # Get DeviceManager instance (should use dependency injection in real app)
        device_manager = DeviceManager.get_instance()
        
        # Submit command through event system
        command_id = await device_manager.event_manager.publish(
            "device.command",
            command.dict()
        )
        
        return {"command_id": command_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/devices/commands/{command_id}")
async def get_command_status(command_id: str) -> CommandStatus:
    try:
        device_manager = DeviceManager.get_instance()
        status = await device_manager.get_command_status(command_id)
        if not status:
            raise HTTPException(status_code=404, detail="Command not found")
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Example configuration (config.yml)
gpio_config = """
gpio:
  pins:
    bulb1:
      pin: 5
      type: "output"
      initial: false
    bulb2:
      pin: 6
      type: "output"
      initial: false
"""

# Example usage in tests
# tests/test_bulb_control.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_bulb_control():
    # Mock GPIO adapter
    gpio_mock = AsyncMock()
    
    # Mock event manager
    event_manager = AsyncMock()
    
    # Create device manager with mocks
    device_manager = DeviceManager(event_manager, gpio_mock)
    await device_manager.initialize()
    
    # Test command execution
    command = DeviceCommand(
        device_id="bulb1",
        command="TURN_ON"
    )
    
    command_id = await device_manager._handle_command_event(command.dict())
    
    # Verify GPIO was called
    gpio_mock.write_data.assert_called_once_with({
        'device_id': 'bulb1',
        'state': True
    })
    
    # Verify status was updated
    status = await device_manager.get_command_status(command_id)
    assert status.status == "SUCCESS"
