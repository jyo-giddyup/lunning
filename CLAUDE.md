# Project rules for AI agents and contributors

## Stage-separation rule (mandatory)

Amateur (college NIL) and professional (post-draft) modeling are
**different stages with different data, different obligations, and
different model cards**. The same governing ideology applies to any
other stage boundary that emerges (e.g., high-school recruiting,
international, NIL collective vs. direct deals).

For every stage:

- **Separate package or module.** Don't mix targets from different
  stages in `nil_predictor.models.TARGETS`. Add a sibling module
  (e.g., `nil_predictor.pro.models`) instead.
- **Separate model card.** New stage → new `MODEL_CARD_<stage>.md`
  with its own intended use, out-of-scope, risk register, and
  fairness baseline.
- **Separate dataset.** Real or synthetic, never blended across
  stages without an explicit, documented join key + purpose.
- **Separate branch and PR.** Never combine an amateur change and
  a pro change in the same branch/PR. Reviewers must see one
  scope at a time.
- **Separate artifacts.** Trained joblib files live under
  `artifacts/<stage>/...` so they cannot be loaded interchangeably.
- **Separate endpoints.** HTTP routes namespace by stage:
  `/predict/amateur`, `/predict/pro`, etc. Cross-stage chaining
  (e.g., gate pro on `drafted=True`) is allowed but must be
  explicit in the call site, not implicit in the model.

This rule is enforced socially today (reviewer responsibility) and
should be codified into CI on the next iteration (path filters or
a check that no PR diffs touch more than one `nil_predictor/<stage>/`
subtree).

## ML endpoints are gated by default (mandatory)

The service is designed to enhance internal / Syncofy consumers, not
to be a public ML endpoint. Any new endpoint whose path reads like an
ML operation — anything matching
`/(predict|explain|schema|train|score|forecast|classify|model|models|infer|inference|evaluate|embed|embeddings|features?|targets?)`
— **defaults to gated** (i.e. requires `X-API-Key` and, when
`NIL_REQUIRE_PAYMENT=1`, an active customer record).

Never add a new ML route to `PUBLIC_PATHS`. If you genuinely need one
publicly reachable (e.g. a public demo playground with per-IP rate
limiting), add its path to
`tests/test_ml_gate_invariant.py::EXPECTED_PUBLIC_ML_PATHS` with a
review comment explaining why. That edit **is** the review gate.

`/health` is intentionally minimal — no filesystem paths, no model
names, no secrets. Everything is on `HEALTH_ALLOWED_FIELDS` in the
same test file. New probe-safe fields go there; anything richer moves
behind `/schema`, which is gated.

The same ideology applies across stages (amateur, pro, and any future
sibling submodule): a new stage's endpoints default gated, its
artifacts default private, and its `/health` contributions stay
minimal.

## Companion docs

- `README.md` — install / train / serve / predict
- `MODEL_CARD.md` — amateur model card (intended use, scope,
  performance, risk register, fairness follow-ups)
- `BUILD_METRICS.json` — reproducible holdout metrics from the last
  release training run
