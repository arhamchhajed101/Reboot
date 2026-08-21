import numpy as np
import pandas as pd
import math

def generate_kaggle_lob_dataset(filename="scenarios/kaggle_optiver_lob_sample.csv", num_steps=120, seed=42):
    """
    Generates a realistic Kaggle-aligned High Frequency Limit Order Book (LOB) dataset.
    Follows Optiver / LOBSTER dataset standards:
    - Intraday volume curve
    - Geometric Brownian Motion price trajectory
    - Volatility & Liquidity shock dynamics
    """
    np.random.seed(seed)

    records = []
    initial_price = 150.0  # e.g., AAPL / SPY stock price scale
    current_price = initial_price
    base_volatility = 0.015
    base_liquidity = 10000.0
    base_volume = 1200.0

    for step in range(num_steps):
        timestamp = float(step * 1.0)  # 1-second ticks

        # Shock event between step 40 and 80 (Vol spike + liquidity drop)
        if 40 <= step <= 80:
            volatility = base_volatility * 3.0
            liquidity = base_liquidity * 0.3
            regime = "COMBINED_SHOCK"
        else:
            volatility = base_volatility
            liquidity = base_liquidity
            regime = "NORMAL"

        # Intraday U-shape volume curve factor
        u_factor = 1.2 - 0.5 * math.sin(math.pi * step / num_steps)
        volume = max(base_volume * (liquidity / base_liquidity) * u_factor * (1.0 + 0.1 * np.random.randn()), 50.0)

        # Spread expands with volatility
        spread = 0.05 * (volatility / base_volatility) * (1.0 + 0.05 * np.random.randn())
        bid_price = current_price - (spread / 2.0)
        ask_price = current_price + (spread / 2.0)

        records.append({
            "timestamp": timestamp,
            "seconds_in_bucket": int(timestamp),
            "mid_price": round(current_price, 4),
            "bid_price": round(bid_price, 4),
            "ask_price": round(ask_price, 4),
            "volume": round(volume, 2),
            "volatility": round(volatility, 6),
            "liquidity": round(liquidity, 2),
            "transaction_cost_bps": 1.0,
            "regime": regime,
        })

        # Price drift & stochastic return
        z = np.random.randn()
        ret = -0.5 * (volatility ** 2) * (1.0 / 60.0) + volatility * math.sqrt(1.0 / 60.0) * z
        current_price = current_price * math.exp(ret)

    df = pd.DataFrame(records)
    df.to_csv(filename, index=False)
    print(f"✓ Created Kaggle LOB sample dataset: '{filename}' ({len(df)} rows)")

if __name__ == "__main__":
    generate_kaggle_lob_dataset()
