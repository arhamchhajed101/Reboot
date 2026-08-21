from app.execution.base import ExecutionStrategy
from app.models.domain import ExecutionContext, ExecutionDecision


class TWAPStrategy(ExecutionStrategy):
    """
    Time-Weighted Average Price (TWAP) Execution Strategy.
    Slices remaining quantity uniformly across remaining time steps.
    """

    @property
    def name(self) -> str:
        return "twap"

    def decide(self, context: ExecutionContext) -> ExecutionDecision:
        remaining_qty = context.remaining_quantity
        step_duration = context.strategy_configuration.get("step_duration_seconds", 1.0)
        remaining_steps = max(int(context.remaining_time / step_duration), 1)

        target_qty = remaining_qty / remaining_steps if remaining_steps > 0 else remaining_qty
        target_qty = min(target_qty, remaining_qty)

        max_participation = context.strategy_configuration.get("max_participation_rate", 0.30)
        market_vol = max(context.market_state.volume, 1e-6)

        # Cap quantity by max allowed participation rate
        capped_qty = min(target_qty, market_vol * max_participation)
        participation_rate = min(capped_qty / market_vol, 1.0)

        aggressiveness = 0.5
        expected_cost = capped_qty * context.market_state.mid_price * (context.market_state.spread_bps * 1e-4 * 0.5)

        return ExecutionDecision(
            timestamp=context.market_state.timestamp,
            quantity=round(capped_qty, 4),
            participation_rate=round(participation_rate, 4),
            aggressiveness=aggressiveness,
            expected_cost=round(expected_cost, 4),
            risk_score=0.2,
            rationale=f"TWAP slice: {capped_qty:.2f} units over {remaining_steps} remaining steps.",
        )
