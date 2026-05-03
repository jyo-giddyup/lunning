# Accessibility statement

We aim for lunning to conform to **WCAG 2.1 Level AA**. This is the standard referenced by US Section 508, the EU Web Accessibility Directive, the UK Public Sector Bodies Accessibility Regulations, and the Americans with Disabilities Act (per recent DOJ guidance).

## Current state

The v1 scaffold uses semantic HTML, native form controls, and tabular numerals for the scoreboard. It has not yet been audited against WCAG 2.1 AA. Known gaps to address before claiming conformance:

- [ ] Color contrast audit (minimum 4.5:1 for body text, 3:1 for large text and UI controls).
- [ ] Keyboard-only navigation pass for the scoreboard (+/- buttons, focus indicators).
- [ ] Screen reader announcement when scores update (use `aria-live="polite"` on the scoreboard region).
- [ ] Visible focus states (do not rely on browser defaults that get overridden by Tailwind reset).
- [ ] `prefers-reduced-motion` honored for any animations.
- [ ] Alt text on any non-decorative images.

## Reporting barriers

If you encounter an accessibility barrier, email **TODO-accessibility@TODO-domain.com** with:

- The page or feature.
- What assistive technology you were using.
- What you expected vs. what happened.

We aim to acknowledge within 5 business days and remediate or provide an alternative within 30 days.
