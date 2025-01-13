# IoT Gateway Project

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
### API Documentation
- **Control Devices**: POST /api/v1/devices/{device_id}/control
- **Get Command Status**: GET /api/v1/devices/{device_id}/commands/{command_id}
- **Get Temperature Readings**: GET /api/v1/temperature/{sensor_id}

Contributing
See CONTRIBUTING.md for guidelines.

License
This project is licensed under the MIT License. See LICENSE for details.


---

## **Code of Conduct**

```markdown
# Code of Conduct

## Our Pledge
We pledge to foster an open and welcoming environment for all contributors.

## Our Standards
- Be respectful and inclusive.
- Use welcoming and inclusive language.
- Accept constructive criticism gracefully.
- Focus on what is best for the community.

## Enforcement
Instances of abusive, harassing, or otherwise unacceptable behavior may be reported to the project maintainers.

## Attribution
This Code of Conduct is adapted from the [Contributor Covenant](https://www.contributor-covenant.org/).
```

Contributing
markdown
# Contributing

We welcome contributions! Here’s how you can help:

1. Fork the repository.
2. Create a new branch:
   ```bash
   git checkout -b feature/your-feature
3. Make your changes and commit them:

    ```bash
    git commit -m "Add your feature"
    ```
4. Push your changes:
    ```bash
    git push origin feature/your-feature
    ```

5. Open a pull request.

## Guidelines
- Follow the existing code style.
- Write clear commit messages.
- Add tests for new features.
- Update documentation as needed.


---

## **License**

```markdown
# MIT License

Copyright (c) 2024 NAGARAJ S

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Conclusion

This README provides a comprehensive guide to setting up and running the IoT Gateway project. For further details, please refer to the project's documentation or source code.