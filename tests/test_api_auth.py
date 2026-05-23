"""API key gate behaviour.

Two modes are tested:

1) Legacy / dev (NIL_REQUIRE_PAYMENT off): single shared NIL_API_KEY
   gates every non-public endpoint.
2) Entitlement (NIL_REQUIRE_PAYMENT on): X-API-Key must resolve to
   either NIL_API_KEY (dev override) or an active customer row in
   the SQLite store.
"""
import pytest
from fastapi.testclient import TestClient

from nil_predictor import api as api_module
from nil_predictor import customers


# --- Legacy single-shared-key mode ---------------------------------------


@pytest.fixture
def gated_client(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "NIL_API_KEY", "shh-its-a-secret")
    monkeypatch.setattr(api_module, "NIL_REQUIRE_PAYMENT", False)
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    return TestClient(api_module.app)


@pytest.fixture
def open_client(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "NIL_API_KEY", "")
    monkeypatch.setattr(api_module, "NIL_REQUIRE_PAYMENT", False)
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    return TestClient(api_module.app)


def test_health_is_public_when_gated(gated_client):
    r = gated_client.get("/health")
    assert r.status_code == 200
    assert r.json()["auth_required"] is True


def test_schema_requires_key_when_gated(gated_client):
    r = gated_client.get("/schema")
    assert r.status_code == 401


def test_schema_accepts_correct_key(gated_client):
    r = gated_client.get("/schema", headers={"X-API-Key": "shh-its-a-secret"})
    assert r.status_code == 200


def test_schema_rejects_wrong_key(gated_client):
    r = gated_client.get("/schema", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401


def test_predict_requires_key_when_gated(gated_client):
    r = gated_client.post("/predict", json={"athletes": []})
    assert r.status_code == 401


def test_open_mode_no_key_required(open_client):
    r = open_client.get("/schema")
    assert r.status_code == 200


# --- Per-customer entitlement mode ---------------------------------------


@pytest.fixture
def entitlement_client(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "NIL_API_KEY", "admin-override")
    monkeypatch.setattr(api_module, "NIL_REQUIRE_PAYMENT", True)
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))
    return TestClient(api_module.app)


def _make_customer(session_id: str = "cs_test",
                   subscription_id: str = "sub_test",
                   email: str = "c@example.com") -> dict:
    return customers.create_from_session({
        "id": session_id,
        "customer": "cus_x",
        "subscription": subscription_id,
        "customer_email": email,
    })


def test_entitlement_no_key_returns_401(entitlement_client):
    r = entitlement_client.get("/schema")
    assert r.status_code == 401


def test_entitlement_valid_customer_key_passes(entitlement_client):
    rec = _make_customer()
    r = entitlement_client.get("/schema", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 200


def test_entitlement_unknown_key_returns_401(entitlement_client):
    r = entitlement_client.get("/schema", headers={"X-API-Key": "nk_garbage"})
    assert r.status_code == 401


def test_entitlement_canceled_customer_returns_401(entitlement_client):
    rec = _make_customer(subscription_id="sub_to_cancel")
    customers.update_status_by_subscription("sub_to_cancel", "canceled")
    r = entitlement_client.get("/schema", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 401


def test_entitlement_past_due_customer_returns_401(entitlement_client):
    rec = _make_customer(subscription_id="sub_past_due")
    customers.update_status_by_subscription("sub_past_due", "past_due")
    r = entitlement_client.get("/schema", headers={"X-API-Key": rec["api_key"]})
    assert r.status_code == 401


def test_entitlement_admin_override_still_works(entitlement_client):
    """NIL_API_KEY remains accepted in entitlement mode so operators can
    still poke /predict without an entry in the customer table."""
    r = entitlement_client.get("/schema", headers={"X-API-Key": "admin-override"})
    assert r.status_code == 200


def test_entitlement_health_public(entitlement_client):
    r = entitlement_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["auth_required"] is True
    assert body["require_payment"] is True


def test_entitlement_bootstrap_path_public(entitlement_client):
    """/customer/bootstrap must NOT be gated — the caller doesn't have
    the key yet. With an unknown session_id we expect 404, not 401."""
    r = entitlement_client.get(
        "/customer/bootstrap", params={"session_id": "cs_nope"},
    )
    assert r.status_code == 404
