import pandas as pd
from typing import List, Optional
from app.models.domain import MarketState, MarketRegime

class HistoricalMarketReplayer:
    """
    Replays real or Kaggle-style high-frequency tick market datasets 
    (LOB / Order Book / High Frequency Trading Data).
    """

    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path

    def load_market_path(self, max_steps: Optional[int] = None) -> List[MarketState]:
        """
        Loads CSV dataset and converts each row into a MarketState tick.
        Expected/Supported CSV Columns:
        - timestamp (or step/time_id)
        - mid_price (or price / ask_price1 & bid_price1)
        - bid_price (or bid_price1)
        - ask_price (or ask_price1)
        - volume (or size / total_volume)
        - volatility (optional, default 0.015)
        - liquidity (optional, default 10000.0)
        - transaction_cost_bps (optional, default 1.0)
        """
        df = pd.read_csv(self.csv_file_path)

        if max_steps is not None:
            df = df.iloc[:max_steps]

        states: List[MarketState] = []

        for idx, row in df.iterrows():
            timestamp = float(row.get("timestamp", row.get("seconds_in_bucket", row.get("time_id", idx * 1.0))))
            
            # Mid price resolution
            if "mid_price" in row:
                mid_price = float(row["mid_price"])
            elif "price" in row:
                mid_price = float(row["price"])
            elif "bid_price1" in row and "ask_price1" in row:
                mid_price = (float(row["bid_price1"]) + float(row["ask_price1"])) / 2.0
            else:
                mid_price = 100.0

            # Bid & Ask resolution
            if "bid_price" in row and "ask_price" in row:
                bid_price = float(row["bid_price"])
                ask_price = float(row["ask_price"])
            elif "bid_price1" in row and "ask_price1" in row:
                bid_price = float(row["bid_price1"])
                ask_price = float(row["ask_price1"])
            else:
                spread = float(row.get("spread", 0.04))
                bid_price = mid_price - (spread / 2.0)
                ask_price = mid_price + (spread / 2.0)

            # Volume resolution
            volume = float(row.get("volume", row.get("total_volume", row.get("ask_size1", 1000.0))))
            volatility = float(row.get("volatility", 0.015))
            liquidity = float(row.get("liquidity", 10000.0))
            trans_cost = float(row.get("transaction_cost_bps", 1.0))

            spread_bps = ((ask_price - bid_price) / max(mid_price, 1e-6)) * 10000.0

            # Regime detection from CSV or parameters
            regime_str = str(row.get("regime", "NORMAL")).upper()
            try:
                regime = MarketRegime(regime_str)
            except ValueError:
                regime = MarketRegime.NORMAL

            state = MarketState(
                timestamp=timestamp,
                mid_price=round(mid_price, 4),
                bid_price=round(bid_price, 4),
                ask_price=round(ask_price, 4),
                spread_bps=round(spread_bps, 2),
                volume=round(volume, 2),
                liquidity=round(liquidity, 2),
                volatility=round(volatility, 6),
                transaction_cost_bps=trans_cost,
                regime=regime,
            )
            states.append(state)

        return states
