# lunning

Multi-target prediction models for college athlete NIL outcomes.

## Standards baseline

Any prediction model added to this repo MUST:

| Concern    | Standard                | Requirement                                              |
| ---------- | ----------------------- | -------------------------------------------------------- |
| Fairness   | ISO/IEC TR 24027:2021   | Report demographic-parity + equalized-odds gaps in CI    |
| Risk       | ISO/IEC 23894:2023      | Maintain a risk register in the model card               |
| Governance | ISO/IEC 42001:2023      | Ship a model card; emit audit-log events on eval/predict |
| Trust      | ISO/IEC TR 24028:2020   | Document intended use + limitations                      |
| Data qual. | ISO/IEC 25012:2008      | Declared schema, provenance, quality dimensions          |
| Security   | ISO/IEC 27001:2022      | Append-only audit trail, no PII in logs                  |
| Privacy    | ISO/IEC 27701:2019      | DPIA required before any real-personal-data use          |

Fairness budgets are enforced as a CI gate — a build fails when the gap
exceeds the model card's declared threshold. Reference implementation
lives in `jyo-giddyup/lunning-` on the `claude/fair-efficient-models-g9gC3`
branch.

> **Status of this package against the baseline:** the synthetic data is
> non-personal so DPIA is N/A (ISO/IEC 27701:2019); intended use +
> limitations are documented in `MODEL_CARD.md` (ISO/IEC TR 24028:2020);
> fairness gates run on every CI build and fail the build on threshold
> violation (`fairness_check`, ISO/IEC TR 24027:2021); the audit log is
> hash-chained, append-only, and fail-closed, with chain integrity
> verified in CI (`audit.verify`, ISO/IEC 27001:2022 / 42001:2023);
> stage-separation across modeling stages is enforced by a CI
> path-filter (`stage_separation` job, see `CLAUDE.md`).

## nil-predictor

Five stacked targets are trained from a single feature set:

| Target        | Type           | Estimator                                      |
| ------------- | -------------- | ---------------------------------------------- |
| `valuation`   | Regression     | GradientBoosting + log-target wrapper          |
| `deal_count`  | Poisson regr.  | HistGradientBoosting (poisson loss)            |
| `tier`        | 4-class classif. | GradientBoostingClassifier                  |
| `portal`      | Binary         | LogisticRegression + isotonic calibration      |
| `drafted`     | Binary         | GradientBoostingClassifier + isotonic calib.   |

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
pip install -e ".[api]"
```

## Train

```bash
python -m nil_predictor.train --n 10000 --out artifacts/
```

Writes `artifacts/<target>.joblib` for each model and a combined
`artifacts/metrics.json`.

## Serve (HTTP)

```bash
uvicorn nil_predictor.api:app --host 0.0.0.0 --port 8000
# or build the docker image:
docker build -t nil-predictor . && docker run -p 8000:8000 nil-predictor
```

Endpoints: `GET /health`, `GET /schema`, `GET /explain?top_k=N`, `POST /predict`.

## Predict (CLI)

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

## Fairness audit

A one-shot fairness audit on the trained binary classifiers (`portal`,
`drafted`) across protected attributes (Power-4 vs other, men's vs
women's sport):

```bash
python scripts/fairness_audit.py \
  --artifacts artifacts/ \
  --lunning-src ../lunning-/src \
  --out FAIRNESS_AUDIT.md
```

Methodology and budgets come from `lunning-`'s `predictions.fairness`
module (ISO/IEC TR 24027:2021): DP ≤ 0.05, EO ≤ 0.10. Latest report:
[`FAIRNESS_AUDIT.md`](./FAIRNESS_AUDIT.md). The audit reports, it does
not gate; CI enforcement is a separate follow-up.

## Production access

The `nil-predictor` HTTP service is not internet-facing on its own.
Operator access (admin shell, deploy hooks, model-artifact rotation,
audit-log inspection) goes through **JYSN** — the identity-locked SSH
access fabric in
[`jyo-giddyup/lunning-`](https://github.com/jyo-giddyup/lunning-).

JYSN enforces the same standards baseline declared above:

- ISO/IEC 27001:2022 audit trail (hash-chained, no-PII)
- ISO/IEC 42001:2023 governance (model card, audit events on eval/predict)
- Privacy by default (Art. VI of `lunning-/CONSTITUTION.md`)

The same identity is used for both internal (mesh VPN) and external
(public bastion) paths; the cert TTL applied to a session is the
strictest of all active industry overlays. To deploy this service in a
regulated context, compose the relevant overlay (HIPAA, PCI, GDPR,
etc.) on top of JYSN — no code change to `nil-predictor` is needed.
