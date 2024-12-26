# src/iot_gateway/__main__.py
import asyncio
import signal
import sys
import yaml
from pathlib import Path
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig

from .core.temperature_monitor import TemperatureMonitor
from .api.routes import router
from .utils.logging import setup_logging

def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

class IoTGatewayApp:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.temperature_monitor = None
        self.api_app = None
        self.shutdown_event = asyncio.Event()
        
        # Setup logging
        setup_logging(self.config.get('logging', {}))

    async def start_api(self):
        self.api_app = FastAPI(title="IoT Gateway API")
        self.api_app.include_router(router, prefix="/api/v1")
        
        hypercorn_config = HyperConfig()
        hypercorn_config.bind = [f"{self.config['api']['host']}:{self.config['api']['port']}"]
        
        # Start API server
        await serve(self.api_app, hypercorn_config, shutdown_trigger=self.shutdown_event.wait)

    async def start_monitor(self):
        self.temperature_monitor = TemperatureMonitor(self.config['temperature_monitor'])
        await self.temperature_monitor.initialize()
        
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

    def handle_shutdown(self, signum, frame):
        print("Received shutdown signal. Shutting down gracefully...")
        self.shutdown_event.set()

    async def run(self):
        try:
            # Setup signal handlers
            self.handle_signals()
            
            # Start all components
            await asyncio.gather(
                self.start_monitor(),
                self.start_api()
            )
        except Exception as e:
            print(f"Error starting application: {e}")
            sys.exit(1)

# Example config.yml
example_config = """
api:
  host: "0.0.0.0"
  port: 8000

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
  mqtt:
    host: "localhost"
    port: 1883
    username: "user"
    password: "pass"
  reading_interval: 60  # seconds
  sync_interval: 300    # seconds

logging:
  level: "INFO"
  file: "iot_gateway.log"
"""

def main():
    # Create default config if it doesn't exist
    config_path = Path("config.yml")
    if not config_path.exists():
        with open(config_path, 'w') as f:
            f.write(example_config)
        print("Created default config.yml")
    
    app = IoTGatewayApp(str(config_path))
    asyncio.run(app.run())

if __name__ == "__main__":
    main()
