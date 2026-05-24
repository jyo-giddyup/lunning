"""SQLite-backed customer store.

Persists across Fly deploys via the `data` volume mounted at /app/data.
Tracks paying customers issued during Stripe checkout, their per-customer
API keys, and current subscription status. The api_key_gate middleware
consults this store when NIL_REQUIRE_PAYMENT is enabled.

The schema is created on every connect (CREATE TABLE IF NOT EXISTS) so
there is no separate migration step. Connections are per-call; SQLite
serializes via file lock, which is fine for the low write volume of
Stripe webhooks.

Env vars:
    NIL_CUSTOMER_DB  Path to the SQLite file.
                     Default: /app/data/customers.db
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    api_key                TEXT PRIMARY KEY,
    stripe_customer_id     TEXT,
    stripe_subscription_id TEXT,
    stripe_session_id      TEXT UNIQUE,
    email                  TEXT,
    status                 TEXT NOT NULL DEFAULT 'active',
    bootstrap_claimed_at   INTEGER,
    created_at             INTEGER NOT NULL,
    updated_at             INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subscription ON customers(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_email        ON customers(email);
"""

API_KEY_PREFIX = "nk_"

# Statuses Stripe assigns that still grant access. "trialing" covers
# free-trial subscriptions; "past_due" intentionally does NOT — once Stripe
# flips a subscription past_due the customer's card has already failed and
# we should withhold the product until they update it.
ACTIVE_STATUSES = frozenset({"active", "trialing"})


def db_path() -> Path:
    return Path(os.environ.get("NIL_CUSTOMER_DB", "/app/data/customers.db"))


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None puts us in autocommit; each statement is its own
    # transaction. Fine for our single-statement operations and avoids the
    # implicit-BEGIN behaviour of the default mode.
    c = sqlite3.connect(path, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        c.executescript(SCHEMA)
        yield c
    finally:
        c.close()


def _new_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_hex(32)}"


def _row_to_dict(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    return dict(row) if row else None


def create_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Insert a customer record from a Stripe checkout.session.completed.

    Idempotent on `stripe_session_id` — replaying the same webhook
    returns the existing record without minting a new API key. Stripe
    retries failed webhooks for up to 3 days, so the predictor must
    survive replays without giving the customer a different key on
    each retry.
    """
    session_id = session.get("id")
    if not session_id:
        raise ValueError("session.id is required")
    now = int(time.time())
    with _conn() as c:
        existing = c.execute(
            "SELECT * FROM customers WHERE stripe_session_id = ?",
            (session_id,),
        ).fetchone()
        if existing:
            return dict(existing)
        c.execute(
            """
            INSERT INTO customers
              (api_key, stripe_customer_id, stripe_subscription_id,
               stripe_session_id, email, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                _new_api_key(),
                session.get("customer"),
                session.get("subscription"),
                session_id,
                session.get("customer_email"),
                now,
                now,
            ),
        )
        row = c.execute(
            "SELECT * FROM customers WHERE stripe_session_id = ?",
            (session_id,),
        ).fetchone()
        return dict(row)


def find_by_api_key(api_key: str) -> Optional[dict[str, Any]]:
    if not api_key:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM customers WHERE api_key = ?", (api_key,)
        ).fetchone()
        return _row_to_dict(row)


def claim_bootstrap(session_id: str) -> Optional[dict[str, Any]]:
    """Return the customer record and mark it as claimed. One-shot.

    Subsequent calls with the same session_id return None — the API key
    is revealed only once at the post-checkout redirect. After that,
    the customer must recover it from their saved copy (or, once we
    ship welcome-email delivery, from the email).
    """
    now = int(time.time())
    with _conn() as c:
        row = c.execute(
            """
            UPDATE customers
               SET bootstrap_claimed_at = ?, updated_at = ?
             WHERE stripe_session_id = ?
               AND bootstrap_claimed_at IS NULL
         RETURNING *
            """,
            (now, now, session_id),
        ).fetchone()
        return _row_to_dict(row)


def update_status_by_subscription(subscription_id: str, status: str) -> bool:
    """Propagate a Stripe subscription status change onto the customer row.

    Returns True if a row was updated, False if no customer was found
    for that subscription id. The caller can choose whether to treat
    the latter as an audit-only event or an error.
    """
    if not subscription_id:
        return False
    now = int(time.time())
    with _conn() as c:
        cur = c.execute(
            """
            UPDATE customers
               SET status = ?, updated_at = ?
             WHERE stripe_subscription_id = ?
            """,
            (status, now, subscription_id),
        )
        return cur.rowcount > 0


def is_active(customer: dict[str, Any]) -> bool:
    return customer.get("status") in ACTIVE_STATUSES
