from typing import List, Dict, Any, Optional, Type, Generic, TypeVar
import aiosqlite
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from abc import ABC, abstractmethod

from ..utils.logging import get_logger
from ..models.things import TemperatureReading
from ..utils.exceptions import ConnectionPoolError, DatabaseError


logger = get_logger(__name__)

# Type definitions
T = TypeVar('T')


class ConnectionPool:
    """Manages a pool of database connections"""
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self._active_connections = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the connection pool"""
        logger.info(f"Initializing connection pool with {self.max_connections} connections")
        try:
            for _ in range(self.max_connections):
                conn = await aiosqlite.connect(self.db_path)
                await conn.execute('PRAGMA journal_mode=WAL')
                await conn.execute('PRAGMA foreign_keys=ON')
                await self._pool.put(conn)
                self._active_connections += 1
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise ConnectionPoolError(f"Connection pool initialization failed: {e}")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        connection = None
        try:
            async with self._lock:
                if self._pool.empty() and self._active_connections < self.max_connections:
                    # Create new connection if pool is empty and we haven't reached max
                    connection = await aiosqlite.connect(self.db_path)
                    await connection.execute('PRAGMA journal_mode=WAL')
                    await connection.execute('PRAGMA foreign_keys=ON')
                    self._active_connections += 1
                else:
                    # Wait for available connection with timeout
                    try:
                        connection = await asyncio.wait_for(self._pool.get(), timeout=5.0)
                    except asyncio.TimeoutError:
                        raise ConnectionPoolError("Timeout waiting for database connection")

            yield connection

        finally:
            if connection:
                try:
                    await self._pool.put(connection)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    # If we can't return to pool, close it and create new one
                    await connection.close()
                    async with self._lock:
                        self._active_connections -= 1

    async def close(self):
        """Close all connections in the pool"""
        while not self._pool.empty():
            conn = await self._pool.get()
            await conn.close()
        self._active_connections = 0



class BaseRepository(ABC, Generic[T]):
    """Abstract base class for sensor repositories"""
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        self.table_name: str = ""  # Must be set by implementing classes

    @abstractmethod
    async def create_table(self) -> None:
        """Create the repository's table"""
        pass

    @abstractmethod
    async def store_reading(self, reading: T) -> None:
        """Store a reading in the database"""
        pass

    @abstractmethod
    async def get_readings(
        self,
        device_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[T]:
        """Retrieve readings for a device within a time range"""
        pass

    async def create_indices(self) -> None:
        """Create indices for the repository's table"""
        pass

    async def get_unsynced_readings(self) -> List[T]:
        """Retrieve all unsynced readings for this sensor type."""
        try:
            async with self.pool.acquire() as conn:
                conn.row_factory = aiosqlite.Row
                query = f'SELECT * FROM {self.table_name} WHERE is_synced = 0'
                async with conn.execute(query) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_reading(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get unsynced readings from {self.table_name}: {e}")
            raise DatabaseError(f"Failed to get unsynced readings: {e}")

    async def bulk_mark_as_synced(self, device_ids: List[str], reading_ids: List[str]) -> None:
        """Mark multiple readings as synced."""
        if not device_ids or not reading_ids:
            return

        try:
            async with self.pool.acquire() as conn:
                placeholders_devices = ','.join(['?' for _ in device_ids])
                placeholders_readings = ','.join(['?' for _ in reading_ids])
                
                query = f'''
                    UPDATE {self.table_name} 
                    SET is_synced = 1 
                    WHERE device_id IN ({placeholders_devices})
                    AND reading_id IN ({placeholders_readings})
                '''
                
                await conn.execute(query, [*device_ids, *reading_ids])
                await conn.commit()
                logger.debug(f"Marked {len(reading_ids)} readings as synced in {self.table_name}")
        except Exception as e:
            logger.error(f"Failed to bulk mark readings as synced in {self.table_name}: {e}")
            raise DatabaseError(f"Failed to bulk mark readings as synced: {e}")

    async def mark_as_synced(self, device_id: str, reading_id: str) -> None:
        """Mark a single reading as synced."""
        if not device_id or not reading_id:
            return

        try:
            async with self.pool.acquire() as conn:
                query = f'''
                    UPDATE {self.table_name} 
                    SET is_synced = 1 
                    WHERE device_id = ? AND reading_id = ?
                '''
                await conn.execute(query, (device_id, reading_id))
                await conn.commit()
                logger.info(f"Marked reading {reading_id} as synced in {self.table_name}")
        except Exception as e:
            logger.error(f"Failed to mark reading as synced in {self.table_name}: {e}")
            raise DatabaseError(f"Failed to mark reading as synced: {e}")

    @abstractmethod
    def _row_to_reading(self, row: Dict[str, Any]) -> T:
        """Convert a database row to a reading object"""
        pass



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