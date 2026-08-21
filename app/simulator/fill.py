from app.models.domain import FillEvent, MarketState, OrderSide


class FillEngine:
    """
    Simulates order execution fills and transaction costs based on market liquidity and order impact.

    FINANCIAL COST MODEL:
    ---------------------
    Total Execution Cost ($) = Spread Cost + Market Impact Cost + Transaction Fee Cost

    1. Spread Cost ($):
       Cost paid to cross the bid-ask spread.
       Spread Cost = 0.5 * (Ask Price - Bid Price) * Filled Quantity

    2. Market Impact Cost ($):
       Price concession caused by order size consuming depth on the order book.
       Uses Almgren-Chriss square root participation model:
       Participation Rate p = Filled Quantity / Market Volume
       Impact (bps) = gamma * sqrt(p) * (volatility / base_vol) * (base_liquidity / liquidity)^0.5
       Impact Cost ($) = Impact (bps) * 1e-4 * Mid Price * Filled Quantity

    3. Transaction Fee Cost ($):
       Broker/Exchange execution commission fee.
       Transaction Cost ($) = transaction_cost_bps * 1e-4 * Mid Price * Filled Quantity

    Fill Price:
       For BUY:  Fill Price = Mid Price + (Spread Cost + Impact Cost + Transaction Cost) / Filled Quantity
       For SELL: Fill Price = Mid Price - (Spread Cost + Impact Cost + Transaction Cost) / Filled Quantity
    """

    def __init__(
        self,
        impact_gamma: float = 15.0,  # impact scale parameter (bps)
        base_volatility: float = 0.015,
        base_liquidity: float = 10000.0,
        max_market_participation_cap: float = 0.50,  # Max % of tick volume an order can consume
    ):
        self.impact_gamma = impact_gamma
        self.base_volatility = max(base_volatility, 1e-6)
        self.base_liquidity = max(base_liquidity, 1e-6)
        self.max_market_participation_cap = max_market_participation_cap

    def simulate_fill(
        self,
        requested_quantity: float,
        market_state: MarketState,
        side: OrderSide,
    ) -> FillEvent:
        if requested_quantity <= 0 or market_state.volume <= 0:
            return FillEvent(
                requested_quantity=max(requested_quantity, 0.0),
                filled_quantity=0.0,
                fill_price=market_state.mid_price,
                spread_cost=0.0,
                impact_cost=0.0,
                transaction_cost=0.0,
                timestamp=market_state.timestamp,
            )

        # Cap fillable volume by available market volume cap
        max_fillable = market_state.volume * self.max_market_participation_cap
        filled_quantity = min(requested_quantity, max_fillable)

        if filled_quantity <= 0:
            return FillEvent(
                requested_quantity=requested_quantity,
                filled_quantity=0.0,
                fill_price=market_state.mid_price,
                spread_cost=0.0,
                impact_cost=0.0,
                transaction_cost=0.0,
                timestamp=market_state.timestamp,
            )

        # 1. Spread Cost
        half_spread = (market_state.ask_price - market_state.bid_price) / 2.0
        spread_cost = half_spread * filled_quantity

        # 2. Market Impact Cost
        participation_rate = filled_quantity / market_state.volume
        vol_factor = market_state.volatility / self.base_volatility
        liq_factor = (self.base_liquidity / market_state.liquidity) ** 0.5

        impact_bps = self.impact_gamma * (participation_rate ** 0.5) * vol_factor * liq_factor
        impact_cost = (impact_bps * 1e-4) * market_state.mid_price * filled_quantity

        # 3. Transaction Fee Cost
        transaction_cost = (market_state.transaction_cost_bps * 1e-4) * market_state.mid_price * filled_quantity

        # Calculate effective Fill Price
        total_slippage_per_share = (spread_cost + impact_cost + transaction_cost) / filled_quantity

        if side == OrderSide.BUY:
            fill_price = market_state.mid_price + total_slippage_per_share
        else:
            fill_price = market_state.mid_price - total_slippage_per_share

        return FillEvent(
            requested_quantity=round(requested_quantity, 4),
            filled_quantity=round(filled_quantity, 4),
            fill_price=round(fill_price, 4),
            spread_cost=round(spread_cost, 4),
            impact_cost=round(impact_cost, 4),
            transaction_cost=round(transaction_cost, 4),
            timestamp=market_state.timestamp,
        )
