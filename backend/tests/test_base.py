"""Cache + last-good-snapshot semantics of CachedFetchTool (no HTTP)."""
import pytest

from app.tools.base import CachedFetchTool


async def test_fresh_fetch_returns_data_and_caches():
    tool = CachedFetchTool()
    calls = 0

    async def fetcher():
        nonlocal calls
        calls += 1
        return {"price": 100.0}

    first = await tool.fetch("k", fetcher, ttl=60)
    assert first == {"price": 100.0, "stale": False}
    assert "k" in tool._fresh and "k" in tool._last_good

    # within TTL the cached value is served without calling the fetcher again
    second = await tool.fetch("k", fetcher, ttl=60)
    assert second == {"price": 100.0, "stale": False}
    assert calls == 1


async def test_failure_returns_last_good_snapshot_stale():
    tool = CachedFetchTool()

    async def ok():
        return {"price": 100.0}

    async def boom():
        raise RuntimeError("upstream down")

    # ttl=0 forces the fetcher to run again on the next call (bypasses cache hit)
    fresh = await tool.fetch("k", ok, ttl=0)
    assert fresh["stale"] is False

    fallback = await tool.fetch("k", boom, ttl=0)
    assert fallback == {"price": 100.0, "stale": True}


async def test_failure_without_snapshot_raises():
    tool = CachedFetchTool()

    async def boom():
        raise RuntimeError("upstream down")

    with pytest.raises(RuntimeError, match="upstream down"):
        await tool.fetch("k", boom, ttl=0)
