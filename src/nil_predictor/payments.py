"""Stripe Checkout + webhook endpoints.

Monetization gate for the predictor:

    POST /checkout         -> create a Checkout Session, return its URL
    POST /webhooks/stripe  -> verify signature, process subscription events

Required env vars (set as Fly secrets in production):
    STRIPE_SECRET_KEY      sk_live_... or sk_test_...
    STRIPE_WEBHOOK_SECRET  whsec_... from the Stripe dashboard webhook
    STRIPE_PRICE_ID        price_... the customer is purchasing
    STRIPE_SUCCESS_URL     where Stripe redirects on successful payment
    STRIPE_CANCEL_URL      where Stripe redirects on cancel

Optional:
    STRIPE_MODE            "subscription" (default) or "payment"

The Stripe SDK is imported lazily so the package and its tests work
without it installed; missing SDK or env surfaces as HTTP 503.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import audit

router = APIRouter()

# Hard cap on webhook body size. Stripe webhooks top out around 256KB; 1 MB
# is an order of magnitude of headroom while still bounding allocation (L2).
MAX_WEBHOOK_BYTES = 1_048_576

# How many recent audit entries to scan for duplicate webhook event IDs (M1).
# Stripe retries failed webhooks for up to 3 days; 200 entries covers the
# typical replay window for a low-volume service. If volume grows, switch
# to an indexed dedup store.
WEBHOOK_DEDUP_WINDOW = 200


def _event_already_processed(event_id: str | None) -> bool:
    """True if a `stripe.webhook` audit record with the same event_id exists."""
    if not event_id:
        return False
    for record in audit.tail(WEBHOOK_DEDUP_WINDOW):
        if record.get("event") != "stripe.webhook":
            continue
        if record.get("payload_meta", {}).get("event_id") == event_id:
            return True
    return False


class CheckoutRequest(BaseModel):
    customer_email: str | None = None
    quantity: int = Field(default=1, ge=1, le=1000)
    client_reference_id: str | None = None


def _stripe():
    """Lazy-load the Stripe SDK + secret key. Raises 503 if either is missing."""
    try:
        import stripe
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail="stripe SDK not installed (pip install stripe)",
        ) from e
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY not set")
    stripe.api_key = key
    return stripe


def _required_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise HTTPException(status_code=503, detail=f"{name} not set")
    return v


@router.post("/checkout")
def create_checkout(req: CheckoutRequest) -> dict[str, Any]:
    stripe = _stripe()
    price_id = _required_env("STRIPE_PRICE_ID")
    success_url = _required_env("STRIPE_SUCCESS_URL")
    cancel_url = _required_env("STRIPE_CANCEL_URL")
    mode = os.environ.get("STRIPE_MODE", "subscription")

    request_id = audit.emit(
        "checkout.request",
        payload={"price_id": price_id, "quantity": req.quantity},
    )["request_id"]

    try:
        session = stripe.checkout.Session.create(
            mode=mode,
            line_items=[{"price": price_id, "quantity": req.quantity}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=req.customer_email,
            client_reference_id=req.client_reference_id,
            metadata={"request_id": request_id},
        )
    except Exception as e:
        # Audit the full error server-side; respond with a generic message
        # plus the request_id so operators can correlate without leaking
        # Stripe internals to the public client (L1).
        audit.emit(
            "checkout.error",
            payload={
                "error_kind": type(e).__name__,
                "error_detail": str(e),
            },
            request_id=request_id,
        )
        raise HTTPException(
            status_code=502,
            detail={"error": "checkout_failed", "request_id": request_id},
        ) from e

    audit.emit(
        "checkout.created",
        payload={"session_id": session.get("id"), "price_id": price_id},
        request_id=request_id,
    )
    return {
        "url": session.get("url"),
        "session_id": session.get("id"),
        "request_id": request_id,
    }


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict[str, Any]:
    stripe = _stripe()
    secret = _required_env("STRIPE_WEBHOOK_SECRET")
    sig = request.headers.get("stripe-signature")
    if not sig:
        raise HTTPException(status_code=400, detail="missing stripe-signature header")

    # Bound body size before allocation (L2). Trust Content-Length when given
    # but also stop reading mid-stream if a client lies about it.
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_WEBHOOK_BYTES:
                raise HTTPException(status_code=413, detail="payload too large")
        except ValueError as e:
            raise HTTPException(status_code=400, detail="invalid Content-Length") from e

    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_WEBHOOK_BYTES:
            raise HTTPException(status_code=413, detail="payload too large")

    try:
        event = stripe.Webhook.construct_event(body, sig, secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid payload") from e
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="invalid signature") from e

    # Idempotency: Stripe retries on 5xx/timeouts for up to 3 days. If we've
    # already audited this event_id, return success without re-processing (M1).
    event_id = event.get("id")
    if _event_already_processed(event_id):
        return {"received": True, "duplicate": True}

    event_type = event.get("type", "")
    request_id = audit.emit(
        "stripe.webhook",
        payload={"event_type": event_type, "event_id": event_id},
    )["request_id"]

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        audit.emit(
            "stripe.checkout_completed",
            payload={
                "event_type": event_type,
                "session_id": session.get("id"),
                "client_reference_id": session.get("client_reference_id"),
                "amount_total": session.get("amount_total"),
            },
            request_id=request_id,
        )

    return {"received": True}
