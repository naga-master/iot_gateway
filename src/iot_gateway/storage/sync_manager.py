import asyncio
from typing import Dict, List, Any, Set, Tuple
# from ..storage.sensor_database import SensorDatabase
from ..utils.logging import get_logger


logger = get_logger(__name__)

class RepositorySyncTracker:
    """Tracks in-progress syncs for a single repository"""
    def __init__(self):
        self._in_progress: Set[Tuple[str, str]] = set() # reading_id, device_id
        self._failed_syncs: Dict[Tuple[str, str], int] = {}  # Tracks failed attempts
        self._lock = asyncio.Lock()
    
    async def add_sync(self, device_id: str, reading_id: str) -> bool:
        """Add a sync operation. Returns False only if currently in progress."""
        key = (device_id, reading_id)
        async with self._lock:
            if key in self._in_progress:
                logger.info(f"Sync already in progress for {device_id}:{reading_id}")
                return False
            
            # Reset failed count if it exists
            if key in self._failed_syncs:
                logger.info(f"Retrying previously failed sync for {device_id}:{reading_id}")
                self._failed_syncs.pop(key)
                
            self._in_progress.add(key)
            return True
    
    async def mark_sync_failed(self, device_id: str, reading_id: str):
        """Record a failed sync attempt"""
        key = (device_id, reading_id)
        async with self._lock:
            count = self._failed_syncs.get(key, 0) + 1
            self._failed_syncs[key] = count
            logger.warning(f"Sync failed for {device_id}:{reading_id} (attempt {count})")
    
    async def remove_sync(self, device_id: str, reading_id: str):
        """Remove from in-progress tracking"""
        async with self._lock:
            self._in_progress.discard((device_id, reading_id))

class SyncManager:
    def __init__(self, db, max_retry_count: int = 3):
        self.db = db
        self.max_retry_count = max_retry_count
        self._sync_lock = asyncio.Lock()
        self._repo_trackers: Dict[str, RepositorySyncTracker] = {
            name: RepositorySyncTracker() 
            for name in db.repositories.keys()
        }
    async def mark_single_as_synced(self, 
                                  repository_name: str,
                                  device_id: str, 
                                  reading_id: str) -> None:
        """Mark a single reading as synced for a specific repository"""
        if repository_name not in self.db.repositories:
            raise ValueError(f"Unknown repository: {repository_name}")
            
        repo = self.db.repositories[repository_name]
        tracker = self._repo_trackers[repository_name]
        
        # If we can't claim the sync (because it's in progress), just return
        if not await tracker.add_sync(device_id, reading_id):
            return
            
        try:
            # Perform the actual sync
            await repo.mark_as_synced(device_id, reading_id)
            logger.info(f"Successfully synced reading {reading_id} from device {device_id}")
            
        except Exception as e:
            # Record the failure
            await tracker.mark_sync_failed(device_id, reading_id)
            logger.error(f"Failed to sync reading {reading_id} from device {device_id}: {e}")
            raise
            
        finally:
            # Remove from in-progress tracking
            await tracker.remove_sync(device_id, reading_id)

    async def get_all_unsynced_readings(self) -> Dict[str, List[Any]]:
        """Get all unsynced readings from all repositories"""
        async with self._sync_lock:
            results = {}
            for repo_name, repo in self.db.repositories.items():
                tracker = self._repo_trackers[repo_name]
                readings = await repo.get_unsynced_readings()
                
                # Only filter out readings that are currently in progress
                filtered_readings = [
                    reading for reading in readings 
                    if (reading.device_id, reading.reading_id) not in tracker._in_progress
                ]
                
                results[repo_name] = filtered_readings
            return results

    async def get_failed_syncs(self, repository_name: str) -> List[Tuple[str, str, int]]:
        """Get list of failed syncs and their attempt counts"""
        if repository_name not in self._repo_trackers:
            raise ValueError(f"Unknown repository: {repository_name}")
            
        tracker = self._repo_trackers[repository_name]
        async with tracker._lock:
            return [(dev_id, read_id, count) 
                   for (dev_id, read_id), count 
                   in tracker._failed_syncs.items()]
