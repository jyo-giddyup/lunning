"""Append-only audit log — ISO/IEC 42001:2023 + 27001:2022.

Writes JSONL events to NIL_AUDIT_LOG (default: artifacts/audit.log)
on training milestones and prediction requests. Logs payload digests
rather than payloads — no PII / raw inputs touch the log even when
real data eventually replaces the synthetic generator.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def audit_path() -> Path:
    raw = os.environ.get("NIL_AUDIT_LOG")
    if raw:
        return Path(raw)
    art = Path(os.environ.get("NIL_ARTIFACTS_DIR", "artifacts"))
    return art / "audit.log"


def emit(event: str, payload: dict[str, Any] | None = None,
         request_id: str | None = None) -> dict[str, Any]:
    record = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        "request_id": request_id or uuid.uuid4().hex[:12],
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "digest": _digest(payload or {}),
        "payload_meta": _strip_payload(payload or {}),
    }
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # O_APPEND guarantees atomic appends across processes on POSIX.
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


# Field whitelist: only non-sensitive metadata is stored verbatim.
# Stripe fields (event_type, event_id, session_id, price_id, quantity,
# client_reference_id, amount_total, subscription_id, status) are
# operational identifiers, not PII.
SAFE_FIELDS = {
    "n_records", "model_version", "n_athletes", "seed",
    "out_dir", "duration_ms", "exit_code", "error_kind",
    "artifacts_dir", "model_count", "violation_count",
    "event_type", "event_id", "session_id", "price_id",
    "quantity", "client_reference_id", "amount_total",
    "error_detail", "subscription_id", "status",
}


def _strip_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k in SAFE_FIELDS}


def tail(n: int = 10) -> list[dict[str, Any]]:
    path = audit_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-n:]
    return [json.loads(line) for line in lines if line.strip()]
