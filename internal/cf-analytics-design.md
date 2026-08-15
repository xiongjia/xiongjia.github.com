# Cloudflare Web Analytics — Design Decision & Setup

> Privacy-friendly, cookieless traffic analytics via **Cloudflare Web
> Analytics** (free tier). Zero infrastructure, zero DNS changes, no cookie
> banner required.

## Decision

**Adopt Cloudflare Web Analytics** (free plan) as the site's traffic analytics.

- **Date**: 2026-08-05
- **Status**: implemented — config-driven beacon (`mkdocs.yml` →
  `overrides/partials/cf-analytics.html` → `main.html` + `404.html`); pending
  live verification after next deploy
- **Scope**: whole site (all pages + 404 page), served from GitHub Pages

## Overview

Cloudflare Web Analytics is a client-side JS beacon that reports page views,
referrers, and visitor breakdowns (country, device, browser) to a dashboard at
`dash.cloudflare.com`. The beacon is a single `<script>` tag:

- Works on **any host** — no need to move DNS or proxy the site through
  Cloudflare. GitHub Pages works as-is.
- **Cookieless & no personal data** by default (GDPR-friendly, no consent banner).
- **Free**, with no request limits relevant to a personal blog.

## Design Decision

### Why Cloudflare Web Analytics

| Option               | Cost          | Server needed | Notes                                                                              |
| -------------------- | ------------- | ------------- | ---------------------------------------------------------------------------------- |
| **CF Web Analytics** | **$0**        | No            | Free, cookieless, no DNS change. Beacon CDN sometimes slow in CN.                  |
| Google Analytics 4   | $0 (standard) | No            | **GA script is blocked in mainland China**; cookie consent burden.                 |
| Umami (self-hosted)  | $0 (OSS)      | Yes (VPS)     | Full data ownership, CN-friendly VPS possible — but adds a server to run/maintain. |
| GoatCounter          | $0 (personal) | No            | Viable, but requires one more external account; CF is already free.                |
| Plausible            | $9/mo SaaS    | No            | Paying for features a personal blog doesn't need.                                  |

Decision drivers, in order:

1. **Zero cost & zero infra** — no VPS, no new service to keep alive
   (matches the static-site philosophy: GitHub Pages + free services).
1. **China-friendliness is acceptable** — the site's audience is mixed; GA is
   completely blocked in mainland China, while CF's beacon generally loads
   (occasionally slow). Undercounting in CN is a known, accepted trade-off.
1. **Privacy-preserving by default** — no cookies, no personal data, no banner
   (consistent with the site's existing privacy-lean choices).

### Known limitations (accepted)

- **Mainland China reachability** of `static.cloudflareinsights.com` is not
  guaranteed → CN visits may be undercounted. Does not affect page rendering
  (beacon is async/non-blocking).
- **Ad blockers / Brave privacy mode** may block the beacon → undercount.
- The beacon **token is public by design** (it ships in client HTML) — it is
  not a credential; the same token is visible to every visitor.

## Registration (one-time, ~5 min)

1. Sign up / log in at [dash.cloudflare.com](https://dash.cloudflare.com)
   (free account is sufficient).

1. In the left sidebar: **Analytics & Logs → Web Analytics**.

1. Click **Add a site** and enter the hostname **`xiongjia.github.io`**.

   - Choose the free plan.
   - Since the site is *not* on Cloudflare DNS, Cloudflare will provide a
     JavaScript beacon snippet instead of proxying traffic.

1. Copy the generated beacon snippet. The current dashboard emits the
   `type='module'` form (module scripts are deferred by default, so no `defer`
   attribute is needed):

   ```html
   <!-- Cloudflare Web Analytics -->
   <script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "<YOUR_TOKEN>"}'></script>
   <!-- End Cloudflare Web Analytics -->
   ```

   (The dashboard may include extra flags such as `"spa": true` — not needed
   for this static site; the plain `token` form is enough.)

1. Optional dashboard settings worth enabling:

   - **Exclude your own visits** (set your IP) so your editing traffic doesn't
     pollute the stats.
   - Review the default **bot/spam filtering** settings.

## Configuration

### `mkdocs.yml` — token lives here

The token is config-driven via the standard `!ENV` mechanism (same pattern as
`SITE_NAME` / `GIT_HASH` already in use):

```yaml
extra:
  cf_analytics:
    enabled: true
    token: !ENV [CF_ANALYTICS_TOKEN, 'cd22530495334b6097e23e273034f4cd']
```

- `enabled: false` turns analytics off completely (templates render nothing).
- `token` falls back to the committed value; setting `CF_ANALYTICS_TOKEN`
  overrides it without a git commit (handy for token rotation). An **empty**
  `CF_ANALYTICS_TOKEN` (e.g. `CF_ANALYTICS_TOKEN='' uv run poe server`) makes
  mkdocs' `!ENV` resolve the token to null and disables the beacon entirely.
- The token is **public by design** (client-side beacon), so committing the
  fallback is safe.

### `overrides/partials/cf-analytics.html`

Shared Jinja fragment, included by both templates. Renders the beacon only when
`enabled` is true and a token is set:

```jinja
{% if config.extra.cf_analytics.enabled and config.extra.cf_analytics.token %}
  <!-- Cloudflare Web Analytics -->
  <script type='module'>
    ... loopback guard, then inject the beacon script ...
  </script>
  <!-- End Cloudflare Web Analytics -->
{% endif %}
```

**Dev-server exclusion (two layers):**

1. `poe server` / `server-prod` / `server-bucket` set `CF_ANALYTICS_TOKEN=""` in
   their env (pyproject.toml) → mkdocs `!ENV` resolves it to null → the
   dev-server HTML contains no beacon bytes at all.
1. Safety net for ad-hoc local serving (`mkdocs serve` run directly, or
   `python -m http.server` previewing `site/`): the partial's inline module
   script only injects the beacon when `location.hostname` is **not** a
   loopback/unspecified host (`localhost`, `127.0.0.1`, `0.0.0.0`, `::1`,
   `[::1]`). Anything else —
   including a LAN IP (e.g. opening the dev server from a phone) — is treated
   as a real visit (covered in practice by layer 1).

The dynamic injection works because the beacon reads its config via
`document.currentScript || document.querySelector('script[data-cf-beacon]')`;
with `type='module'` `currentScript` is null, so it DOM-scans and finds the
injected tag (attribute set before `appendChild`).

### `overrides/main.html`

Inside the existing `{% block extrahead %}`, right after `{{ super() }}`:

```jinja
{{ super() }}
{% include "partials/cf-analytics.html" %}
```

This covers **every normal page** (all pages use `main.html`).

### `overrides/404.html` (bonus coverage)

The 404 page extends `base.html` directly, so it does *not* inherit the
`extrahead` block from `main.html`. It gets its own `{% block extrahead %}`
override (calling `{{ super() }}` first, then the same include) so 404 traffic
is tracked too — useful for spotting dead links from the backlinks feature.

### Notes

- The `minify` plugin (`minify_html: true`) preserves script attributes during
  HTML minification — the snippet survives the production build as-is.
- **Not** added via `extra_javascript`: that mechanism cannot carry the
  `data-cf-beacon` attribute, and it would not cover the 404 page.

## Implementation (done 2026-08-05)

1. Got the beacon token from the dashboard (see Registration).
1. Added `extra.cf_analytics` (enabled + token with `!ENV` fallback) to `mkdocs.yml`.
1. Created `overrides/partials/cf-analytics.html` — conditional beacon fragment.
1. Included the partial in `overrides/main.html` (`extrahead`) and
   `overrides/404.html` (`extrahead` override).
1. Verified: build emits the beacon in `index.html` + `404.html`; `CF_ANALYTICS_TOKEN`
   env override changes the emitted token.
1. Commit → CI builds → GitHub Pages deploy (pending).

## Update (2026-08-16): exclude local dev server

Local `mkdocs serve` visits used to be recorded under the `localhost` hostname
in the dashboard, polluting the stats. Now excluded in two layers — mechanism
documented in the "Dev-server exclusion" note under the partial section above
(empty-token env in `poe server*` + client-side loopback guard).

Verified: `CF_ANALYTICS_TOKEN='' uv run poe build-drafts` (mirrors the
`poe server*` env) emits no beacon in `index.html`/`404.html`; plain
`uv run poe build` (no env override) still emits the beacon with the
mkdocs.yml default token.

## Testing

Local:

```bash
uv run poe server
# DevTools → Network → load a page
# Expect: NO request to https://static.cloudflareinsights.com/beacon.min.js
#         (server task forces an empty token — no beacon in the HTML at all)
```

To test the loopback guard itself (direct `mkdocs serve`, beacon present in
HTML but not injected at runtime):

```bash
uv run mkdocs serve          # or serve a built site locally
# DevTools → Console → location.hostname
# Expect: beacon.min.js NOT fetched on localhost / 127.0.0.1 / ::1
```

Production-style build (beacon must still be emitted):

```bash
uv run poe build
# grep -o 'data-cf-beacon' site/index.html → present
# Live verification happens on the deployed site (see below).
```

Final verification after a production deploy:

1. Push to `master` → CI deploys to GitHub Pages.
1. Visit the live site, reload a few pages.
1. Open the Cloudflare dashboard → Web Analytics → `xiongjia.github.io` →
   confirm visits appear (allow a few minutes for data to settle).

## Edge Cases

- **Beacon CDN failure / blocked**: page still renders fully — the script is
  `type='module'` (deferred by default) + non-blocking; worst case the visit is
  not counted.
- **Beacon now loads via JS injection**: the beacon fetch starts at parse
  completion (inline module runs, then injects) instead of at parse start.
  The view is still recorded — the beacon reads navigation timing at init —
  so the only cost is a sub-second skew for very fast bounces; accepted price
  of the loopback guard.
- **Local dev server** (`localhost` / `127.0.0.1` / `::1`): excluded twice —
  `poe server*` emits no beacon (empty token), and the client-side loopback
  guard skips injection for any other local serving. LAN-IP access to a dev
  server is counted as a real visit (a `poe server*` dev server never sends a
  beacon anyway; direct `mkdocs serve` on a LAN IP is the one gap, accepted).
- **Theme toggle / client-side navigation**: static site uses full page loads;
  no SPA handling needed (the optional `"spa": true` flag is unnecessary).
- **Privacy mode (Brave) / ad blockers**: beacon may not fire → undercount,
  accepted.
- **Own traffic**: mitigate by excluding the editor's IP in the dashboard.

## Dependencies

| Service                                                               | Usage                                     |
| --------------------------------------------------------------------- | ----------------------------------------- |
| [Cloudflare Web Analytics](https://www.cloudflare.com/web-analytics/) | Traffic analytics (free tier, cookieless) |
| `static.cloudflareinsights.com` (CF CDN)                              | Beacon script & payload endpoint          |

## References

- Cloudflare docs: [Web Analytics](https://developers.cloudflare.com/analytics/web-analytics/)
- [Get started guide](https://developers.cloudflare.com/analytics/web-analytics/get-started/) (beacon snippet flow for non-proxied sites)
