import pytest
from datetime import datetime, timedelta, timezone
from app.core.database import init_db, AsyncSessionLocal
from app.services.run_service import RunService
from app.models.domain import OrderSide
from execution_engine.api.adapter import ExecutionEngine
from execution_engine.core.models import Order, MarketState

@pytest.mark.asyncio
async def test_backend_and_engine_integration():
    await init_db()

    # 1. Run Backend RunService
    async with AsyncSessionLocal() as session:
        service = RunService(session)
        metrics = await service.execute_run(
            scenario_id="normal",
            strategy_name="adaptive",
            order_side=OrderSide.BUY,
            quantity=1000.0,
            horizon_seconds=60.0,
            seed=42,
        )
        assert metrics.filled_quantity == 1000.0
        assert metrics.vwap_fill_price > 0.0

    # 2. Test ExecutionEngine Adapter Directly
    engine = ExecutionEngine(strategy="ADAPTIVE")
    start_t = datetime.now(timezone.utc)
    order = Order(
        id="ord_test_1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=1000.0,
        start_time=start_t,
        end_time=start_t + timedelta(seconds=60),
    )
    market_state = MarketState(
        timestamp=start_t,
        price=100.0,
        bid=99.98,
        ask=100.02,
        volume=1000.0,
        volatility=0.015,
        liquidity=10000.0,
    )
    state = engine.create_initial_state(order, market_state, total_steps=60)
    decision = engine.execute_step(order, state, market_state)
    assert decision.quantity > 0.0

    # 3. Test Benchmark Comparison
    async with AsyncSessionLocal() as session:
        service = RunService(session)
        benchmarks = await service.compare_strategies(
            scenario_id="volatility_shock",
            strategies=["twap", "volume_aware", "adaptive"],
            order_side=OrderSide.BUY,
            quantity=5000.0,
            horizon_seconds=60.0,
            seed=42,
        )
        assert len(benchmarks) == 3
        assert "twap" in benchmarks
        assert "volume_aware" in benchmarks
        assert "adaptive" in benchmarks
