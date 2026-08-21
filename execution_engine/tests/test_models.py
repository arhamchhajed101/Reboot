"""Unit tests for core domain models."""

import unittest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

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


class TestOrderModel(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=30)

    def test_valid_order(self):
        order = Order(
            id="ord-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10000.0,
            start_time=self.start,
            end_time=self.end,
        )
        self.assertEqual(order.id, "ord-001")
        self.assertEqual(order.symbol, "AAPL")
        self.assertEqual(order.side, OrderSide.BUY)
        self.assertEqual(order.quantity, 10000.0)

    def test_invalid_quantity_zero_or_negative(self):
        with self.assertRaises(ValidationError):
            Order(
                id="ord-002",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=0.0,
                start_time=self.start,
                end_time=self.end,
            )
        with self.assertRaises(ValidationError):
            Order(
                id="ord-003",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=-50.0,
                start_time=self.start,
                end_time=self.end,
            )

    def test_invalid_horizon_end_before_or_equal_start(self):
        with self.assertRaises(ValidationError):
            Order(
                id="ord-004",
                symbol="AAPL",
                side=OrderSide.SELL,
                quantity=100.0,
                start_time=self.end,
                end_time=self.start,
            )
        with self.assertRaises(ValidationError):
            Order(
                id="ord-005",
                symbol="AAPL",
                side=OrderSide.SELL,
                quantity=100.0,
                start_time=self.start,
                end_time=self.start,
            )


class TestMarketStateModel(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)

    def test_valid_market_state(self):
        state = MarketState(
            timestamp=self.now,
            price=150.0,
            bid=149.95,
            ask=150.05,
            volume=50000.0,
            liquidity=1.0,
            volatility=0.015,
            transaction_cost=0.0005,
        )
        self.assertEqual(state.mid_price, 150.0)
        self.assertAlmostEqual(state.spread, 0.10)
        # spread_bps = (0.10 / 150.0) * 10,000 = 6.666666...
        self.assertAlmostEqual(state.spread_bps, 6.666666666666667)

    def test_inverted_spread_raises_error(self):
        with self.assertRaises(ValidationError):
            MarketState(
                timestamp=self.now,
                price=150.0,
                bid=151.0,  # bid > ask
                ask=149.0,
                volume=1000.0,
                liquidity=1.0,
                volatility=0.01,
            )

    def test_zero_or_negative_price_raises_error(self):
        with self.assertRaises(ValidationError):
            MarketState(
                timestamp=self.now,
                price=0.0,
                bid=149.0,
                ask=150.0,
                volume=1000.0,
                liquidity=1.0,
                volatility=0.01,
            )


class TestExecutionConfigAndState(unittest.TestCase):
    def test_config_defaults_and_validation(self):
        config = ExecutionConfig()
        self.assertEqual(config.interval_seconds, 60.0)
        self.assertEqual(config.max_participation, 0.15)
        self.assertEqual(config.weights["cost"], 1.0)

        # Invalid max_participation > 1.0 or <= 0
        with self.assertRaises(ValidationError):
            ExecutionConfig(max_participation=1.5)
        with self.assertRaises(ValidationError):
            ExecutionConfig(max_participation=0.0)

    def test_execution_state_properties(self):
        state = ExecutionState(
            remaining_quantity=600.0,
            executed_quantity=400.0,
            cumulative_cost=60200.0,  # 400 shares @ avg 150.5
            benchmark_price=150.0,
            current_step=4,
            total_steps=10,
        )
        self.assertFalse(state.is_completed)
        self.assertAlmostEqual(state.completion_rate, 0.4)
        self.assertAlmostEqual(state.average_execution_price, 150.5)

        # Complete state
        completed_state = ExecutionState(
            remaining_quantity=0.0,
            executed_quantity=1000.0,
            cumulative_cost=150000.0,
            benchmark_price=150.0,
        )
        self.assertTrue(completed_state.is_completed)
        self.assertAlmostEqual(completed_state.completion_rate, 1.0)


class TestExecutionDecisionModel(unittest.TestCase):
    def test_valid_decision(self):
        decision = ExecutionDecision(
            timestamp=datetime.now(timezone.utc),
            quantity=100.0,
            target_participation=0.10,
            expected_cost=15020.0,
            risk_score=0.25,
            urgency_score=0.40,
            reason_code=ReasonCode.NORMAL_EXECUTION,
            reason_text="Standard interval execution under normal conditions",
            constraints_hit=[],
        )
        self.assertEqual(decision.quantity, 100.0)
        self.assertEqual(decision.reason_code, "NORMAL_EXECUTION")

    def test_negative_quantity_raises_error(self):
        with self.assertRaises(ValidationError):
            ExecutionDecision(
                timestamp=datetime.now(timezone.utc),
                quantity=-10.0,
                reason_code=ReasonCode.NORMAL_EXECUTION,
                reason_text="Invalid negative",
            )


if __name__ == "__main__":
    unittest.main()
