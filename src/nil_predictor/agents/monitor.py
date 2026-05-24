"""Watchlist monitor — re-predicts and detects meaningful changes."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .. import audit
from ..predict import predict
from . import store

logger = logging.getLogger(__name__)

VALUATION_CHANGE_PCT = float(os.environ.get("NIL_VALUATION_ALERT_PCT", "15"))
PROBA_CHANGE_THRESHOLD = float(os.environ.get("NIL_PROBA_ALERT_THRESHOLD", "0.15"))


def _detect_changes(watchlist_id: str, label: str,
                    old: dict[str, Any],
                    new: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    if old.get("tier") != new.get("tier"):
        alerts.append(store.create_alert(
            watchlist_id, "tier_change", "critical",
            f"{label}: tier changed {old.get('tier')} → {new.get('tier')}",
            {"before": old.get("tier"), "after": new.get("tier")},
        ))

    old_val = old.get("valuation", 0)
    new_val = new.get("valuation", 0)
    if old_val > 0:
        pct = abs(new_val - old_val) / old_val * 100
        if pct >= VALUATION_CHANGE_PCT:
            direction = "up" if new_val > old_val else "down"
            alerts.append(store.create_alert(
                watchlist_id, "valuation_shift",
                "warning" if pct < 30 else "critical",
                f"{label}: valuation {direction} {pct:.1f}% "
                f"(${old_val:,.0f} → ${new_val:,.0f})",
                {"before": old_val, "after": new_val,
                 "change_pct": round(pct, 1)},
            ))

    old_portal = (old.get("portal_proba") or {}).get("True", 0)
    new_portal = (new.get("portal_proba") or {}).get("True", 0)
    delta = abs(new_portal - old_portal)
    if delta >= PROBA_CHANGE_THRESHOLD:
        direction = "up" if new_portal > old_portal else "down"
        alerts.append(store.create_alert(
            watchlist_id, "portal_spike",
            "warning" if delta < 0.3 else "critical",
            f"{label}: portal probability {direction} "
            f"({old_portal:.2f} → {new_portal:.2f})",
            {"before": round(old_portal, 4), "after": round(new_portal, 4)},
        ))

    if old.get("drafted") != new.get("drafted"):
        alerts.append(store.create_alert(
            watchlist_id, "draft_change", "critical",
            f"{label}: draft prediction changed "
            f"{old.get('drafted')} → {new.get('drafted')}",
            {"before": old.get("drafted"), "after": new.get("drafted")},
        ))

    return alerts


def run_check(artifacts_dir: Path) -> dict[str, Any]:
    """Single monitoring pass over the full watchlist."""
    run_id = store.start_run()
    items = store.list_watchlist()

    if not items:
        store.finish_run(run_id, 0, 0)
        return {"run_id": run_id, "athletes_checked": 0,
                "alerts_generated": 0}

    records = store.watchlist_to_records(items)
    total_alerts = 0

    try:
        predictions = predict(records, artifacts_dir)
    except Exception as e:
        logger.error("Monitor prediction failed: %s", e)
        store.finish_run(run_id, 0, 0, error=str(e))
        audit.emit("agent.monitor.error",
                    payload={"error_kind": "prediction_failed"})
        return {"run_id": run_id, "error": str(e)}

    for item, pred in zip(items, predictions):
        wid = item["id"]
        label = item.get("label") or f"{item['position']}/{item['conference']}"
        previous = store.get_latest_prediction(wid)
        store.save_predictions(wid, pred)
        if previous:
            new_alerts = _detect_changes(
                wid, label, previous["predictions"], pred)
            total_alerts += len(new_alerts)

    store.finish_run(run_id, len(items), total_alerts)
    audit.emit("agent.monitor.completed", payload={
        "n_records": len(items),
        "alerts_generated": total_alerts,
    })
    return {"run_id": run_id, "athletes_checked": len(items),
            "alerts_generated": total_alerts}
