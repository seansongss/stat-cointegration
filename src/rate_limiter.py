from __future__ import annotations
import time, random
from collections import deque

class RateLimiter:
    """
    Sliding-window rate limiter.
    Allows at most `max_calls` in the past `window_sec` seconds.
    Adds small jitter to avoid bunching right at boundaries.
    """
    def __init__(self, max_calls: int = 5, window_sec: int = 60, jitter_sec: float = 0.3):
        self.max_calls = max_calls
        self.window_sec = window_sec
        self.jitter_sec = jitter_sec
        self._calls = deque()  # monotonic timestamps

    def acquire(self):
        now = time.monotonic()
        # drop old timestamps
        while self._calls and (now - self._calls[0]) >= self.window_sec:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            # sleep until earliest call falls out of the window + a touch of jitter
            need = self.window_sec - (now - self._calls[0]) + random.uniform(0, self.jitter_sec)
            if need > 0:
                time.sleep(need)
        # record after potential sleep
        self._calls.append(time.monotonic())
