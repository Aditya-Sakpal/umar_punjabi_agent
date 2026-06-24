"""Memory recall + persistence — pgvector cosine similarity."""
from __future__ import annotations

import datetime as dt
import logging
import uuid
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.state import AgentState
from app.db.models import Memory
from app.services.embeddings import Embedder

logger = logging.getLogger(__name__)


class SimilarMemory(TypedDict):
    id: str
    symbol: str
    summary: str
    similarity: float
    metadata: dict
    created_at: str


def _relative_age(created_at: str | dt.datetime) -> str:
    if isinstance(created_at, str):
        try:
            ts = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return "recently"
    else:
        ts = created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    delta = dt.datetime.now(dt.timezone.utc) - ts
    days = delta.days
    if days <= 0:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago" if hours else "today"
    return f"{days} day{'s' if days != 1 else ''} ago"


def _format_outcome(outcome: object) -> str:
    if outcome is None:
        return "pending"
    if isinstance(outcome, dict):
        pnl = outcome.get("pnl") or outcome.get("realized_pnl")
        if pnl is not None:
            sign = "+" if float(pnl) >= 0 else ""
            return f"{sign}{float(pnl):.1f}%"
        return str(outcome.get("status", "pending"))
    if isinstance(outcome, (int, float)):
        sign = "+" if float(outcome) >= 0 else ""
        return f"{sign}{float(outcome):.1f}%"
    return str(outcome)


def format_historical_setups(memories: list[SimilarMemory]) -> str:
    """Render memory hits for the Signal agent prompt."""
    if not memories:
        return "None on record."
    blocks: list[str] = []
    for m in memories:
        meta = m.get("metadata") or {}
        signal = meta.get("signal") or {}
        direction = signal.get("direction", "UNKNOWN")
        blocks.append(
            f"Similar setup observed {_relative_age(m['created_at'])}.\n\n"
            f"Signal:\n{direction}\n\n"
            f"Outcome:\n{_format_outcome(meta.get('outcome'))}"
        )
    return "\n\n".join(blocks)


def build_recall_query(state: AgentState) -> str:
    """Compose a retrieval query from research output."""
    symbol = state.get("symbol", "")
    brief = (state.get("research_brief") or "")[:600]
    evidence_bits = []
    for ev in (state.get("evidence") or [])[:6]:
        evidence_bits.append(f"{ev.get('claim')}={ev.get('value')}")
    ev_text = " ".join(evidence_bits)
    return f"{symbol} {brief} {ev_text}".strip()


def build_run_summary(state: AgentState) -> str:
    """Text blob embedded when persisting a completed run."""
    signal = state.get("signal") or {}
    decision = state.get("decision") or {}
    risk = state.get("risk") or {}
    parts = [
        f"Symbol {state.get('symbol', '')}",
        state.get("research_brief", ""),
        f"Signal {signal.get('direction')} confidence {signal.get('confidence')}",
        f"Risk concerns {', '.join(risk.get('concerns') or [])}",
        f"Decision {decision.get('action')} size {decision.get('size_pct')}%",
    ]
    return " | ".join(p for p in parts if p)


def build_run_metadata(state: AgentState) -> dict:
    sim = state.get("sim_order") or {}
    outcome: object = "pending"
    if sim:
        outcome = {
            "status": "filled" if sim.get("filled") else "simulated",
            "pnl": sim.get("realized_pnl", sim.get("pnl")),
            "side": sim.get("side") or sim.get("action"),
        }
    return {
        "run_id": state.get("run_id"),
        "signal": state.get("signal"),
        "risk": state.get("risk"),
        "decision": state.get("decision"),
        "outcome": outcome,
    }


class MemoryRecallService:
    """Recall and store trading memories via pgvector."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedder: Embedder,
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder

    async def recall(
        self,
        query: str,
        symbol: str,
        *,
        limit: int = 5,
    ) -> list[SimilarMemory]:
        """Return top similar memories for ``symbol``, ordered by cosine similarity."""
        if not query.strip():
            return []
        try:
            query_vec = self._embedder.embed(query)
            async with self._session_factory() as session:
                distance = Memory.embedding.cosine_distance(query_vec).label("distance")
                stmt = (
                    select(Memory, distance)
                    .where(Memory.symbol == symbol.upper())
                    .order_by(distance)
                    .limit(limit)
                )
                rows = (await session.execute(stmt)).all()
            return [
                {
                    "id": row.Memory.id,
                    "symbol": row.Memory.symbol,
                    "summary": row.Memory.summary,
                    "similarity": round(1.0 - float(row.distance), 4),
                    "metadata": row.Memory.meta or {},
                    "created_at": row.Memory.created_at.isoformat().replace("+00:00", "Z"),
                }
                for row in rows
            ]
        except Exception:
            logger.exception("memory recall failed symbol=%s", symbol)
            return []

    async def store(
        self,
        *,
        symbol: str,
        summary: str,
        metadata: dict,
    ) -> str | None:
        """Persist one memory row; returns id or None on failure."""
        try:
            embedding = self._embedder.embed(summary)
            row_id = str(uuid.uuid4())
            async with self._session_factory() as session:
                session.add(
                    Memory(
                        id=row_id,
                        symbol=symbol.upper(),
                        summary=summary,
                        embedding=embedding,
                        meta=metadata,
                    )
                )
                await session.commit()
            return row_id
        except Exception:
            logger.exception("memory store failed symbol=%s", symbol)
            return None

    async def store_from_run(self, state: AgentState) -> str | None:
        """Persist a completed graph run as a recallable memory."""
        if not state.get("decision"):
            return None
        return await self.store(
            symbol=state.get("symbol", ""),
            summary=build_run_summary(state),
            metadata=build_run_metadata(state),
        )
