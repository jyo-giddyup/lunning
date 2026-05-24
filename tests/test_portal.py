"""Tests for /portal-session endpoint.

Tests the Stripe Billing Portal session creation endpoint in isolation.
The Stripe stub is extended with billing_portal.Session.create.
"""
from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

from nil_predictor import api as api_module
from nil_predictor import customers


def _install_stripe_stub_with_portal(monkeypatch, *, portal_session=None,
                                     portal_raise=None):
    """Stripe stub extended with billing_portal.Session.create."""
    stripe_mod = types.ModuleType("stripe")
    stripe_mod.api_key = None

    class _PortalSession:
        @staticmethod
        def create(**kwargs):
            if portal_raise is not None:
                raise portal_raise
            return portal_session or {
                "id": "bps_test_123",
                "url": "https://billing.stripe.com/p/session/test",
            }

    billing_portal_ns = types.SimpleNamespace(Session=_PortalSession)
    stripe_mod.billing_portal = billing_portal_ns

    error_mod = types.ModuleType("stripe.error")
    stripe_mod.error = error_mod

    monkeypatch.setitem(sys.modules, "stripe", stripe_mod)
    monkeypatch.setitem(sys.modules, "stripe.error", error_mod)
    return stripe_mod


@pytest.fixture
def portal_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    # Entitlement mode ON so customer keys pass the middleware.
    monkeypatch.setattr(api_module, "NIL_API_KEY", "admin-key")
    monkeypatch.setattr(api_module, "NIL_REQUIRE_PAYMENT", True)
    api_module._checkout_buckets.clear()
    return TestClient(api_module.app)


def _make_customer(session_id="cs_portal", customer_id="cus_portal",
                   subscription_id="sub_portal"):
    return customers.create_from_session({
        "id": session_id,
        "customer": customer_id,
        "subscription": subscription_id,
        "customer_email": "portal@example.com",
    })


def test_portal_session_success(portal_client, monkeypatch):
    rec = _make_customer()
    _install_stripe_stub_with_portal(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PORTAL_RETURN_URL", "https://example.com/billing")

    r = portal_client.post("/portal-session", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"] == "https://billing.stripe.com/p/session/test"
    assert body["session_id"] == "bps_test_123"
    assert body["request_id"]


def test_portal_session_unknown_key_returns_404(portal_client, monkeypatch):
    _install_stripe_stub_with_portal(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PORTAL_RETURN_URL", "https://example.com/billing")

    r = portal_client.post("/portal-session", headers={"X-API-Key": "admin-key"})
    assert r.status_code == 404
    assert "no customer" in r.json()["detail"]


def test_portal_session_no_stripe_customer_id_returns_409(portal_client, monkeypatch):
    rec = customers.create_from_session({
        "id": "cs_no_cus",
        "customer": None,
        "subscription": "sub_x",
    })
    _install_stripe_stub_with_portal(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PORTAL_RETURN_URL", "https://example.com/billing")

    r = portal_client.post("/portal-session", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 409
    assert "stripe_customer_id" in r.json()["detail"]


def test_portal_session_missing_return_url_returns_503(portal_client, monkeypatch):
    rec = _make_customer(session_id="cs_nourl")
    _install_stripe_stub_with_portal(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.delenv("STRIPE_PORTAL_RETURN_URL", raising=False)

    r = portal_client.post("/portal-session", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 503
    assert "STRIPE_PORTAL_RETURN_URL" in r.json()["detail"]


def test_portal_session_stripe_failure_returns_502(portal_client, monkeypatch):
    rec = _make_customer(session_id="cs_fail")
    _install_stripe_stub_with_portal(monkeypatch, portal_raise=RuntimeError("nope"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PORTAL_RETURN_URL", "https://example.com/billing")

    r = portal_client.post("/portal-session", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert detail["error"] == "portal_create_failed"
    assert detail["request_id"]
    assert "nope" not in r.text

    from nil_predictor import audit
    errors = [e for e in audit.tail(20) if e["event"] == "portal.error"]
    assert errors
    assert errors[-1]["payload_meta"]["error_detail"] == "nope"
