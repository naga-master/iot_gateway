# Device lifecycle management
from typing import Dict, Any, Optional
import asyncio
import uuid
from iot_gateway.models.device import DeviceCommand, CommandStatus, CommandType
from iot_gateway.adapters.base import BaseDevice
from iot_gateway.utils.logging import get_logger
from iot_gateway.devices.factory import DeviceFactory
from datetime import datetime

logger = get_logger(__name__)

class DeviceManager:
    '''
    Singleton class for managing only one device manager throughout the application
    '''
    _instance: Optional['DeviceManager'] = None
    _initialized = False

    def __init__(self, event_manager, gpio_adapter, config):
        if not DeviceManager._initialized and event_manager and gpio_adapter:
            self.event_manager = event_manager
            self.gpio_adapter = gpio_adapter
            self.device_config = config
            self.command_queue = asyncio.Queue()
            self.command_statuses: Dict[str, CommandStatus] = {}
            self.devices: Dict[str, BaseDevice] = {}
            DeviceManager._initialized = True

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> 'DeviceManager':
        if not cls._instance or not cls._initialized:
            raise RuntimeError("DeviceManager not initialized. Call initialize() first.")
        return cls._instance


    async def initialize(self):
        logger.info("Initializing Device Manager")
        if not self.event_manager or not self.gpio_adapter:
            raise RuntimeError("DeviceManager requires event_manager and gpio_adapter")

        # Subscribe to device command events
        await self.event_manager.subscribe("device.command", self._handle_command_event)
        await self._initialize_devices()
        # Start command processor
        asyncio.create_task(self._process_commands())

    async def _initialize_devices(self):
        """Initialize all configured devices"""
        for device_name, config in self.device_config.items():
            try:
                device = DeviceFactory.create_device(
                    device_type=config["type"],
                    device_id=device_name,
                    config=config,
                    gpio_adapter=self.gpio_adapter
                )
                await device.initialize()
                self.devices[device_name] = device
                logger.info(f"Initialized device: {device_name}")
            except Exception as e:
                logger.error(f"Failed to initialize device {device_name}: {e}")

    async def submit_command(self, command: DeviceCommand) -> str:
        """Submit a command and return its ID for tracking"""
        print("Submit command Received", command)
        command_id = await self._handle_command_event(command.model_dump())
        return command_id

    async def _handle_command_event(self, command_data: Dict[str, Any]) -> str:
        """Handle incoming device commands and return command ID"""
        command = DeviceCommand(**command_data)
        command_id = str(uuid.uuid4())
        
        # Create initial status with only the required fields from the model
        status = CommandStatus(
            command_id=command_id,
            status="PENDING"  # Required field
        )
        self.command_statuses[command_id] = status
        
        # Add to processing queue
        await self.command_queue.put((command_id, command))
        
        # Publish command accepted event
        await self.event_manager.publish(
            "device.command.accepted",
            {
                "command_id": command_id,
                "device_id": command.device_id,
                "command": command.command.value,
                "params": command.params,
                "timestamp": command.timestamp.isoformat(),
                "status": "PENDING"
            }
        )
        
        return command_id

    async def _process_commands(self):
        """Process commands from the queue"""
        while True:
            command_id, command = await self.command_queue.get()
            try:
                device = self.devices.get(command.device_id)
                if not device:
                    raise ValueError(f"Unknown device: {command.device_id}")

                # Execute command on the device
                result = await device.execute_command(
                    command.command,
                    command.params
                )
                
                # Update command status
                status = CommandStatus(
                    command_id=command_id,
                    status="COMPLETED",
                    executed_at=datetime.now()
                )
                self.command_statuses[command_id] = status

                # Publish status update event
                await self.event_manager.publish(
                    "device.status",
                    status.model_dump()
                )
                
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                error_status = CommandStatus(
                    command_id=command_id,
                    status="FAILED",
                    message=str(e),
                    executed_at=datetime.now()
                )
                self.command_statuses[command_id] = error_status
                await self.event_manager.publish(
                    "device.status",
                    error_status.model_dump()
                )

    async def get_command_status(self, command_id: str) -> Optional[CommandStatus]:
        """Get the status of a command"""
        return self.command_statuses.get(command_id)

    async def get_device_state(self, device_id: str) -> Dict[str, Any]:
        """Get current state of a device"""
        device = self.devices.get(device_id)
        if not device:
            raise ValueError(f"Unknown device: {device_id}")
        return await device.get_state()

    async def cleanup(self):
        """Cleanup all devices"""
        for device in self.devices.values():
            await device.cleanup()