"""FastAPI router for agent management endpoints.

All routes live under /agents and are gated by the same api_key_gate
middleware as the rest of the service.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import scheduler, store
from .monitor import run_check

router = APIRouter(prefix="/agents", tags=["agents"])


def _artifacts_dir() -> Path:
    return Path(os.environ.get("NIL_ARTIFACTS_DIR", "artifacts")).resolve()


class WatchlistAdd(BaseModel):
    label: str | None = None
    sport: str = Field(max_length=64)
    position: str = Field(max_length=64)
    conference: str = Field(max_length=64)
    year: str = Field(max_length=8)
    starter: bool
    performance_score: float = Field(ge=0, le=100)
    instagram_followers: int = Field(ge=0, le=10**9)
    tiktok_followers: int = Field(ge=0, le=10**9)
    twitter_followers: int = Field(ge=0, le=10**9)


class WatchlistUpdate(BaseModel):
    label: str | None = None
    sport: str | None = Field(default=None, max_length=64)
    position: str | None = Field(default=None, max_length=64)
    conference: str | None = Field(default=None, max_length=64)
    year: str | None = Field(default=None, max_length=8)
    starter: bool | None = None
    performance_score: float | None = Field(default=None, ge=0, le=100)
    instagram_followers: int | None = Field(default=None, ge=0, le=10**9)
    tiktok_followers: int | None = Field(default=None, ge=0, le=10**9)
    twitter_followers: int | None = Field(default=None, ge=0, le=10**9)


@router.post("/watchlist")
def add_watchlist(payload: WatchlistAdd) -> dict[str, Any]:
    return store.add_to_watchlist(payload.model_dump(), label=payload.label)


@router.get("/watchlist")
def list_watchlist() -> dict[str, Any]:
    items = store.list_watchlist()
    return {"items": items, "count": len(items)}


@router.get("/watchlist/{wid}")
def get_watchlist_item(wid: str) -> dict[str, Any]:
    item = store.get_watchlist_item(wid)
    if not item:
        raise HTTPException(404, "not found")
    history = store.get_prediction_history(wid, limit=5)
    return {"athlete": item, "recent_predictions": history}


@router.patch("/watchlist/{wid}")
def update_watchlist_item(wid: str, payload: WatchlistUpdate) -> dict[str, Any]:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    result = store.update_watchlist_item(wid, updates)
    if not result:
        raise HTTPException(404, "not found")
    return result


@router.delete("/watchlist/{wid}")
def delete_watchlist_item(wid: str) -> dict[str, Any]:
    if not store.remove_from_watchlist(wid):
        raise HTTPException(404, "not found")
    return {"deleted": True}


@router.get("/alerts")
def list_alerts(dismissed: bool = False, limit: int = 50) -> dict[str, Any]:
    items = store.list_alerts(dismissed=dismissed, limit=min(limit, 200))
    return {"alerts": items, "count": len(items)}


@router.post("/alerts/{aid}/dismiss")
def dismiss_alert(aid: str) -> dict[str, Any]:
    if not store.dismiss_alert(aid):
        raise HTTPException(404, "not found")
    return {"dismissed": True}


@router.get("/status")
def agent_status() -> dict[str, Any]:
    sched = scheduler.status()
    latest = store.latest_run()
    return {"scheduler": sched, "latest_run": latest}


@router.post("/run")
def force_run() -> dict[str, Any]:
    return run_check(_artifacts_dir())
