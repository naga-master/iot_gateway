# Offline data synchronization
from typing import List, Dict, Any, Optional, Type
from abc import ABC, abstractmethod
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from dataclasses import asdict
import aiomqtt
from collections import defaultdict
from ..utils.logging import get_logger
from ..storage.database import DatabaseHandler, SensorDatabaseHandler
from ..utils.retry import async_retry_with_backoff
from .cache import SyncCache
'''
Usage:

# Initialize sync manager
self.sync_manager = SyncManager(self.config, self.storage.db)
await self.sync_manager.initialize()

# In your initialization
async def initialize(self) -> None:
    logger.info("Initializing Temperature Monitor")
    await self.storage.initialize()
    await self.sync_manager.initialize()
    
    # Start sync loop in background
    asyncio.create_task(self.sync_manager.start_sync_loop())

# Store reading remains the same
await self.storage.store_reading(reading)

# Sync is now handled automatically by sync_manager
# You don't need to manually call get_unsynced_readings or mark_as_synced

# Get readings remains the same
readings = await storage.get_readings(
    sensor_id,
    start_time or datetime.now() - timedelta(hours=24),
    end_time or datetime.now()
)
'''

logger = get_logger(__name__)

class SyncManager:
    def __init__(self, config: Dict[str, Any], database_handler: DatabaseHandler):
        self.config = config
        self.db = database_handler
        self.sync_handlers: Dict[str, SyncProtocolHandler] = {}
        self.cache = SyncCache(
            max_size=config.get("sync", {}).get("cache_size", 1000),
            expiry_time=config.get("sync", {}).get("cache_expiry", 3600)
        )
        
        # Initialize protocol handlers based on config
        if self.config["communication"]["mqtt"]["enabled"]:
            self.sync_handlers["mqtt"] = MQTTSyncHandler(
                self.config["communication"]["mqtt"]
            )
            
        if self.config["communication"]["rest"]["enabled"]:
            self.sync_handlers["rest"] = RESTSyncHandler(
                self.config["communication"]["rest"]
            )

    async def initialize(self) -> None:
        """Initialize sync manager and its handlers."""
        logger.info("Initializing Sync Manager")
        for handler in self.sync_handlers.values():
            await handler.initialize()

    async def sync_data(self, sensor_handler: SensorDatabaseHandler) -> None:
        """Sync unsynced data for a specific sensor type."""
        try:
            # Get unsynced readings with batching
            batch_size = self.config["sync"]["batch_size"]
            unsynced = await sensor_handler.get_unsynced_readings()
            
            if not unsynced:
                return

            # Group readings by protocol for efficient syncing
            protocol_groups = defaultdict(list)
            for reading in unsynced:
                # Get sensor info to determine protocol
                sensor_info = await self.db.get_sensor_info(reading.sensor_id)
                if sensor_info:
                    protocol_groups[sensor_info["protocol"]].append(reading)

            successful_ids = []
            failed_ids = []

            # Sync each protocol group
            for protocol, readings in protocol_groups.items():
                if protocol in self.sync_handlers:
                    handler = self.sync_handlers[protocol]
                    
                    # Process in batches
                    for i in range(0, len(readings), batch_size):
                        batch = readings[i:i + batch_size]
                        try:
                            # Try to sync from cache first
                            cached_batch = [
                                reading for reading in batch
                                if not self.cache.get(f"{reading.sensor_id}_{reading.timestamp}")
                            ]
                            
                            if cached_batch:
                                success = await handler.sync_batch(cached_batch)
                                if success:
                                    # Update cache and track successful syncs
                                    for reading in cached_batch:
                                        cache_key = f"{reading.sensor_id}_{reading.timestamp}"
                                        self.cache.set(cache_key, asdict(reading))
                                        successful_ids.append(reading.id)
                                else:
                                    failed_ids.extend(r.id for r in cached_batch)
                            else:
                                successful_ids.extend(r.id for r in batch)
                                
                        except Exception as e:
                            logger.error(f"Failed to sync batch: {str(e)}")
                            failed_ids.extend(r.id for r in batch)

            # Mark successfully synced readings
            if successful_ids:
                await sensor_handler.mark_as_synced(successful_ids)

            # Handle failed syncs
            if failed_ids:
                logger.warning(f"Failed to sync {len(failed_ids)} readings")
                # Implement retry logic or alert system here

        except Exception as e:
            logger.error(f"Error in sync_data: {str(e)}")
            raise

    async def start_sync_loop(self) -> None:
        """Start the continuous sync loop."""
        while True:
            try:
                # Get all sensor handlers
                sensor_handlers = self._get_sensor_handlers()
                
                # Sync each sensor type
                for handler in sensor_handlers:
                    await self.sync_data(handler)
                    
                # Wait for next sync interval
                await asyncio.sleep(self.config["sync"]["interval"])
                
            except Exception as e:
                logger.error(f"Error in sync loop: {str(e)}")
                await asyncio.sleep(self.config["sync"]["error_retry_interval"])

    def _get_sensor_handlers(self) -> List[SensorDatabaseHandler]:
        """Get all configured sensor handlers."""
        # Implementation depends on your sensor configuration
        return []

class SyncProtocolHandler(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def sync_batch(self, readings: List[Any]) -> bool:
        pass

class MQTTSyncHandler(SyncProtocolHandler):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.connected = False

    async def initialize(self) -> None:
        """Initialize MQTT client connection."""
        try:
            self.client = aiomqtt.Client(
                hostname=self.config["broker"],
                port=self.config["port"],
                username=self.config.get("username"),
                password=self.config.get("password")
            )
            await self.client.connect()
            self.connected = True
        except Exception as e:
            logger.error(f"Failed to initialize MQTT: {str(e)}")
            self.connected = False

    @async_retry_with_backoff(max_retries=3, base_delay=1, max_delay=30.0, exceptions=(ConnectionError, TimeoutError))
    async def sync_batch(self, readings: List[Any]) -> bool:
        """Sync a batch of readings via MQTT."""
        if not self.connected:
            await self.initialize()
            
        try:
            # Convert readings to MQTT message format
            messages = [asdict(reading) for reading in readings]
            
            # Publish messages
            for msg in messages:
                topic = f"{self.config['topic_prefix']}/{msg['sensor_id']}"
                await self.client.publish(
                    topic,
                    payload=json.dumps(msg),
                    qos=self.config["qos"]
                )
                
            return True
            
        except Exception as e:
            logger.error(f"MQTT sync failed: {str(e)}")
            self.connected = False
            raise

class RESTSyncHandler(SyncProtocolHandler):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.session = None

    async def initialize(self) -> None:
        """Initialize HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    @async_retry_with_backoff(max_retries=3, base_delay=1, max_delay=30.0, exceptions=(ConnectionError, TimeoutError))
    async def sync_batch(self, readings: List[Any]) -> bool:
        """Sync a batch of readings via REST API."""
        try:
            if not self.session:
                await self.initialize()

            # Convert readings to API format
            payload = {
                "readings": [asdict(reading) for reading in readings],
                "device_id": self.config["device_id"]
            }

            # Send data to API
            async with self.session.post(
                self.config["endpoint"],
                json=payload,
                headers=self.config.get("headers", {}),
                timeout=self.config["timeout"]
            ) as response:
                if response.status == 200:
                    return True
                else:
                    logger.error(f"API sync failed with status {response.status}")
                    return False

        except Exception as e:
            logger.error(f"REST sync failed: {str(e)}")
            raise