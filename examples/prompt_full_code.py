filepath: src/config/default.yml
code: 
api:
  host: "0.0.0.0"
  port: 8000

# config.yml
communication:
  mqtt:
    host: "broker.hivemq.com"
    port: 1883
    username: "user"
    password: "pass"
    keepalive: 60
    client_id: "gateway"
    ssl: false
    reconnect_interval: 5
    max_reconnect_attempts: 5

devices:
  bulb1:
    type: "bulb"
    pin: 5
    initial: false
  plug1:
    type: "smart_plug"
    pin: 6
    initial: false

temperature_monitor:
  database:
    path: "temperature.db"
  i2c_bus: 1
  sensors:
    - id: "sensor1"
      bus: 1
      address: 0x48
      type: "TMP102"
    - id: "sensor2"
      bus: 1
      address: 0x49
      type: "SHT31"
  reading_interval: 60
  sync_interval: 300

logging:
  level: "INFO"
  file: "logs/iot_gateway.log"
  max_size: 10  # MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"

filepath: src/iot_gateway/devices/factory.py
code:
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

filepath: src/iot_gateway/devices/bulb.py
code:
from iot_gateway.adapters.base import BaseDevice
from iot_gateway.models.device import CommandType, CommandStatus
from typing import Dict, Any, Optional
from iot_gateway.utils.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)

class BulbDevice(BaseDevice):
    """Implementation for bulb devices"""
    def __init__(self, device_id: str, config: Dict[str, Any], gpio_adapter):
        super().__init__(device_id, config)
        self.gpio_adapter = gpio_adapter
        self.pin = config['pin']
        self.state = {"power": False}

    async def initialize(self) -> None:
        """Initialize GPIO pin for the bulb"""
        # GPIO setup is handled by the adapter
        self.state["power"] = self.config.get("initial", False)
        logger.info(f"Initialized bulb device {self.device_id} on pin {self.pin}")

    async def execute_command(self, command_type: CommandType, params: Optional[Dict[str, Any]] = None) -> CommandStatus:
        try:
            if command_type == CommandType.TURN_ON:
                self.state["power"] = True
                status = "SUCCESS"
                message = f"Bulb {self.device_id} turned ON"
                
            elif command_type == CommandType.TURN_OFF:
                await self.gpio_adapter.write_data({
                    'device_id': self.device_id,
                    'state': False
                })
                self.state["power"] = False
                status = "SUCCESS"
                message = f"Bulb {self.device_id} turned OFF"
                
            else:
                status = "FAILED"
                message = f"Unknown command for bulb: {command_type}"

            return CommandStatus(
                command_id="",  # Will be set by DeviceManager
                status=status,
                message=message,
                executed_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error executing command on bulb {self.device_id}: {e}")
            return CommandStatus(
                command_id="",
                status="FAILED",
                message=str(e),
                executed_at=datetime.now()
            )

    async def get_state(self) -> Dict[str, Any]:
        return self.state
    


filepath: src/iot_gateway/adapters/base.py
code: # Abstract base class for all protocol adapters

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
from typing import Dict, Any, Callable, Optional, Union, TypeVar, List
from pydantic import BaseModel, Field
import aiomqtt as mqtt
import json
import traceback
from ..adapters.base import CommunicationAdapter
from ..utils.logging import get_logger
from ..utils.exceptions import CommunicationError
from contextlib import asynccontextmanager

logger = get_logger(__name__)

class MQTTConfig(BaseModel):
    """MQTT configuration model"""
    host: str = Field(..., description="MQTT broker hostname")
    port: int = Field(1883, description="MQTT broker port")
    username: Optional[str] = Field(None, description="MQTT username")
    password: Optional[str] = Field(None, description="MQTT password")
    keepalive: int = Field(60, description="Connection keepalive in seconds")
    client_id: Optional[str] = Field(None, description="MQTT client ID")
    ssl: bool = Field(False, description="Enable SSL/TLS")
    reconnect_interval: float = Field(5.0, description="Reconnection interval in seconds")
    max_reconnect_attempts: int = Field(5, description="Maximum reconnection attempts")

class MQTTMessage(BaseModel):
    """MQTT message model"""
    topic: str
    payload: Union[dict, str, bytes]
    qos: int = Field(0, ge=0, le=2)
    retain: bool = False

class MQTTAdapter(CommunicationAdapter):
    def __init__(self, config: Dict[str, Any]):
        """Initialize MQTT adapter with configuration"""
        try:
            self.config = MQTTConfig(**config)
        except Exception as e:
            raise CommunicationError(f"Invalid MQTT configuration: {traceback.format_exc()}")

        self.client: Optional[mqtt.Client] = None
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.connected = asyncio.Event()
        self._stop_flag = asyncio.Event()
        self._message_processor_task: Optional[asyncio.Task] = None
                
    async def message_handler(topic: str, payload: Any):
        print(f"Received on {topic}: {payload}")

    async def publish(self, message: Union[MQTTMessage, Dict[str, Any]]) -> None:
        """Publish message to MQTT topic"""
        try:
            if isinstance(message, dict):
                message = MQTTMessage(**message)
                
            if not self.connected.is_set():
                raise CommunicationError("Not connected to MQTT broker")
                
            payload = message.payload
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            elif not isinstance(payload, (str, bytes)):
                payload = str(payload)
                
            if isinstance(payload, str):
                payload = payload.encode()
                
            if self.client:
                await self.client.publish(
                    topic=message.topic,
                    payload=payload,
                    qos=message.qos,
                    retain=message.retain
                )
                logger.debug(f"Published to {message.topic}: {message.payload}")
                
        except Exception as e:
            raise CommunicationError(f"Failed to publish MQTT message: {traceback.format_exc()}")

    @asynccontextmanager
    async def _get_client(self):
        """Context manager for MQTT client with automatic reconnection"""
        attempt = 0
        while attempt < self.config.max_reconnect_attempts and not self._stop_flag.is_set():
            try:
                async with mqtt.Client(
                    hostname=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    password=self.config.password,
                    keepalive=self.config.keepalive,
                    identifier=self.config.client_id,
                    # tls_insecure=self.config.ssl
                ) as client:
                    self.client = client
                    self.connected.set()
                    logger.info("Connected to MQTT broker")
                    try:
                        yield client
                    finally:
                        self.connected.clear()
                        self.client = None
                        logger.info("Disconnected from MQTT broker")
                break  # Successful connection and operation
                
            except Exception as e:
                attempt += 1
                logger.error(f"MQTT connection attempt {attempt} failed: {traceback.format_exc()}")
                if attempt >= self.config.max_reconnect_attempts:
                    raise CommunicationError(f"Failed to connect to MQTT broker after {attempt} attempts")
                
                await asyncio.sleep(self.config.reconnect_interval)


    async def _process_messages(self):
        """Process incoming MQTT messages"""
        try:
            async with self._get_client() as client:
                async for message in client.messages:
                    if self._stop_flag.is_set():
                        break
                        
                    topic = str(message.topic)
                    try:
                        payload = message.payload.decode()
                        try:
                            payload = json.loads(payload)
                        except json.JSONDecodeError:
                            pass  # Keep payload as string if not JSON
                            
                        if topic in self.message_handlers:
                            for handler in self.message_handlers[topic]:
                                try:
                                    await handler(topic, payload)
                                except Exception as e:
                                    logger.error(f"Error in message handler for topic {topic}: {e}")
                                    
                    except Exception as e:
                        logger.error(f"Error processing message on topic {topic}: {e}")
                            
        except Exception as e:
            if not self._stop_flag.is_set():
                logger.error(f"Error in message processing loop: {e}")
                # Restart the message processor if not intentionally stopped
                self._message_processor_task = asyncio.create_task(self._process_messages())
    
    async def connect(self) -> None:
        """Connect to MQTT broker and start message processing"""
        try:
            self._stop_flag.clear()
            self._message_processor_task = asyncio.create_task(self._process_messages())
        except Exception as e:
            raise CommunicationError(f"Failed to start MQTT adapter: {traceback.format_exc()}")

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker and cleanup"""
        try:
            self._stop_flag.set()
            if self._message_processor_task:
                await self._message_processor_task
            self.connected.clear()
            logger.info("MQTT adapter stopped")
        except Exception as e:
            raise CommunicationError(f"Error disconnecting from MQTT: {traceback.format_exc()}")

    async def subscribe(self, topic: str, handler: Callable[[str, Any], None]) -> None:
        """Subscribe to MQTT topic with handler"""
        try:
            if not self.connected.is_set():
                raise CommunicationError("Not connected to MQTT broker")
                
            if topic not in self.message_handlers:
                self.message_handlers[topic] = []
                if self.client:
                    await self.client.subscribe(topic)
                    
            self.message_handlers[topic].append(handler)
            logger.info(f"Subscribed to topic: {topic}")
            
        except Exception as e:
            raise CommunicationError(f"Failed to subscribe to topic {topic}: {traceback.format_exc()}")

    async def unsubscribe(self, topic: str, handler: Optional[Callable] = None) -> None:
        """Unsubscribe from MQTT topic"""
        try:
            if topic in self.message_handlers:
                if handler:
                    self.message_handlers[topic].remove(handler)
                    if not self.message_handlers[topic]:
                        del self.message_handlers[topic]
                        if self.client:
                            await self.client.unsubscribe(topic)
                else:
                    del self.message_handlers[topic]
                    if self.client:
                        await self.client.unsubscribe(topic)
                        
            logger.info(f"Unsubscribed from topic: {topic}")
            
        except Exception as e:
            raise CommunicationError(f"Failed to unsubscribe from topic {topic}: {traceback.format_exc()}")

    async def publish(self, message: Union[MQTTMessage, Dict[str, Any]]) -> None:
        """Publish message to MQTT topic"""
        try:
            if isinstance(message, dict):
                message = MQTTMessage(**message)
                
            if not self.connected.is_set():
                raise CommunicationError("Not connected to MQTT broker")
                
            payload = message.payload
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            elif not isinstance(payload, (str, bytes)):
                payload = str(payload)
                
            if isinstance(payload, str):
                payload = payload.encode()
                
            if self.client:
                await self.client.publish(
                    topic=message.topic,
                    payload=payload,
                    qos=message.qos,
                    retain=message.retain
                )
                logger.debug(f"Published to {message.topic}: {message.payload}")
                
        except Exception as e:
            raise CommunicationError(f"Failed to publish MQTT message: {traceback.format_exc()}")

    async def write_data(self, data: Dict[str, Any]) -> None:
        """Write data to MQTT (alias for publish)"""
        await self.publish(data)

    async def read_data(self) -> Dict[str, Any]:
        """Not implemented for MQTT - using callbacks instead"""
        raise NotImplementedError("MQTT adapter uses callbacks for reading data")        

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

    async def _handle_command_event(self, command_data: Dict[str, Any]):
        """Handle incoming device commands"""
        command = DeviceCommand(**command_data)
        command_id = str(uuid.uuid4())
        
        # Create initial status
        status = CommandStatus(
            command_id=command_id,
            status="PENDING"
        )
        self.command_statuses[command_id] = status
        
        await self.command_queue.put((command_id, command))
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
                status = await device.execute_command(
                    command.command,
                    command.params
                )
                status.command_id = command_id
                
                # Update command status
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
import traceback
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
                 communication_service: CommunicationService, mqtt:Optional[MQTTAdapter] = None):
        self.config = config
        self.event_manager = event_manager
        self.communication_service = communication_service
        self.i2c_adapter = None
        self.sensors = []
        self.mqtt = mqtt
        self.storage = TemperatureStorage(self.config['temperature_monitor']["database"]["path"])
        self.is_running = False
        print('*'*10, self.storage)

    async def initialize(self) -> None:
        logger.info("Initializing Temperature Monitor")
        # initialize DB to create table if not exist
        await self.storage.initialize()

        # Initialize I2C adapter
        ## TODO Need to decide how should we need to handle if we have multiple BUS
        self.i2c_adapter = I2CAdapter(self.config['temperature_monitor']['i2c_bus'])
        await self.i2c_adapter.connect()

        # Initialize sensors
        for sensor_config in self.config['temperature_monitor']['sensors']:
            sensor_class = self._get_sensor_class(sensor_config['type'])
            sensor = sensor_class(
                self.i2c_adapter,
                sensor_config['address'],
                sensor_config['id']
            )
            await sensor.initialize()
            self.sensors.append(sensor)

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
                    
                    print(data)
                    # Create reading
                    reading = TemperatureReading(
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
                            logger.error(f"Failed to publish reading: {traceback.format_exc()}")
                            # Will be synced later

                await asyncio.sleep(self.config['temperature_monitor']["reading_interval"])
            except Exception as e:
                logger.error(f"Error in monitoring loop: {traceback.format_exc()}")
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
                            logger.error(f"Failed to sync reading: {traceback.format_exc()}")
                            break  # Stop if MQTT is down
                    
                    # Mark successful syncs
                    synced_ids = [r.sensor_id for r in unsynced if r.is_synced]
                    if synced_ids:
                        await self.storage.mark_as_synced(synced_ids)

            except Exception as e:
                logger.error(f"error in sync loop: {traceback.format_exc()}")
            
            await asyncio.sleep(self.config['temperature_monitor']["sync_interval"])

    async def stop(self) -> None:
        self.is_running = False
        for sensor in self.sensors:
            if hasattr(sensor, "disconnect"):
                await sensor.disconnect()

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
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
import traceback

from iot_gateway.core.event_manager import EventManager
from iot_gateway.core.device_manager import DeviceManager
from iot_gateway.core.temperature_monitor import TemperatureMonitor
from iot_gateway.adapters.gpio import GPIOAdapter
from iot_gateway.core.communication_service import CommunicationService
from iot_gateway.api.routes import temp_router
from iot_gateway.api.endpoints.devices import device_router
from iot_gateway.utils.logging import setup_logging, get_logger
from iot_gateway.utils.exceptions import ConfigurationError, InitializationError

class ConfigManager:
    """Manages configuration loading and validation"""
    
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """Load and validate configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                if config is None:
                    raise ConfigurationError("Configuration file is empty or incorrectly formatted")
                
                # Validate required configuration sections
                required_sections = ['api', 'communication', 'gpio', 'temperature_monitor', 'logging']
                missing_sections = [section for section in required_sections if section not in config]
                if missing_sections:
                    raise ConfigurationError(f"Missing required configuration sections: {', '.join(missing_sections)}")
                
                return config
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing configuration file: {traceback.format_exc()}")
        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {config_path}")

class APIServer:
    """Handles API server initialization and management"""
    
    def __init__(self, config: Dict[str, Any], shutdown_event: asyncio.Event):
        self.config = config
        self.shutdown_event = shutdown_event
        self.logger = get_logger("API Server")
        self.app: Optional[FastAPI] = None

    async def initialize(self) -> FastAPI:
        """Initialize FastAPI application with routes"""
        try:
            self.app = FastAPI(
                title="IoT Gateway API",
                description="IoT Gateway service managing sensors and communication",
                version="1.0.0"
            )
            
            # Register routes
            self.app.include_router(temp_router, prefix="/api/v1")
            self.app.include_router(device_router, prefix="/api/v1")
            
            return self.app
        except Exception as e:
            raise InitializationError(f"Failed to initialize API server: {traceback.format_exc()}")

    async def start(self):
        """Start the API server"""
        if not self.app:
            await self.initialize()

        hypercorn_config = HyperConfig()
        try:
            host = self.config['api']['host']
            port = self.config['api']['port']
            hypercorn_config.bind = [f"{host}:{port}"]
            
            async def shutdown_trigger():
                await self.shutdown_event.wait()
                return
            
            self.logger.info(f"Starting API server on {host}:{port}")
            await serve(self.app, hypercorn_config, shutdown_trigger=shutdown_trigger)
        except Exception as e:
            self.logger.error(f"Failed to start API server: {traceback.format_exc()}")
            raise

class IoTGatewayApp:
    """Main IoT Gateway application class"""
    
    def __init__(self, config_path: str):
        self.logger = get_logger("Main App")
        try:
            self.config = ConfigManager.load_config(config_path)
            setup_logging(self.config.get('logging', {}))
        except ConfigurationError as e:
            self.logger.error(f"Configuration error: {traceback.format_exc()}")
            sys.exit(1)

        # Initialize components
        self.shutdown_event = asyncio.Event()
        self.event_manager = EventManager()
        self.api_server = APIServer(self.config, self.shutdown_event)
        
        # Components to be initialized later
        self.temperature_monitor = None
        self.communication_service = None
        self.device_manager = None

    async def initialize_components(self):
        """Initialize all application components"""
        try:
            # Start event processing
            asyncio.create_task(self.event_manager.process_events())
            
            # Initialize Communication Service
            self.communication_service = CommunicationService(self.config)
            await self.communication_service.initialize()
            
            # Initialize Device Manager
            self.device_manager = DeviceManager(
                self.event_manager,
                GPIOAdapter(self.config['gpio'])
            )
            await self.device_manager.initialize()
            
            # Initialize Temperature Monitor
            self.temperature_monitor = TemperatureMonitor(
                self.config,
                self.event_manager,
                self.communication_service,
                self.communication_service.mqtt
            )
            await self.temperature_monitor.initialize()
            
            self.logger.info("All components initialized successfully")
        except Exception as e:
            raise InitializationError(f"Failed to initialize components: {traceback.format_exc()}")

    async def start_temperature_monitoring(self):
        """Start temperature monitoring tasks"""
        try:
            monitor_task = asyncio.create_task(
                self.temperature_monitor.start_monitoring()
            )
            sync_task = asyncio.create_task(
                self.temperature_monitor.sync_stored_readings()
            )
            
            await asyncio.gather(monitor_task, sync_task)
        except Exception as e:
            self.logger.error(f"Error in temperature monitoring: {traceback.format_exc()}")
            await self.shutdown()

    async def shutdown(self):
        """Gracefully shutdown all components"""
        self.logger.info("Initiating shutdown sequence")
        try:
            if self.temperature_monitor:
                await self.temperature_monitor.stop()
            if self.communication_service:
                await self.communication_service.shutdown()
            # if self.device_manager:
            #     await self.device_manager.shutdown()
            
            self.shutdown_event.set()
            self.logger.info("Shutdown completed successfully")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Error during shutdown: {traceback.format_exc()}")

    def handle_signals(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}")
            asyncio.create_task(self.shutdown())

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, signal_handler)

    async def run(self):
        """Main application entry point"""
        try:
            self.handle_signals()
            await self.initialize_components()
            
            # Start all services
            # gather will not stop all the functions if anyone of the function failed, which is expected here.
            await asyncio.gather(
                self.start_temperature_monitoring(),
                self.api_server.start()
            )
        except InitializationError as e:
            self.logger.error(f"Initialization error: {traceback.format_exc()}")
            await self.shutdown()
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error: {traceback.format_exc()}")
            await self.shutdown()
            sys.exit(1)

def main():
    """Application entry point"""
    config_path = Path("src/config/default.yml")    
    app = IoTGatewayApp(str(config_path))
    asyncio.run(app.run())

if __name__ == "__main__":
    main()