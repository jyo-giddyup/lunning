"""Synthetic pro-stage athlete dataset.

Sampled from the amateur generator restricted to draft-eligible sports
(football / mens_basketball / baseball), then augmented with draft
position and pro outcomes. Calibration is hand-set against public
reporting:

- NFL rookie scale: ~$30M–$40M (4yr) for QBs at top-of-1st, dropping
  steeply through round 7 (~$4M/4yr).
- NBA rookie scale: ~$50M (4yr) for #1 overall, ~$8M for late-1st,
  G-League level for round 2.
- MLB signing bonus: ~$8M for #1 overall, falling under $200K beyond
  round 5.

Heavy log-normal noise on top so the models have to learn a regression
rather than memorise.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data import DataConfig as AmateurDataConfig
from ..data import generate as generate_amateur

DRAFT_ELIGIBLE_SPORTS = ("football", "mens_basketball", "baseball")

# Approximate maximum draft round per sport.
MAX_ROUND = {"football": 7, "mens_basketball": 2, "baseball": 20}


@dataclass
class ProDataConfig:
    n_amateur: int = 30_000          # upstream amateur cohort size
    seed: int = 11
    floor_drafted: int = 400         # require at least this many draftees


def generate(config: ProDataConfig | None = None) -> pd.DataFrame:
    """Return a DataFrame of drafted athletes with pro-stage outcomes."""
    cfg = config or ProDataConfig()

    # Pull a large amateur cohort and keep only the drafted athletes.
    amateur = generate_amateur(AmateurDataConfig(n_athletes=cfg.n_amateur, seed=cfg.seed))
    drafted = amateur[amateur["drafted"]].copy()
    drafted = drafted[drafted["sport"].isin(DRAFT_ELIGIBLE_SPORTS)].reset_index(drop=True)

    if len(drafted) < cfg.floor_drafted:
        raise ValueError(
            f"only {len(drafted)} drafted athletes from n_amateur={cfg.n_amateur}; "
            "increase n_amateur"
        )

    rng = np.random.default_rng(cfg.seed + 1)
    n = len(drafted)

    # Draft round and within-round pick.
    sport_arr = drafted["sport"].to_numpy()
    rounds = np.empty(n, dtype=np.int64)
    picks = np.empty(n, dtype=np.int64)

    perf = drafted["performance_score"].to_numpy()
    perf_pct = (perf - perf.min()) / max(1e-9, perf.max() - perf.min())

    for i in range(n):
        max_r = MAX_ROUND[sport_arr[i]]
        # Higher perf -> earlier round, with noise.
        round_score = perf_pct[i] + rng.normal(0, 0.25)
        # Map round_score to round 1..max_r (1 = highest)
        r = int(np.clip(round((1 - round_score) * (max_r - 1) + 1), 1, max_r))
        rounds[i] = r
        # Within-round pick rank (lower number = better)
        picks[i] = int(rng.integers(1, 33 if sport_arr[i] == "football" else
                                     16 if sport_arr[i] == "mens_basketball" else 41))

    # Combine score 0–100, weakly correlated with performance + size.
    combine_score = np.clip(
        0.6 * drafted["performance_score"].to_numpy()
        + 0.4 * (50 + rng.normal(0, 12, size=n)),
        0,
        100,
    )

    # Pro contract value (USD over rookie deal length).
    sport_base = {"football": 8_500_000, "mens_basketball": 14_000_000, "baseball": 1_200_000}
    base = np.array([sport_base[s] for s in sport_arr], dtype=np.float64)
    # Earlier rounds and earlier picks → exponentially larger contracts.
    slot_factor = np.exp(-0.55 * (rounds - 1)) * np.exp(-0.04 * (picks - 1))
    perf_factor = 0.5 + 0.012 * combine_score
    noise = rng.lognormal(0.0, 0.45, size=n)
    contract_value = np.clip(base * slot_factor * perf_factor * noise, 0, None)

    # Career length (years), log-normal centered on something position-aware.
    sport_career_base = {"football": 3.3, "mens_basketball": 5.0, "baseball": 5.5}
    career_mean = np.array([sport_career_base[s] for s in sport_arr])
    career = rng.lognormal(np.log(career_mean) - 0.4 * (rounds - 1) / 6.0, 0.55)
    career = np.clip(career, 0.0, 22.0)

    # All-Star probability, binary.
    all_star_logit = (
        -3.0
        - 0.55 * (rounds - 1)
        - 0.05 * (picks - 1)
        + 0.04 * combine_score
        + rng.normal(0, 0.4, n)
    )
    all_star_prob = 1 / (1 + np.exp(-all_star_logit))
    all_star = rng.binomial(1, all_star_prob).astype(bool)

    # Top-tier agent signed pre-draft.
    agent_logit = (
        -1.8
        - 0.4 * (rounds - 1)
        + 0.025 * combine_score
        + 0.6 * np.isin(sport_arr, ["football", "mens_basketball"]).astype(float)
        + rng.normal(0, 0.3, n)
    )
    agent_prob = 1 / (1 + np.exp(-agent_logit))
    agent_signed = rng.binomial(1, agent_prob).astype(bool)

    # Carry forward amateur features that are still meaningful at draft time.
    out = drafted[[
        "sport", "position", "conference", "year",
        "starter", "performance_score",
        "instagram_followers", "tiktok_followers", "twitter_followers",
    ]].copy()
    out["draft_round"] = rounds
    out["draft_pick"] = picks
    out["combine_score"] = np.round(combine_score, 2)
    out["pro_contract_value"] = np.round(contract_value, 2)
    out["pro_career_length"] = np.round(career, 2)
    out["pro_all_star"] = all_star
    out["agent_signed"] = agent_signed
    return out


FEATURE_COLUMNS = [
    "sport", "position", "conference", "year",
    "starter", "performance_score",
    "instagram_followers", "tiktok_followers", "twitter_followers",
    "draft_round", "draft_pick", "combine_score",
]

TARGET_COLUMNS = [
    "pro_contract_value",
    "pro_career_length",
    "pro_all_star",
    "agent_signed",
]
