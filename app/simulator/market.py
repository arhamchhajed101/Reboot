import math
import numpy as np
from typing import List, Optional
from app.models.domain import MarketRegime, MarketState, ScenarioConfig


class MarketSimulator:
    def __init__(self, config: ScenarioConfig, override_seed: Optional[int] = None):
        self.config = config
        self.seed = override_seed if override_seed is not None else config.random_seed
        self.rng = np.random.RandomState(self.seed)

    def generate_market_path(self) -> List[MarketState]:
        states: List[MarketState] = []

        cfg = self.config
        steps = cfg.total_steps
        dt = cfg.step_duration_seconds / 60.0  # Normalized dt in minutes

        current_mid = cfg.initial_price

        for step in range(steps):
            timestamp = step * cfg.step_duration_seconds

            # Check if shock is triggered
            is_shock = cfg.shock_timestamp is not None and timestamp >= cfg.shock_timestamp

            if is_shock:
                current_vol = cfg.volatility * cfg.volatility_multiplier
                current_liquidity = cfg.liquidity * cfg.liquidity_multiplier
                current_spread_mult = cfg.spread_multiplier

                # Determine regime enum
                vol_changed = cfg.volatility_multiplier != 1.0
                liq_changed = cfg.liquidity_multiplier != 1.0

                if vol_changed and liq_changed:
                    regime = MarketRegime.COMBINED_SHOCK
                elif vol_changed:
                    regime = MarketRegime.VOLATILITY_SHOCK
                elif liq_changed:
                    regime = MarketRegime.LIQUIDITY_SHOCK
                else:
                    regime = MarketRegime.NORMAL
            else:
                current_vol = cfg.volatility
                current_liquidity = cfg.liquidity
                current_spread_mult = 1.0
                regime = MarketRegime.NORMAL

            # Base spread expands with volatility and shock multiplier
            base_spread = cfg.spread * current_spread_mult * (current_vol / cfg.volatility)
            spread_half = max(base_spread / 2.0, 0.005)

            bid_price = max(current_mid - spread_half, 0.01)
            ask_price = current_mid + spread_half
            spread_bps = ((ask_price - bid_price) / current_mid) * 10000.0

            # Dynamic volume tied to liquidity with slight random fluctuation
            vol_noise = 1.0 + 0.1 * self.rng.randn()
            volume = max(cfg.volume * (current_liquidity / cfg.liquidity) * vol_noise, 10.0)

            state = MarketState(
                timestamp=timestamp,
                mid_price=round(current_mid, 4),
                bid_price=round(bid_price, 4),
                ask_price=round(ask_price, 4),
                spread_bps=round(spread_bps, 2),
                volume=round(volume, 2),
                liquidity=round(current_liquidity, 2),
                volatility=round(current_vol, 6),
                transaction_cost_bps=cfg.transaction_cost_bps,
                regime=regime,
            )
            states.append(state)

            # Evolve mid price for next step using Geometric Brownian Motion
            z = self.rng.randn()
            drift = 0.0  # Assume zero drift for execution simulation
            ret = (drift - 0.5 * (current_vol ** 2)) * dt + current_vol * math.sqrt(dt) * z
            current_mid = current_mid * math.exp(ret)

        return states
