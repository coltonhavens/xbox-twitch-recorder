# Verification checklist

## Source and local Hosting checks

- [ ] Homepage and `/privacy` return 200 in Firebase Hosting emulator.
- [ ] `/privacy.html` redirects to clean `/privacy`; `/privacy/` normalizes without trailing slash.
- [ ] Unknown routes return the custom 404, not the homepage.
- [ ] Local stylesheet and SVG load; security headers match `firebase.json`.
- [ ] Homepage-to-policy and policy-to-home links work, including direct `/privacy` entry.
- [ ] At mobile (360px) and desktop widths, text and controls fit without horizontal scrolling.
- [ ] Keyboard focus is visible; skip link works; headings and landmarks are readable.
- [ ] No external font, script, analytics, tracker, account form, or OAuth request is present.
- [ ] Planned automation is labeled throughout; no guarantee of complete audio or capture.
- [ ] Policy distinguishes current site practices from intended backend handling and unspecified retention/security details.
- [ ] No secrets or private files are tracked; only `public/` will deploy.

## Production (only after authorized deployment)

- [ ] Custom domain homepage and privacy page return the reviewed content over HTTPS.
- [ ] Firebase `web.app` homepage and privacy page return the reviewed content over HTTPS.
- [ ] CSS, navigation, clean URL redirects, headers, custom 404, mobile layout, and keyboard navigation work live.
- [ ] Existing DNS and OAuth credentials remain untouched.
- [ ] Record deployment release, reviewer, verification date, and any remaining issues.

Local results and verification limitations are recorded in `docs/LOCAL-RESULTS.md`. Unchecked items here are tasks to verify, not claims of completed checks.
