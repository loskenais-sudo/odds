"""Service for fetching odds from The Odds API."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.config import get_settings
from app.schemas.odds import OddsEvent

log = logging.getLogger(__name__)


class OddsService:
    """
    Async client for The Odds API.

    Handles authentication, error handling, rate limits, and response parsing.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.settings.odds_api_base_url,
                params={"apiKey": self.settings.odds_api_key},
                timeout=self.settings.request_timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_today_odds(self) -> list[OddsEvent]:
        """
        Fetch odds for events starting in the next 24 hours.

        Applies a date filter after fetching to avoid extra API calls.
        """
        all_events = await self._fetch_odds()
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=24)
        today = [e for e in all_events if now <= e.commence_time <= cutoff]
        log.info(
            "Filtered to today: %d / %d events.", len(today), len(all_events)
        )
        return today

    async def get_all_events(self) -> list[OddsEvent]:
        """Fetch all upcoming events without date filter."""
        return await self._fetch_odds()

    async def _fetch_odds(self) -> list[OddsEvent]:
        client = await self._get_client()
        try:
            response = await client.get(
                f"/sports/{self.settings.sport}/odds",
                params={
                    "regions": self.settings.region,
                    "markets": self.settings.markets,
                    "oddsFormat": "decimal",
                    "dateFormat": "iso",
                },
            )
            self._log_quota(response)

            if response.status_code == 401:
                log.error("Invalid ODDS_API_KEY — check your environment variable.")
                return []
            if response.status_code == 422:
                log.error("Bad request to Odds API: %s", response.text)
                return []
            if response.status_code == 429:
                log.warning("Odds API rate limit reached.")
                return []

            response.raise_for_status()
            raw: list[dict] = response.json()
            events = [OddsEvent(**e) for e in raw]
            log.info("Fetched %d events for sport '%s'.", len(events), self.settings.sport)
            return events

        except httpx.TimeoutException:
            log.error("Odds API request timed out after %.1fs.", self.settings.request_timeout)
            return []
        except httpx.HTTPStatusError as exc:
            log.error("Odds API HTTP error %s: %s", exc.response.status_code, exc.response.text)
            return []
        except httpx.HTTPError as exc:
            log.error("Odds API connection error: %s", exc)
            return []
        except Exception as exc:
            log.error("Unexpected error fetching odds: %s", exc, exc_info=True)
            return []

    def _log_quota(self, response: httpx.Response) -> None:
        remaining = response.headers.get("x-requests-remaining", "?")
        used = response.headers.get("x-requests-used", "?")
        log.info("Odds API quota → used: %s | remaining: %s", used, remaining)
