import pytest
from app.core.database import AsyncSessionLocal, init_db
from app.models.domain import OrderSide
from app.services.run_service import RunService


@pytest.mark.asyncio
async def test_full_simulation_run_lifecycle():
    await init_db()

    async with AsyncSessionLocal() as session:
        service = RunService(session)
        metrics = await service.execute_run(
            scenario_id="normal",
            strategy_name="twap",
            order_side=OrderSide.BUY,
            quantity=500.0,
            horizon_seconds=30.0,
            seed=42,
        )

        assert metrics.run_id.startswith("run_")
        assert metrics.strategy == "twap"
        assert metrics.completion_percentage > 0.0
        assert metrics.total_execution_cost >= 0.0


@pytest.mark.asyncio
async def test_apples_to_apples_strategy_benchmark():
    await init_db()

    async with AsyncSessionLocal() as session:
        service = RunService(session)
        results = await service.compare_strategies(
            scenario_id="volatility_shock",
            order_side=OrderSide.BUY,
            quantity=500.0,
            seed=42,
            strategies=["twap", "volume_aware", "adaptive"],
        )

        assert "twap" in results
        assert "volume_aware" in results
        assert "adaptive" in results

        # All strategies must have evaluated arrival price identically
        arrival_prices = {m.arrival_price for m in results.values()}
        assert len(arrival_prices) == 1
