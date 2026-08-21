"""Unit tests for FeatureExtractor."""

import unittest
from datetime import datetime, timezone, timedelta
from execution_engine.core.models import Order, OrderSide, MarketState, ExecutionConfig, ExecutionState
from execution_engine.core.features import FeatureExtractor


class TestFeatureExtractor(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=10)  # 10 minute horizon
        self.order = Order(
            id="ord-test",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,
            start_time=self.start,
            end_time=self.end,
        )
        self.config = ExecutionConfig(
            interval_seconds=60.0,
            max_participation=0.10,
            volatility_threshold=0.02,
            spread_threshold_bps=10.0,
        )

    def test_feature_extraction_normal(self):
        market_state = MarketState(
            timestamp=self.start,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
        )
        exec_state = ExecutionState(
            remaining_quantity=1000.0,
            executed_quantity=0.0,
            cumulative_cost=0.0,
            benchmark_price=100.0,
            current_step=0,
            total_steps=10,
        )
        features = FeatureExtractor.extract_features(
            self.order, exec_state, market_state, self.config
        )

        self.assertAlmostEqual(features.mid_price, 100.0)
        self.assertAlmostEqual(features.spread_bps, 10.0)
        self.assertAlmostEqual(features.participation_capacity, 500.0)  # 5000 * 0.10
        self.assertAlmostEqual(features.urgency_ratio, 1.0)  # On schedule (1000/10 vs 1000/10)
        self.assertEqual(features.remaining_steps, 10)
        self.assertAlmostEqual(features.volatility_ratio, 0.5)  # 0.01 / 0.02

    def test_urgency_ratio_behind_schedule(self):
        # 800 units remaining with only 2 steps left -> requires 400/step vs initial 100/step -> urgency = 4.0
        market_state = MarketState(
            timestamp=self.start + timedelta(minutes=8),
            price=100.0,
            bid=99.99,
            ask=100.01,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
        )
        exec_state = ExecutionState(
            remaining_quantity=800.0,
            executed_quantity=200.0,
            cumulative_cost=20000.0,
            benchmark_price=100.0,
            current_step=8,
            total_steps=10,
        )
        features = FeatureExtractor.extract_features(
            self.order, exec_state, market_state, self.config
        )
        self.assertEqual(features.remaining_steps, 2)
        self.assertAlmostEqual(features.urgency_ratio, 4.0)
        self.assertGreater(features.normalized_urgency, 0.7)

    def test_zero_volume_features(self):
        market_state = MarketState(
            timestamp=self.start,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=0.0,
            liquidity=0.0,
            volatility=0.01,
        )
        exec_state = ExecutionState(
            remaining_quantity=1000.0,
            executed_quantity=0.0,
            benchmark_price=100.0,
            current_step=0,
            total_steps=10,
        )
        features = FeatureExtractor.extract_features(
            self.order, exec_state, market_state, self.config
        )
        self.assertEqual(features.participation_capacity, 0.0)


if __name__ == "__main__":
    unittest.main()
