import asyncio
from typing import Dict, List, Any
# from ..storage.sensor_database import SensorDatabase

class SyncManager:
    """Manages synchronization operations across all repositories"""
    def __init__(self, db):
        self.db = db
        self._sync_lock = asyncio.Lock()

    async def get_all_unsynced_readings(self) -> Dict[str, List[Any]]:
        """Get all unsynced readings from all repositories"""
        async with self._sync_lock:
            results = {}
            for repo_name, repo in self.db.repositories.items():
                results[repo_name] = await repo.get_unsynced_readings()
            return results

    async def bulk_mark_as_synced(self, 
                                repository_name: str,
                                device_ids: List[str], 
                                reading_ids: List[str]) -> None:
        """Mark multiple readings as synced for a specific repository"""
        if repository_name not in self.db.repositories:
            raise ValueError(f"Unknown repository: {repository_name}")
            
        repo = self.db.repositories[repository_name]
        async with self._sync_lock:
            await repo.bulk_mark_as_synced(device_ids, reading_ids)