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

from . import audit
from .data import DataConfig, generate
from .fairness import evaluate as fairness_evaluate
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
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Point the audit log at the same artifacts dir for this training run.
    import os as _os
    _os.environ.setdefault("NIL_AUDIT_LOG", str(out_path / "audit.log"))

    request_id = audit.emit(
        "train.start",
        payload={"n_athletes": n, "seed": seed, "out_dir": str(out_path)},
    )["request_id"]

    df = generate(DataConfig(n_athletes=n, seed=seed))
    X = df[FEATURE_COLUMNS]

    # We collect predictions for the fairness audit alongside the metrics.
    holdout_frames: list[pd.DataFrame] = []

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

        # Build a per-target slice of the holdout for fairness eval.
        idx = X_test.index
        slice_df = pd.DataFrame({
            "sport": df.loc[idx, "sport"].values,
            "conference": df.loc[idx, "conference"].values,
        })
        if spec.name == "drafted":
            slice_df["drafted"] = df.loc[idx, "drafted"].values
            slice_df["drafted_pred"] = (np.asarray(y_pred) == True)  # noqa: E712
        elif spec.name == "portal":
            slice_df["portal_pred"] = (np.asarray(y_pred) == True)  # noqa: E712
        elif spec.name == "tier":
            slice_df["tier_pred"] = np.asarray(y_pred).astype(str)
        elif spec.name == "valuation":
            slice_df["valuation_pred"] = np.asarray(y_pred, dtype=float)
            slice_df["valuation_label"] = df.loc[idx, "nil_valuation_usd"].values
        holdout_frames.append(slice_df)

    metrics_path = out_path / "metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2))

    # Stitch per-target slices into one frame, keyed by athlete index, so the
    # fairness module sees all predictions side-by-side.
    fairness_df = (
        pd.concat(holdout_frames, axis=0)
          .groupby(level=0).first()
          .reindex(holdout_frames[0].index)
    )
    fairness_report = fairness_evaluate(fairness_df)
    (out_path / "fairness.json").write_text(
        json.dumps(fairness_report.to_dict(), indent=2, default=str)
    )

    audit.emit(
        "train.complete",
        payload={
            "n_athletes": n,
            "seed": seed,
            "out_dir": str(out_path),
            "model_count": len(TARGETS),
            "violation_count": len(fairness_report.violations),
        },
        request_id=request_id,
    )
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
