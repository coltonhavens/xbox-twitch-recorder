# Firebase Hosting deployment

## Prerequisites and authorization

Review and merge the feature pull request, then check out the reviewed commit in `coltonhavens/xbox-twitch-recorder`. Use Node.js 22 LTS. An authorized Google account must have permission to deploy Hosting releases in the existing project (for example, Firebase Hosting Admin plus any required project/service access). This is Firebase CLI authorization, separate from the application's Google Drive OAuth consent. Do not provide application secrets, change OAuth credentials, create a project, or change DNS.

```sh
npm install --global firebase-tools@15.14.0
firebase login
firebase projects:list
firebase hosting:sites:list --project xbox-twitch-recorder
```

Confirm the project `xbox-twitch-recorder` and site `xbox-twitch-recorder` are visible. If access is denied, have the project owner grant appropriate access; do not select or create another project. `firebase login --no-localhost` is available when a local browser callback cannot be used. Never paste login credentials or tokens into issues, source files, or chat.

## Preview before deployment

```sh
firebase emulators:start --only hosting --project xbox-twitch-recorder
```

Check `/`, `/privacy`, `/privacy.html` (redirect to `/privacy`), `/styles.css`, and an unknown route on `http://127.0.0.1:5000`. Review desktop and mobile layouts and policy accuracy. Stop the emulator with Ctrl+C.

## Deploy the reviewed static files

From the repository root:

```sh
firebase deploy --only hosting --project xbox-twitch-recorder
```

`firebase.json` explicitly targets the existing site `xbox-twitch-recorder`. Only `public/` is uploaded. This creates a new Hosting release and replaces the site's current public files; review any existing live content first. It does not deploy Functions, recording jobs, rules, or OAuth changes. No DNS action is needed.

## Verify the actual live release

After the CLI reports success, verify **both** addresses and both routes:

```sh
curl -fsS https://xbox.mrhype420.com/ -o /tmp/xtr-home.html
curl -fsS https://xbox.mrhype420.com/privacy -o /tmp/xtr-privacy.html
curl -fsS https://xbox-twitch-recorder.web.app/ -o /tmp/xtr-firebase-home.html
curl -fsS https://xbox-twitch-recorder.web.app/privacy -o /tmp/xtr-firebase-privacy.html
curl -sSI https://xbox.mrhype420.com/privacy
```

Confirm the returned bodies show “Keep them.” and “Privacy policy”, the Phase 1 notice is present, links work, the stylesheet loads, and the configured CSP and other headers appear. Inspect the live pages on mobile and desktop and confirm an unknown URL gives a 404. Record the release and verification date. Do not report deployment complete based on source preparation or emulator success alone.

If necessary, roll back using the previous release in Firebase Console → Hosting → release history. Do not change DNS as a rollback procedure.

## OAuth application follow-up (outside this implementation)

The intended application URLs are homepage `https://xbox.mrhype420.com/` and policy `https://xbox.mrhype420.com/privacy`. An authorized owner can review these against the existing Google Auth Platform configuration after the pages are live. This work does not change that configuration, establish Google verification approval, or implement an OAuth callback. Before automation, finalize scopes, the existing-folder access flow, credentials handling, cloud storage, retry/cleanup behavior, retention, and an updated policy.


## Separate recording worker deployment

The static Hosting procedure above does not install the recorder. PR #3 proposes a scheduled self-stopping Compute Engine VM, separate state/staging buckets, and scoped owner OAuth. Review [VM-DEPLOYMENT.md](VM-DEPLOYMENT.md) for installation inputs, shutdown/watchdog limits, alerts, cost allowances and exact approvals. These resources and services remain unprovisioned and disabled.
