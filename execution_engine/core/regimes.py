"""Market regime classification module for the RECURZ Execution Engine.

Detects volatility spikes, liquidity dry-ups, wide spreads, and compound stressed regimes.
"""

from typing import NamedTuple
from execution_engine.core.models import MarketState, ExecutionConfig, RegimeType
from execution_engine.core.features import MarketFeatures


class RegimeClassification(NamedTuple):
    """Structured result of regime classification with operational context."""
    regime: RegimeType
    is_stressed: bool
    risk_multiplier: float
    description: str


class RegimeDetector:
    """Deterministic regime classifier based on market indicators and configured thresholds."""

    @staticmethod
    def classify(
        market_state: MarketState,
        features: MarketFeatures,
        config: ExecutionConfig
    ) -> RegimeClassification:
        """Classify the observed market state into a discrete regime.

        Hierarchy of classification:
        1. ZERO_VOLUME: Observable market volume is zero or negligible.
        2. STRESSED: Compound shock (high volatility AND low liquidity).
        3. HIGH_VOLATILITY: Volatility exceeds threshold.
        4. LOW_LIQUIDITY: Liquidity drops below threshold.
        5. HIGH_SPREAD: Bid-ask spread in bps exceeds threshold.
        6. NORMAL: All metrics within standard operational tolerances.
        """
        if market_state.volume <= 1e-7:
            return RegimeClassification(
                regime=RegimeType.ZERO_VOLUME,
                is_stressed=True,
                risk_multiplier=1.0,
                description="Zero observable market volume in interval.",
            )

        high_vol = market_state.volatility >= config.volatility_threshold
        low_liq = market_state.liquidity <= config.liquidity_threshold
        high_spread = features.spread_bps >= config.spread_threshold_bps

        if high_vol and low_liq:
            return RegimeClassification(
                regime=RegimeType.STRESSED,
                is_stressed=True,
                risk_multiplier=0.4,  # Scale down participation to 40%
                description="Compound stress regime: high volatility and low liquidity.",
            )
        elif high_vol:
            return RegimeClassification(
                regime=RegimeType.HIGH_VOLATILITY,
                is_stressed=True,
                risk_multiplier=0.6,  # Scale down participation to 60%
                description=f"High volatility ({market_state.volatility:.4f} >= {config.volatility_threshold:.4f}).",
            )
        elif low_liq:
            return RegimeClassification(
                regime=RegimeType.LOW_LIQUIDITY,
                is_stressed=True,
                risk_multiplier=0.5,  # Scale down participation to 50%
                description=f"Low market liquidity ({market_state.liquidity:.2f} <= {config.liquidity_threshold:.2f}).",
            )
        elif high_spread:
            return RegimeClassification(
                regime=RegimeType.HIGH_SPREAD,
                is_stressed=False,
                risk_multiplier=0.75,
                description=f"Wide bid-ask spread ({features.spread_bps:.1f} bps >= {config.spread_threshold_bps:.1f} bps).",
            )
        else:
            return RegimeClassification(
                regime=RegimeType.NORMAL,
                is_stressed=False,
                risk_multiplier=1.0,
                description="Normal trading regime within standard parameters.",
            )
