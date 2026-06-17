"""Pydantic schemas for analysis requests and responses."""
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class BankrollRequest(BaseModel):
    bankroll: float
    max_daily_risk: float = 50.0

    @field_validator("bankroll")
    @classmethod
    def bankroll_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Bankroll must be positive")
        return v

    @field_validator("max_daily_risk")
    @classmethod
    def risk_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("max_daily_risk must be positive")
        return v


class SingleBet(BaseModel):
    match: str
    market: str
    selection: str
    point: Optional[float] = None
    display_market: str
    bookmaker: str
    odds: float
    estimated_probability: float
    implied_probability: float
    ev: float
    stake: float
    risk: Literal["low", "medium", "high"]
    reason: str


class ParlayLeg(BaseModel):
    match: str
    market: str
    selection: str
    point: Optional[float] = None
    display_market: str
    bookmaker: str
    odds: float
    estimated_probability: float


class ParlayBet(BaseModel):
    legs: list[ParlayLeg]
    combined_odds: float
    estimated_probability: float
    ev: float
    stake: float
    risk: Literal["low", "medium", "high"]
    reason: str


class AnalysisResponse(BaseModel):
    timestamp: str
    sport: str
    bankroll: float
    total_events_analyzed: int
    best_singles: list[SingleBet]
    all_singles: list[SingleBet]
    total_singles_found: int
    allocated_stake: float
    remaining_risk: float


class ParlayResponse(BaseModel):
    timestamp: str
    sport: str
    bankroll: float
    best_parlays: list[ParlayBet]
    total_parlays_analyzed: int
