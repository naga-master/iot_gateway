# Sensor Onboarding Guide

This guide explains how to add support for a new sensor type in the IoT Gateway system. Follow these steps in order.

## 1. Define Data Model
Location: `models.py`

1. Add new sensor type to DeviceType enum:
```python
class DeviceType(Enum):
    TEMPERATURE = "temperature"
    YOUR_SENSOR = "your_sensor"  # Add your new sensor type here
```

2. Create a new dataclass for your sensor readings:
```python
@dataclass
class YourSensorReading:
    device_id: str
    reading_id: str
    timestamp: datetime
    your_measurement: float  # Add your specific measurements
    another_measurement: str
    is_synced: bool = False
```

## 2. Create Database Repository
Location: `storage/db.py`

1. Create a new repository class for your sensor:
```python
class YourSensorRepository(BaseRepository[YourSensorReading]):
    def __init__(self, pool: ConnectionPool):
        super().__init__(pool)
        self.table_name = "your_sensor_readings"

    async def create_table(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS your_sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    reading_id TEXT NOT NULL,
                    your_measurement REAL NOT NULL,
                    another_measurement TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    is_synced BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id),
                    UNIQUE(device_id, reading_id)
                )
            ''')
```

2. Add your repository to SensorDatabase class:
```python
def _setup_repositories(self):
    self.repositories['temperature'] = TemperatureRepository(self.pool)
    self.repositories['your_sensor'] = YourSensorRepository(self.pool)  # Add your repository
```

## 3. Create Sensor Monitor
Location: `core/your_sensor_monitor.py`

1. Create a new monitor class:
```python
class YourSensorMonitor:
    def __init__(self, db: SensorDatabase):
        self.db = db
        self.sensor_id = "your_sensor_1"  # Define your sensor ID

    async def initialize(self):
        # Register your sensor in the database
        await self.db.register_device(
            device_id=self.sensor_id,
            device_type=DeviceType.YOUR_SENSOR,
            name="Your Sensor Name",
            location="Sensor Location"
        )

    async def monitor(self):
        while True:
            try:
                # Read from your sensor
                measurement = await self.read_sensor()
                
                # Create reading object
                reading = YourSensorReading(
                    device_id=self.sensor_id,
                    reading_id=f"{self.sensor_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    timestamp=datetime.now(),
                    your_measurement=measurement.value,
                    another_measurement=measurement.other_value
                )
                
                # Store reading
                await self.db.repositories['your_sensor'].store_reading(reading)
                
                await asyncio.sleep(10)  # Adjust polling interval
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Error backoff

    async def read_sensor(self):
        # Implement your sensor reading logic here
        pass
```

## 4. Update Gateway Configuration
Location: `gateway.py`

1. Add your monitor to the gateway:
```python
class IoTGateway:
    def __init__(self):
        self.db = SensorDatabase('sensors.db')
        self.temp_monitor = TemperatureMonitor(self.db)
        self.your_monitor = YourSensorMonitor(self.db)  # Add your monitor

    async def start(self):
        await self.db.initialize()
        await self.your_monitor.initialize()  # Initialize your monitor
        
        # Start monitoring tasks
        monitor_tasks = [
            asyncio.create_task(self.temp_monitor.monitor()),
            asyncio.create_task(self.your_monitor.monitor()),  # Add your monitoring task
        ]
        await asyncio.gather(*monitor_tasks)
```

## 5. Create Tests
Location: `tests/test_your_sensor.py`

1. Create tests for your sensor:
```python
async def test_your_sensor_reading():
    db = SensorDatabase(':memory:')
    await db.initialize()
    
    reading = YourSensorReading(
        device_id="test_sensor",
        reading_id="test_reading",
        timestamp=datetime.now(),
        your_measurement=42.0,
        another_measurement="test"
    )
    
    await db.repositories['your_sensor'].store_reading(reading)
    readings = await db.repositories['your_sensor'].get_readings(
        device_id="test_sensor",
        start_time=datetime.now() - timedelta(hours=1),
        end_time=datetime.now()
    )
    
    assert len(readings) == 1
    assert readings[0].your_measurement == 42.0
```

## Checklist for Adding New Sensors

- [ ] Add new DeviceType enum value
- [ ] Create new Reading dataclass
- [ ] Create new Repository class
- [ ] Add repository to SensorDatabase._setup_repositories()
- [ ] Create new Monitor class
- [ ] Add monitor to IoTGateway
- [ ] Add tests for new sensor type
- [ ] Update documentation

## Common Issues

1. Foreign Key Constraint Error:
   - Make sure to register your device using `register_device()` before storing readings

2. Type Errors:
   - Ensure your Reading dataclass fields match the database table columns
   - Check that measurement values are of the correct type

3. Connection Issues:
   - Verify your sensor connection logic in the `read_sensor()` method
   - Implement proper error handling and retry logic

## Best Practices

1. Sensor IDs:
   - Use consistent naming patterns (e.g., "sensor_type_number")
   - Document your sensor ID scheme

2. Reading IDs:
   - Include timestamp and sensor ID for uniqueness
   - Use consistent format across all sensors

3. Error Handling:
   - Implement proper logging
   - Use appropriate error backoff strategies
   - Don't let one sensor failure affect others

4. Testing:
   - Test both success and failure scenarios
   - Include integration tests with actual sensor hardware
   - Test concurrent operations

Need help? Contact the IoT Gateway team at [your contact info]