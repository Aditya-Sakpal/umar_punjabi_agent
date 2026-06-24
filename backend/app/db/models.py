"""SQLAlchemy models — MVP tables only (blueprint Part 6).

Run, DecisionLog, Position, Fill, Observation. No tables beyond Part 6.
SQLAlchemy 2.0 typed style (Mapped / mapped_column).
"""
import datetime as dt
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str]
    trigger: Mapped[str]
    status: Mapped[str] = mapped_column(default="running")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DecisionLog(Base):  # the audit record powering Trace View
    __tablename__ = "decision_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(index=True)
    symbol: Mapped[str]
    evidence: Mapped[list] = mapped_column(JSON)
    signal: Mapped[dict] = mapped_column(JSON)
    risk: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[dict] = mapped_column(JSON)
    model_versions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(index=True)
    qty: Mapped[float]
    avg_entry: Mapped[float]
    realized_pnl: Mapped[float] = mapped_column(default=0.0)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)


class Fill(Base):
    __tablename__ = "fills"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(index=True)
    symbol: Mapped[str]
    side: Mapped[str]
    qty: Mapped[float]
    price: Mapped[float]
    fee: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Observation(Base):  # semantic market memory (legacy — prefer Memory)
    __tablename__ = "observations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str]
    text: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(384))  # MiniLM dim
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Memory(Base):
    """Completed-run recall row — pgvector cosine search (Task 13)."""

    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(index=True)
    summary: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
