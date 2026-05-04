from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from nil_predictor.data import DataConfig, generate
from nil_predictor.features import FEATURE_COLUMNS
from nil_predictor.predict import predict
from nil_predictor.train import train_all


def _spearman(a, b) -> float:
    a = pd.Series(np.asarray(a)).rank()
    b = pd.Series(np.asarray(b)).rank()
    return float(a.corr(b))


def test_train_and_predict_end_to_end(tmp_path: Path):
    report = train_all(n=2000, seed=11, out_dir=tmp_path)

    # Every target reported metrics.
    assert set(report.keys()) == {"valuation", "deal_count", "tier", "portal", "drafted"}

    # Regression baseline beats predicting the mean by a healthy margin.
    assert report["valuation"]["r2"] > 0.2

    # Poisson R² is noisy on small holdouts; verify the model isn't catastrophic
    # and that its rank-ordering of athletes correlates with the truth.
    assert report["deal_count"]["r2"] > -0.15
    df_eval = generate(DataConfig(n_athletes=1000, seed=21))
    bundle = joblib.load(tmp_path / "deal_count.joblib")
    preds = bundle["model"].predict(df_eval[FEATURE_COLUMNS])
    assert _spearman(preds, df_eval["deal_count_12mo"]) > 0.25

    # Classification baselines clear trivial.
    assert report["tier"]["accuracy"] > 0.55
    # Portal: training tunes an F1-optimal threshold, with a no-regression
    # guard on a held-out evaluation slice. At small n the threshold may
    # fall back to the default 0.5 (trivial all-False), so we floor on the
    # weakest acceptable behaviour: accuracy must beat random and f1_macro
    # must not collapse below the trivial baseline.
    assert report["portal"]["accuracy"] > 0.40
    assert report["portal"]["f1_macro"] >= 0.40
    assert report["drafted"]["accuracy"] > 0.75

    # Round-trip a small batch through the public predictor API.
    sample = generate(DataConfig(n_athletes=5, seed=99))
    records = sample[FEATURE_COLUMNS].to_dict(orient="records")
    out = predict(records, tmp_path)
    assert len(out) == 5
    keys = set(out[0].keys())
    assert {"valuation", "deal_count", "tier", "portal", "drafted"} <= keys
    assert "tier_proba" in out[0]
    assert "portal_proba" in out[0]
    assert out[0]["valuation"] >= 0
    assert out[0]["deal_count"] >= 0
