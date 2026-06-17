"""Betting analysis service.

Mathematical pipeline:
1. For each event × market, collect odds from all bookmakers.
2. Devig each bookmaker's market (remove house margin via normalisation).
3. Average the fair probabilities across bookmakers → consensus estimate.
4. Find the best available odds for each outcome across all bookmakers.
5. EV = (consensus_prob × best_odds) − 1.
6. Filter EV ≥ threshold, rank, apply fractional Kelly for stake sizing.
"""
import logging
from datetime import datetime, timezone
from itertools import combinations
from typing import Optional

from app.config import get_settings
from app.schemas.analysis import (
    AnalysisResponse,
    BankrollRequest,
    ParlayBet,
    ParlayLeg,
    ParlayResponse,
    SingleBet,
)
from app.schemas.odds import OddsEvent
from app.utils.math_utils import (
    devig_market,
    expected_value,
    format_market,
    implied_probability,
    kelly_fraction,
    kelly_stake,
    risk_level,
)

log = logging.getLogger(__name__)

MARKET_LABELS: dict[str, str] = {
    "h2h":     "1X2 (Match Result)",
    "totals":  "Over/Under Goals",
    "spreads": "Asian Handicap",
}


class AnalysisService:

    def __init__(self) -> None:
        self.settings = get_settings()

    # ── Public API ───────────────────────────────────────────────────────────

    async def analyze_singles(
        self,
        events: list[OddsEvent],
        request: BankrollRequest,
    ) -> AnalysisResponse:
        """Return best single bets ordered by EV, respecting max_daily_risk."""
        candidates = self._extract_candidates(events)
        positive = [c for c in candidates if c.ev >= self.settings.min_ev_threshold]
        positive.sort(key=lambda x: x.ev, reverse=True)

        allocated = 0.0
        final: list[SingleBet] = []

        for bet in positive:
            stake = kelly_stake(
                prob=bet.estimated_probability,
                odds=bet.odds,
                bankroll=request.bankroll,
                multiplier=self.settings.default_kelly_multiplier,
                max_pct=self.settings.max_stake_pct_single,
            )
            if stake <= 0:
                continue
            remaining_budget = request.max_daily_risk - allocated
            if remaining_budget < 0.5:
                break
            stake = min(stake, remaining_budget)
            final.append(bet.model_copy(update={"stake": round(stake, 2)}))
            allocated += stake

        return AnalysisResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sport=self.settings.sport,
            bankroll=request.bankroll,
            total_events_analyzed=len(events),
            best_singles=final[:10],
            all_singles=positive,
            total_singles_found=len(positive),
            allocated_stake=round(allocated, 2),
            remaining_risk=round(request.max_daily_risk - allocated, 2),
        )

    async def analyze_parlays(
        self,
        events: list[OddsEvent],
        request: BankrollRequest,
    ) -> ParlayResponse:
        """Build the best parlay combinations (doubles & triples) from top singles."""
        candidates = self._extract_candidates(events)
        positive = [c for c in candidates if c.ev >= self.settings.min_ev_threshold]
        positive.sort(key=lambda x: x.ev, reverse=True)

        # Limit pool to avoid combinatorial explosion
        pool = positive[:15]
        parlays: list[ParlayBet] = []

        for size in (2, 3):
            for combo in combinations(pool, size):
                if self._is_correlated(list(combo)):
                    continue
                parlay = self._build_parlay(list(combo), request)
                if parlay and parlay.ev >= self.settings.min_ev_threshold:
                    parlays.append(parlay)

        parlays.sort(key=lambda x: x.ev, reverse=True)

        return ParlayResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sport=self.settings.sport,
            bankroll=request.bankroll,
            best_parlays=parlays[:5],
            total_parlays_analyzed=len(parlays),
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _extract_candidates(self, events: list[OddsEvent]) -> list[SingleBet]:
        candidates: list[SingleBet] = []
        for event in events:
            for market_key in ("h2h", "totals", "spreads"):
                candidates.extend(self._analyze_market(event, market_key))
        return candidates

    def _analyze_market(
        self,
        event: OddsEvent,
        market_key: str,
    ) -> list[SingleBet]:
        """
        For one event + market, compute fair probabilities and EV per outcome.

        - Collects odds from every bookmaker offering this market.
        - Devigs each bookmaker's lines to get fair probabilities.
        - Averages the fair probs across bookmakers (consensus estimate).
        - Identifies the best available odds across all bookmakers.
        - EV = (consensus_prob × best_odds) − 1.
        """
        # Gather (bookmaker_title, [(outcome_name, price, point), ...]) pairs
        bk_markets: list[tuple[str, list[tuple[str, float, float | None]]]] = []
        for bookmaker in event.bookmakers:
            for market in bookmaker.markets:
                if market.key != market_key:
                    continue
                outcomes = [(o.name, o.price, o.point) for o in market.outcomes]
                if len(outcomes) >= 2:
                    bk_markets.append((bookmaker.title, outcomes))

        if not bk_markets:
            return []

        # Consensus fair probabilities (average devigged across all bookmakers)
        all_fair: dict[str, list[float]] = {}
        for _bk, outcomes in bk_markets:
            name_price = [(name, price) for name, price, _ in outcomes]
            for name, prob in devig_market(name_price).items():
                all_fair.setdefault(name, []).append(prob)

        consensus: dict[str, float] = {
            name: sum(probs) / len(probs)
            for name, probs in all_fair.items()
        }

        # Best odds per outcome, which bookmaker offers them, and the line value
        best: dict[str, tuple[float, str, float | None]] = {}
        for bk_title, outcomes in bk_markets:
            for name, price, point in outcomes:
                if name not in best or price > best[name][0]:
                    best[name] = (price, bk_title, point)

        bets: list[SingleBet] = []
        market_label = MARKET_LABELS.get(market_key, market_key)

        for outcome_name, (odds, bk_title, point) in best.items():
            est_prob = consensus.get(outcome_name)
            if not est_prob or est_prob <= 0:
                continue

            impl_prob = implied_probability(odds)
            ev = expected_value(est_prob, odds)
            kf = kelly_fraction(est_prob, odds)
            edge = est_prob - impl_prob
            display = format_market(market_key, outcome_name, point)

            reason = (
                f"{market_label}: estimated prob {est_prob:.1%} vs "
                f"implied {impl_prob:.1%} (edge {edge:+.1%}). "
                f"At odds {odds:.2f}, EV = {ev:.2%} per unit wagered."
            )

            bets.append(
                SingleBet(
                    match=event.match_name,
                    market=market_key,
                    selection=outcome_name,
                    point=point,
                    display_market=display,
                    bookmaker=bk_title,
                    odds=round(odds, 3),
                    estimated_probability=round(est_prob, 4),
                    implied_probability=round(impl_prob, 4),
                    ev=round(ev, 4),
                    stake=0.0,
                    risk=risk_level(ev, kf),
                    reason=reason,
                )
            )

        return bets

    @staticmethod
    def _is_correlated(legs: list[SingleBet]) -> bool:
        """Two legs from the same match are considered correlated."""
        matches = [leg.match for leg in legs]
        return len(matches) != len(set(matches))

    def _build_parlay(
        self,
        legs: list[SingleBet],
        request: BankrollRequest,
    ) -> Optional[ParlayBet]:
        if len(legs) < 2:
            return None

        combined_odds = 1.0
        combined_prob = 1.0
        for leg in legs:
            combined_odds *= leg.odds
            combined_prob *= leg.estimated_probability

        ev = expected_value(combined_prob, combined_odds)
        kf = kelly_fraction(combined_prob, combined_odds)
        stake = kelly_stake(
            prob=combined_prob,
            odds=combined_odds,
            bankroll=request.bankroll,
            multiplier=self.settings.default_kelly_multiplier,
            max_pct=self.settings.max_stake_pct_parlay,
        )

        n = len(legs)
        selections = " + ".join(f"{leg.selection} ({leg.match})" for leg in legs)
        reason = (
            f"{n}-leg parlay — {selections}. "
            f"Combined odds {combined_odds:.2f}, "
            f"estimated prob {combined_prob:.2%}, EV {ev:.2%}. "
            f"Each leg independently shows positive expected value."
        )

        return ParlayBet(
            legs=[
                ParlayLeg(
                    match=leg.match,
                    market=leg.market,
                    selection=leg.selection,
                    point=leg.point,
                    display_market=leg.display_market,
                    bookmaker=leg.bookmaker,
                    odds=leg.odds,
                    estimated_probability=leg.estimated_probability,
                )
                for leg in legs
            ],
            combined_odds=round(combined_odds, 3),
            estimated_probability=round(combined_prob, 4),
            ev=round(ev, 4),
            stake=round(stake, 2),
            risk=risk_level(ev, kf),
            reason=reason,
        )
