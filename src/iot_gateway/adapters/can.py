import can
import asyncio
from typing import Dict, Any
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class CANAdapter(CommunicationAdapter):
    """
    Generic CAN communication adapter.
    Handles low-level CAN operations independently of specific sensors.
    """
    def __init__(self, channel: str, bitrate: int = 500000):
        self.channel = channel
        self.bitrate = bitrate
        self.bus = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5

    async def connect(self) -> None:
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.bus = can.interface.Bus(
                #     channel=self.channel,
                #     bustype='socketcan',
                #     bitrate=self.bitrate
                # )
                self.is_connected = True
                logger.info(f"Connected to CAN bus {self.channel}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to connect to CAN bus failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def disconnect(self) -> None:
        if self.bus:
            try:
                self.bus.shutdown()
                self.is_connected = False
                logger.info(f"Disconnected from CAN bus {self.channel}")
            except Exception as e:
                logger.error(f"Error disconnecting from CAN bus: {e}")
                raise

    async def send_message(self, arbitration_id: int, data: bytes, extended_id: bool = False) -> None:
        if not self.is_connected:
            raise RuntimeError("CAN bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # msg = can.Message(
                #     arbitration_id=arbitration_id,
                #     data=data,
                #     extended_id=extended_id
                # )
                # self.bus.send(msg)
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to send CAN message failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def receive_message(self, timeout: float = 1.0) -> can.Message:
        if not self.is_connected:
            raise RuntimeError("CAN bus not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # msg = self.bus.recv(timeout=timeout)
                # return msg
                return None
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to receive CAN message failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise