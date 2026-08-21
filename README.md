# Optimal Trade Execution — Backend & Market Simulator

A high-performance, simulated institutional trade-execution system built with **FastAPI**, **Pydantic v2**, **NumPy**, **SQLAlchemy 2.x**, **PostgreSQL**, and **WebSockets**.

---

## 🏛 Architecture Overview

```
Frontend (React)
   ↓ REST / WebSocket
FastAPI Application (app.main)
   ↓
Run Service (app.services.run_service)
   ├── Market Simulator (app.simulator.market)
   ├── Execution Strategy Plugin Interface (app.execution)
   ├── Fill Engine & Cost Model (app.simulator.fill)
   └── Evaluation Engine (app.evaluation.engine)
          ↓
       PostgreSQL / SQLite Database
```

---

## 📐 Core Interfaces & Financial Formulas

### 1. Quant Strategy Interface
Custom execution strategies implement the `ExecutionStrategy` base class:
```python
class ExecutionStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    def decide(self, context: ExecutionContext) -> ExecutionDecision: pass
```

### 2. Transaction Cost & Market Impact Model
Total Execution Cost ($) = `Spread Cost` + `Market Impact Cost` + `Transaction Fee`

- **Spread Cost ($)**: `0.5 * (Ask Price - Bid Price) * Filled Quantity`
- **Market Impact Cost ($)** (Almgren-Chriss square root participation model):
  $$\text{Impact (bps)} = \gamma \times \sqrt{p} \times \frac{\sigma}{\sigma_0} \times \sqrt{\frac{L_0}{L}}$$
  $$\text{Impact Cost } (\$) = \text{Impact (bps)} \times 10^{-4} \times S_{\text{mid}} \times Q_{\text{filled}}$$
  where $p = \frac{Q_{\text{filled}}}{\text{Volume}}$, $\sigma$ is volatility, and $L$ is liquidity.
- **Transaction Fee ($)**: $\text{transaction\_cost\_bps} \times 10^{-4} \times S_{\text{mid}} \times Q_{\text{filled}}$

### 3. Implementation Shortfall (IS)
Measures opportunity loss against instantaneous fill at arrival mid-price $P_{\text{arrival}}$:
- **BUY**: $\text{IS } (\$) = (\text{Filled Notional} + \text{Unfilled Qty} \times P_{\text{final}}) - (Q_{\text{total}} \times P_{\text{arrival}})$
- **SELL**: $\text{IS } (\$) = (Q_{\text{total}} \times P_{\text{arrival}}) - (\text{Filled Notional} + \text{Unfilled Qty} \times P_{\text{final}})$
- **IS (bps)**: $\frac{\text{IS } (\$)}{Q_{\text{total}} \times P_{\text{arrival}}} \times 10,000$

---

## 🚀 Quick Start (Local Setup)

### 1. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
pytest -v
```

### 3. Start Local API Server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

### 4. Docker Compose Setup (with PostgreSQL)
```bash
docker-compose up --build
```

---

## 📡 API Endpoints

- `GET  /api/health` — System status
- `GET  /api/scenarios` — List available market scenarios (`normal`, `volatility_shock`, `liquidity_shock`, `combined_shock`)
- `POST /api/runs` — Execute execution simulation run
- `GET  /api/runs/{run_id}` — Get run status & metrics
- `GET  /api/runs/{run_id}/events` — Get step-by-step market ticks, decisions, and fills
- `POST /api/runs/compare` — Perform apples-to-apples benchmark comparison across strategies (`twap`, `volume_aware`, `adaptive`) under identical random seed & market path
- `WS   /api/runs/{run_id}/stream` — Real-time event streaming over WebSocket
