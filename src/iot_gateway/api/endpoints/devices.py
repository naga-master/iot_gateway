from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ...models.device import DeviceCommand, CommandStatus
from ...core.device_manager import DeviceManager
from ...utils.logging import get_logger

logger = get_logger(__name__)

device_router = APIRouter()


'''
# Submit command
response = await client.post(f"/api/v1/devices/{device_id}/control", json=command_data)
command_id = response.json()["command_id"]

# Check status
status = await client.get(f"/api/v1/devices/{device_id}/commands/{command_id}")
'''

@device_router.post("/devices/{device_id}/control")
async def control_device(device_id: str, command: DeviceCommand) -> Dict[str, str]:
    try:
        try:
            device_manager = DeviceManager.get_instance()
        except RuntimeError as e:
            logger.error(f"DeviceManager not properly initialized: {e}")
            raise HTTPException(
                status_code=503, 
                detail="Device management system not available"
            )
        
        if device_id != command.device_id:
            raise HTTPException(
                status_code=400,
                detail="Device ID in path does not match command device ID"
            )
        
        # Submit command and get command_id
        command_id = await device_manager.submit_command(command)
        
        return {
            "command_id": command_id,
            "status": "accepted",
            "message": f"Command {command.command.value} for device {device_id} accepted"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling device {device_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to control device: {str(e)}"
        )
        

@device_router.get("/devices/{device_id}/commands/{command_id}")
async def get_command_status(device_id: str, command_id: str) -> Dict[str, Any]:
    try:
        device_manager = DeviceManager.get_instance()
        status = await device_manager.get_command_status(command_id)
        
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Command {command_id} not found"
            )
            
        return status.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting command status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get command status: {str(e)}"
        )