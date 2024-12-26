from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum

class Device(BaseModel):
    id: str
    name: str
    type: str
    protocol: str
    config: Dict[str, Any]


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