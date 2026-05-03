"""Synthetic NIL athlete dataset.

The generative process is intentionally hand-crafted so the downstream
models have signal to learn. Distributions are loosely calibrated to
public NIL reporting (heavy right tail in valuation, dominated by a
small number of QBs / star basketball players at P5 schools).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SPORTS = [
    "football",
    "mens_basketball",
    "womens_basketball",
    "baseball",
    "softball",
    "mens_soccer",
    "womens_soccer",
    "volleyball",
    "gymnastics",
    "track",
]

# Approximate NIL premium per sport (dollar multiplier on a base).
SPORT_MULT = {
    "football": 4.5,
    "mens_basketball": 3.8,
    "womens_basketball": 1.9,
    "baseball": 1.2,
    "softball": 1.1,
    "mens_soccer": 0.7,
    "womens_soccer": 0.8,
    "volleyball": 1.0,
    "gymnastics": 1.4,
    "track": 0.6,
}

CONFERENCES = ["SEC", "Big_Ten", "Big_12", "ACC", "Pac_12", "Big_East", "AAC", "MWC", "FCS", "D2"]
CONF_MULT = {
    "SEC": 2.4,
    "Big_Ten": 2.1,
    "Big_12": 1.7,
    "ACC": 1.6,
    "Pac_12": 1.4,
    "Big_East": 1.3,
    "AAC": 0.9,
    "MWC": 0.7,
    "FCS": 0.4,
    "D2": 0.2,
}

POSITIONS_BY_SPORT = {
    "football": ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "K"],
    "mens_basketball": ["PG", "SG", "SF", "PF", "C"],
    "womens_basketball": ["PG", "SG", "SF", "PF", "C"],
    "baseball": ["P", "C", "IF", "OF"],
    "softball": ["P", "C", "IF", "OF"],
    "mens_soccer": ["GK", "DEF", "MID", "FWD"],
    "womens_soccer": ["GK", "DEF", "MID", "FWD"],
    "volleyball": ["OH", "MB", "S", "L"],
    "gymnastics": ["AA", "VT", "UB", "BB", "FX"],
    "track": ["sprint", "distance", "field"],
}

POSITION_PREMIUM = {
    "QB": 3.2,
    "WR": 1.5,
    "RB": 1.4,
    "PG": 2.1,
    "SG": 1.7,
    "SF": 1.6,
    "C": 1.3,
}

YEARS = ["FR", "SO", "JR", "SR", "GR"]
YEAR_MULT = {"FR": 0.7, "SO": 0.95, "JR": 1.15, "SR": 1.2, "GR": 1.1}


@dataclass
class DataConfig:
    n_athletes: int = 5000
    seed: int = 7


def _draw_followers(rng: np.random.Generator, n: int, scale: float) -> np.ndarray:
    """Log-normal social follower counts with a heavy tail."""
    base = rng.lognormal(mean=8.5, sigma=1.6, size=n)
    return np.clip(base * scale, 50, 8_000_000).astype(np.int64)


def generate(config: DataConfig | None = None) -> pd.DataFrame:
    cfg = config or DataConfig()
    rng = np.random.default_rng(cfg.seed)
    n = cfg.n_athletes

    sport = rng.choice(SPORTS, size=n, p=_sport_probs())
    conference = rng.choice(CONFERENCES, size=n, p=_conf_probs())
    year = rng.choice(YEARS, size=n, p=[0.27, 0.27, 0.22, 0.18, 0.06])
    starter = rng.binomial(1, 0.42, size=n).astype(bool)
    performance = np.clip(rng.normal(55, 18, size=n), 0, 100)

    position = np.array([
        rng.choice(POSITIONS_BY_SPORT[s]) for s in sport
    ])

    ig = _draw_followers(rng, n, scale=1.0)
    tw = _draw_followers(rng, n, scale=0.4)
    tt = _draw_followers(rng, n, scale=0.7)

    # Star athletes get correlated bumps across platforms.
    star_mask = rng.random(n) < 0.04
    ig[star_mask] = (ig[star_mask] * rng.uniform(8, 25, star_mask.sum())).astype(np.int64)
    tt[star_mask] = (tt[star_mask] * rng.uniform(6, 20, star_mask.sum())).astype(np.int64)

    sport_m = np.array([SPORT_MULT[s] for s in sport])
    conf_m = np.array([CONF_MULT[c] for c in conference])
    pos_m = np.array([POSITION_PREMIUM.get(p, 1.0) for p in position])
    year_m = np.array([YEAR_MULT[y] for y in year])
    starter_m = np.where(starter, 1.6, 0.85)
    perf_m = 0.4 + 0.012 * performance  # 0.4 .. 1.6

    follow_signal = np.log1p(ig) * 0.7 + np.log1p(tt) * 0.5 + np.log1p(tw) * 0.3
    base = 90.0 * sport_m * conf_m * pos_m * year_m * starter_m * perf_m
    noise = rng.lognormal(mean=0.0, sigma=0.55, size=n)
    valuation = np.clip(base * np.exp(follow_signal * 0.18) * noise, 0, None)

    # Deal count ~ Poisson driven directly by features (clean signal).
    sport_deal_factor = np.array([
        {"football": 1.4, "mens_basketball": 1.2, "womens_basketball": 0.6,
         "baseball": 0.4, "softball": 0.3, "mens_soccer": 0.2, "womens_soccer": 0.3,
         "volleyball": 0.4, "gymnastics": 0.5, "track": 0.2}[s]
        for s in sport
    ])
    conf_deal_factor = np.array([
        {"SEC": 1.0, "Big_Ten": 0.9, "Big_12": 0.7, "ACC": 0.6, "Pac_12": 0.5,
         "Big_East": 0.4, "AAC": 0.2, "MWC": 0.1, "FCS": -0.2, "D2": -0.4}[c]
        for c in conference
    ])
    lam = np.exp(
        -1.4
        + 0.22 * np.log1p(ig) / np.log(10)   # per decade of IG followers
        + 0.12 * np.log1p(tt) / np.log(10)
        + 0.45 * starter.astype(float)
        + 0.010 * performance
        + 0.6 * sport_deal_factor
        + 0.5 * conf_deal_factor
    )
    lam = np.clip(lam, 0.05, 35)
    deal_count = rng.poisson(lam=lam)

    # Tier from valuation quantiles (fixed thresholds for stability).
    tier = pd.cut(
        valuation,
        bins=[-1, 1_500, 15_000, 150_000, np.inf],
        labels=["low", "mid", "high", "elite"],
    ).astype(str)

    # Transfer-portal probability: lower starter share, low performance, FR/SO bias.
    portal_logit = (
        -1.6
        - 0.9 * starter.astype(float)
        + 0.018 * (60 - performance)
        + np.where(np.isin(year, ["FR", "SO"]), 0.5, -0.2)
        + rng.normal(0, 0.3, n)
    )
    portal_prob = 1 / (1 + np.exp(-portal_logit))
    in_portal = rng.binomial(1, portal_prob).astype(bool)

    # Draft probability: only football / men's basketball plausibly draftable.
    draft_eligible = np.isin(sport, ["football", "mens_basketball", "baseball"])
    draft_logit = (
        -3.5
        + 0.05 * performance
        + 0.7 * starter.astype(float)
        + 0.6 * np.isin(year, ["JR", "SR", "GR"]).astype(float)
        + 0.4 * np.isin(position, ["QB", "PG", "SG"]).astype(float)
        + rng.normal(0, 0.5, n)
    )
    draft_prob = 1 / (1 + np.exp(-draft_logit))
    drafted = (rng.binomial(1, draft_prob) & draft_eligible).astype(bool)

    df = pd.DataFrame({
        "athlete_id": np.arange(n),
        "sport": sport,
        "position": position,
        "conference": conference,
        "year": year,
        "starter": starter,
        "performance_score": np.round(performance, 2),
        "instagram_followers": ig,
        "tiktok_followers": tt,
        "twitter_followers": tw,
        # targets
        "nil_valuation_usd": np.round(valuation, 2),
        "deal_count_12mo": deal_count,
        "tier": tier,
        "in_transfer_portal": in_portal,
        "drafted": drafted,
    })
    return df


def _sport_probs() -> list[float]:
    raw = np.array([1.6, 0.6, 0.55, 0.9, 0.85, 0.75, 0.75, 0.65, 0.4, 1.2])
    return (raw / raw.sum()).tolist()


def _conf_probs() -> list[float]:
    raw = np.array([1.4, 1.4, 1.2, 1.2, 1.0, 0.8, 0.7, 0.6, 0.9, 0.6])
    return (raw / raw.sum()).tolist()


FEATURE_COLUMNS = [
    "sport",
    "position",
    "conference",
    "year",
    "starter",
    "performance_score",
    "instagram_followers",
    "tiktok_followers",
    "twitter_followers",
]

TARGET_COLUMNS = [
    "nil_valuation_usd",
    "deal_count_12mo",
    "tier",
    "in_transfer_portal",
    "drafted",
]
