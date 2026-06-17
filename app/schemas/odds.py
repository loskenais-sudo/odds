"""Pydantic schemas for The Odds API responses."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class Outcome(BaseModel):
    name: str
    price: float
    point: Optional[float] = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 1.0:
            raise ValueError("Decimal odds must be greater than 1.0")
        return round(v, 4)


class Market(BaseModel):
    key: str
    last_update: Optional[datetime] = None
    outcomes: list[Outcome]


class Bookmaker(BaseModel):
    key: str
    title: str
    last_update: Optional[datetime] = None
    markets: list[Market]


class OddsEvent(BaseModel):
    id: str
    sport_key: str
    sport_title: str
    commence_time: datetime
    home_team: str
    away_team: str
    bookmakers: list[Bookmaker] = []

    @property
    def match_name(self) -> str:
        return f"{self.home_team} vs {self.away_team}"
