from fastapi import APIRouter, HTTPException
from typing import Dict
from ...models.device import DeviceCommand, CommandStatus
from ...core.device_manager import DeviceManager
from ...utils.logging import get_logger

logger = get_logger(__name__)

device_router = APIRouter()

@device_router.post("/devices/{device_id}/control")
async def control_device(device_id: str, command: DeviceCommand) -> Dict[str, str]:
    try:
       # Get DeviceManager instance
        try:
            device_manager = DeviceManager.get_instance()
        except RuntimeError as e:
            logger.error(f"DeviceManager not properly initialized: {e}")
            raise HTTPException(
                status_code=503, 
                detail="Device management system not available"
            )
        
        # Validate device_id matches the command
        if device_id != command.device_id:
            raise HTTPException(
                status_code=400,
                detail="Device ID in path does not match command device ID"
            )
        
        # Submit command through event system
        command_id = await device_manager.event_manager.publish(
            "device.command",
            command.model_dump()
        )
        
        return {
            "command_id": command_id,
            "status": "accepted",
            "message": f"Command for device {device_id} accepted"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling device {device_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to control device: {str(e)}"
        )

@device_router.get("/devices/commands/{command_id}")
async def get_command_status(command_id: str) -> CommandStatus:
    try:
        device_manager = DeviceManager.get_instance()
        status = await device_manager.get_command_status(command_id)
        if not status:
            raise HTTPException(status_code=404, detail="Command not found")
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))