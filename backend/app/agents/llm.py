"""Anthropic Claude client factory + tagged-streaming and structured-output helpers.

Built on ``langchain-anthropic`` (not the raw SDK): the entire streaming/attribution
design in the blueprint relies on LangChain's ``astream_events`` emitting
``on_chat_model_stream`` events that carry per-call ``tags``. Those events are a
LangChain mechanism — the raw Anthropic SDK does not produce them — so ChatAnthropic
is the right substrate for end-to-end per-agent token attribution.

Model strings come from settings (LLM_STRONG / LLM_CHEAP); never hardcoded.
"""
from __future__ import annotations

import json
from typing import Any, Literal, get_args, get_origin, get_type_hints

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings

Tier = Literal["strong", "cheap"]


def model_for_tier(tier: Tier) -> str:
    return settings.llm_strong if tier == "strong" else settings.llm_cheap


def make_llm(
    tier: Tier = "strong",
    *,
    streaming: bool = True,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    **kwargs: Any,
) -> ChatAnthropic:
    """Build a ChatAnthropic for the given model tier, reading the model + key from settings."""
    return ChatAnthropic(
        model=model_for_tier(tier),
        api_key=settings.anthropic_api_key,
        streaming=streaming,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )


# --- text extraction helpers -------------------------------------------------

def _content_to_text(content: Any) -> str:
    """Flatten a LangChain message ``content`` (str or list of blocks) to text."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _extract_json_object(text: str) -> dict:
    """Pull the first balanced ``{...}`` JSON object out of (possibly prose-wrapped) text."""
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(stripped)):
            ch = stripped[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = stripped[start : i + 1]
                        try:
                            obj = json.loads(candidate)
                            if isinstance(obj, dict):
                                return obj
                        except json.JSONDecodeError:
                            break  # try next '{'
        start = stripped.find("{", start + 1)

    raise ValueError(f"no parseable JSON object found in model output: {text[:200]!r}")


def _coerce_to_schema(data: dict, schema: type) -> dict:
    """Validate that ``data`` matches the TypedDict ``schema`` and lightly coerce types.

    Raises a clear ValueError if a field is missing or cannot be coerced.
    """
    hints = get_type_hints(schema)
    out: dict[str, Any] = {}
    for key, hint in hints.items():
        if key not in data:
            raise ValueError(f"structured output missing required field {key!r} for {schema.__name__}")
        value = data[key]
        try:
            out[key] = _coerce_value(value, hint, key, schema)
        except (TypeError, ValueError) as e:
            raise ValueError(f"field {key!r} for {schema.__name__}: {e}") from e
    return out


def _coerce_value(value: Any, hint: Any, key: str, schema: type) -> Any:
    if hint is float:
        return float(value)
    if hint is int:
        return int(value)
    if hint is str:
        return str(value)
    if hint is bool:
        if isinstance(value, bool):
            return value
        raise ValueError(f"expected bool, got {type(value).__name__}")
    if get_origin(hint) is Literal:
        allowed = get_args(hint)
        if value not in allowed:
            raise ValueError(f"{value!r} not in allowed {allowed}")
        return value
    if get_origin(hint) is list:
        if not isinstance(value, list):
            raise ValueError(f"expected list, got {type(value).__name__}")
        return value
    return value  # leave anything else as-is


# --- public helpers ----------------------------------------------------------

async def structured_llm(
    *,
    system: str,
    user: str,
    schema: type,
    tags: list[str] | None = None,
    tier: Tier = "strong",
    max_tokens: int = 1024,
) -> dict:
    """Call the model and return a dict conforming to the TypedDict ``schema``.

    The model is asked to emit JSON; the response (which may have surrounding prose)
    is parsed and validated against the schema. Raises ValueError if it cannot be coerced.
    """
    llm = make_llm(tier, streaming=False, max_tokens=max_tokens)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    resp = await llm.ainvoke(messages, config={"tags": tags or []})
    text = _content_to_text(resp.content)
    data = _extract_json_object(text)
    return _coerce_to_schema(data, schema)


async def iter_token_events(
    *,
    system: str,
    user: str,
    agent: str,
    tier: Tier = "strong",
    max_tokens: int = 512,
):
    """Stream the model via ``astream_events`` with a per-agent tag attached.

    Yields the raw LangChain stream events. The call config carries
    ``tags=["agent:<agent>"]`` so every ``on_chat_model_stream`` event is attributable
    to its agent — the foundation for downstream per-agent token attribution.
    """
    llm = make_llm(tier, streaming=True, max_tokens=max_tokens)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    config = {"tags": [f"agent:{agent}"]}
    async for event in llm.astream_events(messages, version="v2", config=config):
        yield event


async def stream_tokens(
    *,
    system: str,
    user: str,
    agent: str,
    tier: Tier = "strong",
    max_tokens: int = 512,
):
    """Convenience: stream just the text deltas (with the agent tag attached)."""
    async for event in iter_token_events(
        system=system, user=user, agent=agent, tier=tier, max_tokens=max_tokens
    ):
        if event["event"] == "on_chat_model_stream":
            delta = _content_to_text(event["data"]["chunk"].content)
            if delta:
                yield delta
