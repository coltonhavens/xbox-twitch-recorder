# Xbox Twitch Recorder

Phase 1 is a public, static application website and privacy policy for a personal project. **Recording automation is planned, not operational.** There is no login, OAuth flow, Twitch download process, Drive upload, or backend in this implementation.

The goal is to detect the owner's completed Xbox Twitch broadcasts and archive available VODs (including audio present in the source) to the owner's Google Drive, with future processing in the cloud. Missing or muted audio cannot be recovered; Twitch VOD availability and Drive capacity apply.

## Website

- `public/index.html`: responsive dark gaming homepage and clearly labeled concept workflow.
- `public/privacy.html`: public policy at `/privacy`, covering current Hosting data and planned API, OAuth, file, token, retention, and revocation behavior.
- `public/styles.css`, `public/icon.svg`: local assets; no remote dependencies, JavaScript, tracking, analytics, or application browser storage.
- `public/404.html`: missing-page response.
- `firebase.json`: serves only `public/`, enables clean URLs and explicit response headers. Unknown routes remain 404; no SPA fallback.
- `.firebaserc`: selects the **existing** `xbox-twitch-recorder` project.

The policy does not assert the existing application's OAuth scopes have been verified. Revisit the policy and security design before enabling any automation.

## Local preview

Use Node.js 22 LTS and the Firebase CLI (v15.14.0 used for local verification):

```sh
npm install --global firebase-tools@15.14.0
firebase emulators:start --only hosting --project xbox-twitch-recorder
```

Open `http://127.0.0.1:5000/` and `http://127.0.0.1:5000/privacy`. No build is required. Stop with Ctrl+C. The CLI may try optional cloud lookups; public static Hosting emulation does not require application OAuth secrets.

## Deployment

See [deployment instructions](docs/DEPLOYMENT.md) and the [verification checklist](docs/VERIFICATION.md). Deployment is a separate step; this source does not imply that production has been updated.

## Project boundaries

- Repository: https://github.com/coltonhavens/xbox-twitch-recorder
- Existing Google Cloud / Firebase project: `xbox-twitch-recorder`
- Existing Hosting site: `xbox-twitch-recorder` (`https://xbox-twitch-recorder.web.app`)
- Connected custom domain: https://xbox.mrhype420.com
- Intended destination folder ID: `1X9VfSes_byvkygreHfdvGNHzVXjvAYBG` (identifier only, not authorization; not exposed in the public site)

Do not create another project, run a new Hosting initialization over this configuration, change DNS, or modify OAuth credentials for this phase. Never commit tokens, secrets, service-account keys, or private recordings. Future backend credentials must stay outside `public/` and source control.
