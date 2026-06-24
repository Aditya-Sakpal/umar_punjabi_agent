"""POST /analyze — synchronous deep-chain run (Task 9)."""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.deps import get_graph_runner, get_orchestrator
from app.api.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeStreamResponse,
    DecisionOut,
    RunMetadataOut,
    SimOrderOut,
    validate_symbol_in_universe,
)
from app.services.graph_runner import GraphRunner
from app.services.orchestrator import GraphOrchestrator

router = APIRouter(tags=["analyze"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Run the trading deep-chain synchronously",
    responses={
        422: {"description": "Invalid symbol or request body"},
        500: {"description": "Graph execution failed"},
    },
)
async def analyze(
    body: AnalyzeRequest,
    runner: GraphRunner = Depends(get_graph_runner),
) -> AnalyzeResponse:
    try:
        validate_symbol_in_universe(body.symbol)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_symbol", "message": str(e)},
        ) from e

    run_id = str(uuid.uuid4())
    started = time.perf_counter()
    try:
        final = await runner.run(run_id=run_id, symbol=body.symbol, trigger="user")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "graph_execution_failed", "message": str(e)},
        ) from e
    duration_ms = int((time.perf_counter() - started) * 1000)

    decision_raw = final.get("decision")
    if not decision_raw:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "missing_decision",
                "message": "graph completed without a decision",
            },
        )

    sim_raw = final.get("sim_order")
    sim_order = SimOrderOut.model_validate(sim_raw) if sim_raw else None

    return AnalyzeResponse(
        run_id=run_id,
        decision=DecisionOut.model_validate(decision_raw),
        sim_order=sim_order,
        metadata=RunMetadataOut(duration_ms=duration_ms, status="completed"),
    )


@router.post(
    "/analyze/stream",
    response_model=AnalyzeStreamResponse,
    summary="Start a streaming deep-chain run",
    responses={422: {"description": "Invalid symbol or request body"}},
)
async def analyze_stream(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    orchestrator: GraphOrchestrator = Depends(get_orchestrator),
) -> AnalyzeStreamResponse:
    try:
        validate_symbol_in_universe(body.symbol)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_symbol", "message": str(e)},
        ) from e

    run_id = str(uuid.uuid4())
    background_tasks.add_task(
        orchestrator.run,
        run_id=run_id,
        symbol=body.symbol,
        trigger="user",
    )
    return AnalyzeStreamResponse(run_id=run_id)
