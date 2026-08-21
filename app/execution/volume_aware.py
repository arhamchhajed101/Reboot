from app.execution.base import ExecutionStrategy
from app.models.domain import ExecutionContext, ExecutionDecision


class VolumeAwareStrategy(ExecutionStrategy):
    """
    Volume-Aware / Volume-Weighted Execution Strategy.
    Scales target execution volume proportionally to current market volume relative to expected baseline.
    """

    @property
    def name(self) -> str:
        return "volume_aware"

    def decide(self, context: ExecutionContext) -> ExecutionDecision:
        remaining_qty = context.remaining_quantity
        step_duration = context.strategy_configuration.get("step_duration_seconds", 1.0)
        remaining_steps = max(int(context.remaining_time / step_duration), 1)

        base_slice = remaining_qty / remaining_steps

        # Calculate volume factor relative to baseline liquidity/volume
        current_vol = context.market_state.volume
        baseline_vol = context.strategy_configuration.get("baseline_volume", 1000.0)

        vol_factor = max(current_vol / baseline_vol, 0.2)

        # Scale order quantity with market volume
        target_qty = base_slice * vol_factor
        target_qty = min(target_qty, remaining_qty)

        max_participation = context.strategy_configuration.get("max_participation_rate", 0.35)
        capped_qty = min(target_qty, current_vol * max_participation)
        participation_rate = min(capped_qty / max(current_vol, 1e-6), 1.0)

        aggressiveness = min(0.3 + 0.4 * vol_factor, 1.0)
        expected_cost = capped_qty * context.market_state.mid_price * (context.market_state.spread_bps * 1e-4 * 0.5)

        return ExecutionDecision(
            timestamp=context.market_state.timestamp,
            quantity=round(capped_qty, 4),
            participation_rate=round(participation_rate, 4),
            aggressiveness=round(aggressiveness, 2),
            expected_cost=round(expected_cost, 4),
            risk_score=0.25,
            rationale=f"Volume-aware slice: {capped_qty:.2f} (vol factor: {vol_factor:.2f}).",
        )
