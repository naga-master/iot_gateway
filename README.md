# README.md for IoT Gateway Project

## Overview

The IoT Gateway project is designed to facilitate communication between IoT devices and cloud services. It acts as a middleware, ensuring efficient data transfer and management. This project is built to be straightforward and efficient, allowing users to run the gateway in multiple ways.

## Installation

You can run the IoT Gateway using one of the following methods:

### Method 1: Using Python Module

To run the gateway as a Python module, use the following command:

```bash
python -m iot_gateway
```

### Method 2: If Installed as a Package

If you have installed the IoT Gateway as a package, you can run it directly with:

```bash
iot_gateway
```

### Method 3: Using the Script Directly

Alternatively, you can execute the main script directly:

```bash
python src/iot_gateway/__main__.py
```

## Running Tests

To ensure the functionality of the IoT Gateway, you can run tests using `pytest`.

### Run All Tests

To execute all tests in the project, use:

```bash
pytest
```

### Run Specific Tests

To run a specific test file, you can specify the path as follows:

```bash
pytest src/tests/test_core/test_temperature_monitor.py -v
```

## Managing Open Ports on macOS

If you need to manage open ports, you can use the following commands:

### View Open Ports

To view open ports, execute:

```bash
sudo lsof -i -n -P | grep 8000
```

### Kill Open Ports

To terminate a process using a specific port, use:

```bash
sudo kill -9 [PID]
```

### MQTT Temperature sensor topics and message formats
#### Syncing temperature sensor
```bash
Type: Publish
Topic : temperature/sync
Payload : {"device_ids":["sensor1", "sensor2"],"topic": "sensor1/temperature"}
```
#### Acknowledge temperature sensor 
```bash
Type: Publish
Topic : temperature/ack
Payload : {"device_id":"sensor1","reading_id":"sensor1_20250109155827859843_574"}
```
#### Receiving temperature data
 ```bash
Type: subscribe
Topic : temperature/sensor1
Payload : {"device_id":"sensor1","reading_id":"sensor1_20250112114049406364_751","timestamp":"2025-01-12T11:40:46.950790","is_synced":false,"celsius":72.39,"fahrenheit":162.31}
```

## Conclusion

This README provides a comprehensive guide to setting up and running the IoT Gateway project. For further details, please refer to the project's documentation or source code.