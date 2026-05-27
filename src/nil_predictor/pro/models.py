"""Four pro-stage targets, each with its own estimator.

pro_contract_value     log-target gradient boosting              regression
pro_career_length      log-target gradient boosting              regression
pro_all_star           gradient boosting + isotonic calibration  binary
agent_signed           logistic + isotonic calibration           binary
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .features import build_preprocessor


@dataclass(frozen=True)
class ProTargetSpec:
    name: str
    column: str
    kind: str  # "regression" | "classification"


TARGETS: tuple[ProTargetSpec, ...] = (
    ProTargetSpec("pro_contract_value", "pro_contract_value", "regression"),
    ProTargetSpec("pro_career_length", "pro_career_length", "regression"),
    ProTargetSpec("pro_all_star", "pro_all_star", "classification"),
    ProTargetSpec("agent_signed", "agent_signed", "classification"),
)


def build_model(target: str) -> Pipeline:
    pre = build_preprocessor()

    if target == "pro_contract_value":
        regressor = GradientBoostingRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05, random_state=0,
        )
        estimator = TransformedTargetRegressor(
            regressor=regressor, func=np.log1p, inverse_func=np.expm1,
        )
    elif target == "pro_career_length":
        regressor = GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.06, random_state=0,
        )
        estimator = TransformedTargetRegressor(
            regressor=regressor, func=np.log1p, inverse_func=np.expm1,
        )
    elif target == "pro_all_star":
        base = GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.07, random_state=0,
        )
        estimator = CalibratedClassifierCV(base, method="isotonic", cv=3)
    elif target == "agent_signed":
        base = LogisticRegression(max_iter=400, C=1.0)
        estimator = CalibratedClassifierCV(base, method="isotonic", cv=3)
    else:
        raise ValueError(f"unknown pro target: {target}")

    return Pipeline([("pre", pre), ("est", estimator)])
