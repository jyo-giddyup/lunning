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
        audit.emit(
            "checkout.error",
            payload={"error": type(e).__name__},
            request_id=request_id,
        )
        raise HTTPException(status_code=502, detail=f"stripe error: {e}") from e

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
    body = await request.body()

    try:
        event = stripe.Webhook.construct_event(body, sig, secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid payload") from e
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="invalid signature") from e

    event_type = event.get("type", "")
    request_id = audit.emit(
        "stripe.webhook",
        payload={"event_type": event_type, "event_id": event.get("id")},
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
