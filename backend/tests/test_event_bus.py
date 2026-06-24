"""Event bus unit tests (fakeredis — no live Redis required)."""
from __future__ import annotations

import asyncio

import pytest
from fakeredis.aioredis import FakeRedis

from app.core.events import EVENT_TYPES
from app.services.event_bus import EventBus, channel_for_run


@pytest.fixture
def bus():
    return EventBus(FakeRedis(decode_responses=True))


async def _collect(bus: EventBus, run_id: str, limit: int = 100) -> list[dict]:
    out: list[dict] = []
    async for ev in bus.subscribe(run_id):
        out.append(ev)
        if len(out) >= limit:
            break
    return out


@pytest.mark.asyncio
async def test_publish_assigns_monotonic_seq(bus: EventBus):
    run_id = "run-seq"
    task = asyncio.create_task(_collect(bus, run_id))
    await asyncio.sleep(0.05)

    published = []
    for i in range(5):
        published.append(
            await bus.publish(run_id, {"type": "token", "payload": {"n": i}})
        )
    published.append(await bus.publish(run_id, {"type": "done", "payload": {}}))

    received = await asyncio.wait_for(task, timeout=5)
    assert [e["seq"] for e in received] == [1, 2, 3, 4, 5, 6]
    assert [e["seq"] for e in published] == [1, 2, 3, 4, 5, 6]
    assert all(e["run_id"] == run_id for e in received)
    assert all("ts" in e and e["ts"].endswith("Z") for e in received)
    assert all(e.get("event_version") == "1.0" for e in received)


@pytest.mark.asyncio
async def test_runs_are_isolated(bus: EventBus):
    async def drain(run_id: str) -> list[dict]:
        return await _collect(bus, run_id)

    t_a = asyncio.create_task(drain("run-a"))
    t_b = asyncio.create_task(drain("run-b"))
    await asyncio.sleep(0.05)

    await bus.publish("run-a", {"type": "agent_status", "payload": {"agent": "research"}})
    await bus.publish("run-b", {"type": "agent_status", "payload": {"agent": "risk"}})
    await bus.publish("run-a", {"type": "done", "payload": {}})
    await bus.publish("run-b", {"type": "done", "payload": {}})

    a, b = await asyncio.gather(t_a, t_b)
    assert len(a) == 2 and a[0]["payload"]["agent"] == "research"
    assert len(b) == 2 and b[0]["payload"]["agent"] == "risk"
    assert a[0]["seq"] == 1 and b[0]["seq"] == 1


@pytest.mark.asyncio
async def test_subscriber_reconnect_gets_new_events_with_continued_seq(bus: EventBus):
    run_id = "run-reconnect"

    first = asyncio.create_task(_collect(bus, run_id, limit=2))
    await asyncio.sleep(0.05)
    await bus.publish(run_id, {"type": "token", "payload": {"delta": "a"}})
    await bus.publish(run_id, {"type": "token", "payload": {"delta": "b"}})
    batch1 = await asyncio.wait_for(first, timeout=5)

    second = asyncio.create_task(_collect(bus, run_id, limit=2))
    await asyncio.sleep(0.05)
    await bus.publish(run_id, {"type": "token", "payload": {"delta": "c"}})
    await bus.publish(run_id, {"type": "done", "payload": {}})
    batch2 = await asyncio.wait_for(second, timeout=5)

    assert [e["seq"] for e in batch1] == [1, 2]
    assert [e["seq"] for e in batch2] == [3, 4]
    assert batch2[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_all_event_types_publishable(bus: EventBus):
    run_id = "run-types"
    task = asyncio.create_task(_collect(bus, run_id, limit=len(EVENT_TYPES)))
    await asyncio.sleep(0.05)
    for et in EVENT_TYPES:
        await bus.publish(run_id, {"type": et, "payload": {}})
    received = await asyncio.wait_for(task, timeout=5)
    assert [e["type"] for e in received] == list(EVENT_TYPES)


@pytest.mark.asyncio
async def test_channel_format():
    assert channel_for_run("abc-123") == "run:abc-123"
