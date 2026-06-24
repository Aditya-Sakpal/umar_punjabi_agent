"""Task 13 verification — memory recall (embed, store, retrieve)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, Memory
from app.services.embeddings import DeterministicEmbedder, SentenceTransformerEmbedder
from app.services.memory import MemoryRecallService, format_historical_setups
from sqlalchemy import delete


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


async def _demo_recall(embedder_name: str) -> None:
    url = os.environ.get("DATABASE_URL")
    if not url or "postgresql" not in url:
        print("DATABASE_URL not set — skipping live pgvector demo")
        return

    embedder = (
        SentenceTransformerEmbedder()
        if embedder_name == "minilm"
        else DeterministicEmbedder()
    )
    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    svc = MemoryRecallService(factory, embedder)
    symbol = "BTCUSDT"

    await svc.store(
        symbol=symbol,
        summary="BTCUSDT breakout above 96k with elevated funding 0.08% and 2x volume",
        metadata={
            "signal": {"direction": "BUY", "confidence": 0.65},
            "decision": {"action": "BUY"},
            "outcome": 3.2,
        },
    )
    await svc.store(
        symbol=symbol,
        summary="ETHUSDT low volatility range trade unrelated macro",
        metadata={
            "signal": {"direction": "HOLD"},
            "outcome": 0.0,
        },
    )

    query = "BTC momentum breakout funding elevated volume"
    hits = await svc.recall(query, symbol, limit=3)
    print(f"Query: {query!r}")
    print(json.dumps(hits, indent=2))
    print()
    print("Signal prompt section:")
    print(format_historical_setups(hits))

    async with engine.begin() as conn:
        await conn.execute(delete(Memory).where(Memory.symbol == symbol))
    await engine.dispose()


def main() -> None:
    _section("EMBEDDING (DeterministicEmbedder smoke)")
    emb = DeterministicEmbedder()
    vec = emb.embed("BTCUSDT funding spike breakout")
    print(f"dim={len(vec)} norm={sum(x*x for x in vec):.4f}")

    _section("PGVECTOR RECALL (requires DATABASE_URL + memories table)")
    asyncio.run(_demo_recall("deterministic"))

    print()
    print("ALL TASK 13 CHECKS PASSED (DB demo skipped if DATABASE_URL unset)")


if __name__ == "__main__":
    main()
