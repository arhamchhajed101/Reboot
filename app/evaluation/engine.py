import numpy as np
from typing import List
from app.models.domain import (
    ExecutionDecision,
    FillEvent,
    MarketState,
    Order,
    OrderSide,
    RunMetrics,
)


class EvaluationEngine:
    """
    Evaluates trade execution performance metrics.

    FINANCIAL FORMULAS & ASSUMPTIONS:
    --------------------------------
    1. Completion Percentage (%):
       Completion % = (Total Filled Quantity / Order Quantity) * 100

    2. Volume-Weighted Average Price (VWAP):
       VWAP = Sum(Fill Price_i * Filled Quantity_i) / Total Filled Quantity

    3. Costs Breakdown ($ and BPS relative to Arrival Price):
       Cost (bps) = (Cost ($) / (Total Quantity * Arrival Mid Price)) * 10,000

    4. Implementation Shortfall (IS):
       Measures execution slippage and opportunity cost against instant fill at arrival mid price.
       - BUY Order:
         IS ($) = Sum(Fill Price_i * Q_i) + Unfilled Q * Final Mid Price - (Order Q * Arrival Mid Price)
       - SELL Order:
         IS ($) = (Order Q * Arrival Mid Price) - [Sum(Fill Price_i * Q_i) + Unfilled Q * Final Mid Price]
       IS (bps) = (IS ($) / (Order Q * Arrival Mid Price)) * 10,000

    5. Max Participation Rate (%):
       Peak order volume consumption as a fraction of market tick volume.

    6. Risk Score (0.0 to 1.0 proxy):
       Normalized volatility exposure over execution horizon.

    7. Stability Score (0.0 to 1.0 proxy):
       Measures pace consistency (1.0 - std(participation_rates)). Higher means smoother execution.
    """

    @staticmethod
    def evaluate_run(
        run_id: str,
        strategy_name: str,
        order: Order,
        market_ticks: List[MarketState],
        decisions: List[ExecutionDecision],
        fills: List[FillEvent],
    ) -> RunMetrics:
        if not market_ticks:
            raise ValueError("Cannot evaluate run with empty market ticks")

        arrival_price = market_ticks[0].mid_price
        final_price = market_ticks[-1].mid_price
        order_notional = order.quantity * arrival_price

        total_filled = sum(f.filled_quantity for f in fills)
        completion_pct = (total_filled / order.quantity) * 100.0 if order.quantity > 0 else 0.0

        if total_filled > 0:
            vwap_fill_price = sum(f.fill_price * f.filled_quantity for f in fills) / total_filled
        else:
            vwap_fill_price = arrival_price

        total_spread_cost = sum(f.spread_cost for f in fills)
        total_impact_cost = sum(f.impact_cost for f in fills)
        total_transaction_cost = sum(f.transaction_cost for f in fills)

        total_execution_cost = total_spread_cost + total_impact_cost + total_transaction_cost

        # Calculate BPS values
        spread_bps = (total_spread_cost / order_notional) * 10000.0 if order_notional > 0 else 0.0
        impact_bps = (total_impact_cost / order_notional) * 10000.0 if order_notional > 0 else 0.0
        trans_bps = (total_transaction_cost / order_notional) * 10000.0 if order_notional > 0 else 0.0
        total_cost_bps = (total_execution_cost / order_notional) * 10000.0 if order_notional > 0 else 0.0

        # Implementation Shortfall Calculation
        unfilled_qty = max(order.quantity - total_filled, 0.0)
        filled_notional = sum(f.fill_price * f.filled_quantity for f in fills)
        unfilled_notional = unfilled_qty * final_price

        if order.side == OrderSide.BUY:
            implementation_shortfall = (filled_notional + unfilled_notional) - order_notional
        else:  # SELL
            implementation_shortfall = order_notional - (filled_notional + unfilled_notional)

        is_bps = (implementation_shortfall / order_notional) * 10000.0 if order_notional > 0 else 0.0

        # Max participation rate & stability
        participation_rates = [d.participation_rate for d in decisions] if decisions else [0.0]
        max_participation = max(participation_rates) if participation_rates else 0.0

        if len(participation_rates) > 1:
            part_std = float(np.std(participation_rates))
            stability_score = max(0.0, min(1.0, 1.0 - (part_std * 2.0)))
        else:
            stability_score = 1.0

        # Risk score calculation based on price standard deviation during execution
        prices = [t.mid_price for t in market_ticks]
        if len(prices) > 1:
            price_std = float(np.std(prices))
            risk_score = max(0.0, min(1.0, (price_std / arrival_price) * 10.0))
        else:
            risk_score = 0.1

        return RunMetrics(
            run_id=run_id,
            strategy=strategy_name,
            order_side=order.side,
            total_quantity=round(order.quantity, 4),
            filled_quantity=round(total_filled, 4),
            completion_percentage=round(completion_pct, 2),
            arrival_price=round(arrival_price, 4),
            vwap_fill_price=round(vwap_fill_price, 4),
            final_price=round(final_price, 4),
            total_execution_cost=round(total_execution_cost, 4),
            total_execution_cost_bps=round(total_cost_bps, 2),
            spread_cost=round(total_spread_cost, 4),
            spread_cost_bps=round(spread_bps, 2),
            impact_cost=round(total_impact_cost, 4),
            impact_cost_bps=round(impact_bps, 2),
            transaction_cost=round(total_transaction_cost, 4),
            transaction_cost_bps=round(trans_bps, 2),
            implementation_shortfall=round(implementation_shortfall, 4),
            implementation_shortfall_bps=round(is_bps, 2),
            max_participation_rate=round(max_participation, 4),
            risk_score=round(risk_score, 4),
            stability_score=round(stability_score, 4),
        )
