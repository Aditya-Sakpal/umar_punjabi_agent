"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import create_async_engine

from app.agents.deps import build_node_deps
from app.agents.graph import build_graph, graph_info
from app.api.routes.analyze import router as analyze_router
from app.api.routes.ws import router as ws_router
from app.config import settings
from app.db.session import async_session_factory
from app.services.embeddings import SentenceTransformerEmbedder
from app.services.event_bus import EventBus
from app.services.graph_runner import GraphRunner
from app.services.memory import MemoryRecallService
from app.services.orchestrator import GraphOrchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_engine = create_async_engine(settings.database_url, future=True)
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    app.state.event_bus = EventBus(app.state.redis)

    node_deps = await build_node_deps()
    compiled = build_graph(node_deps)
    app.state.node_deps = node_deps
    app.state.graph = compiled
    app.state.graph_info = graph_info()
    app.state.graph_runner = GraphRunner(compiled)
    memory_service = MemoryRecallService(async_session_factory, SentenceTransformerEmbedder())
    app.state.memory_service = memory_service
    app.state.orchestrator = GraphOrchestrator(compiled, app.state.event_bus, memory_service)

    try:
        yield
    finally:
        await node_deps.aclose()
        await app.state.redis.aclose()
        await app.state.db_engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Trading Intelligence Demo",
        description="Multi-agent trading intelligence API",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            raise exc
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "internal_error",
                    "message": str(exc),
                }
            },
        )

    application.include_router(analyze_router)
    application.include_router(ws_router)
    application.get("/health")(health)
    return application


async def health() -> dict[str, str]:
    return {"status": "ok"}


app = create_app()
