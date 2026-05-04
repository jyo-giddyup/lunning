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
   subscribed to at least `checkout.session.completed`. Copy the `whsec_...`
   signing secret.
3. Set Fly secrets (these never appear in logs or the image):

```bash
flyctl secrets set \
  STRIPE_SECRET_KEY=sk_live_... \
  STRIPE_WEBHOOK_SECRET=whsec_... \
  STRIPE_PRICE_ID=price_... \
  STRIPE_SUCCESS_URL=https://how-to-do-this.vercel.app/billing/success \
  STRIPE_CANCEL_URL=https://how-to-do-this.vercel.app/billing/cancel
```

Use `sk_test_...` / `whsec_test_...` keys against the Stripe test mode first;
the test card `4242 4242 4242 4242` will succeed.

**Pre-launch legal checklist** (not provided by this repo, get from counsel):
Terms of Service, Privacy Policy, refund policy, Stripe Tax configured for
your jurisdictions, and confirmation that your Stripe account's business
profile is complete.

## Wire the rest of the stack

In Vercel, set env vars then redeploy:

- **kolx** project: `NIL_PREDICTOR_URL=https://nil-predictor.fly.dev`
- **how-to-do-this** project: `PREDICT_API_URL=https://kolx.vercel.app`

Live consumer URL: `https://how-to-do-this.vercel.app/predict`
