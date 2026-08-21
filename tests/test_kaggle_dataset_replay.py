import pytest
import os
from datetime import datetime, timedelta, timezone
from app.simulator.historical import HistoricalMarketReplayer
from app.simulator.fill import FillEngine
from app.models.domain import Order, OrderSide, ExecutionContext
from app.execution.twap import TWAPStrategy
from app.execution.volume_aware import VolumeAwareStrategy
from app.execution.adaptive import AdaptiveStrategy
from app.evaluation.engine import EvaluationEngine
from execution_engine.api.adapter import ExecutionEngine

@pytest.fixture
def kaggle_dataset_path():
    path = "scenarios/kaggle_optiver_lob_sample.csv"
    assert os.path.exists(path), "Kaggle LOB dataset CSV must exist."
    return path

def test_kaggle_dataset_loading(kaggle_dataset_path):
    replayer = HistoricalMarketReplayer(kaggle_dataset_path)
    market_path = replayer.load_market_path()
    assert len(market_path) == 120
    assert market_path[0].mid_price > 0
    assert market_path[45].regime.value == "COMBINED_SHOCK"

def test_kaggle_dataset_strategy_replay_comparison(kaggle_dataset_path):
    """
    Replay TWAP, Volume-Aware, and Adaptive strategies on real Kaggle LOB dataset.
    Verify that Adaptive strategy handles the Kaggle shock window safely.
    """
    replayer = HistoricalMarketReplayer(kaggle_dataset_path)
    market_path = replayer.load_market_path()

    order = Order(
        order_id="ord_kaggle_1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10000.0,
        start_time=0.0,
        end_time=120.0,
    )

    strategies = {
        "TWAP": TWAPStrategy(),
        "VolumeAware": VolumeAwareStrategy(),
        "Adaptive": AdaptiveStrategy(),
    }

    results = {}

    for name, strategy in strategies.items():
        fill_engine = FillEngine(max_market_participation_cap=0.30)
        remaining_qty = order.quantity
        decisions = []
        fills = []

        for step, tick in enumerate(market_path):
            if remaining_qty <= 1e-6:
                break

            elapsed = tick.timestamp
            remaining_time = max(order.end_time - elapsed, 0.0)

            context = ExecutionContext(
                order=order,
                market_state=tick,
                elapsed_time=elapsed,
                remaining_time=remaining_time,
                remaining_quantity=remaining_qty,
                strategy_configuration={"step_duration_seconds": 1.0, "max_participation_rate": 0.30},
            )

            # Strategy decision
            decision = strategy.decide(context)

            # Cap strategy target
            target_qty = min(decision.quantity, remaining_qty)

            # Fill engine simulation
            fill = fill_engine.simulate_fill(
                requested_quantity=target_qty,
                market_state=tick,
                side=order.side,
            )

            remaining_qty -= fill.filled_quantity
            decisions.append(decision)
            fills.append(fill)

        # Evaluate performance
        metrics = EvaluationEngine.evaluate_run(
            run_id=f"run_kaggle_{name.lower()}",
            strategy_name=name.lower(),
            order=order,
            market_ticks=market_path[:len(fills)],
            decisions=decisions,
            fills=fills,
        )
        results[name] = metrics

    print("\n" + "=" * 75)
    print(f"KAGGLE LOB DATASET EXECUTION REPLAY BENCHMARK")
    print("=" * 75)
    print(f"{'Strategy':<15} | {'Filled Qty':<12} | {'VWAP Price':<12} | {'Cost ($)':<12} | {'IS (bps)':<10}")
    print("-" * 75)
    for name, m in results.items():
        print(f"{name:<15} | {m.filled_quantity:<12.1f} | {m.vwap_fill_price:<12.4f} | ${m.total_execution_cost:<11.2f} | {m.implementation_shortfall_bps:<10.2f}")
    print("=" * 75)

    # Assertions
    assert results["TWAP"].filled_quantity > 0
    assert results["VolumeAware"].filled_quantity > 0
    assert results["Adaptive"].filled_quantity > 0
    assert results["Adaptive"].stability_score >= 0.70

def test_execution_engine_on_kaggle_dataset(kaggle_dataset_path):
    """Test Quant ExecutionEngine facade on Kaggle LOB dataset"""
    replayer = HistoricalMarketReplayer(kaggle_dataset_path)
    market_path = replayer.load_market_path()

    engine = ExecutionEngine(strategy="ADAPTIVE")

    from execution_engine.core.models import Order as EEOrder, OrderSide as EEOrderSide, MarketState as EEMarketState

    start_t = datetime.now(timezone.utc)
    ee_order = EEOrder(
        id="ord_kaggle_1",
        symbol="AAPL",
        side=EEOrderSide.BUY,
        quantity=10000.0,
        start_time=start_t,
        end_time=start_t + timedelta(seconds=120),
    )

    ee_market_states = [
        EEMarketState(
            timestamp=start_t + timedelta(seconds=m.timestamp),
            price=m.mid_price,
            bid=m.bid_price,
            ask=m.ask_price,
            volume=m.volume,
            volatility=m.volatility,
            liquidity=m.liquidity,
        )
        for m in market_path
    ]

    report = engine.run_benchmark(
        order=ee_order,
        market_states=ee_market_states,
        scenario_name="KAGGLE_LOB_BENCHMARK",
    )

    assert report is not None
    assert "TWAP" in report.strategy_results
    assert "ADAPTIVE" in report.strategy_results
    assert len(report.summary_comparison) == 3
