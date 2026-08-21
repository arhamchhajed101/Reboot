"""Unit tests for MetricsCalculator."""

import unittest
from datetime import datetime, timezone, timedelta
from execution_engine.core.models import (
    Order,
    OrderSide,
    MarketState,
    ExecutionState,
    ExecutionDecision,
    ReasonCode,
)
from execution_engine.evaluation.metrics import MetricsCalculator


class TestMetricsCalculator(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.order_buy = Order(
            id="ord-buy",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            start_time=self.now,
            end_time=self.now + timedelta(minutes=2),
        )
        self.order_sell = Order(
            id="ord-sell",
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100.0,
            start_time=self.now,
            end_time=self.now + timedelta(minutes=2),
        )
        self.init_state = ExecutionState(
            remaining_quantity=100.0,
            executed_quantity=0.0,
            benchmark_price=100.0,
            current_step=0,
            total_steps=2,
        )
        self.final_state = ExecutionState(
            remaining_quantity=0.0,
            executed_quantity=100.0,
            benchmark_price=100.0,
            current_step=2,
            total_steps=2,
        )
        self.market_states = [
            MarketState(timestamp=self.now, price=100.0, bid=99.95, ask=100.05, volume=1000.0, liquidity=1.0, volatility=0.01),
            MarketState(timestamp=self.now + timedelta(minutes=1), price=101.0, bid=100.95, ask=101.05, volume=1000.0, liquidity=1.0, volatility=0.01),
        ]
        self.decisions = [
            ExecutionDecision(timestamp=self.now, quantity=50.0, target_participation=0.05, reason_code=ReasonCode.NORMAL_EXECUTION.value, reason_text="ok"),
            ExecutionDecision(timestamp=self.now + timedelta(minutes=1), quantity=50.0, target_participation=0.05, reason_code=ReasonCode.NORMAL_EXECUTION.value, reason_text="ok"),
        ]

    def test_metrics_buy_order_is_bps(self):
        fill_prices = [100.20, 101.20]  # Avg price = 100.70 vs arrival 100.0 -> +70 bps
        fill_quantities = [50.0, 50.0]
        impacts = [5.0, 5.0]
        fees = [1.0, 1.0]

        metrics = MetricsCalculator.compute(
            order=self.order_buy,
            initial_state=self.init_state,
            final_state=self.final_state,
            decisions=self.decisions,
            market_states=self.market_states,
            fill_prices=fill_prices,
            fill_quantities=fill_quantities,
            impact_costs=impacts,
            fees=fees,
            strategy_name="TEST_STRAT",
        )

        self.assertEqual(metrics.completion_rate, 1.0)
        self.assertTrue(metrics.deadline_adhered)
        self.assertAlmostEqual(metrics.average_execution_price, 100.70)
        self.assertAlmostEqual(metrics.implementation_shortfall_bps, 70.0)
        self.assertAlmostEqual(metrics.implementation_shortfall_usd, 70.0)
        self.assertAlmostEqual(metrics.total_market_impact_usd, 10.0)

    def test_metrics_sell_order_is_bps(self):
        # For SELL: arrival 100.0, avg price 99.30 -> IS = (100 - 99.3) / 100 = +70 bps cost
        fill_prices = [99.50, 99.10]  # Avg price = 99.30
        fill_quantities = [50.0, 50.0]
        impacts = [5.0, 5.0]
        fees = [1.0, 1.0]

        metrics = MetricsCalculator.compute(
            order=self.order_sell,
            initial_state=self.init_state,
            final_state=self.final_state,
            decisions=self.decisions,
            market_states=self.market_states,
            fill_prices=fill_prices,
            fill_quantities=fill_quantities,
            impact_costs=impacts,
            fees=fees,
            strategy_name="TEST_STRAT",
        )

        self.assertAlmostEqual(metrics.average_execution_price, 99.30)
        self.assertAlmostEqual(metrics.implementation_shortfall_bps, 70.0)


if __name__ == "__main__":
    unittest.main()
