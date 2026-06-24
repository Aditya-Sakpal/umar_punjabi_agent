"""Memory system tests — embeddings, recall ranking, node degrade, graph wiring."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.deps import NodeDeps
from app.agents.graph import build_graph, route_after_research
from app.agents.nodes import memory_recall, signal
from app.agents.state import AgentState
from app.db.models import Base, Memory
from app.services.embeddings import (
    EMBEDDING_DIM,
    DeterministicEmbedder,
    SentenceTransformerEmbedder,
)
from app.services.memory import (
    MemoryRecallService,
    build_recall_query,
    format_historical_setups,
)
from app.services.paper_engine import PaperEngine
from app.tools.memory import MemoryTool
from tests.stubs import StubMemoryTool
from tests.test_graph import THIN, _deps as graph_deps_base


@pytest.fixture
def embedder():
    return DeterministicEmbedder()


def test_deterministic_embedder_dimension(embedder):
    vec = embedder.embed("BTC breakout with elevated funding")
    assert len(vec) == EMBEDDING_DIM
    assert abs(sum(x * x for x in vec) - 1.0) < 0.01


def test_similar_texts_have_higher_cosine_than_unrelated(embedder):
    a = embedder.embed("BTCUSDT breakout funding elevated volume surge")
    b = embedder.embed("BTCUSDT breakout funding rate high momentum")
    c = embedder.embed("unrelated weather forecast gardening tips")
    dot_ab = sum(x * y for x, y in zip(a, b))
    dot_ac = sum(x * y for x, y in zip(a, c))
    assert dot_ab > dot_ac


@pytest.mark.slow
def test_sentence_transformer_embedder_loads():
    emb = SentenceTransformerEmbedder()
    vec = emb.embed("test")
    assert len(vec) == EMBEDDING_DIM


def test_format_historical_setups_renders_signal_section():
    memories = [
        {
            "id": "1",
            "symbol": "BTCUSDT",
            "summary": "x",
            "similarity": 0.9,
            "metadata": {
                "signal": {"direction": "BUY"},
                "outcome": 3.2,
            },
            "created_at": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat().replace("+00:00", "Z"),
        }
    ]
    text = format_historical_setups(memories)
    assert "Similar setup observed" in text
    assert "BUY" in text
    assert "+3.2%" in text


def test_build_recall_query_uses_research_brief():
    q = build_recall_query(
        {
            "symbol": "BTCUSDT",
            "research_brief": "Funding elevated breakout",
            "evidence": [{"claim": "funding rate", "value": "0.08%"}],
        }
    )
    assert "BTCUSDT" in q
    assert "Funding elevated" in q


@pytest.mark.asyncio
async def test_memory_recall_node_degrades_on_failure():
    deps = graph_deps_base()
    deps.memory = StubMemoryTool(fail=True)  # type: ignore[attr-defined]
    out = await memory_recall.make_node(deps)(
        {"symbol": "BTCUSDT", "research_brief": "brief", "evidence": THIN}
    )
    assert out["similar_memories"] == []
    assert out["status"] == "degraded:memory_recall"


@pytest.mark.asyncio
async def test_signal_receives_historical_setups_in_prompt():
    memories = [
        {
            "id": "m1",
            "symbol": "BTCUSDT",
            "summary": "prior",
            "similarity": 0.88,
            "metadata": {"signal": {"direction": "BUY"}, "outcome": 2.1},
            "created_at": "2026-06-20T12:00:00Z",
        }
    ]
    deps = graph_deps_base()
    deps.memory = StubMemoryTool(memories)  # type: ignore[attr-defined]
    captured: dict = {}

    async def fake_structured_llm(**kwargs):
        captured["user"] = kwargs["user"]
        return {
            "direction": "HOLD",
            "confidence": 0.3,
            "thesis": "cautious",
            "horizon": "intraday",
        }

    import app.agents.nodes.signal as signal_mod

    original = signal_mod.structured_llm
    signal_mod.structured_llm = fake_structured_llm
    try:
        await signal.make_node(deps)(
            {
                "symbol": "BTCUSDT",
                "research_brief": "test brief",
                "evidence": THIN,
                "similar_memories": memories,
            }
        )
    finally:
        signal_mod.structured_llm = original

    assert "Relevant Historical Setups" in captured["user"]
    assert "BUY" in captured["user"]


@pytest.mark.asyncio
async def test_graph_includes_memory_recall_node():
    async def stub_research(state):
        return {"research_brief": "ok", "evidence": THIN * 3, "status": "research_done"}

    async def stub_memory(state):
        return {"similar_memories": [], "status": "memory_recall_done"}

    visits: list[str] = []

    async def stub_signal(state):
        visits.append("signal")
        return {
            "signal": {
                "direction": "HOLD",
                "confidence": 0.3,
                "thesis": "t",
                "horizon": "intraday",
            },
            "status": "signal_done",
        }

    graph = build_graph(
        graph_deps_base(),
        node_overrides={
            "research": stub_research,
            "memory_recall": stub_memory,
            "signal": stub_signal,
        },
    )
    await graph.ainvoke({"run_id": "t", "symbol": "BTCUSDT", "trigger": "user"})
    assert visits == ["signal"]
    assert route_after_research({"evidence": THIN * 3, "revision_count": 0}) == "memory_recall"


@pytest.mark.asyncio
async def test_recall_returns_empty_on_db_failure(embedder):
    class BrokenSession:
        async def __aenter__(self):
            raise OSError("db down")

        async def __aexit__(self, *args):
            pass

    class BrokenFactory:
        def __call__(self):
            return BrokenSession()

    svc = MemoryRecallService(BrokenFactory(), embedder)  # type: ignore[arg-type]
    assert await svc.recall("query", "BTCUSDT") == []


def _pg_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or "postgresql" not in url:
        return None
    return url


@pytest.mark.asyncio
async def test_pgvector_recall_ranking(embedder):
    url = _pg_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL / DATABASE_URL not set")

    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    svc = MemoryRecallService(factory, embedder)
    symbol = "BTCUSDT"
    await svc.store(
        symbol=symbol,
        summary="BTCUSDT momentum breakout with elevated funding and volume",
        metadata={"signal": {"direction": "BUY"}, "outcome": 3.2},
    )
    await svc.store(
        symbol=symbol,
        summary="ETHUSDT unrelated defi governance vote low volatility",
        metadata={"signal": {"direction": "HOLD"}, "outcome": 0.0},
    )

    hits = await svc.recall("BTC breakout funding volume surge", symbol, limit=2)
    assert len(hits) >= 1
    assert "BTCUSDT momentum" in hits[0]["summary"]
    assert hits[0]["similarity"] >= hits[-1]["similarity"]

    async with engine.begin() as conn:
        await conn.execute(Memory.__table__.delete().where(Memory.symbol == symbol))
    await engine.dispose()
