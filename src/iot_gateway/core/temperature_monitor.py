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
                 communication_service: CommunicationService, mqtt: Optional[MQTTAdapter] = None):
        self.config = config
        self.event_manager = event_manager
        self.communication_service = communication_service
        self.i2c_adapters: Dict[int, I2CAdapter] = {}  # Support multiple buses
        self.sensors = []
        self.mqtt = mqtt
        self.storage = TemperatureStorage(self.config['temperature_monitor']["database"]["path"])
        self.is_running = False
        self._sensor_read_lock = asyncio.Lock()  # Prevent concurrent sensor reads

    async def initialize(self) -> None:
        logger.info("Initializing Temperature Monitor")
        await self.storage.initialize()

        # Initialize I2C adapters for each configured bus
        for bus_config in self.config['temperature_monitor']['i2c_buses']:
            bus_number = bus_config['bus_number']
            adapter = I2CAdapter(bus_number)
            try:
                await adapter.connect()
                self.i2c_adapters[bus_number] = adapter
            except Exception as e:
                logger.error(f"Failed to initialize I2C bus {bus_number}: {e}")
                continue

        # Initialize sensors
        for sensor_config in self.config['temperature_monitor']['sensors']:
            try:
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
                await sensor.initialize()
                self.sensors.append(sensor)
                logger.info(f"Initialized sensor {sensor_config['id']} on bus {bus_number}")
            except Exception as e:
                logger.error(f"Failed to initialize sensor {sensor_config['id']}: {e}")

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

