from datetime import datetime
import random

def generate_msg_id(id: str) -> str:
    """
    Generate a lightweight unique ID for sensor readings.
    Format: {id}_{timestamp}_{random3}
    Example: temp1_20240107123456789_123
    
    Args:
        id: The unique identifier of the sensor
        
    Returns:
        A string containing a unique reading identifier
    """
    # Get current timestamp in microseconds
    ts = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    # Add 3 random digits for extra uniqueness
    # This handles case of multiple readings in same microsecond
    rand = str(random.randint(0, 999)).zfill(3)
    
    return f"{id}_{ts}_{rand}"