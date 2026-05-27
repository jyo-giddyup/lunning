"""Load pro-stage models and emit predictions.

Usage:
    python -m nil_predictor.pro.predict --artifacts artifacts/pro/ --input draftee.json
    cat draftees.jsonl | python -m nil_predictor.pro.predict --artifacts artifacts/pro/

Inputs require all twelve fields documented in `FEATURE_COLUMNS`,
including `draft_round`, `draft_pick`, and `combine_score`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS
from .models import TARGETS


def _load(artifacts: Path) -> dict[str, Any]:
    bundles = {}
    for spec in TARGETS:
        path = artifacts / f"{spec.name}.joblib"
        if not path.exists():
            raise FileNotFoundError(f"missing pro artifact: {path}")
        bundles[spec.name] = joblib.load(path)
    return bundles


def predict(records: list[dict], artifacts_dir: str | Path) -> list[dict]:
    df = pd.DataFrame(records)
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required pro feature columns: {missing}")
    X = df[FEATURE_COLUMNS]

    bundles = _load(Path(artifacts_dir))
    out: list[dict[str, Any]] = [{} for _ in range(len(df))]

    for spec in TARGETS:
        model = bundles[spec.name]["model"]
        preds = model.predict(X)
        for i, value in enumerate(preds):
            if spec.kind == "regression":
                out[i][spec.name] = float(np.round(value, 2))
            else:
                out[i][spec.name] = bool(value) if isinstance(value, (bool, np.bool_)) else str(value)

        if spec.kind == "classification" and hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)
            classes = list(model.classes_)
            for i, row in enumerate(proba):
                out[i][f"{spec.name}_proba"] = {
                    str(c): float(np.round(p, 4)) for c, p in zip(classes, row)
                }

    return out


def _read_input(arg: str | None) -> list[dict]:
    text = (Path(arg).read_text() if arg else sys.stdin.read()).strip()
    if not text:
        return []
    if text.startswith(("[", "{")):
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else [parsed]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict pro-stage outcomes")
    parser.add_argument("--artifacts", default="artifacts/pro")
    parser.add_argument("--input")
    args = parser.parse_args()

    records = _read_input(args.input)
    if not records:
        print("[]")
        return
    if isinstance(records, dict):
        records = [records]
    print(json.dumps(predict(records, args.artifacts), indent=2))


if __name__ == "__main__":
    main()
