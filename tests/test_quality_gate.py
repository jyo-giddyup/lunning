"""Quality gate: enforce minimum predictive quality at production scale.

Mirror of `tests/test_fairness_gate.py`. Trains a fresh model at the same
seed and size production ships, then asserts each target's headline metric
clears a floor calibrated below the current `BUILD_METRICS.json` numbers
with margin for normal training variance.

Catches regressions where a feature change tanks a target without anyone
noticing — fairness can stay green while accuracy collapses.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pytest

from nil_predictor.train import train_all


# Match the production training run baked into the Dockerfile.
TRAIN_N = 10_000
TRAIN_SEED = 7

# Floors are calibrated ~5-15pp below the current BUILD_METRICS.json values
# to absorb seed-to-seed variance without admitting silent regressions.
# When you genuinely improve a target, ratchet its floor here and update
# BUILD_METRICS.json so future runs hold the higher bar.
FLOORS = {
    "valuation":  {"r2": 0.40},
    "deal_count": {"r2": 0.35},
    "tier":       {"accuracy": 0.70, "f1_macro": 0.45},
    # Portal: f1_macro reflects the threshold-tuned operating point we ship,
    # not the trivial all-False classifier (which has f1_macro ~0.45 at this
    # base rate). Floor sits above the trivial baseline to enforce real work.
    "portal":     {"f1_macro": 0.46},
    "drafted":    {"accuracy": 0.80, "f1_macro": 0.70},
}


@pytest.fixture(scope="module")
def trained_report(tmp_path_factory):
    out = tmp_path_factory.mktemp("nil-artifacts-quality")
    return train_all(n=TRAIN_N, seed=TRAIN_SEED, out_dir=out), out


@pytest.mark.parametrize(
    ("target", "metric", "floor"),
    [
        (target, metric, floor)
        for target, metrics in FLOORS.items()
        for metric, floor in metrics.items()
    ],
)
def test_quality_floor(trained_report, target, metric, floor):
    report, _out = trained_report
    actual = report.get(target, {}).get(metric)
    assert actual is not None, f"metrics report missing {target}.{metric}: {report}"
    assert actual >= floor, (
        f"{target}.{metric} = {actual:.4f} below floor {floor:.4f}. "
        "Either the model regressed or the floor is stale — investigate."
    )


def test_artifacts_present(trained_report):
    """All five .joblib bundles land on disk after training."""
    _report, out = trained_report
    for target in FLOORS:
        path = Path(out) / f"{target}.joblib"
        assert path.exists(), f"missing artifact: {path}"
        bundle = joblib.load(path)
        assert "model" in bundle, f"bundle for {target} missing 'model' key"
