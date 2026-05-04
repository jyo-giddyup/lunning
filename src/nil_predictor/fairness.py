"""Fairness metrics — ISO/IEC TR 24027:2021.

Computes group-wise gaps for binary, multiclass, and regression
targets, plus a single PASS/FAIL determination against declared
thresholds. The grouping schema reflects the synthetic dataset:

    conference_tier  P5 (SEC, Big_Ten, Big_12, ACC, Pac_12) vs.
                     G5 (Big_East, AAC, MWC) vs.
                     subdiv (FCS, D2)

    gender_proxy     "men"   (mens_basketball, mens_soccer, baseball,
                              football)
                     "women" (womens_basketball, womens_soccer,
                              softball, volleyball, gymnastics)
                     "mixed" (track)

    sport            individual sport (per-sport gaps tracked in
                     fairness.json; not yet enforced as a CI gate —
                     real-data thresholds tightened in next iteration)

Real data should override these maps by passing custom group_fns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

P5 = {"SEC", "Big_Ten", "Big_12", "ACC", "Pac_12"}
G5 = {"Big_East", "AAC", "MWC"}
SUBDIV = {"FCS", "D2"}

MEN_SPORTS = {"mens_basketball", "mens_soccer", "baseball", "football"}
WOMEN_SPORTS = {"womens_basketball", "womens_soccer", "softball",
                "volleyball", "gymnastics"}


def conference_tier(conf: str) -> str:
    if conf in P5:
        return "P5"
    if conf in G5:
        return "G5"
    if conf in SUBDIV:
        return "subdiv"
    return "other"


def gender_proxy(sport: str) -> str:
    if sport in MEN_SPORTS:
        return "men"
    if sport in WOMEN_SPORTS:
        return "women"
    return "mixed"


def _safe_max_minus_min(values: list[float]) -> float:
    finite = [v for v in values if np.isfinite(v)]
    if len(finite) < 2:
        return 0.0
    return float(max(finite) - min(finite))


def demographic_parity_gap(
    df: pd.DataFrame, *, prediction: str, group: str
) -> dict[str, Any]:
    """Max selection-rate − min selection-rate across groups.

    For binary `prediction` (bool/0-1). Skips groups with < 30 samples.
    """
    rates: dict[str, float] = {}
    counts: dict[str, int] = {}
    for g, sub in df.groupby(group):
        if len(sub) < 30:
            continue
        rates[str(g)] = float(np.mean(sub[prediction].astype(float)))
        counts[str(g)] = int(len(sub))
    return {
        "metric": "demographic_parity_gap",
        "prediction": prediction,
        "group": group,
        "rates": rates,
        "counts": counts,
        "gap": _safe_max_minus_min(list(rates.values())),
    }


def equal_opportunity_gap(
    df: pd.DataFrame, *, prediction: str, label: str, group: str
) -> dict[str, Any]:
    """Max TPR − min TPR across groups (for the positive class)."""
    tprs: dict[str, float] = {}
    counts: dict[str, int] = {}
    for g, sub in df.groupby(group):
        positives = sub[sub[label] == True]  # noqa: E712
        if len(positives) < 30:
            continue
        tprs[str(g)] = float(np.mean(positives[prediction].astype(float)))
        counts[str(g)] = int(len(positives))
    return {
        "metric": "equal_opportunity_gap",
        "prediction": prediction,
        "label": label,
        "group": group,
        "tpr": tprs,
        "counts_positive": counts,
        "gap": _safe_max_minus_min(list(tprs.values())),
    }


def regression_gap(
    df: pd.DataFrame, *, prediction: str, label: str, group: str
) -> dict[str, Any]:
    """Per-group |mean predicted − mean actual| spread."""
    bias: dict[str, float] = {}
    counts: dict[str, int] = {}
    for g, sub in df.groupby(group):
        if len(sub) < 30:
            continue
        bias[str(g)] = float(np.mean(sub[prediction]) - np.mean(sub[label]))
        counts[str(g)] = int(len(sub))
    return {
        "metric": "regression_bias_gap",
        "prediction": prediction,
        "label": label,
        "group": group,
        "mean_bias": bias,
        "counts": counts,
        "gap": _safe_max_minus_min(list(bias.values())),
    }


# ---------------------------------------------------------------------------
# Declared thresholds (also surfaced in MODEL_CARD.md). A fairness CI gate
# fails the build when any of these are exceeded. Per-sport metrics are
# computed and serialised in fairness.json but are not in this dict yet —
# the synthetic generator produces large by-design per-sport gaps; real-data
# thresholds will be added once real data lands.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "drafted_dp_gap_conference_tier": 0.30,
    "drafted_eo_gap_conference_tier": 0.30,
    "portal_dp_gap_conference_tier": 0.20,
    "tier_dp_gap_conference_tier": 0.30,  # any class
    "valuation_bias_gap_gender_proxy_log10": 0.40,
}


@dataclass
class FairnessReport:
    metrics: list[dict[str, Any]] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)
    violations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "thresholds": self.thresholds,
            "violations": self.violations,
            "metrics": self.metrics,
        }


def _check(report: FairnessReport, key: str, gap: float) -> None:
    threshold = report.thresholds.get(key)
    if threshold is None:
        return
    if gap > threshold:
        report.violations.append({"check": key, "gap": gap, "threshold": threshold})


def evaluate(
    df: pd.DataFrame,
    *,
    thresholds: dict[str, float] | None = None,
    conf_fn: Callable[[str], str] = conference_tier,
    sport_fn: Callable[[str], str] = gender_proxy,
) -> FairnessReport:
    """Compute the standard fairness suite on an evaluated holdout.

    Expects columns: sport, conference,
        drafted, drafted_pred, portal_pred, tier_pred, tier (label),
        valuation_pred, valuation_label.
    """
    df = df.copy()
    df["_conference_tier"] = df["conference"].map(conf_fn)
    df["_gender_proxy"] = df["sport"].map(sport_fn)

    rep = FairnessReport(thresholds=dict(thresholds or DEFAULT_THRESHOLDS))

    if {"drafted_pred", "drafted"}.issubset(df.columns):
        m = demographic_parity_gap(df, prediction="drafted_pred", group="_conference_tier")
        rep.metrics.append(m)
        _check(rep, "drafted_dp_gap_conference_tier", m["gap"])

        m = equal_opportunity_gap(df, prediction="drafted_pred", label="drafted",
                                  group="_conference_tier")
        rep.metrics.append(m)
        _check(rep, "drafted_eo_gap_conference_tier", m["gap"])

        # Per-sport breakdowns (resolves MODEL_CARD risk-register TODO).
        m = demographic_parity_gap(df, prediction="drafted_pred", group="sport")
        rep.metrics.append({**m, "note": "per-sport draft selection rate"})

        m = equal_opportunity_gap(df, prediction="drafted_pred", label="drafted",
                                  group="sport")
        rep.metrics.append({**m, "note": "per-sport draft TPR"})

    if "portal_pred" in df.columns:
        m = demographic_parity_gap(df, prediction="portal_pred", group="_conference_tier")
        rep.metrics.append(m)
        _check(rep, "portal_dp_gap_conference_tier", m["gap"])

        m = demographic_parity_gap(df, prediction="portal_pred", group="sport")
        rep.metrics.append({**m, "note": "per-sport portal selection rate"})

    if "tier_pred" in df.columns:
        # treat the top tier as a positive selection signal
        df["_tier_top"] = df["tier_pred"].astype(str).isin({"high", "elite"})
        m = demographic_parity_gap(df, prediction="_tier_top", group="_conference_tier")
        rep.metrics.append({**m, "note": "top-tier (high|elite) selection rate"})
        _check(rep, "tier_dp_gap_conference_tier", m["gap"])

        m = demographic_parity_gap(df, prediction="_tier_top", group="sport")
        rep.metrics.append({**m, "note": "per-sport top-tier selection rate"})

    if {"valuation_pred", "valuation_label"}.issubset(df.columns):
        df["_log_pred"] = np.log10(np.maximum(df["valuation_pred"], 1.0))
        df["_log_label"] = np.log10(np.maximum(df["valuation_label"], 1.0))
        m = regression_gap(df, prediction="_log_pred", label="_log_label",
                           group="_gender_proxy")
        rep.metrics.append({**m, "note": "log10 USD bias gap across gender proxy"})
        _check(rep, "valuation_bias_gap_gender_proxy_log10", abs(m["gap"]))

        m = regression_gap(df, prediction="_log_pred", label="_log_label",
                           group="sport")
        rep.metrics.append({**m, "note": "per-sport log10 USD bias gap"})

    return rep
