"""
Layer 3 – Math Engine
Expected Value, Kelly Criterion, Bayesian updating, log returns.
All pure functions — no I/O.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class TradeDecision:
    should_trade: bool
    side: str                 # "YES" or "NO"
    ai_probability: float
    market_price: float
    ev: float
    kelly_fraction: float
    position_size_usd: float
    reasoning: str


def expected_value(p_win: float, profit: float, loss: float) -> float:
    """
    EV = P(win) * profit - P(lose) * loss
    profit and loss are in dollar terms per $1 staked.
    """
    p_lose = 1.0 - p_win
    return p_win * profit - p_lose * loss


def kelly_fraction(p: float, b: float) -> float:
    """
    Full Kelly: f* = (p*b - q) / b
      p = probability of winning
      b = net odds (payout per $1 staked, i.e. (1 - price) / price for binary market)
      q = 1 - p
    """
    q = 1.0 - p
    if b <= 0:
        return 0.0
    f = (p * b - q) / b
    return max(0.0, f)


def bayesian_update(prior: float, likelihood_given_h: float, likelihood_given_not_h: float) -> float:
    """
    P(H|E) = P(E|H) * P(H) / P(E)
    Used to update probability when new evidence arrives mid-trade.
    """
    p_e = likelihood_given_h * prior + likelihood_given_not_h * (1 - prior)
    if p_e == 0:
        return prior
    posterior = (likelihood_given_h * prior) / p_e
    return max(0.01, min(0.99, posterior))


def log_return(p0: float, p1: float) -> float:
    """
    logreturn = ln(P1 / P0)
    Additive across compounding periods; avoids arithmetic return distortion.
    """
    if p0 <= 0 or p1 <= 0:
        return 0.0
    return math.log(p1 / p0)


def evaluate_trade(
    ai_probability: float,
    yes_price: float,
    no_price: float,
    bankroll_usd: float,
    ev_threshold: float,
    kelly_fraction_multiplier: float,
    max_position_usd: float,
) -> TradeDecision:
    """
    Decide whether to trade YES or NO, and how much.

    For a binary prediction market:
      - YES bet: pay `yes_price`, win $1 if YES resolves
      - NO  bet: pay `no_price`,  win $1 if NO  resolves
    """
    no_probability = 1.0 - ai_probability

    # Net odds for each side: (1 - price) / price
    yes_odds = (1.0 - yes_price) / yes_price if yes_price > 0 else 0.0
    no_odds = (1.0 - no_price) / no_price if no_price > 0 else 0.0

    # EV in cents per dollar staked
    yes_ev = expected_value(ai_probability, yes_odds, 1.0)
    no_ev = expected_value(no_probability, no_odds, 1.0)

    best_side = "YES" if yes_ev >= no_ev else "NO"
    best_ev = yes_ev if best_side == "YES" else no_ev
    best_p = ai_probability if best_side == "YES" else no_probability
    best_odds = yes_odds if best_side == "YES" else no_odds
    best_price = yes_price if best_side == "YES" else no_price

    if best_ev < ev_threshold:
        return TradeDecision(
            should_trade=False,
            side=best_side,
            ai_probability=ai_probability,
            market_price=best_price,
            ev=best_ev,
            kelly_fraction=0.0,
            position_size_usd=0.0,
            reasoning=f"EV {best_ev:.2%} below threshold {ev_threshold:.2%}",
        )

    raw_kelly = kelly_fraction(best_p, best_odds)
    scaled_kelly = raw_kelly * kelly_fraction_multiplier
    position_usd = min(bankroll_usd * scaled_kelly, max_position_usd)

    return TradeDecision(
        should_trade=position_usd >= 1.0,
        side=best_side,
        ai_probability=ai_probability,
        market_price=best_price,
        ev=best_ev,
        kelly_fraction=scaled_kelly,
        position_size_usd=round(position_usd, 2),
        reasoning=(
            f"EV={best_ev:.2%}, Kelly={scaled_kelly:.2%}, "
            f"AI prob={best_p:.2%} vs market {best_price:.2%}"
        ),
    )


def portfolio_log_pnl(positions: list[dict]) -> float:
    """
    Aggregate portfolio P&L using log returns.
    Each position dict: {"entry_price": float, "current_price": float, "size_usd": float}
    """
    returns = np.array(
        [log_return(p["entry_price"], p["current_price"]) * p["size_usd"] for p in positions]
    )
    return float(np.sum(returns))
