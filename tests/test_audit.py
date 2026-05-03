import json
import os
from pathlib import Path

from nil_predictor import audit


def test_emit_appends_record(tmp_path: Path, monkeypatch):
    log = tmp_path / "audit.log"
    monkeypatch.setenv("NIL_AUDIT_LOG", str(log))

    rec = audit.emit("test.event", payload={"n_records": 7, "seed": 42, "secret": "hidden"})
    assert rec["event"] == "test.event"
    assert "ts" in rec and "iso" in rec and "request_id" in rec
    # SAFE_FIELDS allowlist filters out unknown keys, including 'secret'.
    assert rec["payload_meta"] == {"n_records": 7, "seed": 42}

    lines = log.read_text().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event"] == "test.event"
    assert "secret" not in json.dumps(parsed)


def test_emit_is_appendable_across_calls(tmp_path: Path, monkeypatch):
    log = tmp_path / "audit.log"
    monkeypatch.setenv("NIL_AUDIT_LOG", str(log))

    rid = audit.emit("a", payload={"n_records": 1})["request_id"]
    audit.emit("b", payload={"n_records": 2}, request_id=rid)
    audit.emit("c", payload={"n_records": 3}, request_id=rid)

    lines = log.read_text().splitlines()
    assert len(lines) == 3
    rids = {json.loads(line)["request_id"] for line in lines}
    assert rids == {rid}


def test_tail_returns_last_n(tmp_path: Path, monkeypatch):
    log = tmp_path / "audit.log"
    monkeypatch.setenv("NIL_AUDIT_LOG", str(log))
    for i in range(5):
        audit.emit("x", payload={"n_records": i})
    last = audit.tail(2)
    assert len(last) == 2
    assert [r["payload_meta"]["n_records"] for r in last] == [3, 4]
