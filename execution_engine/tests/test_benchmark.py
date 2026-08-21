"""Unit tests for BenchmarkRunner."""

import unittest
from datetime import datetime, timezone, timedelta
from execution_engine.core.models import Order, OrderSide, ExecutionConfig
from execution_engine.strategies.twap import TWAPStrategy
from execution_engine.strategies.volume_aware import VolumeAwareStrategy
from execution_engine.strategies.adaptive import AdaptiveStrategy
from execution_engine.evaluation.scenario import ScenarioGenerator, ScenarioType
from execution_engine.evaluation.benchmark import BenchmarkRunner


class TestBenchmarkRunner(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.order = Order(
            id="ord-bench",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,
            start_time=self.now,
            end_time=self.now + timedelta(minutes=10),
        )
        self.config = ExecutionConfig(
            interval_seconds=60.0,
            max_participation=0.25,
            max_single_child_pct=0.30,
            volatility_threshold=0.02,
            liquidity_threshold=0.5,
            spread_threshold_bps=20.0,
            impact_coefficient=0.5,
        )
        self.strategies = [
            TWAPStrategy(),
            VolumeAwareStrategy(),
            AdaptiveStrategy(),
        ]

    def test_benchmark_on_mid_scenario_shock(self):
        states = ScenarioGenerator.generate(
            ScenarioType.MID_SCENARIO_SHOCK, num_steps=10, seed=42
        )
        report = BenchmarkRunner.run_benchmark(
            order=self.order,
            market_states=states,
            strategies=self.strategies,
            config=self.config,
            scenario_name="MID_SCENARIO_SHOCK_TEST",
        )

        self.assertEqual(report.scenario_name, "MID_SCENARIO_SHOCK_TEST")
        self.assertEqual(len(report.strategy_results), 3)
        self.assertEqual(len(report.summary_comparison), 3)

        for name, res in report.strategy_results.items():
            self.assertEqual(res.metrics.completion_rate, 1.0)
            self.assertTrue(res.metrics.deadline_adhered)
            self.assertEqual(len(res.trajectory), 10)


if __name__ == "__main__":
    unittest.main()
