from pathlib import Path

import numpy as np

from nil_predictor.data import DataConfig as AmateurDataConfig
from nil_predictor.data import generate as generate_amateur
from nil_predictor.train import train_all as amateur_train_all
from nil_predictor.pro.chain import predict as chain_predict
from nil_predictor.pro.train import train_all as pro_train_all


def test_chain_runs_pro_only_for_draft_likely(tmp_path: Path):
    amateur_dir = tmp_path / "amateur"
    pro_dir = tmp_path / "pro"
    amateur_train_all(n=2000, seed=11, out_dir=amateur_dir)
    pro_train_all(n_amateur=6000, seed=11, out_dir=pro_dir)

    # Feed two athletes: one obvious draft prospect, one walk-on.
    records = [
        {
            "sport": "football", "position": "QB", "conference": "SEC", "year": "JR",
            "starter": True, "performance_score": 95,
            "instagram_followers": 350_000, "tiktok_followers": 180_000,
            "twitter_followers": 90_000,
            "draft_round": 1, "draft_pick": 1, "combine_score": 96,
        },
        {
            "sport": "track", "position": "distance", "conference": "MWC", "year": "FR",
            "starter": False, "performance_score": 35,
            "instagram_followers": 400, "tiktok_followers": 100,
            "twitter_followers": 25,
            # caller intentionally omits draft fields — this is not a draft prospect
        },
    ]
    out = chain_predict(
        records,
        amateur_artifacts=amateur_dir,
        pro_artifacts=pro_dir,
        pro_threshold=0.4,
    )
    assert len(out) == 2
    # Every record gets an amateur block.
    assert all("amateur" in r for r in out)
    # Pro is populated only for the draft-likely athlete.
    assert out[0]["pro"] is not None
    assert "pro_contract_value" in out[0]["pro"]
    assert out[1]["pro"] is None
