"""Unit tests for RegimeDetector."""

import unittest
from datetime import datetime, timezone, timedelta
from execution_engine.core.models import (
    Order,
    OrderSide,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    RegimeType,
)
from execution_engine.core.features import FeatureExtractor
from execution_engine.core.regimes import RegimeDetector


class TestRegimeDetector(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.order = Order(
            id="ord-regime",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,
            start_time=self.now,
            end_time=self.now + timedelta(minutes=10),
        )
        self.config = ExecutionConfig(
            volatility_threshold=0.02,
            liquidity_threshold=0.5,
            spread_threshold_bps=20.0,
        )
        self.state = ExecutionState(
            remaining_quantity=1000.0,
            executed_quantity=0.0,
            benchmark_price=100.0,
            current_step=0,
            total_steps=10,
        )

    def _get_classification(self, price=100.0, bid=99.95, ask=100.05, volume=5000.0, liquidity=1.0, volatility=0.01):
        market_state = MarketState(
            timestamp=self.now,
            price=price,
            bid=bid,
            ask=ask,
            volume=volume,
            liquidity=liquidity,
            volatility=volatility,
        )
        features = FeatureExtractor.extract_features(self.order, self.state, market_state, self.config)
        return RegimeDetector.classify(market_state, features, self.config)

    def test_normal_regime(self):
        res = self._get_classification(volatility=0.01, liquidity=1.0, bid=99.95, ask=100.05)
        self.assertEqual(res.regime, RegimeType.NORMAL)
        self.assertFalse(res.is_stressed)
        self.assertEqual(res.risk_multiplier, 1.0)

    def test_high_volatility_regime(self):
        res = self._get_classification(volatility=0.035, liquidity=0.9)
        self.assertEqual(res.regime, RegimeType.HIGH_VOLATILITY)
        self.assertTrue(res.is_stressed)
        self.assertEqual(res.risk_multiplier, 0.6)

    def test_low_liquidity_regime(self):
        res = self._get_classification(volatility=0.01, liquidity=0.3)
        self.assertEqual(res.regime, RegimeType.LOW_LIQUIDITY)
        self.assertTrue(res.is_stressed)
        self.assertEqual(res.risk_multiplier, 0.5)

    def test_stressed_compound_regime(self):
        # High vol AND low liq
        res = self._get_classification(volatility=0.04, liquidity=0.2)
        self.assertEqual(res.regime, RegimeType.STRESSED)
        self.assertTrue(res.is_stressed)
        self.assertEqual(res.risk_multiplier, 0.4)

    def test_high_spread_regime(self):
        # 30 bps spread
        res = self._get_classification(volatility=0.01, liquidity=0.8, bid=99.85, ask=100.15)
        self.assertEqual(res.regime, RegimeType.HIGH_SPREAD)
        self.assertEqual(res.risk_multiplier, 0.75)

    def test_zero_volume_regime(self):
        res = self._get_classification(volume=0.0)
        self.assertEqual(res.regime, RegimeType.ZERO_VOLUME)
        self.assertTrue(res.is_stressed)


if __name__ == "__main__":
    unittest.main()
