import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Optimal Trade Execution Simulator"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # SQLite fallback if PostgreSQL is not running
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./trade_simulator.db"
    )

    SCENARIOS_DIR: str = os.getenv("SCENARIOS_DIR", "./scenarios")

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()
