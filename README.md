# lunning

Open, auditable scorekeeping for amateur sports. Every score change is timestamped, append-only, and viewable by anyone with the game URL. No more "what was the score?" arguments.

## What's here (v1)

- Create a game with a title and any number of sides (teams or players).
- Add or subtract points per side. Every change is logged.
- Share the game URL — spectators see the live score and the full event history.
- Sport-agnostic: works for tennis points, basketball, pickleball, beer pong, anything where you count points per side.

Future (v1.1+): sport-specific rule engines (tennis sets, basketball quarters, golf strokes), device-signed events, dispute resolution, public leaderboards.

## Stack

Next.js 14 (App Router) · React Server Components · Supabase (Postgres + Realtime) · Tailwind · TypeScript. Designed to deploy to Vercel free tier.

## Local setup

```bash
pnpm install
cp .env.example .env.local           # fill in Supabase URL + anon key
psql "$DATABASE_URL" -f supabase/schema.sql
pnpm dev
```

Open http://localhost:3000.

## Deploy

1. Create a Supabase project (free tier). Run `supabase/schema.sql` in the SQL editor.
2. Push this repo to GitHub (already done if you're reading this on github.com).
3. Import the repo on Vercel. Set env vars from `.env.example`.
4. Deploy. Live within 60 seconds.
5. (Optional) Custom domain: see [`docs/ORG_SETUP.md`](./docs/ORG_SETUP.md).

No paywalls, no auth flow yet — anyone with a game URL can score. Treat URLs as semi-private until v1.1 adds device signing.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## License

MIT — see [LICENSE](./LICENSE).

## Legal

Legal scaffolding lives in [`legal/`](./legal/README.md): privacy policy, terms of service, security policy, accessibility statement. **All templates — not legal advice. Have counsel review before launch.**

## Reporting issues

- Bugs / features: open a GitHub issue (templates provided).
- Security: see [`legal/SECURITY.md`](./legal/SECURITY.md).
- Accessibility barriers: see [`legal/ACCESSIBILITY.md`](./legal/ACCESSIBILITY.md).
