from ..storage.database import ConnectionPool
from ..storage.temp_db import TemperatureRepository
from ..storage.device_stats import SystemMonitorRepository
from ..storage.sync_manager import SyncManager
from ..models.things import DeviceType
from ..utils.logging import get_logger
from ..utils.exceptions import DatabaseError
from typing import Optional

logger = get_logger(__name__)

class SensorDatabase:
    """Main database manager class"""
    def __init__(self, db_path: str, max_connections: int = 5):
        self.pool = ConnectionPool(db_path, max_connections)
        self.repositories = {}
        self.sync_manager = SyncManager(self)
        self._setup_repositories()
        # Add other repositories as needed
        self._retention_days = 30

    def _setup_repositories(self):
        """Initialize all repository instances"""
        self.repositories['temperature'] = TemperatureRepository(self.pool)
        self.repositories['system'] = SystemMonitorRepository(self.pool)
        # Add other repositories as needed
        # self.repositories['humidity'] = HumidityRepository(self.pool)
        # self.repositories['smart_plug'] = SmartPlugRepository(self.pool)

    async def initialize(self) -> None:
        """Initialize the database and all repositories"""
        await self.pool.initialize()
        
        async with self.pool.acquire() as conn:
            # Create devices table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    device_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP
                )
            ''')
            await conn.commit()

        # Initialize all repositories
        for repo in self.repositories.values():
            await repo.create_table()
            await repo.create_indices()

    async def register_device(self, device_id: str, device_type: DeviceType, name: str, location: Optional[str] = None) -> None:
        """Register a new device in the database."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT OR REPLACE INTO devices 
                    (device_id, device_type, name, location, last_seen)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (device_id, device_type.value, name, location))
                await conn.commit()
                logger.info(f"Registered device: {device_id} of type {device_type.value}")
        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            raise DatabaseError(f"Failed to register device: {e}")


    async def close(self) -> None:
        """Close all database connections"""
        await self.pool.close()