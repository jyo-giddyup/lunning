"""Audit chain integrity — ISO/IEC 27001:2022 traceability."""
from __future__ import annotations

import builtins
import hashlib
import json
from pathlib import Path

import pytest

from nil_predictor import audit


def _emit_three(monkeypatch, tmp_path: Path) -> Path:
    log = tmp_path / "audit.log"
    monkeypatch.setenv("NIL_AUDIT_LOG", str(log))
    audit.emit("train.start", {"n_athletes": 100, "seed": 1})
    audit.emit("train.complete", {"n_athletes": 100, "seed": 1, "model_count": 5})
    audit.emit("predict.request", {"n_records": 1})
    return log


def test_chain_verifies_on_intact_log(monkeypatch, tmp_path: Path):
    log = _emit_three(monkeypatch, tmp_path)
    assert audit.verify(log) is True


def test_first_record_links_to_genesis(monkeypatch, tmp_path: Path):
    log = _emit_three(monkeypatch, tmp_path)
    first = json.loads(log.read_text().splitlines()[0])
    assert first["prev_hash"] == "0" * 64


def test_each_record_links_to_previous(monkeypatch, tmp_path: Path):
    log = _emit_three(monkeypatch, tmp_path)
    raws = [r for r in log.read_bytes().split(b"\n") if r.strip()]
    for prev_raw, cur_raw in zip(raws, raws[1:]):
        cur = json.loads(cur_raw)
        assert cur["prev_hash"] == hashlib.sha256(prev_raw).hexdigest()


def test_chain_detects_payload_tampering(monkeypatch, tmp_path: Path):
    log = _emit_three(monkeypatch, tmp_path)
    lines = log.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["payload_meta"]["n_athletes"] = 999_999
    lines[1] = json.dumps(rec, sort_keys=True)
    log.write_text("\n".join(lines) + "\n")
    assert audit.verify(log) is False


def test_chain_detects_record_deletion(monkeypatch, tmp_path: Path):
    log = _emit_three(monkeypatch, tmp_path)
    lines = log.read_text().splitlines()
    log.write_text(lines[0] + "\n" + lines[2] + "\n")
    assert audit.verify(log) is False


def test_verify_handles_missing_log(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "nope.log"))
    assert audit.verify() is True


def test_emit_fails_closed_on_write_error(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    real_open = builtins.open

    def boom(p, *a, **kw):
        if str(p).endswith("audit.log") and "a" in (a[0] if a else kw.get("mode", "")):
            raise OSError("disk full")
        return real_open(p, *a, **kw)

    monkeypatch.setattr(builtins, "open", boom)
    with pytest.raises(OSError):
        audit.emit("predict.request", {"n_records": 1})


def test_emit_fail_open_when_env_set(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NIL_AUDIT_LOG", str(tmp_path / "audit.log"))
    monkeypatch.setenv("NIL_AUDIT_FAIL_OPEN", "1")
    real_open = builtins.open

    def boom(p, *a, **kw):
        if str(p).endswith("audit.log") and "a" in (a[0] if a else kw.get("mode", "")):
            raise OSError("disk full")
        return real_open(p, *a, **kw)

    monkeypatch.setattr(builtins, "open", boom)
    rec = audit.emit("predict.request", {"n_records": 1})
    assert rec["event"] == "predict.request"
    assert rec["prev_hash"] == "0" * 64
