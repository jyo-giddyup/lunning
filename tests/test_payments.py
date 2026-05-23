"""Tests for the Stripe checkout + webhook + customer endpoints.

The Stripe SDK is replaced with a stub so no real API or network calls
are made. We verify:
  - missing env / SDK -> 503
  - successful checkout returns the session URL
  - webhook rejects missing/invalid signatures, replays, oversize bodies
  - webhook on checkout.session.completed mints a customer + API key
  - webhook on subscription.updated / .deleted propagates status
  - /customer/bootstrap is one-shot
  - /me returns the calling customer's record
"""
from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

from nil_predictor import api as api_module


def _install_stripe_stub(monkeypatch, *, session=None, raise_on_create=None,
                        construct_event=None):
    """Insert a fake `stripe` module into sys.modules and return it.

    Caller can mutate the returned module afterwards (e.g. swap out
    Webhook.construct_event) so SignatureVerificationError raised by a
    boom function and the one caught by the handler are the same class.
    """
    stripe_mod = types.ModuleType("stripe")
    stripe_mod.api_key = None

    class _Session:
        @staticmethod
        def create(**kwargs):
            if raise_on_create is not None:
                raise raise_on_create
            return session or {
                "id": "cs_test_123",
                "url": "https://checkout.stripe.com/test",
            }

    checkout_ns = types.SimpleNamespace(Session=_Session)
    stripe_mod.checkout = checkout_ns

    error_mod = types.ModuleType("stripe.error")

    class SignatureVerificationError(Exception):
        pass

    error_mod.SignatureVerificationError = SignatureVerificationError
    stripe_mod.error = error_mod

    class _Webhook:
        @staticmethod
        def construct_event(body, sig, secret):
            if construct_event is not None:
                return construct_event(body, sig, secret)
            return {"id": "evt_1", "type": "ping", "data": {"object": {}}}

    stripe_mod.Webhook = _Webhook

    monkeypatch.setitem(sys.modules, "stripe", stripe_mod)
    monkeypatch.setitem(sys.modules, "stripe.error", error_mod)
    return stripe_mod


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    # Each test gets its own customers DB so webhook customer creation
    # lands in an isolated file and doesn't bleed between tests.
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    # Force the auth gate dormant for every payments test, regardless of
    # what other tests might have left in os.environ.
    monkeypatch.setattr(api_module, "NIL_API_KEY", "")
    monkeypatch.setattr(api_module, "NIL_REQUIRE_PAYMENT", False)
    # Reset the in-memory rate-limit buckets so tests don't bleed into
    # each other's quotas.
    api_module._checkout_buckets.clear()
    return TestClient(api_module.app)


def test_checkout_missing_secret_key_returns_503(app_client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    _install_stripe_stub(monkeypatch)
    r = app_client.post("/checkout", json={})
    assert r.status_code == 503
    assert "STRIPE_SECRET_KEY" in r.json()["detail"]


def test_checkout_missing_price_id_returns_503(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
    r = app_client.post("/checkout", json={})
    assert r.status_code == 503
    assert "STRIPE_PRICE_ID" in r.json()["detail"]


def test_checkout_success_returns_session_url(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")
    monkeypatch.setenv("STRIPE_SUCCESS_URL", "https://example.com/ok")
    monkeypatch.setenv("STRIPE_CANCEL_URL", "https://example.com/cancel")
    r = app_client.post("/checkout", json={"customer_email": "a@b.co"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"] == "https://checkout.stripe.com/test"
    assert body["session_id"] == "cs_test_123"
    assert body["request_id"]


def test_checkout_stripe_failure_returns_generic_502(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch, raise_on_create=RuntimeError("boom"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")
    monkeypatch.setenv("STRIPE_SUCCESS_URL", "https://example.com/ok")
    monkeypatch.setenv("STRIPE_CANCEL_URL", "https://example.com/cancel")
    r = app_client.post("/checkout", json={})
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert detail["error"] == "checkout_failed"
    assert detail["request_id"]
    assert "boom" not in r.text

    from nil_predictor import audit
    matches = [
        rec for rec in audit.tail(20)
        if rec["event"] == "checkout.error"
        and rec["request_id"] == detail["request_id"]
    ]
    assert matches, "checkout.error not found in audit log"
    assert matches[-1]["payload_meta"]["error_detail"] == "boom"
    assert matches[-1]["payload_meta"]["error_kind"] == "RuntimeError"


def test_webhook_missing_signature_returns_400(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    r = app_client.post("/webhooks/stripe", content=b"{}")
    assert r.status_code == 400
    assert "signature" in r.json()["detail"]


def test_webhook_invalid_signature_returns_400(app_client, monkeypatch):
    stripe_mod = _install_stripe_stub(monkeypatch)

    def boom(body, sig, secret):
        raise stripe_mod.error.SignatureVerificationError("bad sig")

    stripe_mod.Webhook.construct_event = staticmethod(boom)

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    r = app_client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert r.status_code == 400
    assert "signature" in r.json()["detail"]


def test_webhook_checkout_completed_creates_customer(app_client, monkeypatch):
    event = {
        "id": "evt_42",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_42",
            "client_reference_id": "user_99",
            "customer": "cus_42",
            "subscription": "sub_42",
            "customer_email": "new@example.com",
            "amount_total": 2900,
        }},
    }
    _install_stripe_stub(monkeypatch, construct_event=lambda b, s, k: event)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    r = app_client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=ok"},
    )
    assert r.status_code == 200
    assert r.json() == {"received": True}

    # Customer row exists with status active and an nk_-prefixed api_key.
    from nil_predictor import customers
    bootstrap = customers.claim_bootstrap("cs_test_42")
    assert bootstrap is not None
    assert bootstrap["api_key"].startswith("nk_")
    assert bootstrap["email"] == "new@example.com"
    assert bootstrap["status"] == "active"

    from nil_predictor import audit
    events = [e["event"] for e in audit.tail(20)]
    assert "stripe.webhook" in events
    assert "stripe.checkout_completed" in events
    assert "stripe.customer_created" in events


def test_customer_bootstrap_endpoint_is_one_shot(app_client, monkeypatch):
    """After the customer is created via webhook, /customer/bootstrap
    returns the api_key on the first call and 404 on subsequent calls."""
    event = {
        "id": "evt_b1",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_boot_1",
            "customer_email": "boot@example.com",
            "amount_total": 1000,
        }},
    }
    _install_stripe_stub(monkeypatch, construct_event=lambda b, s, k: event)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    app_client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=ok"},
    )

    r = app_client.get("/customer/bootstrap", params={"session_id": "cs_boot_1"})
    assert r.status_code == 200
    body = r.json()
    assert body["api_key"].startswith("nk_")
    assert body["email"] == "boot@example.com"
    assert body["status"] == "active"

    # Second call must be 404.
    r2 = app_client.get("/customer/bootstrap", params={"session_id": "cs_boot_1"})
    assert r2.status_code == 404


def test_me_returns_customer_record_when_key_known(app_client):
    from nil_predictor import customers
    rec = customers.create_from_session({
        "id": "cs_me", "customer_email": "me@example.com",
    })
    r = app_client.get("/me", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@example.com"
    assert body["status"] == "active"


def test_me_returns_404_for_unknown_key(app_client):
    r = app_client.get("/me", headers={"X-API-Key": "nk_does_not_exist"})
    assert r.status_code == 404


def test_webhook_subscription_canceled_flips_status(app_client, monkeypatch):
    from nil_predictor import customers
    customers.create_from_session({
        "id": "cs_sub_c",
        "subscription": "sub_to_cancel",
        "customer_email": "sub@example.com",
    })

    event = {
        "id": "evt_sub_cancel",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_to_cancel", "status": "canceled"}},
    }
    _install_stripe_stub(monkeypatch, construct_event=lambda b, s, k: event)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    r = app_client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=ok"},
    )
    assert r.status_code == 200

    rec = customers.claim_bootstrap("cs_sub_c")
    assert rec is not None
    assert rec["status"] == "canceled"

    from nil_predictor import audit
    events = [e["event"] for e in audit.tail(20)]
    assert "stripe.subscription_canceled" in events


def test_webhook_subscription_updated_propagates_status(app_client, monkeypatch):
    from nil_predictor import customers
    customers.create_from_session({
        "id": "cs_sub_u",
        "subscription": "sub_to_update",
    })

    event = {
        "id": "evt_sub_update",
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_to_update", "status": "past_due"}},
    }
    _install_stripe_stub(monkeypatch, construct_event=lambda b, s, k: event)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    r = app_client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=ok"},
    )
    assert r.status_code == 200

    rec = customers.claim_bootstrap("cs_sub_u")
    assert rec is not None
    assert rec["status"] == "past_due"
    assert not customers.is_active(rec)


def test_webhook_replay_is_idempotent(app_client, monkeypatch):
    event = {
        "id": "evt_replay_1",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_replay_1", "amount_total": 1000}},
    }
    _install_stripe_stub(monkeypatch, construct_event=lambda b, s, k: event)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")

    first = app_client.post(
        "/webhooks/stripe", content=b"{}",
        headers={"stripe-signature": "t=1,v1=ok"},
    )
    assert first.status_code == 200
    assert first.json() == {"received": True}

    second = app_client.post(
        "/webhooks/stripe", content=b"{}",
        headers={"stripe-signature": "t=1,v1=ok"},
    )
    assert second.status_code == 200
    assert second.json() == {"received": True, "duplicate": True}

    from nil_predictor import audit
    webhook_records = [
        r for r in audit.tail(50)
        if r["event"] == "stripe.webhook"
        and r["payload_meta"].get("event_id") == "evt_replay_1"
    ]
    assert len(webhook_records) == 1


def test_webhook_invalid_payload_returns_400(app_client, monkeypatch):
    stripe_mod = _install_stripe_stub(monkeypatch)

    def bad_payload(body, sig, secret):
        raise ValueError("not json")

    stripe_mod.Webhook.construct_event = staticmethod(bad_payload)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")

    r = app_client.post(
        "/webhooks/stripe",
        content=b"not really json",
        headers={"stripe-signature": "t=1,v1=ok"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid payload"


def test_webhook_oversize_body_returns_413(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")

    big_body = b"x" * (2 * 1024 * 1024)
    r = app_client.post(
        "/webhooks/stripe",
        content=big_body,
        headers={"stripe-signature": "t=1,v1=ok"},
    )
    assert r.status_code == 413
    assert "too large" in r.json()["detail"]


def test_checkout_rate_limit(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")
    monkeypatch.setenv("STRIPE_SUCCESS_URL", "https://example.com/ok")
    monkeypatch.setenv("STRIPE_CANCEL_URL", "https://example.com/cancel")

    monkeypatch.setattr(api_module, "CHECKOUT_RATE_LIMIT", 3)

    for _ in range(3):
        r = app_client.post("/checkout", json={})
        assert r.status_code == 200, r.text

    blocked = app_client.post("/checkout", json={})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1
