# nil-predictor

Multi-target prediction models for college athlete NIL outcomes.

Five stacked targets are trained from a single feature set:

| Target        | Type           | Estimator                              |
| ------------- | -------------- | -------------------------------------- |
| `valuation`   | Regression     | GradientBoosting + log-target wrapper  |
| `deal_count`  | Poisson regr.  | HistGradientBoosting (poisson loss)    |
| `tier`        | 4-class classif. | GradientBoostingClassifier            |
| `portal`      | Binary         | LogisticRegression                     |
| `drafted`     | Binary         | GradientBoostingClassifier             |

Inputs:

- `sport`, `position`, `conference`, `year`
- `starter` (bool), `performance_score` (0–100)
- `instagram_followers`, `tiktok_followers`, `twitter_followers`

> Real On3/Opendorse data is not bundled. The included generator
> produces a deterministic, hand-calibrated synthetic dataset so the
> full pipeline runs offline. Swap in real data by replacing
> `nil_predictor.data.generate`.

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

Writes `artifacts/<target>.joblib` for each model and a combined
`artifacts/metrics.json`.

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
