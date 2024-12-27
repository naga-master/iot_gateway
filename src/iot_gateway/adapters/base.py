# Abstract base class for all protocol adapters
# Separate files for each protocol implementation (bluetooth.py, wifi.py, etc.)
# Each adapter implements the interface defined in base.py


from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
# from ..adapters.i2c import I2CAdapter

# Protocol Adapters
class CommunicationAdapter(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def read_data(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def write_data(self, data: Dict[str, Any]) -> None:
        pass



class I2CSensor(ABC):
    """
    Base class for all I2C sensors.
    Each sensor type should implement this interface.
    """
    def __init__(self, i2c_adapter, address: int, sensor_id: str):
        self.i2c = i2c_adapter
        self.address = address
        self.sensor_id = sensor_id

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the sensor with required settings."""
        pass

    @abstractmethod
    async def read_data(self) -> Dict[str, Any]:
        """Read and return processed sensor data."""
        pass

    @abstractmethod
    async def get_config(self) -> Dict[str, Any]:
        """Get current sensor configuration."""
        pass


class BaseDevice(ABC):
    """Base class for all device implementations"""
    def __init__(self, device_id: str, config: Dict[str, Any]):
        self.device_id = device_id
        self.config = config
        self.state: Dict[str, Any] = {}

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the device with required settings"""
        pass

    @abstractmethod
    async def execute_command(self, command_type: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute device-specific command"""
        pass

    @abstractmethod
    async def get_state(self) -> Dict[str, Any]:
        """Get current device state"""
        pass

    async def cleanup(self) -> None:
        """Cleanup resources. Override if needed."""
        pass