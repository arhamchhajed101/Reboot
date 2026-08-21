"""Objective scoring and market impact modeling for candidate execution evaluation.

Implements the multi-objective optimization function:
Score = w_cost * DirectCost + w_impact * MarketImpact + w_urgency * UrgencyPenalty + w_risk * RiskPenalty
"""

from pydantic import BaseModel, Field

from execution_engine.core.models import Order, MarketState, ExecutionConfig, ExecutionState
from execution_engine.core.features import MarketFeatures
from execution_engine.core.regimes import RegimeClassification


class CandidateScore(BaseModel):
    """Decomposed objective score for a candidate child order quantity."""
    quantity: float
    total_score: float
    cost_component: float
    impact_component: float
    urgency_penalty: float
    risk_penalty: float


class ObjectiveScorer:
    """Evaluates execution candidate quantities against the multi-objective function."""

    @staticmethod
    def calculate_impact_penalty(
        quantity: float,
        market_state: MarketState,
        config: ExecutionConfig,
    ) -> float:
        """Calibrated prototype quadratic market impact model.

        Formula (Tech Stack Sec 9):
        impact = impact_coeff * mid_price * quantity * (quantity / max(volume, eps))^2 * liquidity_penalty_factor
        where liquidity_penalty_factor = max(1.0, 1.0 / max(liquidity, 0.01))
        """
        if quantity <= 0.0:
            return 0.0

        vol = max(market_state.volume, 1.0)
        participation = quantity / vol
        liquidity_penalty = max(1.0, 1.0 / max(market_state.liquidity, 0.01))

        # Quadratic penalty in participation rate scaled by nominal order value
        impact = (
            config.impact_coefficient
            * market_state.mid_price
            * quantity
            * (participation ** 2)
            * liquidity_penalty
        )
        return impact

    @staticmethod
    def score_candidate(
        candidate_qty: float,
        target_schedule_qty: float,
        order: Order,
        state: ExecutionState,
        market_state: MarketState,
        features: MarketFeatures,
        regime_info: RegimeClassification,
        config: ExecutionConfig,
    ) -> CandidateScore:
        """Score a single candidate quantity using the weighted objective function."""
        q = max(0.0, candidate_qty)
        mid = market_state.mid_price
        weights = config.weights

        w_cost = weights.get("cost", 1.0)
        w_impact = weights.get("impact", 1.0)
        w_urgency = weights.get("urgency", 1.0)
        w_risk = weights.get("risk", 1.0)

        # 1. Direct Execution & Spread Cost
        half_spread_rate = (features.spread_bps / 20_000.0)
        direct_cost = q * mid * (half_spread_rate + market_state.transaction_cost)

        # 2. Market Impact Penalty
        impact_cost = ObjectiveScorer.calculate_impact_penalty(q, market_state, config)

        # 3. Urgency & Inventory Exposure Penalty
        # Penalizes unexecuted inventory remaining and under-executing vs schedule
        unexecuted_inventory = max(0.0, state.remaining_quantity - q)
        under_target = max(0.0, target_schedule_qty - q)
        
        # As deadline nears or urgency ratio rises, cost of delaying execution increases exponentially
        urgency_penalty = (
            (unexecuted_inventory * mid * market_state.volatility * (features.urgency_ratio ** 1.5) * 0.1)
            + (under_target * mid * 0.001 * (features.urgency_ratio ** 2.0))
        )

        # 4. Immediate Regime Friction Penalty
        # Penalizes trading large sizes into high spread / stressed market conditions right now
        stress_mult = 2.5 if regime_info.is_stressed else 1.0
        excess_spread = max(0.0, (features.spread_bps - config.spread_threshold_bps) / 10_000.0)
        adverse_friction = (market_state.volatility * stress_mult * 0.05) + excess_spread
        risk_penalty = q * mid * adverse_friction

        total_score = (
            (w_cost * direct_cost)
            + (w_impact * impact_cost)
            + (w_urgency * urgency_penalty)
            + (w_risk * risk_penalty)
        )

        return CandidateScore(
            quantity=q,
            total_score=total_score,
            cost_component=direct_cost,
            impact_component=impact_cost,
            urgency_penalty=urgency_penalty,
            risk_penalty=risk_penalty,
        )
