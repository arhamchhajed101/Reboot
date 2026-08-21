from app.models.domain import MarketRegime, MarketState, OrderSide
from app.simulator.fill import FillEngine


def test_fill_engine_zero_quantity():
    engine = FillEngine()
    state = MarketState(
        timestamp=0.0,
        mid_price=100.0,
        bid_price=99.9,
        ask_price=100.1,
        spread_bps=20.0,
        volume=1000.0,
        liquidity=5000.0,
        volatility=0.02,
        transaction_cost_bps=1.0,
        regime=MarketRegime.NORMAL,
    )
    fill = engine.simulate_fill(0.0, state, OrderSide.BUY)
    assert fill.filled_quantity == 0.0
    assert fill.spread_cost == 0.0
    assert fill.impact_cost == 0.0


def test_fill_engine_buy_vs_sell_price():
    engine = FillEngine()
    state = MarketState(
        timestamp=0.0,
        mid_price=100.0,
        bid_price=99.9,
        ask_price=100.1,
        spread_bps=20.0,
        volume=1000.0,
        liquidity=5000.0,
        volatility=0.02,
        transaction_cost_bps=1.0,
        regime=MarketRegime.NORMAL,
    )

    buy_fill = engine.simulate_fill(100.0, state, OrderSide.BUY)
    sell_fill = engine.simulate_fill(100.0, state, OrderSide.SELL)

    # Buy fill price > mid_price, sell fill price < mid_price
    assert buy_fill.fill_price > state.mid_price
    assert sell_fill.fill_price < state.mid_price


def test_market_impact_increases_with_participation():
    engine = FillEngine(max_market_participation_cap=0.50)
    state = MarketState(
        timestamp=0.0,
        mid_price=100.0,
        bid_price=99.9,
        ask_price=100.1,
        spread_bps=20.0,
        volume=1000.0,
        liquidity=5000.0,
        volatility=0.02,
        transaction_cost_bps=1.0,
        regime=MarketRegime.NORMAL,
    )

    small_fill = engine.simulate_fill(50.0, state, OrderSide.BUY)
    large_fill = engine.simulate_fill(400.0, state, OrderSide.BUY)

    # Unit impact cost per share should be higher for larger participation rate
    small_unit_impact = small_fill.impact_cost / small_fill.filled_quantity
    large_unit_impact = large_fill.impact_cost / large_fill.filled_quantity

    assert large_unit_impact > small_unit_impact
