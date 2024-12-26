import pytest
from unittest.mock import AsyncMock, patch
from iot_gateway.core.device_manager import DeviceManager, DeviceCommand
import asyncio

@pytest.mark.asyncio
async def test_bulb_control():
    # Mock GPIO adapter
    gpio_mock = AsyncMock()
    
    # Mock event manager
    event_manager = AsyncMock()
    
    # Create device manager with mocks
    device_manager = DeviceManager(event_manager, gpio_mock)
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