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