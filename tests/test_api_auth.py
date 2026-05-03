"""API key gate behaviour."""
import pytest
from fastapi.testclient import TestClient

from nil_predictor import api as api_module


@pytest.fixture
def gated_client(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "NIL_API_KEY", "shh-its-a-secret")
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
    return TestClient(api_module.app)


@pytest.fixture
def open_client(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "NIL_API_KEY", "")
    monkeypatch.setenv("NIL_ARTIFACTS_DIR", str(tmp_path))
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
    assert r.json()  # not 401
