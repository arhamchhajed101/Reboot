from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    CompareRequest,
    CompareResponse,
    CreateRunRequest,
    RunEventsResponse,
    RunResponse,
)
from app.core.database import get_db
from app.models.domain import (
    ExecutionDecision,
    FillEvent,
    MarketState,
    RunMetrics,
    ScenarioConfig,
)
from app.repositories.run_repository import RunRepository
from app.services.run_service import RunService
from app.simulator.scenarios import list_scenarios, load_scenario

router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "trade-execution-backend"}


@router.get("/scenarios", response_model=List[ScenarioConfig], tags=["Scenarios"])
async def get_scenarios():
    return list_scenarios()


@router.get("/scenarios/{scenario_id}", response_model=ScenarioConfig, tags=["Scenarios"])
async def get_scenario_by_id(scenario_id: str):
    try:
        return load_scenario(scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/runs", response_model=RunMetrics, status_code=status.HTTP_201_CREATED, tags=["Runs"])
async def create_and_execute_run(
    req: CreateRunRequest, db: AsyncSession = Depends(get_db)
):
    service = RunService(db)
    try:
        metrics = await service.execute_run(
            scenario_id=req.scenario_id,
            strategy_name=req.strategy,
            order_side=req.order_side,
            quantity=req.quantity,
            horizon_seconds=req.horizon_seconds,
            symbol=req.symbol,
            seed=req.seed,
            max_participation_rate=req.max_participation_rate,
        )
        return metrics
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/runs/{run_id}", response_model=RunResponse, tags=["Runs"])
async def get_run_by_id(run_id: str, db: AsyncSession = Depends(get_db)):
    repo = RunRepository(db)
    run_db = await repo.get_run_with_details(run_id)
    if not run_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")

    metrics_obj = None
    if run_db.metrics and run_db.metrics.raw_json:
        metrics_obj = RunMetrics(**run_db.metrics.raw_json)

    return RunResponse(
        run_id=run_db.run_id,
        scenario_id=run_db.scenario_id,
        strategy=run_db.strategy,
        order_side=run_db.order_side,
        symbol=run_db.symbol,
        quantity=run_db.quantity,
        horizon=run_db.horizon,
        status=run_db.status,
        seed=run_db.seed,
        metrics=metrics_obj,
    )


@router.get("/runs/{run_id}/events", response_model=RunEventsResponse, tags=["Runs"])
async def get_run_events(run_id: str, db: AsyncSession = Depends(get_db)):
    repo = RunRepository(db)
    run_db = await repo.get_run_with_details(run_id)
    if not run_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")

    ticks = [
        MarketState(
            timestamp=t.timestamp,
            mid_price=t.mid_price,
            bid_price=t.bid_price,
            ask_price=t.ask_price,
            spread_bps=t.spread_bps,
            volume=t.volume,
            liquidity=t.liquidity,
            volatility=t.volatility,
            transaction_cost_bps=getattr(t, "transaction_cost_bps", 1.0),
            regime=t.regime,
        )
        for t in sorted(run_db.ticks, key=lambda x: x.step)
    ]

    decisions = [
        ExecutionDecision(
            timestamp=d.timestamp,
            quantity=d.quantity,
            participation_rate=d.participation_rate,
            aggressiveness=d.aggressiveness,
            expected_cost=d.expected_cost,
            risk_score=d.risk_score,
            rationale=d.rationale or "",
        )
        for d in sorted(run_db.decisions, key=lambda x: x.step)
    ]

    fills = [
        FillEvent(
            requested_quantity=f.requested_quantity,
            filled_quantity=f.filled_quantity,
            fill_price=f.fill_price,
            spread_cost=f.spread_cost,
            impact_cost=f.impact_cost,
            transaction_cost=f.transaction_cost,
            timestamp=f.timestamp,
        )
        for f in sorted(run_db.fills, key=lambda x: x.step)
    ]

    metrics_obj = None
    if run_db.metrics and run_db.metrics.raw_json:
        metrics_obj = RunMetrics(**run_db.metrics.raw_json)

    return RunEventsResponse(
        run_id=run_db.run_id,
        status=run_db.status,
        ticks=ticks,
        decisions=decisions,
        fills=fills,
        metrics=metrics_obj,
    )


@router.post("/runs/compare", response_model=CompareResponse, tags=["Benchmarking"])
async def compare_run_benchmark(
    req: CompareRequest, db: AsyncSession = Depends(get_db)
):
    service = RunService(db)
    try:
        benchmark_results = await service.compare_strategies(
            scenario_id=req.scenario_id,
            order_side=req.order_side,
            quantity=req.quantity,
            horizon_seconds=req.horizon_seconds,
            symbol=req.symbol,
            seed=req.seed,
            strategies=req.strategies,
        )
        return CompareResponse(
            scenario_id=req.scenario_id,
            order_side=req.order_side,
            quantity=req.quantity,
            seed=req.seed,
            benchmark_results=benchmark_results,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
