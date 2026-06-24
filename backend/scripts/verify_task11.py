"""Demonstrate translator + event bus wiring (fixtures + optional live graph tokens)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fakeredis.aioredis import FakeRedis

from app.config import settings
from app.services.event_bus import EventBus
from app.services.translator import translate
from tests.test_translator import RUN_ID
from types import SimpleNamespace


def _chunk(text: str):
    return SimpleNamespace(content=text)


def _run_fixture_sequence() -> list[str]:
    fixtures = [
        {"event": "on_chain_start", "name": "research", "data": {}},
        {
            "event": "on_chat_model_stream",
            "tags": ["agent:research"],
            "data": {"chunk": _chunk("Scanning...")},
        },
        {"event": "on_chain_end", "name": "signal", "data": {"output": {"signal": {"direction": "BUY", "confidence": 0.6, "thesis": "x", "horizon": "swing"}}}},
        {"event": "on_chain_end", "name": "execute", "data": {"output": {"sim_order": {"symbol": "BTCUSDT", "side": "BUY", "qty": 0.01, "price": 62000.0}}}},
    ]
    return [translate(ev, RUN_ID)["type"] for ev in fixtures if translate(ev, RUN_ID)]


def _section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


async def _live_token_example() -> None:
    from app.agents.llm import iter_token_events
    from app.agents.prompts.signal import SIGNAL_SYSTEM, SIGNAL_USER

    user = SIGNAL_USER.format(
        research_brief="BTC +2% on volume.",
        evidence='[{"source":"binance","claim":"funding","value":"0.04%","ts":"t"}]',
    )
    count = 0
    async for lg_ev in iter_token_events(
        system=SIGNAL_SYSTEM, user=user, agent="signal", tier="strong", max_tokens=64
    ):
        draft = translate(lg_ev, "live-translate-demo")
        if draft and draft["type"] == "token":
            count += 1
            if count <= 2:
                print(json.dumps(draft, indent=2))
    print(f"Live token drafts translated: {count}")


async def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    _section("FIXTURE SEQUENCE")
    types = _run_fixture_sequence()
    print("translated types:", types)
    assert "agent_status" in types and "token" in types and "signal_ready" in types and "order_filled" in types

    _section("TRANSLATOR + EVENT BUS (draft → publish adds seq + ts)")
    bus = EventBus(FakeRedis(decode_responses=True))
    draft = {
        "run_id": "demo",
        "type": "token",
        "payload": {"agent": "risk", "delta": "Funding elevated..."},
    }
    wire = await bus.publish("demo", draft)
    print(json.dumps(wire, indent=2))
    assert wire["seq"] == 1 and "ts" in wire

    if settings.anthropic_api_key:
        _section("LIVE LANGGRAPH TOKEN → TRANSLATOR")
        await _live_token_example()
    else:
        print("Skipping live token example (no ANTHROPIC_API_KEY)")

    print("\nALL TASK 11 CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
