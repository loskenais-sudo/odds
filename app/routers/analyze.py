"""Analysis endpoints."""
from fastapi import APIRouter, Depends, HTTPException

from app.schemas.analysis import AnalysisResponse, BankrollRequest, ParlayResponse
from app.services.analysis_service import AnalysisService
from app.services.odds_service import OddsService

router = APIRouter(prefix="/analyze", tags=["Analysis"])


def get_odds_service() -> OddsService:
    return OddsService()


def get_analysis_service() -> AnalysisService:
    return AnalysisService()


@router.post("", response_model=AnalysisResponse)
async def analyze_singles(
    request: BankrollRequest,
    odds_service: OddsService = Depends(get_odds_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    """
    Analyze today's matches and return the best single bets.

    Uses consensus probability (average devigged odds across bookmakers)
    to estimate true probabilities, then calculates EV and fractional
    Kelly stakes.

    Body:
    - **bankroll**: total available capital
    - **max_daily_risk**: maximum total stake to allocate today
    """
    events = await odds_service.get_today_odds()
    if not events:
        raise HTTPException(
            status_code=404,
            detail=(
                "No events found for today. "
                "The competition may be on break or the sport key is incorrect."
            ),
        )
    return await analysis_service.analyze_singles(events, request)


@router.post("/parlays", response_model=ParlayResponse)
async def analyze_parlays(
    request: BankrollRequest,
    odds_service: OddsService = Depends(get_odds_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> ParlayResponse:
    """
    Find the best parlay combinations (doubles & triples) from today's
    positive-EV bets.

    Correlated legs (two selections from the same match) are excluded.
    Returns up to 5 best parlays ranked by EV.
    """
    events = await odds_service.get_today_odds()
    if not events:
        raise HTTPException(
            status_code=404,
            detail="No events found for today.",
        )
    return await analysis_service.analyze_parlays(events, request)
