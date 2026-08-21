"""Feature engineering module for the RECURZ Execution Engine.

Extracts normalized indicators for spread, participation capacity,
urgency, liquidity score, and market activity.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from execution_engine.core.models import Order, MarketState, ExecutionConfig, ExecutionState


class MarketFeatures(BaseModel):
    """Structured container of calculated market and execution features."""
    mid_price: float = Field(..., description="Current reference mid-price: (bid + ask) / 2")
    spread_bps: float = Field(..., description="Spread in basis points: ((ask - bid) / mid) * 10,000")
    participation_capacity: float = Field(..., description="Maximum allowable child quantity for interval: volume * max_participation")
    urgency_ratio: float = Field(..., description="Ratio of current remaining pace required vs initial baseline pace")
    normalized_urgency: float = Field(..., description="Normalised urgency index in [0, 1] for penalty calculations")
    liquidity_score: float = Field(..., description="Observed normalized liquidity indicator")
    volatility_ratio: float = Field(..., description="Observed volatility relative to configured threshold")
    remaining_steps: int = Field(..., description="Estimated or discrete steps remaining in horizon")
    time_remaining_seconds: float = Field(..., description="Remaining seconds until order deadline")


class FeatureExtractor:
    """Calculates features from current Order, MarketState, ExecutionState, and ExecutionConfig."""

    @staticmethod
    def extract_features(
        order: Order,
        state: ExecutionState,
        market_state: MarketState,
        config: ExecutionConfig,
        current_time: Optional[datetime] = None,
    ) -> MarketFeatures:
        """Extract all mathematical features for strategy evaluation.

        Formulas:
        - mid_price = (bid + ask) / 2.0
        - spread_bps = ((ask - bid) / mid_price) * 10,000
        - participation_capacity = volume * max_participation
        - time_remaining_seconds = max(0.0, (order.end_time - current_time).total_seconds())
        - remaining_steps = max(1, state.total_steps - state.current_step) (or time_remaining / interval)
        - urgency_ratio = (remaining_quantity / remaining_steps) / (parent_quantity / total_steps)
        """
        # 1. Mid price and spread in bps
        mid = (market_state.bid + market_state.ask) / 2.0
        spread = market_state.ask - market_state.bid
        spread_bps = (spread / mid * 10_000.0) if mid > 0 else 0.0

        # 2. Participation capacity
        participation_cap = market_state.volume * config.max_participation

        # 3. Time and step horizon calculation
        now = current_time or market_state.timestamp
        time_rem = max(0.0, (order.end_time - now).total_seconds())

        if state.total_steps > 0:
            remaining_steps = max(1, state.total_steps - state.current_step)
            total_steps = state.total_steps
        else:
            # Derive discrete steps from time if total_steps was not explicitly initialized
            est_steps = int(time_rem // config.interval_seconds) + 1
            remaining_steps = max(1, est_steps)
            total_steps = max(1, int((order.end_time - order.start_time).total_seconds() // config.interval_seconds))

        # 4. Urgency ratio
        # Baseline per-step quantity
        base_step_qty = order.quantity / float(total_steps)
        # Required per-step quantity to finish on time
        current_req_qty = state.remaining_quantity / float(remaining_steps)

        if base_step_qty > 0:
            urgency_ratio = current_req_qty / base_step_qty
        else:
            urgency_ratio = 1.0

        # Normalised urgency index in [0.0, 1.0] (clamped for risk scoring)
        # 0.0 means ahead of schedule / 0 remaining, 1.0 means critical urgency (1 step left with high remainder)
        urgency_progress = 1.0 - (remaining_steps / float(max(1, total_steps)))
        fraction_remaining = state.remaining_quantity / float(order.quantity) if order.quantity > 0 else 0.0
        normalized_urgency = min(1.0, max(0.0, fraction_remaining * (1.0 + urgency_progress)))

        # 5. Volatility ratio relative to threshold
        vol_ratio = (market_state.volatility / config.volatility_threshold) if config.volatility_threshold > 0 else 1.0

        return MarketFeatures(
            mid_price=mid,
            spread_bps=spread_bps,
            participation_capacity=max(0.0, participation_cap),
            urgency_ratio=urgency_ratio,
            normalized_urgency=normalized_urgency,
            liquidity_score=market_state.liquidity,
            volatility_ratio=vol_ratio,
            remaining_steps=remaining_steps,
            time_remaining_seconds=time_rem,
        )
