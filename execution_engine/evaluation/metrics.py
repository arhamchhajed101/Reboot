"""Evaluation metrics for algorithmic trade execution.

Computes completion rate, implementation shortfall (bps and absolute),
average slippage, market impact proxy, risk scores, and decision stability.
"""

from typing import List
import numpy as np
from pydantic import BaseModel, Field

from execution_engine.core.models import Order, OrderSide, ExecutionState, ExecutionDecision, MarketState


class StrategyMetrics(BaseModel):
    """Comprehensive performance metrics for a single execution run."""
    strategy_name: str
    completion_rate: float = Field(..., description="Executed quantity / Parent quantity (0.0 to 1.0)")
    parent_quantity: float
    executed_quantity: float
    remaining_quantity: float
    deadline_adhered: bool
    benchmark_arrival_price: float
    average_execution_price: float
    implementation_shortfall_bps: float = Field(..., description="Implementation shortfall in basis points vs arrival price")
    implementation_shortfall_usd: float = Field(..., description="Dollar cost vs arrival benchmark: total spent - (parent_qty * arrival_price)")
    total_market_impact_usd: float
    total_transaction_fees_usd: float
    average_slippage_bps: float
    average_risk_score: float
    max_risk_score: float
    decision_stability_variance: float = Field(..., description="Variance of participation rates across executed intervals")


class MetricsCalculator:
    """Computes standard institutional execution metrics."""

    @staticmethod
    def compute(
        order: Order,
        initial_state: ExecutionState,
        final_state: ExecutionState,
        decisions: List[ExecutionDecision],
        market_states: List[MarketState],
        fill_prices: List[float],
        fill_quantities: List[float],
        impact_costs: List[float],
        fees: List[float],
        strategy_name: str,
    ) -> StrategyMetrics:
        """Calculate end-to-end execution metrics for a simulated run."""
        parent_qty = order.quantity
        exec_qty = sum(fill_quantities)
        rem_qty = max(0.0, parent_qty - exec_qty)
        completion_rate = min(1.0, exec_qty / parent_qty) if parent_qty > 0 else 1.0
        deadline_adhered = (rem_qty <= 1e-5)

        arrival_price = initial_state.benchmark_price

        # Weighted average execution price
        if exec_qty > 0:
            total_cash = sum(p * q for p, q in zip(fill_prices, fill_quantities))
            avg_exec_price = total_cash / exec_qty
        else:
            avg_exec_price = arrival_price

        # Implementation Shortfall (IS)
        # For BUY: (avg_price - arrival_price) / arrival_price
        # For SELL: (arrival_price - avg_price) / arrival_price
        if order.side == OrderSide.BUY:
            is_ratio = (avg_exec_price - arrival_price) / arrival_price if arrival_price > 0 else 0.0
            is_usd = (avg_exec_price * exec_qty) - (arrival_price * exec_qty)
        else:
            is_ratio = (arrival_price - avg_exec_price) / arrival_price if arrival_price > 0 else 0.0
            is_usd = (arrival_price * exec_qty) - (avg_exec_price * exec_qty)

        is_bps = is_ratio * 10_000.0

        # Slippage vs interval mid-price
        slippage_bps_list = []
        for p_fill, q_fill, m_state in zip(fill_prices, fill_quantities, market_states):
            if q_fill > 0 and m_state.mid_price > 0:
                if order.side == OrderSide.BUY:
                    slip = (p_fill - m_state.mid_price) / m_state.mid_price
                else:
                    slip = (m_state.mid_price - p_fill) / m_state.mid_price
                slippage_bps_list.append(slip * 10_000.0)

        avg_slippage = float(np.mean(slippage_bps_list)) if slippage_bps_list else 0.0

        # Total market impact and fees
        total_impact = sum(impact_costs)
        total_fees = sum(fees)

        # Risk scores
        risk_scores = [d.risk_score for d in decisions]
        avg_risk = float(np.mean(risk_scores)) if risk_scores else 0.0
        max_risk = float(np.max(risk_scores)) if risk_scores else 0.0

        # Participation stability variance
        participations = [d.target_participation for d in decisions]
        participation_var = float(np.var(participations)) if participations else 0.0

        return StrategyMetrics(
            strategy_name=strategy_name,
            completion_rate=completion_rate,
            parent_quantity=parent_qty,
            executed_quantity=exec_qty,
            remaining_quantity=rem_qty,
            deadline_adhered=deadline_adhered,
            benchmark_arrival_price=arrival_price,
            average_execution_price=avg_exec_price,
            implementation_shortfall_bps=is_bps,
            implementation_shortfall_usd=is_usd,
            total_market_impact_usd=total_impact,
            total_transaction_fees_usd=total_fees,
            average_slippage_bps=avg_slippage,
            average_risk_score=avg_risk,
            max_risk_score=max_risk,
            decision_stability_variance=participation_var,
        )
