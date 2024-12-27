from typing import Dict, Any, Optional
from ..adapters.mqtt import MQTTAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class CommunicationService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mqtt: Optional[MQTTAdapter] = None
        # Future communication adapters
        # self.wifi = None 
        # self.bluetooth = None

    async def initialize(self) -> None:
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
        if self.mqtt:
            await self.mqtt.disconnect()
        # Shutdown other adapters