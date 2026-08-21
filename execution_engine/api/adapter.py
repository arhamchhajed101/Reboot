"""Public integration facade and adapter for the RECURZ Execution Engine.

Provides a unified interface for the Backend / Simulator to interact with
strategy decision-making, state progression, and full scenario evaluation.
"""

from datetime import datetime
from typing import List, Optional, Union
from execution_engine.core.models import (
    Order,
    OrderSide,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    ExecutionDecision,
    RegimeType,
    ReasonCode,
)
from execution_engine.risk.controller import RiskController
from execution_engine.strategies.base import StrategyBase
from execution_engine.strategies.twap import TWAPStrategy
from execution_engine.strategies.volume_aware import VolumeAwareStrategy
from execution_engine.strategies.adaptive import AdaptiveStrategy
from execution_engine.evaluation.benchmark import BenchmarkRunner, StrategyRunResult, BenchmarkReport


STRATEGY_REGISTRY = {
    "TWAP": TWAPStrategy,
    "VOLUME_AWARE": VolumeAwareStrategy,
    "ADAPTIVE": AdaptiveStrategy,
}


def get_strategy(strategy: Union[StrategyBase, str]) -> StrategyBase:
    """Resolve a strategy instance from name or return if already an instance."""
    if isinstance(strategy, StrategyBase):
        return strategy
    strat_key = strategy.upper()
    if strat_key not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy '{strategy}'. Supported: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[strat_key]()


class ExecutionEngine:
    """Unified Execution Engine Facade for Backend / Simulator integration.

    Example usage:
        engine = ExecutionEngine(strategy="ADAPTIVE")
        decision = engine.execute_step(order, state, market_state)
        new_state = engine.update_state(state, fill_qty, fill_price)
    """

    def __init__(
        self,
        strategy: Union[StrategyBase, str] = "ADAPTIVE",
        config: Optional[ExecutionConfig] = None,
        risk_controller: Optional[RiskController] = None,
    ):
        self.strategy: StrategyBase = get_strategy(strategy)
        self.config: ExecutionConfig = config or ExecutionConfig()
        self.risk_controller: RiskController = risk_controller or RiskController()

    def set_strategy(self, strategy: Union[StrategyBase, str]) -> None:
        """Dynamically switch active execution strategy."""
        self.strategy = get_strategy(strategy)

    def create_initial_state(
        self,
        order: Order,
        initial_market_state: MarketState,
        total_steps: Optional[int] = None,
    ) -> ExecutionState:
        """Initialize the starting execution state for a parent order."""
        if total_steps is None:
            horizon_secs = (order.end_time - order.start_time).total_seconds()
            total_steps = max(1, int(horizon_secs // self.config.interval_seconds))

        return ExecutionState(
            remaining_quantity=order.quantity,
            executed_quantity=0.0,
            cumulative_cost=0.0,
            benchmark_price=initial_market_state.mid_price,
            current_step=0,
            total_steps=total_steps,
        )

    def execute_step(
        self,
        order: Order,
        state: ExecutionState,
        market_state: MarketState,
        config: Optional[ExecutionConfig] = None,
    ) -> ExecutionDecision:
        """Compute the next child order execution decision for the given market interval."""
        cfg = config or self.config
        return self.strategy.decide(
            order=order,
            state=state,
            market_state=market_state,
            config=cfg,
        )

    def update_state(
        self,
        state: ExecutionState,
        fill_quantity: float,
        fill_price: float,
        transaction_cost_rate: float = 0.0,
    ) -> ExecutionState:
        """Progress execution state following a simulated or executed fill."""
        q_fill = max(0.0, min(fill_quantity, state.remaining_quantity))
        fee = q_fill * fill_price * transaction_cost_rate
        slice_cost = (q_fill * fill_price) + fee

        new_remaining = max(0.0, state.remaining_quantity - q_fill)
        new_executed = state.executed_quantity + q_fill
        new_cum_cost = state.cumulative_cost + slice_cost

        return ExecutionState(
            remaining_quantity=new_remaining,
            executed_quantity=new_executed,
            cumulative_cost=new_cum_cost,
            benchmark_price=state.benchmark_price,
            current_step=state.current_step + 1,
            total_steps=state.total_steps,
        )

    def run_scenario(
        self,
        order: Order,
        market_states: List[MarketState],
        config: Optional[ExecutionConfig] = None,
    ) -> StrategyRunResult:
        """Run a full multi-interval execution simulation for the active strategy."""
        cfg = config or self.config
        return BenchmarkRunner.simulate_strategy(
            order=order,
            market_states=market_states,
            strategy=self.strategy,
            config=cfg,
        )

    def run_benchmark(
        self,
        order: Order,
        market_states: List[MarketState],
        strategies: Optional[List[Union[StrategyBase, str]]] = None,
        config: Optional[ExecutionConfig] = None,
        scenario_name: str = "SCENARIO_RUN",
    ) -> BenchmarkReport:
        """Run comparative benchmark across multiple strategies on the same market sequence."""
        cfg = config or self.config
        if strategies is None:
            strat_instances = [TWAPStrategy(), VolumeAwareStrategy(), AdaptiveStrategy()]
        else:
            strat_instances = [get_strategy(s) for s in strategies]

        return BenchmarkRunner.run_benchmark(
            order=order,
            market_states=market_states,
            strategies=strat_instances,
            config=cfg,
            scenario_name=scenario_name,
        )
