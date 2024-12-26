# Core components
from abc import ABC, abstractmethod
from typing import Dict, Any
import asyncio
import logging
from dataclasses import dataclass
import json

# Configuration Management
@dataclass
class SystemConfig:
    device_configs: Dict[str, Any]
    protocol_configs: Dict[str, Any]
    processing_rules: Dict[str, Any]

class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> SystemConfig:
        with open(self.config_path) as f:
            config_data = json.load(f)
        return SystemConfig(**config_data)

# Protocol Adapters
class ProtocolAdapter(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def read_data(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def write_data(self, data: Dict[str, Any]) -> None:
        pass

class BluetoothAdapter(ProtocolAdapter):
    async def connect(self) -> None:
        # Implementation
        pass

# Event Management
class EventManager:
    def __init__(self):
        self.subscribers = {}
        self.event_queue = asyncio.Queue()

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        await self.event_queue.put((event_type, data))
        
    async def subscribe(self, event_type: str, callback) -> None:
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    async def process_events(self) -> None:
        while True:
            event_type, data = await self.event_queue.get()
            if event_type in self.subscribers:
                for callback in self.subscribers[event_type]:
                    await callback(data)

# Business Logic Processing
class BusinessProcessor:
    def __init__(self, rules_config: Dict[str, Any]):
        self.rules = rules_config

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Apply business rules
        return processed_data

# Data Storage
class StorageManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.offline_queue = asyncio.Queue()

    async def store(self, data: Dict[str, Any]) -> None:
        try:
            # Store in database
            pass
        except ConnectionError:
            await self.offline_queue.put(data)

    async def sync_offline_data(self) -> None:
        while not self.offline_queue.empty():
            data = await self.offline_queue.get()
            await self.store(data)

# Main Application
class IoTGateway:
    def __init__(self, config_path: str):
        self.config_manager = ConfigManager(config_path)
        self.event_manager = EventManager()
        self.storage_manager = StorageManager("db.sqlite")
        self.business_processor = BusinessProcessor(
            self.config_manager.config.processing_rules
        )
        self.protocol_adapters = self._init_protocol_adapters()

    def _init_protocol_adapters(self) -> Dict[str, ProtocolAdapter]:
        # Initialize protocol adapters based on configuration
        pass

    async def start(self) -> None:
        # Start event processing
        asyncio.create_task(self.event_manager.process_events())
        
        # Connect all protocol adapters
        for adapter in self.protocol_adapters.values():
            await adapter.connect()

    async def stop(self) -> None:
        # Cleanup and disconnect
        for adapter in self.protocol_adapters.values():
            await adapter.disconnect()

# Usage Example
async def main():
    gateway = IoTGateway("config.json")
    await gateway.start()
    
    try:
        # Keep the gateway running
        await asyncio.Event().wait()
    finally:
        await gateway.stop()

if __name__ == "__main__":
    asyncio.run(main())
