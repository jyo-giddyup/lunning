# Contributing to lunning

Thanks for your interest. This project is small and the bar for contribution is straightforward: solve a real problem, keep the diff focused, leave the codebase a little tidier than you found it.

## Ground rules

- **One concern per PR.** A bug fix, a feature, or a refactor — not all three.
- **No drive-by formatting.** If you have to touch unrelated code to do your work, do that in a separate PR.
- **Tests when behavior changes.** If you fix a bug, add a test that fails without your fix.
- **Honor the audit-log invariant.** Events are append-only. Never UPDATE or DELETE rows in `events` from application code.

## Local setup

See [README.md](./README.md#local-setup).

## Workflow

1. Open an issue first for anything non-trivial. Cheap to discuss before you build.
2. Fork (or branch if you have push access).
3. Branch naming: `<kind>/<short-slug>` — e.g. `fix/scoreboard-undo`, `feat/sport-tennis`, `docs/contributing`.
4. Commits: imperative mood, present tense ("Add tennis rules engine", not "Added"). Don't squash unrelated work into one commit.
5. Open a PR against `main`. Fill in the PR template.
6. CI must pass. Reviewer will merge.

## Code style

- TypeScript strict mode, no `any`.
- Prefer Server Components and Server Actions over client components and API routes.
- Tailwind utility classes; avoid one-off CSS unless the rule is genuinely shared.
- No client-side data fetching for content that's available server-side.

## What's in scope

- v1.x: scorekeeping UX polish, sport-specific rule engines (tennis, basketball, pickleball), shareable game URLs, a11y, basic moderation tools.
- v2: device-signed events, dispute resolution, leagues/tournaments.

## What's out of scope (for now)

- Native mobile apps. PWA-first.
- Auth/accounts. Will revisit when there's a clear need.
- Predictions/analytics/ML. Lives in a separate repo.

## Reporting

- Bugs: open an issue using the bug template.
- Security: see [legal/SECURITY.md](./legal/SECURITY.md). Do not file public issues for security findings.
- Accessibility barriers: see [legal/ACCESSIBILITY.md](./legal/ACCESSIBILITY.md).
