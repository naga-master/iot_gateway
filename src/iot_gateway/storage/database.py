from typing import List, Dict, Any, Optional, Type, Generic, TypeVar
import aiosqlite
from datetime import datetime
from abc import ABC, abstractmethod
from ..utils.logging import get_logger
from dataclasses import dataclass
from ..sensors.temperature import TemperatureReading

logger = get_logger(__name__)

T = TypeVar('T')

@dataclass
class BaseReading:
    id: Optional[int]
    sensor_id: str
    timestamp: datetime
    is_synced: bool = False

class DatabaseHandler:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection_pool = []
        self.MAX_POOL_SIZE = 5

    async def get_connection(self) -> aiosqlite.Connection:
        """Get a connection from the pool or create a new one."""
        if not self._connection_pool:
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            self._connection_pool.append(conn)
            return conn
        return self._connection_pool.pop()

    async def release_connection(self, conn: aiosqlite.Connection):
        """Return a connection to the pool or close it if pool is full."""
        if len(self._connection_pool) < self.MAX_POOL_SIZE:
            self._connection_pool.append(conn)
        else:
            await conn.close()

    async def initialize(self) -> None:
        """Initialize the database with common tables."""
        logger.info("Initializing base database")
        async with await self.get_connection() as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sensors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id TEXT UNIQUE NOT NULL,
                    sensor_type TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    location TEXT,
                    last_reading_timestamp TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()

    async def register_sensor(self, sensor_id: str, sensor_type: str, protocol: str, location: str = None) -> None:
        """Register a new sensor in the database."""
        async with await self.get_connection() as db:
            await db.execute('''
                INSERT OR REPLACE INTO sensors 
                (sensor_id, sensor_type, protocol, location)
                VALUES (?, ?, ?, ?)
            ''', (sensor_id, sensor_type, protocol, location))
            await db.commit()

    async def get_sensor_info(self, sensor_id: str) -> Dict[str, Any]:
        """Get sensor information."""
        async with await self.get_connection() as db:
            async with db.execute(
                'SELECT * FROM sensors WHERE sensor_id = ?',
                (sensor_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

class SensorDatabaseHandler(ABC, Generic[T]):
    def __init__(self, db_handler: DatabaseHandler):
        self.db = db_handler

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize sensor-specific tables."""
        pass

    @abstractmethod
    async def store_reading(self, reading: T) -> None:
        """Store a sensor reading."""
        pass

    @abstractmethod
    async def get_readings(
        self,
        sensor_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[T]:
        """Retrieve readings for a specific sensor."""
        pass

    async def get_unsynced_readings(self) -> List[T]:
        """Get unsynced readings."""
        pass

    async def mark_as_synced(self, reading_ids: List[int]) -> None:
        """Mark readings as synced."""
        pass


logger = get_logger(__name__)

class TemperatureStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize(self) -> None:
        """Initialize the database and create required tables."""
        logger.info("Setting up database")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.cursor()
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS temperature_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id TEXT NOT NULL,
                    reading_id TEXT NOT NULL,
                    celsius REAL NOT NULL,
                    fahrenheit REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_synced BOOLEAN NOT NULL DEFAULT 0,
                    CONSTRAINT valid_temp_c CHECK (celsius BETWEEN -273.15 AND 1000),
                    CONSTRAINT valid_temp_f CHECK (fahrenheit BETWEEN -459.67 AND 1832)
                )
            ''')
            # Add index for common queries
            await cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sensor_time 
                ON temperature_readings(sensor_id, timestamp)
            ''')
            await cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sync_status
                ON temperature_readings(is_synced)
            ''')
            await db.commit()
            logger.info("Database initialized")

    async def store_reading(self, reading: TemperatureReading) -> None:
        """Store a single temperature reading in the database."""
        try:
            print(reading)
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                await cursor.execute('''
                    INSERT INTO temperature_readings 
                    (sensor_id, reading_id, celsius, fahrenheit, timestamp, is_synced)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    reading.sensor_id,
                    reading.reading_id,
                    reading.celsius,
                    reading.fahrenheit,
                    reading.timestamp,
                    reading.is_synced
                ))
                await db.commit()
                logger.debug(f"Stored reading from sensor {reading.sensor_id}")
        except aiosqlite.IntegrityError as e:
            logger.error(f"Invalid temperature reading: {e}")
            raise ValueError("Temperature reading outside valid range")
        except Exception as e:
            logger.error(f"Failed to store reading: {e}")
            raise

    async def get_unsynced_readings(self) -> List[TemperatureReading]:
        """Retrieve all unsynced temperature readings."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM temperature_readings WHERE is_synced = 0'
            ) as cursor:
                rows = await cursor.fetchall()

                return [TemperatureReading(**dict(row)) for row in rows]

    async def bulk_mark_as_synced(self, sensor_ids: List[str], reading_ids: List[str]) -> None:
        """Mark multiple readings as synced by their IDs."""
        if not reading_ids:
            return
        
        if not sensor_ids:
            return
            
        async with aiosqlite.connect(self.db_path) as db:
            reading_ids_placeholders = ','.join('?' * len(reading_ids))
            sensor_ids_placeholders = ','.join('?' * len(sensor_ids))

            await db.execute(
                f'UPDATE temperature_readings SET is_synced = 1 WHERE sensor_id IN ({sensor_ids_placeholders}) AND reading_id IN ({reading_ids_placeholders})',
                sensor_ids_placeholders,
                reading_ids_placeholders
            )
            await db.commit()
            logger.debug(f"Marked {len(reading_ids)} readings as synced")
    
    async def mark_as_synced(self, sensor_id: str, reading_id: str) -> None:
        """Mark one sensor rading as synced by their ID"""
        if not sensor_id or not reading_id:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f'UPDATE temperature_readings SET is_synced = 1 WHERE sensor_id = ? AND reading_id = ?',
                (sensor_id, reading_id)
            )
            await db.commit()
            logger.debug(f"Marked {reading_id} reading as synced")


    async def get_readings(
        self, 
        sensor_id: str, 
        start_time: datetime, 
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[TemperatureReading]:
        """
        Retrieve temperature readings for a specific sensor within a time range.
        
        Args:
            sensor_id: The ID of the sensor to query
            start_time: Start of the time range
            end_time: End of the time range
            limit: Optional maximum number of readings to return
        
        Returns:
            List of TemperatureReading objects matching the criteria
        """
        query = '''
            SELECT * FROM temperature_readings 
            WHERE sensor_id = ? 
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        '''
        
        if limit is not None:
            query += ' LIMIT ?'
            params = (sensor_id, start_time, end_time, limit)
        else:
            params = (sensor_id, start_time, end_time)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [TemperatureReading(**dict(row)) for row in rows]