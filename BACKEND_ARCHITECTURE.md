# Backend Architecture & Mathematical Specifications

This document outlines the core architectural components, financial metrics, and modeling logic implemented in the trade-execution engine.

---

## 🏛 1. High-Level Control Flow & Request Lifecycle

```
API Client Request
       │
       ▼ (1. Request Validation via Pydantic)
   POST /api/runs (CreateRunRequest)
       │
       ▼ (2. Load Scenario & Setup DB Connection)
   RunService.execute_run()
       │
       ▼ (3. Generate Market Path)
   MarketSimulator.generate_market_path()
       │
       ▼ (4. Core Step Loop - Iterate ticks within Horizon window)
   For each step in market_path:
       ├─► 4.1 Create ExecutionContext
       ├─► 4.2 Strategy decides target quantity: ExecutionStrategy.decide()
       ├─► 4.3 Validate & cap target quantity: min(quantity, remaining_qty)
       ├─► 4.4 Simulate fill: FillEngine.simulate_fill()
       ├─► 4.5 Accumulate costs and decrement remaining inventory
       └─► 4.6 Broadcast event over WebSockets: event_bus.broadcast()
       │
       ▼ (5. Evaluate overall run performance)
   EvaluationEngine.evaluate_run()
       │
       ▼ (6. Persist results in DB)
   RunRepository.save_metrics()
       │
       ▼ (7. Final status transition)
   Set status to COMPLETED & broadcast run_completed
```

---

## 📐 2. Financial Modeling & Equations

### Market Impact Model
Uses the Almgren-Chriss square-root participation model.
- **Participation Rate**:
  $$p_t = \frac{Q_{\text{filled}, t}}{V_{\text{market}, t}}$$
- **Dynamic Impact (bps)**:
  $$\text{Impact Bps}_t = \gamma \times \sqrt{p_t} \times \left( \frac{\sigma_t}{\sigma_0} \right) \times \sqrt{\frac{L_0}{L_t}}$$
  where:
  - $\gamma$ (`impact_gamma`): Baseline impact scaling coefficient (default = 15 bps).
  - $\sigma_t$ (`volatility`): Current step volatility.
  - $\sigma_0$ (`base_volatility`): Scenario base volatility parameter.
  - $L_t$ (`liquidity`): Current step liquidity.
  - $L_0$ (`base_liquidity`): Scenario base liquidity parameter.
- **Impact Cost ($)**:
  $$\text{Impact Cost}_t = \text{Impact Bps}_t \times 10^{-4} \times S_{\text{mid}, t} \times Q_{\text{filled}, t}$$

---

### Cost Breakdown
- **Spread Cost ($)**:
  $$\text{Spread Cost}_t = 0.5 \times (S_{\text{ask}, t} - S_{\text{bid}, t}) \times Q_{\text{filled}, t}$$
- **Transaction Cost ($)**:
  $$\text{Transaction Cost}_t = \text{transaction\_cost\_bps} \times 10^{-4} \times S_{\text{mid}, t} \times Q_{\text{filled}, t}$$
- **Fill Price ($)**:
  - **BUY**: $S_{\text{mid}, t} + \frac{\text{Spread Cost}_t + \text{Impact Cost}_t + \text{Transaction Cost}_t}{Q_{\text{filled}, t}}$
  - **SELL**: $S_{\text{mid}, t} - \frac{\text{Spread Cost}_t + \text{Impact Cost}_t + \text{Transaction Cost}_t}{Q_{\text{filled}, t}}$

---

### Implementation Shortfall (IS)
Measures the opportunity cost and slippage of the execution program against instant execution at the arrival price:
- **BUY Order**:
  $$\text{IS} = \sum_{t} (P_{\text{fill}, t} \times Q_{\text{filled}, t}) + (Q_{\text{total}} - Q_{\text{filled}}) \times S_{\text{final}} - (Q_{\text{total}} \times S_{\text{arrival}})$$
- **SELL Order**:
  $$\text{IS} = (Q_{\text{total}} \times S_{\text{arrival}}) - \left( \sum_{t} (P_{\text{fill}, t} \times Q_{\text{filled}, t}) + (Q_{\text{total}} - Q_{\text{filled}}) \times S_{\text{final}} \right)$$

---

## 📈 3. Metrics, Risk, & Stability Scores

- **Risk Score**:
  Proxy based on the volatility of the mid-price during the execution horizon:
  $$\text{Risk Score} = \min \left( 1.0, \frac{\text{Std}(\{S_{\text{mid}, t}\})}{S_{\text{arrival}}} \times 10.0 \right)$$
- **Stability Score**:
  Measures the smoothness/uniformity of the order execution pace (standard deviation of participation rates):
  $$\text{Stability Score} = \max \left( 0.0, 1.0 - 2.0 \times \text{Std}(\{p_t\}) \right)$$
  *(Uniform TWAP results in 1.0; highly erratic/bursty trading approach 0.0)*.
