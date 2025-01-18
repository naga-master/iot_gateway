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
                    logger.info(reading)

                    # Store reading
                    await self.db.repositories['temperature'].store_reading(reading)
                    
                    if self.mqtt.connected.is_set():
                        # Publish reading
                        try:
                            await self.mqtt.write_data({
                                "topic": f"temperature/{reading.device_id}",
                                "payload": reading.model_dump_json(),
                                "qos": self.mqtt.config.publish_qos,
                                "retain": False
                            })
                        except Exception as e:
                            logger.error(f"Failed to publish reading: {traceback.format_exc()}")

                await asyncio.sleep(self.config['sensors']['temperature']['reading_interval'])
            except Exception as e:
                logger.error(f"Error in monitoring loop: {traceback.format_exc()}")
                await asyncio.sleep(self.config['sync']['error_retry_interval'])  # Wait before retry

    async def sync_stored_readings(self, internal_sync_call:bool = False) -> None:
        if not self.config['sync']['periodic_sync']:
            logger.info("Periodic Sync is disabled")
            return False
        
        next_sync_interval = self.config['sync']["interval"]
        
        while self.is_running:
            try:
                unsynced = await self.db.sync_manager.get_all_unsynced_readings()
                unsynced_temp_data = unsynced.get('temperature')

                if unsynced_temp_data:
                    logger.info(f"Sending {len(unsynced_temp_data)} stored unsynced readings")
                    if len(unsynced_temp_data) > next_sync_interval:

                        # assuming one second will take for a full round trip syncing from mqtt to db
                        # so increasing the sync interval based on the len of unsynced data
                        next_sync_interval = len(unsynced_temp_data) + 10
                    else:
                         next_sync_interval = self.config['sync']["interval"] # reset to default sync interval

                    # Get unsynced readings
                    await self.sync_temperature_readings(unsynced_temp_data)

            except Exception as e:
                logger.error(f"error in sync loop: {traceback.format_exc()}")
            
            logger.info(f'Syncing will happen after {next_sync_interval} seconds')
            await asyncio.sleep(next_sync_interval)

    async def sync_temperature_readings(self, unsynced_temp_readings:list, topic: str=None, device_ids:list=None):
        """Retrieve unsynced data and push via mqtt"""
        # change the next syncing interval based on current unsynced data
        for reading in unsynced_temp_readings:
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
                        "payload": sensor_data,
                        "qos": self.mqtt.config.publish_qos
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
            # Use sync manager to mark the reading as synced
            await self.db.sync_manager.mark_single_as_synced(
                repository_name='temperature',
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

        # For monitoring failed syncs
    async def check_failed_syncs(self):
        failed = await self.db.sync_manager.get_failed_syncs("your_repo_name")
        for device_id, reading_id, attempt_count in failed:
            logger.warning(f"Sync failed {attempt_count} times for {device_id}:{reading_id}")
    
    async def stop(self) -> None:
        self.is_running = False
        for sensor in self.sensors:
            if hasattr(sensor, "disconnect"):
                await sensor.disconnect()
        
        logger.info("Temperature monitor stopped")

