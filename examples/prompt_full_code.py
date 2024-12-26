filepath: src/config/default.yml
code: 
api:
  host: "0.0.0.0"
  port: 8000

# config.yml
communication:
  mqtt:
    host: "localhost"
    port: 1883
    username: "user"
    password: "pass"

gpio:
  pins:
    bulb1:
      pin: 5
      type: "output"
      initial: false

temperature_monitor:
  database:
    path: "temperature.db"
  sensors:
    - id: "sensor1"
      bus: 1
      address: 0x48
    - id: "sensor2"
      bus: 1
      address: 0x49
  reading_interval: 60
  sync_interval: 300

logging:
  level: "INFO"
  file: "logs/iot_gateway.log"
  max_size: 10  # MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"


filepath: src/iot_gateway/adapters/base.py
code: # Abstract base class for all protocol adapters
# Separate files for each protocol implementation (bluetooth.py, wifi.py, etc.)
# Each adapter implements the interface defined in base.py


from abc import ABC, abstractmethod
from typing import Dict, Any
from ..adapters.i2c import I2CAdapter

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
    def __init__(self, i2c_adapter: I2CAdapter, address: int, sensor_id: str):
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
    

filepath: src/iot_gateway/adapters/gpio.py
code: 
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


filepath: src/iot_gateway/adapters/i2c.py
code: import smbus2
from .base import CommunicationAdapter
from ..utils.logging import get_logger
logger = get_logger(__name__)

class I2CAdapter(CommunicationAdapter):
    """
    Generic I2C communication adapter.
    Handles low-level I2C operations independently of specific sensors.
    """
    def __init__(self, bus_number: int):
        self.bus_number = bus_number
        self.bus = None
        self.is_connected = False

    async def connect(self) -> None:
        try:
            self.bus = smbus2.SMBus(self.bus_number)
            self.is_connected = True
            logger.info(f"Connected to I2C bus {self.bus_number}")
        except Exception as e:
            logger.error(f"Failed to connect to I2C bus {self.bus_number}: {e}")
            raise

    async def disconnect(self) -> None:
        if self.bus:
            self.bus.close()
            self.is_connected = False
            logger.info(f"Disconnected from I2C bus {self.bus_number}")

    async def read_bytes(self, address: int, register: int, num_bytes: int) -> bytes:
        """Read bytes from an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            data = self.bus.read_i2c_block_data(address, register, num_bytes)
            return bytes(data)
        except Exception as e:
            logger.error(f"Error reading from I2C device 0x{address:02x}: {e}")
            raise

    async def write_bytes(self, address: int, register: int, data: bytes) -> None:
        """Write bytes to an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            self.bus.write_i2c_block_data(address, register, list(data))
        except Exception as e:
            logger.error(f"Error writing to I2C device 0x{address:02x}: {e}")
            raise

    async def read_byte(self, address: int, register: int) -> int:
        """Read a single byte from an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            return self.bus.read_byte_data(address, register)
        except Exception as e:
            logger.error(f"Error reading from I2C device 0x{address:02x}: {e}")
            raise

    async def write_byte(self, address: int, register: int, value: int) -> None:
        """Write a single byte to an I2C device."""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
        try:
            self.bus.write_byte_data(address, register, value)
        except Exception as e:
            logger.error(f"Error writing to I2C device 0x{address:02x}: {e}")
            raise
        
filepath: src/iot_gateway/adapters/mqtt.py
code: 
import asyncio
from typing import Dict, Any, Callable
import asyncio_mqtt as mqtt
from ..adapters.base import BaseAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class MQTTAdapter(BaseAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.message_handlers = {}

    async def connect(self) -> None:
        try:
            self.client = mqtt.Client(
                hostname=self.config["host"],
                port=self.config["port"],
                username=self.config.get("username"),
                password=self.config.get("password")
            )
            await self.client.connect()
            logger.info("Connected to MQTT broker")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            raise

    async def disconnect(self) -> None:
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected from MQTT broker")

    async def subscribe(self, topic: str, handler: Callable) -> None:
        await self.client.subscribe(topic)
        self.message_handlers[topic] = handler
        logger.info(f"Subscribed to topic: {topic}")

    async def read_data(self) -> Dict[str, Any]:
        # Not used for MQTT - using callbacks instead
        pass

    async def write_data(self, data: Dict[str, Any]) -> None:
        try:
            topic = data.pop("topic")
            await self.client.publish(topic, data["payload"])
            logger.debug(f"Published to {topic}: {data['payload']}")
        except Exception as e:
            logger.error(f"Failed to publish MQTT message: {e}")
            raise
        

filepath: src/iot_gateway/api/endpoints/devices.py
code: 
from fastapi import APIRouter, HTTPException
from typing import Dict
from ...models.device import DeviceCommand, CommandStatus
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
    
filepath: src/iot_gateway/api/routes.py
code: 
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta
from ..storage.database import TemperatureStorage
from ..sensors.temperature import TemperatureReading

router = APIRouter()

@router.get("/temperature/{sensor_id}")
async def get_temperature_readings(
    sensor_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[TemperatureReading]:
    try:
        storage = TemperatureStorage("temperature.db")  # Should use DI in real app
        readings = await storage.get_readings(
            sensor_id,
            start_time or datetime.now() - timedelta(hours=24),
            end_time or datetime.now()
        )
        return readings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

file path: src/iot_gateway/core/config_manager.py
code:

# Configuration management
from typing import Dict, Any
import json
from dataclasses import dataclass

@dataclass
class SystemConfig:
    device_configs: Dict[str, Any]
    protocol_configs: Dict[str, Any]
    processing_rules: Dict[str, Any]


class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> SystemConfig:
        with open(self.config_path) as f:
            config_data = json.load(f)
        return SystemConfig(**config_data)
    
filepath: src/iot_gateway/core/device_manager.py
code:
# Device lifecycle management
from typing import Dict, Any
import asyncio
import uuid
from ..models.device import DeviceCommand, CommandStatus
from ..utils.logging import get_logger
from datetime import datetime

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
    
filepath: src/iot_gateway/core/event_manager.py
code: 
# Central event handling system
import asyncio
from typing import Dict, Any

class EventManager:
    def __init__(self):
        self.subscribers = {}
        self.event_queue = asyncio.Queue()

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        await self.event_queue.put((event_type, data))
        
    async def subscribe(self, event_type: str, callback) -> None:
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    async def process_events(self) -> None:
        while True:
            event_type, data = await self.event_queue.get()
            if event_type in self.subscribers:
                for callback in self.subscribers[event_type]:
                    await callback(data)

filepath: src/iot_gateway/core/communication_service.py
code:
from typing import Dict, Any, Optional
from ..adapters.mqtt import MQTTAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class CommunicationService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mqtt: Optional[MQTTAdapter] = None

    async def initialize(self) -> None:
        # Initialize MQTT
        if 'mqtt' in self.config:
            self.mqtt = MQTTAdapter(self.config['mqtt'])
            await self.mqtt.connect()
            logger.info("Temperature monitor initialized")

    async def shutdown(self) -> None:
        if self.mqtt:
            await self.mqtt.disconnect()
        # Shutdown other adapters

filepath: src/iot_gateway/core/temperature_monitor.py
code: 
from typing import Dict, Any, Optional
import asyncio
from ..adapters.i2c import I2CAdapter
from ..adapters.mqtt import MQTTAdapter
from ..storage.database import TemperatureStorage
from ..sensors.temperature import TMP102Sensor, SHT31Sensor
from ..sensors.temperature import TemperatureReading
from ..core.communication_service import CommunicationService
from ..utils.logging import get_logger

logger = get_logger(__name__)

class TemperatureMonitor:
    def __init__(self, config: Dict[str, Any], event_manager, 
                 communication_service: CommunicationService):
        self.config = config
        self.event_manager = event_manager
        self.communication_service = communication_service
        self.i2c_adapter = None
        self.sensors = []
        self.mqtt: Optional[MQTTAdapter] = None
        self.storage = TemperatureStorage(config["database"]["path"])
        self.is_running = False

    async def initialize(self) -> None:
        # Initialize I2C adapter
        self.i2c_adapter = I2CAdapter(self.config['i2c_bus'])
        await self.i2c_adapter.connect()

        # Initialize sensors
        for sensor_config in self.config['sensors']:
            sensor_class = self._get_sensor_class(sensor_config['type'])
            sensor = sensor_class(
                self.i2c_adapter,
                sensor_config['address'],
                sensor_config['id']
            )
            await sensor.initialize()
            self.sensors.append(sensor)

        ## TODO Move this to somewhere 
        # Initialize MQTT
        self.mqtt = MQTTAdapter(self.config["mqtt"])
        await self.mqtt.connect()

        logger.info("Temperature monitor initialized")

    def _get_sensor_class(self, sensor_type: str) -> type:
        """Get sensor class based on type."""
        sensor_classes = {
            'TMP102': TMP102Sensor,
            'SHT31': SHT31Sensor,
            # Add more sensor types here
        }
        return sensor_classes.get(sensor_type)
    
    async def start_monitoring(self) -> None:
        self.is_running = True
        while self.is_running:
            try:
                for sensor in self.sensors:
                    # Read sensor
                    data = await sensor.read_data()
                    
                    # Create reading
                    reading = TemperatureReading(
                        sensor_id=sensor.sensor_id,
                        **data
                    )

                    # Store reading
                    await self.storage.store_reading(reading)

                    # Use communication service for MQTT
                    if self.communication_service.mqtt:
                        # Publish reading
                        try:
                            await self.mqtt.write_data({
                                "topic": f"temperature/{sensor.sensor_id}",
                                "payload": reading.model_dump_json()
                            })
                            reading.is_synced = True
                        except Exception as e:
                            logger.error(f"Failed to publish reading: {e}")
                            # Will be synced later

                await asyncio.sleep(self.config["reading_interval"])
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Wait before retry

    async def sync_stored_readings(self) -> None:
        while self.is_running:
            try:
                unsynced = await self.storage.get_unsynced_readings()
                if unsynced:
                    logger.info(f"Syncing {len(unsynced)} stored readings")
                    for reading in unsynced:
                        try:
                            await self.mqtt.write_data({
                                "topic": f"temperature/{reading.sensor_id}",
                                "payload": reading.model_dump_json()
                            })
                            reading.is_synced = True
                        except Exception as e:
                            logger.error(f"Failed to sync reading: {e}")
                            break  # Stop if MQTT is down
                    
                    # Mark successful syncs
                    synced_ids = [r.id for r in unsynced if r.is_synced]
                    if synced_ids:
                        await self.storage.mark_as_synced(synced_ids)

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
            
            await asyncio.sleep(self.config["sync_interval"])

    async def stop(self) -> None:
        self.is_running = False
        for sensor in self.sensors:
            await sensor.disconnect()
        if self.mqtt:
            await self.mqtt.disconnect()
        logger.info("Temperature monitor stopped")


filepath: src/iot_gateway/models/device.py
code:
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

filepath: src/iot_gateway/processing/business_processor.py
code: 
# Business rules implementation
from typing import Dict, Any
class BusinessProcessor:
    def __init__(self, rules_config: Dict[str, Any]):
        self.rules = rules_config

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Apply business rules
        processed_data = ""
        return processed_data
    
filepath: src/iot_gateway/sensors/temperature.py
code:
from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Dict, Any
from ..adapters.base import I2CSensor
from ..utils.logging import get_logger

logger = get_logger(__name__)

class TMP102Sensor(I2CSensor):
    """
    Implementation for TMP102 temperature sensor.
    """
    # TMP102 registers
    TEMP_REGISTER = 0x00
    CONFIG_REGISTER = 0x01
    
    async def initialize(self) -> None:
        """Initialize TMP102 sensor with default settings."""
        try:
            # Set 12-bit resolution
            await self.i2c.write_byte(self.address, self.CONFIG_REGISTER, 0x60)
            logger.info(f"Initialized TMP102 sensor {self.sensor_id}")
        except Exception as e:
            logger.error(f"Failed to initialize TMP102 sensor {self.sensor_id}: {e}")
            raise

    async def read_data(self) -> Dict[str, Any]:
        """Read and convert temperature data."""
        try:
            # Read temperature register
            data = await self.i2c.read_bytes(self.address, self.TEMP_REGISTER, 2)
            
            # Convert to temperature
            temp_c = ((data[0] << 8) | data[1]) / 256.0
            temp_f = (temp_c * 9/5) + 32
            
            logger.debug(f"Sensor {self.sensor_id} read: {temp_c}°C / {temp_f}°F")
            return {
                "sensor_id": self.sensor_id,
                "celsius": round(temp_c, 2),
                "fahrenheit": round(temp_f, 2)
            }
        except Exception as e:
            logger.error(f"Error reading TMP102 sensor {self.sensor_id}: {e}")
            raise

    async def get_config(self) -> Dict[str, Any]:
        """Get current sensor configuration."""
        config = await self.i2c.read_byte(self.address, self.CONFIG_REGISTER)
        return {
            "sensor_id": self.sensor_id,
            "resolution": "12-bit" if config & 0x60 else "13-bit",
            "address": self.address
        }
    

class SHT31Sensor(I2CSensor):
    """
    Implementation for SHT31 temperature and humidity sensor.
    """
    # SHT31 registers and commands
    MEASURE_HIGH_REP = bytes([0x24, 0x00])
    
    async def initialize(self) -> None:
        # Implementation for SHT31
        pass

    async def read_data(self) -> Dict[str, Any]:
        # Implementation for SHT31
        pass

    async def get_config(self) -> Dict[str, Any]:
        # Implementation for SHT31
        pass


class TemperatureReading(BaseModel):
    sensor_id: str
    celsius: float
    fahrenheit: float
    timestamp: datetime = datetime.now()
    is_synced: bool = False

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

filepath: src/iot_gateway/storage/database.py
code: 
# Database interactions
from typing import List, Optional
import aiosqlite
from ..sensors.temperature import TemperatureReading
from ..utils.logging import get_logger

logger = get_logger(__name__)

class TemperatureStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS temperature_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id TEXT NOT NULL,
                    celsius REAL NOT NULL,
                    fahrenheit REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_synced BOOLEAN NOT NULL DEFAULT 0
                )
            ''')
            await db.commit()
            logger.info("Database initialized")

    async def store_reading(self, reading: TemperatureReading) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO temperature_readings 
                (sensor_id, celsius, fahrenheit, timestamp, is_synced)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                reading.sensor_id,
                reading.celsius,
                reading.fahrenheit,
                reading.timestamp,
                reading.is_synced
            ))
            await db.commit()
            logger.debug(f"Stored reading from sensor {reading.sensor_id}")

    async def get_unsynced_readings(self) -> List[TemperatureReading]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM temperature_readings WHERE is_synced = 0'
            ) as cursor:
                rows = await cursor.fetchall()
                return [TemperatureReading(**dict(row)) for row in rows]

    async def mark_as_synced(self, reading_ids: List[int]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE temperature_readings SET is_synced = 1 WHERE id IN (?)',
                [tuple(reading_ids)]
            )
            await db.commit()

filepath: __main__.py
code:

# src/iot_gateway/__main__.py
import asyncio
import signal
import yaml
import logging
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
import sys

from iot_gateway.core.event_manager import EventManager
from iot_gateway.core.device_manager import DeviceManager
from iot_gateway.core.temperature_monitor import TemperatureMonitor
from iot_gateway.adapters.mqtt import MQTTAdapter
from iot_gateway.adapters.gpio import GPIOAdapter
from iot_gateway.sensors.temperature import TemperatureMonitor
from iot_gateway.storage.database import TemperatureStorage
from iot_gateway.api.routes import router
from iot_gateway.api.endpoints.devices import router as device_router
from iot_gateway.utils.logging import setup_logging
from iot_gateway.core.communication_service import CommunicationService

def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

class IoTGatewayApp:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.temperature_monitor = None
        self.communication_service = None
        self.api_app = None
        self.shutdown_event = asyncio.Event()
        self.event_manager = EventManager()
        self.device_manager = None
        
        # Setup logging
        setup_logging(self.config.get('logging', {}))

    async def initialize(self):
        # Start event processing loop
        asyncio.create_task(self.event_manager.process_events())

        # Initialize Communication Service
        self.communication_service = CommunicationService(self.config)
        await self.communication_service.initialize()

        # Initialize device manager
        self.device_manager = DeviceManager(self.event_manager, GPIOAdapter(self.config['gpio']))
        await self.device_manager.initialize()

    async def start_api(self):
        #  FastAPI app is created
        self.api_app = FastAPI(title="IoT Gateway API")
        # 2. Routes are registered
        self.api_app.include_router(router, prefix="/api/v1")
        
        hypercorn_config = HyperConfig()
        hypercorn_config.bind = [f"{self.config['api']['host']}:{self.config['api']['port']}"]
        
        # Start API server
        await serve(self.api_app, hypercorn_config, shutdown_trigger=self.shutdown_event.wait)

    async def start_monitor(self):
        self.temperature_monitor = TemperatureMonitor(self.config['temperature_monitor'], 
                                                      self.event_manager, self.communication_service)
        await self.temperature_monitor.initialize()
        
        # Start monitoring and syncing in separate tasks
        monitor_task = asyncio.create_task(self.temperature_monitor.start_monitoring())
        sync_task = asyncio.create_task(self.temperature_monitor.sync_stored_readings())

        
        # Wait for shutdown
        await self.shutdown_event.wait()
        
        # Clean shutdown
        await self.temperature_monitor.stop()
        await asyncio.gather(monitor_task, sync_task, return_exceptions=True)

    def handle_signals(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self.handle_shutdown)

    async def shutdown(self):
        print("Received shutdown signal. Shutting down services gracefully...")
        if self.temperature_monitor:
            await self.temperature_monitor.stop()
        if self.communication_service:
            await self.communication_service.shutdown()
        self.shutdown_event.set()

    def handle_shutdown(self, signum, frame):
        print("Received shutdown signal. Shutting down gracefully...")
        self.shutdown_event.set()

    async def run(self):
        try:
            # Signal handlers are set up for graceful shutdown
            self.handle_signals()
            
            # Start all components
            await self.initialize()
            await asyncio.gather(
                self.start_monitor(), # Temperature monitoring
                self.start_api() # API server
            )
        except Exception as e:
            print(f"Error starting application: {e}")
            sys.exit(1)


# Example config.yml
example_config = """
api:
  host: "0.0.0.0"
  port: 8000

temperature_monitor:
  database:
    path: "temperature.db"
  sensors:
    - id: "sensor1"
      bus: 1
      address: 0x48
    - id: "sensor2"
      bus: 1
      address: 0x49
  mqtt:
    host: "localhost"
    port: 1883
    username: "user"
    password: "pass"
  reading_interval: 60  # seconds
  sync_interval: 300    # seconds

logging:
  level: "INFO"
  file: "iot_gateway.log"
"""

def main():
    # Create default config if it doesn't exist
    config_path = Path("config.yml")
    if not config_path.exists():
        with open(config_path, 'w') as f:
            f.write(example_config)
        print("Created default config.yml")
    
    app = IoTGatewayApp(str(config_path))
    asyncio.run(app.run()) # This kicks off everything

if __name__ == "__main__":
    main()