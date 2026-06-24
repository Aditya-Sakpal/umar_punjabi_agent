"""AgentState reducer semantics: Annotated[..., add] fields must APPEND, not overwrite."""
from operator import add
from typing import Annotated, get_args, get_type_hints

from app.agents.state import AgentState, Evidence


def _reducer_for(field: str):
    """Pull the reducer callable out of an Annotated[type, reducer] field on AgentState."""
    hints = get_type_hints(AgentState, include_extras=True)
    args = get_args(hints[field])  # (base_type, reducer, ...)
    assert len(args) >= 2, f"{field} is not Annotated with a reducer"
    return args[1]


def test_evidence_and_errors_use_add_reducer():
    assert _reducer_for("evidence") is add
    assert _reducer_for("errors") is add


def test_reducer_appends_evidence():
    reducer = _reducer_for("evidence")
    first: list[Evidence] = [{"source": "binance", "claim": "price", "value": 100.0, "ts": "t1"}]
    second: list[Evidence] = [{"source": "news:cd", "claim": "headline", "value": None, "ts": "t2"}]
    merged = reducer(first, second)
    assert len(merged) == 2  # appended, not overwritten
    assert merged[0]["source"] == "binance" and merged[1]["source"] == "news:cd"


def test_reducer_appends_errors():
    reducer = _reducer_for("errors")
    merged = reducer(["risk: boom"], ["signal: oops"])
    assert merged == ["risk: boom", "signal: oops"]
