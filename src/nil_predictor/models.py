"""Five stacked targets, each with its own estimator.

valuation     : log-transformed regression  (GradientBoosting)
deal_count    : Poisson regression           (HistGradientBoosting, poisson loss)
tier          : 4-class classification       (GradientBoosting)
portal        : binary classification        (LogisticRegression + isotonic calibration)
drafted       : binary classification        (GradientBoosting + isotonic calibration)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .features import build_preprocessor


@dataclass(frozen=True)
class TargetSpec:
    name: str
    column: str
    kind: str  # "regression" | "classification"


TARGETS: tuple[TargetSpec, ...] = (
    TargetSpec("valuation", "nil_valuation_usd", "regression"),
    TargetSpec("deal_count", "deal_count_12mo", "regression"),
    TargetSpec("tier", "tier", "classification"),
    TargetSpec("portal", "in_transfer_portal", "classification"),
    TargetSpec("drafted", "drafted", "classification"),
)


def build_model(target: str) -> Pipeline:
    """Return a fresh pipeline for a target name."""
    pre = build_preprocessor()

    if target == "valuation":
        # Log-transform the heavy-tailed dollar target.
        regressor = GradientBoostingRegressor(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            random_state=0,
        )
        estimator = TransformedTargetRegressor(
            regressor=regressor, func=np.log1p, inverse_func=np.expm1
        )
    elif target == "deal_count":
        estimator = HistGradientBoostingRegressor(
            loss="poisson",
            max_iter=200,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=20,
            l2_regularization=0.5,
            random_state=0,
        )
    elif target == "tier":
        estimator = GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.07, random_state=0
        )
    elif target == "portal":
        # Linear features capture most of the signal here; isotonic calibration
        # on top makes the predicted probabilities reliable.
        base = LogisticRegression(max_iter=400, C=1.0)
        estimator = CalibratedClassifierCV(base, method="isotonic", cv=3)
    elif target == "drafted":
        base = GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.07, random_state=0
        )
        estimator = CalibratedClassifierCV(base, method="isotonic", cv=3)
    else:
        raise ValueError(f"unknown target: {target}")

    return Pipeline([("pre", pre), ("est", estimator)])
