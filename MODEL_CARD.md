# Model Card — nil-predictor v0.1.0

## Intended use

Predict five NIL-related outcomes for **college (amateur) athletes**:
`valuation`, `deal_count`, `tier`, `portal`, `drafted`. Intended for
internal scenario analysis and demos. **Not for individual decisions
that materially affect a person's livelihood without human review.**

## Out of scope

- Pro contract value, salary, or career projection (no pro-stage data).
- Any decision involving protected characteristics (race, gender,
  national origin, religion, age, disability).
- Sports betting / line-setting.

> **Stage-separation rule:** amateur and pro outcomes live in separate
> packages, model cards, datasets, branches, artifacts, and HTTP
> routes. See [`CLAUDE.md`](./CLAUDE.md) for the full rule. The same
> ideology applies to any future stage boundary (high-school,
> international, etc.).

## Data

- **Source:** `nil_predictor.data.generate` — deterministic synthetic
  generator, not real athletes.
- **Provenance:** hand-calibrated to public NIL reporting; no PII; no
  scraped data.
- **Schema:** see `nil_predictor.features.FEATURE_COLUMNS`.
- **Quality dimensions (ISO/IEC 25012):** completeness ✓ (all rows
  fully populated by construction), accuracy ⚠ (synthetic — not real),
  consistency ✓, plausibility ✓ for distributions vs public reporting.

## Performance

Holdout n=10,000, seed=7, 80/20 split:

| Target       | Headline                              |
| ------------ | ------------------------------------- |
| valuation    | R² = 0.50, MAE = $1,851               |
| deal_count   | R² = 0.48, MAE = 1.53 deals           |
| tier         | accuracy = 0.80                       |
| portal       | accuracy = 0.83, log_loss = 0.441 (calibrated) |
| drafted      | accuracy = 0.87, AUC = 0.93, log_loss = 0.239 (calibrated) |

## Limitations

- Synthetic data ceiling — real-world generalization unverified.
- `portal` AUC near 0.64 reflects intentional generator noise floor;
  do not interpret single-athlete portal probabilities as actionable.
- Calibration was done on the same synthetic distribution; real data
  will require recalibration.

## Risk register (preliminary)

| Risk                                   | Severity | Mitigation                                |
| -------------------------------------- | -------- | ----------------------------------------- |
| Sport-segregated outcomes (M vs W)     | Medium   | Per-sport gaps tracked in fairness.json   |
| Conference proxy for school resources  | Medium   | Document in feature glossary              |
| Synthetic → real distribution shift    | High     | Block prod deploy until real-data eval    |
| Probability miscalibration on real data| Medium   | Recalibrate via CalibratedClassifierCV    |

## Fairness — declared thresholds (ISO/IEC TR 24027:2021)

Computed on the holdout split of every training run and gated in CI.
Groups are derived from the existing features:

- `conference_tier`: P5 (SEC, Big Ten, Big 12, ACC, Pac-12) vs G5
  (Big East, AAC, MWC) vs subdivision (FCS, D2)
- `gender_proxy`: men's vs women's sport partitions
- `sport`: individual sport — per-sport gaps are computed and
  surfaced in `fairness.json` for review, but are not yet enforced as
  CI gates (synthetic data produces large by-design per-sport gaps;
  thresholds will be tightened with real data).

| Check                                              | Threshold |
| -------------------------------------------------- | --------- |
| `drafted_dp_gap_conference_tier`                   | ≤ 0.30    |
| `drafted_eo_gap_conference_tier`                   | ≤ 0.30    |
| `portal_dp_gap_conference_tier`                    | ≤ 0.20    |
| `tier_dp_gap_conference_tier` (top-tier selection) | ≤ 0.30    |
| `valuation_bias_gap_gender_proxy_log10`            | ≤ 0.40    |

Builds fail when any threshold is exceeded. The synthetic generator
produces large by-design gaps across `gender_proxy` for valuation —
real-data thresholds will tighten in the next iteration. Source
implementation: `nil_predictor.fairness`.

## Governance — ISO/IEC 42001:2023 + 27001:2022

- **License / ownership:** internal only at this time.
- **Audit trail:** append-only, **hash-chained** JSONL at
  `<artifacts>/audit.log` (override via `NIL_AUDIT_LOG`). Each record
  carries the SHA-256 of the prior record's serialised line — any
  retroactive edit invalidates every subsequent hash (tamper-evidence).
  Events: `train.start`, `train.complete`, `predict.request`,
  `predict.response`, `predict.error`. Logs payload digests, never raw
  inputs — no PII even when real data replaces the synthetic
  generator. Chain integrity verified in CI via
  `nil_predictor.audit.verify`. The emitter is **fail-closed**: an
  `OSError` on append propagates so a request that cannot be audited
  is not served (mirrors JYSN L12 in `lunning-`). Set
  `NIL_AUDIT_FAIL_OPEN=1` to revert to fail-open for local fixtures.
- **DPIA:** N/A (synthetic data); required before any real-personal-
  data ingestion (ISO/IEC 27701:2019).

## Contact

Owner: nil-predictor maintainers (see CODEOWNERS once added).
