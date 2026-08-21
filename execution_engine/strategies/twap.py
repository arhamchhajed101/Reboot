"""Time-Weighted Average Price (TWAP) baseline execution strategy.
"""

from datetime import datetime
from execution_engine.core.models import (
    Order,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    ExecutionDecision,
    ReasonCode,
)
from execution_engine.core.features import FeatureExtractor
from execution_engine.risk.controller import RiskController
from execution_engine.strategies.base import StrategyBase


class TWAPStrategy(StrategyBase):
    """Uniform Time-Weighted Average Price strategy baseline.

    Distributes remaining parent order quantity evenly over remaining intervals:
    proposed_quantity = remaining_quantity / remaining_steps
    """

    @property
    def name(self) -> str:
        return "TWAP"

    def decide(
        self,
        order: Order,
        state: ExecutionState,
        market_state: MarketState,
        config: ExecutionConfig,
    ) -> ExecutionDecision:
        # Extract features
        features = FeatureExtractor.extract_features(
            order=order,
            state=state,
            market_state=market_state,
            config=config,
        )

        if state.is_completed:
            return ExecutionDecision(
                timestamp=market_state.timestamp,
                quantity=0.0,
                target_participation=0.0,
                expected_cost=0.0,
                risk_score=0.0,
                urgency_score=0.0,
                reason_code=ReasonCode.ORDER_COMPLETED.value,
                reason_text="Parent order already completed.",
                constraints_hit=[],
            )

        # Uniform slice based on remaining steps
        remaining_steps = max(1, features.remaining_steps)
        raw_target_qty = state.remaining_quantity / float(remaining_steps)

        # Validate through independent risk controller
        risk_result = RiskController.validate_and_sanitize(
            proposed_quantity=raw_target_qty,
            order=order,
            state=state,
            market_state=market_state,
            features=features,
            config=config,
        )

        final_qty = risk_result.sanitized_quantity
        part_rate = (final_qty / market_state.volume) if market_state.volume > 0 else 0.0
        expected_cost = final_qty * market_state.mid_price * (1.0 + market_state.transaction_cost)

        reason_code = risk_result.reason_code_override or ReasonCode.NORMAL_TWAP.value
        reason_text = risk_result.reason_text_override or (
            f"TWAP uniform allocation of {final_qty:.2f} units over {remaining_steps} remaining intervals."
        )

        return ExecutionDecision(
            timestamp=market_state.timestamp,
            quantity=final_qty,
            target_participation=min(1.0, part_rate),
            expected_cost=expected_cost,
            risk_score=risk_result.risk_score,
            urgency_score=features.normalized_urgency,
            reason_code=reason_code,
            reason_text=reason_text,
            constraints_hit=risk_result.constraints_hit,
        )
