import psutil

## should be uncommented while deploying raspberry pi
from gpiozero import CPUTemperature
import traceback
import traceback
from typing import Dict, Any
import asyncio
import uuid
from ..adapters.mqtt import MQTTAdapter
from ..models.things import HearBeat
from ..utils.logging import get_logger
from ..models.things import DeviceType

logger = get_logger(__name__)

class SystemMonitor:
    def __init__(self, config: Dict[str, Any], db, mqtt: MQTTAdapter):
        self.config = config
        self.mqtt = mqtt
        self.db = db
        self.is_running = False
        self.metrics:HearBeat = None
        self.device_id = None

    async def initialize(self):
        
        logger.info("Initializing System Monitoring")
        ## should be uncommented while deploying raspberry pi
        # self.cpu_temp = CPUTemperature()

        self.device_id = self.config['system']['device_id']

        # First register the device
        await self.db.register_device(
            device_id=self.device_id,
            device_type=DeviceType.GATEWAY,
            name=f"IoT Gateway {self.device_id}",
            location="India"
        )

    async def start_monitoring(self) -> None:
        self.is_running = True
        while self.is_running:
            try:
                self.metrics = self.get_system_metrics()

                try:
                    await self.mqtt.write_data({
                        "topic": f"{self.config['system']['heart_beat_topic_prefix']}/{self.device_id}",
                        "payload": self.metrics.model_dump_json(),
                        "qos": self.mqtt.config.publish_qos
                    })

                    # Store the metrics into db
                    await self.db.repositories['system'].store_reading(self.metrics)
                except Exception as e:
                    logger.error(f"Failed to publish reading: {traceback.format_exc()}")

                await asyncio.sleep(self.config['system']['heart_beat_interval'])
            except Exception as e:
                logger.error(f"Error while getting system metrics, {traceback.format_exc()}")
                await asyncio.sleep(self.config['sync']['error_retry_interval'])

    def get_system_metrics(self) -> HearBeat:
        # Get CPU temperature
        # temperature = f"{self.cpu_temp.temperature:.2f}°C"
        temperature = "36°C"
        
        # Get memory information
        memory = psutil.virtual_memory()
        available_memory = f"{memory.available / (1024 * 1024):.2f}MB"
        
        # Get CPU usage
        cpu_usage = f"{psutil.cpu_percent(interval=1):.1f}%"

        # Create heartbeat reading
        reading = HearBeat(
            device_id=self.device_id,
            reading_id=str(uuid.uuid4()),
            temperature=temperature,
            available_memory=available_memory,
            cpu_usage=cpu_usage,
            is_synced=True # set always true for now
        )
        
        return reading
    
    async def stop(self) -> None:
        self.is_running = False
        logger.info("System Monitoring stopped")