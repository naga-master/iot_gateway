# Caching implementation

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import OrderedDict
import threading
from ..utils.logging import get_logger

logger = get_logger(__name__)

class SyncCache:
    def __init__(self, max_size: int = 1000, expiry_time: int = 3600):
        self.max_size = max_size
        self.expiry_time = expiry_time
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.expiry: Dict[str, datetime] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get item from cache with thread safety and expiry check."""
        with self._lock:
            if key in self.cache:
                # Check expiry
                if datetime.now() > self.expiry[key]:
                    self._remove(key)
                    return None
                
                # Move to end for LRU
                value = self.cache.pop(key)
                self.cache[key] = value
                return value
                
            return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Set item in cache with thread safety and LRU eviction."""
        with self._lock:
            # Remove expired entries
            self._cleanup()
            
            # Remove oldest if at capacity
            if len(self.cache) >= self.max_size:
                _, _ = self.cache.popitem(last=False)
            
            # Add new item
            self.cache[key] = value
            self.expiry[key] = datetime.now() + timedelta(seconds=self.expiry_time)

    def _remove(self, key: str) -> None:
        """Remove item from cache and expiry tracking."""
        self.cache.pop(key, None)
        self.expiry.pop(key, None)

    def _cleanup(self) -> None:
        """Remove all expired entries."""
        now = datetime.now()
        expired = [
            key for key, expiry in self.expiry.items()
            if now > expiry
        ]
        for key in expired:
            self._remove(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self.cache.clear()
            self.expiry.clear()

    def get_size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self.cache)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "expiry_time": self.expiry_time,
                "oldest_entry": min(self.expiry.values()) if self.expiry else None,
                "newest_entry": max(self.expiry.values()) if self.expiry else None
            }