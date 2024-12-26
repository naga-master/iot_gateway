import logging
import logging.handlers
import os
from pathlib import Path
from typing import Dict, Any, Optional

def setup_logging(config: Dict[str, Any]) -> None:
    """
    Setup application-wide logging configuration.
    
    Args:
        config: Dictionary containing logging configuration
            {
                'level': str,  # DEBUG, INFO, WARNING, ERROR, CRITICAL
                'file': str,   # Log file path
                'max_size': int,  # Max size in MB before rotation
                'backup_count': int,  # Number of backup files to keep
                'format': str  # Log message format
            }
    """
    # Set default values if not provided
    log_level = getattr(logging, config.get('level', 'INFO'))
    log_file = config.get('file', 'iot_gateway.log')
    max_size = config.get('max_size', 10) * 1024 * 1024  # Convert MB to bytes
    backup_count = config.get('backup_count', 5)
    log_format = config.get('format', 
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Setup file handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_size,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)

    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Usually __name__ of the module
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)

# Example usage
if __name__ == "__main__":
    # Example configuration
    log_config = {
        'level': 'DEBUG',
        'file': 'logs/iot_gateway.log',
        'max_size': 5,  # 5MB
        'backup_count': 3,
        'format': '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
    }
    
    setup_logging(log_config)
    logger = get_logger(__name__)
    
    # Test logging
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")