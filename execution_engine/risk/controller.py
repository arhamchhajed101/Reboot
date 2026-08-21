"""Risk controller enforcing hard execution invariants independently of strategy preferences.
"""

import math
from typing import List, Tuple
from execution_engine.core.models import (
    Order,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    ReasonCode,
)
from execution_engine.core.features import MarketFeatures
from execution_engine.risk.constraints import RiskConstraint


class RiskValidationResult:
    """Container for the risk validation outcome."""
    def __init__(
        self,
        sanitized_quantity: float,
        risk_score: float,
        constraints_hit: List[str],
        reason_code_override: str | None = None,
        reason_text_override: str | None = None,
    ):
        self.sanitized_quantity = sanitized_quantity
        self.risk_score = risk_score
        self.constraints_hit = constraints_hit
        self.reason_code_override = reason_code_override
        self.reason_text_override = reason_text_override


class RiskController:
    """Enforces hard risk constraints and sanitizes proposed child orders."""

    @staticmethod
    def validate_and_sanitize(
        proposed_quantity: float,
        order: Order,
        state: ExecutionState,
        market_state: MarketState,
        features: MarketFeatures,
        config: ExecutionConfig,
    ) -> RiskValidationResult:
        """Sanitize proposed child order quantity according to hard risk invariants.

        Invariants:
        1. Non-negative quantity: q >= 0.0.
        2. Never exceed remaining order quantity: q <= state.remaining_quantity.
        3. Never exceed max single-child percentage cap: q <= order.quantity * config.max_single_child_pct (unless deadline emergency).
        4. Participation cap: q <= volume * config.max_participation (relaxed only under deadline emergency mode).
        5. Zero volume clamp: q = 0 if volume == 0 (unless deadline emergency).
        6. Fail-closed on invalid / NaN inputs.
        """
        constraints_hit: List[str] = []
        reason_code_override: str | None = None
        reason_text_override: str | None = None

        # Fail-closed guard against NaN / infinite values
        if not math.isfinite(proposed_quantity) or proposed_quantity < 0.0:
            constraints_hit.append(RiskConstraint.NON_NEGATIVE_QUANTITY.value)
            proposed_quantity = 0.0

        # Check if already completed
        if state.remaining_quantity <= 1e-7:
            constraints_hit.append(RiskConstraint.ORDER_ALREADY_COMPLETED.value)
            return RiskValidationResult(
                sanitized_quantity=0.0,
                risk_score=0.0,
                constraints_hit=constraints_hit,
                reason_code_override=ReasonCode.ORDER_COMPLETED.value,
                reason_text_override="Parent order is already completely filled.",
            )

        # Check zero volume
        is_zero_volume = market_state.volume <= 1e-7
        is_deadline_emergency = features.remaining_steps <= config.emergency_deadline_buffer_steps

        if is_zero_volume and not is_deadline_emergency:
            constraints_hit.append(RiskConstraint.ZERO_VOLUME_CLAMP.value)
            return RiskValidationResult(
                sanitized_quantity=0.0,
                risk_score=0.8,
                constraints_hit=constraints_hit,
                reason_code_override=ReasonCode.ZERO_MARKET_VOLUME.value,
                reason_text_override="Zero observable market volume; execution halted to prevent extreme slippage.",
            )

        qty = proposed_quantity

        # Single child cap
        max_single_child = order.quantity * config.max_single_child_pct
        if not is_deadline_emergency and qty > max_single_child:
            qty = max_single_child
            constraints_hit.append(RiskConstraint.MAX_SINGLE_CHILD_CAP.value)

        # Participation cap
        part_capacity = features.participation_capacity
        if is_deadline_emergency:
            # Deadline emergency: relax participation cap to ensure order completion
            if qty > part_capacity and not is_zero_volume:
                constraints_hit.append(RiskConstraint.DEADLINE_EMERGENCY_OVERRIDE.value)
                reason_code_override = ReasonCode.DEADLINE_EMERGENCY.value
                reason_text_override = f"Deadline emergency: executing {qty:.2f} units to avoid incomplete order."
        else:
            if qty > part_capacity:
                qty = part_capacity
                constraints_hit.append(RiskConstraint.MAX_PARTICIPATION_CAP.value)

        # Remaining quantity cap
        if qty > state.remaining_quantity:
            qty = state.remaining_quantity
            constraints_hit.append(RiskConstraint.REMAINING_QUANTITY_CAP.value)

        # Final non-negative clamp
        final_qty = max(0.0, min(qty, state.remaining_quantity))

        # Calculate composite risk score in [0.0, 1.0]
        vol_score = min(1.0, market_state.volatility / max(1e-5, config.volatility_threshold * 2.0))
        spread_score = min(1.0, features.spread_bps / max(1e-5, config.spread_threshold_bps * 2.0))
        participation_rate = (final_qty / market_state.volume) if market_state.volume > 0 else 1.0
        part_score = min(1.0, participation_rate / max(1e-5, config.max_participation))

        composite_risk = (0.4 * vol_score) + (0.3 * spread_score) + (0.3 * part_score)
        clamped_risk = max(0.0, min(1.0, composite_risk))

        return RiskValidationResult(
            sanitized_quantity=final_qty,
            risk_score=clamped_risk,
            constraints_hit=constraints_hit,
            reason_code_override=reason_code_override,
            reason_text_override=reason_text_override,
        )
