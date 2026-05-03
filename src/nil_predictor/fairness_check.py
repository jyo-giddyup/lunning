"""CI fairness gate.

Reads `<artifacts>/fairness.json` produced by `train_all` and exits
non-zero if any declared threshold is exceeded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fairness gate (ISO/IEC TR 24027)")
    parser.add_argument("--artifacts", default="artifacts")
    args = parser.parse_args()

    path = Path(args.artifacts) / "fairness.json"
    if not path.exists():
        print(f"fairness.json not found at {path}", file=sys.stderr)
        return 2

    report = json.loads(path.read_text())
    print(json.dumps({
        "passed": report.get("passed"),
        "violations": report.get("violations", []),
        "thresholds": report.get("thresholds", {}),
    }, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
