"""Unit tests for TWAP baseline strategy."""

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
from execution_engine.strategies.twap import TWAPStrategy


class TestTWAPStrategy(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=10)
        self.order = Order(
            id="ord-twap",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,
            start_time=self.start,
            end_time=self.end,
        )
        self.config = ExecutionConfig(
            interval_seconds=60.0,
            max_participation=0.20,
            max_single_child_pct=0.25,
            volatility_threshold=0.02,
        )
        self.strategy = TWAPStrategy()

    def test_twap_normal_step(self):
        state = ExecutionState(
            remaining_quantity=1000.0,
            executed_quantity=0.0,
            benchmark_price=150.0,
            current_step=0,
            total_steps=10,
        )
        market_state = MarketState(
            timestamp=self.start,
            price=150.0,
            bid=149.95,
            ask=150.05,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
            transaction_cost=0.0005,
        )

        decision = self.strategy.decide(self.order, state, market_state, self.config)
        # 1000 remaining over 10 steps = 100 per step
        self.assertAlmostEqual(decision.quantity, 100.0)
        self.assertEqual(decision.reason_code, ReasonCode.NORMAL_TWAP.value)
        self.assertAlmostEqual(decision.target_participation, 100.0 / 5000.0)
        self.assertEqual(len(decision.constraints_hit), 0)

    def test_twap_clamped_by_participation(self):
        # Market volume is low (e.g. 200), max part = 20% -> cap = 40 units
        state = ExecutionState(
            remaining_quantity=1000.0,
            executed_quantity=0.0,
            benchmark_price=150.0,
            current_step=0,
            total_steps=10,
        )
        low_vol_market = MarketState(
            timestamp=self.start,
            price=150.0,
            bid=149.95,
            ask=150.05,
            volume=200.0,
            liquidity=0.5,
            volatility=0.01,
        )

        decision = self.strategy.decide(self.order, state, low_vol_market, self.config)
        # Target was 100, but clamped to 40
        self.assertAlmostEqual(decision.quantity, 40.0)
        self.assertIn("MAX_PARTICIPATION_CAP", decision.constraints_hit)

    def test_twap_already_completed(self):
        state = ExecutionState(
            remaining_quantity=0.0,
            executed_quantity=1000.0,
            benchmark_price=150.0,
            current_step=10,
            total_steps=10,
        )
        market_state = MarketState(
            timestamp=self.end,
            price=150.0,
            bid=149.95,
            ask=150.05,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
        )
        decision = self.strategy.decide(self.order, state, market_state, self.config)
        self.assertEqual(decision.quantity, 0.0)
        self.assertEqual(decision.reason_code, ReasonCode.ORDER_COMPLETED.value)


if __name__ == "__main__":
    unittest.main()
