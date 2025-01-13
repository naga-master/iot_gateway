from ..storage.database import ConnectionPool
from ..storage.temp_db import TemperatureRepository
from ..storage.device_stats import SystemMonitorRepository
from ..storage.sync_manager import SyncManager
from ..models.things import DeviceType
from ..utils.logging import get_logger
from ..utils.exceptions import DatabaseError
from typing import Optional
from datetime import datetime, timedelta
import asyncio

logger = get_logger(__name__)

class SensorDatabase:
    """Main database manager class"""
    def __init__(self, db_path: str, max_connections: int = 5, retention_days: int = 30):
        self.pool = ConnectionPool(db_path, max_connections)
        self.repositories = {}
        self.sync_manager = SyncManager(self)
        self._setup_repositories()
        # Add other repositories as needed
        self.retention_days = retention_days
        self._cleanup_task = None
        self._cleanup_running = False

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

        # Start the cleanup task
        self._cleanup_running = True
        self._cleanup_task = asyncio.create_task(self._run_daily_cleanup())
        logger.info("Started database cleanup task")

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
        
    async def cleanup_old_data(self) -> None:
        """Delete synced readings older than retention_days"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_counts = {}

        try:
            async with self.pool.acquire() as conn:
                for table_name, repo in self.repositories.items():
                    query = f'''
                        DELETE FROM {repo.table_name}
                        WHERE is_synced = 1
                        AND timestamp < ?
                    '''
                    cursor = await conn.execute(query, (cutoff_date,))
                    deleted_counts[table_name] = cursor.rowcount
                await conn.commit()

            total_deleted = sum(deleted_counts.values())
            logger.info(
                f"Cleaned up {total_deleted} old records older than {self.retention_days} days: "
                f"{', '.join(f'{k}: {v}' for k, v in deleted_counts.items())}"
            )
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            raise DatabaseError(f"Failed to cleanup old data: {e}")
        
    async def _run_daily_cleanup(self) -> None:
        """Run the cleanup task daily"""
        while self._cleanup_running:
            try:
                await self.cleanup_old_data()
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
            
            try:
                # Sleep for 24 hours, but check every minute if we should stop
                for _ in range(24 * 60):  # 24 hours * 60 minutes
                    if not self._cleanup_running:
                        break
                    await asyncio.sleep(60)  # 1 minute
            except asyncio.CancelledError:
                break


    @property
    def retention_days(self) -> int:
        return self._retention_days
    
    @retention_days.setter
    def retention_days(self, days: int) -> None:
        if not isinstance(days, int) or days < 1:
            raise ValueError("retention_days must be a positive integer")
        self._retention_days = days

    async def close(self) -> None:
        """Close all database connections and stop the cleanup task"""
        logger.info("Shutting down database...")
        
        # Stop the cleanup task
        self._cleanup_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Cleanup task stopped")

        await self.pool.close()
        logger.info("Database connections closed")