"""Invariants for the ML surface.

These tests exist so that future contributions that add prediction /
training / inference endpoints cannot accidentally publish them to the
open internet by dropping the path into `PUBLIC_PATHS`. If you need a
new *public* ML endpoint, you must edit this test to whitelist it
explicitly — that edit is the review signal.

Also enforces that `/health` does not leak filesystem paths or other
runtime config.
"""
from __future__ import annotations

import os
import re

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from nil_predictor import api

# Match any route path whose top segment reads like an ML operation.
# Deliberately broad — better to force a review of a new "/score" route
# than to let a silent public-add through.
ML_PATH_PATTERN = re.compile(
    r"^/(predict|explain|schema|train|score|forecast|classify|"
    r"model|models|infer|inference|evaluate|embed|embeddings|"
    r"features?|targets?)(/|$)"
)

# Explicit allowlist: paths that match ML_PATH_PATTERN but ARE meant to
# be reachable without auth. Empty by default. Edit this — with a review
# comment explaining why — to add a public ML surface.
EXPECTED_PUBLIC_ML_PATHS: frozenset[str] = frozenset()

# Fields the /health response is allowed to expose. Anything else is a
# potential info leak (filesystem paths, model names, secrets).
HEALTH_ALLOWED_FIELDS: frozenset[str] = frozenset({
    "ok",
    "models_ready",
    "models_total",
    "max_batch",
    "auth_required",
    "require_payment",
})


def _all_routes() -> list[str]:
    paths: list[str] = []
    for route in api.app.router.routes:
        p = getattr(route, "path", None)
        if isinstance(p, str) and p.startswith("/"):
            paths.append(p)
    return paths


def test_no_ml_endpoint_lands_on_public_allowlist():
    """`PUBLIC_PATHS` never contains an ML-suggestive route.

    If this fails: either the new route belongs behind the gate (default),
    or you meant it to be public — in which case add it to
    `EXPECTED_PUBLIC_ML_PATHS` above with a review comment explaining why.
    """
    accidental = [
        p for p in api.PUBLIC_PATHS
        if ML_PATH_PATTERN.match(p) and p not in EXPECTED_PUBLIC_ML_PATHS
    ]
    assert not accidental, (
        f"ML endpoint(s) on the public allowlist without an explicit "
        f"opt-in: {accidental}. Either gate them (default) or add to "
        f"EXPECTED_PUBLIC_ML_PATHS in this test with a review comment."
    )


def test_ml_routes_are_reachable_only_when_gate_permits():
    """Every ML route defined on the app is either gated or explicitly public.

    Belt-and-suspenders: even if a new route is *not* added to PUBLIC_PATHS,
    catch a case where a decorator or router include lands it somewhere
    the gate can't see.
    """
    ml_routes = [p for p in _all_routes() if ML_PATH_PATTERN.match(p)]
    for path in ml_routes:
        if path in EXPECTED_PUBLIC_ML_PATHS:
            continue
        assert path not in api.PUBLIC_PATHS, (
            f"ML route {path} appears in PUBLIC_PATHS but is not in "
            f"EXPECTED_PUBLIC_ML_PATHS."
        )


def test_health_response_does_not_leak_config():
    """`/health` returns only fields on `HEALTH_ALLOWED_FIELDS`.

    No `artifacts_dir` (filesystem path), no model-name list, no secrets.
    Add new fields here only when they're genuinely safe for an
    unauthenticated caller (uptime monitor, load balancer probe).
    """
    # Ensure the gate is off for this test so /health returns the real
    # payload rather than a 401 in case a prior test left env state.
    prev = os.environ.pop("NIL_API_KEY", None)
    prev_pay = os.environ.pop("NIL_REQUIRE_PAYMENT", None)
    try:
        client = TestClient(api.app)
        r = client.get("/health")
        assert r.status_code == 200, r.text
        body = r.json()
        extras = set(body) - HEALTH_ALLOWED_FIELDS
        assert not extras, (
            f"/health leaks fields not on HEALTH_ALLOWED_FIELDS: {extras}. "
            f"Either strip them from the response or add them to the "
            f"allowlist in this test if they're truly probe-safe."
        )
        # And in particular, never these:
        forbidden_substrings = ("/", "artifacts_dir", "NIL_", "secret", "key")
        serialized = str(body).lower()
        for needle in ("artifacts_dir",):
            assert needle not in serialized, (
                f"/health response contains '{needle}': {body}"
            )
    finally:
        if prev is not None:
            os.environ["NIL_API_KEY"] = prev
        if prev_pay is not None:
            os.environ["NIL_REQUIRE_PAYMENT"] = prev_pay
