from typing import List, Optional, Dict, Any
from datetime import datetime
import traceback 
from .database import ConnectionPool, BaseRepository
import aiosqlite
from ..utils.logging import get_logger
from ..utils.exceptions import DatabaseError
from ..models.things import TemperatureReading

logger = get_logger(__name__)

class TemperatureRepository(BaseRepository[TemperatureReading]):
    def __init__(self, pool: ConnectionPool):
        super().__init__(pool)
        self.table_name = "temperature_readings"

    async def create_table(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS temperature_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    reading_id TEXT NOT NULL,
                    celsius REAL NOT NULL,
                    fahrenheit REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_synced BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id),
                    CONSTRAINT valid_temp_c CHECK (celsius BETWEEN -273.15 AND 1000),
                    CONSTRAINT valid_temp_f CHECK (fahrenheit BETWEEN -459.67 AND 1832),
                    UNIQUE(device_id, reading_id)
                )
            ''')
            await conn.commit()

    async def create_indices(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_temp_device_time 
                ON temperature_readings(device_id, timestamp)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_temp_sync 
                ON temperature_readings(is_synced)
            ''')
            await conn.commit()

    async def store_reading(self, reading: TemperatureReading) -> None:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO temperature_readings 
                    (device_id, reading_id, celsius, fahrenheit, timestamp, is_synced)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    reading.device_id,
                    reading.reading_id,
                    reading.celsius,
                    reading.fahrenheit,
                    reading.timestamp,
                    reading.is_synced
                ))
                await conn.commit()
        except aiosqlite.IntegrityError as e:
            logger.error(f"Invalid temperature reading: {traceback.format_exc()}")
            raise ValueError("Temperature reading outside valid range")
        except Exception as e:
            logger.error(f"Failed to store temperature reading: {e}")
            raise DatabaseError(f"Failed to store temperature reading: {e}")

    async def get_readings(
        self,
        device_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[TemperatureReading]:
        query = '''
            SELECT * FROM temperature_readings 
            WHERE device_id = ? 
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        '''
        params = [device_id, start_time, end_time]
        
        if limit is not None:
            query += ' LIMIT ?'
            params.append(limit)

        async with self.pool.acquire() as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [TemperatureReading(**dict(row)) for row in rows]
            
    def _row_to_reading(self, row: Dict[str, Any]) -> TemperatureReading:
        return TemperatureReading(
            device_id=row['device_id'],
            reading_id=row['reading_id'],
            celsius=row['celsius'],
            fahrenheit=row['fahrenheit'],
            timestamp=row['timestamp'],
            is_synced=bool(row['is_synced'])
        )