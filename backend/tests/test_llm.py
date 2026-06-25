"""LLM helpers that don't need network: JSON extraction, schema coercion, tier resolution."""
import pytest

from app.agents import llm as llm_mod
from app.agents.state import Signal
from app.config import settings


def test_model_for_tier_resolves_from_settings():
    assert llm_mod.model_for_tier("strong") == settings.llm_strong
    assert llm_mod.model_for_tier("cheap") == settings.llm_cheap


def test_extract_json_from_prose():
    text = (
        "Here is my reasoning about the setup, funding looks elevated.\n"
        'Final answer:\n{"direction": "BUY", "confidence": 0.6, '
        '"thesis": "clean breakout", "horizon": "swing"} -- done'
    )
    obj = llm_mod._extract_json_object(text)
    assert obj["direction"] == "BUY" and obj["confidence"] == 0.6


def test_extract_json_handles_braces_in_strings():
    text = 'prefix {"thesis": "a {nested} brace", "confidence": 0.5} suffix'
    obj = llm_mod._extract_json_object(text)
    assert obj["thesis"] == "a {nested} brace"


def test_extract_json_returns_last_object_when_schema_echoed():
    # Regression: the model echoes the (invalid) schema, then emits the real JSON last.
    text = (
        "Thinking out loud about the trade.\n"
        'Output JSON: { "concerns": [str], "adjusted_confidence": 0..1, "veto": bool }\n'
        "...reasoning...\n"
        '{"concerns": ["funding elevated at 0.04%"], "adjusted_confidence": 0.35, '
        '"suggested_size_pct": 2.0, "stop_loss_pct": 4.5, "veto": false}'
    )
    obj = llm_mod._extract_json_object(text)
    assert obj["adjusted_confidence"] == 0.35 and obj["veto"] is False
    assert obj["concerns"] == ["funding elevated at 0.04%"]


def test_coerce_to_signal_schema_coerces_and_validates():
    raw = {"direction": "BUY", "confidence": "0.65", "thesis": "x", "horizon": "intraday"}
    out = llm_mod._coerce_to_schema(raw, Signal)
    assert out["confidence"] == 0.65 and isinstance(out["confidence"], float)
    assert set(out) == {"direction", "confidence", "thesis", "horizon"}


def test_coerce_missing_field_raises():
    raw = {"direction": "BUY", "confidence": 0.6, "thesis": "x"}  # missing horizon
    with pytest.raises(ValueError, match="missing required field 'horizon'"):
        llm_mod._coerce_to_schema(raw, Signal)


def test_coerce_bad_literal_raises():
    raw = {"direction": "MAYBE", "confidence": 0.6, "thesis": "x", "horizon": "swing"}
    with pytest.raises(ValueError, match="direction"):
        llm_mod._coerce_to_schema(raw, Signal)


def test_extract_json_none_raises():
    with pytest.raises(ValueError, match="no parseable JSON"):
        llm_mod._extract_json_object("there is no json here at all")
