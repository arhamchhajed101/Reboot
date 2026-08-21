"""Abstract base strategy class defining the standard execution interface.
"""

from abc import ABC, abstractmethod
from execution_engine.core.models import (
    Order,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    ExecutionDecision,
)


class StrategyBase(ABC):
    """Abstract base contract for all execution strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier."""
        pass

    @abstractmethod
    def decide(
        self,
        order: Order,
        state: ExecutionState,
        market_state: MarketState,
        config: ExecutionConfig,
    ) -> ExecutionDecision:
        """Generate child-order execution decision for the current interval.

        Parameters:
            order: Institutional parent order.
            state: Current execution state (remaining quantity, current step, etc.).
            market_state: Current interval market state observation.
            config: Execution and risk configuration parameters.

        Returns:
            ExecutionDecision containing the sanitized child quantity and explainability metadata.
        """
        pass
