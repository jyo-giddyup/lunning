from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from nil_predictor.pro.data import (
    DRAFT_ELIGIBLE_SPORTS,
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
    ProDataConfig,
    generate,
)
from nil_predictor.pro.predict import predict as pro_predict
from nil_predictor.pro.train import train_all


def test_generate_only_drafted_eligible_sports():
    df = generate(ProDataConfig(n_amateur=8000, seed=11))
    assert set(df["sport"].unique()) <= set(DRAFT_ELIGIBLE_SPORTS)
    for col in FEATURE_COLUMNS + TARGET_COLUMNS:
        assert col in df.columns
    assert (df["draft_round"] >= 1).all()
    assert (df["combine_score"].between(0, 100)).all()


def test_generate_is_deterministic():
    a = generate(ProDataConfig(n_amateur=4000, seed=42))
    b = generate(ProDataConfig(n_amateur=4000, seed=42))
    assert a.equals(b)


def test_contracts_skew_to_top_picks():
    df = generate(ProDataConfig(n_amateur=12000, seed=11))
    top = df[(df["draft_round"] == 1) & (df["draft_pick"] <= 8)]
    rest = df[df["draft_round"] >= 3]
    if len(top) >= 30 and len(rest) >= 30:
        assert top["pro_contract_value"].median() > rest["pro_contract_value"].median()


def test_train_and_predict_round_trip(tmp_path: Path):
    report = train_all(n_amateur=6000, seed=11, out_dir=tmp_path)
    assert set(report.keys()) == {
        "pro_contract_value", "pro_career_length", "pro_all_star", "agent_signed",
    }
    # Regression baselines must beat predicting the mean.
    assert report["pro_contract_value"]["r2"] > 0.4
    assert report["pro_career_length"]["r2"] > 0.0
    # Classification baselines clear trivial.
    assert report["pro_all_star"]["accuracy"] > 0.7
    assert report["agent_signed"]["accuracy"] > 0.6

    sample = generate(ProDataConfig(n_amateur=4000, seed=99))
    records = sample[FEATURE_COLUMNS].head(5).to_dict(orient="records")
    out = pro_predict(records, tmp_path)
    assert len(out) == 5
    keys = set(out[0])
    assert {"pro_contract_value", "pro_career_length", "pro_all_star", "agent_signed"} <= keys
    assert "pro_all_star_proba" in out[0]
    assert "agent_signed_proba" in out[0]
    assert out[0]["pro_contract_value"] >= 0
    assert out[0]["pro_career_length"] >= 0
