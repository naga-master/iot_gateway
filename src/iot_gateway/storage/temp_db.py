from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass
from .database import BaseReading, SensorDatabaseHandler, DatabaseHandler

@dataclass
class TemperatureReading(BaseReading):
    celsius: float
    fahrenheit: float

class TemperatureDatabaseHandler(SensorDatabaseHandler[TemperatureReading]):
    async def initialize(self) -> None:
        """Initialize temperature-specific tables with optimized indexes."""
        async with await self.db.get_connection() as conn:
            # Use WITHOUT ROWID for better performance on RPi
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS temperature_readings (
                    id INTEGER PRIMARY KEY,
                    sensor_id TEXT NOT NULL,
                    celsius REAL NOT NULL,
                    fahrenheit REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_synced BOOLEAN NOT NULL DEFAULT 0,
                    CONSTRAINT valid_temp_c CHECK (celsius BETWEEN -273.15 AND 1000),
                    CONSTRAINT valid_temp_f CHECK (fahrenheit BETWEEN -459.67 AND 1832)
                ) WITHOUT ROWID
            ''')
            
            # Create covering index for common queries
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_temp_sensor_time 
                ON temperature_readings(sensor_id, timestamp) 
                INCLUDE (celsius, fahrenheit, is_synced)
            ''')

            # Create partial index for unsynced readings
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_temp_unsynced
                ON temperature_readings(id)
                WHERE is_synced = 0
            ''')
            
            await conn.commit()

    async def store_reading(self, reading: TemperatureReading) -> None:
        """Store a temperature reading with optimized batch insert."""
        async with await self.db.get_connection() as conn:
            await conn.execute('''
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
            await conn.commit()

    async def get_readings(
        self,
        sensor_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[TemperatureReading]:
        """Get temperature readings with optimized query."""
        query = '''
            SELECT id, sensor_id, celsius, fahrenheit, timestamp, is_synced
            FROM temperature_readings 
            WHERE sensor_id = ? 
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        '''
        
        params = [sensor_id, start_time, end_time]
        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        async with await self.db.get_connection() as conn:
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [TemperatureReading(**dict(row)) for row in rows]

    async def get_unsynced_readings(self) -> List[TemperatureReading]:
        """Get unsynced readings using partial index."""
        async with await self.db.get_connection() as conn:
            async with conn.execute('''
                SELECT id, sensor_id, celsius, fahrenheit, timestamp, is_synced
                FROM temperature_readings 
                WHERE is_synced = 0
                LIMIT 100
            ''') as cursor:
                rows = await cursor.fetchall()
                return [TemperatureReading(**dict(row)) for row in rows]

    async def mark_as_synced(self, reading_ids: List[int]) -> None:
        """Mark readings as synced with optimized batch update."""
        if not reading_ids:
            return
            
        async with await self.db.get_connection() as conn:
            # Use chunking for large updates
            chunk_size = 500
            for i in range(0, len(reading_ids), chunk_size):
                chunk = reading_ids[i:i + chunk_size]
                placeholders = ','.join('?' * len(chunk))
                await conn.execute(
                    f'UPDATE temperature_readings SET is_synced = 1 WHERE id IN ({placeholders})',
                    chunk
                )
            await conn.commit()