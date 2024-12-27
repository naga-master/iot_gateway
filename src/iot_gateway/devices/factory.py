from typing import Dict, Any, Type
from iot_gateway.adapters.base import BaseDevice
from .bulb import BulbDevice
from .smart_plug import SmartPlug

class DeviceFactory:
    """Factory for creating device instances"""
    _device_types: Dict[str, Type[BaseDevice]] = {
        "bulb": BulbDevice,
        "smart_plug": SmartPlug
    }

    @classmethod
    def register_device_type(cls, device_type: str, device_class: Type[BaseDevice]) -> None:
        """Register a new device type"""
        cls._device_types[device_type] = device_class

    @classmethod
    def create_device(cls, device_type: str, device_id: str, config: Dict[str, Any], **kwargs) -> BaseDevice:
        """Create a device instance based on type"""
        if device_type not in cls._device_types:
            raise ValueError(f"Unknown device type: {device_type}")
            
        device_class = cls._device_types[device_type]
        return device_class(device_id, config, **kwargs)