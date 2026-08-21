"""RECURZ Execution Engine.

Optimal Adaptive Algorithmic Trade Execution Subsystem.
"""

__version__ = "1.0.0"

from execution_engine.core.models import (
    Order,
    OrderSide,
    MarketState,
    ExecutionConfig,
    ExecutionState,
    ExecutionDecision,
    RegimeType,
    ReasonCode,
)
from execution_engine.core.features import (
    FeatureExtractor,
    MarketFeatures,
)
from execution_engine.core.regimes import (
    RegimeDetector,
    RegimeClassification,
)
from execution_engine.core.objectives import (
    ObjectiveScorer,
    CandidateScore,
)
from execution_engine.risk.constraints import (
    RiskConstraint,
)
from execution_engine.risk.controller import (
    RiskController,
    RiskValidationResult,
)
from execution_engine.strategies.base import StrategyBase
from execution_engine.strategies.twap import TWAPStrategy
from execution_engine.strategies.volume_aware import VolumeAwareStrategy
from execution_engine.strategies.adaptive import AdaptiveStrategy
from execution_engine.evaluation.metrics import (
    StrategyMetrics,
    MetricsCalculator,
)
from execution_engine.evaluation.scenario import (
    ScenarioGenerator,
    ScenarioType,
)
from execution_engine.evaluation.benchmark import (
    BenchmarkRunner,
    BenchmarkReport,
    BenchmarkStepRecord,
    StrategyRunResult,
)
from execution_engine.api.adapter import (
    ExecutionEngine,
    get_strategy,
    STRATEGY_REGISTRY,
)

__all__ = [
    "Order",
    "OrderSide",
    "MarketState",
    "ExecutionConfig",
    "ExecutionState",
    "ExecutionDecision",
    "RegimeType",
    "ReasonCode",
    "FeatureExtractor",
    "MarketFeatures",
    "RegimeDetector",
    "RegimeClassification",
    "ObjectiveScorer",
    "CandidateScore",
    "RiskConstraint",
    "RiskController",
    "RiskValidationResult",
    "StrategyBase",
    "TWAPStrategy",
    "VolumeAwareStrategy",
    "AdaptiveStrategy",
    "StrategyMetrics",
    "MetricsCalculator",
    "ScenarioGenerator",
    "ScenarioType",
    "BenchmarkRunner",
    "BenchmarkReport",
    "BenchmarkStepRecord",
    "StrategyRunResult",
    "ExecutionEngine",
    "get_strategy",
    "STRATEGY_REGISTRY",
]
