"""Domain models and data contracts for the RECURZ Execution Engine.

Follows Pydantic v2 conventions for typed, validated execution models.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class RegimeType(str, Enum):
    """Market regime classification enum."""
    NORMAL = "NORMAL"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    HIGH_SPREAD = "HIGH_SPREAD"
    STRESSED = "STRESSED"
    ZERO_VOLUME = "ZERO_VOLUME"


class ReasonCode(str, Enum):
    """Structured, machine-readable reason codes for execution decisions."""
    NORMAL_EXECUTION = "NORMAL_EXECUTION"
    NORMAL_TWAP = "NORMAL_TWAP"
    NORMAL_VOLUME_AWARE = "NORMAL_VOLUME_AWARE"
    ADAPTIVE_OPTIMAL = "ADAPTIVE_OPTIMAL"
    HIGH_VOLATILITY_THROTTLE = "HIGH_VOLATILITY_THROTTLE"
    LOW_LIQUIDITY_THROTTLE = "LOW_LIQUIDITY_THROTTLE"
    WIDE_SPREAD_THROTTLE = "WIDE_SPREAD_THROTTLE"
    MAX_PARTICIPATION_CLAMP = "MAX_PARTICIPATION_CLAMP"
    SINGLE_CHILD_CLAMP = "SINGLE_CHILD_CLAMP"
    DEADLINE_EMERGENCY = "DEADLINE_EMERGENCY"
    ZERO_MARKET_VOLUME = "ZERO_MARKET_VOLUME"
    ORDER_COMPLETED = "ORDER_COMPLETED"
    RISK_THROTTLED = "RISK_THROTTLED"
    INVALID_MARKET_STATE = "INVALID_MARKET_STATE"


class Order(BaseModel):
    """Parent order definition contract."""
    id: str = Field(..., description="Unique order identifier")
    symbol: str = Field(..., min_length=1, description="Instrument ticker / identifier")
    side: OrderSide = Field(..., description="Order side (BUY or SELL)")
    quantity: float = Field(..., gt=0.0, description="Total parent order quantity")
    start_time: datetime = Field(..., description="Execution start timestamp")
    end_time: datetime = Field(..., description="Execution deadline timestamp")

    @model_validator(mode="after")
    def validate_horizon(self) -> "Order":
        if self.end_time <= self.start_time:
            raise ValueError(f"end_time ({self.end_time}) must be strictly after start_time ({self.start_time})")
        return self


class MarketState(BaseModel):
    """Per-interval market observation contract."""
    timestamp: datetime = Field(..., description="Market state observation timestamp")
    price: float = Field(..., gt=0.0, description="Current reference or mid price")
    bid: float = Field(..., gt=0.0, description="Current best bid price")
    ask: float = Field(..., gt=0.0, description="Current best ask price")
    volume: float = Field(..., ge=0.0, description="Observable market volume for interval")
    liquidity: float = Field(..., ge=0.0, description="Normalised liquidity indicator (0.0=illiquid, 1.0=normal, >1.0=deep)")
    volatility: float = Field(..., ge=0.0, description="Current volatility indicator (e.g. annualized or per-interval sigma)")
    transaction_cost: float = Field(0.0, ge=0.0, description="Direct transaction cost estimate per unit or fee rate")

    @model_validator(mode="after")
    def validate_quotes(self) -> "MarketState":
        if self.ask < self.bid:
            raise ValueError(f"Inverted spread: ask ({self.ask}) cannot be less than bid ({self.bid})")
        return self

    @property
    def mid_price(self) -> float:
        """Computed mid price: (bid + ask) / 2."""
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        """Absolute spread: ask - bid."""
        return self.ask - self.bid

    @property
    def spread_bps(self) -> float:
        """Spread in basis points relative to mid price."""
        mid = self.mid_price
        if mid <= 0:
            return 0.0
        return (self.spread / mid) * 10_000.0


class ExecutionConfig(BaseModel):
    """Configuration parameters for execution strategies and risk limits."""
    interval_seconds: float = Field(60.0, gt=0.0, description="Duration of each decision interval in seconds")
    total_intervals: Optional[int] = Field(None, gt=0, description="Total number of intervals in the horizon, if pre-discretized")
    max_participation: float = Field(0.15, gt=0.0, le=1.0, description="Maximum participation rate of interval market volume (e.g. 0.15 = 15%)")
    max_single_child_pct: float = Field(0.25, gt=0.0, le=1.0, description="Maximum single child order size as a fraction of parent quantity")
    spread_threshold_bps: float = Field(20.0, ge=0.0, description="Spread threshold in basis points above which throttling occurs")
    volatility_threshold: float = Field(0.02, ge=0.0, description="Volatility threshold above which risk regime triggers")
    liquidity_threshold: float = Field(0.5, ge=0.0, description="Liquidity indicator below which liquidity stress triggers")
    impact_coefficient: float = Field(0.5, ge=0.0, description="Coefficient for quadratic market impact penalty")
    emergency_deadline_buffer_steps: int = Field(2, ge=1, description="Number of steps before deadline when emergency completion mode activates")
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "cost": 1.0,
            "impact": 1.0,
            "urgency": 1.0,
            "risk": 1.0,
        },
        description="Weights for multi-objective candidate scoring"
    )


class ExecutionState(BaseModel):
    """Dynamic tracking of execution progress and cumulative statistics."""
    remaining_quantity: float = Field(..., ge=0.0, description="Unfilled parent order quantity")
    executed_quantity: float = Field(0.0, ge=0.0, description="Cumulative filled child quantity")
    cumulative_cost: float = Field(0.0, description="Cumulative total cash spent (BUY) or received (SELL)")
    benchmark_price: float = Field(..., gt=0.0, description="Decision arrival reference price")
    current_step: int = Field(0, ge=0, description="Current interval step index (0-based)")
    total_steps: int = Field(0, ge=0, description="Total planned steps in the horizon")

    @property
    def is_completed(self) -> bool:
        """True if parent order is completely filled within epsilon."""
        return self.remaining_quantity <= 1e-7

    @property
    def average_execution_price(self) -> float:
        """Weighted average execution price across all executed slices."""
        if self.executed_quantity <= 0:
            return 0.0
        return self.cumulative_cost / self.executed_quantity

    @property
    def completion_rate(self) -> float:
        """Fraction of parent order completed (0.0 to 1.0)."""
        total = self.remaining_quantity + self.executed_quantity
        if total <= 0:
            return 1.0
        return self.executed_quantity / total


class ExecutionDecision(BaseModel):
    """Output decision generated by a strategy for a single interval."""
    timestamp: datetime = Field(..., description="Decision timestamp")
    quantity: float = Field(..., ge=0.0, description="Target child order quantity to execute in this interval")
    target_participation: float = Field(0.0, ge=0.0, le=1.0, description="Desired participation rate relative to market volume")
    expected_cost: float = Field(0.0, description="Estimated total execution cost for this slice")
    risk_score: float = Field(0.0, ge=0.0, le=1.0, description="Normalised risk/exposure indicator (0.0=safe, 1.0=extreme)")
    urgency_score: float = Field(0.0, ge=0.0, le=1.0, description="Normalised urgency score based on deadline and completion gap")
    reason_code: str = Field(..., description="Machine-readable reason code from ReasonCode enum or custom string")
    reason_text: str = Field(..., description="Human-readable explanation of why this quantity was chosen")
    constraints_hit: List[str] = Field(default_factory=list, description="List of constraints that bounded or altered the proposed quantity")
