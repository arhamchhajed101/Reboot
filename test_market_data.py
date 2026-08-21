import urllib.request
import json
from datetime import datetime, timezone, timedelta
from typing import List
import numpy as np

from execution_engine.core.models import Order, OrderSide, MarketState, ExecutionConfig
from execution_engine.evaluation.benchmark import BenchmarkRunner
from execution_engine.strategies.twap import TWAPStrategy
from execution_engine.strategies.volume_aware import VolumeAwareStrategy
from execution_engine.strategies.adaptive import AdaptiveStrategy


def fetch_binance_klines(symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 60) -> List[MarketState]:
    """Fetch real-world historical klines and transform them into MarketState objects."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    with urllib.request.urlopen(req, timeout=10) as response:
        raw_candles = json.loads(response.read().decode())

    market_states: List[MarketState] = []
    
    closes = [float(c[4]) for c in raw_candles]
    volumes = [float(c[5]) for c in raw_candles]
    avg_vol = np.mean(volumes) if volumes else 1.0

    for i, c in enumerate(raw_candles):
        open_time_ms = c[0]
        high_p = float(c[2])
        low_p = float(c[3])
        close_p = float(c[4])
        vol = float(c[5])
        
        # Real spread proxy from intraday high/low
        spread_approx = max(0.01, (high_p - low_p) * 0.15)
        bid_p = close_p - (spread_approx / 2.0)
        ask_p = close_p + (spread_approx / 2.0)
        
        # Volatility proxy: rolling return standard deviation
        if i >= 5:
            rets = np.diff(closes[max(0, i-10):i+1]) / closes[max(0, i-10):i]
            volatility = float(np.std(rets)) if len(rets) > 1 else 0.001
        else:
            volatility = 0.001

        # Normalized liquidity relative to average volume
        norm_liquidity = float(vol / avg_vol) if avg_vol > 0 else 1.0

        ts = datetime.fromtimestamp(open_time_ms / 1000.0, tz=timezone.utc)

        m_state = MarketState(
            timestamp=ts,
            price=close_p,
            bid=bid_p,
            ask=ask_p,
            volume=vol,
            liquidity=max(0.05, norm_liquidity),
            volatility=max(0.0001, volatility),
            transaction_cost=0.0002,  # 2 bps taker fee
        )
        market_states.append(m_state)

    return market_states


def run_real_world_test():
    symbol = "BTCUSDT"
    print(f"[*] Fetching live 1-minute historical market data from Binance for {symbol}...")
    market_states = fetch_binance_klines(symbol=symbol, interval="1m", limit=60)
    print(f"[+] Loaded {len(market_states)} real market intervals.")
    print(f"    Initial Mid Price: ${market_states[0].mid_price:,.2f}")
    print(f"    Final Mid Price:   ${market_states[-1].mid_price:,.2f}")
    print(f"    Avg 1m Volume:     {np.mean([m.volume for m in market_states]):.2f} {symbol}")

    start_time = market_states[0].timestamp
    end_time = market_states[-1].timestamp + timedelta(minutes=1)

    # Parent Order: Execute 10.0 BTC over 60 intervals
    order_qty = 10.0
    order = Order(
        id="PARENT-REAL-001",
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=order_qty,
        start_time=start_time,
        end_time=end_time,
    )

    config = ExecutionConfig(
        interval_seconds=60.0,
        max_participation_rate=0.25,
        single_child_max_fraction=0.15,
        risk_aversion=0.5,
    )

    strategies = [
        TWAPStrategy(),
        VolumeAwareStrategy(),
        AdaptiveStrategy(),
    ]

    print("\n" + "=" * 80)
    print(f" EXECUTING COMPARATIVE BENCHMARK ON REAL-WORLD MARKET DATA ({symbol})")
    print("=" * 80)

    report = BenchmarkRunner.run_benchmark(
        order=order,
        market_states=market_states,
        strategies=strategies,
        config=config,
        scenario_name="Binance_1m_RealMarketData",
    )

    print(f"\n{'Strategy':<18} | {'Completion %':<12} | {'IS (bps)':<12} | {'IS (USD)':<14} | {'Avg Exec Price':<16} | {'Avg Slippage':<14}")
    print("-" * 96)
    for row in report.summary_comparison:
        print(f"{row['strategy']:<18} | {row['completion_rate_pct']:>10.2f}% | {row['is_bps']:>10.2f} | ${row['is_usd']:>12.2f} | ${row['avg_exec_price']:>14.2f} | {row['avg_slippage_bps']:>12.2f} bps")

    print("=" * 96)

    # Inspect decision traces
    adaptive_result = report.strategy_results["ADAPTIVE"]
    reason_counts = {}
    for step in adaptive_result.trajectory:
        code = step.reason_code
        reason_counts[code] = reason_counts.get(code, 0) + 1

    print("\n[Adaptive Strategy Dynamic Reason Breakdown]")
    for code, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        print(f" - {code}: {count} steps")


if __name__ == "__main__":
    run_real_world_test()
