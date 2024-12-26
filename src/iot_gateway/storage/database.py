# Database interactions
from typing import List, Optional, Type
import aiosqlite
from ..sensors.temperature import TemperatureReading
from ..utils.logging import get_logger

logger = get_logger(__name__)

class TemperatureStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize(self) -> None:
        logger.info("Setting up database")
        async with aiosqlite.connect(self.db_path) as db:
            
            cursor = await db.cursor()
            await cursor.execute('''
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
            cursor = await db.cursor()
            await cursor.execute('''
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

    async def get_readings(self, sensor_id:int, start_time, end_time):
        raise NotImplementedError("retrieving data from sensor is not yet implemented")
