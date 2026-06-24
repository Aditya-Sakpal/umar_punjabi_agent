"""FastAPI dependency injection."""
from __future__ import annotations

from fastapi import Request

from app.config import Settings, get_settings
from app.services.event_bus import EventBus
from app.services.graph_runner import GraphRunner
from app.services.orchestrator import GraphOrchestrator


def get_settings_dep() -> Settings:
    return get_settings()


def get_graph_runner(request: Request) -> GraphRunner:
    return request.app.state.graph_runner


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_orchestrator(request: Request) -> GraphOrchestrator:
    return request.app.state.orchestrator
