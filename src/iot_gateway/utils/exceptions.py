# src/iot_gateway/utils/exceptions.py

class IoTGatewayError(Exception):
    """Base exception class for IoT Gateway"""
    pass

class ConfigurationError(IoTGatewayError):
    """Raised when there are issues with configuration"""
    pass

class InitializationError(IoTGatewayError):
    """Raised when component initialization fails"""
    pass

class CommunicationError(IoTGatewayError):
    """Raised when communication with external services fails"""
    pass

class DeviceError(IoTGatewayError):
    """Raised when there are issues with device operations"""
    pass

class SensorError(IoTGatewayError):
    """Raised when there are issues with sensor operations"""
    pass

class DatabaseError(Exception):
    """Base exception for database errors"""
    pass

class ConnectionPoolError(DatabaseError):
    """Exception for connection pool related errors"""
    pass