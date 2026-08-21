"""Comparative benchmarking runner across execution strategies on identical scenarios.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field

from execution_engine.core.models import (
    Order,
    OrderSide,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    ExecutionDecision,
)
from execution_engine.strategies.base import StrategyBase
from execution_engine.evaluation.metrics import StrategyMetrics, MetricsCalculator


class BenchmarkStepRecord(BaseModel):
    """Detailed execution event for a single interval in a benchmark run."""
    step: int
    timestamp: str
    decision_quantity: float
    fill_quantity: float
    fill_price: float
    mid_price: float
    spread_bps: float
    market_volume: float
    liquidity: float
    volatility: float
    reason_code: str
    reason_text: str
    constraints_hit: List[str]
    remaining_quantity: float
    cumulative_cost: float


class StrategyRunResult(BaseModel):
    """Complete run result for one strategy."""
    strategy_name: str
    metrics: StrategyMetrics
    trajectory: List[BenchmarkStepRecord]


class BenchmarkReport(BaseModel):
    """Comparative benchmark report across multiple strategies on the same market scenario."""
    scenario_name: str
    order_id: str
    order_symbol: str
    order_side: str
    order_quantity: float
    num_intervals: int
    strategy_results: Dict[str, StrategyRunResult]
    summary_comparison: List[Dict[str, Any]]


class BenchmarkRunner:
    """Runs comparative execution simulations across multiple strategies under identical conditions."""

    @staticmethod
    def simulate_strategy(
        order: Order,
        market_states: List[MarketState],
        strategy: StrategyBase,
        config: ExecutionConfig,
    ) -> StrategyRunResult:
        """Simulate one strategy over the provided sequence of market states."""
        total_steps = len(market_states)
        initial_price = market_states[0].mid_price if market_states else 100.0

        current_state = ExecutionState(
            remaining_quantity=order.quantity,
            executed_quantity=0.0,
            cumulative_cost=0.0,
            benchmark_price=initial_price,
            current_step=0,
            total_steps=total_steps,
        )
        initial_state = current_state.model_copy()

        decisions: List[ExecutionDecision] = []
        fill_prices: List[float] = []
        fill_quantities: List[float] = []
        impact_costs: List[float] = []
        fees: List[float] = []
        trajectory: List[BenchmarkStepRecord] = []

        for step_idx, m_state in enumerate(market_states):
            current_state.current_step = step_idx

            # 1. Strategy Decision
            decision = strategy.decide(
                order=order,
                state=current_state,
                market_state=m_state,
                config=config,
            )
            decisions.append(decision)

            q_fill = decision.quantity

            # 2. Realistic Fill Pricing (Mid + Half-Spread + Market Impact)
            half_spread = m_state.spread * 0.5
            vol = max(m_state.volume, 1.0)
            part_rate = q_fill / vol
            liq_factor = max(1.0, 1.0 / max(m_state.liquidity, 0.01))

            # Impact on execution price per share
            price_impact = (
                m_state.mid_price
                * config.impact_coefficient
                * (part_rate ** 2)
                * liq_factor
            )
            impact_cost_dollars = q_fill * price_impact

            if order.side == OrderSide.BUY:
                fill_price = m_state.mid_price + half_spread + price_impact
            else:
                fill_price = max(0.01, m_state.mid_price - half_spread - price_impact)

            fee_dollars = q_fill * fill_price * m_state.transaction_cost
            slice_total_cost = (q_fill * fill_price) + fee_dollars

            fill_prices.append(fill_price)
            fill_quantities.append(q_fill)
            impact_costs.append(impact_cost_dollars)
            fees.append(fee_dollars)

            # 3. Update State
            new_remaining = max(0.0, current_state.remaining_quantity - q_fill)
            new_executed = current_state.executed_quantity + q_fill
            new_cum_cost = current_state.cumulative_cost + slice_total_cost

            current_state = ExecutionState(
                remaining_quantity=new_remaining,
                executed_quantity=new_executed,
                cumulative_cost=new_cum_cost,
                benchmark_price=initial_price,
                current_step=step_idx + 1,
                total_steps=total_steps,
            )

            # 4. Record Trajectory Step
            trajectory.append(
                BenchmarkStepRecord(
                    step=step_idx,
                    timestamp=m_state.timestamp.isoformat(),
                    decision_quantity=decision.quantity,
                    fill_quantity=q_fill,
                    fill_price=fill_price,
                    mid_price=m_state.mid_price,
                    spread_bps=m_state.spread_bps,
                    market_volume=m_state.volume,
                    liquidity=m_state.liquidity,
                    volatility=m_state.volatility,
                    reason_code=decision.reason_code,
                    reason_text=decision.reason_text,
                    constraints_hit=decision.constraints_hit,
                    remaining_quantity=new_remaining,
                    cumulative_cost=new_cum_cost,
                )
            )

        # 5. Calculate Metrics
        metrics = MetricsCalculator.compute(
            order=order,
            initial_state=initial_state,
            final_state=current_state,
            decisions=decisions,
            market_states=market_states,
            fill_prices=fill_prices,
            fill_quantities=fill_quantities,
            impact_costs=impact_costs,
            fees=fees,
            strategy_name=strategy.name,
        )

        return StrategyRunResult(
            strategy_name=strategy.name,
            metrics=metrics,
            trajectory=trajectory,
        )

    @staticmethod
    def run_benchmark(
        order: Order,
        market_states: List[MarketState],
        strategies: List[StrategyBase],
        config: ExecutionConfig,
        scenario_name: str = "CUSTOM_SCENARIO",
    ) -> BenchmarkReport:
        """Run multiple strategies on the identical market state sequence and return comparison."""
        strategy_results: Dict[str, StrategyRunResult] = {}
        summary_rows: List[Dict[str, Any]] = []

        for strat in strategies:
            res = BenchmarkRunner.simulate_strategy(order, market_states, strat, config)
            strategy_results[strat.name] = res

            m = res.metrics
            summary_rows.append({
                "strategy": strat.name,
                "completion_rate_pct": round(m.completion_rate * 100.0, 2),
                "is_bps": round(m.implementation_shortfall_bps, 2),
                "is_usd": round(m.implementation_shortfall_usd, 2),
                "avg_exec_price": round(m.average_execution_price, 4),
                "avg_slippage_bps": round(m.average_slippage_bps, 2),
                "total_market_impact_usd": round(m.total_market_impact_usd, 2),
                "deadline_adhered": m.deadline_adhered,
            })

        return BenchmarkReport(
            scenario_name=scenario_name,
            order_id=order.id,
            order_symbol=order.symbol,
            order_side=order.side.value,
            order_quantity=order.quantity,
            num_intervals=len(market_states),
            strategy_results=strategy_results,
            summary_comparison=summary_rows,
        )
