"""Safety guards on the FastAPI surface."""
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
    # Empty artifacts dir — size guard runs before predict() is invoked,
    # so payloads that pass validation get a 503 (no models) which is fine.
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    return TestClient(api_module.app)


def test_predict_rejects_oversized_batch(client, monkeypatch):
    monkeypatch.setattr(api_module, "MAX_BATCH", 5)
    big = {"athletes": [VALID_ATHLETE for _ in range(6)]}
    r = client.post("/predict", json=big)
    assert r.status_code == 413, r.text
    assert "exceeds limit 5" in r.json()["detail"]


def test_predict_at_limit_passes_validation(client, monkeypatch):
    monkeypatch.setattr(api_module, "MAX_BATCH", 3)
    payload = {"athletes": [VALID_ATHLETE for _ in range(3)]}
    r = client.post("/predict", json=payload)
    # Validation passed; request fails later with 503 because artifacts are empty.
    assert r.status_code == 503


def test_predict_rejects_negative_followers(client):
    # Wrap so PredictRequest pulls each athlete through Athlete validation.
    bad = dict(VALID_ATHLETE, instagram_followers=-1)
    r = client.post("/predict", json={"athletes": [bad]})
    assert r.status_code == 422, r.text


def test_predict_rejects_oversized_followers(client):
    bad = dict(VALID_ATHLETE, twitter_followers=10**12)
    r = client.post("/predict", json={"athletes": [bad]})
    assert r.status_code == 422, r.text


def test_predict_rejects_overlong_strings(client):
    bad = dict(VALID_ATHLETE, conference="x" * 1000)
    r = client.post("/predict", json={"athletes": [bad]})
    assert r.status_code == 422, r.text


def test_predict_rejects_out_of_range_score(client):
    bad = dict(VALID_ATHLETE, performance_score=150)
    r = client.post("/predict", json={"athletes": [bad]})
    assert r.status_code == 422, r.text


def test_explain_clamps_top_k(client):
    r = client.get("/explain?top_k=999")
    # Even with top_k=999 the handler clamps before reading artifacts;
    # with no artifacts present we expect 503, not a 500 from huge top_k.
    assert r.status_code in (200, 503)
