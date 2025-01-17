import pytest
from unittest.mock import AsyncMock, patch
from iot_gateway.core.device_manager import DeviceManager, DeviceCommand
import asyncio


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
        "devices": {
            "bulb1": {
                "enabled": True,
                "type": "bulb",
                "pin": 5,
                "initial": False
            }
        }
       
    }

@pytest.mark.asyncio
async def test_bulb_control():
    # Mock GPIO adapter
    gpio_mock = AsyncMock()
    
    # Mock event manager
    event_manager = AsyncMock()

    # Mock config
    config = AsyncMock()
    
    # Create device manager with mocks
    device_manager = DeviceManager(event_manager, gpio_mock, config)
    await device_manager.initialize()
    
    # Test command execution
    command = DeviceCommand(
        device_id="bulb1",
        command="TURN_ON"
    )
    
    command_id = await device_manager._handle_command_event(command.model_dump())

    # Allow some time for the command to be processed
    await asyncio.sleep(1)
    
    # Verify GPIO was called
    gpio_mock.write_data.assert_called_once_with({
        'device_id': 'bulb1',
        'state': True
    })
    
    # Verify status was updated
    status = await device_manager.get_command_status(command_id)
    assert status.status == "SUCCESS"