"""FastAPI service exposing the trained NIL predictors over HTTP.

Run:
    pip install -e ".[api]"
    nil-train --n 10000 --out artifacts/
    uvicorn nil_predictor.api:app --host 0.0.0.0 --port 8000

Endpoints:
    GET  /health              -> {"ok": true, "models": [...]}
    GET  /schema              -> required feature columns
    GET  /explain?top_k=15    -> per-target feature importances
    POST /predict             -> single athlete or batch (array / {athletes: [...]})
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import audit
from .features import FEATURE_COLUMNS
from .models import TARGETS
from .predict import predict as _predict
from .explain import per_target_importances

# Hard cap on records per request — prevents single-request DoS via giant batches.
# Override with NIL_MAX_BATCH env var. 100 fits comfortably under typical 30s
# request timeouts (latency is ~0.2 ms/record on this model).
MAX_BATCH = max(1, int(os.environ.get("NIL_MAX_BATCH", "100")))


class Athlete(BaseModel):
    sport: str = Field(max_length=64)
    position: str = Field(max_length=64)
    conference: str = Field(max_length=64)
    year: str = Field(max_length=8)
    starter: bool
    performance_score: float = Field(ge=0, le=100)
    instagram_followers: int = Field(ge=0, le=10**9)
    tiktok_followers: int = Field(ge=0, le=10**9)
    twitter_followers: int = Field(ge=0, le=10**9)


class PredictRequest(BaseModel):
    athletes: list[Athlete] | None = None


def _artifacts_dir() -> Path:
    raw = os.environ.get("NIL_ARTIFACTS_DIR", "artifacts")
    return Path(raw).resolve()


app = FastAPI(title="nil-predictor", version="0.1.1")


@app.get("/health")
def health() -> dict[str, Any]:
    art = _artifacts_dir()
    present = []
    missing = []
    for spec in TARGETS:
        path = art / f"{spec.name}.joblib"
        (present if path.exists() else missing).append(spec.name)
    return {
        "ok": not missing,
        "artifacts_dir": str(art),
        "models_present": present,
        "models_missing": missing,
        "max_batch": MAX_BATCH,
    }


@app.get("/schema")
def schema() -> dict[str, Any]:
    return {
        "required_fields": FEATURE_COLUMNS,
        "targets": [t.name for t in TARGETS],
        "max_batch": MAX_BATCH,
    }


@app.get("/explain")
def explain(top_k: int = 15) -> dict[str, Any]:
    # Bound top_k so a malicious caller can't request a huge response.
    top_k = max(1, min(int(top_k), 100))
    art = _artifacts_dir()
    if not art.exists():
        raise HTTPException(status_code=503, detail=f"artifacts dir not found: {art}")
    return per_target_importances(art, top_k=top_k)


@app.post("/predict")
def predict_one(payload: Athlete | list[Athlete] | PredictRequest) -> dict[str, Any]:
    if isinstance(payload, Athlete):
        records = [payload.model_dump()]
    elif isinstance(payload, list):
        records = [a.model_dump() for a in payload]
    else:
        if not payload.athletes:
            raise HTTPException(status_code=400, detail="athletes array is empty")
        records = [a.model_dump() for a in payload.athletes]

    if len(records) > MAX_BATCH:
        # 413 Payload Too Large — single-request DoS guard.
        raise HTTPException(
            status_code=413,
            detail=f"batch size {len(records)} exceeds limit {MAX_BATCH}",
        )

    art = _artifacts_dir()
    request_id = audit.emit(
        "predict.request",
        payload={"n_records": len(records), "artifacts_dir": str(art)},
    )["request_id"]
    if not art.exists():
        audit.emit("predict.error", payload={"error_kind": "missing_artifacts"},
                   request_id=request_id)
        raise HTTPException(status_code=503, detail=f"artifacts dir not found: {art}")
    try:
        preds = _predict(records, art)
    except FileNotFoundError as e:
        audit.emit("predict.error", payload={"error_kind": "missing_artifact"},
                   request_id=request_id)
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        audit.emit("predict.error", payload={"error_kind": "validation"},
                   request_id=request_id)
        raise HTTPException(status_code=400, detail=str(e))
    audit.emit("predict.response", payload={"n_records": len(preds)},
               request_id=request_id)
    return {"predictions": preds, "count": len(preds), "request_id": request_id}
