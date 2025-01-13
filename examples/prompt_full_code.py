filepath: src/config/default.yml
code: 
api:
  host: "0.0.0.0"
  port: 8000

database:
  # path: "/var/lib/sensor_data/sensors.db"
  path: sensors.db
  pool_size: 5
  vacuum_interval: 86400  # Daily vacuum for optimization

sync:
  interval: 30  # sync interval in seconds
  batch_size: 100
  error_retry_interval: 5
  cache_size: 1000
  cache_expiry: 3600
  periodic_sync: false
  protocols:
    mqtt:
      enabled: true
      batch_size: 50
      retry_interval: 300
      qos: 1
    rest:
      enabled: true
      batch_size: 20
      retry_interval: 600
      timeout: 30

# config.yml
communication:
  mqtt:
    enabled: true
    host: "broker.emqx.io"
    port: 1883
    username: "user"
    password: "pass"
    client_id: "gateway"
    keepalive: 60
    reconnect_interval: 5.0
    max_reconnect_attempts: 5
    message_queue_size: 1000
    connection_timeout: 100
    subscribe_topics:
      - devices/smart_plug/plug1/command
      - gateway/#
      - temperature/ack
      - temperature/sync
  # Future communication configs
  # wifi:
  #   enabled: true
  #   ssid: "network"
  #   password: "pass"

devices:
  bulb1:
    enabled: true
    type: "bulb"
    pin: 5
    initial: false
  plug1:
    enabled: true
    type: "smart_plug"
    pin: 6
    initial: false
  device3:
    enabled: true
    type: "new_device"

system:
  device_id: "iot_gateway"
  heart_beat_interval: 60
  heart_beat_topic_prefix: "iot_gateway"

sensors:
  temperature:
    table_name: "humidity_readings"
    batch_size: 100
    max_age_days: 30
    reading_interval: 60
    i2c:
      - id: "sensor1"
        enabled: true
        bus: 1
        address: 0x48
        type: "TMP102"
        bus_number: 1  # specify which bus to use
        reading_interval: 60
        sync_interval: 300

      - id: "sensor2"
        enabled: true
        bus: 1
        address: 0x49
        type: "SHT31"
        bus_number: 2  # specify which bus to use
        reading_interval: 60
        sync_interval: 300
  
  humidity:
    table_name: "humidity_readings"
    batch_size: 100
    max_age_days: 30

      
  pressure:
    table_name: "pressure_readings"
    batch_size: 100
    max_age_days: 30

logging:
  level: "INFO"
  # level: "DEBUG"
  file: "logs/iot_gateway.log"
  max_size: 10  # MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"
logging:
  level: "INFO"
  file: "logs/iot_gateway.log"
  max_size: 10  # MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"

filepath: src/iot_gateway/devices/smart_plug.py
code: 
from iot_gateway.adapters.base import BaseDevice
from iot_gateway.models.device import CommandType, CommandStatus
from typing import Dict, Any, Optional
from iot_gateway.utils.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)

class SmartPlug(BaseDevice):
    """Implementation for smart plug devices"""
    def __init__(self, device_id: str, config: Dict[str, Any], gpio_adapter):
        super().__init__(device_id, config)
        self.gpio_adapter = gpio_adapter
        self.pin = config['pin']
        self.state = {
            "power": False,
            "power_consumption": 0.0,
            "voltage": 0.0
        }

    async def initialize(self) -> None:
        self.state["power"] = self.config.get("initial", False)
        logger.info(f"Initialized smart plug {self.device_id} on pin {self.pin}")

    async def execute_command(self, command_type: CommandType, params: Optional[Dict[str, Any]] = None) -> CommandStatus:
        try:
            if command_type == CommandType.TURN_ON:
                await self.gpio_adapter.write_data({
                    'device_id': self.device_id,
                    'state': True
                })
                self.state["power"] = True
                status = "SUCCESS"
                message = f"Smart plug {self.device_id} turned ON"
                
            elif command_type == CommandType.TURN_OFF:
                await self.gpio_adapter.write_data({
                    'device_id': self.device_id,
                    'state': False
                })
                self.state["power"] = False
                self.state["power_consumption"] = 0.0
                status = "SUCCESS"
                message = f"Smart plug {self.device_id} turned OFF"
                
            else:
                status = "FAILED"
                message = f"Unknown command for smart plug: {command_type}"

            return CommandStatus(
                command_id="",
                status=status,
                message=message,
                executed_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error executing command on smart plug {self.device_id}: {e}")
            return CommandStatus(
                command_id="",
                status="FAILED",
                message=str(e),
                executed_at=datetime.now()
            )

    async def get_state(self) -> Dict[str, Any]:
        if self.state["power"]:
            self.state["power_consumption"] = 120.5  
            self.state["voltage"] = 220.0
        return self.state
    
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
                command_id="",
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
code: 
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


class CANSensor(ABC):
    """
    Base class for all CAN sensors.
    Each sensor type should implement this interface.
    """
    def __init__(self, can_adapter, arbitration_id: int, sensor_id: str):
        self.can = can_adapter
        self.arbitration_id = arbitration_id
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


class ModbusSensor(ABC):
    """
    Base class for all Modbus sensors.
    Each sensor type should implement this interface.
    """
    def __init__(self, modbus_adapter, slave_address: int, sensor_id: str):
        self.modbus = modbus_adapter
        self.slave_address = slave_address
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

filepath: src/iot_gateway/adapters/gpio.py
code: 
from typing import Dict, Any
# import RPi.GPIO as GPIO
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class GPIOAdapter(CommunicationAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pins: Dict[str, int] = {}
        self.initialized = False

    async def connect(self) -> None:
        try:
            # GPIO.setmode(GPIO.BCM)
            for _, pin_config in self.config.items():
                pin = pin_config['pin']
                # GPIO.setup(pin, GPIO.OUT)
                self.pins[pin_config['type']] = pin
            self.initialized = True
            logger.info("GPIO adapter initialized")
        except Exception as e:
            logger.error(f"GPIO initialization failed: {e}")
            raise

    async def disconnect(self) -> None:
        if self.initialized:
            # GPIO.cleanup()
            self.initialized = False
            logger.info("GPIO adapter cleaned up")

    async def read_data(self) -> Dict[str, Any]:
        if not self.initialized:
            raise RuntimeError("GPIO not initialized")
        
        states = {}
        for device_id, pin in self.pins.items():
            # states[device_id] = GPIO.input(pin)
            states[device_id] = pin
        return states

    async def write_data(self, data: Dict[str, Any]) -> None:
        if not self.initialized:
            raise RuntimeError("GPIO not initialized")
        
        device_id = data.get('device_id')
        state = data.get('state')
        
        if device_id not in self.pins:
            raise ValueError(f"Unknown device ID: {device_id}")
        
        pin = self.pins[device_id]
        # GPIO.output(pin, state)
        logger.info(f"Set {device_id} (PIN {pin}) to {state}")

filepath: src/iot_gateway/adapters/i2c.py
code: 
import smbus2
import asyncio
from typing import List
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class I2CAdapter(CommunicationAdapter):
    def __init__(self, bus_number: int):
        self.bus_number = bus_number
        self.bus = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5  # seconds

    async def connect(self) -> None:
        for attempt in range(self._retry_count):
            try:
                # self.bus = smbus2.SMBus(self.bus_number)
                self.is_connected = True
                logger.info(f"Connected to I2C bus {self.bus_number}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to connect to I2C bus {self.bus_number} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to connect to I2C bus {self.bus_number} after {self._retry_count} attempts")
                    raise

    async def disconnect(self) -> None:
        if self.bus:
            try:
                self.bus.close()
                self.is_connected = False
                logger.info(f"Disconnected from I2C bus {self.bus_number}")
            except Exception as e:
                logger.error(f"Error disconnecting from I2C bus {self.bus_number}: {e}")
                raise

    async def read_bytes(self, address: int, register: int, num_bytes: int) -> bytes:
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                # data = self.bus.read_i2c_block_data(address, register, num_bytes)
                data = f"dummy {attempt + 1}/{self._retry_count}"
                return bytes(data)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to read from I2C device 0x{address:02x} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to read from I2C device 0x{address:02x} after {self._retry_count} attempts")
                    raise

    async def write_bytes(self, address: int, register: int, data: bytes) -> None:
        """Write bytes to an I2C device with retry mechanism"""
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                # self.bus.write_i2c_block_data(address, register, list(data))
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to write to I2C device 0x{address:02x} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to write to I2C device 0x{address:02x} after {self._retry_count} attempts")
                    raise

    async def read_byte(self, address: int, register: int) -> int:
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                return self.bus.read_byte_data(address, register)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to read byte from I2C device 0x{address:02x} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to read byte from I2C device 0x{address:02x} after {self._retry_count} attempts")
                    raise

    async def write_byte(self, address: int, register: int, value: int) -> None:
        if not self.is_connected:
            raise RuntimeError("I2C bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                # self.bus.write_byte_data(address, register, value)
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to write byte to I2C device 0x{address:02x} failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to write byte to I2C device 0x{address:02x} after {self._retry_count} attempts")
                    raise

    def read_data(self):
        pass

    def write_data(self, data):
        pass
                    
filepath: src/iot_gateway/adapters/mqtt.py
code: 
import asyncio
from typing import Dict, Any, Callable, Optional, Union, List, Set
from pydantic import BaseModel, Field
import aiomqtt as mqtt
import json
import traceback
from ..adapters.base import CommunicationAdapter
from ..utils.logging import get_logger
from ..utils.exceptions import CommunicationError
from contextlib import asynccontextmanager
import random

logger = get_logger(__name__)

'''
usage Examples

await mqtt_adapter.connect()
await mqtt_adapter.subscribe("test/topic", message_handler)

await mqtt_adapter.publish({
    "topic": "test/topic",
    "payload": {"key": "value"},
    "qos": 1
})

await mqtt_adapter.disconnect()

'''


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
    message_queue_size: int = Field(1000, description="Maximum size of message queue")

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
            raise CommunicationError(f"Invalid MQTT configuration: {str(e)}")

        self.client: Optional[mqtt.Client] = None
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.pending_subscriptions: Set[str] = set()
        self.connected = asyncio.Event()
        self._stop_flag = asyncio.Event()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._message_processor_task: Optional[asyncio.Task] = None
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=self.config.message_queue_size)
        self._subscription_lock = asyncio.Lock()

    async def _subscribe_topics(self) -> None:
        """Subscribe to all stored topics"""
        async with self._subscription_lock:
            for topic, handlers in self.message_handlers.items():
                if self.client:
                    try:
                        await self.client.subscribe(topic)
                        logger.info(f"Resubscribed to topic: {topic}")
                    except Exception as e:
                        logger.error(f"Failed to resubscribe to topic {topic}: {str(e)}")
                        self.pending_subscriptions.add(topic)
                
    @staticmethod
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
                    identifier=f"{self.config.client_id}_{random.randint(1000, 9999)}",
                    tls_context=True if self.config.ssl else None
                ) as client:
                    self.client = client
                    self.connected.set()
                    logger.info("Connected to MQTT broker")
                    await self._subscribe_topics()  # Add subscription here when connection is established
                   
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


    async def _process_messages(self) -> None:
        """Process incoming MQTT messages"""
        while not self._stop_flag.is_set():
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
                                logger.debug(f"received {payload} from {topic}")
                            except json.JSONDecodeError:
                                pass  # Keep payload as string if not JSON

                            # Queue message for processing
                            try:
                                await self._message_queue.put((topic, payload))
                            except asyncio.QueueFull:
                                logger.warning("Message queue full, dropping message")
                                continue

                        except Exception as e:
                            logger.error(f"Error processing message on topic {topic}: {str(e)}")

            except Exception as e:
                if not self._stop_flag.is_set():
                    logger.error(f"Error in message processing loop: {str(e)}")

    async def _process_message_queue(self) -> None:
        """Process messages from the queue"""
        while not self._stop_flag.is_set():
            try:
                topic, payload = await self._message_queue.get()
                if topic in self.message_handlers:
                    for handler in self.message_handlers[topic]:
                        try:
                            await handler(topic, payload)
                        except Exception as e:
                            logger.error(f"Error in message handler for topic {topic}: {str(e)}")
                self._message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing queued message: {traceback.format_exc()}")
                await asyncio.sleep(1)

    
    async def connect(self) -> None:
        """Connect to MQTT broker and start message processing"""
        try:
            self._stop_flag.clear()
            self._message_processor_task = asyncio.create_task(self._process_messages())
            asyncio.create_task(self._process_message_queue())
        except Exception as e:
            raise CommunicationError(f"Failed to start MQTT adapter: {str(e)}")

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker and cleanup"""
        try:
            self._stop_flag.set()
            
            # Cancel all running tasks
            tasks = [self._message_processor_task]
            if self._reconnect_task:
                tasks.append(self._reconnect_task)
            
            for task in tasks:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Clear state
            self.connected.clear()
            self.pending_subscriptions.clear()
            await self._message_queue.join()  # Wait for queued messages to be processed
            
            logger.info("MQTT adapter stopped")
        except Exception as e:
            raise CommunicationError(f"Error disconnecting from MQTT: {str(e)}")

    async def subscribe(self, topic: str, handler: Callable[[str, Any], None]) -> None:
        """Subscribe to MQTT topic with handler"""
        async with self._subscription_lock:
            try:
                if topic not in self.message_handlers:
                    self.message_handlers[topic] = []
                    if self.client and self.connected.is_set():
                        await self.client.subscribe(topic)
                    else:
                        self.pending_subscriptions.add(topic)
                
                self.message_handlers[topic].append(handler)
                logger.info(f"Subscribed to topic: {topic}")
            except Exception as e:
                raise CommunicationError(f"Failed to subscribe to topic {topic}: {str(e)}")
            
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
        """Publish message to MQTT topic with retry logic"""
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

            attempt = 0
            while attempt < self.config.max_reconnect_attempts:
                try:
                    if self.client:
                        await self.client.publish(
                            topic=message.topic,
                            payload=payload,
                            qos=message.qos,
                            retain=message.retain
                        )
                        logger.debug(f"Published to {message.topic}")
                        return
                except Exception as e:
                    attempt += 1
                    if attempt >= self.config.max_reconnect_attempts:
                        raise
                    logger.warning(f"Publish attempt {attempt} failed, retrying...")
                    await asyncio.sleep(self.config.reconnect_interval)

        except Exception as e:
            raise CommunicationError(f"Failed to publish MQTT message: {str(e)}")
        
    async def write_data(self, data: Dict[str, Any]) -> None:
        """Write data to MQTT (alias for publish)"""
        await self.publish(data)

    async def read_data(self) -> Dict[str, Any]:
        """Not implemented for MQTT - using callbacks instead"""
        raise NotImplementedError("MQTT adapter uses callbacks for reading data")
        
filepath: src/iot_gateway/api/endpoints/devices.py
code: 
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ...models.device import DeviceCommand, CommandStatus
from ...core.device_manager import DeviceManager
from ...utils.logging import get_logger

logger = get_logger(__name__)

device_router = APIRouter()

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
        
filepath: src/iot_gateway/api/routes.py
code: 
# src/iot_gateway/api/routes.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta
from ..models.things import TemperatureReading
from .dependencies import DBDependency

temp_router = APIRouter()

@temp_router.get(
    "/temperature/{sensor_id}",
    response_model=List[TemperatureReading]
)
async def get_temperature_readings(
    sensor_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: DBDependency = None
) -> List[TemperatureReading]:
    try:
        readings = await db.repositories['temperature'].get_readings(
            sensor_id,
            start_time or datetime.now() - timedelta(hours=24),
            end_time or datetime.now()
        )
        return readings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
filepath: src/iot_gateway/api/dependencies.py
code:
# src/iot_gateway/api/dependencies.py
from fastapi import Request
from typing import Annotated
from fastapi import Depends
from ..storage.sensor_database import SensorDatabase
from ..core.temperature_monitor import TemperatureMonitor
from ..core.device_manager import DeviceManager
from ..core.heartbeat import SystemMonitor

async def get_db(request: Request) -> SensorDatabase:
    return request.app.state.components.db

async def get_temperature_monitor(request: Request) -> TemperatureMonitor:
    return request.app.state.components.temperature_monitor

async def get_device_manager(request: Request) -> DeviceManager:
    return request.app.state.components.device_manager

async def get_system_monitor(request: Request) -> SystemMonitor:
    return request.app.state.components.system_monitor

# Type definitions for dependencies
DBDependency = Annotated[SensorDatabase, Depends(get_db)]
TempMonitorDependency = Annotated[TemperatureMonitor, Depends(get_temperature_monitor)]
DeviceManagerDependency = Annotated[DeviceManager, Depends(get_device_manager)]
SystemMonitorDependency = Annotated[SystemMonitor, Depends(get_system_monitor)]

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

    async def submit_command(self, command: DeviceCommand) -> str:
        command_id = await self._handle_command_event(command.model_dump())
        return command_id

    async def _handle_command_event(self, command_data: Dict[str, Any]) -> str:
        command = DeviceCommand(**command_data)
        command_id = str(uuid.uuid4())
        
        # Create initial status with only the required fields from the model
        status = CommandStatus(
            command_id=command_id,
            status="PENDING"  # Required field
        )
        self.command_statuses[command_id] = status
        
        # Add to processing queue
        await self.command_queue.put((command_id, command))
        
        # Publish command accepted event
        await self.event_manager.publish(
            "device.command.accepted",
            {
                "command_id": command_id,
                "device_id": command.device_id,
                "command": command.command.value,
                "params": command.params,
                "timestamp": command.timestamp.isoformat(),
                "status": "PENDING"
            }
        )
        
        return command_id

    async def _process_commands(self):
        while True:
            command_id, command = await self.command_queue.get()
            try:
                device = self.devices.get(command.device_id)
                if not device:
                    raise ValueError(f"Unknown device: {command.device_id}")

                # Execute command on the device
                result = await device.execute_command(
                    command.command,
                    command.params
                )
                
                # Update command status
                status = CommandStatus(
                    command_id=command_id,
                    status="COMPLETED",
                    executed_at=datetime.now()
                )
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
        return self.command_statuses.get(command_id)

    async def get_device_state(self, device_id: str) -> Dict[str, Any]:
        device = self.devices.get(device_id)
        if not device:
            raise ValueError(f"Unknown device: {device_id}")
        return await device.get_state()

    async def cleanup(self):
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
import asyncio
from ..adapters.mqtt import MQTTAdapter
from ..utils.logging import get_logger
from ..utils.exceptions import CommunicationError
from ..handlers.mqtt_handlers import MQTTMessageHandlers

logger = get_logger(__name__)

class CommunicationService:
    def __init__(self, config: Dict[str, Any], event_manager = None):
        self.config = config
        self.communication_config = config['communication']
        self.mqtt: Optional[MQTTAdapter] = None
        self._mqtt_connection_timeout = self.communication_config['mqtt'].get('connection_timeout', 90)  # seconds
        self.handlers = MQTTMessageHandlers(event_manager)
        self.handler_mapping = None
        # Future communication adapters
        # self.wifi = None 
        # self.bluetooth = None

    async def _wait_for_mqtt_connection(self) -> None:
        """Wait for MQTT connection to be established"""
        try:
            # Wait for the connected event to be set
            await asyncio.wait_for(
                self.mqtt.connected.wait(),
                timeout=self._mqtt_connection_timeout
            )
        except asyncio.TimeoutError:
            raise CommunicationError(
                f"MQTT connection timeout after {self._mqtt_connection_timeout} seconds"
            )

    async def initialize(self) -> None:
        logger.info(f"Initializing Communication Service")
        # Initialize MQTT
        if 'mqtt' in self.communication_config and self.communication_config['mqtt']['enabled']:
            try:
                self.mqtt = MQTTAdapter(self.communication_config['mqtt'])
                await self.mqtt.connect()
                logger.info("Mqtt service started")
                # Wait for connection to be established
                await self._wait_for_mqtt_connection()
                logger.info("MQTT connection established")
                
                # Subscribe to configured topics
                await self._subscribe_to_topics()
                
                logger.info("MQTT service fully initialized")
            except Exception as e:
                logger.error(f"Failed to initialize MQTT service: {str(e)}")
                if self.mqtt:
                    await self.mqtt.disconnect()
                raise CommunicationError(f"MQTT initialization failed: {str(e)}")

        # Future initializations
        # if 'wifi' in self.config:
        #     self.wifi = WiFiAdapter(self.config['wifi'])
        #     await self.wifi.connect()

    async def _subscribe_to_topics(self) -> None:
        """Subscribe to configured MQTT topics"""
        if 'subscribe_topics' not in self.communication_config['mqtt']:
            logger.warning("No MQTT topics configured for subscription")
            return
        
        # Map topic patterns to specific handlers
        self.handler_mapping = {
            'devices/smart_plug/plug1/command': self.handlers.smart_plug_handler,
            'gateway/#': MQTTAdapter.message_handler,
            'temperature/ack': self.handlers.temperature_ack_handler,
            'temperature/sync': self.handlers.temperature_sync_handler
            # Add more mappings as needed
        }

        # Add Acknowledgement handlers for all temperature sensors
        for topic in self.communication_config['mqtt']['subscribe_topics']:
            # topic = topic_config['topic']
            # handler = topic_config.get('handler')            
            if not self.handler_mapping.get(topic):
                continue
            try:
                await self.mqtt.subscribe(topic, self.handler_mapping.get(topic))
                logger.info(f"Subscribed to topic: {topic}")
            except Exception as e:
                logger.error(f"Failed to subscribe to topic {topic}: {str(e)}")
                raise CommunicationError(f"Topic subscription failed: {str(e)}")

        

    async def shutdown(self) -> None:
        logger.info("Shutting down communication services")
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
from ..sensors.temperature import TMP102Sensor, SHT31Sensor
from ..models.things import TemperatureReading
from ..utils.logging import get_logger
from ..models.things import DeviceType

logger = get_logger(__name__)

class TemperatureMonitor:
    def __init__(self, config: Dict[str, Any], event_manager, db,
                 mqtt: Optional[MQTTAdapter] = None):
        self.config = config
        self.event_manager = event_manager
        self.i2c_adapters: Dict[int, I2CAdapter] = {}  # Support multiple buses
        self.sensors = []
        self.mqtt = mqtt
        self.db = db
        self.is_running = False
        self._sensor_read_lock = asyncio.Lock()  # Prevent concurrent sensor reads

        
    async def initialize(self) -> None:
        logger.info("Initializing Temperature Monitor")

        # Register handler for ack events
        await self.event_manager.subscribe('temperature_ack', self.handle_temperature_ack)
        await self.event_manager.subscribe('sync_temperature', self.get_unsynced_temp_data)

        # await self.storage.initialize()

        # Initialize I2C adapters for each configured bus
        for sensor in self.config['sensors']['temperature']['i2c']:
            if sensor['enabled']:
                bus_number = sensor['bus_number']
                adapter = I2CAdapter(bus_number)
                try:
                    await adapter.connect()
                    self.i2c_adapters[bus_number] = adapter
                except Exception as e:
                    logger.error(f"Failed to initialize I2C bus {bus_number}: {e}")
                    continue

        # Initialize sensors
        for sensor_config in self.config['sensors']['temperature']['i2c']:
            try:

                if sensor_config['enabled']:
                    bus_number = sensor_config.get('bus_number', 1)  # Default to bus 1
                    if bus_number not in self.i2c_adapters:
                        logger.error(f"I2C bus {bus_number} not available for sensor {sensor_config['id']}")
                        continue

                    sensor_class = self._get_sensor_class(sensor_config['type'])
                    if not sensor_class:
                        logger.error(f"Unknown sensor type: {sensor_config['type']}")
                        continue

                    sensor = sensor_class(
                        self.i2c_adapters[bus_number],
                        sensor_config['address'],
                        sensor_config['id']
                    )
                    # First register the device
                    await self.db.register_device(
                        device_id=sensor_config['id'],
                        device_type=DeviceType.TEMPERATURE,
                        name=f"Temperature Sensor {sensor_config['id']}",
                        location="Room 1"
                    )

                    await sensor.initialize()
                    self.sensors.append(sensor)
                    logger.info(f"Initialized sensor {sensor_config['id']} on bus {bus_number}")
            except Exception as e:
                logger.error(f"Failed to initialize sensor {sensor_config['id']}: {traceback.format_exc()}")

        if not self.sensors:
            logger.warning("No sensors were successfully initialized")
        else:
            logger.info(f"Temperature monitor initialized with {len(self.sensors)} sensors")

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
                        **data
                    )
                    print(reading)
                    
                    if self.mqtt.connected.is_set():
                        # Publish reading
                        try:
                            await self.mqtt.write_data({
                                "topic": f"temperature/{reading.device_id}",
                                "payload": reading.model_dump_json()
                            })
                            # reading.is_synced = True
                        except Exception as e:
                            logger.error(f"Failed to publish reading: {traceback.format_exc()}")

                    # Store reading
                    await self.db.repositories['temperature'].store_reading(reading)
                    # await self.storage.store_reading(reading)

                await asyncio.sleep(self.config['sensors']['temperature']['reading_interval'])
            except Exception as e:
                logger.error(f"Error in monitoring loop: {traceback.format_exc()}")
                await asyncio.sleep(self.config['sync']['error_retry_interval'])  # Wait before retry

    async def sync_stored_readings(self, internal_sync_call:bool = False) -> None:
        if not self.config['sync']['periodic_sync']:
            logger.info("Periodic Sync is disabled")
            return False
        
        while self.is_running:
            try:
                # Get unsynced readings
                await self.sync_temperature_readings()

            except Exception as e:
                logger.error(f"error in sync loop: {traceback.format_exc()}")
            
            logger.info(f'Syncing will happen after {self.config["sync"]["interval"]} seconds')
            await asyncio.sleep(self.config['sync']["interval"])

    async def sync_temperature_readings(self, topic: str=None, device_ids:list=None):
        """Retrieve unsynced data and push via mqtt"""
        unsynced = await self.db.sync_manager.get_all_unsynced_readings()
        unsynced_temp_data = unsynced.get('temperature')
        if unsynced_temp_data:
            logger.info(f"Sending {len(unsynced_temp_data)} stored unsynced readings")
            for reading in unsynced_temp_data:
                try:
                    if self.mqtt.connected.is_set():
                        send_topic = f"temperature/{reading.device_id}"
                        sensor_data = reading.model_dump_json()

                        # set resend_topic id if supplied
                        if topic:
                            send_topic = topic

                        # don't send if not specific device_id
                        
                        if device_ids and reading.device_id not in device_ids:
                            continue
                        
                        await self.mqtt.write_data({
                            "topic": send_topic,
                            "payload": sensor_data
                        })

                except Exception as e:
                    logger.error(f"Failed to sync reading: {traceback.format_exc()}")
                    break  # Stop if MQTT is down


    async def handle_temperature_ack(self, topic: str, payload: Any) -> None:
        """Handle acknowledgment messages for temperature readings"""
        try:
            # Extract sensor_id and reading_id from payload
            logger.debug(f"Handling temperature acknowledgement - {topic}: {[payload]}")
            sensor_id = payload.get('device_id')
            reading_id = payload.get('reading_id')
            
            if not all([sensor_id, reading_id]):
                logger.error(f"Invalid acknowledgment payload: {payload}")
                return
            
            # Mark the reading as synced in the database
            # Mark as synced
            await self.db.repositories['temperature'].mark_as_synced(
                device_id=sensor_id,
                reading_id=reading_id
            )
            # logger.info(f"Marked reading {reading_id} from sensor {sensor_id} as synced")

        except Exception as e:
            logger.error(f"Error handling temperature acknowledgment: {traceback.format_exc()}")

    async def get_unsynced_temp_data(self, topic:str=None, payload=None):
        try:
            # Extract device_id and resend topic
            logger.debug(f"Getting unsynced temperature_data - {topic}: {payload}")
            device_ids = payload.get("device_ids")
            resend_topic = payload.get("resend_topic")

            await self.sync_temperature_readings(topic=resend_topic, device_ids=device_ids)
        except Exception as e:
            logger.error(f"Error while getting unsynced temperature data: {e}")

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
from typing import Dict, Any
class BusinessProcessor:
    def __init__(self, rules_config: Dict[str, Any]):
        self.rules = rules_config

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        processed_data = ""
        return processed_data
    
filepath: src/iot_gateway/sensors/temperature.py
code:
from typing import Dict, Any
from ..adapters.base import I2CSensor
from ..utils.logging import get_logger
import traceback
from ..utils.helpers import generate_msg_id

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
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # await self.i2c.write_byte(self.address, self.CONFIG_REGISTER, 0x60)

            logger.info(f"Initialized TMP102 sensor {self.sensor_id}")
        except Exception as e:
            logger.error(f"Failed to initialize TMP102 sensor {self.sensor_id}: {traceback.format_exc()}")
            raise

    async def read_data(self) -> Dict[str, Any]:
        """Read and convert temperature data."""
        try:
            # Read temperature register
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # data = await self.i2c.read_bytes(self.address, self.TEMP_REGISTER, 2)

            data = "Hello".encode("UTF-8")
            
            # Convert to temperature
            temp_c = ((data[0] << 8) | data[1]) / 256.0
            temp_f = (temp_c * 9/5) + 32
            
            logger.debug(f"Sensor {self.sensor_id} read: {temp_c}°C / {temp_f}°F")
            return {
                "device_id": self.sensor_id,
                "celsius": round(temp_c, 2),
                "fahrenheit": round(temp_f, 2),
                "reading_id": generate_msg_id(self.sensor_id)
            }
        except Exception as e:
            logger.error(f"Error reading TMP102 sensor {self.sensor_id}: {traceback.format_exc()}")
            raise

    async def get_config(self) -> Dict[str, Any]:
        """Get current sensor configuration."""
        ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
        # config = await self.i2c.read_byte(self.address, self.CONFIG_REGISTER)

        config = True
        return {
            "device_id": self.sensor_id,
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
        # Read temperature register
        ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
        # data = await self.i2c.read_bytes(self.address, self.TEMP_REGISTER, 2)

        data = "sensor2".encode("UTF-8")
        
        # Convert to temperature
        temp_c = ((data[0] << 8) | data[1]) / 256.0
        temp_f = (temp_c * 9/5) + 32
        
        logger.debug(f"Sensor {self.sensor_id} read: {temp_c}°C / {temp_f}°F")
        return {
                "device_id": self.sensor_id,
                "celsius": round(temp_c, 2),
                "fahrenheit": round(temp_f, 2),
                "reading_id": generate_msg_id(self.sensor_id)
            }

    async def get_config(self) -> Dict[str, Any]:
        # Implementation for SHT31
        pass

filepath: src/iot_gateway/storage/database.py
code: 
from typing import List, Dict, Any, Optional, Type, Generic, TypeVar
import aiosqlite
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from abc import ABC, abstractmethod

from ..utils.logging import get_logger
from ..models.things import TemperatureReading
from ..utils.exceptions import ConnectionPoolError, DatabaseError


logger = get_logger(__name__)

# Type definitions
T = TypeVar('T')


class ConnectionPool:
    """Manages a pool of database connections"""
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self._active_connections = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the connection pool"""
        logger.info(f"Initializing connection pool with {self.max_connections} connections")
        try:
            for _ in range(self.max_connections):
                conn = await aiosqlite.connect(self.db_path)
                await conn.execute('PRAGMA journal_mode=WAL')
                await conn.execute('PRAGMA foreign_keys=ON')
                await self._pool.put(conn)
                self._active_connections += 1
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise ConnectionPoolError(f"Connection pool initialization failed: {e}")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        connection = None
        try:
            async with self._lock:
                if self._pool.empty() and self._active_connections < self.max_connections:
                    # Create new connection if pool is empty and we haven't reached max
                    connection = await aiosqlite.connect(self.db_path)
                    await connection.execute('PRAGMA journal_mode=WAL')
                    await connection.execute('PRAGMA foreign_keys=ON')
                    self._active_connections += 1
                else:
                    # Wait for available connection with timeout
                    try:
                        connection = await asyncio.wait_for(self._pool.get(), timeout=5.0)
                    except asyncio.TimeoutError:
                        raise ConnectionPoolError("Timeout waiting for database connection")

            yield connection

        finally:
            if connection:
                try:
                    await self._pool.put(connection)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    # If we can't return to pool, close it and create new one
                    await connection.close()
                    async with self._lock:
                        self._active_connections -= 1

    async def close(self):
        """Close all connections in the pool"""
        while not self._pool.empty():
            conn = await self._pool.get()
            await conn.close()
        self._active_connections = 0



class BaseRepository(ABC, Generic[T]):
    """Abstract base class for sensor repositories"""
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        self.table_name: str = ""  # Must be set by implementing classes

    @abstractmethod
    async def create_table(self) -> None:
        """Create the repository's table"""
        pass

    @abstractmethod
    async def store_reading(self, reading: T) -> None:
        """Store a reading in the database"""
        pass

    @abstractmethod
    async def get_readings(
        self,
        device_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[T]:
        """Retrieve readings for a device within a time range"""
        pass

    async def create_indices(self) -> None:
        """Create indices for the repository's table"""
        pass

    async def get_unsynced_readings(self) -> List[T]:
        """Retrieve all unsynced readings for this sensor type."""
        try:
            async with self.pool.acquire() as conn:
                conn.row_factory = aiosqlite.Row
                query = f'SELECT * FROM {self.table_name} WHERE is_synced = 0'
                async with conn.execute(query) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_reading(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get unsynced readings from {self.table_name}: {e}")
            raise DatabaseError(f"Failed to get unsynced readings: {e}")

    async def bulk_mark_as_synced(self, device_ids: List[str], reading_ids: List[str]) -> None:
        """Mark multiple readings as synced."""
        if not device_ids or not reading_ids:
            return

        try:
            async with self.pool.acquire() as conn:
                placeholders_devices = ','.join(['?' for _ in device_ids])
                placeholders_readings = ','.join(['?' for _ in reading_ids])
                
                query = f'''
                    UPDATE {self.table_name} 
                    SET is_synced = 1 
                    WHERE device_id IN ({placeholders_devices})
                    AND reading_id IN ({placeholders_readings})
                '''
                
                await conn.execute(query, [*device_ids, *reading_ids])
                await conn.commit()
                logger.debug(f"Marked {len(reading_ids)} readings as synced in {self.table_name}")
        except Exception as e:
            logger.error(f"Failed to bulk mark readings as synced in {self.table_name}: {e}")
            raise DatabaseError(f"Failed to bulk mark readings as synced: {e}")

    async def mark_as_synced(self, device_id: str, reading_id: str) -> None:
        """Mark a single reading as synced."""
        if not device_id or not reading_id:
            return

        try:
            async with self.pool.acquire() as conn:
                query = f'''
                    UPDATE {self.table_name} 
                    SET is_synced = 1 
                    WHERE device_id = ? AND reading_id = ?
                '''
                await conn.execute(query, (device_id, reading_id))
                await conn.commit()
                logger.info(f"Marked reading {reading_id} as synced in {self.table_name}")
        except Exception as e:
            logger.error(f"Failed to mark reading as synced in {self.table_name}: {e}")
            raise DatabaseError(f"Failed to mark reading as synced: {e}")

    @abstractmethod
    def _row_to_reading(self, row: Dict[str, Any]) -> T:
        """Convert a database row to a reading object"""
        pass

filepath: src/iot_gateway/storage/device_stats.py
from typing import Dict, Any, Optional, List
from ..models.things import HearBeat
from datetime import datetime
from ..storage.database import ConnectionPool, BaseRepository
import aiosqlite
from ..utils.logging import get_logger
from ..utils.exceptions import DatabaseError


logger = get_logger(__name__)

class SystemMonitorRepository(BaseRepository[HearBeat]):
    def __init__(self, pool: ConnectionPool):
        super().__init__(pool)
        self.table_name = "system_heartbeats"

    async def create_table(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS system_heartbeats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    reading_id TEXT NOT NULL,
                    temperature TEXT NOT NULL,
                    available_memory TEXT NOT NULL,
                    cpu_usage TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_synced BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id),
                    UNIQUE(device_id, reading_id)
                )
            ''')
            await conn.commit()

    async def create_indices(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_heartbeat_device_time 
                ON system_heartbeats(device_id, timestamp)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_heartbeat_sync 
                ON system_heartbeats(is_synced)
            ''')
            await conn.commit()

    async def store_reading(self, reading: HearBeat) -> None:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO system_heartbeats 
                    (device_id, reading_id, temperature, available_memory, cpu_usage, 
                     timestamp, is_synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    reading.device_id,
                    reading.reading_id,
                    reading.temperature,
                    reading.available_memory,
                    reading.cpu_usage,
                    reading.timestamp,
                    reading.is_synced
                ))
                await conn.commit()
                logger.debug("Stored system metrics successfully")
        except Exception as e:
            logger.error(f"Failed to store system heartbeat: {e}")
            raise DatabaseError(f"Failed to store system heartbeat: {e}")
        

    async def get_readings(
        self,
        device_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[HearBeat]:
        """
        Retrieve system heartbeat readings for a device within a specified time range.
        
        Args:
            device_id: The ID of the device to get readings for
            start_time: Start of the time range
            end_time: End of the time range
            limit: Optional limit on number of readings to return
            
        Returns:
            List of HearBeat objects ordered by timestamp descending
        """
        query = '''
            SELECT * FROM system_heartbeats 
            WHERE device_id = ? 
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        '''
        params = [device_id, start_time, end_time]
        
        if limit is not None:
            query += ' LIMIT ?'
            params.append(limit)

        try:
            async with self.pool.acquire() as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_reading(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get system heartbeat readings: {e}")
            raise DatabaseError(f"Failed to get system heartbeat readings: {e}")
        

    def _row_to_reading(self, row: Dict[str, Any]) -> HearBeat:
        return HearBeat(
            device_id=row['device_id'],
            reading_id=row['reading_id'],
            temperature=row['temperature'],
            available_memory=row['available_memory'],
            cpu_usage=row['cpu_usage'],
            timestamp=row['timestamp'],
            is_synced=bool(row['is_synced'])
        )
    
filepath: src/iot_gateway/storage/sensor_database.py
code:from ..storage.database import ConnectionPool
from ..storage.temp_db import TemperatureRepository
from ..storage.device_stats import SystemMonitorRepository
from ..storage.sync_manager import SyncManager
from ..models.things import DeviceType
from ..utils.logging import get_logger
from ..utils.exceptions import DatabaseError
from typing import Optional

logger = get_logger(__name__)

class SensorDatabase:
    """Main database manager class"""
    def __init__(self, db_path: str, max_connections: int = 5):
        self.pool = ConnectionPool(db_path, max_connections)
        self.repositories = {}
        self.sync_manager = SyncManager(self)
        self._setup_repositories()
        # Add other repositories as needed
        self._retention_days = 30

    def _setup_repositories(self):
        """Initialize all repository instances"""
        self.repositories['temperature'] = TemperatureRepository(self.pool)
        self.repositories['system'] = SystemMonitorRepository(self.pool)
        # Add other repositories as needed
        # self.repositories['humidity'] = HumidityRepository(self.pool)
        # self.repositories['smart_plug'] = SmartPlugRepository(self.pool)

    async def initialize(self) -> None:
        """Initialize the database and all repositories"""
        await self.pool.initialize()
        
        async with self.pool.acquire() as conn:
            # Create devices table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    device_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP
                )
            ''')
            await conn.commit()

        # Initialize all repositories
        for repo in self.repositories.values():
            await repo.create_table()
            await repo.create_indices()

    async def register_device(self, device_id: str, device_type: DeviceType, name: str, location: Optional[str] = None) -> None:
        """Register a new device in the database."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT OR REPLACE INTO devices 
                    (device_id, device_type, name, location, last_seen)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (device_id, device_type.value, name, location))
                await conn.commit()
                logger.info(f"Registered device: {device_id} of type {device_type.value}")
        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            raise DatabaseError(f"Failed to register device: {e}")


    async def close(self) -> None:
        """Close all database connections"""
        await self.pool.close()

file path :src/iot_gateway/storage/sync_manager.py
code: 
import asyncio
from typing import Dict, List, Any
# from ..storage.sensor_database import SensorDatabase

class SyncManager:
    """Manages synchronization operations across all repositories"""
    def __init__(self, db):
        self.db = db
        self._sync_lock = asyncio.Lock()

    async def get_all_unsynced_readings(self) -> Dict[str, List[Any]]:
        """Get all unsynced readings from all repositories"""
        async with self._sync_lock:
            results = {}
            for repo_name, repo in self.db.repositories.items():
                results[repo_name] = await repo.get_unsynced_readings()
            return results

    async def bulk_mark_as_synced(self, 
                                repository_name: str,
                                device_ids: List[str], 
                                reading_ids: List[str]) -> None:
        """Mark multiple readings as synced for a specific repository"""
        if repository_name not in self.db.repositories:
            raise ValueError(f"Unknown repository: {repository_name}")
            
        repo = self.db.repositories[repository_name]
        async with self._sync_lock:
            await repo.bulk_mark_as_synced(device_ids, reading_ids)

filepath: src/iot_gateway/storage/temp_db.py
code: 
from typing import List, Optional, Dict, Any
from datetime import datetime
import traceback 
from .database import ConnectionPool, BaseRepository
import aiosqlite
from ..utils.logging import get_logger
from ..utils.exceptions import DatabaseError
from ..models.things import TemperatureReading

logger = get_logger(__name__)

class TemperatureRepository(BaseRepository[TemperatureReading]):
    def __init__(self, pool: ConnectionPool):
        super().__init__(pool)
        self.table_name = "temperature_readings"

    async def create_table(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS temperature_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    reading_id TEXT NOT NULL,
                    celsius REAL NOT NULL,
                    fahrenheit REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_synced BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id),
                    CONSTRAINT valid_temp_c CHECK (celsius BETWEEN -273.15 AND 1000),
                    CONSTRAINT valid_temp_f CHECK (fahrenheit BETWEEN -459.67 AND 1832),
                    UNIQUE(device_id, reading_id)
                )
            ''')
            await conn.commit()

    async def create_indices(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_temp_device_time 
                ON temperature_readings(device_id, timestamp)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_temp_sync 
                ON temperature_readings(is_synced)
            ''')
            await conn.commit()

    async def store_reading(self, reading: TemperatureReading) -> None:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO temperature_readings 
                    (device_id, reading_id, celsius, fahrenheit, timestamp, is_synced)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    reading.device_id,
                    reading.reading_id,
                    reading.celsius,
                    reading.fahrenheit,
                    reading.timestamp,
                    reading.is_synced
                ))
                await conn.commit()
        except aiosqlite.IntegrityError as e:
            logger.error(f"Invalid temperature reading: {traceback.format_exc()}")
            raise ValueError("Temperature reading outside valid range")
        except Exception as e:
            logger.error(f"Failed to store temperature reading: {e}")
            raise DatabaseError(f"Failed to store temperature reading: {e}")

    async def get_readings(
        self,
        device_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[TemperatureReading]:
        query = '''
            SELECT * FROM temperature_readings 
            WHERE device_id = ? 
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        '''
        params = [device_id, start_time, end_time]
        
        if limit is not None:
            query += ' LIMIT ?'
            params.append(limit)

        async with self.pool.acquire() as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [TemperatureReading(**dict(row)) for row in rows]
            
    def _row_to_reading(self, row: Dict[str, Any]) -> TemperatureReading:
        return TemperatureReading(
            device_id=row['device_id'],
            reading_id=row['reading_id'],
            celsius=row['celsius'],
            fahrenheit=row['fahrenheit'],
            timestamp=row['timestamp'],
            is_synced=bool(row['is_synced'])
        )
    
filepath: src/iot_gateway/models/things.py
code:
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
    GATEWAY = "gateway"


class BaseReading(BaseModel):
    device_id: str
    reading_id: str
    timestamp: datetime = datetime.now()
    is_synced: bool = False


class HearBeat(BaseReading):
    temperature: str
    available_memory: str
    cpu_usage : str


class HumidityReading(BaseReading):
    humidity: float

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

filepath: __main__.py
code:

# src/iot_gateway/__main__.py
import asyncio
import signal
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
import traceback

from iot_gateway.core.event_manager import EventManager
from iot_gateway.core.device_manager import DeviceManager
from iot_gateway.core.temperature_monitor import TemperatureMonitor
from iot_gateway.core.heartbeat import SystemMonitor
from iot_gateway.adapters.gpio import GPIOAdapter
from iot_gateway.core.communication_service import CommunicationService
from iot_gateway.api.routes import temp_router
from iot_gateway.api.endpoints.devices import device_router
from iot_gateway.utils.logging import setup_logging, get_logger
from iot_gateway.utils.exceptions import ConfigurationError, InitializationError
from iot_gateway.storage.sensor_database import SensorDatabase

class AppState:
    """Holds application state and components"""
    def __init__(self):
        self.temperature_monitor: Optional[TemperatureMonitor] = None
        self.db: Optional[SensorDatabase] = None
        self.device_manager: Optional[DeviceManager] = None
        self.event_manager: Optional[EventManager] = None
        self.communication_service: Optional[CommunicationService] = None
        self.system_monitor: Optional[SystemMonitor] = None

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
                required_sections = ['api', 'communication', 'devices', 'logging']
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
    
    def __init__(self, config: Dict[str, Any], shutdown_event: asyncio.Event, app_state: AppState):
        self.config = config
        self.shutdown_event = shutdown_event
        self.logger = get_logger("API Server")
        self.app: Optional[FastAPI] = None
        self.app_state = app_state

    async def initialize(self) -> FastAPI:
        """Initialize FastAPI application with routes"""
        try:
            self.app = FastAPI(
                title="IoT Gateway API",
                description="IoT Gateway service managing sensors and communication",
                version="1.0.0"
            )
            
            # Store app state for dependency injection
            self.app.state.components = self.app_state
            
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
        self.app_state = AppState()
        self.app_state.event_manager = EventManager()
        self.api_server = APIServer(self.config, self.shutdown_event, self.app_state)

    async def initialize_components(self):
        """Initialize all application components"""
        try:
            # Start event processing
            asyncio.create_task(self.app_state.event_manager.process_events())

            # Initialize Device Manager
            self.app_state.device_manager = DeviceManager(
                self.app_state.event_manager,
                GPIOAdapter(self.config['devices']),
                self.config['devices']
            )
            await self.app_state.device_manager.initialize()

            # Initialize database
            self.app_state.db = SensorDatabase(self.config['database']['path'], max_connections=10)
            await self.app_state.db.initialize()
            
            # Initialize Communication Service
            self.app_state.communication_service = CommunicationService(
                self.config, 
                event_manager=self.app_state.event_manager
            )
            await self.app_state.communication_service.initialize()
            
            # Initialize Temperature Monitor
            self.app_state.temperature_monitor = TemperatureMonitor(
                self.config,
                self.app_state.event_manager,
                self.app_state.db,
                self.app_state.communication_service.mqtt
            )
            await self.app_state.temperature_monitor.initialize()

            # Initialize System Monitoring
            self.app_state.system_monitor = SystemMonitor(
                config=self.config,
                db=self.app_state.db,
                mqtt=self.app_state.communication_service.mqtt
            )
            await self.app_state.system_monitor.initialize()
            
            self.logger.info("All components initialized successfully")
        except Exception as e:
            raise InitializationError(f"Failed to initialize components: {traceback.format_exc()}")

    async def start_temperature_monitoring(self):
        """Start temperature monitoring tasks"""
        try:
            monitor_task = asyncio.create_task(
                self.app_state.temperature_monitor.start_monitoring()
            )
            sync_task = asyncio.create_task(
                self.app_state.temperature_monitor.sync_stored_readings()
            )
            
            await asyncio.gather(monitor_task, sync_task)
        except Exception as e:
            self.logger.error(f"Error in temperature monitoring: {traceback.format_exc()}")
            await self.shutdown()

    async def shutdown(self):
        """Gracefully shutdown all components"""
        self.logger.info("Initiating shutdown sequence")
        try:
            if self.app_state.temperature_monitor:
                await self.app_state.temperature_monitor.stop()
            if self.app_state.communication_service:
                await self.app_state.communication_service.shutdown()
            if self.app_state.system_monitor:
                await self.app_state.system_monitor.stop()
            if self.app_state.db:
                await self.app_state.db.close()
            
            self.shutdown_event.set()
            self.logger.info("Shutdown completed successfully")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {traceback.format_exc()}")
        finally:
            sys.exit(1)

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
            await asyncio.gather(
                self.start_temperature_monitoring(),
                self.app_state.system_monitor.start_monitoring(),
                self.api_server.start()
            )
        except InitializationError as e:
            self.logger.error(f"Initialization error: {traceback.format_exc()}")
            await self.shutdown()
        except Exception as e:
            self.logger.error(f"Unexpected error: {traceback.format_exc()}")
            await self.shutdown()

def main():
    """Application entry point"""
    config_path = Path("src/config/default.yml")    
    app = IoTGatewayApp(str(config_path))
    asyncio.run(app.run())

if __name__ == "__main__":
    main()