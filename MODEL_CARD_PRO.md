# Model Card — nil-predictor / pro v0.1.0

Sibling to [`MODEL_CARD.md`](./MODEL_CARD.md). Per the
stage-separation rule documented in
[`lunning-/CLAUDE.md`](https://github.com/jyo-giddyup/lunning-/blob/main/CLAUDE.md),
the pro stage has its own card, dataset, code path, artifact
directory, and CI footprint. The amateur stage's invariants do not
imply this stage's; they are independent.

## Intended use

Predict four outcomes for **drafted** college athletes after they
enter the professional pipeline:

| Target               | Type       | Question                                      |
| -------------------- | ---------- | --------------------------------------------- |
| `pro_contract_value` | regression | First-pro-contract dollars                    |
| `pro_career_length`  | regression | Expected pro years                            |
| `pro_all_star`       | binary     | P(All-Pro / All-Star within first 5 years)    |
| `agent_signed`       | binary     | P(top-tier agency signs the player pre-draft) |

For internal scenario analysis only. **Not for individual decisions
that materially affect a person's livelihood or bargaining position
without human review.**

## Out of scope

- Amateur (NIL) outcomes — handled by the sibling amateur package.
- Sports betting / line-setting / DFS pricing.
- Any decision involving protected characteristics
  (race, gender, national origin, religion, age, disability).
- Athletes the amateur predictor does not flag as draft-likely. The
  pro stage is meaningless without a non-trivial draft probability;
  callers must gate explicitly via
  [`nil_predictor.pro.chain`](./src/nil_predictor/pro/chain.py).

## Data

- **Source:** `nil_predictor.pro.data.generate` — derived from the
  amateur synthetic generator restricted to draft-eligible sports
  (football, men's basketball, baseball), augmented with synthetic
  draft-round / draft-pick / combine-score and pro outcomes.
- **Provenance:** hand-calibrated against public NFL/NBA/MLB rookie
  scale and signing-bonus reporting. No PII; no scraped data.
- **Schema:** `nil_predictor.pro.data.FEATURE_COLUMNS` (12 columns:
  the 9 amateur features plus `draft_round`, `draft_pick`,
  `combine_score`).
- **Quality dimensions (ISO/IEC 25012):**
  completeness ✓ (full rows by construction),
  accuracy ⚠ (synthetic — needs real NFL/NBA/MLB data before any
  production use), consistency ✓, plausibility ✓ for distributions
  vs public reporting.

## Performance

Holdout, n_amateur=30000 (≈ 1500–2500 drafted athletes), seed=11:

| Target               | Headline                            |
| -------------------- | ----------------------------------- |
| pro_contract_value   | R² ≈ 0.72                            |
| pro_career_length    | R² ≈ 0.30                            |
| pro_all_star         | accuracy ≈ 0.78, AUC ≈ 0.78          |
| agent_signed         | accuracy ≈ 0.71                      |

(Exact values printed by `python -m nil_predictor.pro.train`.)

## Limitations

- Synthetic data ceiling — real-world generalization unverified.
- The amateur generator's "drafted" label is coarse-grained; the pro
  generator inherits that signal floor for `pro_career_length`.
- Calibration was done on the synthetic distribution; real data will
  require recalibration of the binary classifiers (`pro_all_star`,
  `agent_signed`).
- Pro contract value is heavily right-tailed; MAE is dominated by a
  few star draftees and is not a good single number for ranking.

## Risk register (preliminary)

| Risk                                          | Severity | Mitigation                                             |
| --------------------------------------------- | -------- | ------------------------------------------------------ |
| Synthetic → real distribution shift           | High     | Block prod deploy until eval on real NFL/NBA/MLB data  |
| Sport-segregated outcomes (M football vs MBB) | Medium   | Track per-sport metrics; consider sport-specific heads |
| Agent-signing label leaks future contract size| Medium   | Audit feature correlations before any real-data train  |
| Misuse for player-bargaining advantage        | High     | Card declares scope; access gated by JYSN              |

## Governance

- License / ownership: internal only at this time.
- Audit trail: `train.start` / `train.complete` events tagged
  `stage=pro` go to the same hash-chained log as the amateur stage.
- DPIA: N/A while data is synthetic; **required** before any real
  player data is ingested.

## Stage-separation invariants

| Concern        | Pro stage location                        |
| -------------- | ----------------------------------------- |
| Package        | `src/nil_predictor/pro/`                  |
| Data generator | `nil_predictor.pro.data.generate`         |
| Models         | `nil_predictor.pro.models.TARGETS`        |
| Train CLI      | `python -m nil_predictor.pro.train`       |
| Predict CLI    | `python -m nil_predictor.pro.predict`     |
| Artifacts      | `artifacts/pro/`                          |
| Tests          | `tests/test_pro.py`, `tests/test_pro_chain.py` |
| Model card     | `MODEL_CARD_PRO.md` (this file)           |

The chain helper (`nil_predictor.pro.chain.predict`) is the only
sanctioned way to compose amateur + pro at runtime; it is explicit at
the call site and never substitutes for either stage's CLI.
