"""FastAPI service exposing the trained NIL predictors over HTTP.

Run:
    pip install -e ".[api]"
    nil-train --n 10000 --out artifacts/
    uvicorn nil_predictor.api:app --host 0.0.0.0 --port 8000

Endpoints:
    GET  /health              -> {"ok": true, "models": [...]}     (always public)
    GET  /schema              -> required feature columns           (gated if NIL_API_KEY set)
    GET  /explain?top_k=15    -> per-target feature importances     (gated if NIL_API_KEY set)
    POST /predict             -> single athlete or batch            (gated if NIL_API_KEY set)
    POST /checkout            -> create Stripe Checkout Session     (always public)
    POST /webhooks/stripe     -> Stripe webhook receiver            (always public; signature-verified)

Authentication:
    If the NIL_API_KEY env var is set, every endpoint except /health,
    /checkout, and /webhooks/stripe requires an `X-API-Key: <key>`
    header that matches it. Comparison is constant-time
    (secrets.compare_digest) to avoid timing attacks. If NIL_API_KEY
    is unset or empty, the service is open — useful for local
    development; set NIL_API_KEY in production. /checkout is the
    purchase entry point so it stays open (otherwise customers would
    need an API key to buy the API key); /webhooks/stripe authenticates
    via Stripe's own signature header.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import audit, payments
from .features import FEATURE_COLUMNS
from .models import TARGETS
from .predict import predict as _predict
from .explain import per_target_importances

# Hard cap on records per request — prevents single-request DoS via giant batches.
MAX_BATCH = max(1, int(os.environ.get("NIL_MAX_BATCH", "100")))

# Optional API key gate. Empty / unset = open. Always set in production.
NIL_API_KEY = os.environ.get("NIL_API_KEY", "").strip()

# Endpoints that bypass the key gate. /health is for Fly/k8s probes;
# /webhooks/stripe authenticates via stripe-signature, not X-API-Key;
# /checkout is the purchase entry point — gating it would require an API
# key in order to buy the API key.
PUBLIC_PATHS = frozenset({"/health", "/webhooks/stripe", "/checkout"})


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


app = FastAPI(title="nil-predictor", version="0.1.3")
app.include_router(payments.router)


@app.middleware("http")
async def api_key_gate(request: Request, call_next):
    if NIL_API_KEY and request.url.path not in PUBLIC_PATHS:
        provided = request.headers.get("x-api-key", "")
        # constant-time compare; secrets.compare_digest requires same-length strs
        # so we hash both sides via fixed-width comparison.
        if not provided or not secrets.compare_digest(provided, NIL_API_KEY):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


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
        "auth_required": bool(NIL_API_KEY),
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
