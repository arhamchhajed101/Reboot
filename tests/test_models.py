import pytest
from pydantic import ValidationError
from app.models.domain import (
    ExecutionDecision,
    FillEvent,
    MarketRegime,
    MarketState,
    Order,
    OrderSide,
)


def test_order_model_valid():
    order = Order(
        order_id="ord_1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=500.0,
        start_time=0.0,
        end_time=60.0,
    )
    assert order.quantity == 500.0
    assert order.side == OrderSide.BUY


def test_order_model_invalid_quantity():
    with pytest.raises(ValidationError):
        Order(
            order_id="ord_1",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=-10.0,
            start_time=0.0,
            end_time=60.0,
        )


def test_order_model_nan_rejection():
    with pytest.raises(ValidationError):
        Order(
            order_id="ord_1",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=float("nan"),
            start_time=0.0,
            end_time=60.0,
        )


def test_market_state_price_validation():
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
    assert state.mid_price == 100.0

    # Inverted ask/bid must fail
    with pytest.raises(ValidationError):
        MarketState(
            timestamp=0.0,
            mid_price=100.0,
            bid_price=101.0,
            ask_price=99.0,
            spread_bps=20.0,
            volume=1000.0,
            liquidity=5000.0,
            volatility=0.02,
            transaction_cost_bps=1.0,
            regime=MarketRegime.NORMAL,
        )
