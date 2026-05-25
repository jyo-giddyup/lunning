"""Tier definitions, usage tracking, and feature-gate logic.

Three tiers: free, pro, enterprise. Each has a daily request limit,
max batch size, and a set of endpoint path prefixes it can access.

Env vars for Stripe price mapping:
    STRIPE_PRICE_ID_FREE        price_... for the free tier ($0)
    STRIPE_PRICE_ID_PRO         price_... for the pro tier
    STRIPE_PRICE_ID_ENTERPRISE  price_... for the enterprise tier

The legacy STRIPE_PRICE_ID is still read as a fallback for pro.
"""
from __future__ import annotations

import enum
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any


class TierName(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


@dataclass(frozen=True)
class TierSpec:
    name: TierName
    daily_limit: int | None
    max_batch: int
    features: frozenset[str]


FREE_FEATURES = frozenset({"/predict", "/me"})
PRO_FEATURES = frozenset({"/predict", "/explain", "/schema", "/agents", "/me"})
ENTERPRISE_FEATURES = frozenset({
    "/predict", "/explain", "/schema", "/agents", "/revenue", "/me",
})

TIERS: dict[TierName, TierSpec] = {
    TierName.free: TierSpec(
        name=TierName.free, daily_limit=50, max_batch=1,
        features=FREE_FEATURES,
    ),
    TierName.pro: TierSpec(
        name=TierName.pro, daily_limit=1000, max_batch=100,
        features=PRO_FEATURES,
    ),
    TierName.enterprise: TierSpec(
        name=TierName.enterprise, daily_limit=None, max_batch=100,
        features=ENTERPRISE_FEATURES,
    ),
}

DEFAULT_TIER = TierName.pro


def price_to_tier(price_id: str) -> TierName:
    """Resolve a Stripe price_id to a tier. Defaults to pro if unknown."""
    mapping: dict[str, TierName] = {}
    for tier_name in TierName:
        env_key = f"STRIPE_PRICE_ID_{tier_name.value.upper()}"
        pid = os.environ.get(env_key, "").strip()
        if pid:
            mapping[pid] = tier_name
    legacy = os.environ.get("STRIPE_PRICE_ID", "").strip()
    if legacy and legacy not in mapping:
        mapping[legacy] = TierName.pro
    return mapping.get(price_id, DEFAULT_TIER)


# ── Usage tracking ──────────────────────────────────────────────────

USAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    api_key       TEXT NOT NULL,
    date          TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (api_key, date)
);
"""


def _ensure_usage_table(c: sqlite3.Connection) -> None:
    c.executescript(USAGE_SCHEMA)


def increment_usage(api_key: str, conn_factory) -> int:
    """Increment today's counter, return the new count."""
    today = time.strftime("%Y-%m-%d", time.gmtime())
    with conn_factory() as c:
        _ensure_usage_table(c)
        c.execute(
            "INSERT INTO usage (api_key, date, request_count) VALUES (?, ?, 1) "
            "ON CONFLICT(api_key, date) "
            "DO UPDATE SET request_count = request_count + 1",
            (api_key, today),
        )
        row = c.execute(
            "SELECT request_count FROM usage WHERE api_key = ? AND date = ?",
            (api_key, today),
        ).fetchone()
        return row[0] if row else 1


def get_usage(api_key: str, conn_factory) -> dict[str, Any]:
    """Return today's usage count."""
    today = time.strftime("%Y-%m-%d", time.gmtime())
    with conn_factory() as c:
        _ensure_usage_table(c)
        row = c.execute(
            "SELECT request_count FROM usage WHERE api_key = ? AND date = ?",
            (api_key, today),
        ).fetchone()
        return {"date": today, "request_count": row[0] if row else 0}


# ── Feature gating ──────────────────────────────────────────────────

def path_allowed(path: str, tier: TierName) -> bool:
    """Check whether a request path is accessible by the given tier."""
    spec = TIERS[tier]
    return any(path.startswith(prefix) for prefix in spec.features)
