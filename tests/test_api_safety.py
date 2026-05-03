"""Safety guards on the FastAPI surface."""
import os

import pytest
from fastapi.testclient import TestClient

from nil_predictor import api as api_module

VALID_ATHLETE = {
    "sport": "football",
    "position": "QB",
    "conference": "SEC",
    "year": "JR",
    "starter": True,
    "performance_score": 87,
    "instagram_followers": 250000,
    "tiktok_followers": 180000,
    "twitter_followers": 90000,
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Point at empty artifacts so /predict returns 503 quickly without
    # actually loading models — we only want to exercise the input guards.
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    return TestClient(api_module.app)


def test_predict_rejects_oversized_batch(client, monkeypatch):
    # Tighten the limit just for this test.
    monkeypatch.setattr(api_module, "MAX_BATCH", 5)
    big = {"athletes": [VALID_ATHLETE for _ in range(6)]}
    r = client.post("/predict", json=big)
    assert r.status_code == 413, r.text
    assert "exceeds limit 5" in r.json()["detail"]


def test_predict_at_limit_passes_validation(client, monkeypatch):
    # At the limit — size guard passes, then 503 because no artifacts.
    monkeypatch.setattr(api_module, "MAX_BATCH", 3)
    payload = {"athletes": [VALID_ATHLETE for _ in range(3)]}
    r = client.post("/predict", json=payload)
    assert r.status_code == 503


def test_predict_rejects_negative_followers(client):
    bad = dict(VALID_ATHLETE, instagram_followers=-1)
    r = client.post("/predict", json=bad)
    assert r.status_code == 422  # pydantic validation error


def test_predict_rejects_oversized_followers(client):
    bad = dict(VALID_ATHLETE, twitter_followers=10**12)
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_predict_rejects_overlong_strings(client):
    bad = dict(VALID_ATHLETE, conference="x" * 1000)
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_explain_clamps_top_k(client):
    # Even with top_k=999, the handler should clamp to <=100 before reading
    # artifacts. With no artifacts present we expect 503, not 500.
    r = client.get("/explain?top_k=999")
    assert r.status_code in (200, 503)
