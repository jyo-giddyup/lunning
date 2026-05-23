# Deploying nil-predictor

The full path from this repo to a live HTTPS URL.

## Prerequisites (one-time)

```bash
# Fly CLI
brew install flyctl                # macOS
# or: curl -L https://fly.io/install.sh | sh
flyctl auth signup                 # or: flyctl auth login
```

If the GHCR image is private (default for new repos), make it pullable:

- Easy: visit https://github.com/users/jyo-giddyup/packages/container/nil-predictor/settings → *Change visibility* → public.
- Or: keep it private and give Fly a registry token. See https://fly.io/docs/reference/private-registry/.

## Persistent volume (one-time)

The predictor mounts a Fly volume at `/app/data` to persist:

- `/app/data/customers.db` — the per-customer entitlement store
- `/app/data/audit.log` — the JSONL audit log

Without the volume both files are wiped on every deploy. Create it once:

```bash
flyctl volumes create data --region iad --size 1 --app nil-predictor --yes
```

The `[mounts]` block in `fly.toml` references this volume by name, so subsequent deploys mount it automatically.

## Each deploy

The image is auto-built and pushed to `ghcr.io/jyo-giddyup/nil-predictor:latest` by `.github/workflows/publish-image.yml` on every push to `main` that touches the build inputs.

```bash
# First time:
flyctl launch --image ghcr.io/jyo-giddyup/nil-predictor:latest \
  --copy-config --no-deploy --name nil-predictor
flyctl deploy

# Subsequent deploys:
flyctl deploy
```

Live URL: `https://nil-predictor.fly.dev`

## Verify

```bash
curl https://nil-predictor.fly.dev/health
# {"ok": true, "models_present": ["valuation","deal_count","tier","portal","drafted"], "models_missing": []}

curl -X POST https://nil-predictor.fly.dev/predict \
  -H 'content-type: application/json' \
  -d '{"sport":"football","position":"QB","conference":"SEC","year":"JR",\
       "starter":true,"performance_score":87,\
       "instagram_followers":250000,"tiktok_followers":180000,"twitter_followers":90000}'
```

## Stripe billing

The service exposes `POST /checkout` (creates a Stripe Checkout Session) and
`POST /webhooks/stripe` (receives Stripe events). Before going live:

1. In the Stripe dashboard create a product + recurring price; copy the
   `price_...` ID.
2. Add a webhook endpoint pointing at `https://nil-predictor.fly.dev/webhooks/stripe`
   subscribed to at least:
   - `checkout.session.completed` (mints the customer + API key)
   - `customer.subscription.updated` (propagates status changes)
   - `customer.subscription.deleted` (revokes access)

   Or use the `register-stripe-webhook` workflow in Actions to do this automatically.
3. Set Fly secrets (these never appear in logs or the image):

```bash
flyctl secrets set \
  STRIPE_SECRET_KEY=sk_live_... \
  STRIPE_WEBHOOK_SECRET=whsec_... \
  STRIPE_PRICE_ID=price_... \
  STRIPE_SUCCESS_URL=https://how-to-do-this.vercel.app/billing/success \
  STRIPE_CANCEL_URL=https://how-to-do-this.vercel.app/billing/cancel
```

Or use the `set-stripe-secrets` workflow in Actions.

Use `sk_test_...` / `whsec_test_...` keys against the Stripe test mode first;
the test card `4242 4242 4242 4242` will succeed.

## Customer entitlement (per-API-key)

By default the service runs in legacy mode: `/predict` and friends are gated only by `NIL_API_KEY` if set, otherwise open. To enforce per-customer entitlement (paying customers each get their own `nk_*` API key, cancelled customers automatically lose access), flip the feature flag:

```bash
flyctl secrets set NIL_REQUIRE_PAYMENT=true
```

In entitlement mode every gated request must carry `X-API-Key: nk_...` and the key must resolve to a customer row in `/app/data/customers.db` with status `active` or `trialing`. `NIL_API_KEY` (if also set) stays accepted as a dev/admin override.

### Customer bootstrap flow

1. Customer hits `/billing` on the consumer, clicks Subscribe.
2. Consumer's `/api/checkout` proxies to the predictor's `/checkout`, gets a Stripe URL.
3. Customer pays. Stripe redirects to `STRIPE_SUCCESS_URL?session_id=cs_...`.
4. Consumer's `/billing/success` page reads `session_id` and calls the predictor's `GET /customer/bootstrap?session_id=cs_...`.
5. Predictor returns the freshly-minted `api_key` exactly once. Subsequent calls with the same `session_id` return 404 — the customer must save the key (or recover it from a welcome email once that ships).
6. Customer uses the key in `X-API-Key` for all future `/predict` calls.

### Rollout sequence

1. Deploy this change with `NIL_REQUIRE_PAYMENT` unset — nothing changes for existing users.
2. Verify the customer DB is created on the volume (`flyctl ssh console -C 'ls -la /app/data/'`).
3. Subscribe the webhook to the new event types (or run the `register-stripe-webhook` workflow).
4. Do a Stripe test-mode checkout end-to-end; confirm `audit.tail()` shows `stripe.customer_created`.
5. Flip `NIL_REQUIRE_PAYMENT=true`. Existing un-keyed users get 401; paying users continue.

**Pre-launch legal checklist** (not provided by this repo, get from counsel):
Terms of Service, Privacy Policy, refund policy, Stripe Tax configured for
your jurisdictions, and confirmation that your Stripe account's business
profile is complete.

## Wire the rest of the stack

In Vercel, set env vars then redeploy:

- **kolx** project: `NIL_PREDICTOR_URL=https://nil-predictor.fly.dev`
- **how-to-do-this** project: `PREDICT_API_URL=https://kolx.vercel.app`

Live consumer URL: `https://how-to-do-this.vercel.app/predict`
