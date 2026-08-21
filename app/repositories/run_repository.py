import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import (
    DecisionDB,
    FillDB,
    MarketTickDB,
    MetricsDB,
    RunDB,
    ScenarioDB,
)
from app.models.domain import (
    ExecutionDecision,
    FillEvent,
    MarketState,
    OrderSide,
    RunMetrics,
    RunStatus,
    ScenarioConfig,
)


class RunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_scenario(self, config: ScenarioConfig) -> ScenarioDB:
        existing = await self.session.get(ScenarioDB, config.scenario_id)
        if existing:
            existing.name = config.name
            existing.description = config.description
            existing.config_json = config.model_dump()
            db_scenario = existing
        else:
            db_scenario = ScenarioDB(
                scenario_id=config.scenario_id,
                name=config.name,
                description=config.description,
                config_json=config.model_dump(),
            )
            self.session.add(db_scenario)
        await self.session.commit()
        return db_scenario

    async def get_scenario(self, scenario_id: str) -> Optional[ScenarioConfig]:
        db_scenario = await self.session.get(ScenarioDB, scenario_id)
        if db_scenario:
            return ScenarioConfig(**db_scenario.config_json)
        return None

    async def create_run(
        self,
        run_id: str,
        scenario_id: str,
        strategy: str,
        order_side: OrderSide,
        symbol: str,
        quantity: float,
        horizon: float,
        seed: int = 42,
        configuration: Optional[dict] = None,
    ) -> RunDB:
        db_run = RunDB(
            run_id=run_id,
            scenario_id=scenario_id,
            strategy=strategy,
            order_side=order_side,
            symbol=symbol,
            quantity=quantity,
            horizon=horizon,
            status=RunStatus.CREATED,
            seed=seed,
            configuration=configuration or {},
        )
        self.session.add(db_run)
        await self.session.commit()
        return db_run

    async def update_run_status(
        self, run_id: str, status: RunStatus, error_message: Optional[str] = None
    ):
        db_run = await self.session.get(RunDB, run_id)
        if db_run:
            db_run.status = status
            if status == RunStatus.COMPLETED or status == RunStatus.FAILED:
                db_run.completed_at = datetime.now(timezone.utc)
            if error_message:
                db_run.error_message = error_message
            await self.session.commit()

    async def record_tick(self, run_id: str, step: int, state: MarketState):
        tick_db = MarketTickDB(
            run_id=run_id,
            step=step,
            timestamp=state.timestamp,
            mid_price=state.mid_price,
            bid_price=state.bid_price,
            ask_price=state.ask_price,
            spread_bps=state.spread_bps,
            volume=state.volume,
            liquidity=state.liquidity,
            volatility=state.volatility,
            transaction_cost_bps=state.transaction_cost_bps,
            regime=state.regime,
        )
        self.session.add(tick_db)

    async def record_decision(self, run_id: str, step: int, decision: ExecutionDecision):
        dec_db = DecisionDB(
            run_id=run_id,
            step=step,
            timestamp=decision.timestamp,
            quantity=decision.quantity,
            participation_rate=decision.participation_rate,
            aggressiveness=decision.aggressiveness,
            expected_cost=decision.expected_cost,
            risk_score=decision.risk_score,
            rationale=decision.rationale,
        )
        self.session.add(dec_db)

    async def record_fill(self, run_id: str, step: int, fill: FillEvent):
        fill_db = FillDB(
            run_id=run_id,
            step=step,
            timestamp=fill.timestamp,
            requested_quantity=fill.requested_quantity,
            filled_quantity=fill.filled_quantity,
            fill_price=fill.fill_price,
            spread_cost=fill.spread_cost,
            impact_cost=fill.impact_cost,
            transaction_cost=fill.transaction_cost,
        )
        self.session.add(fill_db)

    async def save_metrics(self, metrics: RunMetrics):
        metrics_db = MetricsDB(
            run_id=metrics.run_id,
            completion_percentage=metrics.completion_percentage,
            total_execution_cost=metrics.total_execution_cost,
            total_execution_cost_bps=metrics.total_execution_cost_bps,
            spread_cost=metrics.spread_cost,
            spread_cost_bps=metrics.spread_cost_bps,
            impact_cost=metrics.impact_cost,
            impact_cost_bps=metrics.impact_cost_bps,
            transaction_cost=metrics.transaction_cost,
            transaction_cost_bps=metrics.transaction_cost_bps,
            implementation_shortfall=metrics.implementation_shortfall,
            implementation_shortfall_bps=metrics.implementation_shortfall_bps,
            max_participation_rate=metrics.max_participation_rate,
            risk_score=metrics.risk_score,
            stability_score=metrics.stability_score,
            raw_json=metrics.model_dump(),
        )
        self.session.add(metrics_db)
        await self.session.commit()

    async def get_run_with_details(self, run_id: str) -> Optional[RunDB]:
        stmt = (
            select(RunDB)
            .where(RunDB.run_id == run_id)
            .options(
                selectinload(RunDB.ticks),
                selectinload(RunDB.decisions),
                selectinload(RunDB.fills),
                selectinload(RunDB.metrics),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
