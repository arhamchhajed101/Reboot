"""Synthetic reproducible scenario generator for execution strategy evaluation and stress testing.
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List
import numpy as np

from execution_engine.core.models import MarketState


class ScenarioType(str, Enum):
    """Predefined reproducible market test scenarios."""
    NORMAL_MARKET = "NORMAL_MARKET"
    MID_SCENARIO_SHOCK = "MID_SCENARIO_SHOCK"
    ILLIQUID_MARKET = "ILLIQUID_MARKET"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    ZERO_VOLUME_GAP = "ZERO_VOLUME_GAP"


class ScenarioGenerator:
    """Generates reproducible time-series of MarketState objects."""

    @staticmethod
    def generate(
        scenario_type: ScenarioType,
        num_steps: int = 10,
        start_time: datetime | None = None,
        base_price: float = 100.0,
        interval_seconds: float = 60.0,
        seed: int = 42,
    ) -> List[MarketState]:
        """Generate a sequence of MarketState observations for a given scenario."""
        rng = np.random.RandomState(seed)
        start = start_time or datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        states: List[MarketState] = []
        current_price = base_price

        for step in range(num_steps):
            timestamp = start + timedelta(seconds=step * interval_seconds)

            if scenario_type == ScenarioType.NORMAL_MARKET:
                volatility = 0.01 + rng.uniform(-0.002, 0.002)
                liquidity = 1.0 + rng.uniform(-0.1, 0.1)
                volume = 5000.0 + rng.uniform(-500.0, 500.0)
                spread_bps = 5.0 + rng.uniform(-1.0, 1.0)
                price_ret = rng.normal(0.0, volatility * 0.1)

            elif scenario_type == ScenarioType.MID_SCENARIO_SHOCK:
                # Steps 4 to 6 suffer a severe volatility spike and liquidity collapse
                if 4 <= step <= 6:
                    volatility = 0.045 + rng.uniform(0.0, 0.01)
                    liquidity = 0.15 + rng.uniform(0.0, 0.05)
                    volume = 1500.0 + rng.uniform(-200.0, 200.0)
                    spread_bps = 35.0 + rng.uniform(0.0, 10.0)
                    price_ret = rng.normal(-0.005, volatility * 0.3)  # Adverse price drift
                elif step > 6:
                    # Post-shock recovery
                    volatility = 0.018 + rng.uniform(-0.002, 0.002)
                    liquidity = 0.75 + rng.uniform(-0.05, 0.05)
                    volume = 4000.0 + rng.uniform(-300.0, 300.0)
                    spread_bps = 10.0 + rng.uniform(-1.0, 1.0)
                    price_ret = rng.normal(0.0, volatility * 0.1)
                else:
                    # Pre-shock normal
                    volatility = 0.01 + rng.uniform(-0.002, 0.002)
                    liquidity = 1.0 + rng.uniform(-0.1, 0.1)
                    volume = 5000.0 + rng.uniform(-500.0, 500.0)
                    spread_bps = 5.0 + rng.uniform(-1.0, 1.0)
                    price_ret = rng.normal(0.0, volatility * 0.1)

            elif scenario_type == ScenarioType.ILLIQUID_MARKET:
                volatility = 0.02 + rng.uniform(-0.003, 0.003)
                liquidity = 0.25 + rng.uniform(-0.05, 0.05)
                volume = 800.0 + rng.uniform(-100.0, 100.0)
                spread_bps = 25.0 + rng.uniform(-2.0, 2.0)
                price_ret = rng.normal(0.0, volatility * 0.15)

            elif scenario_type == ScenarioType.HIGH_VOLATILITY:
                volatility = 0.05 + rng.uniform(-0.005, 0.005)
                liquidity = 0.6 + rng.uniform(-0.1, 0.1)
                volume = 6000.0 + rng.uniform(-800.0, 800.0)
                spread_bps = 20.0 + rng.uniform(-2.0, 2.0)
                price_ret = rng.normal(0.0, volatility * 0.25)

            elif scenario_type == ScenarioType.ZERO_VOLUME_GAP:
                if step in (3, 4):
                    volatility = 0.02
                    liquidity = 0.0
                    volume = 0.0
                    spread_bps = 40.0
                    price_ret = 0.0
                else:
                    volatility = 0.012
                    liquidity = 0.9
                    volume = 4500.0
                    spread_bps = 6.0
                    price_ret = rng.normal(0.0, volatility * 0.1)

            current_price = max(1.0, current_price * (1.0 + price_ret))
            half_spread = (spread_bps / 10_000.0) * current_price * 0.5
            bid = max(0.01, current_price - half_spread)
            ask = current_price + half_spread

            states.append(
                MarketState(
                    timestamp=timestamp,
                    price=current_price,
                    bid=bid,
                    ask=ask,
                    volume=max(0.0, volume),
                    liquidity=max(0.0, liquidity),
                    volatility=max(0.0001, volatility),
                    transaction_cost=0.0002,  # 2 bps transaction cost
                )
            )

        return states
