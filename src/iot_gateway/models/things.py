from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from pydantic import BaseModel, field_validator

class DeviceType(Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    MOTION = "motion"
    SMART_PLUG = "smart_plug"
    CAMERA = "camera"
    LIGHT = "light"
    HEARTBEAT = "heartbeat"


class BaseReading(BaseModel):
    device_id: str
    reading_id: str
    timestamp: datetime = datetime.now()
    is_synced: bool = False


@dataclass
class HumidityReading(BaseReading):
    humidity: float


@dataclass
class HeartbeatReading(BaseReading):
    status: str
    latency_ms: float


@dataclass
class SmartPlugReading(BaseReading):
    power_watts: float
    voltage: float
    current: float
    is_on: bool


class TemperatureReading(BaseReading):
    celsius: float
    fahrenheit: float

    @field_validator('celsius')
    def validate_celsius(cls, v):
        if not -40 <= v <= 125:  # Common I2C temperature sensor range
            raise ValueError(f"Temperature {v}°C is out of valid range")
        return round(v, 2)

    @field_validator('fahrenheit')
    def validate_fahrenheit(cls, v):
        if not -40 <= v <= 257:  # Converted range
            raise ValueError(f"Temperature {v}°F is out of valid range")
        return round(v, 2)