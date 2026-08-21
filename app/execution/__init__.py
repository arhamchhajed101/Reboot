from typing import Dict, Type
from app.execution.base import ExecutionStrategy
from app.execution.twap import TWAPStrategy
from app.execution.volume_aware import VolumeAwareStrategy
from app.execution.adaptive import AdaptiveStrategy

STRATEGY_REGISTRY: Dict[str, Type[ExecutionStrategy]] = {
    "twap": TWAPStrategy,
    "volume_aware": VolumeAwareStrategy,
    "adaptive": AdaptiveStrategy,
}


def get_strategy(strategy_name: str) -> ExecutionStrategy:
    name_lower = strategy_name.lower()
    if name_lower not in STRATEGY_REGISTRY:
        raise ValueError(
            f"Strategy '{strategy_name}' is invalid. Choose from: {list(STRATEGY_REGISTRY.keys())}"
        )
    return STRATEGY_REGISTRY[name_lower]()
