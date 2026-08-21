"""Unit tests for RiskController."""

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
from execution_engine.core.features import FeatureExtractor
from execution_engine.risk.constraints import RiskConstraint
from execution_engine.risk.controller import RiskController


class TestRiskController(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=10)
        self.order = Order(
            id="ord-risk",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,
            start_time=self.start,
            end_time=self.end,
        )
        self.config = ExecutionConfig(
            interval_seconds=60.0,
            max_participation=0.10,  # 10%
            max_single_child_pct=0.20,  # 20% = 200 units max
            volatility_threshold=0.02,
            spread_threshold_bps=20.0,
            emergency_deadline_buffer_steps=2,
        )
        self.state = ExecutionState(
            remaining_quantity=800.0,
            executed_quantity=200.0,
            benchmark_price=100.0,
            current_step=2,
            total_steps=10,
        )
        self.market_state = MarketState(
            timestamp=self.start,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=5000.0,  # Part cap = 500
            liquidity=1.0,
            volatility=0.01,
        )
        self.features = FeatureExtractor.extract_features(
            self.order, self.state, self.market_state, self.config
        )

    def test_normal_valid_quantity(self):
        # Propose 100 units (<= remaining 800, <= single child 200, <= part cap 500)
        res = RiskController.validate_and_sanitize(
            100.0, self.order, self.state, self.market_state, self.features, self.config
        )
        self.assertEqual(res.sanitized_quantity, 100.0)
        self.assertEqual(len(res.constraints_hit), 0)
        self.assertGreaterEqual(res.risk_score, 0.0)
        self.assertLessEqual(res.risk_score, 1.0)

    def test_negative_quantity_clamped_to_zero(self):
        res = RiskController.validate_and_sanitize(
            -50.0, self.order, self.state, self.market_state, self.features, self.config
        )
        self.assertEqual(res.sanitized_quantity, 0.0)
        self.assertIn(RiskConstraint.NON_NEGATIVE_QUANTITY.value, res.constraints_hit)

    def test_nan_quantity_fail_closed(self):
        res = RiskController.validate_and_sanitize(
            float('nan'), self.order, self.state, self.market_state, self.features, self.config
        )
        self.assertEqual(res.sanitized_quantity, 0.0)
        self.assertIn(RiskConstraint.NON_NEGATIVE_QUANTITY.value, res.constraints_hit)

    def test_single_child_cap_clamped(self):
        # Propose 300 units -> max single child is 200 units (20% of 1000)
        res = RiskController.validate_and_sanitize(
            300.0, self.order, self.state, self.market_state, self.features, self.config
        )
        self.assertEqual(res.sanitized_quantity, 200.0)
        self.assertIn(RiskConstraint.MAX_SINGLE_CHILD_CAP.value, res.constraints_hit)

    def test_participation_cap_clamped(self):
        # Set market volume to 1000 -> part cap is 100 (10% of 1000)
        low_vol_market = MarketState(
            timestamp=self.start,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=1000.0,
            liquidity=1.0,
            volatility=0.01,
        )
        features = FeatureExtractor.extract_features(
            self.order, self.state, low_vol_market, self.config
        )
        # Propose 150 units
        res = RiskController.validate_and_sanitize(
            150.0, self.order, self.state, low_vol_market, features, self.config
        )
        self.assertEqual(res.sanitized_quantity, 100.0)
        self.assertIn(RiskConstraint.MAX_PARTICIPATION_CAP.value, res.constraints_hit)

    def test_remaining_quantity_cap(self):
        # State with only 50 units remaining
        state = ExecutionState(
            remaining_quantity=50.0,
            executed_quantity=950.0,
            benchmark_price=100.0,
            current_step=8,
            total_steps=10,
        )
        features = FeatureExtractor.extract_features(
            self.order, state, self.market_state, self.config
        )
        # Propose 100 units
        res = RiskController.validate_and_sanitize(
            100.0, self.order, state, self.market_state, features, self.config
        )
        self.assertEqual(res.sanitized_quantity, 50.0)
        self.assertIn(RiskConstraint.REMAINING_QUANTITY_CAP.value, res.constraints_hit)

    def test_order_already_completed(self):
        state = ExecutionState(
            remaining_quantity=0.0,
            executed_quantity=1000.0,
            benchmark_price=100.0,
            current_step=8,
            total_steps=10,
        )
        res = RiskController.validate_and_sanitize(
            100.0, self.order, state, self.market_state, self.features, self.config
        )
        self.assertEqual(res.sanitized_quantity, 0.0)
        self.assertEqual(res.reason_code_override, ReasonCode.ORDER_COMPLETED.value)
        self.assertIn(RiskConstraint.ORDER_ALREADY_COMPLETED.value, res.constraints_hit)

    def test_zero_market_volume_clamped(self):
        zero_vol_market = MarketState(
            timestamp=self.start,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=0.0,
            liquidity=0.0,
            volatility=0.01,
        )
        features = FeatureExtractor.extract_features(
            self.order, self.state, zero_vol_market, self.config
        )
        res = RiskController.validate_and_sanitize(
            100.0, self.order, self.state, zero_vol_market, features, self.config
        )
        self.assertEqual(res.sanitized_quantity, 0.0)
        self.assertEqual(res.reason_code_override, ReasonCode.ZERO_MARKET_VOLUME.value)
        self.assertIn(RiskConstraint.ZERO_VOLUME_CLAMP.value, res.constraints_hit)

    def test_deadline_emergency_mode_relaxation(self):
        # 1 step left (emergency deadline buffer = 2)
        state = ExecutionState(
            remaining_quantity=200.0,
            executed_quantity=800.0,
            benchmark_price=100.0,
            current_step=9,
            total_steps=10,
        )
        features = FeatureExtractor.extract_features(
            self.order, state, self.market_state, self.config
        )
        self.assertEqual(features.remaining_steps, 1)

        # In emergency mode, propose 200 units (which exceeds standard participation limit if volume is small)
        market = MarketState(
            timestamp=self.start + timedelta(minutes=9),
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=1000.0,  # Standard cap would be 100
            liquidity=1.0,
            volatility=0.01,
        )
        feat = FeatureExtractor.extract_features(self.order, state, market, self.config)
        res = RiskController.validate_and_sanitize(
            200.0, self.order, state, market, feat, self.config
        )
        self.assertEqual(res.sanitized_quantity, 200.0)
        self.assertEqual(res.reason_code_override, ReasonCode.DEADLINE_EMERGENCY.value)
        self.assertIn(RiskConstraint.DEADLINE_EMERGENCY_OVERRIDE.value, res.constraints_hit)


if __name__ == "__main__":
    unittest.main()
