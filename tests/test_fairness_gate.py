"""Fairness gate: budgets enforced as part of CI.

Trains a small model on a fixed seed, predicts on a held-out synthetic set,
and asserts demographic-parity and equalized-odds gaps stay within the
budgets declared by the lunning- methodology
(`predictions.fairness`, ISO/IEC TR 24027:2021).

Skips a (target, attribute) cell when one group has base rate 0 in the data —
that's a label-availability artifact, not a fairness signal.

Requires the `predictions` package from `lunning-`. Add as a dev dep with:

    pip install 'predictions @ git+https://github.com/jyo-giddyup/lunning-'

If `predictions` is not installed, the whole module is skipped (no false
red on dev environments without lunning- available).
"""
from __future__ import annotations

import pytest

pytest.importorskip(
    "predictions.fairness",
    reason=(
        "fairness gate requires the 'predictions' package from lunning-. "
        "Install with: pip install 'predictions @ git+https://github.com/jyo-giddyup/lunning-'"
    ),
)

import numpy as np

from nil_predictor.data import DataConfig, generate
from nil_predictor.predict import predict
from nil_predictor.train import train_all
from predictions.fairness import report  # noqa: E402

# Budgets per ISO/IEC TR 24027 — same numbers as the on-demand audit script.
DEMOGRAPHIC_PARITY_BUDGET = 0.05
EQUALIZED_ODDS_BUDGET = 0.10

POWER_4 = {"SEC", "Big_Ten", "ACC", "Big_12"}
WOMENS_SPORTS = {"womens_basketball", "womens_soccer", "softball"}


# Match production: the Dockerfile bakes the image with `nil-train --n 10000
# --seed 7`. Smaller n produces noisier per-group rates and pushes the
# Power-4 EO gap above budget on common seeds, so we don't try to evaluate
# a model that's smaller than the one we ship.
TRAIN_N = 10_000
AUDIT_N = 5_000


@pytest.fixture(scope="module")
def trained_artifacts(tmp_path_factory):
    out = tmp_path_factory.mktemp("nil-artifacts")
    train_all(n=TRAIN_N, seed=42, out_dir=out)
    return out


@pytest.fixture(scope="module")
def audit_predictions(trained_artifacts):
    df = generate(DataConfig(n_athletes=AUDIT_N, seed=99))
    target_cols = [
        "athlete_id",
        "nil_valuation_usd",
        "deal_count_12mo",
        "tier",
        "in_transfer_portal",
        "drafted",
    ]
    features = df.drop(columns=[c for c in target_cols if c in df.columns]).to_dict("records")
    preds = predict(features, trained_artifacts)
    return df, preds


def _binary(values, true_label: str = "True"):
    return np.array([1 if str(v) == true_label else 0 for v in values], dtype=int)


def _is_structural(per_group: dict) -> bool:
    rates = [stats["base_rate"] for stats in per_group.values()]
    return bool(rates) and min(rates) == 0.0 and max(rates) > 0.0


@pytest.mark.parametrize("target", ["drafted", "portal"])
@pytest.mark.parametrize("attr_name", ["power_4", "womens_sport"])
def test_fairness_budget(audit_predictions, target, attr_name):
    df, preds = audit_predictions

    if target == "drafted":
        ypred = _binary([p["drafted"] for p in preds])
        ytrue = df["drafted"].astype(int).to_numpy()
    else:  # portal
        ypred = _binary([p["portal"] for p in preds])
        ytrue = df["in_transfer_portal"].astype(int).to_numpy()

    if attr_name == "power_4":
        attr = np.array([1 if c in POWER_4 else 0 for c in df["conference"]], dtype=int)
    else:
        attr = np.array([1 if s in WOMENS_SPORTS else 0 for s in df["sport"]], dtype=int)

    r = report(ytrue, ypred, attr)
    per_group = r["per_group"]

    if _is_structural(per_group):
        pytest.skip(
            f"{target} × {attr_name}: one group has base rate 0 in the data; "
            "EO/DP gap is a label-availability artifact, not bias"
        )

    dp = r["demographic_parity_gap"]
    eo = r["equalized_odds_gap"]
    assert dp <= DEMOGRAPHIC_PARITY_BUDGET, (
        f"{target} × {attr_name}: DP gap {dp:.3f} exceeds budget "
        f"{DEMOGRAPHIC_PARITY_BUDGET}. per_group={per_group}"
    )
    assert eo <= EQUALIZED_ODDS_BUDGET, (
        f"{target} × {attr_name}: EO gap {eo:.3f} exceeds budget "
        f"{EQUALIZED_ODDS_BUDGET}. per_group={per_group}"
    )
