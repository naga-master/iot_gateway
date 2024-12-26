# src/iot_gateway/__main__.py
import asyncio
import signal
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
import traceback

from iot_gateway.core.event_manager import EventManager
from iot_gateway.core.device_manager import DeviceManager
from iot_gateway.core.temperature_monitor import TemperatureMonitor
from iot_gateway.adapters.gpio import GPIOAdapter
from iot_gateway.core.communication_service import CommunicationService
from iot_gateway.api.routes import temp_router
from iot_gateway.api.endpoints.devices import device_router
from iot_gateway.utils.logging import setup_logging, get_logger
from iot_gateway.utils.exceptions import ConfigurationError, InitializationError

class ConfigManager:
    """Manages configuration loading and validation"""
    
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """Load and validate configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                if config is None:
                    raise ConfigurationError("Configuration file is empty or incorrectly formatted")
                
                # Validate required configuration sections
                required_sections = ['api', 'communication', 'gpio', 'temperature_monitor', 'logging']
                missing_sections = [section for section in required_sections if section not in config]
                if missing_sections:
                    raise ConfigurationError(f"Missing required configuration sections: {', '.join(missing_sections)}")
                
                return config
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing configuration file: {traceback.format_exc()}")
        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {config_path}")

class APIServer:
    """Handles API server initialization and management"""
    
    def __init__(self, config: Dict[str, Any], shutdown_event: asyncio.Event):
        self.config = config
        self.shutdown_event = shutdown_event
        self.logger = get_logger("API Server")
        self.app: Optional[FastAPI] = None

    async def initialize(self) -> FastAPI:
        """Initialize FastAPI application with routes"""
        try:
            self.app = FastAPI(
                title="IoT Gateway API",
                description="API for managing IoT devices and temperature monitoring",
                version="1.0.0"
            )
            
            # Register routes
            self.app.include_router(temp_router, prefix="/api/v1")
            self.app.include_router(device_router, prefix="/api/v1")
            
            return self.app
        except Exception as e:
            raise InitializationError(f"Failed to initialize API server: {traceback.format_exc()}")

    async def start(self):
        """Start the API server"""
        if not self.app:
            await self.initialize()

        hypercorn_config = HyperConfig()
        try:
            host = self.config['api']['host']
            port = self.config['api']['port']
            hypercorn_config.bind = [f"{host}:{port}"]
            
            async def shutdown_trigger():
                await self.shutdown_event.wait()
                return
            
            self.logger.info(f"Starting API server on {host}:{port}")
            await serve(self.app, hypercorn_config, shutdown_trigger=shutdown_trigger)
        except Exception as e:
            self.logger.error(f"Failed to start API server: {traceback.format_exc()}")
            raise

class IoTGatewayApp:
    """Main IoT Gateway application class"""
    
    def __init__(self, config_path: str):
        self.logger = get_logger("Main App")
        try:
            self.config = ConfigManager.load_config(config_path)
            setup_logging(self.config.get('logging', {}))
        except ConfigurationError as e:
            self.logger.error(f"Configuration error: {traceback.format_exc()}")
            sys.exit(1)

        # Initialize components
        self.shutdown_event = asyncio.Event()
        self.event_manager = EventManager()
        self.api_server = APIServer(self.config, self.shutdown_event)
        
        # Components to be initialized later
        self.temperature_monitor = None
        self.communication_service = None
        self.device_manager = None

    async def initialize_components(self):
        """Initialize all application components"""
        try:
            # Start event processing
            asyncio.create_task(self.event_manager.process_events())
            
            # Initialize Communication Service
            self.communication_service = CommunicationService(self.config)
            await self.communication_service.initialize()
            
            # Initialize Device Manager
            self.device_manager = DeviceManager(
                self.event_manager,
                GPIOAdapter(self.config['gpio'])
            )
            await self.device_manager.initialize()
            
            # Initialize Temperature Monitor
            self.temperature_monitor = TemperatureMonitor(
                self.config,
                self.event_manager,
                self.communication_service
            )
            await self.temperature_monitor.initialize()
            
            self.logger.info("All components initialized successfully")
        except Exception as e:
            raise InitializationError(f"Failed to initialize components: {traceback.format_exc()}")

    async def start_temperature_monitoring(self):
        """Start temperature monitoring tasks"""
        try:
            monitor_task = asyncio.create_task(
                self.temperature_monitor.start_monitoring()
            )
            sync_task = asyncio.create_task(
                self.temperature_monitor.sync_stored_readings()
            )
            
            await asyncio.gather(monitor_task, sync_task)
        except Exception as e:
            self.logger.error(f"Error in temperature monitoring: {traceback.format_exc()}")
            await self.shutdown()

    async def shutdown(self):
        """Gracefully shutdown all components"""
        self.logger.info("Initiating shutdown sequence")
        try:
            if self.temperature_monitor:
                await self.temperature_monitor.stop()
            if self.communication_service:
                await self.communication_service.shutdown()
            # if self.device_manager:
            #     await self.device_manager.shutdown()
            
            self.shutdown_event.set()
            self.logger.info("Shutdown completed successfully")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {traceback.format_exc()}")

    def handle_signals(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}")
            asyncio.create_task(self.shutdown())

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, signal_handler)

    async def run(self):
        """Main application entry point"""
        try:
            self.handle_signals()
            await self.initialize_components()
            
            # Start all services
            await asyncio.gather(
                self.start_temperature_monitoring(),
                self.api_server.start()
            )
        except InitializationError as e:
            self.logger.error(f"Initialization error: {traceback.format_exc()}")
            await self.shutdown()
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error: {traceback.format_exc()}")
            await self.shutdown()
            sys.exit(1)

def create_default_config(config_path: Path):
    """Create default configuration file if it doesn't exist"""
    if not config_path.exists():
        example_config = """
api:
  host: "0.0.0.0"
  port: 8000

communication:
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
  file: "logs/iot_gateway.log"
  max_size: 10
  backup_count: 5
  format: "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"
"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(example_config)
        print(f"Created default config at {config_path}")

def main():
    """Application entry point"""
    config_path = Path("src/config/default.yml")
    create_default_config(config_path)
    
    app = IoTGatewayApp(str(config_path))
    asyncio.run(app.run())

if __name__ == "__main__":
    main()