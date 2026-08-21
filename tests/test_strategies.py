from app.execution import get_strategy
from app.models.domain import (
    ExecutionContext,
    MarketRegime,
    MarketState,
    Order,
    OrderSide,
)


def make_context(volatility=0.02, volume=1000.0, regime=MarketRegime.NORMAL):
    order = Order(
        order_id="ord_1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=600.0,
        start_time=0.0,
        end_time=60.0,
    )
    state = MarketState(
        timestamp=0.0,
        mid_price=100.0,
        bid_price=99.9,
        ask_price=100.1,
        spread_bps=20.0,
        volume=volume,
        liquidity=5000.0,
        volatility=volatility,
        transaction_cost_bps=1.0,
        regime=regime,
    )
    return ExecutionContext(
        order=order,
        market_state=state,
        remaining_quantity=600.0,
        elapsed_time=0.0,
        remaining_time=60.0,
        strategy_configuration={"step_duration_seconds": 1.0, "max_participation_rate": 0.30},
    )


def test_twap_strategy():
    strategy = get_strategy("twap")
    context = make_context()
    decision = strategy.decide(context)

    assert decision.quantity > 0
    assert decision.quantity <= 600.0 / 60.0 + 1e-5 or decision.quantity <= 1000.0 * 0.30


def test_adaptive_strategy_slows_down_on_volatility_shock():
    strategy = get_strategy("adaptive")

    normal_context = make_context(volatility=0.015, regime=MarketRegime.NORMAL)
    shock_context = make_context(volatility=0.06, regime=MarketRegime.VOLATILITY_SHOCK)

    normal_dec = strategy.decide(normal_context)
    shock_dec = strategy.decide(shock_context)

    # Adaptive strategy should reduce quantity/participation during volatility shock
    assert shock_dec.quantity < normal_dec.quantity
