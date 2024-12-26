# Device lifecycle management
from typing import Dict, Any, Optional
import asyncio
import uuid
from iot_gateway.models.device import DeviceCommand, CommandStatus, CommandType
from iot_gateway.utils.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)

class DeviceManager:
    '''
    Singleton class
    '''
    _instance: Optional['DeviceManager'] = None
    _initialized = False

    def __init__(self, event_manager, gpio_adapter):
        if not DeviceManager._initialized and event_manager and gpio_adapter:
            self.event_manager = event_manager
            self.gpio_adapter = gpio_adapter
            self.command_queue = asyncio.Queue()
            self.command_statuses: Dict[str, CommandStatus] = {}
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
        if not self.event_manager or not self.gpio_adapter:
            raise RuntimeError("DeviceManager requires event_manager and gpio_adapter")

        # Subscribe to device command events
        await self.event_manager.subscribe("device.command", self._handle_command_event)
        # Start command processor
        asyncio.create_task(self._process_commands())

    async def _handle_command_event(self, command_data: Dict[str, Any]):
        # When a command event arrives:
        command = DeviceCommand(**command_data) # data = {"device_id": "bulb1", "command": "TURN_ON"}
        command_id = str(uuid.uuid4()) # 4c99eadd-35e0-4263-86ec-59bcd5923c74
        
        # Create initial status
        status = CommandStatus(
            command_id=command_id,
            status="PENDING"
        )
        # {"4c99eadd-35e0-4263-86ec-59bcd5923c74": {"command_id": "4c99eadd-35e0-4263-86ec-59bcd5923c74", "status": "PENDING"} }
        self.command_statuses[command_id] = status
        
        # Queue command for processing
        # {"4c99eadd-35e0-4263-86ec-59bcd5923c74": {"device_id": "bulb1", "command": "TURN_ON"}}
        await self.command_queue.put((command_id, command))
        
        return command_id

    async def _process_commands(self):
        while True:
            command_id, command = await self.command_queue.get()
            print(command_id, command)
            try:
                if command.command == CommandType.TURN_ON:
                    ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                    # await self.gpio_adapter.write_data({
                    #     'device_id': command.device_id,
                    #     'state': True
                    # })
                    status = "SUCCESS"
                    message = f"Device {command.device_id} turned ON"
                elif command.command ==CommandType.TURN_OFF:
                    ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                    # await self.gpio_adapter.write_data({
                    #     'device_id': command.device_id,
                    #     'state': False
                    # })
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
            print(self.command_statuses)

            # Publish status update event
            await self.event_manager.publish("device.status", 
                self.command_statuses[command_id].model_dump())

    async def get_command_status(self, command_id: str) -> CommandStatus:
        return self.command_statuses.get(command_id)