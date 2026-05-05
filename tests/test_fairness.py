import pandas as pd

from nil_predictor.fairness import (
    DEFAULT_THRESHOLDS,
    conference_tier,
    demographic_parity_gap,
    equal_opportunity_gap,
    evaluate,
    gender_proxy,
)


def test_grouping_helpers():
    assert conference_tier("SEC") == "P5"
    assert conference_tier("MWC") == "G5"
    assert conference_tier("FCS") == "subdiv"
    assert conference_tier("UNKNOWN") == "other"

    assert gender_proxy("mens_basketball") == "men"
    assert gender_proxy("womens_soccer") == "women"
    assert gender_proxy("track") == "mixed"


def test_dp_gap_zero_when_groups_equal():
    df = pd.DataFrame({
        "g": ["a"] * 50 + ["b"] * 50,
        "y": [1] * 25 + [0] * 25 + [1] * 25 + [0] * 25,
    })
    out = demographic_parity_gap(df, prediction="y", group="g")
    assert out["gap"] == 0.0


def test_dp_gap_skips_tiny_groups():
    df = pd.DataFrame({"g": ["a"] * 100 + ["b"] * 5, "y": [1] * 100 + [1] * 5})
    out = demographic_parity_gap(df, prediction="y", group="g")
    # b is dropped (n<30) so only one group remains -> gap=0.
    assert out["gap"] == 0.0
    assert "b" not in out["rates"]


def test_eo_gap_uses_positives():
    df = pd.DataFrame({
        "g": ["a"] * 60 + ["b"] * 60,
        "y": [True] * 60 + [True] * 60,
        "p": [True] * 30 + [False] * 30 + [True] * 60,
    })
    out = equal_opportunity_gap(df, prediction="p", label="y", group="g")
    # a has TPR 0.5, b has TPR 1.0 -> gap = 0.5
    assert abs(out["gap"] - 0.5) < 1e-6


def test_evaluate_full_pipeline_passes_when_under_thresholds():
    rng_n = 200
    df = pd.DataFrame({
        "sport": ["football"] * rng_n + ["mens_basketball"] * rng_n,
        "conference": (["SEC"] * 100 + ["MWC"] * 100) * 2,
        "drafted": [True] * (rng_n * 2),
        "drafted_pred": [True, False] * (rng_n),
        "portal_pred": [False] * (rng_n * 2),
        "tier_pred": ["high"] * (rng_n * 2),
        "valuation_pred": [10000.0] * (rng_n * 2),
        "valuation_label": [10000.0] * (rng_n * 2),
    })
    rep = evaluate(df, thresholds=DEFAULT_THRESHOLDS)
    assert rep.passed, rep.violations
    assert rep.metrics  # something was computed


def test_evaluate_emits_per_sport_metrics():
    rng_n = 200
    df = pd.DataFrame({
        "sport": ["football"] * rng_n + ["mens_basketball"] * rng_n,
        "conference": (["SEC"] * 100 + ["MWC"] * 100) * 2,
        "drafted": [True] * (rng_n * 2),
        "drafted_pred": [True, False] * (rng_n),
        "portal_pred": [False] * (rng_n * 2),
        "tier_pred": ["high"] * (rng_n * 2),
        "valuation_pred": [10000.0] * (rng_n * 2),
        "valuation_label": [10000.0] * (rng_n * 2),
    })
    rep = evaluate(df, thresholds=DEFAULT_THRESHOLDS)
    sport_metrics = [m for m in rep.metrics if m.get("group") == "sport"]
    # per-sport: drafted DP, drafted EO, portal DP, top-tier DP, valuation regression
    assert len(sport_metrics) == 5
    for m in sport_metrics:
        bucket = m.get("rates") or m.get("tpr") or m.get("mean_bias") or {}
        assert {"football", "mens_basketball"}.issubset(bucket.keys())
    # Per-sport metrics are tracked-only — no thresholds, so report still passes.
    assert rep.passed, rep.violations
