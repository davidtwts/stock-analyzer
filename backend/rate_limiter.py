# backend/rate_limiter.py
"""Rate limiter for TWSE API requests."""

import threading
import time
from typing import Optional


class RateLimiter:
    """
    Thread-safe rate limiter for TWSE API.

    TWSE enforces 3 requests per 5 seconds.
    """

    def __init__(self, max_requests: int = 3, period: float = 5.0):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in the period
            period: Time period in seconds
        """
        self.max_requests = max_requests
        self.period = period
        self.timestamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Wait until a request can be made.

        Args:
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            True if acquired, False if timeout
        """
        start_time = time.time()

        while True:
            with self._lock:
                now = time.time()

                # Remove timestamps outside the period window
                self.timestamps = [
                    t for t in self.timestamps if now - t < self.period
                ]

                if len(self.timestamps) < self.max_requests:
                    self.timestamps.append(now)
                    return True

                # Calculate wait time
                oldest = self.timestamps[0]
                wait_time = self.period - (now - oldest) + 0.1  # Add small buffer

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False

            time.sleep(min(wait_time, 0.5))  # Sleep in small increments

    def reset(self):
        """Clear all timestamps."""
        with self._lock:
            self.timestamps.clear()

    @property
    def available_requests(self) -> int:
        """Get number of requests available right now."""
        with self._lock:
            now = time.time()
            active = [t for t in self.timestamps if now - t < self.period]
            return self.max_requests - len(active)
