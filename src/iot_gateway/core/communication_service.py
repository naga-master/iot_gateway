from typing import Dict, Any, Optional
from ..adapters.mqtt import MQTTAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class CommunicationService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config['communication']
        self.mqtt: Optional[MQTTAdapter] = None
        # Future communication adapters
        # self.wifi = None 
        # self.bluetooth = None

    async def initialize(self) -> None:
        logger.info(f"Initializing Communication Service")
        # Initialize MQTT
        if 'mqtt' in self.config:
            self.mqtt = MQTTAdapter(self.config['mqtt'])
            await self.mqtt.connect()
            logger.info("Mqtt service started")
        
        # Future initializations
        # if 'wifi' in self.config:
        #     self.wifi = WiFiAdapter(self.config['wifi'])
        #     await self.wifi.connect()

        

    async def shutdown(self) -> None:
        logger.info("Shutting down communication services")
        if self.mqtt:
            await self.mqtt.disconnect()
        # Shutdown other adapters