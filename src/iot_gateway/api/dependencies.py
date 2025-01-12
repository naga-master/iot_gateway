# src/iot_gateway/api/dependencies.py
from fastapi import Request
from typing import Annotated
from fastapi import Depends
from ..storage.sensor_database import SensorDatabase
from ..core.temperature_monitor import TemperatureMonitor
from ..core.device_manager import DeviceManager
from ..core.heartbeat import SystemMonitor

async def get_db(request: Request) -> SensorDatabase:
    return request.app.state.components.db

async def get_temperature_monitor(request: Request) -> TemperatureMonitor:
    return request.app.state.components.temperature_monitor

async def get_device_manager(request: Request) -> DeviceManager:
    return request.app.state.components.device_manager

async def get_system_monitor(request: Request) -> SystemMonitor:
    return request.app.state.components.system_monitor

# Type definitions for dependencies
DBDependency = Annotated[SensorDatabase, Depends(get_db)]
TempMonitorDependency = Annotated[TemperatureMonitor, Depends(get_temperature_monitor)]
DeviceManagerDependency = Annotated[DeviceManager, Depends(get_device_manager)]
SystemMonitorDependency = Annotated[SystemMonitor, Depends(get_system_monitor)]