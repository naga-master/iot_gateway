import asyncio
from typing import Dict, Any, Callable, Optional, Union, List, Set
from pydantic import BaseModel, Field
import aiomqtt as mqtt
from aiomqtt import Will
import json
import traceback
from ..adapters.base import CommunicationAdapter
from ..utils.logging import get_logger
from ..utils.exceptions import CommunicationError
from contextlib import asynccontextmanager
import random
import ssl

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
    ca_cert: Optional[str] = Field(None, description="Custom CA certificate")
    client_cert: Optional[str] = Field(None, description="Client certificate")
    client_key: Optional[str] = Field(None, description="Required if client_cert is set")
    verify_hostname: bool = Field(True, description="Verify broker's hostname")
    tls_version: Optional[str] = Field(None, description="TLS1_2, TLS1_3, etc.")
    subscribe_qos: int =  Field(0, description="qos for subscribe topics")
    publish_qos: int =  Field(0, description="qos for publish message")
    clean_session: bool = Field(False, description="persistent sessions with clean_session=False")

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
            self.config.keepalive = max(30, self.config.keepalive)
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
        self._connection_lock = asyncio.Lock()
        self._publish_lock = asyncio.Lock()
        self._publish_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._publisher_task: Optional[asyncio.Task] = None

    async def _publish_worker(self):
        """Worker task to handle publishing messages from queue"""
        while not self._stop_flag.is_set():
            try:
                message = await self._publish_queue.get()
                attempt = 0
                while attempt < self.config.max_reconnect_attempts and not self._stop_flag.is_set():
                    try:
                        async with self._publish_lock:  # Ensure only one publish operation at a time
                            if self.client and self.connected.is_set():
                                await self.client.publish(
                                    topic=message.topic,
                                    payload=message.payload,
                                    qos=message.qos,
                                    retain=message.retain
                                )
                                logger.debug(f"Published to {message.topic}")
                                self._publish_queue.task_done()
                                break
                            else:
                                raise CommunicationError("Not connected to MQTT broker")
                    except Exception as e:
                        attempt += 1
                        if attempt >= self.config.max_reconnect_attempts:
                            logger.error(f"Failed to publish message after {attempt} attempts: {str(e)}")
                            self._publish_queue.task_done()
                            break
                        wait_time = min(self.config.reconnect_interval * (2 ** (attempt - 1)), 60)
                        logger.warning(f"Publish attempt {attempt} failed, retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in publish worker: {str(e)}")
                await asyncio.sleep(1)

    async def _subscribe_topics(self) -> None:
        """Subscribe to all stored topics"""
        async with self._subscription_lock:
            for topic, handlers in self.message_handlers.items():
                if self.client:
                    try:
                        await self.client.subscribe(topic, qos=self.config.subscribe_qos)
                        logger.info(f"Resubscribed to topic: {topic}")
                    except Exception as e:
                        logger.error(f"Failed to resubscribe to topic {topic}: {str(e)}")
                        self.pending_subscriptions.add(topic)

    def _create_tls_context(self) -> Optional[ssl.SSLContext]:
        """Create SSL context for MQTT connection based on config"""
        if not self.config.ssl:
            return None

        context = ssl.create_default_context()
        
        if hasattr(self.config, 'ca_cert') and self.config.ca_cert:
            context.load_verify_locations(cafile=self.config.ca_cert)
        
        if hasattr(self.config, 'client_cert') and self.config.client_cert:
            if not hasattr(self.config, 'client_key') or not self.config.client_key:
                raise ValueError("Client key must be provided when using client certificate")
            context.load_cert_chain(
                certfile=self.config.client_cert,
                keyfile=self.config.client_key
            )
        
        if hasattr(self.config, 'tls_version'):
            context.minimum_version = getattr(ssl.TLSVersion, self.config.tls_version.upper(), 
                                        ssl.TLSVersion.TLSv1_2)
        
        if hasattr(self.config, 'verify_hostname'):
            context.check_hostname = self.config.verify_hostname
        
        return context
                
    @staticmethod
    async def message_handler(topic: str, payload: Any):
        print(f"Received on {topic}: {payload}")

    async def _heartbeat(self, client: mqtt.Client):
        """Send periodic heartbeat to keep connection alive"""
        while not self._stop_flag.is_set():
            try:
                if self.connected.is_set():
                    await client.publish(
                        f"{self.config.client_id}/heartbeat",
                        payload=b"ping",
                        qos=0
                    )
                await asyncio.sleep(self.config.keepalive // 2)
            except Exception as e:
                logger.warning(f"Heartbeat failed: {str(e)}")
                await asyncio.sleep(1)

    
    @asynccontextmanager
    async def _get_client(self):
        """Context manager for MQTT client with automatic reconnection"""
        attempt = 0
        while attempt < self.config.max_reconnect_attempts and not self._stop_flag.is_set():
            try:
                # Set up Last Will and Testament (LWT)
                will =Will(
                    topic=f"{self.config.client_id}/status",
                    payload="Offline",
                    qos=self.config.subscribe_qos, 
                    retain=True)
                
                async with mqtt.Client(
                    hostname=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    password=self.config.password,
                    keepalive=self.config.keepalive,
                    identifier=f"{self.config.client_id}_{random.randint(1000, 9999)}",
                    clean_session=self.config.clean_session,
                    will=will,
                    tls_context=self._create_tls_context() if self.config.ssl else None
                ) as client:
                    self.client = client
                    self.connected.set()

                    # Publish online status
                    await client.publish(
                        f"{self.config.client_id}/status",
                        payload="Online",
                        qos=1,
                        retain=True
                    )
                    
                    # Start heartbeat task
                    heartbeat_task = asyncio.create_task(self._heartbeat(client))
                    
                    logger.info("Connected to MQTT broker")
                    try:
                        await self._subscribe_topics()
                        logger.info(f"Connected to MQTT broker with client ID: {self.config.client_id}")
                        yield client
                    finally:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass
                        self.connected.clear()
                        self.client = None
                        logger.info("Disconnected from MQTT broker")
                break  # Successful connection and operation
                
            except Exception as e:
                attempt += 1
                logger.error(f"MQTT connection attempt {attempt} failed: {traceback.format_exc()}")
                if attempt >= self.config.max_reconnect_attempts:
                    raise CommunicationError(f"Failed to connect to MQTT broker after {attempt} attempts")
                
                # Exponential backoff for reconnection attempts
                wait_time = min(self.config.reconnect_interval * (2 ** (attempt - 1)), 60)
                logger.info(f"MQTT Retry will happen after {wait_time} seconds")
                await asyncio.sleep(wait_time)


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

            except asyncio.CancelledError:
                break
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
            self._publisher_task = asyncio.create_task(self._publish_worker())
            asyncio.create_task(self._process_message_queue())
        except Exception as e:
            raise CommunicationError(f"Failed to start MQTT adapter: {str(e)}")

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker and cleanup"""
        try:
            self._stop_flag.set()
            
            # Cancel all running tasks
            tasks = [self._message_processor_task, self._publisher_task]
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

            # Wait for all queued messages to be processed
            await self._message_queue.join()
            await self._publish_queue.join()
            
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
        """Queue message for publishing"""
        try:
            if isinstance(message, dict):
                message = MQTTMessage(**message)

            payload = message.payload
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            elif not isinstance(payload, (str, bytes)):
                payload = str(payload)

            if isinstance(payload, str):
                payload = payload.encode()

            # Create new message with encoded payload
            queued_message = MQTTMessage(
                topic=message.topic,
                payload=payload,
                qos=message.qos,
                retain=message.retain
            )

            try:
                await self._publish_queue.put(queued_message)
                logger.debug(f"Queued message for topic: {message.topic}")
            except asyncio.QueueFull:
                logger.error("Publish queue full, dropping message")
                raise CommunicationError("Publish queue full")

        except Exception as e:
            raise CommunicationError(f"Failed to queue MQTT message: {str(e)}")
                
    async def write_data(self, data: Dict[str, Any]) -> None:
        """Write data to MQTT (alias for publish)"""
        await self.publish(data)

    async def read_data(self) -> Dict[str, Any]:
        """Not implemented for MQTT - using callbacks instead"""
        raise NotImplementedError("MQTT adapter uses callbacks for reading data")