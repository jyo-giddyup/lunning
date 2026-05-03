"""Tests for the Stripe checkout + webhook endpoints.

The Stripe SDK is replaced with a stub so no real API or network calls
are made. We verify:
  - missing env / SDK -> 503
  - successful checkout returns the session URL
  - webhook rejects missing/invalid signatures
  - webhook accepts a valid event and dispatches to the audit log
"""
from __future__ import annotations

import sys
import types

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient


def _install_stripe_stub(monkeypatch, *, session=None, raise_on_create=None,
                        construct_event=None):
    """Insert a fake `stripe` module into sys.modules."""
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
    # Force a fresh import so the router picks up the patched env.
    for mod in list(sys.modules):
        if mod.startswith("nil_predictor"):
            sys.modules.pop(mod)
    from nil_predictor.api import app
    return TestClient(app)


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


def test_checkout_stripe_failure_returns_502(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch, raise_on_create=RuntimeError("boom"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")
    monkeypatch.setenv("STRIPE_SUCCESS_URL", "https://example.com/ok")
    monkeypatch.setenv("STRIPE_CANCEL_URL", "https://example.com/cancel")
    r = app_client.post("/checkout", json={})
    assert r.status_code == 502
    assert "boom" in r.json()["detail"]


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

    _install_stripe_stub(monkeypatch, construct_event=boom)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
    r = app_client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert r.status_code == 400
    assert "signature" in r.json()["detail"]


def test_webhook_checkout_completed_is_acknowledged(app_client, monkeypatch, tmp_path):
    event = {
        "id": "evt_42",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_42",
            "client_reference_id": "user_99",
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

    # Audit log should record both stripe.webhook and stripe.checkout_completed.
    from nil_predictor import audit
    events = [e["event"] for e in audit.tail(10)]
    assert "stripe.webhook" in events
    assert "stripe.checkout_completed" in events
