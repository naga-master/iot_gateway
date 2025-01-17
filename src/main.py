# src/iot_gateway/__main__.py
import asyncio
import signal
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
from fastapi.staticfiles import StaticFiles
import traceback
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request

from iot_gateway.core.event_manager import EventManager
from iot_gateway.core.device_manager import DeviceManager
from iot_gateway.core.temperature_monitor import TemperatureMonitor
from iot_gateway.core.heartbeat import SystemMonitor
from iot_gateway.adapters.gpio import GPIOAdapter
from iot_gateway.core.communication_service import CommunicationService
from iot_gateway.api.routes import temp_router
from iot_gateway.api.endpoints.devices import device_router
from iot_gateway.api.endpoints.ui_config import ui_config_router
from iot_gateway.utils.logging import setup_logging, get_logger
from iot_gateway.utils.exceptions import ConfigurationError, InitializationError
from iot_gateway.storage.sensor_database import SensorDatabase

class AppState:
    """Holds application state and components"""
    def __init__(self):
        self.temperature_monitor: Optional[TemperatureMonitor] = None
        self.db: Optional[SensorDatabase] = None
        self.device_manager: Optional[DeviceManager] = None
        self.event_manager: Optional[EventManager] = None
        self.communication_service: Optional[CommunicationService] = None
        self.system_monitor: Optional[SystemMonitor] = None

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
                required_sections = ['api', 'communication', 'devices', 'logging']
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
    
    def __init__(self, config: Dict[str, Any], shutdown_event: asyncio.Event, app_state: AppState):
        self.config = config
        self.shutdown_event = shutdown_event
        self.logger = get_logger("API Server")
        self.app: Optional[FastAPI] = None
        self.app_state = app_state
        self.templates: Optional[Jinja2Templates] = None

    async def initialize(self) -> FastAPI:
        """Initialize FastAPI application with routes"""
        try:
            self.app = FastAPI(
                title="IoT Gateway API",
                description="IoT Gateway service managing sensors and communication",
                version="1.0.0"
            )

            # Initialize templates
            self.templates = Jinja2Templates(directory="src/templates")

            # Serve static files
            self.app.mount("/static", StaticFiles(directory="src/static"), name="static")
            
            # Store app state for dependency injection
            self.app.state.components = self.app_state
            
            # Register routes
            self.app.include_router(temp_router, prefix="/api/v1")
            self.app.include_router(device_router, prefix="/api/v1")
            self.app.include_router(ui_config_router, prefix="")
            
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
        self.app_state = AppState()
        self.app_state.event_manager = EventManager()
        self.api_server = APIServer(self.config, self.shutdown_event, self.app_state)

    async def initialize_components(self):
        """Initialize all application components"""
        try:
            # Start event processing
            asyncio.create_task(self.app_state.event_manager.process_events())

            # Initialize Device Manager
            self.app_state.device_manager = DeviceManager(
                self.app_state.event_manager,
                GPIOAdapter(self.config['devices']),
                self.config['devices']
            )
            await self.app_state.device_manager.initialize()

            # Initialize database
            self.app_state.db = SensorDatabase(self.config['database']['path'], 
                                               max_connections=self.config['database']['pool_size'],
                                               retention_days=self.config['database']['retention_days'])
            await self.app_state.db.initialize()
            
            # Initialize Communication Service
            self.app_state.communication_service = CommunicationService(
                self.config, 
                event_manager=self.app_state.event_manager
            )
            await self.app_state.communication_service.initialize()
            
            # Initialize Temperature Monitor
            self.app_state.temperature_monitor = TemperatureMonitor(
                self.config,
                self.app_state.event_manager,
                self.app_state.db,
                self.app_state.communication_service.mqtt
            )
            await self.app_state.temperature_monitor.initialize()

            # Initialize System Monitoring
            self.app_state.system_monitor = SystemMonitor(
                config=self.config,
                db=self.app_state.db,
                mqtt=self.app_state.communication_service.mqtt
            )
            await self.app_state.system_monitor.initialize()
            
            self.logger.info("All components initialized successfully")
        except Exception as e:
            raise InitializationError(f"Failed to initialize components: {traceback.format_exc()}")

    async def start_temperature_monitoring(self):
        """Start temperature monitoring tasks"""
        try:
            monitor_task = asyncio.create_task(
                self.app_state.temperature_monitor.start_monitoring()
            )
            sync_task = asyncio.create_task(
                self.app_state.temperature_monitor.sync_stored_readings()
            )
            
            await asyncio.gather(monitor_task, sync_task)
        except Exception as e:
            self.logger.error(f"Error in temperature monitoring: {traceback.format_exc()}")
            await self.shutdown()

    async def shutdown(self):
        """Gracefully shutdown all components"""
        self.logger.info("Initiating shutdown sequence")
        try:
            if self.app_state.temperature_monitor:
                await self.app_state.temperature_monitor.stop()
            if self.app_state.communication_service:
                await self.app_state.communication_service.shutdown()
            if self.app_state.system_monitor:
                await self.app_state.system_monitor.stop()
            if self.app_state.db:
                await self.app_state.db.close()
            
            self.shutdown_event.set()
            self.logger.info("Shutdown completed successfully")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {traceback.format_exc()}")
        finally:
            sys.exit(1)

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
                self.app_state.system_monitor.start_monitoring(),
                self.api_server.start()
            )
        except InitializationError as e:
            self.logger.error(f"Initialization error: {traceback.format_exc()}")
            await self.shutdown()
        except Exception as e:
            self.logger.error(f"Unexpected error: {traceback.format_exc()}")
            await self.shutdown()

def main():
    """Application entry point"""
    config_path = Path("src/config/default.yml")    
    app = IoTGatewayApp(str(config_path))
    asyncio.run(app.run())

if __name__ == "__main__":
    main()