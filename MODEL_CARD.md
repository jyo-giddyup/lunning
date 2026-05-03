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
| Sport-segregated outcomes (M vs W)     | Medium   | Track per-sport metrics in CI (TODO)      |
| Conference proxy for school resources  | Medium   | Document in feature glossary              |
| Synthetic → real distribution shift    | High     | Block prod deploy until real-data eval    |
| Probability miscalibration on real data| Medium   | Recalibrate via CalibratedClassifierCV    |

## Fairness baseline (TODO)

Per the org standards baseline, the next iteration must add:
- Demographic-parity gap on `drafted` and `tier` across `sport` (a
  proxy for gender) and `conference` (a proxy for school resources).
- Equalized-odds gap on `drafted` (TPR/FPR per group).
- A CI gate that fails when gaps exceed declared thresholds.

These are tracked as follow-up; not yet implemented in this commit.

## Governance

- License / ownership: internal only at this time.
- Audit trail: not yet emitted (TODO — required by ISO/IEC 42001:2023).
- DPIA: N/A (synthetic data).

## Contact

Owner: nil-predictor maintainers (see CODEOWNERS once added).
