"""Translator unit tests — fixture LangGraph events, no live graph."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.translator import translate

RUN_ID = "test-run-001"


def _chunk(text: str):
    return SimpleNamespace(content=text)


class TestAgentStatus:
    def test_research_thinking(self):
        ev = {"event": "on_chain_start", "name": "research", "data": {}}
        out = translate(ev, RUN_ID)
        assert out == {
            "run_id": RUN_ID,
            "type": "agent_status",
            "payload": {"agent": "research", "state": "thinking"},
        }

    def test_risk_challenging(self):
        ev = {"event": "on_chain_start", "name": "risk", "data": {}}
        out = translate(ev, RUN_ID)
        assert out["payload"]["state"] == "challenging"

    def test_committee_deciding(self):
        ev = {"event": "on_chain_start", "name": "committee", "data": {}}
        out = translate(ev, RUN_ID)
        assert out["payload"]["state"] == "deciding"


class TestTokenStreaming:
    def test_preserves_agent_tag_and_delta(self):
        ev = {
            "event": "on_chat_model_stream",
            "tags": ["agent:risk"],
            "data": {"chunk": _chunk("Funding appears elevated...")},
        }
        out = translate(ev, RUN_ID)
        assert out == {
            "run_id": RUN_ID,
            "type": "token",
            "payload": {"agent": "risk", "delta": "Funding appears elevated..."},
        }

    def test_missing_agent_tag_returns_none(self):
        ev = {
            "event": "on_chat_model_stream",
            "tags": ["deepchain"],
            "data": {"chunk": _chunk("orphan")},
        }
        assert translate(ev, RUN_ID) is None

    def test_empty_delta_returns_none(self):
        ev = {
            "event": "on_chat_model_stream",
            "tags": ["agent:signal"],
            "data": {"chunk": _chunk("")},
        }
        assert translate(ev, RUN_ID) is None


class TestToolEnd:
    def test_evidence_from_structured_output(self):
        ev = {
            "event": "on_tool_end",
            "name": "binance_funding",
            "data": {
                "output": {
                    "source": "binance",
                    "claim": "funding rate",
                    "value": "0.085%",
                }
            },
        }
        out = translate(ev, RUN_ID)
        assert out["type"] == "evidence"
        assert out["payload"]["source"] == "binance"

    def test_evidence_from_funding_tool_shape(self):
        ev = {
            "event": "on_tool_end",
            "name": "funding",
            "data": {"output": {"symbol": "BTCUSDT", "funding_rate": 0.00085}},
        }
        out = translate(ev, RUN_ID)
        assert out["payload"]["value"] == "0.0850%"


class TestNodeOutputs:
    def test_signal_ready(self):
        signal = {"direction": "BUY", "confidence": 0.6, "thesis": "x", "horizon": "swing"}
        ev = {
            "event": "on_chain_end",
            "name": "signal",
            "data": {"output": {"signal": signal, "status": "signal_done"}},
        }
        out = translate(ev, RUN_ID)
        assert out["type"] == "signal_ready"
        assert out["payload"] == signal

    def test_risk_ready(self):
        risk = {
            "concerns": ["crowded"],
            "adjusted_confidence": 0.4,
            "suggested_size_pct": 2.0,
            "stop_loss_pct": 3.0,
            "veto": False,
        }
        ev = {"event": "on_chain_end", "name": "risk", "data": {"output": {"risk": risk}}}
        assert translate(ev, RUN_ID)["type"] == "risk_ready"

    def test_decision_ready(self):
        decision = {
            "action": "HOLD",
            "confidence": 0.3,
            "size_pct": 0.0,
            "stop_loss_pct": 0.0,
            "rationale": "flat",
        }
        ev = {
            "event": "on_chain_end",
            "name": "committee",
            "data": {"output": {"decision": decision}},
        }
        assert translate(ev, RUN_ID)["type"] == "decision_ready"

    def test_order_filled(self):
        sim = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.01,
            "price": 62000.0,
            "filled": True,
        }
        ev = {
            "event": "on_chain_end",
            "name": "execute",
            "data": {"output": {"sim_order": sim}},
        }
        out = translate(ev, RUN_ID)
        assert out["type"] == "order_filled"
        assert out["payload"]["qty"] == 0.01


class TestErrors:
    def test_chain_error(self):
        ev = {
            "event": "on_chain_error",
            "name": "risk",
            "data": {"error": "funding API down"},
        }
        out = translate(ev, RUN_ID)
        assert out["type"] == "error"
        assert out["payload"]["agent"] == "risk"


class TestUnknown:
    def test_unknown_event_returns_none(self):
        assert translate({"event": "on_prompt_start"}, RUN_ID) is None

    def test_internal_chain_start_ignored(self):
        assert translate({"event": "on_chain_start", "name": "ChatAnthropic"}, RUN_ID) is None


def test_full_sample_translation_sequence():
    """End-to-end fixture sequence mirroring a deep-chain run."""
    fixtures = [
        {"event": "on_chain_start", "name": "research", "data": {}},
        {
            "event": "on_chat_model_stream",
            "tags": ["agent:research"],
            "data": {"chunk": _chunk("Scanning funding...")},
        },
        {
            "event": "on_tool_end",
            "data": {"output": {"source": "binance", "claim": "funding rate", "value": "0.05%"}},
        },
        {
            "event": "on_chain_end",
            "name": "research",
            "data": {"output": {"research_brief": "...", "status": "research_done"}},
        },
        {"event": "on_chain_start", "name": "signal", "data": {}},
        {
            "event": "on_chat_model_stream",
            "tags": ["agent:signal"],
            "data": {"chunk": _chunk("Bull case: volume.")},
        },
        {
            "event": "on_chain_end",
            "name": "signal",
            "data": {
                "output": {
                    "signal": {
                        "direction": "BUY",
                        "confidence": 0.62,
                        "thesis": "breakout",
                        "horizon": "swing",
                    }
                }
            },
        },
        {"event": "on_chain_start", "name": "risk", "data": {}},
        {
            "event": "on_chat_model_stream",
            "tags": ["agent:risk"],
            "data": {"chunk": _chunk("Funding elevated at 0.085%.")},
        },
        {
            "event": "on_chain_end",
            "name": "risk",
            "data": {
                "output": {
                    "risk": {
                        "concerns": ["crowded long"],
                        "adjusted_confidence": 0.4,
                        "suggested_size_pct": 2.0,
                        "stop_loss_pct": 3.0,
                        "veto": False,
                    }
                }
            },
        },
        {"event": "on_chain_start", "name": "committee", "data": {}},
        {
            "event": "on_chain_end",
            "name": "committee",
            "data": {
                "output": {
                    "decision": {
                        "action": "BUY",
                        "confidence": 0.5,
                        "size_pct": 2.0,
                        "stop_loss_pct": 3.0,
                        "rationale": "Sized down.",
                    }
                }
            },
        },
        {
            "event": "on_chain_end",
            "name": "execute",
            "data": {
                "output": {
                    "sim_order": {
                        "symbol": "BTCUSDT",
                        "side": "BUY",
                        "qty": 0.032,
                        "price": 62400.0,
                    }
                }
            },
        },
    ]

    translated = [translate(ev, RUN_ID) for ev in fixtures]
    types = [t["type"] for t in translated if t]
    assert types == [
        "agent_status",
        "token",
        "evidence",
        "agent_status",
        "token",
        "signal_ready",
        "agent_status",
        "token",
        "risk_ready",
        "agent_status",
        "decision_ready",
        "order_filled",
    ]
    risk_tokens = [t for t in translated if t and t["type"] == "token" and t["payload"].get("agent") == "risk"]
    assert len(risk_tokens) == 1
