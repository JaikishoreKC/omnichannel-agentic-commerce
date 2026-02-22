from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import time


@dataclass
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[str, dict[str, int]] = {}

    def check(self, *, key: str, limit: int, window_seconds: int = 60) -> RateLimitDecision:
        now = int(time())
        window_start = now - (now % window_seconds)
        reset_epoch = window_start + window_seconds
        bucket_key = f"{key}:{window_start}"

        with self._lock:
            bucket = self._buckets.get(bucket_key)
            if bucket is None:
                bucket = {"count": 0}
                self._buckets[bucket_key] = bucket

            # Opportunistic cleanup for old windows.
            stale_before = window_start - (window_seconds * 3)
            stale_keys = []
            for candidate in self._buckets:
                _, _, suffix = candidate.rpartition(":")
                try:
                    candidate_window = int(suffix)
                except ValueError:
                    continue
                if candidate_window < stale_before:
                    stale_keys.append(candidate)
            for candidate in stale_keys:
                self._buckets.pop(candidate, None)

            current = int(bucket["count"])
            if current >= limit:
                return RateLimitDecision(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_epoch=reset_epoch,
                )

            bucket["count"] = current + 1
            remaining = max(0, limit - bucket["count"])
            return RateLimitDecision(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_epoch=reset_epoch,
            )
