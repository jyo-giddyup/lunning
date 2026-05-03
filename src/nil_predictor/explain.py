"""Feature importance utilities.

Per-target global importances extracted from the fitted pipeline. For
gradient-boosting models we surface `feature_importances_` directly;
for calibrated wrappers we average across folds.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import TransformedTargetRegressor

from .models import TARGETS


def _feature_names(pipeline) -> list[str]:
    pre = pipeline.named_steps["pre"]
    try:
        return list(pre.get_feature_names_out())
    except Exception:
        # Fallback: probe transform output width with a synthetic row.
        import pandas as pd
        from .features import FEATURE_COLUMNS
        probe = pd.DataFrame([{c: 0 if c not in {
            "sport", "position", "conference", "year"} else "x" for c in FEATURE_COLUMNS}])
        probe["starter"] = False
        n = pre.transform(probe).shape[1]
        return [f"f{i}" for i in range(n)]


def _coef_magnitude(est) -> np.ndarray | None:
    coef = getattr(est, "coef_", None)
    if coef is None:
        return None
    arr = np.asarray(coef)
    return np.abs(arr).mean(axis=0)


def _importances_from_estimator(est) -> np.ndarray | None:
    if isinstance(est, TransformedTargetRegressor):
        inner = est.regressor_
        fi = getattr(inner, "feature_importances_", None)
        return fi if fi is not None else _coef_magnitude(inner)
    if isinstance(est, CalibratedClassifierCV):
        contribs = []
        for cal in est.calibrated_classifiers_:
            inner = cal.estimator
            fi = getattr(inner, "feature_importances_", None)
            if fi is None:
                fi = _coef_magnitude(inner)
            if fi is not None:
                contribs.append(fi)
        if contribs:
            return np.mean(contribs, axis=0)
        return None
    fi = getattr(est, "feature_importances_", None)
    if fi is not None:
        return fi
    return _coef_magnitude(est)


def per_target_importances(artifacts_dir: str | Path, top_k: int = 15) -> dict[str, Any]:
    art = Path(artifacts_dir)
    out: dict[str, Any] = {}
    for spec in TARGETS:
        path = art / f"{spec.name}.joblib"
        if not path.exists():
            continue
        pipeline = joblib.load(path)["model"]
        names = _feature_names(pipeline)
        fi = _importances_from_estimator(pipeline.named_steps["est"])
        if fi is None or len(fi) != len(names):
            out[spec.name] = {
                "available": False,
                "reason": "estimator does not expose feature_importances_ or coef_ (use permutation_importance)",
            }
            continue
        order = np.argsort(fi)[::-1][:top_k]
        out[spec.name] = {
            "available": True,
            "top_features": [
                {"feature": names[i], "importance": float(round(fi[i], 4))}
                for i in order
            ],
        }
    return out
