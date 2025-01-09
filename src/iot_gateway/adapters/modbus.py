# modbus_adapter.py
import minimalmodbus
import serial
import asyncio
from typing import List
from .base import CommunicationAdapter
from ..utils.logging import get_logger

logger = get_logger(__name__)

class ModbusRTUAdapter(CommunicationAdapter):
    """
    Generic Modbus RTU communication adapter.
    Handles low-level Modbus RTU operations independently of specific sensors.
    """
    def __init__(self, port: str, slave_address: int, baudrate: int = 9600):
        self.port = port
        self.slave_address = slave_address
        self.baudrate = baudrate
        self.instrument = None
        self.is_connected = False
        self._retry_count = 3
        self._retry_delay = 0.5

    async def connect(self) -> None:
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.instrument = minimalmodbus.Instrument(self.port, self.slave_address)
                # self.instrument.serial.baudrate = self.baudrate
                # self.instrument.serial.timeout = 1.0
                self.is_connected = True
                logger.info(f"Connected to Modbus RTU device at {self.port}")
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to connect to Modbus RTU device failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def disconnect(self) -> None:
        if self.instrument:
            try:
                self.instrument.serial.close()
                self.is_connected = False
                logger.info(f"Disconnected from Modbus RTU device at {self.port}")
            except Exception as e:
                logger.error(f"Error disconnecting from Modbus RTU device: {e}")
                raise

    async def read_register(self, address: int, number_of_decimals: int = 0, 
                          functioncode: int = 3, signed: bool = False) -> float:
        if not self.is_connected:
            raise RuntimeError("Modbus RTU device not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # value = self.instrument.read_register(
                #     address, number_of_decimals, functioncode, signed)
                # return value
                return 0.0
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to read Modbus register failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise

    async def write_register(self, address: int, value: float, 
                           number_of_decimals: int = 0, 
                           functioncode: int = 16, signed: bool = False) -> None:
        if not self.is_connected:
            raise RuntimeError("Modbus RTU device not connected")
            
        for attempt in range(self._retry_count):
            try:
                ### SHOULD BE UNCOMMENTED WHEN RUNNING WITH RASPBERRY PI ###
                # self.instrument.write_register(
                #     address, value, number_of_decimals, functioncode, signed)
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self._retry_count} to write Modbus register failed: {e}")
                if attempt < self._retry_count - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise