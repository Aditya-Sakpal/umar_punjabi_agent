"""Live Redis verification for Task 10 event bus.

Run:  uv run python scripts/verify_task10.py
Requires Redis at REDIS_URL (docker compose up redis).
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import redis.asyncio as aioredis

from app.config import settings
from app.services.event_bus import EventBus


def _section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


async def _collect(bus: EventBus, run_id: str, limit: int = 50) -> list[dict]:
    out: list[dict] = []
    async for ev in bus.subscribe(run_id):
        out.append(ev)
        if len(out) >= limit:
            break
    return out


async def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
    except Exception as e:
        print(f"ERROR: Redis not reachable at {settings.redis_url}: {e}")
        return 1

    bus = EventBus(redis)
    failures: list[str] = []

    _section("ORDERING PROOF")
    run_order = f"verify-order-{uuid.uuid4().hex[:8]}"
    task = asyncio.create_task(_collect(bus, run_order))
    await asyncio.sleep(0.1)
    for i in range(1, 11):
        await bus.publish(run_order, {"type": "token", "payload": {"i": i}})
    await bus.publish(run_order, {"type": "done", "payload": {}})
    ordered = await asyncio.wait_for(task, timeout=10)
    seqs = [e["seq"] for e in ordered]
    print("seqs:", seqs)
    if seqs != list(range(1, 12)):
        failures.append(f"ordering expected 1..11 got {seqs}")

    _section("CONCURRENT RUN ISOLATION")
    run_a = f"verify-a-{uuid.uuid4().hex[:8]}"
    run_b = f"verify-b-{uuid.uuid4().hex[:8]}"
    ta = asyncio.create_task(_collect(bus, run_a))
    tb = asyncio.create_task(_collect(bus, run_b))
    await asyncio.sleep(0.1)
    await bus.publish(run_a, {"type": "agent_status", "payload": {"agent": "research"}})
    await bus.publish(run_b, {"type": "agent_status", "payload": {"agent": "risk"}})
    await bus.publish(run_a, {"type": "done", "payload": {}})
    await bus.publish(run_b, {"type": "done", "payload": {}})
    a, b = await asyncio.gather(ta, tb)
    print("run_a:", json.dumps(a, indent=2))
    print("run_b:", json.dumps(b, indent=2))
    if a[0]["payload"].get("agent") != "research" or b[0]["payload"].get("agent") != "risk":
        failures.append("isolation cross-talk")
    if a[0]["run_id"] != run_a or b[0]["run_id"] != run_b:
        failures.append("run_id mismatch on wire")

    _section("SUBSCRIBER RECONNECT (seq continues)")
    run_rc = f"verify-rc-{uuid.uuid4().hex[:8]}"
    first = asyncio.create_task(_collect(bus, run_rc, limit=2))
    await asyncio.sleep(0.1)
    await bus.publish(run_rc, {"type": "evidence", "payload": {"claim": "one"}})
    await bus.publish(run_rc, {"type": "evidence", "payload": {"claim": "two"}})
    batch1 = await asyncio.wait_for(first, timeout=10)
    second = asyncio.create_task(_collect(bus, run_rc, limit=2))
    await asyncio.sleep(0.1)
    await bus.publish(run_rc, {"type": "signal_ready", "payload": {"direction": "BUY"}})
    await bus.publish(run_rc, {"type": "done", "payload": {}})
    batch2 = await asyncio.wait_for(second, timeout=10)
    print("batch1 seqs:", [e["seq"] for e in batch1])
    print("batch2 seqs:", [e["seq"] for e in batch2])
    if [e["seq"] for e in batch1] != [1, 2] or [e["seq"] for e in batch2] != [3, 4]:
        failures.append("reconnect seq continuity")

    await redis.aclose()

    _section("SUMMARY")
    if failures:
        print("FAILED:", failures)
        return 1
    print("ALL TASK 10 ACCEPTANCE CRITERIA PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
