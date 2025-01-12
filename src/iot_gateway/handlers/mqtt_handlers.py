from typing import Any, Dict, Optional
from datetime import datetime
from ..utils.logging import get_logger
from ..core.device_manager import DeviceManager
from ..models.device import CommandType, DeviceCommand
import json

logger = get_logger(__name__)

class MQTTMessageHandlers:
    def __init__(self, event_manager):
        self.device_manager = DeviceManager.get_instance()
        self.event_manager = event_manager

    async def smart_plug_handler(self, topic: str, payload: Any) -> None:
        """Handle smart plug control messages
        Expected topic format: devices/smart_plug/{device_id}/command
        Expected payload format: {"command": "TURN_ON"} or {"command": "TURN_OFF"}
        """
        try:
            # Extract device_id from topic
            # Example topic: devices/smart_plug/plug1/command
            parts = topic.split('/')
            if len(parts) != 4:
                logger.error(f"Invalid topic format: {topic}")
                return
            
            device_id = parts[2]
            
            # Parse payload
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON payload: {payload}")
                    return
            
            # Validate payload
            if not isinstance(payload, dict) or 'command' not in payload:
                logger.error(f"Invalid payload format: {payload}")
                return
                
            # Map command string to CommandType
            command_map = {
                'TURN_ON': CommandType.TURN_ON,
                'TURN_OFF': CommandType.TURN_OFF
            }
            
            command_str = payload['command'].upper()
            if command_str not in command_map:
                logger.error(f"Unknown command: {command_str}")
                return
                
            # Extract additional parameters if any
            params = payload.get('params', {})

            # device_id
            device_id = payload['device_id']
            
            # Create and submit command
            command_data = {
                "device_id": device_id,
                "command":command_str,
                "params": params,
                "timestamp":datetime.now().isoformat()
                }

            
            command = DeviceCommand(**command_data)
            # Submit command to device manager
            command_id = await self.device_manager.submit_command(command)
            logger.info(f"Command {command_id} submitted for device {device_id}: {command_str}")
                
        except Exception as e:
            logger.error(f"Error processing smart plug command: {str(e)}")

    @staticmethod
    async def temperature_handler(topic: str, payload: Any) -> None:
        """Handle temperature related messages"""
        logger.info(f"Temperature reading from {topic}: {payload}")

    async def temperature_ack_handler(self, topic: str, payload: Any) -> None:
        """Forward temperature acks to event manager"""
        for callback in self.event_manager.subscribers.get("temperature_ack"):
            await callback(topic, payload)

    async def temperature_sync_handler(self, topic: str, payload: Any) -> None:
        """Forward temperature sync to event manager"""
        for callback in self.event_manager.subscribers.get("sync_temperature"):
            await callback(topic, payload)
        
    @staticmethod
    async def general_handler(topic: str, payload: Any) -> None:
        """General purpose message handler"""
        logger.info(f"Received message on {topic}: {payload}")