"""Stripe Checkout + webhook endpoints + customer-facing reads.

Monetization gate for the predictor:

    POST /checkout                 -> create a Checkout Session, return its URL
    POST /webhooks/stripe          -> verify signature, process subscription events
    GET  /customer/bootstrap       -> one-shot API-key retrieval after checkout
    GET  /me                       -> the calling customer's record
    GET  /revenue                  -> succeeded-charge totals per currency

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
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import audit, customers

router = APIRouter()

# Hard cap on webhook body size. Stripe webhooks top out around 256KB; 1 MB
# is an order of magnitude of headroom while still bounding allocation.
MAX_WEBHOOK_BYTES = 1_048_576

# How many recent audit entries to scan for duplicate webhook event IDs.
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

    # Bound body size before allocation. Trust Content-Length when given
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
    # already audited this event_id, return success without re-processing.
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
        try:
            rec = customers.create_from_session(session)
            audit.emit(
                "stripe.customer_created",
                payload={
                    "event_type": event_type,
                    "session_id": rec["stripe_session_id"],
                    "subscription_id": rec.get("stripe_subscription_id"),
                },
                request_id=request_id,
            )
        except Exception as e:
            # Customer creation failing is bad but we still want to ACK
            # the webhook so Stripe doesn't retry forever. The audit
            # entry plus the alert from missing stripe.customer_created
            # is enough signal for an operator to investigate.
            audit.emit(
                "stripe.customer_create_error",
                payload={
                    "event_type": event_type,
                    "error_kind": type(e).__name__,
                    "error_detail": str(e),
                },
                request_id=request_id,
            )

    elif event_type == "customer.subscription.updated":
        sub = event["data"]["object"]
        status = sub.get("status", "")
        customers.update_status_by_subscription(sub.get("id", ""), status)
        audit.emit(
            "stripe.subscription_updated",
            payload={
                "event_type": event_type,
                "subscription_id": sub.get("id"),
                "status": status,
            },
            request_id=request_id,
        )

    elif event_type == "customer.subscription.deleted":
        sub = event["data"]["object"]
        customers.update_status_by_subscription(sub.get("id", ""), "canceled")
        audit.emit(
            "stripe.subscription_canceled",
            payload={
                "event_type": event_type,
                "subscription_id": sub.get("id"),
                "status": "canceled",
            },
            request_id=request_id,
        )

    return {"received": True}


# --- Customer-facing reads -----------------------------------------------


@router.get("/customer/bootstrap")
def customer_bootstrap(session_id: str) -> dict[str, Any]:
    """One-shot API-key retrieval right after Stripe redirects.

    The consumer's /billing/success page calls this with the
    `session_id` Stripe substitutes into the redirect URL. Returns
    the API key once; subsequent calls with the same session_id
    return 404 — the customer must save the value (or, once we
    ship welcome-email delivery, recover it from email).

    Authentication is by knowledge of the one-time Stripe session id;
    the path is in PUBLIC_PATHS so the middleware doesn't gate it.
    """
    rec = customers.claim_bootstrap(session_id)
    if not rec:
        raise HTTPException(
            status_code=404,
            detail="session not found or already claimed",
        )
    return {
        "api_key": rec["api_key"],
        "email": rec["email"],
        "status": rec["status"],
    }


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    """Return the calling customer's record.

    Gated by the regular X-API-Key middleware (this is why /me is
    NOT in PUBLIC_PATHS — we *need* the gate to identify the caller).
    Useful for the consumer to render "Signed in as ..." or to check
    that a saved API key is still active.
    """
    rec = customers.find_by_api_key(request.headers.get("x-api-key", ""))
    if not rec:
        raise HTTPException(status_code=404, detail="no customer for this key")
    return {
        "email": rec["email"],
        "status": rec["status"],
        "created_at": rec["created_at"],
    }


# --- Revenue --------------------------------------------------------------


def _parse_date(s: str, label: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"invalid `{label}` date {s!r}, expected YYYY-MM-DD",
        ) from e


def _parse_window(since: str | None, until: str | None) -> tuple[int, int]:
    """Parse YYYY-MM-DD into UTC unix timestamps; defaults to last 30 days."""
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    until_dt = (today + timedelta(days=1)) if until is None else _parse_date(until, "until")
    since_dt = (today - timedelta(days=30)) if since is None else _parse_date(since, "since")
    if since_dt >= until_dt:
        raise HTTPException(status_code=400, detail="`since` must be before `until`")
    return int(since_dt.timestamp()), int(until_dt.timestamp())


@router.get("/revenue")
def revenue(since: str | None = None, until: str | None = None) -> dict[str, Any]:
    """Succeeded-charge totals per currency in a date window.

    Defaults to the last 30 days (UTC). Amounts are returned in
    Stripe's smallest unit per currency (cents for USD, yen for JPY,
    etc.) so callers format correctly without a zero-decimal-currency
    table. Net = gross - refunds; processing fees are not subtracted
    (those live on BalanceTransaction, not Charge).
    """
    stripe = _stripe()
    since_ts, until_ts = _parse_window(since, until)

    request_id = audit.emit(
        "revenue.request",
        payload={"since": since_ts, "until": until_ts},
    )["request_id"]

    by_currency: dict[str, dict[str, int]] = {}
    total = 0
    try:
        page = stripe.Charge.list(
            created={"gte": since_ts, "lt": until_ts},
            limit=100,
        )
        for charge in page.auto_paging_iter():
            if charge.get("status") != "succeeded":
                continue
            cur = (charge.get("currency") or "").lower()
            bucket = by_currency.setdefault(
                cur, {"gross_minor": 0, "net_minor": 0, "count": 0}
            )
            amount = int(charge.get("amount") or 0)
            refunded = int(charge.get("amount_refunded") or 0)
            bucket["gross_minor"] += amount
            bucket["net_minor"] += amount - refunded
            bucket["count"] += 1
            total += 1
    except HTTPException:
        raise
    except Exception as e:
        audit.emit(
            "revenue.error",
            payload={"error_kind": type(e).__name__},
            request_id=request_id,
        )
        raise HTTPException(status_code=502, detail=f"stripe error: {e}") from e

    audit.emit(
        "revenue.response",
        payload={"currencies": sorted(by_currency), "n_charges": total},
        request_id=request_id,
    )
    return {
        "since": since_ts,
        "until": until_ts,
        "currencies": by_currency,
        "total_charges": total,
        "request_id": request_id,
    }
