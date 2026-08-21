"""Volume-Aware baseline execution strategy.
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


class VolumeAwareStrategy(StrategyBase):
    """Volume-Aware baseline strategy.

    Scales execution slice size dynamically with observable interval volume:
    allocates more quantity to high-volume intervals and less to low-volume intervals,
    bounded by the max participation rate.
    """

    @property
    def name(self) -> str:
        return "VOLUME_AWARE"

    def decide(
        self,
        order: Order,
        state: ExecutionState,
        market_state: MarketState,
        config: ExecutionConfig,
    ) -> ExecutionDecision:
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

        # Baseline volume participation rate adjusted for schedule progress
        target_participation = min(config.max_participation, config.max_participation * max(0.5, features.urgency_ratio))
        raw_target_qty = market_state.volume * target_participation

        # Pass through risk controller
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

        reason_code = risk_result.reason_code_override or ReasonCode.NORMAL_VOLUME_AWARE.value
        reason_text = risk_result.reason_text_override or (
            f"Volume-aware allocation of {final_qty:.2f} units ({part_rate*100:.1f}% of volume {market_state.volume:.0f})."
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
