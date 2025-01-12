# src/iot_gateway/api/routes.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta
from ..models.things import TemperatureReading
from .dependencies import DBDependency

temp_router = APIRouter()

@temp_router.get(
    "/temperature/{sensor_id}",
    response_model=List[TemperatureReading]
)
async def get_temperature_readings(
    sensor_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: DBDependency = None
) -> List[TemperatureReading]:
    try:
        readings = await db.repositories['temperature'].get_readings(
            sensor_id,
            start_time or datetime.now() - timedelta(hours=24),
            end_time or datetime.now()
        )
        return readings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))