"""Tests for multi-tier API plans."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from nil_predictor import customers, tiers
from nil_predictor.tiers import TierName, TIERS
from nil_predictor.train import train_all


ATHLETE = {
    "sport": "football",
    "position": "QB",
    "conference": "SEC",
    "year": "JR",
    "starter": True,
    "performance_score": 88,
    "instagram_followers": 250_000,
    "tiktok_followers": 180_000,
    "twitter_followers": 90_000,
}


@pytest.fixture(scope="module")
def art_dir(tmp_path_factory):
    art = tmp_path_factory.mktemp("art")
    train_all(n=600, seed=3, out_dir=art)
    return art


# ── Tier definition tests ───────────────────────────────────────────

def test_all_tiers_defined():
    assert set(TIERS.keys()) == {TierName.free, TierName.pro, TierName.enterprise}


def test_free_tier_limits():
    spec = TIERS[TierName.free]
    assert spec.daily_limit == 50
    assert spec.max_batch == 1
    assert "/predict" in spec.features
    assert "/explain" not in spec.features


def test_pro_tier_limits():
    spec = TIERS[TierName.pro]
    assert spec.daily_limit == 1000
    assert spec.max_batch == 100
    assert "/predict" in spec.features
    assert "/explain" in spec.features
    assert "/agents" in spec.features
    assert "/revenue" not in spec.features


def test_enterprise_tier_unlimited():
    spec = TIERS[TierName.enterprise]
    assert spec.daily_limit is None
    assert "/revenue" in spec.features


# ── Price mapping tests ─────────────────────────────────────────────

def test_price_to_tier_default(monkeypatch):
    monkeypatch.delenv("STRIPE_PRICE_ID_FREE", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID_PRO", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID_ENTERPRISE", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
    assert tiers.price_to_tier("price_unknown") == TierName.pro


def test_price_to_tier_from_env(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_ID_FREE", "price_free_123")
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", "price_pro_456")
    monkeypatch.setenv("STRIPE_PRICE_ID_ENTERPRISE", "price_ent_789")
    assert tiers.price_to_tier("price_free_123") == TierName.free
    assert tiers.price_to_tier("price_pro_456") == TierName.pro
    assert tiers.price_to_tier("price_ent_789") == TierName.enterprise


def test_price_to_tier_legacy_fallback(monkeypatch):
    monkeypatch.delenv("STRIPE_PRICE_ID_FREE", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID_PRO", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID_ENTERPRISE", raising=False)
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_legacy")
    assert tiers.price_to_tier("price_legacy") == TierName.pro


# ── Usage tracking tests ────────────────────────────────────────────

def test_increment_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    count = tiers.increment_usage("nk_test_key", customers._conn)
    assert count == 1
    count = tiers.increment_usage("nk_test_key", customers._conn)
    assert count == 2


def test_get_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    usage = tiers.get_usage("nk_nobody", customers._conn)
    assert usage["request_count"] == 0
    tiers.increment_usage("nk_nobody", customers._conn)
    usage = tiers.get_usage("nk_nobody", customers._conn)
    assert usage["request_count"] == 1


# ── Feature gate tests ──────────────────────────────────────────────

def test_path_allowed_free():
    assert tiers.path_allowed("/predict", TierName.free) is True
    assert tiers.path_allowed("/explain", TierName.free) is False
    assert tiers.path_allowed("/agents/watchlist", TierName.free) is False
    assert tiers.path_allowed("/revenue", TierName.free) is False


def test_path_allowed_pro():
    assert tiers.path_allowed("/predict", TierName.pro) is True
    assert tiers.path_allowed("/explain", TierName.pro) is True
    assert tiers.path_allowed("/agents/run", TierName.pro) is True
    assert tiers.path_allowed("/revenue", TierName.pro) is False


def test_path_allowed_enterprise():
    assert tiers.path_allowed("/predict", TierName.enterprise) is True
    assert tiers.path_allowed("/revenue", TierName.enterprise) is True


# ── Customer tier migration tests ───────────────────────────────────

def test_customer_created_with_tier(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    rec = customers.create_from_session(
        {"id": "cs_tier_test", "customer_email": "a@b.co"},
        tier="free",
    )
    assert rec["tier"] == "free"


def test_customer_defaults_to_pro(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    rec = customers.create_from_session(
        {"id": "cs_default_test", "customer_email": "b@c.co"},
    )
    assert rec["tier"] == "pro"


# ── API integration tests ───────────────────────────────────────────

@pytest.fixture()
def tier_client(art_dir, tmp_path, monkeypatch):
    """Client with per-customer entitlement enabled."""
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(art_dir))
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    import nil_predictor.api as api_mod
    monkeypatch.setattr(api_mod, "NIL_API_KEY", "admin-key")
    monkeypatch.setattr(api_mod, "NIL_REQUIRE_PAYMENT", True)
    monkeypatch.setattr(api_mod, "NIL_ENABLE_AGENTS", False)
    api_mod._checkout_buckets.clear()
    return TestClient(api_mod.app)


def _make_customer(tier: str) -> dict:
    import uuid
    session_id = f"cs_{uuid.uuid4().hex[:8]}"
    return customers.create_from_session(
        {"id": session_id, "customer_email": f"{tier}@test.co"},
        tier=tier,
    )


def test_free_tier_denied_explain(tier_client):
    rec = _make_customer("free")
    r = tier_client.get("/explain", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 403


def test_free_tier_allowed_predict(tier_client):
    rec = _make_customer("free")
    r = tier_client.post("/predict", json=ATHLETE,
                         headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 200


def test_free_tier_batch_limited(tier_client):
    rec = _make_customer("free")
    r = tier_client.post("/predict", json=[ATHLETE, ATHLETE],
                         headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 413


def test_pro_tier_allowed_explain(tier_client):
    rec = _make_customer("pro")
    r = tier_client.get("/explain", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 200


def test_pro_tier_denied_revenue(tier_client):
    rec = _make_customer("pro")
    r = tier_client.get("/revenue", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 403


def test_enterprise_tier_allowed_revenue(tier_client):
    rec = _make_customer("enterprise")
    # Revenue needs Stripe SDK which isn't installed in test, but the
    # request should get past the tier gate (503 from missing SDK is fine).
    r = tier_client.get("/revenue", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code in (200, 503)


def test_admin_key_bypasses_tier_gate(tier_client):
    r = tier_client.get("/revenue", headers={"X-API-Key": "admin-key"})
    assert r.status_code in (200, 503)


def test_rate_limit_enforced(tier_client, tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    rec = _make_customer("free")
    # The free tier has a 50/day limit. We'll exceed it.
    for _ in range(50):
        tiers.increment_usage(rec["api_key"], customers._conn)
    r = tier_client.post("/predict", json=ATHLETE,
                         headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 429
    assert "daily_rate_limit_exceeded" in r.json()["detail"]


def test_me_shows_tier_and_usage(tier_client):
    rec = _make_customer("pro")
    r = tier_client.get("/me", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "pro"
    assert "usage" in body
    assert body["usage"]["daily_limit"] == 1000
    assert body["max_batch"] == 100
    assert "/predict" in body["features"]


def test_checkout_with_tier_param(tier_client, monkeypatch, tmp_path):
    """Checkout accepts a tier param and resolves the correct price env."""
    import types
    import sys

    # Install Stripe stub
    stripe_mod = types.ModuleType("stripe")
    stripe_mod.api_key = None

    class _Checkout:
        class Session:
            @staticmethod
            def create(**kwargs):
                return {"id": "cs_new", "url": "https://pay.stripe.com/x"}
    stripe_mod.checkout = _Checkout
    stripe_mod.error = types.ModuleType("stripe.error")

    class SigError(Exception):
        pass
    stripe_mod.error.SignatureVerificationError = SigError
    monkeypatch.setitem(sys.modules, "stripe", stripe_mod)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PRICE_ID_FREE", "price_free_test")
    monkeypatch.setenv("STRIPE_SUCCESS_URL", "https://example.com/ok")
    monkeypatch.setenv("STRIPE_CANCEL_URL", "https://example.com/cancel")

    r = tier_client.post("/checkout", json={"tier": "free"})
    assert r.status_code == 200
    assert "url" in r.json()


def test_checkout_unknown_tier_returns_400(tier_client, monkeypatch, tmp_path):
    import types
    import sys

    stripe_mod = types.ModuleType("stripe")
    stripe_mod.api_key = None
    stripe_mod.error = types.ModuleType("stripe.error")
    monkeypatch.setitem(sys.modules, "stripe", stripe_mod)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")

    r = tier_client.post("/checkout", json={"tier": "platinum"})
    assert r.status_code == 400
