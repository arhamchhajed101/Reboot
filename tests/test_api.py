import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.database import init_db


@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_get_scenarios_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        scenario_ids = [s["scenario_id"] for s in data]
        assert "normal" in scenario_ids
        assert "volatility_shock" in scenario_ids


@pytest.mark.asyncio
async def test_post_runs_endpoint():
    await init_db()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        payload = {
            "scenario_id": "normal",
            "strategy": "adaptive",
            "order_side": "BUY",
            "quantity": 300.0,
            "horizon_seconds": 30.0,
            "symbol": "AAPL",
            "seed": 42,
            "max_participation_rate": 0.25,
        }
        response = await client.post("/api/runs", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "run_id" in data
        assert data["strategy"] == "adaptive"

        # Check retrieving events for this run
        run_id = data["run_id"]
        events_resp = await client.get(f"/api/runs/{run_id}/events")
        assert events_resp.status_code == 200
        events_data = events_resp.json()
        assert len(events_data["ticks"]) > 0
        assert len(events_data["decisions"]) > 0
        assert len(events_data["fills"]) > 0


@pytest.mark.asyncio
async def test_compare_runs_endpoint():
    await init_db()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        payload = {
            "scenario_id": "combined_shock",
            "order_side": "SELL",
            "quantity": 400.0,
            "horizon_seconds": 20.0,
            "seed": 99,
            "strategies": ["twap", "adaptive"],
        }
        response = await client.post("/api/runs/compare", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "benchmark_results" in data
        assert "twap" in data["benchmark_results"]
        assert "adaptive" in data["benchmark_results"]
