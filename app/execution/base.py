from abc import ABC, abstractmethod
from app.models.domain import ExecutionContext, ExecutionDecision


class ExecutionStrategy(ABC):
    """
    Abstract Base Class for trade execution strategies.
    The Quant Engineer implements custom adaptive algorithms conforming to this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the strategy identifier name."""
        pass

    @abstractmethod
    def decide(self, context: ExecutionContext) -> ExecutionDecision:
        """
        Calculates the execution decision (target quantity, aggressiveness, expected cost)
        given the current ExecutionContext.
        """
        pass
