from typing import Dict, Any
### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
# import RPi.GPIO as GPIO
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class GPIOAdapter(CommunicationAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pins: Dict[str, int] = {}
        self.initialized = False

    async def connect(self) -> None:
        try:
            # GPIO.setmode(GPIO.BCM)
            # Initialize pins from config
            for _, pin_config in self.config.items():
                pin = pin_config['pin']
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # GPIO.setup(pin, GPIO.OUT)
                self.pins[pin_config['type']] = pin
            self.initialized = True
            logger.info("GPIO adapter initialized")
        except Exception as e:
            logger.error(f"GPIO initialization failed: {e}")
            raise

    async def disconnect(self) -> None:
        if self.initialized:
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # GPIO.cleanup()
            self.initialized = False
            logger.info("GPIO adapter cleaned up")

    async def read_data(self) -> Dict[str, Any]:
        if not self.initialized:
            raise RuntimeError("GPIO not initialized")
        
        states = {}
        for device_id, pin in self.pins.items():
            ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
            # states[device_id] = GPIO.input(pin)
            states[device_id] = pin
        return states

    async def write_data(self, data: Dict[str, Any]) -> None:
        if not self.initialized:
            raise RuntimeError("GPIO not initialized")
        
        device_id = data.get('device_id')
        state = data.get('state')
        
        if device_id not in self.pins:
            raise ValueError(f"Unknown device ID: {device_id}")
        
        pin = self.pins[device_id]
        ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
        # GPIO.output(pin, state)
        logger.info(f"Set {device_id} (PIN {pin}) to {state}")