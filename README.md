# lunning

NIL outcome predictor for college athletes. The implementation in this repo (`nil-predictor`) is the org's first concrete model and is held to the standards baseline below.

Reference methodology: `jyo-giddyup/lunning-` on the `claude/fair-efficient-models-g9gC3` branch.

## Standards baseline

Any prediction model in this repo MUST:

| Concern    | Standard                | Requirement                                              |
| ---------- | ----------------------- | -------------------------------------------------------- |
| Fairness   | ISO/IEC TR 24027:2021   | Report demographic-parity + equalized-odds gaps in CI    |
| Risk       | ISO/IEC 23894:2023      | Maintain a risk register in the model card               |
| Governance | ISO/IEC 42001:2023      | Ship a model card; emit audit-log events on eval/predict |
| Trust      | ISO/IEC TR 24028:2020   | Document intended use + limitations                      |
| Data qual. | ISO/IEC 25012:2008      | Declared schema, provenance, quality dimensions          |
| Security   | ISO/IEC 27001:2022      | Append-only audit trail, no PII in logs                  |
| Privacy    | ISO/IEC 27701:2019      | DPIA required before any real-personal-data use          |

Fairness budgets are enforced as a CI gate — a build fails when the gap exceeds the model card's declared threshold. The `nil-predictor` package below ships with synthetic data so this gate runs without privacy implications; before any real On3/Opendorse data is loaded, a DPIA per ISO/IEC 27701 must be completed.

## nil-predictor

Five stacked targets are trained from a single shared feature set:

| Target        | Type           | Estimator                              |
| ------------- | -------------- | -------------------------------------- |
| `valuation`   | Regression     | GradientBoosting + log-target wrapper  |
| `deal_count`  | Poisson regr.  | HistGradientBoosting (poisson loss)    |
| `tier`        | 4-class clf.   | GradientBoostingClassifier             |
| `portal`      | Binary clf.    | LogisticRegression                     |
| `drafted`     | Binary clf.    | GradientBoostingClassifier             |

Inputs:

- `sport`, `position`, `conference`, `year`
- `starter` (bool), `performance_score` (0–100)
- `instagram_followers`, `tiktok_followers`, `twitter_followers`

> Real On3/Opendorse data is not bundled. The included generator produces a deterministic, hand-calibrated synthetic dataset so the full pipeline runs offline. Swap in real data by replacing `nil_predictor.data.generate` — and complete the DPIA first.

## Install

```bash
pip install -r requirements.txt
# or, for an editable install with console scripts:
pip install -e .
```

## Train

```bash
python -m nil_predictor.train --n 5000 --out artifacts/
```

Writes `artifacts/<target>.joblib` for each model and a combined `artifacts/metrics.json`.

## Predict

```bash
echo '{
  "sport": "football",
  "position": "QB",
  "conference": "SEC",
  "year": "JR",
  "starter": true,
  "performance_score": 87,
  "instagram_followers": 250000,
  "tiktok_followers": 180000,
  "twitter_followers": 90000
}' | python -m nil_predictor.predict --artifacts artifacts/
```

## Test

```bash
pytest -q
```

## Holdout metrics (n=10,000, seed=7, 80/20 split)

| Target       | Headline                              |
| ------------ | ------------------------------------- |
| valuation    | R² = 0.50, MAE = $1,851               |
| deal_count   | R² = 0.48, MAE = 1.53 deals           |
| tier         | accuracy = 0.80                       |
| portal       | accuracy = 0.83, AUC = 0.64           |
| drafted      | accuracy = 0.86, AUC = 0.93           |

Latency: 0.19 ms / record at batch size 1,000.

## Companion repos

- **`kolx`** — `/api/predict` Next.js endpoint that bridges to this package's CLI.
- **`lunning-`** — reference fair/efficient/compliant prediction-model methodology this implementation conforms to.
