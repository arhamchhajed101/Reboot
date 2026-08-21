"""Unit tests for ObjectiveScorer and market impact model."""

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
from execution_engine.core.regimes import RegimeClassification
from execution_engine.core.objectives import ObjectiveScorer


class TestObjectiveScorer(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.order = Order(
            id="ord-obj",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,
            start_time=self.now,
            end_time=self.now + timedelta(minutes=10),
        )
        self.config = ExecutionConfig(
            impact_coefficient=0.5,
            volatility_threshold=0.02,
        )
        self.state = ExecutionState(
            remaining_quantity=1000.0,
            executed_quantity=0.0,
            benchmark_price=100.0,
            current_step=0,
            total_steps=10,
        )

    def test_market_impact_calculation(self):
        market_normal = MarketState(
            timestamp=self.now,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=10000.0,
            liquidity=1.0,
            volatility=0.01,
        )
        # 100 shares / 10000 vol = 0.01 participation
        # Impact = 0.5 * 100 * 100 * (0.01)^2 * 1.0 = 5000 * 0.0001 * 1.0 = 0.5
        impact = ObjectiveScorer.calculate_impact_penalty(100.0, market_normal, self.config)
        self.assertAlmostEqual(impact, 0.5)

        # Low liquidity market (liquidity = 0.2) -> penalty factor = 1.0 / 0.2 = 5.0
        market_illiquid = MarketState(
            timestamp=self.now,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=10000.0,
            liquidity=0.2,
            volatility=0.01,
        )
        impact_illiquid = ObjectiveScorer.calculate_impact_penalty(100.0, market_illiquid, self.config)
        self.assertAlmostEqual(impact_illiquid, 2.5)  # 5x higher impact

    def test_candidate_scoring_penalties(self):
        market = MarketState(
            timestamp=self.now,
            price=100.0,
            bid=99.95,
            ask=100.05,
            volume=5000.0,
            liquidity=1.0,
            volatility=0.01,
        )
        features = FeatureExtractor.extract_features(self.order, self.state, market, self.config)
        regime = RegimeClassification(
            regime=RegimeType.NORMAL,
            is_stressed=False,
            risk_multiplier=1.0,
            description="Normal",
        )

        score_full = ObjectiveScorer.score_candidate(
            candidate_qty=100.0,
            target_schedule_qty=100.0,
            order=self.order,
            state=self.state,
            market_state=market,
            features=features,
            regime_info=regime,
            config=self.config,
        )
        self.assertEqual(score_full.quantity, 100.0)
        self.assertGreater(score_full.cost_component, 0.0)

        # Under-executing: candidate = 0.0 when target was 100.0
        score_zero = ObjectiveScorer.score_candidate(
            candidate_qty=0.0,
            target_schedule_qty=100.0,
            order=self.order,
            state=self.state,
            market_state=market,
            features=features,
            regime_info=regime,
            config=self.config,
        )
        # Delaying execution significantly increases urgency and unexecuted inventory penalty
        self.assertGreater(score_zero.urgency_penalty, score_full.urgency_penalty)


if __name__ == "__main__":
    unittest.main()
