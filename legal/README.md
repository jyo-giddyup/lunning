# Legal scaffolding for lunning

**These documents are templates, not legal advice.** Drafted by an AI as a starting point. Have an attorney review and adapt them before publishing to real users, especially if you ever expand to regulated contexts (healthcare, finance, education, anything with under-13 users, official tournament records).

Scope assumed: a non-regulated, consumer-facing scorekeeping web app for amateur sports. If that changes, this scaffolding is not enough.

## What's here

- `PRIVACY.md` — short privacy policy: what's collected, why, how to delete.
- `TERMS.md` — short terms of service: acceptable use, no warranty, liability cap.
- `SECURITY.md` — vulnerability disclosure policy.
- `ACCESSIBILITY.md` — WCAG 2.1 AA commitment + reporting channel.

## What still needs a human (even for non-regulated)

1. **Trademark check** for the name "lunning" before investing in branding. I have not searched any registry.
2. **Choice of governing law / venue** in `TERMS.md` — currently a TODO.
3. **Entity formation** if you intend to limit personal liability.
4. **Insurance** — general liability and cyber, especially once you have paying users.
5. **Trigger events that move you into a regulated zone**: accepting payments (PCI-DSS scope via Stripe), adding under-13 user flows (COPPA), targeting EU users (GDPR), partnering with sanctioned leagues.

## Engineering follow-ups

- [ ] Add `/privacy`, `/terms`, `/security` routes that render these markdown files.
- [ ] Footer link on every page.
- [ ] Right-to-erasure: a way for a game owner to delete their game and its events from the UI (currently DB-only).
- [ ] Consider a Postgres trigger that REVOKEs UPDATE/DELETE on `events` so the audit log is enforced at the DB layer, not just the application layer.
