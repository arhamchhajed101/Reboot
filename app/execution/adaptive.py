from app.execution.base import ExecutionStrategy
from app.models.domain import ExecutionContext, ExecutionDecision, MarketRegime


class AdaptiveStrategy(ExecutionStrategy):
    """
    Adaptive Execution Strategy.
    Dynamically balances market impact vs completion risk by adapting to changing market regimes,
    volatility spikes, and liquidity crunches.
    """

    @property
    def name(self) -> str:
        return "adaptive"

    def decide(self, context: ExecutionContext) -> ExecutionDecision:
        remaining_qty = context.remaining_quantity
        step_duration = context.strategy_configuration.get("step_duration_seconds", 1.0)
        remaining_steps = max(int(context.remaining_time / step_duration), 1)

        total_horizon_steps = max(
            int((context.elapsed_time + context.remaining_time) / step_duration), 1
        )
        time_elapsed_ratio = context.elapsed_time / (context.elapsed_time + context.remaining_time + 1e-6)

        # Target TWAP baseline quantity
        base_slice = remaining_qty / remaining_steps

        # Market signals
        regime = context.market_state.regime
        volatility = context.market_state.volatility
        spread_bps = context.market_state.spread_bps
        current_vol = context.market_state.volume

        # Dynamic multipliers based on market conditions
        vol_multiplier = 1.0
        if regime in (MarketRegime.VOLATILITY_SHOCK, MarketRegime.COMBINED_SHOCK) or volatility > 0.03:
            # High volatility -> reduce participation to avoid paying inflated market impact
            vol_multiplier = 0.4

        liq_multiplier = 1.0
        if regime in (MarketRegime.LIQUIDITY_SHOCK, MarketRegime.COMBINED_SHOCK) or current_vol < 300:
            # Liquidity crunch -> reduce order size to fit thin market depth
            liq_multiplier = 0.5

        # Urgency multiplier increases as deadline approaches (completion risk)
        urgency_multiplier = 1.0
        if time_elapsed_ratio > 0.7:
            urgency_multiplier = 1.0 + (time_elapsed_ratio - 0.7) * 4.0  # up to 2.2x

        # Calculate adapted quantity slice
        adapted_slice = base_slice * vol_multiplier * liq_multiplier * urgency_multiplier
        target_qty = min(adapted_slice, remaining_qty)

        max_participation = context.strategy_configuration.get("max_participation_rate", 0.40)
        capped_qty = min(target_qty, current_vol * max_participation)
        participation_rate = min(capped_qty / max(current_vol, 1e-6), 1.0)

        aggressiveness = max(0.1, min(0.9, 0.4 * urgency_multiplier / (vol_multiplier * liq_multiplier)))
        expected_cost = capped_qty * context.market_state.mid_price * (spread_bps * 1e-4 * 0.5)

        risk_score = round(0.1 + 0.5 * (volatility / 0.05) + 0.4 * (1.0 - liq_multiplier), 4)

        rationale = (
            f"Adaptive decision: regime={regime.value}, vol_mult={vol_multiplier:.2f}, "
            f"liq_mult={liq_multiplier:.2f}, urgency={urgency_multiplier:.2f}."
        )

        return ExecutionDecision(
            timestamp=context.market_state.timestamp,
            quantity=round(capped_qty, 4),
            participation_rate=round(participation_rate, 4),
            aggressiveness=round(aggressiveness, 2),
            expected_cost=round(expected_cost, 4),
            risk_score=min(risk_score, 1.0),
            rationale=rationale,
        )
