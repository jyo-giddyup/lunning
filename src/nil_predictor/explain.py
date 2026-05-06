"""Feature importance utilities.

Per-target global importances extracted from the fitted pipeline. For
gradient-boosting models we surface `feature_importances_` directly;
for calibrated wrappers we average across folds. For estimators that
expose neither (HistGradientBoosting in particular) we fall back to
sklearn's `permutation_importance` on a freshly-generated synthetic
holdout — slower but model-agnostic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import TransformedTargetRegressor
from sklearn.inspection import permutation_importance

from .data import DataConfig, generate
from .features import FEATURE_COLUMNS
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


def _permutation_importances(
    pipeline,
    target_column: str,
    n: int = 1500,
    seed: int = 4242,
    n_repeats: int = 5,
) -> tuple[list[str], np.ndarray]:
    """Per-RAW-feature permutation importance on a fresh synthetic holdout.

    Uses the same calibration seed (4242) train.py uses for threshold tuning
    so this stays a held-out evaluation set, not training data. Reports
    importances per raw input column (9 features) rather than per OHE
    feature, which is the right granularity when sklearn can't expose
    structural importances.
    """
    df = generate(DataConfig(n_athletes=n, seed=seed))
    X = df[FEATURE_COLUMNS]
    y = df[target_column]
    result = permutation_importance(
        pipeline, X, y,
        n_repeats=n_repeats, random_state=seed, n_jobs=1,
    )
    return list(FEATURE_COLUMNS), result.importances_mean


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
        if fi is not None and len(fi) == len(names):
            order = np.argsort(fi)[::-1][:top_k]
            out[spec.name] = {
                "available": True,
                "method": "feature_importances_",
                "top_features": [
                    {"feature": names[i], "importance": float(round(fi[i], 4))}
                    for i in order
                ],
            }
            continue
        # Fall back to permutation importance on raw features. Slower (~1-3s
        # per target, n_repeats=5) but works for HistGradientBoosting and
        # any other estimator without exposed importances.
        try:
            raw_names, perm = _permutation_importances(pipeline, spec.column)
        except Exception as e:
            out[spec.name] = {
                "available": False,
                "reason": f"permutation_importance failed: {e}",
            }
            continue
        # permutation importance can be negative when shuffling helps;
        # clamp display order to magnitude but report the signed value.
        order = np.argsort(np.abs(perm))[::-1][:top_k]
        out[spec.name] = {
            "available": True,
            "method": "permutation_importance",
            "top_features": [
                {"feature": raw_names[i], "importance": float(round(perm[i], 4))}
                for i in order
            ],
        }
    return out


def raw_feature_importances(
    artifacts_dir: str | Path,
    top_k: int = 9,
    n: int = 1500,
    seed: int = 4242,
    n_repeats: int = 5,
) -> dict[str, Any]:
    """Per-RAW-feature permutation importance for *every* target.

    Complement to `per_target_importances`: the latter returns per-OHE
    importances when the estimator exposes `feature_importances_`, which is
    fine-grained but mixes structural variants (e.g. `sport_football` vs
    `position_QB`) that aren't user-actionable in isolation. This function
    always reports per-raw-feature granularity (9 columns), so a consumer
    can answer \"which input has the most leverage on this target?\"
    regardless of the estimator's introspection surface.

    Defaults match the per-target permutation fallback (seed 4242, the
    calibration set held out from training and audit seeds).
    """
    art = Path(artifacts_dir)
    out: dict[str, Any] = {}
    for spec in TARGETS:
        path = art / f"{spec.name}.joblib"
        if not path.exists():
            continue
        pipeline = joblib.load(path)["model"]
        try:
            raw_names, perm = _permutation_importances(
                pipeline, spec.column, n=n, seed=seed, n_repeats=n_repeats,
            )
        except Exception as e:
            out[spec.name] = {
                "available": False,
                "reason": f"permutation_importance failed: {e}",
            }
            continue
        order = np.argsort(np.abs(perm))[::-1][:top_k]
        out[spec.name] = {
            "available": True,
            "method": "permutation_importance",
            "top_features": [
                {"feature": raw_names[i], "importance": float(round(perm[i], 4))}
                for i in order
            ],
        }
    return out
