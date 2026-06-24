"""LangGraph ``astream_events`` v2 → :class:`WSEvent` translation (blueprint §7.3)."""
from __future__ import annotations

from typing import Any

from app.agents.llm import _content_to_text
from app.core.events import GRAPH_NODES, EventDraft

# Node name → agent_status.state verb (research/signal think; risk challenges; committee decides)
_NODE_STATE: dict[str, str] = {
    "research": "thinking",
    "signal": "thinking",
    "risk": "challenging",
    "committee": "deciding",
}

# Priority when a node returns multiple owned keys in one output
_OUTPUT_READY: tuple[tuple[str, str], ...] = (
    ("sim_order", "order_filled"),
    ("decision", "decision_ready"),
    ("risk", "risk_ready"),
    ("signal", "signal_ready"),
)


def _draft(run_id: str, event_type: str, payload: dict) -> EventDraft:
    return {"run_id": run_id, "type": event_type, "payload": payload}  # type: ignore[typeddict-item]


def _event_tags(ev: dict) -> list[str]:
    tags = list(ev.get("tags") or [])
    meta = ev.get("metadata") or {}
    if isinstance(meta.get("tags"), list):
        tags.extend(meta["tags"])
    return tags


def _agent_from_tags(tags: list[str]) -> str | None:
    for tag in tags:
        if tag.startswith("agent:"):
            return tag.split(":", 1)[1]
    return None


def _node_name(ev: dict) -> str | None:
    name = ev.get("name")
    if isinstance(name, str) and name in GRAPH_NODES:
        return name
    meta = ev.get("metadata") or {}
    lg_node = meta.get("langgraph_node")
    if isinstance(lg_node, str) and lg_node in GRAPH_NODES:
        return lg_node
    return None


def _chain_output(ev: dict) -> dict:
    data = ev.get("data") or {}
    output = data.get("output")
    if isinstance(output, dict):
        return output
    return {}


def _evidence_from_tool_output(output: Any) -> dict | None:
    if isinstance(output, dict):
        if {"source", "claim"} <= set(output.keys()):
            return {
                "source": output["source"],
                "claim": output["claim"],
                "value": output.get("value"),
            }
        if "headlines" in output and isinstance(output["headlines"], list):
            first = output["headlines"][0] if output["headlines"] else {}
            return {
                "source": f"news:{first.get('source', 'rss')}",
                "claim": first.get("title", "headline"),
                "value": first.get("summary"),
            }
        if "funding_rate" in output:
            rate = output["funding_rate"]
            return {
                "source": "binance",
                "claim": "funding rate",
                "value": f"{float(rate) * 100:.4f}%",
            }
        if "price" in output and "symbol" in output:
            return {
                "source": "binance",
                "claim": "spot price",
                "value": output["price"],
            }
    return None


def _order_filled_payload(sim_order: dict) -> dict:
    return {
        "symbol": sim_order.get("symbol"),
        "side": sim_order.get("side") or sim_order.get("action"),
        "qty": sim_order.get("qty"),
        "price": sim_order.get("price"),
        "pnl": sim_order.get("realized_pnl", sim_order.get("pnl", 0)),
    }


def translate(langgraph_event: dict, run_id: str) -> EventDraft | None:
    """Map one LangGraph v2 stream event to a WSEvent draft, or ``None`` if ignored."""
    kind = langgraph_event.get("event")
    if not kind:
        return None

    if kind == "on_chain_start":
        node = _node_name(langgraph_event)
        if not node:
            return None
        return _draft(
            run_id,
            "agent_status",
            {"agent": node, "state": _NODE_STATE.get(node, "thinking")},
        )

    if kind == "on_chat_model_stream":
        tags = _event_tags(langgraph_event)
        agent = _agent_from_tags(tags)
        if not agent:
            return None
        chunk = (langgraph_event.get("data") or {}).get("chunk")
        if chunk is None:
            return None
        delta = _content_to_text(getattr(chunk, "content", chunk))
        if not delta:
            return None
        return _draft(run_id, "token", {"agent": agent, "delta": delta})

    if kind == "on_tool_end":
        output = (langgraph_event.get("data") or {}).get("output")
        evidence = _evidence_from_tool_output(output)
        if not evidence:
            return None
        return _draft(run_id, "evidence", evidence)

    if kind == "on_chain_end":
        node = _node_name(langgraph_event)
        if not node:
            return None
        output = _chain_output(langgraph_event)
        for key, ready_type in _OUTPUT_READY:
            if key in output:
                payload = (
                    _order_filled_payload(output[key])
                    if key == "sim_order"
                    else output[key]
                )
                return _draft(run_id, ready_type, payload)
        return None

    if kind in ("on_chain_error", "on_tool_error"):
        node = _node_name(langgraph_event) or "graph"
        data = langgraph_event.get("data") or {}
        err = data.get("error") or data.get("message") or str(data)
        return _draft(run_id, "error", {"agent": node, "message": str(err)})

    return None
