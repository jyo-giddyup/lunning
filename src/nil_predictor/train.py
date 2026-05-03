"""Train every target and persist artifacts.

Usage:
    python -m nil_predictor.train --n 5000 --out artifacts/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from .data import DataConfig, generate
from .features import FEATURE_COLUMNS
from .models import TARGETS, build_model


def _evaluate(spec, y_true, y_pred, y_proba=None) -> dict:
    if spec.kind == "regression":
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        return {
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": rmse,
            "r2": float(r2_score(y_true, y_pred)),
        }
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
    }
    if y_proba is not None:
        try:
            if y_proba.shape[1] == 2:
                metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba[:, 1]))
                metrics["log_loss"] = float(log_loss(y_true, y_proba))
            else:
                metrics["log_loss"] = float(log_loss(y_true, y_proba))
        except ValueError:
            pass
    return metrics


def train_all(n: int = 5000, seed: int = 7, out_dir: str | Path = "artifacts") -> dict:
    df = generate(DataConfig(n_athletes=n, seed=seed))
    X = df[FEATURE_COLUMNS]

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    report: dict[str, dict] = {}
    for spec in TARGETS:
        y = df[spec.column]
        stratify = None
        if spec.kind == "classification":
            counts = pd.Series(y).value_counts()
            if counts.min() >= 2:
                stratify = y
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=seed, stratify=stratify,
        )
        model = build_model(spec.name)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        proba = None
        if spec.kind == "classification" and hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_test)
        report[spec.name] = _evaluate(spec, y_test, y_pred, proba)

        artifact = out_path / f"{spec.name}.joblib"
        joblib.dump({"model": model, "spec": spec}, artifact)

    metrics_path = out_path / "metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train NIL prediction models")
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="artifacts")
    args = parser.parse_args()

    report = train_all(n=args.n, seed=args.seed, out_dir=args.out)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
