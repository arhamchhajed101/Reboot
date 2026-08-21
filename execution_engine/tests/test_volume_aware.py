"""Unit tests for VolumeAware baseline strategy."""

import unittest
from datetime import datetime, timezone, timedelta
from execution_engine.core.models import (
    Order,
    OrderSide,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    ReasonCode,
)
from execution_engine.strategies.volume_aware import VolumeAwareStrategy


class TestVolumeAwareStrategy(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=10)
        self.order = Order(
            id="ord-va",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,
            start_time=self.start,
            end_time=self.end,
        )
        self.config = ExecutionConfig(
            interval_seconds=60.0,
            max_participation=0.15,  # 15%
            max_single_child_pct=0.25,
            volatility_threshold=0.02,
        )
        self.strategy = VolumeAwareStrategy()

    def test_volume_aware_scales_with_volume(self):
        state = ExecutionState(
            remaining_quantity=800.0,
            executed_quantity=200.0,
            benchmark_price=100.0,
            current_step=2,
            total_steps=10,
        )
        # High volume interval = 10000 -> 15% of 10000 is 1500, but single child cap = 250 (25% of 1000)
        high_vol_market = MarketState(
            timestamp=self.start,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=1000.0,  # 15% of 1000 = 150 units
            liquidity=1.0,
            volatility=0.01,
        )

        decision = self.strategy.decide(self.order, state, high_vol_market, self.config)
        self.assertAlmostEqual(decision.quantity, 150.0)
        self.assertEqual(decision.reason_code, ReasonCode.NORMAL_VOLUME_AWARE.value)

        # Low volume interval = 400 -> 15% of 400 = 60 units
        low_vol_market = MarketState(
            timestamp=self.start,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=400.0,
            liquidity=0.8,
            volatility=0.01,
        )
        decision_low = self.strategy.decide(self.order, state, low_vol_market, self.config)
        self.assertAlmostEqual(decision_low.quantity, 60.0)
        self.assertLess(decision_low.quantity, decision.quantity)


if __name__ == "__main__":
    unittest.main()
