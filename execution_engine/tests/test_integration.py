"""End-to-end integration tests for ExecutionEngine facade."""

import unittest
from datetime import datetime, timezone, timedelta
from execution_engine import (
    Order,
    OrderSide,
    MarketState,
    ExecutionConfig,
    ExecutionEngine,
    ScenarioGenerator,
    ScenarioType,
    ReasonCode,
)


class TestExecutionEngineIntegration(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.order = Order(
            id="parent-int-01",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,
            start_time=self.now,
            end_time=self.now + timedelta(minutes=5),
        )
        self.config = ExecutionConfig(
            interval_seconds=60.0,
            max_participation=0.20,
            volatility_threshold=0.02,
        )

    def test_engine_initialization_and_step_progression(self):
        engine = ExecutionEngine(strategy="ADAPTIVE", config=self.config)

        initial_market = MarketState(
            timestamp=self.now,
            price=150.0,
            bid=149.95,
            ask=150.05,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
        )

        state = engine.create_initial_state(self.order, initial_market)
        self.assertEqual(state.remaining_quantity, 1000.0)
        self.assertEqual(state.executed_quantity, 0.0)
        self.assertEqual(state.benchmark_price, 150.0)
        self.assertEqual(state.total_steps, 5)

        # Step 0 Execution
        decision = engine.execute_step(self.order, state, initial_market)
        self.assertGreater(decision.quantity, 0.0)
        self.assertLessEqual(decision.quantity, 250.0)

        # Update state after fill
        fill_qty = decision.quantity
        new_state = engine.update_state(state, fill_quantity=fill_qty, fill_price=150.05)
        self.assertEqual(new_state.executed_quantity, fill_qty)
        self.assertEqual(new_state.remaining_quantity, 1000.0 - fill_qty)
        self.assertEqual(new_state.current_step, 1)

    def test_engine_strategy_switch(self):
        engine = ExecutionEngine(strategy="TWAP", config=self.config)
        self.assertEqual(engine.strategy.name, "TWAP")

        engine.set_strategy("VOLUME_AWARE")
        self.assertEqual(engine.strategy.name, "VOLUME_AWARE")

        engine.set_strategy("ADAPTIVE")
        self.assertEqual(engine.strategy.name, "ADAPTIVE")

    def test_engine_run_scenario_and_benchmark(self):
        engine = ExecutionEngine(strategy="ADAPTIVE", config=self.config)
        states = ScenarioGenerator.generate(ScenarioType.MID_SCENARIO_SHOCK, num_steps=5, seed=42)

        # 1. Single scenario simulation
        run_res = engine.run_scenario(self.order, states)
        self.assertEqual(run_res.strategy_name, "ADAPTIVE")
        self.assertEqual(run_res.metrics.completion_rate, 1.0)
        self.assertEqual(len(run_res.trajectory), 5)

        # 2. Benchmark against all strategies
        report = engine.run_benchmark(self.order, states, scenario_name="INTEGRATION_BENCHMARK")
        self.assertEqual(len(report.strategy_results), 3)
        self.assertIn("TWAP", report.strategy_results)
        self.assertIn("VOLUME_AWARE", report.strategy_results)
        self.assertIn("ADAPTIVE", report.strategy_results)


if __name__ == "__main__":
    unittest.main()
