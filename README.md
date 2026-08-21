# RECURZ Execution Engine - Frontend UI

This is a modern, single-page web application designed to act as the interactive control panel for the RECURZ Execution Engine. It visualizes the execution trajectory, provides forms for configuring order and strategy constraints, and includes a benchmark comparison view.

## Visual Design
The UI closely mirrors the design of `https://propely-trusty-home.lovable.app`, incorporating:
- Glassmorphism UI elements with `backdrop-filter`
- Dark mode theme with indigo and purple gradient accents
- Fully responsive layout using CSS Grid and Flexbox (via Tailwind CSS)
- Interactive charting via Chart.js

## Running the UI

Since the app is built with vanilla HTML/JS/CSS and imports Tailwind and Chart.js via CDNs, no build step is required. 

To view it, simply start a local static file server:

```bash
python -m http.server 8000
```
Then open `http://localhost:8000` in your web browser.

## API Contracts (For Backend Integration)
The `app.js` currently mocks the API responses for visual demonstration. To connect to the Python backend, the following endpoints should be implemented:

1. **`POST /api/run_scenario`**
   - **Request**: JSON containing order details, config, and strategy name.
   - **Response**: Array of execution steps containing `filled` (cumulative), `target` (benchmark trajectory), `participation`, and `price`.

2. **`POST /api/run_benchmark`**
   - **Request**: JSON containing order details and config.
   - **Response**: Summary metrics for TWAP, Volume-Aware, and Adaptive strategies.
