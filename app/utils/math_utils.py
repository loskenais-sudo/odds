"""Mathematical utilities for betting analysis.

All formulas are pure functions with no side effects.
"""


def implied_probability(odds: float) -> float:
    """
    Implied probability from decimal odds.

    implied_prob = 1 / odds
    """
    if odds <= 1.0:
        return 0.0
    return 1.0 / odds


def remove_margin(implied_probs: list[float]) -> list[float]:
    """
    Normalize implied probabilities to remove bookmaker overround.

    Divides each value by the total sum so they add up to 1.0,
    giving the 'fair' probability for each outcome.
    """
    total = sum(implied_probs)
    if total <= 0:
        return implied_probs
    return [p / total for p in implied_probs]


def devig_market(outcomes: list[tuple[str, float]]) -> dict[str, float]:
    """
    Remove the bookmaker margin from a market and return fair probabilities.

    outcomes: list of (outcome_name, decimal_odds)
    Returns: {outcome_name: fair_probability}
    """
    implied = [(name, implied_probability(price)) for name, price in outcomes]
    probs = [p for _, p in implied]
    fair = remove_margin(probs)
    return {name: fp for (name, _), fp in zip(implied, fair)}


def expected_value(estimated_prob: float, odds: float) -> float:
    """
    Expected value of a bet.

    EV = (estimated_probability × odds) − 1

    Positive EV means a profitable bet in the long run.
    EV of 0.10 = 10 cents profit per 1 unit wagered on average.
    """
    return round((estimated_prob * odds) - 1, 6)


def kelly_fraction(prob: float, odds: float) -> float:
    """
    Kelly criterion fraction.

    f* = ((b × p) − q) / b

    b = odds − 1  (net return per unit)
    p = estimated probability of winning
    q = 1 − p     (probability of losing)

    Returns 0 when Kelly suggests not betting.
    """
    b = odds - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - prob
    f = ((b * prob) - q) / b
    return max(0.0, f)


def kelly_stake(
    prob: float,
    odds: float,
    bankroll: float,
    multiplier: float = 0.25,
    max_pct: float = 0.02,
) -> float:
    """
    Recommended stake using fractional Kelly criterion.

    Applies a multiplier (default 0.25) to reduce variance,
    and caps at max_pct of bankroll for risk control.
    Returns 0 when Kelly is non-positive.
    """
    fraction = kelly_fraction(prob, odds)
    if fraction <= 0:
        return 0.0
    raw = fraction * bankroll * multiplier
    cap = bankroll * max_pct
    return round(min(raw, cap), 2)


def risk_level(ev: float, kf: float) -> str:
    """
    Classify bet risk.

    High EV or high Kelly fraction → higher variance → higher risk label.
    """
    if ev >= 0.15 or kf >= 0.08:
        return "high"
    if ev >= 0.06 or kf >= 0.03:
        return "medium"
    return "low"
