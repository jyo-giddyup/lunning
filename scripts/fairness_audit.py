"""One-shot fairness audit for nil-predictor's binary classifiers.

Generates a held-out synthetic test set, runs the trained `portal` and
`drafted` models on it, and writes a markdown report with demographic-parity
gap and equalized-odds gap across protected attributes (Power-4 conference
membership, men's vs women's sport).

Methodology and budgets come from the lunning- repo's `predictions.fairness`
module. The audit reports — it does not gate. Wire a CI gate as a separate
follow-up.

Usage:
    python scripts/fairness_audit.py \\
        --artifacts /tmp/nil-artifacts-prod \\
        --lunning-src ../lunning-/src \\
        --out FAIRNESS_AUDIT.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path
from typing import Any

import numpy as np


# Budgets per ISO/IEC TR 24027 (matches lunning- tests/test_fairness.py).
DEMOGRAPHIC_PARITY_BUDGET = 0.05
EQUALIZED_ODDS_BUDGET = 0.10

POWER_4 = {"SEC", "Big_Ten", "ACC", "Big_12"}
# Only sports with unambiguous women's identity in the data generator.
# `gymnastics` and `volleyball` exist without a gender prefix and are dropped
# from the audit rather than misclassified.
WOMENS_SPORTS = {"womens_basketball", "womens_soccer", "softball"}


def _import_predictions(lunning_src: Path):
    """Resolve the `predictions` package from lunning-. Tries pip-installed
    first, then sys.path injection. Fails loudly if neither works."""
    try:
        import predictions.fairness  # noqa: F401
        return
    except ImportError:
        pass
    if not lunning_src.exists():
        sys.exit(
            f"error: predictions package not found.\n"
            f"  Either: pip install -e {lunning_src.parent} (from a lunning- checkout)\n"
            f"  Or pass --lunning-src pointing to lunning-'s src/ directory.\n"
            f"  Tried: {lunning_src} (does not exist)"
        )
    sys.path.insert(0, str(lunning_src))
    try:
        import predictions.fairness  # noqa: F401
    except ImportError as e:
        sys.exit(f"error: failed to import predictions from {lunning_src}: {e}")


def _binary(values: list[Any], true_label: str = "True") -> np.ndarray:
    return np.array([1 if str(v) == true_label else 0 for v in values], dtype=int)


def _verdict(value: float, budget: float) -> str:
    return "PASS" if value <= budget else "FAIL"


def _render_section(
    f, title: str, attr_label: str, group_labels: dict[int, str], r: dict
) -> None:
    """Render one (target, attribute) section to the markdown file handle."""
    dp = r["demographic_parity_gap"]
    eo = r["equalized_odds_gap"]
    f.write(f"### by {attr_label}\n\n")
    f.write("| Group | n | base rate | selection | TPR | FPR | accuracy |\n")
    f.write("|---|---:|---:|---:|---:|---:|---:|\n")
    base_rates: list[float] = []
    for key, stats in r["per_group"].items():
        # key is "group_0" / "group_1"
        idx = int(key.split("_")[1])
        label = group_labels.get(idx, key)
        base_rates.append(stats["base_rate"])
        f.write(
            f"| {label} | {stats['n']} | "
            f"{stats['base_rate']:.3f} | {stats['selection_rate']:.3f} | "
            f"{stats['tpr']:.3f} | {stats['fpr']:.3f} | {stats['accuracy']:.3f} |\n"
        )
    f.write(f"\n- Demographic-parity gap: **{dp:.3f}** "
            f"({_verdict(dp, DEMOGRAPHIC_PARITY_BUDGET)} vs budget {DEMOGRAPHIC_PARITY_BUDGET})\n")
    f.write(f"- Equalized-odds gap: **{eo:.3f}** "
            f"({_verdict(eo, EQUALIZED_ODDS_BUDGET)} vs budget {EQUALIZED_ODDS_BUDGET})\n")
    if r.get("insufficient_cohorts"):
        f.write(f"- Insufficient-cohort exclusions: {r['insufficient_cohorts']}\n")
    # Flag structural budget failures: a group with base_rate==0 cannot generate
    # true positives, so TPR=0 there is correct, not biased. The EO gap will
    # still trigger FAIL, but it's a label-availability artifact.
    if base_rates and min(base_rates) == 0.0 and max(base_rates) > 0.0:
        f.write(
            "- ⚠️ **Structural caveat**: one group has base rate 0 in the data "
            "(no positive labels exist for it). EO/DP gaps measure a label "
            "imbalance the model cannot remove and should not be read as bias.\n"
        )
    f.write("\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=5000, help="size of held-out audit set (default 5000)")
    p.add_argument("--seed", type=int, default=99, help="RNG seed (must differ from training seeds)")
    p.add_argument("--artifacts", type=Path, default=Path("artifacts"),
                   help="directory holding trained .joblib files")
    p.add_argument("--out", type=Path, default=Path("FAIRNESS_AUDIT.md"),
                   help="output report path")
    p.add_argument("--lunning-src", dest="lunning_src", type=Path,
                   default=Path("../lunning-/src"),
                   help="path to lunning-'s src/ directory if not pip-installed")
    args = p.parse_args()

    _import_predictions(args.lunning_src.resolve())

    # Reuse nil-predictor's data generator and predict pipeline.
    from nil_predictor.data import DataConfig, generate
    from nil_predictor.predict import predict
    from predictions.fairness import report

    df = generate(DataConfig(n_athletes=args.n, seed=args.seed))
    target_cols = [
        "athlete_id",
        "nil_valuation_usd", "deal_count_12mo", "tier",
        "in_transfer_portal", "drafted",
    ]
    feature_records = df.drop(columns=[c for c in target_cols if c in df.columns]).to_dict("records")
    preds = predict(feature_records, args.artifacts)

    # Predicted classes (0/1) and ground truth.
    drafted_pred = _binary([p["drafted"] for p in preds])
    portal_pred = _binary([p["portal"] for p in preds])
    drafted_true = df["drafted"].astype(int).to_numpy()
    portal_true = df["in_transfer_portal"].astype(int).to_numpy()

    # Protected attributes. 1 = the named group, 0 = everyone else.
    power = np.array([1 if c in POWER_4 else 0 for c in df["conference"]], dtype=int)
    women = np.array([1 if s in WOMENS_SPORTS else 0 for s in df["sport"]], dtype=int)

    sections: list[tuple[str, str, dict[int, str], np.ndarray, np.ndarray, np.ndarray]] = [
        ("drafted", "Power-4 vs other", {0: "non-Power-4", 1: "Power-4"},
         drafted_true, drafted_pred, power),
        ("drafted", "Men's vs Women's sport", {0: "men's / mixed", 1: "women's"},
         drafted_true, drafted_pred, women),
        ("portal", "Power-4 vs other", {0: "non-Power-4", 1: "Power-4"},
         portal_true, portal_pred, power),
        ("portal", "Men's vs Women's sport", {0: "men's / mixed", 1: "women's"},
         portal_true, portal_pred, women),
    ]

    # Stdout summary first so a CI log shows the verdict without scrolling.
    print(f"=== FAIRNESS AUDIT (n={args.n}, seed={args.seed}, artifacts={args.artifacts}) ===")
    for target, attr_label, _labels, ytrue, ypred, attr in sections:
        r = report(ytrue, ypred, attr)
        dp = r["demographic_parity_gap"]
        eo = r["equalized_odds_gap"]
        print(f"  {target:<8} {attr_label:<26} "
              f"DP={dp:.3f} {_verdict(dp, DEMOGRAPHIC_PARITY_BUDGET):4}  "
              f"EO={eo:.3f} {_verdict(eo, EQUALIZED_ODDS_BUDGET):4}")

    # Write the report.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        ts = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        f.write("# nil-predictor fairness audit\n\n")
        f.write(
            f"_Generated {ts} · n={args.n} · seed={args.seed} · "
            f"artifacts={args.artifacts}_\n\n"
        )
        f.write(
            f"Budgets: DP ≤ {DEMOGRAPHIC_PARITY_BUDGET}, "
            f"EO ≤ {EQUALIZED_ODDS_BUDGET}. "
            "Methodology: lunning- `predictions.fairness` (ISO/IEC TR 24027:2021).\n\n"
        )
        f.write(
            "Protected attributes are derived from the synthetic data generator. "
            "`Power-4` = `{SEC, Big_Ten, ACC, Big_12}`. `Women's` = "
            "`{womens_basketball, womens_soccer, softball}` only — "
            "`gymnastics` and `volleyball` are excluded because the generator "
            "doesn't tag gender for those sports.\n\n"
        )
        f.write(
            "**This audit reports, it does not gate.** It is generated on demand "
            "and committed for visibility. CI enforcement is a separate "
            "follow-up.\n\n"
        )

        current_target = None
        for target, attr_label, labels, ytrue, ypred, attr in sections:
            if target != current_target:
                f.write(f"## `{target}`\n\n")
                current_target = target
            r = report(ytrue, ypred, attr)
            _render_section(f, target, attr_label, labels, r)

        f.write("---\n\n")
        f.write(f"To regenerate: `python scripts/fairness_audit.py --artifacts {args.artifacts}`\n")

    print(f"\nReport written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
