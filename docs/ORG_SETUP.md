# Repository organization & domain setup

This is a checklist of the org-level changes that can't be done from inside the repo.

## 1. `.org` domain (lunning.org)

- [ ] Register `lunning.org` at a registrar (Cloudflare Registrar, Porkbun, or Namecheap; Cloudflare's at-cost pricing is cheapest, ~$10/yr).
- [ ] In Vercel: project → Settings → Domains → Add `lunning.org` and `www.lunning.org`. Vercel will show the DNS records to set.
- [ ] At your DNS provider:
      - `A @` → `76.76.21.21` (Vercel's apex)
      - `CNAME www` → `cname.vercel-dns.com`
- [ ] After Vercel provisions a TLS cert (~5 min), set `NEXT_PUBLIC_SITE_URL=https://lunning.org` in Vercel env vars and redeploy.

Why `.org`: signals community/non-commercial intent for amateur sports. If you ever monetize beyond donations, switch to `.com` or run both with one redirecting.

## 2. GitHub Organization

Moving from `jyo-giddyup/<repo>` to `<org>/<repo>` is worth doing **before** you have many forks, stars, or external links — GitHub auto-redirects URLs but it's still cleaner.

- [ ] github.com → your avatar → *Your organizations* → *New organization*. Free plan is fine.
- [ ] Pick a name. `lunning-sports` if `lunning` is taken. Verify domain ownership later for the verified-org badge.
- [ ] Repo → Settings → *Transfer ownership* → select the new org. Old URLs redirect.
- [ ] After transfer, update:
      - `package.json` `repository.url`
      - Any hardcoded GitHub URLs in code (search for `jyo-giddyup`)
      - Vercel project's git connection (it follows automatically but verify)
      - Branch protection rules — not transferred. Re-add: require PR, require CI to pass, dismiss stale approvals.
- [ ] In the new org: enable two-factor for all members, enable secret scanning + push protection, enable Dependabot security updates.

## 3. Branch protection on `main` (do this regardless of org move)

Repo → Settings → Branches → Add rule for `main`:

- [x] Require a pull request before merging
- [x] Require approvals: 1
- [x] Require status checks to pass: `CI / typecheck`
- [x] Require branches to be up to date before merging
- [x] Require conversation resolution before merging
- [x] Do not allow force pushes
- [x] Do not allow deletions
