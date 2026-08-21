import math
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class MarketRegime(str, Enum):
    NORMAL = "NORMAL"
    VOLATILITY_SHOCK = "VOLATILITY_SHOCK"
    LIQUIDITY_SHOCK = "LIQUIDITY_SHOCK"
    COMBINED_SHOCK = "COMBINED_SHOCK"


class RunStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def _check_finite(val: float, field_name: str) -> float:
    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"Field '{field_name}' must be a finite number, got {val}")
    return val


class StrictBaseModel(BaseModel):
    @model_validator(mode="after")
    def validate_finite_floats(self) -> "StrictBaseModel":
        for name, value in self.__dict__.items():
            if isinstance(value, float):
                _check_finite(value, name)
        return self


class Order(StrictBaseModel):
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float = Field(..., gt=0, description="Total order quantity")
    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_times(self) -> "Order":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        return self


class MarketState(StrictBaseModel):
    timestamp: float = Field(..., ge=0)
    mid_price: float = Field(..., gt=0)
    bid_price: float = Field(..., gt=0)
    ask_price: float = Field(..., gt=0)
    spread_bps: float = Field(..., ge=0)
    volume: float = Field(..., ge=0)
    liquidity: float = Field(..., gt=0)
    volatility: float = Field(..., ge=0)
    transaction_cost_bps: float = Field(..., ge=0)
    regime: MarketRegime = MarketRegime.NORMAL

    @model_validator(mode="after")
    def validate_prices(self) -> "MarketState":
        if self.ask_price < self.bid_price:
            raise ValueError("ask_price cannot be lower than bid_price")
        return self


class ExecutionDecision(StrictBaseModel):
    timestamp: float = Field(..., ge=0)
    quantity: float = Field(..., ge=0)
    participation_rate: float = Field(..., ge=0.0, le=1.0)
    aggressiveness: float = Field(..., ge=0.0, le=1.0)
    expected_cost: float = Field(..., ge=0.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    rationale: str = ""


class ExecutionContext(StrictBaseModel):
    order: Order
    market_state: MarketState
    remaining_quantity: float = Field(..., ge=0)
    elapsed_time: float = Field(..., ge=0)
    remaining_time: float = Field(..., ge=0)
    previous_decision: Optional[ExecutionDecision] = None
    strategy_configuration: Dict[str, Any] = Field(default_factory=dict)


class FillEvent(StrictBaseModel):
    requested_quantity: float = Field(..., ge=0)
    filled_quantity: float = Field(..., ge=0)
    fill_price: float = Field(..., ge=0)
    spread_cost: float = Field(..., ge=0)
    impact_cost: float = Field(..., ge=0)
    transaction_cost: float = Field(..., ge=0)
    timestamp: float = Field(..., ge=0)


class ScenarioConfig(StrictBaseModel):
    scenario_id: str
    name: str
    description: str = ""
    initial_price: float = Field(100.0, gt=0)
    volatility: float = Field(0.02, ge=0)
    liquidity: float = Field(10000.0, gt=0)
    volume: float = Field(1000.0, ge=0)
    spread: float = Field(0.05, ge=0)  # absolute price spread or bps reference
    transaction_cost_bps: float = Field(1.0, ge=0)
    shock_timestamp: Optional[float] = None
    volatility_multiplier: float = Field(1.0, gt=0)
    liquidity_multiplier: float = Field(1.0, gt=0)
    spread_multiplier: float = Field(1.0, gt=0)
    random_seed: int = 42
    total_steps: int = Field(60, gt=0)
    step_duration_seconds: float = Field(1.0, gt=0)


class RunMetrics(StrictBaseModel):
    run_id: str
    strategy: str
    order_side: OrderSide
    total_quantity: float
    filled_quantity: float
    completion_percentage: float
    arrival_price: float
    vwap_fill_price: float
    final_price: float
    total_execution_cost: float
    total_execution_cost_bps: float
    spread_cost: float
    spread_cost_bps: float
    impact_cost: float
    impact_cost_bps: float
    transaction_cost: float
    transaction_cost_bps: float
    implementation_shortfall: float
    implementation_shortfall_bps: float
    max_participation_rate: float
    risk_score: float
    stability_score: float
