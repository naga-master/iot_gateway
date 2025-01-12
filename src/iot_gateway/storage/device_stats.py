from typing import Dict, Any, Optional, List
from ..models.things import HearBeat
from datetime import datetime
from ..storage.database import ConnectionPool, BaseRepository
import aiosqlite
from ..utils.logging import get_logger
from ..utils.exceptions import DatabaseError


logger = get_logger(__name__)

class SystemMonitorRepository(BaseRepository[HearBeat]):
    def __init__(self, pool: ConnectionPool):
        super().__init__(pool)
        self.table_name = "system_heartbeats"

    async def create_table(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS system_heartbeats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    reading_id TEXT NOT NULL,
                    temperature TEXT NOT NULL,
                    available_memory TEXT NOT NULL,
                    cpu_usage TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_synced BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id),
                    UNIQUE(device_id, reading_id)
                )
            ''')
            await conn.commit()

    async def create_indices(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_heartbeat_device_time 
                ON system_heartbeats(device_id, timestamp)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_heartbeat_sync 
                ON system_heartbeats(is_synced)
            ''')
            await conn.commit()

    async def store_reading(self, reading: HearBeat) -> None:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO system_heartbeats 
                    (device_id, reading_id, temperature, available_memory, cpu_usage, 
                     timestamp, is_synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    reading.device_id,
                    reading.reading_id,
                    reading.temperature,
                    reading.available_memory,
                    reading.cpu_usage,
                    reading.timestamp,
                    reading.is_synced
                ))
                await conn.commit()
                logger.debug("Stored system metrics successfully")
        except Exception as e:
            logger.error(f"Failed to store system heartbeat: {e}")
            raise DatabaseError(f"Failed to store system heartbeat: {e}")
        

    async def get_readings(
        self,
        device_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[HearBeat]:
        """
        Retrieve system heartbeat readings for a device within a specified time range.
        
        Args:
            device_id: The ID of the device to get readings for
            start_time: Start of the time range
            end_time: End of the time range
            limit: Optional limit on number of readings to return
            
        Returns:
            List of HearBeat objects ordered by timestamp descending
        """
        query = '''
            SELECT * FROM system_heartbeats 
            WHERE device_id = ? 
            AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        '''
        params = [device_id, start_time, end_time]
        
        if limit is not None:
            query += ' LIMIT ?'
            params.append(limit)

        try:
            async with self.pool.acquire() as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_reading(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get system heartbeat readings: {e}")
            raise DatabaseError(f"Failed to get system heartbeat readings: {e}")
        

    def _row_to_reading(self, row: Dict[str, Any]) -> HearBeat:
        return HearBeat(
            device_id=row['device_id'],
            reading_id=row['reading_id'],
            temperature=row['temperature'],
            available_memory=row['available_memory'],
            cpu_usage=row['cpu_usage'],
            timestamp=row['timestamp'],
            is_synced=bool(row['is_synced'])
        )