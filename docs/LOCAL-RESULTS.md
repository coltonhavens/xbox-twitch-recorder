# Local verification results

Verified November 1, 2026, against the Firebase Hosting emulator (Firebase CLI 15.14.0, Node.js 24.19.0 in the coding environment). The deployment guide recommends Node.js 22 LTS.

## Passed

- `GET /`, `/privacy`, `/styles.css`, and `/icon.svg`: HTTP 200.
- `/privacy.html` and `/privacy/`: HTTP 301 with `Location: /privacy`.
- Unknown path: HTTP 404 with the custom “Wrong checkpoint” page.
- Responses contain configured CSP and `X-Content-Type-Options: nosniff`.
- Chromium: homepage and policy at 360, 390, 768, and 1440 CSS pixel widths, without horizontal overflow or JavaScript page errors.
- Keyboard skip links move focus to the main landmark on both pages.
- Browser navigation from homepage to policy and back succeeds.
- Source audit: local page links resolve; no forms, scripts, iframes, remote assets, analytics, or tracking dependencies.
- Project/site IDs and clean URL configuration match the requested existing Firebase resources.
- `git diff --check` passes.

Screenshots were inspected locally; mobile and desktop layouts were checked. Scratch tools and screenshots are excluded from source control.

## Limits

No production deployment was performed. Live custom-domain and `web.app` homepage/policy verification remains pending authorized deployment. No Google/Firebase CLI login, application OAuth credentials, scopes, DNS configuration, or Drive contents were accessed or modified. The unauthenticated emulator emitted optional cloud configuration lookup warnings; this static website uses no Firebase client SDK and served correctly without that configuration.

These checks are not an OAuth verification approval, a backend security audit, or a claim that future recording automation works.
