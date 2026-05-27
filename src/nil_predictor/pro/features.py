"""Feature engineering pipeline for the pro stage.

Reuses the amateur preprocessor as a base and adds three draft-time
features (round, pick, combine score). Kept as a separate function
rather than importing the amateur one verbatim so that tightening the
amateur pipeline can never silently change pro behavior.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

CATEGORICAL = ["sport", "position", "conference", "year"]
BOOLEAN = ["starter"]
NUMERIC_RAW = ["performance_score", "draft_round", "draft_pick", "combine_score"]
FOLLOWER_COLS = ["instagram_followers", "tiktok_followers", "twitter_followers"]


def _log1p(values: np.ndarray | pd.DataFrame) -> np.ndarray:
    return np.log1p(np.asarray(values, dtype=np.float64))


def _to_float(values: np.ndarray | pd.DataFrame) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def build_preprocessor() -> ColumnTransformer:
    log_pipe = Pipeline([
        ("log1p", FunctionTransformer(_log1p, validate=False, feature_names_out="one-to-one")),
        ("scale", StandardScaler()),
    ])
    numeric_pipe = Pipeline([("scale", StandardScaler())])
    bool_pipe = Pipeline([
        ("cast", FunctionTransformer(_to_float, feature_names_out="one-to-one")),
    ])

    try:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse=False)

    return ColumnTransformer(
        transformers=[
            ("cat", ohe, CATEGORICAL),
            ("bool", bool_pipe, BOOLEAN),
            ("num", numeric_pipe, NUMERIC_RAW),
            ("follow", log_pipe, FOLLOWER_COLS),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


FEATURE_COLUMNS = CATEGORICAL + BOOLEAN + NUMERIC_RAW + FOLLOWER_COLS
