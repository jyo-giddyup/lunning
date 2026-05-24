"""Tests for the agentic workflows subsystem."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

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


@pytest.fixture()
def client(art_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(art_dir))
    monkeypatch.setenv("NIL_ENABLE_AGENTS", "true")
    monkeypatch.setenv("NIL_AGENT_DB", str(tmp_path / "agents.db"))
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    # Re-import with agent flag on so the router is registered.
    import importlib
    import nil_predictor.api as api_mod
    importlib.reload(api_mod)
    return TestClient(api_mod.app)


# ── Store unit tests ────────────────────────────────────────────────

def test_store_watchlist_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_AGENT_DB", str(tmp_path / "agents.db"))
    from nil_predictor.agents import store
    importlib = __import__("importlib")
    importlib.reload(store)

    item = store.add_to_watchlist(ATHLETE, label="Test QB")
    assert item["label"] == "Test QB"
    assert item["sport"] == "football"

    items = store.list_watchlist()
    assert len(items) == 1

    fetched = store.get_watchlist_item(item["id"])
    assert fetched is not None
    assert fetched["id"] == item["id"]

    updated = store.update_watchlist_item(item["id"], {"label": "Updated"})
    assert updated["label"] == "Updated"

    assert store.remove_from_watchlist(item["id"]) is True
    assert store.list_watchlist() == []


def test_store_predictions_and_alerts(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_AGENT_DB", str(tmp_path / "agents.db"))
    from nil_predictor.agents import store
    importlib = __import__("importlib")
    importlib.reload(store)

    item = store.add_to_watchlist(ATHLETE, label="Pred Test")
    store.save_predictions(item["id"], {"valuation": 50000, "tier": "Gold"})
    store.save_predictions(item["id"], {"valuation": 60000, "tier": "Gold"})

    latest = store.get_latest_prediction(item["id"])
    assert latest["predictions"]["valuation"] == 60000

    history = store.get_prediction_history(item["id"])
    assert len(history) == 2

    alert = store.create_alert(
        item["id"], "tier_change", "critical",
        "tier changed", {"before": "Silver", "after": "Gold"})
    assert alert["kind"] == "tier_change"

    alerts = store.list_alerts()
    assert len(alerts) == 1
    assert store.dismiss_alert(alert["id"]) is True
    assert store.list_alerts(dismissed=False) == []
    assert len(store.list_alerts(dismissed=True)) == 1


def test_store_run_tracking(tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_AGENT_DB", str(tmp_path / "agents.db"))
    from nil_predictor.agents import store
    importlib = __import__("importlib")
    importlib.reload(store)

    rid = store.start_run()
    store.finish_run(rid, 5, 2)
    latest = store.latest_run()
    assert latest["status"] == "completed"
    assert latest["athletes_checked"] == 5


# ── Monitor unit tests ──────────────────────────────────────────────

def test_monitor_empty_watchlist(art_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_AGENT_DB", str(tmp_path / "agents.db"))
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    from nil_predictor.agents import store, monitor
    importlib = __import__("importlib")
    importlib.reload(store)
    importlib.reload(monitor)

    result = monitor.run_check(art_dir)
    assert result["athletes_checked"] == 0
    assert result["alerts_generated"] == 0


def test_monitor_detects_no_change_on_first_run(art_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_AGENT_DB", str(tmp_path / "agents.db"))
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    from nil_predictor.agents import store, monitor
    importlib = __import__("importlib")
    importlib.reload(store)
    importlib.reload(monitor)

    store.add_to_watchlist(ATHLETE, label="First Run")
    result = monitor.run_check(art_dir)
    assert result["athletes_checked"] == 1
    assert result["alerts_generated"] == 0


def test_monitor_stable_predictions_no_alerts(art_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("NIL_AGENT_DB", str(tmp_path / "agents.db"))
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    from nil_predictor.agents import store, monitor
    importlib = __import__("importlib")
    importlib.reload(store)
    importlib.reload(monitor)

    store.add_to_watchlist(ATHLETE, label="Stable")
    monitor.run_check(art_dir)
    result = monitor.run_check(art_dir)
    assert result["alerts_generated"] == 0


# ── API endpoint tests ──────────────────────────────────────────────

def test_health_shows_agents_enabled(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["agents_enabled"] is True


def test_watchlist_endpoints(client):
    r = client.post("/agents/watchlist", json={**ATHLETE, "label": "API Test"})
    assert r.status_code == 200
    wid = r.json()["id"]

    r = client.get("/agents/watchlist")
    assert r.status_code == 200
    assert r.json()["count"] == 1

    r = client.get(f"/agents/watchlist/{wid}")
    assert r.status_code == 200
    assert r.json()["athlete"]["label"] == "API Test"

    r = client.patch(f"/agents/watchlist/{wid}", json={"label": "Patched"})
    assert r.status_code == 200
    assert r.json()["label"] == "Patched"

    r = client.delete(f"/agents/watchlist/{wid}")
    assert r.status_code == 200

    r = client.get(f"/agents/watchlist/{wid}")
    assert r.status_code == 404


def test_alerts_empty(client):
    r = client.get("/agents/alerts")
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_agent_status(client):
    r = client.get("/agents/status")
    assert r.status_code == 200
    body = r.json()
    assert "scheduler" in body
    assert "interval_seconds" in body["scheduler"]


def test_force_run(client):
    client.post("/agents/watchlist", json={**ATHLETE, "label": "Run Test"})
    r = client.post("/agents/run")
    assert r.status_code == 200
    assert r.json()["athletes_checked"] == 1
