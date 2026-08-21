# Frontend Integration Guide — Optimal Trade Execution
> **Version**: 2.0 | **Backend**: FastAPI + WebSocket | **Base URL**: `http://localhost:8000`

---

## 🗂 Table of Contents
1. [Project Architecture](#architecture)
2. [Base URLs & Environment](#environment)
3. [Run Lifecycle & States](#lifecycle)
4. [REST API Reference](#rest-api)
5. [WebSocket Streaming](#websocket)
6. [Data Types & Enums](#data-types)
7. [UI Integration Flow](#ui-flow)
8. [Chart Data Mapping](#charts)
9. [Error Handling](#errors)
10. [CORS & Auth Notes](#cors)

---

## 1. Project Architecture <a name="architecture"></a>

```
React Frontend (Port 3000)
    │
    ├── REST (HTTP/JSON)  ──►  FastAPI Backend (Port 8000)
    │                              │
    └── WebSocket (WS)   ──►      ├── Market Simulator (GBM / Kaggle CSV)
                                  ├── Execution Strategies (TWAP / Vol-Aware / Adaptive)
                                  ├── Fill Engine (Almgren-Chriss impact model)
                                  ├── Evaluation Engine (IS / VWAP / Risk / Stability)
                                  └── PostgreSQL / SQLite Database
```

---

## 2. Base URLs & Environment <a name="environment"></a>

| Environment | REST API Base            | WebSocket Base                |
|-------------|--------------------------|-------------------------------|
| Local Dev   | `http://localhost:8000/api` | `ws://localhost:8000/api`  |
| Docker      | `http://backend:8000/api`  | `ws://backend:8000/api`    |
| Production  | `https://api.yourdomain.com/api` | `wss://api.yourdomain.com/api` |

---

## 3. Run Lifecycle & States <a name="lifecycle"></a>

A simulation run transitions through the following states:

```
CREATED ──► RUNNING ──► COMPLETED
                   └──► FAILED
                   └──► CANCELLED
```

| Status      | Description                                                  |
|-------------|--------------------------------------------------------------|
| `CREATED`   | Run record created in DB. Execution not yet started.         |
| `RUNNING`   | Simulation active. WebSocket streaming is live.              |
| `COMPLETED` | Execution finished. Final metrics saved.                     |
| `FAILED`    | Execution error occurred. `error_message` field set.         |
| `CANCELLED` | Manually cancelled (future feature).                         |

---

## 4. REST API Reference <a name="rest-api"></a>

---

### `GET /api/health`

**Purpose**: Verify backend is running.

**Response**:
```json
{
  "status": "ok",
  "service": "trade-execution-backend"
}
```

---

### `GET /api/scenarios`

**Purpose**: Fetch all available market scenarios.

**Response** (`Array<ScenarioSummary>`):
```json
[
  {
    "scenario_id": "normal",
    "name": "Normal Market Conditions",
    "description": "Stable baseline with standard volatility and high liquidity.",
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
    "total_steps": 60,
    "step_duration_seconds": 1.0
  },
  {
    "scenario_id": "volatility_shock",
    "name": "Volatility Shock",
    "description": "Mid-session volatility spike (3.5× multiplier at t=30s).",
    "shock_timestamp": 30.0,
    "volatility_multiplier": 3.5,
    "liquidity_multiplier": 1.0
  },
  {
    "scenario_id": "liquidity_shock",
    "name": "Liquidity Shock",
    "description": "Severe liquidity drought (20% of normal depth) at t=20s.",
    "shock_timestamp": 20.0,
    "liquidity_multiplier": 0.2
  },
  {
    "scenario_id": "combined_shock",
    "name": "Combined Crisis",
    "description": "Simultaneous volatility spike + liquidity drought.",
    "shock_timestamp": 30.0,
    "volatility_multiplier": 3.5,
    "liquidity_multiplier": 0.2
  }
]
```

**UI Usage**: Populate a `<Select>` dropdown on the simulation config form.

---

### `POST /api/runs`

**Purpose**: Create and immediately execute a simulation run.

**Request Body**:
```json
{
  "scenario_id": "volatility_shock",
  "strategy": "adaptive",
  "order_side": "BUY",
  "quantity": 10000.0,
  "horizon_seconds": 60.0,
  "symbol": "AAPL",
  "seed": 42,
  "max_participation_rate": 0.30
}
```

| Field                   | Type    | Required | Description                                      |
|-------------------------|---------|----------|--------------------------------------------------|
| `scenario_id`           | string  | ✅       | One of: `normal`, `volatility_shock`, `liquidity_shock`, `combined_shock` |
| `strategy`              | string  | ✅       | One of: `twap`, `volume_aware`, `adaptive`       |
| `order_side`            | string  | ✅       | `"BUY"` or `"SELL"`                              |
| `quantity`              | float   | ✅       | Total shares to execute (must be > 0)            |
| `horizon_seconds`       | float   | ✅       | Total execution window in seconds                |
| `symbol`                | string  | ❌       | Stock ticker (display only, default `"STOCK"`)   |
| `seed`                  | int     | ❌       | Random seed for deterministic replay (default 42)|
| `max_participation_rate`| float   | ❌       | Max % of market volume per step (default 0.30)   |

**Response** (`RunMetrics`):
```json
{
  "run_id": "run_a1b2c3d4e5",
  "strategy": "adaptive",
  "order_side": "BUY",
  "total_quantity": 10000.0,
  "filled_quantity": 10000.0,
  "completion_percentage": 100.0,
  "arrival_price": 100.0,
  "vwap_fill_price": 100.37,
  "final_price": 101.02,
  "total_execution_cost": 1274.55,
  "total_execution_cost_bps": 12.75,
  "spread_cost": 200.0,
  "spread_cost_bps": 2.0,
  "impact_cost": 1044.55,
  "impact_cost_bps": 10.45,
  "transaction_cost": 30.0,
  "transaction_cost_bps": 0.30,
  "implementation_shortfall": 3700.0,
  "implementation_shortfall_bps": 37.0,
  "max_participation_rate": 0.30,
  "risk_score": 0.14,
  "stability_score": 0.93
}
```

**HTTP Status Codes**:
- `201 Created` — Run completed successfully.
- `400 Bad Request` — Invalid inputs (check `detail` field).
- `422 Unprocessable Entity` — Validation failure.
- `500 Internal Server Error` — Simulation engine error.

---

### `GET /api/runs/{run_id}`

**Purpose**: Poll run status and retrieve summary metrics.

**Response**:
```json
{
  "run_id": "run_a1b2c3d4e5",
  "scenario_id": "volatility_shock",
  "strategy": "adaptive",
  "order_side": "BUY",
  "symbol": "AAPL",
  "quantity": 10000.0,
  "horizon": 60.0,
  "status": "COMPLETED",
  "seed": 42,
  "error_message": null,
  "metrics": { ... }
}
```

---

### `GET /api/runs/{run_id}/events`

**Purpose**: Fetch the full step-by-step event log after a run completes (for historical replay / post-run chart rendering).

**Response** (all arrays aligned by step index):
```json
{
  "run_id": "run_a1b2c3d4e5",
  "status": "COMPLETED",
  "ticks": [
    {
      "timestamp": 0.0,
      "mid_price": 100.0,
      "bid_price": 99.98,
      "ask_price": 100.02,
      "spread_bps": 4.0,
      "volume": 1024.3,
      "liquidity": 10000.0,
      "volatility": 0.015,
      "transaction_cost_bps": 1.0,
      "regime": "NORMAL"
    },
    ...
  ],
  "decisions": [
    {
      "timestamp": 0.0,
      "quantity": 166.7,
      "participation_rate": 0.163,
      "aggressiveness": 0.4,
      "expected_cost": 3.33,
      "risk_score": 0.14,
      "rationale": "Adaptive decision: regime=NORMAL, vol_mult=1.00, liq_mult=1.00, urgency=1.00."
    },
    ...
  ],
  "fills": [
    {
      "requested_quantity": 166.7,
      "filled_quantity": 166.7,
      "fill_price": 100.08,
      "spread_cost": 1.67,
      "impact_cost": 6.85,
      "transaction_cost": 1.67,
      "timestamp": 0.0
    },
    ...
  ],
  "metrics": { ... }
}
```

---

### `POST /api/runs/compare`

**Purpose**: Run an apples-to-apples strategy benchmark across the same market scenario and seed.

**Request Body**:
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

**Response**:
```json
{
  "scenario_id": "volatility_shock",
  "order_side": "BUY",
  "quantity": 10000.0,
  "seed": 42,
  "benchmark_results": {
    "twap": {
      "run_id": "run_xxx",
      "strategy": "twap",
      "filled_quantity": 10000.0,
      "vwap_fill_price": 101.50,
      "total_execution_cost": 3182.91,
      "total_execution_cost_bps": 31.83,
      "implementation_shortfall_bps": 150.5,
      "risk_score": 0.21,
      "stability_score": 0.99
    },
    "volume_aware": { ... },
    "adaptive": { ... }
  }
}
```

**UI Usage**: Render this data as the **Strategy Comparison Bar Chart / Radar Chart** on the benchmarking dashboard panel.

---

## 5. WebSocket Streaming <a name="websocket"></a>

Connect immediately after calling `POST /api/runs` with the returned `run_id`.

```javascript
const ws = new WebSocket(`ws://localhost:8000/api/runs/${run_id}/stream`);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case 'market_update': handleMarketTick(msg.data);   break;
    case 'decision':      handleDecision(msg.data);     break;
    case 'fill':          handleFill(msg.data);         break;
    case 'run_completed': handleCompletion(msg.data);   break;
  }
};
```

### Message Types

#### `market_update`
```json
{
  "type": "market_update",
  "run_id": "run_a1b2c3d4e5",
  "data": {
    "step": 5,
    "market_state": {
      "timestamp": 5.0,
      "mid_price": 100.42,
      "bid_price": 100.40,
      "ask_price": 100.44,
      "spread_bps": 4.0,
      "volume": 987.3,
      "liquidity": 10000.0,
      "volatility": 0.015,
      "transaction_cost_bps": 1.0,
      "regime": "NORMAL"
    },
    "regime": "NORMAL"
  }
}
```

#### `decision`
```json
{
  "type": "decision",
  "run_id": "run_a1b2c3d4e5",
  "data": {
    "step": 5,
    "decision": {
      "timestamp": 5.0,
      "quantity": 166.7,
      "participation_rate": 0.169,
      "aggressiveness": 0.40,
      "expected_cost": 3.33,
      "risk_score": 0.14,
      "rationale": "Adaptive decision: regime=NORMAL..."
    }
  }
}
```

#### `fill`
```json
{
  "type": "fill",
  "run_id": "run_a1b2c3d4e5",
  "data": {
    "step": 5,
    "fill": {
      "requested_quantity": 166.7,
      "filled_quantity": 166.7,
      "fill_price": 100.50,
      "spread_cost": 1.67,
      "impact_cost": 6.85,
      "transaction_cost": 1.67,
      "timestamp": 5.0
    },
    "remaining_quantity": 8166.5
  }
}
```

#### `run_completed`
```json
{
  "type": "run_completed",
  "run_id": "run_a1b2c3d4e5",
  "data": {
    "metrics": {
      "run_id": "run_a1b2c3d4e5",
      "strategy": "adaptive",
      "order_side": "BUY",
      "total_quantity": 10000.0,
      "filled_quantity": 10000.0,
      "completion_percentage": 100.0,
      "arrival_price": 100.0,
      "vwap_fill_price": 100.37,
      "final_price": 101.02,
      "total_execution_cost": 1274.55,
      "total_execution_cost_bps": 12.75,
      "implementation_shortfall": 3700.0,
      "implementation_shortfall_bps": 37.0,
      "risk_score": 0.14,
      "stability_score": 0.93
    }
  }
}
```

---

## 6. Data Types & Enums <a name="data-types"></a>

### `OrderSide`
```ts
type OrderSide = "BUY" | "SELL";
```

### `RunStatus`
```ts
type RunStatus = "CREATED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
```

### `MarketRegime`
```ts
type MarketRegime = "NORMAL" | "VOLATILITY_SHOCK" | "LIQUIDITY_SHOCK" | "COMBINED_SHOCK";
```

### Strategy Names
```ts
type StrategyName = "twap" | "volume_aware" | "adaptive";
```

### Regime → UI Badge Color Mapping
| Regime             | Color Token        | Label              |
|--------------------|--------------------|--------------------|
| `NORMAL`           | `#4CAF82` (green)  | ● Normal           |
| `VOLATILITY_SHOCK` | `#F59E0B` (amber)  | ⚠ Vol Shock        |
| `LIQUIDITY_SHOCK`  | `#EF4444` (red)    | 🔻 Liquidity Shock |
| `COMBINED_SHOCK`   | `#7C3AED` (purple) | ⚡ Combined Crisis |

---

## 7. UI Integration Flow <a name="ui-flow"></a>

### Recommended Step-by-Step Integration

```
Step 1: Load Scenarios
  GET /api/scenarios  →  Populate scenario dropdown

Step 2: Configure Order
  User fills: symbol, side, quantity, horizon, strategy, seed

Step 3: Submit Order
  POST /api/runs  →  Returns { run_id, metrics }

Step 4: Open WebSocket
  ws://localhost:8000/api/runs/{run_id}/stream
  → Begin live chart updates

Step 5: Stream & Render
  On 'market_update'  → Append to price chart
  On 'fill'           → Update inventory decay bar + cost accumulator
  On 'decision'       → Show strategy rationale tooltip
  On 'run_completed'  → Render final scorecard metrics

Step 6: Compare Strategies
  POST /api/runs/compare  →  Render strategy comparison chart
```

---

## 8. Chart Data Mapping <a name="charts"></a>

### Chart 1: Live Price Feed
| WebSocket Field               | Chart Axis / Series       |
|-------------------------------|---------------------------|
| `market_state.timestamp`      | X-axis (seconds)          |
| `market_state.mid_price`      | Line: Mid Price           |
| `fill.fill_price`             | Scatter: Fill Price       |
| `market_state.regime`         | Background band color     |

### Chart 2: Inventory Decay
| Field                         | Chart Representation      |
|-------------------------------|---------------------------|
| `fill.remaining_quantity`     | Area chart decaying to 0  |
| `fill.filled_quantity`        | Stacked bar fill progress |

### Chart 3: Cost Accumulation
| Field                         | Chart Representation      |
|-------------------------------|---------------------------|
| `fill.spread_cost`            | Stacked area: Spread      |
| `fill.impact_cost`            | Stacked area: Impact      |
| `fill.transaction_cost`       | Stacked area: Transaction |

### Chart 4: Regime Timeline
| Field                         | Chart Representation       |
|-------------------------------|----------------------------|
| `market_state.regime`         | Color-coded horizontal bar |
| `market_state.volatility`     | Line overlay               |
| `market_state.volume`         | Bar chart overlay          |

### Chart 5: Strategy Benchmark (Post-run)
| `benchmark_results[strategy]` | Chart Representation      |
|-------------------------------|---------------------------|
| `total_execution_cost_bps`    | Grouped bar chart         |
| `implementation_shortfall_bps`| Grouped bar chart         |
| `stability_score`             | Radar / spider chart      |
| `risk_score`                  | Radar / spider chart      |

---

## 9. Error Handling <a name="errors"></a>

All error responses follow this format:
```json
{
  "detail": "Human-readable error message"
}
```

| HTTP Code | Cause                                                    |
|-----------|----------------------------------------------------------|
| `400`     | Invalid `strategy`, `scenario_id`, `quantity <= 0`, etc |
| `404`     | `run_id` not found in database                          |
| `422`     | Pydantic validation failure (missing/wrong type fields) |
| `500`     | Internal simulation engine failure                       |

**WebSocket Disconnection**: If the server disconnects mid-stream (e.g. simulation error), attempt reconnect once and poll `GET /api/runs/{run_id}` for final status.

---

## 10. CORS & Auth Notes <a name="cors"></a>

- **CORS**: The backend currently allows all origins (`*`) in development. Configure `CORS_ORIGINS` env var for production.
- **Auth**: No authentication is implemented (hackathon scope). All endpoints are open.
- **Content-Type**: Always send `Content-Type: application/json` on POST requests.

---

## Appendix: Recommended React Component Map

```
App
├── Layout
│   ├── Sidebar (scenario + order config form)
│   └── MainCanvas
│       ├── LivePriceChart         (Chart 1 — WebSocket driven)
│       ├── InventoryDecayChart    (Chart 2 — WebSocket driven)
│       ├── CostAccumulationChart  (Chart 3 — WebSocket driven)
│       ├── RegimeTimeline         (Chart 4 — WebSocket driven)
│       ├── MetricsScorecard       (POST /runs → run_completed)
│       └── BenchmarkPanel         (POST /runs/compare)
```

---

*Last updated: 2026-08-22 | Backend version: main branch @ arhamchhajed101/Reboot*
