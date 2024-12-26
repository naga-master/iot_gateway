from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta
from ..storage.database import TemperatureStorage
from ..sensors.temperature import TemperatureReading

temp_router = APIRouter()

@temp_router.get("/temperature/{sensor_id}")
async def get_temperature_readings(
    sensor_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[TemperatureReading]:
    try:
        storage = TemperatureStorage("temperature.db")  # Should use DI in real app
        readings = await storage.get_readings(
            sensor_id,
            start_time or datetime.now() - timedelta(hours=24),
            end_time or datetime.now()
        )
        return readings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
