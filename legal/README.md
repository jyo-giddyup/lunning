# Legal scaffolding for lunning

**These documents are templates, not legal advice.** They were drafted by an AI assistant as a starting point. Before publishing this app to real users, you must have a qualified attorney in your jurisdiction(s) review and adapt every document here.

What's in this folder:

- `PRIVACY.md` — privacy policy template covering what the app collects, why, retention, and user rights.
- `TERMS.md` — terms of service template: acceptable use, disclaimer of warranties, liability cap, governing law placeholder.
- `SECURITY.md` — responsible disclosure / vulnerability reporting policy.
- `ACCESSIBILITY.md` — commitment to WCAG 2.1 AA and how to report barriers.
- `DPA.md` — data processing addendum skeleton for B2B customers under GDPR.

## What still needs a human lawyer

This list is not exhaustive. It is the minimum I would not ship without:

1. **Jurisdictional review.** GDPR (EU), UK GDPR, CCPA/CPRA (California), VCDPA (Virginia), CPA (Colorado), CTDPA (Connecticut), UCPA (Utah), Quebec Law 25, Brazil LGPD, India DPDP Act — each has different consent, notice, and rights requirements. The privacy policy template uses generic language; counsel must tailor it.
2. **Data Protection Impact Assessment (DPIA).** Required under GDPR Art. 35 if you process data on a large scale or systematically.
3. **EU/UK representative.** GDPR Art. 27 requires a local representative if you target EU users from outside the EU. Same for UK.
4. **Standard Contractual Clauses (SCCs)** for cross-border data transfer (e.g. EU users → US-hosted Supabase/Vercel). Schrems II implications.
5. **COPPA.** If anyone under 13 might use the app, US federal law requires verifiable parental consent. The app currently has no age gate.
6. **Section 230 / EU DSA / UK Online Safety Act.** Game titles, side names, and notes are user-generated. You inherit moderation duties.
7. **Trademark clearance** for the name "lunning." I have not searched USPTO, EUIPO, or any other registry. Run a clearance search before investing in branding.
8. **Entity formation, terms enforceability, choice-of-law/forum, arbitration clauses, class-action waivers** — all materially affect what "defending in court" looks like.
9. **Insurance.** General liability, errors & omissions, cyber. Counsel and a broker.
10. **Subprocessor disclosure.** If you collect personal data, you must list every vendor that touches it (Supabase, Vercel, etc.) and pass through their DPAs.

## What the engineering side is responsible for

These are within scope of this codebase and should be wired up before launch:

- [ ] Footer link to `/privacy`, `/terms`, `/security` on every page (TODO: add routes that render these markdown files).
- [ ] Cookie banner only if you add cookies/tracking (you currently have none — keep it that way to avoid the requirement).
- [ ] Right-to-erasure endpoint: a way for a user to request deletion of a game and all its events (currently only deletable via DB).
- [ ] Audit-log integrity: events are append-only at the application layer, but the service-role key can still UPDATE/DELETE. Consider a Postgres trigger that REVOKEs UPDATE/DELETE on `events` for everyone except a dedicated migration role.
- [ ] Backups + retention policy documented and tested.
- [ ] Incident response runbook.
