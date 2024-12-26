# src/iot_gateway/__main__.py
import asyncio
import signal
import yaml
import logging
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
import sys

from iot_gateway.core.event_manager import EventManager
from iot_gateway.core.device_manager import DeviceManager
from iot_gateway.core.temperature_monitor import TemperatureMonitor
from iot_gateway.adapters.mqtt import MQTTAdapter
from iot_gateway.adapters.gpio import GPIOAdapter
# from iot_gateway.sensors.temperature import TemperatureMonitor
from iot_gateway.storage.database import TemperatureStorage
from iot_gateway.api.routes import temp_router
from iot_gateway.api.endpoints.devices import device_router
from iot_gateway.utils.logging import setup_logging, get_logger
from iot_gateway.core.communication_service import CommunicationService

def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        print("Opening Config file", config_path)
        config = yaml.safe_load(f)
        if config is None:
            raise ValueError("Configuration file is empty or incorrectly formatted")
        print("Loaded config:", config)
        return config

class IoTGatewayApp:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.temperature_monitor = None
        self.communication_service = None
        self.api_app = None
        self.shutdown_event = asyncio.Event()
        self.event_manager = EventManager()
        self.device_manager = None
        
        # Setup logging
        setup_logging(self.config.get('logging', {}))
        self.logger = get_logger("Main App")

    async def initialize(self):
        self.logger.info("Initializing IoT Gateway")
        # Start event processing loop
        asyncio.create_task(self.event_manager.process_events())

        # Initialize Communication Service
        self.communication_service = CommunicationService(self.config)
        await self.communication_service.initialize()
        self.logger.info("Initializing communication service")

        # Initialize device manager
        self.device_manager = DeviceManager(self.event_manager, GPIOAdapter(self.config['gpio']))
        await self.device_manager.initialize()
        self.logger.info("Initializing device manager")

    async def start_api(self):
        self.logger.info("IoT Gateway API Service Starting")
        #  FastAPI app is created
        self.api_app = FastAPI(title="IoT Gateway API")
        # 2. Routes are registered
        self.api_app.include_router(temp_router, prefix="/api/v1")
        self.api_app.include_router(device_router, prefix="/api/v1")
        
        hypercorn_config = HyperConfig()
        hypercorn_config.bind = [f"{self.config['api']['host']}:{self.config['api']['port']}"]
        self.logger.info(f"IoT Gateway API route binded {hypercorn_config}, {self.api_app}, {self.shutdown_event.wait}")

        # Create a proper shutdown trigger function
        async def shutdown_trigger():
            await self.shutdown_event.wait()
            return
    
        # Start API server
        try:
          await serve(self.api_app, hypercorn_config, shutdown_trigger=shutdown_trigger)
          self.logger.info("IoT Gateway API Started")
        except Exception as e:
            self.logger.error(f"Failed to start API server: {e}")
            raise
        self.logger.info("IoT Gateway API Started")

    async def start_monitor(self):
        self.temperature_monitor = TemperatureMonitor(self.config['temperature_monitor'], 
                                                      self.event_manager, self.communication_service)
        await self.temperature_monitor.initialize()
        self.logger.info("Initializing temperature monitor")
        
        # Start monitoring and syncing in separate tasks
        monitor_task = asyncio.create_task(self.temperature_monitor.start_monitoring())
        sync_task = asyncio.create_task(self.temperature_monitor.sync_stored_readings())
        
        # Wait for shutdown
        await self.shutdown_event.wait()
        
        # Clean shutdown
        await self.temperature_monitor.stop()
        await asyncio.gather(monitor_task, sync_task, return_exceptions=True)

    def handle_signals(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self.handle_shutdown)

    async def shutdown(self):
        print("Received shutdown signal. Shutting down services gracefully...")
        if self.temperature_monitor:
            await self.temperature_monitor.stop()
        if self.communication_service:
            await self.communication_service.shutdown()
        self.shutdown_event.set()

    def handle_shutdown(self, signum, frame):
        print("Received shutdown signal. Shutting down gracefully...")
        self.shutdown_event.set()

    async def run(self):
        try:
            # Signal handlers are set up for graceful shutdown
            self.handle_signals()
            
            # Start all components
            # Create tasks explicitly
            # monitor_task = asyncio.create_task(self.start_monitor()) # Temperature monitoring
            # api_task = asyncio.create_task(self.start_api()) # API server
            
            # Wait for both tasks
            # await asyncio.gather(monitor_task, api_task)
            await self.initialize()
            await asyncio.gather(
                self.start_monitor(), 
                self.start_api()
            )
        except Exception as e:
            print(f"Error starting application: {e}")
            await self.shutdown()
            sys.exit(1)



# Example config.yml
example_config = """
api:
  host: "0.0.0.0"
  port: 8000

# config.yml
communication:
  mqtt:
    host: "localhost"
    port: 1883
    username: "user"
    password: "pass"
  # Future communication configs
  # wifi:
  #   ssid: "network"
  #   password: "pass"

gpio:
  pins:
    bulb1:
      pin: 5
      type: "output"
      initial: false

temperature_monitor:
  database:
    path: "temperature.db"
  sensors:
    - id: "sensor1"
      bus: 1
      address: 0x48
    - id: "sensor2"
      bus: 1
      address: 0x49
  reading_interval: 60
  sync_interval: 300

logging:
  level: "INFO"
  file: "logs/iot_gateway.log"
  max_size: 10  # MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"
"""

def main():
    # Create default config if it doesn't exist
    config_path = Path("src/config/default.yml")
    print(config_path, config_path.exists())
    if not config_path.exists():
        with open(config_path, 'w') as f:
            f.write(example_config)
        print("Created default config at src/config/default.yml")
    
    app = IoTGatewayApp(str(config_path))
    asyncio.run(app.run()) # This kicks off everything

if __name__ == "__main__":
    main()