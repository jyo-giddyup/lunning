from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from nil_predictor.train import train_all


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    art = tmp_path_factory.mktemp("art")
    train_all(n=600, seed=3, out_dir=art)
    import os
    os.environ["NIL_ARTIFACTS_DIR"] = str(art)
    # Import after env is set so the resolver picks it up at request time.
    from nil_predictor.api import app
    return TestClient(app)


def test_health_reports_present_models(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert set(body["models_present"]) == {
        "valuation", "deal_count", "tier", "portal", "drafted",
    }


def test_schema_lists_required_fields(client):
    r = client.get("/schema")
    assert r.status_code == 200
    fields = r.json()["required_fields"]
    assert "sport" in fields and "instagram_followers" in fields


def test_predict_single(client):
    payload = {
        "sport": "football", "position": "QB", "conference": "SEC", "year": "JR",
        "starter": True, "performance_score": 88,
        "instagram_followers": 250000, "tiktok_followers": 180000, "twitter_followers": 90000,
    }
    r = client.post("/predict", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1
    p = body["predictions"][0]
    assert p["valuation"] >= 0
    assert {"valuation", "deal_count", "tier", "portal", "drafted"} <= set(p.keys())


def test_predict_batch_via_athletes_key(client):
    payload = {"athletes": [
        {"sport": "track", "position": "distance", "conference": "MWC", "year": "FR",
         "starter": False, "performance_score": 40,
         "instagram_followers": 600, "tiktok_followers": 200, "twitter_followers": 50},
        {"sport": "mens_basketball", "position": "PG", "conference": "Big_East", "year": "SR",
         "starter": True, "performance_score": 82,
         "instagram_followers": 75000, "tiktok_followers": 30000, "twitter_followers": 10000},
    ]}
    r = client.post("/predict", json=payload)
    assert r.status_code == 200
    assert r.json()["count"] == 2


def test_explain_returns_top_features(client):
    r = client.get("/explain?top_k=3")
    assert r.status_code == 200
    body = r.json()
    # At least one target must produce feature importances.
    available = [t for t, v in body.items() if v.get("available")]
    assert len(available) >= 3
    sample = body[available[0]]
    assert len(sample["top_features"]) <= 3
    assert sample["top_features"][0]["importance"] >= 0


def test_predict_validates_payload(client):
    # Object missing required Athlete fields gets coerced into the
    # PredictRequest branch with athletes=None, which we reject as 400.
    r = client.post("/predict", json={"sport": "football"})
    assert r.status_code in (400, 422), r.text

    # Array shape with a clearly invalid record returns 422 (pydantic).
    r = client.post("/predict", json=[{"sport": "football"}])
    assert r.status_code == 422
