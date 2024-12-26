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