"""Per-run Redis pub/sub event bus with monotonic sequence numbers."""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from app.core.events import EVENT_VERSION, WSEvent


def channel_for_run(run_id: str) -> str:
    return f"run:{run_id}"


def seq_key_for_run(run_id: str) -> str:
    return f"run:{run_id}:seq"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


class EventBus:
    """Async pub/sub bus keyed by ``run:{run_id}`` with Redis INCR sequencing."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def publish(self, run_id: str, event: dict) -> WSEvent:
        """Assign the next ``seq`` and ``ts`` for ``run_id`` and publish to the run channel."""
        seq = int(await self._redis.incr(seq_key_for_run(run_id)))
        wire: WSEvent = {
            "event_version": EVENT_VERSION,
            "run_id": run_id,
            "seq": seq,
            "type": event["type"],
            "payload": event.get("payload", {}),
            "ts": utc_now_iso(),
        }
        await self._redis.publish(channel_for_run(run_id), json.dumps(wire))
        return wire

    async def subscribe(self, run_id: str) -> AsyncIterator[WSEvent]:
        """Yield ordered events for a single run until ``done`` or unsubscribe."""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel_for_run(run_id))
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=5.0,
                )
                if message is None:
                    continue
                if message.get("type") != "message":
                    continue
                raw = message["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode()
                ev: WSEvent = json.loads(raw)
                yield ev
                if ev["type"] == "done":
                    break
        finally:
            await pubsub.unsubscribe(channel_for_run(run_id))
            await pubsub.aclose()
