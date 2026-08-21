import json
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import settings
from app.models.domain import ScenarioConfig

PRESET_SCENARIOS: Dict[str, ScenarioConfig] = {
    "normal": ScenarioConfig(
        scenario_id="normal",
        name="Normal Market Conditions",
        description="Standard baseline market environment with stable volatility and high liquidity.",
        initial_price=100.0,
        volatility=0.015,
        liquidity=10000.0,
        volume=1000.0,
        spread=0.04,
        transaction_cost_bps=1.0,
        shock_timestamp=None,
        volatility_multiplier=1.0,
        liquidity_multiplier=1.0,
        spread_multiplier=1.0,
        random_seed=42,
        total_steps=60,
        step_duration_seconds=1.0,
    ),
    "volatility_shock": ScenarioConfig(
        scenario_id="volatility_shock",
        name="Volatility Shock Event",
        description="Sudden 3.5x spike in volatility mid-way through execution window causing bid-ask spreads to widen.",
        initial_price=100.0,
        volatility=0.015,
        liquidity=10000.0,
        volume=1000.0,
        spread=0.04,
        transaction_cost_bps=1.0,
        shock_timestamp=25.0,
        volatility_multiplier=3.5,
        liquidity_multiplier=1.0,
        spread_multiplier=2.5,
        random_seed=42,
        total_steps=60,
        step_duration_seconds=1.0,
    ),
    "liquidity_shock": ScenarioConfig(
        scenario_id="liquidity_shock",
        name="Liquidity Crunch Event",
        description="Severe market liquidity drop (75% reduction) mid-way through execution window.",
        initial_price=100.0,
        volatility=0.015,
        liquidity=10000.0,
        volume=1000.0,
        spread=0.04,
        transaction_cost_bps=1.0,
        shock_timestamp=25.0,
        volatility_multiplier=1.2,
        liquidity_multiplier=0.25,
        spread_multiplier=2.0,
        random_seed=42,
        total_steps=60,
        step_duration_seconds=1.0,
    ),
    "combined_shock": ScenarioConfig(
        scenario_id="combined_shock",
        name="Combined Volatility & Liquidity Shock",
        description="Simultaneous volatility spike (4x) and liquidity freeze (80% drop) representing extreme stress.",
        initial_price=100.0,
        volatility=0.015,
        liquidity=10000.0,
        volume=1000.0,
        spread=0.04,
        transaction_cost_bps=1.0,
        shock_timestamp=25.0,
        volatility_multiplier=4.0,
        liquidity_multiplier=0.2,
        spread_multiplier=3.5,
        random_seed=42,
        total_steps=60,
        step_duration_seconds=1.0,
    ),
}


def load_scenario(scenario_id: str, custom_scenarios_dir: Optional[str] = None) -> ScenarioConfig:
    scenarios_dir = Path(custom_scenarios_dir or settings.SCENARIOS_DIR)
    file_path = scenarios_dir / f"{scenario_id}.json"

    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return ScenarioConfig(**data)

    if scenario_id in PRESET_SCENARIOS:
        return PRESET_SCENARIOS[scenario_id]

    raise ValueError(f"Scenario '{scenario_id}' not found in directory '{scenarios_dir}' or presets.")


def list_scenarios(custom_scenarios_dir: Optional[str] = None) -> List[ScenarioConfig]:
    scenarios = dict(PRESET_SCENARIOS)
    scenarios_dir = Path(custom_scenarios_dir or settings.SCENARIOS_DIR)

    if scenarios_dir.exists():
        for p in scenarios_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = ScenarioConfig(**json.load(f))
                    scenarios[cfg.scenario_id] = cfg
            except Exception:
                continue

    return list(scenarios.values())
