"""Cached-fetch base for external tools.

Every read tool extends :class:`CachedFetchTool` to get TTL caching plus a
last-good-snapshot fallback for free: a dead upstream degrades to stale data,
never a hang or a crash.

Backend: in-process TTL cache (a dict). Chosen for self-containment and easy
unit testing without infra; the last-good snapshot survives any fetch failure
for the process lifetime. (Live price fan-out via Redis is a separate concern
handled by the WS price-stream in a later task.)
"""
import time
from collections.abc import Awaitable, Callable

Fetcher = Callable[[], Awaitable[dict]]


class CachedFetchTool:
    def __init__(self) -> None:
        # key -> (expires_at_monotonic, clean_data)
        self._fresh: dict[str, tuple[float, dict]] = {}
        # key -> clean_data; updated on every success, never expires (fallback source)
        self._last_good: dict[str, dict] = {}

    async def fetch(self, key: str, fetcher: Fetcher, ttl: float) -> dict:
        """Return fresh data and cache it; on failure return the last-good snapshot
        tagged ``stale=True``; if there is no snapshot, re-raise.

        The returned dict is a shallow copy of the fetcher's payload with a
        ``stale`` flag added (``False`` when fresh/within-TTL, ``True`` on fallback).
        """
        now = time.monotonic()
        hit = self._fresh.get(key)
        if hit is not None and hit[0] > now:
            return {**hit[1], "stale": False}

        try:
            data = await fetcher()
        except Exception:
            snapshot = self._last_good.get(key)
            if snapshot is not None:
                return {**snapshot, "stale": True}
            raise

        self._fresh[key] = (now + ttl, data)
        self._last_good[key] = data
        return {**data, "stale": False}
