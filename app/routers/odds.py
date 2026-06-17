"""Odds endpoints."""
from fastapi import APIRouter, Depends

from app.schemas.odds import OddsEvent
from app.services.odds_service import OddsService

router = APIRouter(prefix="/odds", tags=["Odds"])


def get_odds_service() -> OddsService:
    return OddsService()


@router.get("/today", response_model=list[OddsEvent])
async def get_today_odds(
    service: OddsService = Depends(get_odds_service),
) -> list[OddsEvent]:
    """
    Fetch all odds for today's events (next 24 hours).

    Returns raw structured odds from The Odds API.
    """
    return await service.get_today_odds()


@router.get("/all", response_model=list[OddsEvent])
async def get_all_odds(
    service: OddsService = Depends(get_odds_service),
) -> list[OddsEvent]:
    """Fetch all upcoming events for the configured sport (no date filter)."""
    return await service.get_all_events()
