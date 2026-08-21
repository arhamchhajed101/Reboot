"""Unit tests for Adaptive Strategy."""

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
from execution_engine.strategies.adaptive import AdaptiveStrategy


class TestAdaptiveStrategy(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=10)
        self.order = Order(
            id="ord-adapt",
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
            liquidity_threshold=0.5,
            spread_threshold_bps=20.0,
            impact_coefficient=0.5,
        )
        self.strategy = AdaptiveStrategy()

    def test_adaptive_normal_conditions(self):
        state = ExecutionState(
            remaining_quantity=1000.0,
            executed_quantity=0.0,
            benchmark_price=100.0,
            current_step=0,
            total_steps=10,
        )
        normal_market = MarketState(
            timestamp=self.start,
            price=100.0,
            bid=99.98,
            ask=100.02,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
            transaction_cost=0.0002,
        )
        decision = self.strategy.decide(self.order, state, normal_market, self.config)
        self.assertGreater(decision.quantity, 0.0)
        self.assertLessEqual(decision.quantity, 250.0)  # Respects single child cap
        self.assertIn("NORMAL", decision.reason_text)

    def test_adaptive_throttles_under_volatility_and_liquidity_shock(self):
        state = ExecutionState(
            remaining_quantity=800.0,
            executed_quantity=200.0,
            benchmark_price=100.0,
            current_step=2,
            total_steps=10,
        )
        # Normal market comparison
        normal_market = MarketState(
            timestamp=self.start + timedelta(minutes=2),
            price=100.0,
            bid=99.98,
            ask=100.02,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
        )
        normal_decision = self.strategy.decide(self.order, state, normal_market, self.config)

        # Stressed market shock (high vol=0.04, low liq=0.2, wide spread=30 bps)
        shock_market = MarketState(
            timestamp=self.start + timedelta(minutes=2),
            price=100.0,
            bid=99.85,
            ask=100.15,
            volume=5000.0,
            liquidity=0.2,
            volatility=0.04,
        )
        shock_decision = self.strategy.decide(self.order, state, shock_market, self.config)

        # Under shock, adaptive strategy must reduce execution size to preserve execution cost
        self.assertLess(shock_decision.quantity, normal_decision.quantity)
        self.assertEqual(shock_decision.reason_code, ReasonCode.HIGH_VOLATILITY_THROTTLE.value)
        self.assertIn("Compound stress detected", shock_decision.reason_text)

    def test_adaptive_deadline_emergency_completion(self):
        # 1 step left with 200 units remaining -> must escalate execution to complete order
        state = ExecutionState(
            remaining_quantity=200.0,
            executed_quantity=800.0,
            benchmark_price=100.0,
            current_step=9,
            total_steps=10,
        )
        market = MarketState(
            timestamp=self.start + timedelta(minutes=9),
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
        )
        decision = self.strategy.decide(self.order, state, market, self.config)
        self.assertEqual(decision.quantity, 200.0)
        self.assertEqual(decision.reason_code, ReasonCode.DEADLINE_EMERGENCY.value)
        self.assertIn("Deadline emergency", decision.reason_text)


if __name__ == "__main__":
    unittest.main()
