import uuid
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.engine import EvaluationEngine
from app.execution import get_strategy
from app.models.db_models import RunDB
from app.models.domain import (
    ExecutionContext,
    ExecutionDecision,
    FillEvent,
    MarketState,
    Order,
    OrderSide,
    RunMetrics,
    RunStatus,
    ScenarioConfig,
)
from app.repositories.run_repository import RunRepository
from app.services.event_bus import event_bus
from app.simulator.fill import FillEngine
from app.simulator.market import MarketSimulator
from app.simulator.scenarios import load_scenario


class RunService:
    def __init__(self, session: AsyncSession):
        self.repo = RunRepository(session)

    async def execute_run(
        self,
        scenario_id: str,
        strategy_name: str,
        order_side: OrderSide,
        quantity: float,
        horizon_seconds: float = 60.0,
        symbol: str = "AAPL",
        seed: Optional[int] = None,
        max_participation_rate: float = 0.30,
        custom_scenario: Optional[ScenarioConfig] = None,
        strategy_config: Optional[dict] = None,
    ) -> RunMetrics:
        run_id = f"run_{uuid.uuid4().hex[:10]}"

        scenario = custom_scenario or load_scenario(scenario_id)
        effective_seed = seed if seed is not None else scenario.random_seed

        # Save scenario metadata
        await self.repo.save_scenario(scenario)

        # Create Run DB entry
        strat_config = strategy_config or {}
        strat_config["max_participation_rate"] = max_participation_rate
        strat_config["step_duration_seconds"] = scenario.step_duration_seconds

        await self.repo.create_run(
            run_id=run_id,
            scenario_id=scenario.scenario_id,
            strategy=strategy_name,
            order_side=order_side,
            symbol=symbol,
            quantity=quantity,
            horizon=horizon_seconds,
            seed=effective_seed,
            configuration=strat_config,
        )
        await self.repo.update_run_status(run_id, RunStatus.RUNNING)

        try:
            order = Order(
                order_id=f"ord_{run_id}",
                symbol=symbol,
                side=order_side,
                quantity=quantity,
                start_time=0.0,
                end_time=horizon_seconds,
            )

            strategy = get_strategy(strategy_name)
            simulator = MarketSimulator(scenario, override_seed=effective_seed)
            fill_engine = FillEngine(
                base_volatility=scenario.volatility,
                base_liquidity=scenario.liquidity,
                max_market_participation_cap=max_participation_rate,
            )

            market_path = simulator.generate_market_path()
            # Limit execution to the requested horizon window
            market_path = [s for s in market_path if s.timestamp < horizon_seconds]
            if not market_path:
                # Edge case: horizon shorter than first tick — run one step
                market_path = simulator.generate_market_path()[:1]

            remaining_qty = quantity
            prev_decision: Optional[ExecutionDecision] = None

            recorded_ticks: List[MarketState] = []
            recorded_decisions: List[ExecutionDecision] = []
            recorded_fills: List[FillEvent] = []

            for step, market_state in enumerate(market_path):
                elapsed_time = market_state.timestamp
                remaining_time = max(horizon_seconds - elapsed_time, 0.0)

                context = ExecutionContext(
                    order=order,
                    market_state=market_state,
                    remaining_quantity=remaining_qty,
                    elapsed_time=elapsed_time,
                    remaining_time=remaining_time,
                    previous_decision=prev_decision,
                    strategy_configuration=strat_config,
                )

                # 1. Strategy produces decision
                decision = strategy.decide(context)
                # Enforce non-negative and cap by remaining
                decision_qty = max(0.0, min(decision.quantity, remaining_qty))
                if decision_qty != decision.quantity:
                    decision = ExecutionDecision(
                        timestamp=decision.timestamp,
                        quantity=decision_qty,
                        participation_rate=decision.participation_rate,
                        aggressiveness=decision.aggressiveness,
                        expected_cost=decision.expected_cost,
                        risk_score=decision.risk_score,
                        rationale=decision.rationale + " [Capped by remaining qty]",
                    )

                # 2. Simulate Fill
                fill = fill_engine.simulate_fill(decision.quantity, market_state, order.side)
                remaining_qty = max(0.0, remaining_qty - fill.filled_quantity)

                # 3. Record DB entries
                await self.repo.record_tick(run_id, step, market_state)
                await self.repo.record_decision(run_id, step, decision)
                await self.repo.record_fill(run_id, step, fill)

                recorded_ticks.append(market_state)
                recorded_decisions.append(decision)
                recorded_fills.append(fill)

                prev_decision = decision

                # 4. Stream events over WebSocket
                await event_bus.broadcast(
                    run_id,
                    "market_update",
                    {
                        "step": step,
                        "market_state": market_state.model_dump(),
                        "regime": market_state.regime.value,
                    },
                )
                await event_bus.broadcast(
                    run_id, "decision", {"step": step, "decision": decision.model_dump()}
                )
                await event_bus.broadcast(
                    run_id, "fill", {"step": step, "fill": fill.model_dump(), "remaining_quantity": remaining_qty}
                )

            # 5. Evaluate overall run performance
            metrics = EvaluationEngine.evaluate_run(
                run_id=run_id,
                strategy_name=strategy_name,
                order=order,
                market_ticks=recorded_ticks,
                decisions=recorded_decisions,
                fills=recorded_fills,
            )

            await self.repo.save_metrics(metrics)
            await self.repo.update_run_status(run_id, RunStatus.COMPLETED)

            await event_bus.broadcast(
                run_id, "run_completed", {"metrics": metrics.model_dump()}
            )

            return metrics

        except Exception as e:
            await self.repo.update_run_status(run_id, RunStatus.FAILED, error_message=str(e))
            await event_bus.broadcast(run_id, "run_failed", {"error": str(e)})
            raise

    async def compare_strategies(
        self,
        scenario_id: str,
        order_side: OrderSide,
        quantity: float,
        horizon_seconds: float = 60.0,
        symbol: str = "AAPL",
        seed: int = 42,
        strategies: Optional[List[str]] = None,
    ) -> Dict[str, RunMetrics]:
        """
        Runs multiple execution strategies under the EXACT SAME scenario, order, and random seed.
        Ensures strict apples-to-apples dynamic benchmarking.
        """
        if strategies is None:
            strategies = ["twap", "volume_aware", "adaptive"]

        results: Dict[str, RunMetrics] = {}
        for strat in strategies:
            metrics = await self.execute_run(
                scenario_id=scenario_id,
                strategy_name=strat,
                order_side=order_side,
                quantity=quantity,
                horizon_seconds=horizon_seconds,
                symbol=symbol,
                seed=seed,
            )
            results[strat] = metrics

        return results
