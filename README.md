# Xbox Twitch Recorder

Find completed saved Twitch broadcasts from **MrHype420**, stream each full video with available microphone/game audio into **one MP4**, and upload it to the owner's existing Google Drive folder. Runs on scheduled standard **GitHub Actions** runners; no home computer, VM, Cloud Run, GCS or Firebase deployment is required for recording.

**Prepared in PR #3, not activated.** Drive authorization and actual source-to-Drive acceptance are pending. The owner confirmed microphone audio in VOD 2917078189; this environment's attempted Twitch download was blocked by network policy. No success is claimed for that VOD.

- [Existing OAuth app production readiness](docs/OAUTH-PRODUCTION.md)
- [Browser-only Drive connection and required hosting approval](docs/DRIVE-AUTHORIZATION.md)
- [Recorder behavior, runner limits and recovery](docs/RECORDING.md)
- [Actual test results and limits](docs/SESSION-RESULTS.md)

No Homebrew, Python or GitHub CLI is required on the owner’s Mac. The browser connection UI and secure server-side GitHub-secret handoff are prepared under `broker/`. A static page cannot safely replace that trusted backend; approve temporary free hosting before expecting a live link. Nothing has been deployed or connected. Development test instructions are in the recording docs, not owner setup requirements.

The workflow is `.github/workflows/archive-vods.yml`, gated off unless XTR_ARCHIVE_ENABLED=true on main in this public repository. This work does not set that variable, merge, dispatch or activate any workflow. Credentials belong only in the encrypted Actions secret XTR_DRIVE_AUTH; no service-account keys or public credential files.

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

The website is independent of recording. Do not create another project, reinitialize Hosting, change DNS, or modify OAuth settings without the owner’s separate approval. Never commit tokens, secrets, service-account keys, or private recordings. Future backend credentials must stay outside `public/` and source control.

