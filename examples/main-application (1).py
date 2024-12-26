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

from .core.event_manager import EventManager
from .core.device_manager import DeviceManager
from .core.temperature_monitor import TemperatureMonitor
from .adapters.mqtt_client import MQTTAdapter
from .adapters.gpio_controller import GPIOAdapter
from .adapters.i2c_temp import I2CTemperatureSensor
from .storage.database import TemperatureStorage
from .api.routes import router as api_router
from .api.endpoints.devices import router as device_router
from .utils.logging import setup_logging

class IoTGateway:
    """
    Main application class that initializes and manages all components.
    
    Extension Points:
    1. Add new adapters in self.init_adapters()
    2. Add new managers in self.init_managers()
    3. Add new API routes in self.init_api()
    4. Add new tasks in self.start_background_tasks()
    """
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.event_manager = EventManager()
        self.components = {}
        self.tasks = []
        self.shutdown_event = asyncio.Event()
        
        # Setup logging
        setup_logging(self.config.get('logging', {}))
        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    async def init_adapters(self) -> None:
        """
        Initialize all adapters.
        Extension Point: Add new adapter initialization here.
        """
        try:
            # Initialize MQTT
            mqtt_adapter = MQTTAdapter(self.config['mqtt'])
            await mqtt_adapter.connect()
            self.components['mqtt'] = mqtt_adapter

            # Initialize GPIO
            gpio_adapter = GPIOAdapter(self.config['gpio'])
            await gpio_adapter.connect()
            self.components['gpio'] = gpio_adapter

            # Initialize Temperature Sensors
            temp_sensors = []
            for sensor_config in self.config['temperature_monitor']['sensors']:
                sensor = I2CTemperatureSensor(
                    bus_number=sensor_config['bus'],
                    address=sensor_config['address'],
                    sensor_id=sensor_config['id']
                )
                await sensor.connect()
                temp_sensors.append(sensor)
            self.components['temp_sensors'] = temp_sensors

            self.logger.info("All adapters initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize adapters: {e}")
            raise

    async def init_managers(self) -> None:
        """
        Initialize all managers.
        Extension Point: Add new manager initialization here.
        """
        try:
            # Initialize Device Manager
            device_manager = DeviceManager(
                self.event_manager,
                self.components['gpio']
            )
            await device_manager.initialize()
            self.components['device_manager'] = device_manager

            # Initialize Temperature Monitor
            temp_monitor = TemperatureMonitor(
                self.config['temperature_monitor'],
                self.components['temp_sensors'],
                self.components['mqtt']
            )
            await temp_monitor.initialize()
            self.components['temp_monitor'] = temp_monitor

            self.logger.info("All managers initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize managers: {e}")
            raise

    def init_api(self) -> FastAPI:
        """
        Initialize FastAPI application.
        Extension Point: Add new API routes here.
        """
        app = FastAPI(title="IoT Gateway API")
        
        # Add routes
        app.include_router(api_router, prefix="/api/v1")
        app.include_router(device_router, prefix="/api/v1")
        
        # Add any new route here
        # app.include_router(new_router, prefix="/api/v1")
        
        return app

    async def start_background_tasks(self) -> None:
        """
        Start background tasks.
        Extension Point: Add new background tasks here.
        """
        # Temperature monitoring task
        self.tasks.append(
            asyncio.create_task(
                self.components['temp_monitor'].start_monitoring()
            )
        )
        
        # Temperature data sync task
        self.tasks.append(
            asyncio.create_task(
                self.components['temp_monitor'].sync_stored_readings()
            )
        )
        
        # Add any new background tasks here
        # self.tasks.append(asyncio.create_task(new_background_task()))

    async def cleanup(self) -> None:
        """Cleanup all components and tasks."""
        self.logger.info("Starting cleanup...")
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Cleanup components
        for name, component in self.components.items():
            try:
                if hasattr(component, 'disconnect'):
                    await component.disconnect()
                elif hasattr(component, 'stop'):
                    await component.stop()
            except Exception as e:
                self.logger.error(f"Error cleaning up {name}: {e}")

        self.logger.info("Cleanup completed")

    async def run(self) -> None:
        """Main application runner."""
        try:
            # Initialize components
            await self.init_adapters()
            await self.init_managers()
            
            # Initialize API
            app = self.init_api()
            
            # Configure Hypercorn
            hypercorn_config = HyperConfig()
            hypercorn_config.bind = [
                f"{self.config['api']['host']}:{self.config['api']['port']}"
            ]
            
            # Start background tasks
            await self.start_background_tasks()
            
            # Start API server
            await serve(
                app,
                hypercorn_config,
                shutdown_trigger=self.shutdown_event.wait
            )
            
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            raise
        finally:
            await self.cleanup()

    def handle_signals(self) -> None:
        """Setup signal handlers."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}")
            self.shutdown_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, signal_handler)

def main():
    # Create default config if it doesn't exist
    config_path = Path("config.yml")
    if not config_path.exists():
        default_config = """
api:
  host: "0.0.0.0"
  port: 8000

mqtt:
  host: "localhost"
  port: 1883
  username: "user"
  password: "pass"

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
  file: "iot_gateway.log"
"""
        with open(config_path, 'w') as f:
            f.write(default_config)
        print("Created default config.yml")

    # Start the application
    gateway = IoTGateway(str(config_path))
    gateway.handle_signals()
    
    try:
        asyncio.run(gateway.run())
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()
