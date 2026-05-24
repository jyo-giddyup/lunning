"""SQLite store for agent state: watchlist, prediction history, alerts."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    id                  TEXT PRIMARY KEY,
    label               TEXT,
    sport               TEXT NOT NULL,
    position            TEXT NOT NULL,
    conference          TEXT NOT NULL,
    year                TEXT NOT NULL,
    starter             INTEGER NOT NULL,
    performance_score   REAL NOT NULL,
    instagram_followers INTEGER NOT NULL,
    tiktok_followers    INTEGER NOT NULL,
    twitter_followers   INTEGER NOT NULL,
    created_at          INTEGER NOT NULL,
    updated_at          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS prediction_history (
    id           TEXT PRIMARY KEY,
    watchlist_id TEXT NOT NULL REFERENCES watchlist(id) ON DELETE CASCADE,
    predictions  TEXT NOT NULL,
    run_at       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ph_wid   ON prediction_history(watchlist_id);
CREATE INDEX IF NOT EXISTS idx_ph_runat ON prediction_history(run_at);

CREATE TABLE IF NOT EXISTS alerts (
    id           TEXT PRIMARY KEY,
    watchlist_id TEXT NOT NULL REFERENCES watchlist(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,
    severity     TEXT NOT NULL,
    summary      TEXT NOT NULL,
    detail       TEXT,
    dismissed    INTEGER NOT NULL DEFAULT 0,
    created_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_al_wid  ON alerts(watchlist_id);
CREATE INDEX IF NOT EXISTS idx_al_dism ON alerts(dismissed);

CREATE TABLE IF NOT EXISTS agent_runs (
    id               TEXT PRIMARY KEY,
    started_at       INTEGER NOT NULL,
    finished_at      INTEGER,
    status           TEXT NOT NULL DEFAULT 'running',
    athletes_checked INTEGER DEFAULT 0,
    alerts_generated INTEGER DEFAULT 0,
    error            TEXT
);
"""


def db_path() -> Path:
    return Path(os.environ.get("NIL_AGENT_DB", "/app/data/agents.db"))


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        c.executescript(SCHEMA)
        yield c
    finally:
        c.close()


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ── Watchlist ───────────────────────────────────────────────────────

def add_to_watchlist(athlete: dict[str, Any],
                     label: str | None = None) -> dict[str, Any]:
    wid = _uid()
    now = int(time.time())
    with _conn() as c:
        c.execute(
            """INSERT INTO watchlist
                 (id, label, sport, position, conference, year, starter,
                  performance_score, instagram_followers, tiktok_followers,
                  twitter_followers, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (wid, label, athlete["sport"], athlete["position"],
             athlete["conference"], athlete["year"], int(athlete["starter"]),
             athlete["performance_score"], athlete["instagram_followers"],
             athlete["tiktok_followers"], athlete["twitter_followers"],
             now, now),
        )
        return dict(c.execute("SELECT * FROM watchlist WHERE id = ?", (wid,)).fetchone())


def list_watchlist() -> list[dict[str, Any]]:
    with _conn() as c:
        return [dict(r) for r in
                c.execute("SELECT * FROM watchlist ORDER BY created_at DESC").fetchall()]


def get_watchlist_item(wid: str) -> Optional[dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM watchlist WHERE id = ?", (wid,)).fetchone()
        return dict(row) if row else None


def update_watchlist_item(wid: str,
                          updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    allowed = {"label", "sport", "position", "conference", "year", "starter",
               "performance_score", "instagram_followers", "tiktok_followers",
               "twitter_followers"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return get_watchlist_item(wid)
    filtered["updated_at"] = int(time.time())
    sets = ", ".join(f"{k} = ?" for k in filtered)
    vals = list(filtered.values()) + [wid]
    with _conn() as c:
        c.execute(f"UPDATE watchlist SET {sets} WHERE id = ?", vals)
        row = c.execute("SELECT * FROM watchlist WHERE id = ?", (wid,)).fetchone()
        return dict(row) if row else None


def remove_from_watchlist(wid: str) -> bool:
    with _conn() as c:
        return c.execute("DELETE FROM watchlist WHERE id = ?", (wid,)).rowcount > 0


def watchlist_to_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sport": it["sport"],
            "position": it["position"],
            "conference": it["conference"],
            "year": it["year"],
            "starter": bool(it["starter"]),
            "performance_score": it["performance_score"],
            "instagram_followers": it["instagram_followers"],
            "tiktok_followers": it["tiktok_followers"],
            "twitter_followers": it["twitter_followers"],
        }
        for it in items
    ]


# ── Prediction history ──────────────────────────────────────────────

def save_predictions(watchlist_id: str, predictions: dict[str, Any]) -> str:
    pid = _uid()
    now = int(time.time())
    with _conn() as c:
        c.execute(
            "INSERT INTO prediction_history (id, watchlist_id, predictions, run_at) "
            "VALUES (?,?,?,?)",
            (pid, watchlist_id, json.dumps(predictions), now),
        )
    return pid


def get_latest_prediction(watchlist_id: str) -> Optional[dict[str, Any]]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM prediction_history "
            "WHERE watchlist_id = ? ORDER BY rowid DESC LIMIT 1",
            (watchlist_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["predictions"] = json.loads(d["predictions"])
        return d


def get_prediction_history(watchlist_id: str,
                           limit: int = 20) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM prediction_history "
            "WHERE watchlist_id = ? ORDER BY rowid DESC LIMIT ?",
            (watchlist_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["predictions"] = json.loads(d["predictions"])
            out.append(d)
        return out


# ── Alerts ──────────────────────────────────────────────────────────

def create_alert(watchlist_id: str, kind: str, severity: str,
                 summary: str,
                 detail: dict[str, Any] | None = None) -> dict[str, Any]:
    aid = _uid()
    now = int(time.time())
    with _conn() as c:
        c.execute(
            "INSERT INTO alerts "
            "(id, watchlist_id, kind, severity, summary, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (aid, watchlist_id, kind, severity, summary,
             json.dumps(detail) if detail else None, now),
        )
        d = dict(c.execute("SELECT * FROM alerts WHERE id = ?", (aid,)).fetchone())
        if d.get("detail"):
            d["detail"] = json.loads(d["detail"])
        return d


def list_alerts(dismissed: bool = False,
                limit: int = 50) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM alerts WHERE dismissed = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (int(dismissed), limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("detail"):
                d["detail"] = json.loads(d["detail"])
            out.append(d)
        return out


def dismiss_alert(aid: str) -> bool:
    with _conn() as c:
        return c.execute(
            "UPDATE alerts SET dismissed = 1 WHERE id = ?", (aid,),
        ).rowcount > 0


# ── Agent runs ──────────────────────────────────────────────────────

def start_run() -> str:
    rid = _uid()
    with _conn() as c:
        c.execute(
            "INSERT INTO agent_runs (id, started_at, status) VALUES (?,?,'running')",
            (rid, int(time.time())),
        )
    return rid


def finish_run(rid: str, athletes_checked: int, alerts_generated: int,
               error: str | None = None) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE agent_runs "
            "SET finished_at=?, status=?, athletes_checked=?, "
            "    alerts_generated=?, error=? "
            "WHERE id=?",
            (int(time.time()), "failed" if error else "completed",
             athletes_checked, alerts_generated, error, rid),
        )


def latest_run() -> Optional[dict[str, Any]]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT 1",
        ).fetchone()
        return dict(row) if row else None
