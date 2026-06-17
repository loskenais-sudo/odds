"""Application configuration using Pydantic Settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # The Odds API
    odds_api_key: str
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"

    # Sport & region
    sport: str = "soccer_fifa_world_cup"
    region: str = "eu"
    markets: str = "h2h,totals,spreads"

    # Kelly criterion
    default_kelly_multiplier: float = 0.25

    # Risk management
    max_stake_pct_single: float = 0.02   # 2% bankroll per single
    max_stake_pct_parlay: float = 0.005  # 0.5% bankroll per parlay
    min_ev_threshold: float = 0.03       # Minimum 3% EV to consider a bet

    # HTTP
    request_timeout: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
