from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.domain import (
    ExecutionDecision,
    FillEvent,
    MarketState,
    OrderSide,
    RunMetrics,
    RunStatus,
    ScenarioConfig,
)


class CreateRunRequest(BaseModel):
    scenario_id: str = "normal"
    strategy: str = "twap"
    order_side: OrderSide = OrderSide.BUY
    quantity: float = Field(1000.0, gt=0)
    horizon_seconds: float = Field(60.0, gt=0)
    symbol: str = "AAPL"
    seed: Optional[int] = 42
    max_participation_rate: float = Field(0.30, ge=0.01, le=1.0)


class RunResponse(BaseModel):
    run_id: str
    scenario_id: str
    strategy: str
    order_side: OrderSide
    symbol: str
    quantity: float
    horizon: float
    status: RunStatus
    seed: int
    metrics: Optional[RunMetrics] = None


class RunEventsResponse(BaseModel):
    run_id: str
    status: RunStatus
    ticks: List[MarketState]
    decisions: List[ExecutionDecision]
    fills: List[FillEvent]
    metrics: Optional[RunMetrics] = None


class CompareRequest(BaseModel):
    scenario_id: str = "normal"
    order_side: OrderSide = OrderSide.BUY
    quantity: float = Field(1000.0, gt=0)
    horizon_seconds: float = Field(60.0, gt=0)
    symbol: str = "AAPL"
    seed: int = 42
    strategies: List[str] = Field(default_factory=lambda: ["twap", "volume_aware", "adaptive"])


class CompareResponse(BaseModel):
    scenario_id: str
    order_side: OrderSide
    quantity: float
    seed: int
    benchmark_results: Dict[str, RunMetrics]
