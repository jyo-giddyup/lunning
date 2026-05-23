"""FastAPI service exposing the trained NIL predictors over HTTP.

Run:
    pip install -e ".[api]"
    nil-train --n 10000 --out artifacts/
    uvicorn nil_predictor.api:app --host 0.0.0.0 --port 8000

Endpoints:
    GET  /health                  -> liveness                       (always public)
    GET  /schema                  -> required feature columns        (gated)
    GET  /explain?top_k=15        -> per-target feature importances  (gated)
    POST /predict                 -> single athlete or batch         (gated)
    POST /checkout                -> create Stripe Checkout Session  (always public)
    POST /webhooks/stripe         -> Stripe webhook receiver         (always public)
    GET  /customer/bootstrap      -> one-shot API-key retrieval      (always public)
    GET  /me                      -> current customer record         (gated)
    GET  /revenue                 -> succeeded-charge totals         (gated)

Authentication:
    Two modes, controlled by NIL_REQUIRE_PAYMENT:

    1) Off (default — legacy / dev): if NIL_API_KEY is set, gated
       endpoints require an X-API-Key header that matches it. If
       NIL_API_KEY is unset, gated endpoints are open. Single shared
       key, no notion of identity.

    2) On: gated endpoints require an X-API-Key header that resolves
       to either NIL_API_KEY (dev/admin override) or a customer row
       in the SQLite store with status in {active, trialing}. Per-
       customer entitlement, populated by the Stripe webhook on
       checkout.session.completed. Cancelled customers automatically
       lose access on the next request.

    /checkout always bypasses the gate (otherwise customers couldn't
    buy the API key) and /webhooks/stripe authenticates via Stripe's
    own signature, not X-API-Key. /customer/bootstrap is also public
    because the caller doesn't have the API key yet — it's gated by
    knowledge of the one-time Stripe session_id instead.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import audit, customers, payments
from .features import FEATURE_COLUMNS
from .models import TARGETS
from .predict import predict as _predict
from .explain import per_target_importances

# Hard cap on records per request — prevents single-request DoS via giant batches.
MAX_BATCH = max(1, int(os.environ.get("NIL_MAX_BATCH", "100")))

# Optional shared API key. In legacy mode (NIL_REQUIRE_PAYMENT off), this is
# the single gate. In per-customer mode it stays available as a dev /
# admin override so operators can still poke /predict without a customer
# row.
NIL_API_KEY = os.environ.get("NIL_API_KEY", "").strip()

# Feature flag for per-customer entitlement enforcement. When false the
# middleware behaves exactly as before, so flipping the new database +
# webhook handlers into production at merge time is safe.
NIL_REQUIRE_PAYMENT = os.environ.get("NIL_REQUIRE_PAYMENT", "").lower() in (
    "1", "true", "yes", "on",
)

# Endpoints that bypass the key gate. /health is for Fly/k8s probes;
# /webhooks/stripe authenticates via stripe-signature, not X-API-Key;
# /checkout is the purchase entry point; /customer/bootstrap is the
# one-shot key-retrieval endpoint right after Stripe redirects the
# customer back — they don't have the key yet.
PUBLIC_PATHS = frozenset({
    "/health", "/webhooks/stripe", "/checkout", "/customer/bootstrap",
})

# In-memory sliding-window rate limit on /checkout (M2 from the security
# review). Per-instance only — if the predictor is ever horizontally
# scaled, replace with a Redis-backed counter so all instances share state.
CHECKOUT_RATE_LIMIT = int(os.environ.get("NIL_CHECKOUT_RATE_LIMIT", "10"))
CHECKOUT_RATE_WINDOW = float(os.environ.get("NIL_CHECKOUT_RATE_WINDOW", "60"))
_checkout_buckets: dict[str, deque[float]] = defaultdict(deque)


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


app = FastAPI(title="nil-predictor", version="0.1.4")
app.include_router(payments.router)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def checkout_rate_limit(request: Request, call_next):
    if request.url.path == "/checkout" and request.method == "POST":
        ip = _client_ip(request)
        now = time.monotonic()
        bucket = _checkout_buckets[ip]
        cutoff = now - CHECKOUT_RATE_WINDOW
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= CHECKOUT_RATE_LIMIT:
            retry_after = max(1, int(CHECKOUT_RATE_WINDOW - (now - bucket[0])) + 1)
            return JSONResponse(
                {"detail": "rate_limited"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
    return await call_next(request)


def _matches_admin_key(provided: str) -> bool:
    """Constant-time check against NIL_API_KEY, working for empty inputs.

    We hash both sides to fixed length so compare_digest runs in constant
    time regardless of whether `provided` is empty or wrong-length. The
    earlier `not provided`-short-circuit leaked "header missing" versus
    "header wrong" via response timing.
    """
    if not NIL_API_KEY:
        return False
    provided_hash = hashlib.sha256(provided.encode()).digest()
    expected_hash = hashlib.sha256(NIL_API_KEY.encode()).digest()
    return secrets.compare_digest(provided_hash, expected_hash)


@app.middleware("http")
async def api_key_gate(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS:
        return await call_next(request)

    if NIL_REQUIRE_PAYMENT:
        # Per-customer mode: accept the admin key OR a known customer key
        # whose subscription is active.
        provided = request.headers.get("x-api-key", "")
        if not provided:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        if _matches_admin_key(provided):
            return await call_next(request)
        rec = customers.find_by_api_key(provided)
        if rec is None or not customers.is_active(rec):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    # Legacy single-shared-key mode.
    if NIL_API_KEY:
        if not _matches_admin_key(request.headers.get("x-api-key", "")):
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
        "auth_required": bool(NIL_API_KEY) or NIL_REQUIRE_PAYMENT,
        "require_payment": NIL_REQUIRE_PAYMENT,
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
