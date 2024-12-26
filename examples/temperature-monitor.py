# src/iot_gateway/models/temperature.py
from datetime import datetime
from pydantic import BaseModel, validator
from typing import Optional

class TemperatureReading(BaseModel):
    sensor_id: str
    celsius: float
    fahrenheit: float
    timestamp: datetime = datetime.now()
    is_synced: bool = False

    @validator('celsius')
    def validate_celsius(cls, v):
        if not -40 <= v <= 125:  # Common I2C temperature sensor range
            raise ValueError(f"Temperature {v}°C is out of valid range")
        return round(v, 2)

    @validator('fahrenheit')
    def validate_fahrenheit(cls, v):
        if not -40 <= v <= 257:  # Converted range
            raise ValueError(f"Temperature {v}°F is out of valid range")
        return round(v, 2)

# src/iot_gateway/adapters/i2c_temp.py
from typing import Dict, Any
import smbus2
from ..adapters.base import BaseAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class I2CTemperatureSensor(BaseAdapter):
    def __init__(self, bus_number: int, address: int, sensor_id: str):
        self.bus = smbus2.SMBus(bus_number)
        self.address = address
        self.sensor_id = sensor_id
        self.is_connected = False

    async def connect(self) -> None:
        try:
            # Test connection by reading a byte
            self.bus.read_byte(self.address)
            self.is_connected = True
            logger.info(f"Connected to sensor {self.sensor_id} at address {self.address}")
        except Exception as e:
            logger.error(f"Failed to connect to sensor {self.sensor_id}: {e}")
            raise

    async def disconnect(self) -> None:
        self.bus.close()
        self.is_connected = False
        logger.info(f"Disconnected from sensor {self.sensor_id}")

    async def read_data(self) -> Dict[str, float]:
        if not self.is_connected:
            raise RuntimeError("Sensor not connected")
        
        try:
            # Read temperature register (example for TMP102 sensor)
            data = self.bus.read_i2c_block_data(self.address, 0x00, 2)
            temp_c = ((data[0] << 8) | data[1]) / 256.0
            temp_f = (temp_c * 9/5) + 32
            
            logger.debug(f"Sensor {self.sensor_id} read: {temp_c}°C / {temp_f}°F")
            return {"celsius": temp_c, "fahrenheit": temp_f}
        except Exception as e:
            logger.error(f"Error reading sensor {self.sensor_id}: {e}")
            raise

    async def write_data(self, data: Dict[str, Any]) -> None:
        # Not implemented for read-only sensor
        pass

# src/iot_gateway/adapters/mqtt_client.py
import asyncio
from typing import Dict, Any, Callable
import asyncio_mqtt as mqtt
from ..adapters.base import BaseAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class MQTTAdapter(BaseAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.message_handlers = {}

    async def connect(self) -> None:
        try:
            self.client = mqtt.Client(
                hostname=self.config["host"],
                port=self.config["port"],
                username=self.config.get("username"),
                password=self.config.get("password")
            )
            await self.client.connect()
            logger.info("Connected to MQTT broker")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            raise

    async def disconnect(self) -> None:
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected from MQTT broker")

    async def subscribe(self, topic: str, handler: Callable) -> None:
        await self.client.subscribe(topic)
        self.message_handlers[topic] = handler
        logger.info(f"Subscribed to topic: {topic}")

    async def read_data(self) -> Dict[str, Any]:
        # Not used for MQTT - using callbacks instead
        pass

    async def write_data(self, data: Dict[str, Any]) -> None:
        try:
            topic = data.pop("topic")
            await self.client.publish(topic, data["payload"])
            logger.debug(f"Published to {topic}: {data['payload']}")
        except Exception as e:
            logger.error(f"Failed to publish MQTT message: {e}")
            raise

# src/iot_gateway/storage/database.py
from typing import List, Optional
import aiosqlite
from ..models.temperature import TemperatureReading
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

# src/iot_gateway/core/temperature_monitor.py
from typing import List, Dict, Any
import asyncio
from ..adapters.i2c_temp import I2CTemperatureSensor
from ..adapters.mqtt_client import MQTTAdapter
from ..storage.database import TemperatureStorage
from ..models.temperature import TemperatureReading
from ..utils.logging import get_logger

logger = get_logger(__name__)

class TemperatureMonitor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sensors: List[I2CTemperatureSensor] = []
        self.mqtt: Optional[MQTTAdapter] = None
        self.storage = TemperatureStorage(config["database"]["path"])
        self.is_running = False

    async def initialize(self) -> None:
        # Initialize storage
        await self.storage.initialize()

        # Initialize sensors
        for sensor_config in self.config["sensors"]:
            sensor = I2CTemperatureSensor(
                bus_number=sensor_config["bus"],
                address=sensor_config["address"],
                sensor_id=sensor_config["id"]
            )
            await sensor.connect()
            self.sensors.append(sensor)

        # Initialize MQTT
        self.mqtt = MQTTAdapter(self.config["mqtt"])
        await self.mqtt.connect()

        logger.info("Temperature monitor initialized")

    async def start_monitoring(self) -> None:
        self.is_running = True
        while self.is_running:
            try:
                for sensor in self.sensors:
                    # Read sensor
                    data = await sensor.read_data()
                    
                    # Create reading
                    reading = TemperatureReading(
                        sensor_id=sensor.sensor_id,
                        **data
                    )

                    # Store reading
                    await self.storage.store_reading(reading)

                    # Publish reading
                    try:
                        await self.mqtt.write_data({
                            "topic": f"temperature/{sensor.sensor_id}",
                            "payload": reading.json()
                        })
                        reading.is_synced = True
                    except Exception as e:
                        logger.error(f"Failed to publish reading: {e}")
                        # Will be synced later

                await asyncio.sleep(self.config["reading_interval"])
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
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
                                "payload": reading.json()
                            })
                            reading.is_synced = True
                        except Exception as e:
                            logger.error(f"Failed to sync reading: {e}")
                            break  # Stop if MQTT is down
                    
                    # Mark successful syncs
                    synced_ids = [r.id for r in unsynced if r.is_synced]
                    if synced_ids:
                        await self.storage.mark_as_synced(synced_ids)

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
            
            await asyncio.sleep(self.config["sync_interval"])

    async def stop(self) -> None:
        self.is_running = False
        for sensor in self.sensors:
            await sensor.disconnect()
        if self.mqtt:
            await self.mqtt.disconnect()
        logger.info("Temperature monitor stopped")

# src/iot_gateway/api/routes.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta
from ..storage.database import TemperatureStorage
from ..models.temperature import TemperatureReading

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

# tests/test_temperature_monitor.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from iot_gateway.core.temperature_monitor import TemperatureMonitor
from iot_gateway.models.temperature import TemperatureReading

@pytest.fixture
def mock_config():
    return {
        "database": {"path": ":memory:"},
        "sensors": [
            {"id": "sensor1", "bus": 1, "address": 0x48},
            {"id": "sensor2", "bus": 1, "address": 0x49}
        ],
        "mqtt": {
            "host": "localhost",
            "port": 1883
        },
        "reading_interval": 60,
        "sync_interval": 300
    }

@pytest.fixture
async def monitor(mock_config):
    monitor = TemperatureMonitor(mock_config)
    monitor.storage.initialize = AsyncMock()
    monitor.mqtt = AsyncMock()
    yield monitor
    await monitor.stop()

@pytest.mark.asyncio
async def test_temperature_reading_validation():
    # Test valid temperature
    valid_reading = TemperatureReading(
        sensor_id="test",
        celsius=25.0,
        fahrenheit=77.0
    )
    assert valid_reading.celsius == 25.0

    # Test invalid temperature
    with pytest.raises(ValueError):
        TemperatureReading(
            sensor_id="test",
            celsius=150.0,  # Too high
            fahrenheit=302.0
        )

@pytest.mark.asyncio
async def test_monitor_initialization(monitor, mock_config):
    await monitor.initialize()
    
    # Check if storage was initialized
    monitor.storage.initialize.assert_called_once()
    
    # Check if MQTT was connected
    monitor.mqtt.connect.assert_called_once()
    
    # Check if correct number of sensors were created
    assert len(monitor.sensors) == len(mock_config["sensors"])
