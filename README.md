 # Project documentation
 # Method 1: Using python -m
python -m iot_gateway

# Method 2: If installed as a package
iot_gateway

# Method 3: Using the script directly
python src/iot_gateway/__main__.py


# Run Tests 
run all tests = `pytest`
run specific tests = pytest src/tests/test_core/test_temperature_monitor.py -v


# view open ports in mac
sudo lsof -i -n -P | grep 8000
 # kill open ports
 sudo kill -9 [PID]
