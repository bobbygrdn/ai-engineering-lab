import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict


@dataclass
class RateLimitRule:
    limit: int
    window_seconds: int


class AuthRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._events: Dict[str, Deque[float]] = {}

    def _prune(self, key: str, now: float, window_seconds: int) -> Deque[float]:
        events = self._events.setdefault(key, deque())
        cutoff = now - float(window_seconds)
        while events and events[0] < cutoff:
            events.popleft()
        return events

    def allow(self, key: str, rule: RateLimitRule) -> bool:
        now = time.time()
        with self._lock:
            events = self._prune(key, now, rule.window_seconds)
            if len(events) >= rule.limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
