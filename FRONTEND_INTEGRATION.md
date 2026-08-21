# Frontend Integration Guide — Optimal Trade Execution Backend

This guide is designed for the Frontend Engineer to integrate the React dashboard with the trade-execution simulation engine.

---

## 📡 Base URLs
- **REST API**: `http://localhost:8000/api`
- **WebSocket**: `ws://localhost:8000/api`

---

## 🔄 Run Lifecycle & States

A simulation run progresses through the following states (`RunStatus` enum):
- `CREATED`: Database record created.
- `RUNNING`: Simulation active, executing step loop, publishing events.
- `COMPLETED`: Run finished successfully, metrics calculated and persisted.
- `FAILED`: Simulation failed with error (exception logged to database).
- `CANCELLED`: Execution halted manually.

---

## 📡 REST API Contract

### 1. Health Status
- **Method & Path**: `GET /api/health`
- **Response JSON**:
```json
{
  "status": "ok",
  "service": "trade-execution-backend"
}
```

### 2. List Scenarios
- **Method & Path**: `GET /api/scenarios`
- **Response JSON**:
```json
[
  {
    "scenario_id": "normal",
    "name": "Normal Market Conditions",
    "description": "Standard baseline market environment with stable volatility and high liquidity.",
    "initial_price": 100.0,
    "volatility": 0.015,
    "liquidity": 10000.0,
    "volume": 1000.0,
    "spread": 0.04,
    "transaction_cost_bps": 1.0,
    "shock_timestamp": null,
    "volatility_multiplier": 1.0,
    "liquidity_multiplier": 1.0,
    "spread_multiplier": 1.0,
    "random_seed": 42,
    "total_steps": 60,
    "step_duration_seconds": 1.0
  }
]
```

### 3. Create & Run Simulation
- **Method & Path**: `POST /api/runs`
- **Request Body**:
```json
{
  "scenario_id": "normal",
  "strategy": "adaptive",
  "order_side": "BUY",
  "quantity": 1000.0,
  "horizon_seconds": 60.0,
  "symbol": "AAPL",
  "seed": 42,
  "max_participation_rate": 0.30
}
```
- **Response Body (`RunMetrics` JSON)**:
```json
{
  "run_id": "run_0a1b2c3d4e",
  "strategy": "adaptive",
  "order_side": "BUY",
  "total_quantity": 1000.0,
  "filled_quantity": 1000.0,
  "completion_percentage": 100.0,
  "arrival_price": 100.0,
  "vwap_fill_price": 100.27,
  "final_price": 99.96,
  "total_execution_cost": 274.45,
  "total_execution_cost_bps": 27.45,
  "spread_cost": 20.0,
  "spread_cost_bps": 2.0,
  "impact_cost": 244.45,
  "impact_cost_bps": 24.45,
  "transaction_cost": 10.0,
  "transaction_cost_bps": 1.0,
  "implementation_shortfall": 270.0,
  "implementation_shortfall_bps": 27.0,
  "max_participation_rate": 0.3,
  "risk_score": 0.02,
  "stability_score": 1.0
}
```

### 4. Get Run Status
- **Method & Path**: `GET /api/runs/{run_id}`
- **Response JSON**:
```json
{
  "run_id": "run_0a1b2c3d4e",
  "scenario_id": "normal",
  "strategy": "adaptive",
  "order_side": "BUY",
  "symbol": "AAPL",
  "quantity": 1000.0,
  "horizon": 60.0,
  "status": "COMPLETED",
  "seed": 42,
  "metrics": { ... }
}
```

### 5. Get Step-by-Step Run Events
- **Method & Path**: `GET /api/runs/{run_id}/events`
- **Response JSON**:
```json
{
  "run_id": "run_0a1b2c3d4e",
  "status": "COMPLETED",
  "ticks": [
    {
      "timestamp": 0.0,
      "mid_price": 100.0,
      "bid_price": 99.98,
      "ask_price": 100.02,
      "spread_bps": 4.0,
      "volume": 1022.4,
      "liquidity": 10000.0,
      "volatility": 0.015,
      "transaction_cost_bps": 1.0,
      "regime": "NORMAL"
    }
  ],
  "decisions": [
    {
      "timestamp": 0.0,
      "quantity": 16.67,
      "participation_rate": 0.016,
      "aggressiveness": 0.4,
      "expected_cost": 0.33,
      "risk_score": 0.25,
      "rationale": "Adaptive decision..."
    }
  ],
  "fills": [
    {
      "requested_quantity": 16.67,
      "filled_quantity": 16.67,
      "fill_price": 100.1,
      "spread_cost": 0.33,
      "impact_cost": 1.2,
      "transaction_cost": 0.17,
      "timestamp": 0.0
    }
  ],
  "metrics": { ... }
}
```

### 6. Strategy Benchmark Comparison
- **Method & Path**: `POST /api/runs/compare`
- **Request Body**:
```json
{
  "scenario_id": "volatility_shock",
  "order_side": "BUY",
  "quantity": 10000.0,
  "horizon_seconds": 60.0,
  "symbol": "AAPL",
  "seed": 42,
  "strategies": ["twap", "volume_aware", "adaptive"]
}
```
- **Response Body**:
```json
{
  "scenario_id": "volatility_shock",
  "order_side": "BUY",
  "quantity": 10000.0,
  "seed": 42,
  "benchmark_results": {
    "twap": { "run_id": "...", "vwap_fill_price": 101.50, ... },
    "volume_aware": { "run_id": "...", "vwap_fill_price": 101.35, ... },
    "adaptive": { "run_id": "...", "vwap_fill_price": 100.85, ... }
  }
}
```

---

## 🔌 WebSocket Events Stream
Establish a connection at `ws://localhost:8000/api/runs/{run_id}/stream`.
The server streams structured JSON messages as the simulation progresses.

### Message Payload Formats

#### 1. `market_update`
```json
{
  "type": "market_update",
  "run_id": "run_0a1b2c3d4e",
  "data": {
    "step": 0,
    "market_state": {
      "timestamp": 0.0,
      "mid_price": 100.0,
      "bid_price": 99.98,
      "ask_price": 100.02,
      "spread_bps": 4.0,
      "volume": 1022.4,
      "liquidity": 10000.0,
      "volatility": 0.015,
      "transaction_cost_bps": 1.0,
      "regime": "NORMAL"
    },
    "regime": "NORMAL"
  }
}
```

#### 2. `decision`
```json
{
  "type": "decision",
  "run_id": "run_0a1b2c3d4e",
  "data": {
    "step": 0,
    "decision": {
      "timestamp": 0.0,
      "quantity": 16.67,
      "participation_rate": 0.016,
      "aggressiveness": 0.4,
      "expected_cost": 0.33,
      "risk_score": 0.25,
      "rationale": "Adaptive decision..."
    }
  }
}
```

#### 3. `fill`
```json
{
  "type": "fill",
  "run_id": "run_0a1b2c3d4e",
  "data": {
    "step": 0,
    "fill": {
      "requested_quantity": 16.67,
      "filled_quantity": 16.67,
      "fill_price": 100.1,
      "spread_cost": 0.33,
      "impact_cost": 1.2,
      "transaction_cost": 0.17,
      "timestamp": 0.0
    },
    "remaining_quantity": 983.33
  }
}
```

#### 4. `run_completed`
```json
{
  "type": "run_completed",
  "run_id": "run_0a1b2c3d4e",
  "data": {
    "metrics": {
      "run_id": "run_0a1b2c3d4e",
      "strategy": "adaptive",
      "order_side": "BUY",
      "total_quantity": 1000.0,
      "filled_quantity": 1000.0,
      "completion_percentage": 100.0,
      "arrival_price": 100.0,
      "vwap_fill_price": 100.27,
      "final_price": 99.96,
      "total_execution_cost": 274.45,
      "total_execution_cost_bps": 27.45,
      "spread_cost": 20.0,
      "spread_cost_bps": 2.0,
      "impact_cost": 244.45,
      "impact_cost_bps": 24.45,
      "transaction_cost": 10.0,
      "transaction_cost_bps": 1.0,
      "implementation_shortfall": 270.0,
      "implementation_shortfall_bps": 27.0,
      "max_participation_rate": 0.3,
      "risk_score": 0.02,
      "stability_score": 1.0
    }
  }
}
```

---

## 🔄 Suggested UI Integration Sequence
1. **Configure Simulation**: Call `GET /api/scenarios` to populate dropdown list.
2. **Submit Order**: Call `POST /api/runs` and extract `run_id`.
3. **Connect WebSocket**: Instantiate `new WebSocket('ws://localhost:8000/api/runs/' + run_id + '/stream')`.
4. **Stream & Render live plots**:
   - Plot 1: Mid Price & Fill Price vs Time.
   - Plot 2: Remaining Inventory (qty) decaying over time.
   - Plot 3: Participation Rate & Market Volume vs Time.
5. **On Completion**: Render the strategy comparison dashboard using `POST /api/runs/compare` to show the benchmark chart of TWAP, Volume-Aware, and Adaptive metrics side-by-side.
