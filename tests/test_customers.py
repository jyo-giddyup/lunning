"""Unit tests for the SQLite customer store.

Each test isolates its DB via NIL_CUSTOMER_DB pointed at tmp_path so
the store starts empty and tests can't bleed into each other.
"""
from __future__ import annotations

import pytest

from nil_predictor import customers


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch, tmp_path):
    monkeypatch.setenv("NIL_CUSTOMER_DB", str(tmp_path / "customers.db"))


def test_create_returns_record_with_api_key():
    rec = customers.create_from_session({
        "id": "cs_1",
        "customer": "cus_1",
        "subscription": "sub_1",
        "customer_email": "a@b.co",
    })
    assert rec["stripe_session_id"] == "cs_1"
    assert rec["api_key"].startswith("nk_")
    assert len(rec["api_key"]) > len("nk_")
    assert rec["status"] == "active"
    assert customers.is_active(rec)


def test_create_is_idempotent_on_session_id():
    """Stripe retries the same webhook for up to 3 days; a replay must
    return the same record (same api_key) instead of minting a new one."""
    rec1 = customers.create_from_session({"id": "cs_2"})
    rec2 = customers.create_from_session({"id": "cs_2"})
    assert rec1["api_key"] == rec2["api_key"]
    assert rec1["stripe_session_id"] == rec2["stripe_session_id"]


def test_create_without_session_id_raises():
    with pytest.raises(ValueError):
        customers.create_from_session({})


def test_find_by_api_key_round_trip():
    rec = customers.create_from_session({"id": "cs_3"})
    found = customers.find_by_api_key(rec["api_key"])
    assert found is not None
    assert found["stripe_session_id"] == "cs_3"


def test_find_by_api_key_unknown_returns_none():
    assert customers.find_by_api_key("nk_does_not_exist") is None
    assert customers.find_by_api_key("") is None


def test_claim_bootstrap_is_one_shot():
    customers.create_from_session({"id": "cs_4"})
    first = customers.claim_bootstrap("cs_4")
    assert first is not None
    assert first["bootstrap_claimed_at"] is not None
    # Second call must return None — the API key was already revealed.
    second = customers.claim_bootstrap("cs_4")
    assert second is None


def test_claim_bootstrap_unknown_session_returns_none():
    assert customers.claim_bootstrap("cs_never_existed") is None


def test_update_status_canceled_flips_is_active():
    rec = customers.create_from_session({"id": "cs_5", "subscription": "sub_5"})
    assert customers.is_active(rec)

    assert customers.update_status_by_subscription("sub_5", "canceled") is True

    found = customers.find_by_api_key(rec["api_key"])
    assert found is not None
    assert found["status"] == "canceled"
    assert not customers.is_active(found)


def test_update_status_unknown_subscription_returns_false():
    assert customers.update_status_by_subscription("sub_nope", "canceled") is False
    assert customers.update_status_by_subscription("", "canceled") is False


def test_is_active_includes_trialing_but_not_past_due():
    assert customers.is_active({"status": "active"})
    assert customers.is_active({"status": "trialing"})
    # past_due means Stripe has flagged the card as failed; withhold
    # access until they update payment method.
    assert not customers.is_active({"status": "past_due"})
    assert not customers.is_active({"status": "canceled"})
    assert not customers.is_active({"status": "unpaid"})
