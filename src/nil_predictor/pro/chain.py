"""Explicit amateur -> pro chaining.

The stage-separation rule (`CLAUDE.md`) forbids implicit composition:
the pro models must never be invoked transparently when an amateur
prediction comes in. This helper makes the join visible at the call
site by:

1. Running the amateur predictor on raw athlete features.
2. For each athlete whose `drafted_proba.True >= threshold`, augmenting
   with caller-supplied draft fields and running the pro predictor.
3. Returning a merged dict per athlete with `amateur` and `pro` blocks.

The caller still supplies `draft_round`, `draft_pick`, and
`combine_score` for the pro stage — those are post-college signals
the amateur stage can't know.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import predict as amateur_predict
from . import predict as pro_predict
from .features import FEATURE_COLUMNS as PRO_FEATURE_COLUMNS

DRAFT_FIELDS = {"draft_round", "draft_pick", "combine_score"}


def predict(
    records: list[dict],
    *,
    amateur_artifacts: str | Path = "artifacts",
    pro_artifacts: str | Path = "artifacts/pro",
    pro_threshold: float = 0.5,
) -> list[dict]:
    """Run amateur, then run pro on draft-likely athletes.

    Each input record may carry the pro draft fields ahead of time;
    if not, only the amateur block is returned for that record.
    """
    amateur_results = amateur_predict.predict(records, amateur_artifacts)

    pro_indices: list[int] = []
    pro_inputs: list[dict] = []
    for i, (athlete, am) in enumerate(zip(records, amateur_results)):
        prob_true = am.get("drafted_proba", {}).get("True", 0.0)
        if prob_true < pro_threshold:
            continue
        if not DRAFT_FIELDS.issubset(athlete):
            continue  # pro stage requires post-college signals
        merged = {**athlete}
        for col in PRO_FEATURE_COLUMNS:
            merged.setdefault(col, athlete.get(col))
        pro_indices.append(i)
        pro_inputs.append(merged)

    pro_results: list[dict] = []
    if pro_inputs:
        pro_results = pro_predict.predict(pro_inputs, pro_artifacts)

    out: list[dict[str, Any]] = []
    by_index = dict(zip(pro_indices, pro_results))
    for i, am in enumerate(amateur_results):
        out.append({"amateur": am, "pro": by_index.get(i)})
    return out
