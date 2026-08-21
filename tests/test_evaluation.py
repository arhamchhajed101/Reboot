from app.evaluation.engine import EvaluationEngine
from app.models.domain import (
    ExecutionDecision,
    FillEvent,
    MarketRegime,
    MarketState,
    Order,
    OrderSide,
)


def test_evaluation_buy_implementation_shortfall():
    order = Order(
        order_id="ord_1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100.0,
        start_time=0.0,
        end_time=60.0,
    )
    ticks = [
        MarketState(
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
        ),
        MarketState(
            timestamp=60.0,
            mid_price=102.0,
            bid_price=101.9,
            ask_price=102.1,
            spread_bps=20.0,
            volume=1000.0,
            liquidity=5000.0,
            volatility=0.02,
            transaction_cost_bps=1.0,
            regime=MarketRegime.NORMAL,
        ),
    ]
    decisions = [
        ExecutionDecision(
            timestamp=0.0,
            quantity=100.0,
            participation_rate=0.10,
            aggressiveness=0.5,
            expected_cost=10.0,
            risk_score=0.1,
            rationale="",
        )
    ]
    fills = [
        FillEvent(
            requested_quantity=100.0,
            filled_quantity=100.0,
            fill_price=100.5,
            spread_cost=10.0,
            impact_cost=35.0,
            transaction_cost=5.0,
            timestamp=0.0,
        )
    ]

    metrics = EvaluationEngine.evaluate_run(
        run_id="run_1",
        strategy_name="twap",
        order=order,
        market_ticks=ticks,
        decisions=decisions,
        fills=fills,
    )

    assert metrics.completion_percentage == 100.0
    assert metrics.total_execution_cost == 50.0
    # Filled notional = 100 * 100.5 = 10050. Benchmark = 100 * 100.0 = 10000. IS = 50.0
    assert metrics.implementation_shortfall == 50.0
    assert metrics.implementation_shortfall_bps == 50.0  # (50 / 10000) * 10000 = 50 bps


def test_evaluation_sell_implementation_shortfall():
    order = Order(
        order_id="ord_1",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100.0,
        start_time=0.0,
        end_time=60.0,
    )
    ticks = [
        MarketState(
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
    ]
    decisions = []
    fills = [
        FillEvent(
            requested_quantity=100.0,
            filled_quantity=100.0,
            fill_price=99.5,
            spread_cost=10.0,
            impact_cost=35.0,
            transaction_cost=5.0,
            timestamp=0.0,
        )
    ]

    metrics = EvaluationEngine.evaluate_run(
        run_id="run_2",
        strategy_name="twap",
        order=order,
        market_ticks=ticks,
        decisions=decisions,
        fills=fills,
    )

    # Benchmark = 10000. Filled = 9950. SELL IS = 10000 - 9950 = 50.0
    assert metrics.implementation_shortfall == 50.0
