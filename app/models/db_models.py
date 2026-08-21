from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    DateTime,
    JSON,
    ForeignKey,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.domain import OrderSide, MarketRegime, RunStatus


def utc_now():
    return datetime.now(timezone.utc)


class ScenarioDB(Base):
    __tablename__ = "scenarios"

    scenario_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    config_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class RunDB(Base):
    __tablename__ = "runs"

    run_id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey("scenarios.scenario_id"), nullable=False)
    strategy = Column(String, nullable=False)
    order_side = Column(SQLEnum(OrderSide), nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    horizon = Column(Float, nullable=False)
    status = Column(SQLEnum(RunStatus), default=RunStatus.CREATED, nullable=False)
    seed = Column(Integer, nullable=False, default=42)
    configuration = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)


    ticks = relationship("MarketTickDB", back_populates="run", cascade="all, delete-orphan")
    decisions = relationship("DecisionDB", back_populates="run", cascade="all, delete-orphan")
    fills = relationship("FillDB", back_populates="run", cascade="all, delete-orphan")
    metrics = relationship("MetricsDB", back_populates="run", uselist=False, cascade="all, delete-orphan")


class MarketTickDB(Base):
    __tablename__ = "market_ticks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False, index=True)
    step = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    mid_price = Column(Float, nullable=False)
    bid_price = Column(Float, nullable=False)
    ask_price = Column(Float, nullable=False)
    spread_bps = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    liquidity = Column(Float, nullable=False)
    volatility = Column(Float, nullable=False)
    transaction_cost_bps = Column(Float, nullable=False, default=1.0)
    regime = Column(SQLEnum(MarketRegime), nullable=False)

    run = relationship("RunDB", back_populates="ticks")


class DecisionDB(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False, index=True)
    step = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    participation_rate = Column(Float, nullable=False)
    aggressiveness = Column(Float, nullable=False)
    expected_cost = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    rationale = Column(Text, nullable=True)

    run = relationship("RunDB", back_populates="decisions")


class FillDB(Base):
    __tablename__ = "fills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False, index=True)
    step = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    requested_quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, nullable=False)
    fill_price = Column(Float, nullable=False)
    spread_cost = Column(Float, nullable=False)
    impact_cost = Column(Float, nullable=False)
    transaction_cost = Column(Float, nullable=False)

    run = relationship("RunDB", back_populates="fills")


class MetricsDB(Base):
    __tablename__ = "metrics"

    run_id = Column(String, ForeignKey("runs.run_id"), primary_key=True)
    completion_percentage = Column(Float, nullable=False)
    total_execution_cost = Column(Float, nullable=False)
    total_execution_cost_bps = Column(Float, nullable=False)
    spread_cost = Column(Float, nullable=False)
    spread_cost_bps = Column(Float, nullable=False)
    impact_cost = Column(Float, nullable=False)
    impact_cost_bps = Column(Float, nullable=False)
    transaction_cost = Column(Float, nullable=False)
    transaction_cost_bps = Column(Float, nullable=False)
    implementation_shortfall = Column(Float, nullable=False)
    implementation_shortfall_bps = Column(Float, nullable=False)
    max_participation_rate = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    stability_score = Column(Float, nullable=False)
    raw_json = Column(JSON, nullable=False)

    run = relationship("RunDB", back_populates="metrics")
