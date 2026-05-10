"""Tests for the /revenue endpoint.

Stripe is replaced with a stub so no real API or network calls are
made. We cover the 503 / 400 / 502 error paths and verify per-currency
rollup math against a fixture of mixed-status, mixed-currency charges.
"""
from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

from nil_predictor import api as api_module


def _install_stripe_stub(monkeypatch, *, charges=None, raise_on_list=None):
    """Insert a fake `stripe` module whose Charge.list().auto_paging_iter()
    yields the given dict list."""
    stripe_mod = types.ModuleType("stripe")
    stripe_mod.api_key = None

    class _Page:
        def __init__(self, items):
            self._items = items

        def auto_paging_iter(self):
            return iter(self._items)

    class _Charge:
        @staticmethod
        def list(**kwargs):
            if raise_on_list is not None:
                raise raise_on_list
            return _Page(list(charges or []))

    stripe_mod.Charge = _Charge

    # Other payments.py paths import these — stub so a stray import does
    # not blow up when the test exercises only /revenue.
    stripe_mod.checkout = types.SimpleNamespace(
        Session=types.SimpleNamespace(create=lambda **kw: {}),
    )
    error_mod = types.ModuleType("stripe.error")

    class SignatureVerificationError(Exception):
        pass

    error_mod.SignatureVerificationError = SignatureVerificationError
    stripe_mod.error = error_mod
    stripe_mod.Webhook = types.SimpleNamespace(
        construct_event=lambda *a, **kw: {},
    )

    monkeypatch.setitem(sys.modules, "stripe", stripe_mod)
    monkeypatch.setitem(sys.modules, "stripe.error", error_mod)
    return stripe_mod


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    monkeypatch.setattr(api_module, "NIL_API_KEY", "")
    return TestClient(api_module.app)


def test_revenue_missing_secret_key_returns_503(app_client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    _install_stripe_stub(monkeypatch)
    r = app_client.get("/revenue")
    assert r.status_code == 503
    assert "STRIPE_SECRET_KEY" in r.json()["detail"]


def test_revenue_invalid_date_returns_400(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    r = app_client.get("/revenue?since=yesterday")
    assert r.status_code == 400
    assert "since" in r.json()["detail"]


def test_revenue_since_after_until_returns_400(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    r = app_client.get("/revenue?since=2026-02-01&until=2026-01-01")
    assert r.status_code == 400
    assert "before" in r.json()["detail"]


def test_revenue_aggregates_per_currency_correctly(app_client, monkeypatch):
    charges = [
        {"amount": 10000, "amount_refunded": 0,
         "currency": "usd", "status": "succeeded"},
        {"amount": 5000, "amount_refunded": 1500,
         "currency": "usd", "status": "succeeded"},
        {"amount": 9999, "amount_refunded": 0,
         "currency": "usd", "status": "failed"},
        {"amount": 8000, "amount_refunded": 0,
         "currency": "eur", "status": "succeeded"},
    ]
    _install_stripe_stub(monkeypatch, charges=charges)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    r = app_client.get("/revenue")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_charges"] == 3
    assert body["currencies"]["usd"] == {
        "gross_minor": 15000, "net_minor": 13500, "count": 2,
    }
    assert body["currencies"]["eur"] == {
        "gross_minor": 8000, "net_minor": 8000, "count": 1,
    }


def test_revenue_stripe_failure_returns_502(app_client, monkeypatch):
    _install_stripe_stub(monkeypatch, raise_on_list=RuntimeError("boom"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    r = app_client.get("/revenue")
    assert r.status_code == 502
    assert "boom" in r.json()["detail"]
