import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from iot_gateway.core.temperature_monitor import TemperatureMonitor
from iot_gateway.core.communication_service import CommunicationService
from iot_gateway.core.event_manager import EventManager
from iot_gateway.sensors.temperature import TemperatureReading
import pytest_asyncio

@pytest.fixture
def mock_config():
    return {
        "temperature_monitor" : {
            "database": {"path": ":memory:"},
            "i2c_bus": 1,
            "sensors": [
                {"id": "sensor1", "bus": 1, "address": 0x48},
                {"id": "sensor2", "bus": 1, "address": 0x49}
            ],
            "reading_interval": 60,
                "sync_interval": 300
            },
        "communication": {"mqtt": {
            "host": "localhost",
            "port": 1883
        }},
       
    }

@pytest_asyncio.fixture
async def monitor(mock_config):
    event_manager = EventManager()
    communication_service = CommunicationService(mock_config)   
    monitor = TemperatureMonitor(mock_config, event_manager, communication_service)
    monitor.storage.initialize = AsyncMock()
    monitor.mqtt = AsyncMock()
    yield monitor
    await monitor.stop()

@pytest.mark.asyncio
async def test_temperature_reading_validation():
    # Test valid temperature
    valid_reading = TemperatureReading(
        sensor_id="test",
        celsius=25.0,
        fahrenheit=77.0
    )
    assert valid_reading.celsius == 25.0

    # Test invalid temperature
    with pytest.raises(ValueError):
        TemperatureReading(
            sensor_id="test",
            celsius=150.0,  # Too high
            fahrenheit=302.0
        )

@pytest.mark.skip
@pytest.mark.asyncio
async def test_monitor_initialization(monitor, mock_config):
    await monitor.initialize()
    
    # Check if storage was initialized
    monitor.storage.initialize.assert_called_once()
    
    # Check if MQTT was connected
    monitor.mqtt.connect.assert_called_once()
    
    # Check if correct number of sensors were created
    assert len(monitor.sensors) == len(mock_config["sensors"])
