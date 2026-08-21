"""Adaptive Multi-Regime Algorithmic Execution Strategy.

Implements constrained candidate-set optimization across market regimes,
balancing cost, market impact, urgency, and volatility risk with explainable reasoning.
"""

from typing import List
from execution_engine.core.models import (
    Order,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    ExecutionDecision,
    RegimeType,
    ReasonCode,
)
from execution_engine.core.features import FeatureExtractor, MarketFeatures
from execution_engine.core.regimes import RegimeDetector, RegimeClassification
from execution_engine.core.objectives import ObjectiveScorer, CandidateScore
from execution_engine.risk.controller import RiskController
from execution_engine.strategies.base import StrategyBase


class AdaptiveStrategy(StrategyBase):
    """Adaptive Execution Strategy.

    Dynamically adapts child order sizing in response to:
    - Volatility spikes (throttles size to avoid adverse price movement)
    - Liquidity deteriorations (reduces participation to minimize market impact)
    - Spread widening (waits or reduces child slice)
    - Approaching deadlines (gradually escalates urgency without erratic surges)
    - Observable market volume (participates deeper when liquidity is favorable)
    """

    @property
    def name(self) -> str:
        return "ADAPTIVE"

    def decide(
        self,
        order: Order,
        state: ExecutionState,
        market_state: MarketState,
        config: ExecutionConfig,
    ) -> ExecutionDecision:
        # 1. Feature Extraction & Regime Detection
        features: MarketFeatures = FeatureExtractor.extract_features(
            order=order,
            state=state,
            market_state=market_state,
            config=config,
        )
        regime_info: RegimeClassification = RegimeDetector.classify(
            market_state=market_state,
            features=features,
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

        # 2. Compute Baseline & Target Schedule Quantities
        remaining_steps = max(1, features.remaining_steps)
        q_baseline = state.remaining_quantity / float(remaining_steps)

        # In emergency deadline buffer, prioritize order completion
        is_deadline_emergency = remaining_steps <= config.emergency_deadline_buffer_steps

        # 3. Decision Determination
        if remaining_steps <= 1:
            # Final interval completion feasibility rule (PRD Sec 10 & 16)
            selected_qty = state.remaining_quantity
        else:
            # Compute feasible upper bound for intermediate steps
            max_single_child = order.quantity * config.max_single_child_pct
            if is_deadline_emergency:
                q_max = state.remaining_quantity
                q_target = state.remaining_quantity
                raw_candidates = [
                    q_baseline,
                    state.remaining_quantity * 0.5,
                    state.remaining_quantity * 0.75,
                    state.remaining_quantity,
                ]
            else:
                q_max = min(state.remaining_quantity, features.participation_capacity, max_single_child)
                urgency_factor = max(0.5, min(2.5, features.urgency_ratio))
                q_target = q_baseline * regime_info.risk_multiplier * urgency_factor
                raw_candidates = [
                    0.0,
                    0.25 * q_target,
                    0.50 * q_target,
                    0.75 * q_target,
                    1.00 * q_target,
                    1.25 * q_target,
                    1.50 * q_target,
                    q_baseline,
                    q_max,
                ]

            # Filter, clamp to [0, q_max], and remove duplicates
            candidate_set: List[float] = []
            seen = set()
            for c in raw_candidates:
                clamped = max(0.0, min(c, q_max))
                rounded = round(clamped, 4)
                if rounded not in seen:
                    seen.add(rounded)
                    candidate_set.append(clamped)

            if not candidate_set:
                candidate_set = [0.0]

            # Multi-Objective Scoring
            best_score: CandidateScore | None = None
            for candidate_qty in candidate_set:
                score = ObjectiveScorer.score_candidate(
                    candidate_qty=candidate_qty,
                    target_schedule_qty=q_target if not is_deadline_emergency else state.remaining_quantity,
                    order=order,
                    state=state,
                    market_state=market_state,
                    features=features,
                    regime_info=regime_info,
                    config=config,
                )
                if best_score is None or score.total_score < best_score.total_score:
                    best_score = score

            selected_qty = best_score.quantity if best_score else 0.0

        # 4. Independent Risk Sanitization
        risk_result = RiskController.validate_and_sanitize(
            proposed_quantity=selected_qty,
            order=order,
            state=state,
            market_state=market_state,
            features=features,
            config=config,
        )

        final_qty = risk_result.sanitized_quantity
        part_rate = (final_qty / market_state.volume) if market_state.volume > 0 else 0.0
        expected_cost = final_qty * market_state.mid_price * (1.0 + market_state.transaction_cost)

        # 5. Generate Machine-Readable Reason Code & Explainability Rationale
        if risk_result.reason_code_override:
            reason_code = risk_result.reason_code_override
            reason_text = risk_result.reason_text_override or "Risk controller constraint applied."
        elif is_deadline_emergency:
            reason_code = ReasonCode.DEADLINE_EMERGENCY.value
            reason_text = f"Deadline emergency mode active ({remaining_steps} steps left). Executing {final_qty:.2f} units to ensure complete fill."
        elif regime_info.regime == RegimeType.STRESSED:
            reason_code = ReasonCode.HIGH_VOLATILITY_THROTTLE.value
            reason_text = (
                f"Compound stress detected (volatility {market_state.volatility:.4f}, liquidity {market_state.liquidity:.2f}). "
                f"Throttled execution to {final_qty:.2f} units to mitigate adverse impact."
            )
        elif regime_info.regime == RegimeType.HIGH_VOLATILITY:
            reason_code = ReasonCode.HIGH_VOLATILITY_THROTTLE.value
            reason_text = (
                f"High market volatility ({market_state.volatility:.4f} >= {config.volatility_threshold:.4f}). "
                f"Reduced slice to {final_qty:.2f} units."
            )
        elif regime_info.regime == RegimeType.LOW_LIQUIDITY:
            reason_code = ReasonCode.LOW_LIQUIDITY_THROTTLE.value
            reason_text = (
                f"Low market liquidity ({market_state.liquidity:.2f} <= {config.liquidity_threshold:.2f}). "
                f"Restricted participation to {final_qty:.2f} units to prevent price depression/surge."
            )
        elif regime_info.regime == RegimeType.HIGH_SPREAD:
            reason_code = ReasonCode.WIDE_SPREAD_THROTTLE.value
            reason_text = (
                f"Elevated spread ({features.spread_bps:.1f} bps >= {config.spread_threshold_bps:.1f} bps). "
                f"Reduced execution size to {final_qty:.2f} units."
            )
        elif features.urgency_ratio > 1.2:
            reason_code = ReasonCode.ADAPTIVE_OPTIMAL.value
            reason_text = (
                f"Urgency elevated (ratio {features.urgency_ratio:.2f}). "
                f"Accelerated execution pace to {final_qty:.2f} units."
            )
        else:
            reason_code = ReasonCode.ADAPTIVE_OPTIMAL.value
            reason_text = (
                f"Optimal multi-objective child order of {final_qty:.2f} units under {regime_info.regime.value} regime."
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
