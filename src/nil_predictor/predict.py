"""Load trained models and emit predictions for a single athlete (or a JSON list).

Usage:
    python -m nil_predictor.predict --artifacts artifacts/ --input athlete.json
    cat athletes.jsonl | python -m nil_predictor.predict --artifacts artifacts/
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
            raise FileNotFoundError(f"missing artifact: {path}")
        bundles[spec.name] = joblib.load(path)
    return bundles


def predict(records: list[dict], artifacts_dir: str | Path) -> list[dict]:
    df = pd.DataFrame(records)
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required feature columns: {missing}")
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
                out[i][spec.name] = str(value)

        if spec.kind == "classification" and hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)
            classes = list(model.classes_)
            for i, row in enumerate(proba):
                out[i][f"{spec.name}_proba"] = {
                    str(c): float(np.round(p, 4)) for c, p in zip(classes, row)
                }

    return out


def _read_input(arg: str | None) -> list[dict]:
    if arg:
        text = Path(arg).read_text()
    else:
        text = sys.stdin.read()
    text = text.strip()
    if not text:
        return []
    if text.startswith(("[", "{")):
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else [parsed]
    # JSONL fallback.
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict NIL outcomes")
    parser.add_argument("--artifacts", default="artifacts")
    parser.add_argument("--input", help="JSON file (object, array, or JSONL). Reads stdin if omitted.")
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
