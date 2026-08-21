import asyncio
from app.services.run_service import RunService
from app.models.domain import OrderSide
from app.core.database import init_db, AsyncSessionLocal

async def demo():
    await init_db()
    print("=" * 115)
    print(f" {'STRATEGY':<16} | {'COMPLETION %':<14} | {'IS (USD)':<12} | {'IS (bps)':<10} | {'VWAP FILL PRICE':<16} | {'TOTAL COST (bps)':<16}")
    print("=" * 115)
    
    for strat in ["TWAP", "VOLUME_AWARE", "ADAPTIVE"]:
        async with AsyncSessionLocal() as session:
            service = RunService(session)
            metrics = await service.execute_run(
                scenario_id="normal",
                strategy_name=strat,
                order_side=OrderSide.BUY,
                quantity=10000.0,
                symbol="BTC-USD",
                seed=42
            )
            print(f" {strat:<16} | {metrics.completion_percentage:>12.2f}% | ${metrics.implementation_shortfall:>10.2f} | {metrics.implementation_shortfall_bps:>8.2f} | ${metrics.vwap_fill_price:>14.4f} | {metrics.total_execution_cost_bps:>14.2f} bps")
            await session.commit()
            
    print("=" * 115)

if __name__ == "__main__":
    asyncio.run(demo())
