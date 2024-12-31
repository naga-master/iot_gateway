from typing import TypeVar, Callable, Any, Optional
import asyncio
import random
import functools
from datetime import datetime
from ..utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

def async_retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator for async functions to retry with exponential backoff.
    
    Args:
        max_retries (int): Maximum number of retry attempts
        base_delay (float): Initial delay between retries in seconds
        max_delay (float): Maximum delay between retries in seconds
        exponential_base (float): Base for exponential backoff calculation
        jitter (bool): Whether to add random jitter to delay
        exceptions (tuple): Exception types to catch and retry on
    
    Returns:
        Callable: Decorated async function with retry logic
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_count = 0
            total_delay = 0.0
            last_exception: Optional[Exception] = None
            
            while retry_count <= max_retries:
                try:
                    start_time = datetime.now()
                    
                    if retry_count > 0:
                        logger.info(
                            f"Retry attempt {retry_count} for {func.__name__} "
                            f"after {total_delay:.2f}s total delay"
                        )
                    
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    retry_count += 1
                    last_exception = e
                    
                    if retry_count > max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}. "
                            f"Last error: {str(e)}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (retry_count - 1)),
                        max_delay
                    )
                    
                    # Add jitter if enabled (±25% of delay)
                    if jitter:
                        jitter_range = delay * 0.25
                        delay += random.uniform(-jitter_range, jitter_range)
                    
                    # Ensure delay is positive and within bounds
                    delay = max(0.0, min(delay, max_delay))
                    total_delay += delay
                    
                    logger.warning(
                        f"Attempt {retry_count} failed for {func.__name__}. "
                        f"Error: {str(e)}. Retrying in {delay:.2f}s"
                    )
                    
                    # Wait before next retry
                    await asyncio.sleep(delay)
                    
            # This should never be reached due to the raise in the loop
            raise last_exception or Exception("Unexpected retry failure")
        
        return wrapper
    
    return decorator

# Example usage with custom exceptions
class NetworkError(Exception):
    pass

class DatabaseError(Exception):
    pass