# One-time Drive authorization on the owner's Mac

Owner reports the **existing Xbox Twitch Recorder Web client** in `xbox-twitch-recorder` is now **In production**, with drive.file, Drive/Picker APIs and localhost origin/callback already configured. Do not repeat that setup. No publishing, client creation, scope change, billing, merge, deployment or recording activation is part of this procedure. Existing app state is owner-reported, not an independent Console read.

## What to have ready

- The JSON downloaded from the **existing Web client**, kept locally. If already downloaded after the callback was saved, reuse it. Do not create a new client or use a service-account key. The file chooser accepts its current filename; no renaming/copying into source is needed.
- A Google Picker **API key** for that same project. API enabled and API key available are different prerequisites. Use the existing key if present; the helper cannot manufacture it or read it from the OAuth client JSON. It should be restricted to Picker and `http://localhost:8765/*`. Do not paste it into chat. The launcher asks for it with input hidden.
- The existing numeric **project number**, available in [project settings](https://console.cloud.google.com/iam-admin/settings?project=xbox-twitch-recorder). Do not enter the project ID or client ID. The helper does not guess it.
- Python 3 and GitHub CLI (`gh`) on the Mac. If missing and Homebrew is already installed, `brew install python gh` supplies them. No gcloud, ffmpeg, server, paid compute or persistent home computer is needed for one-time consent.

## Exact Terminal commands

The fresh temporary checkout avoids modifying an existing local checkout or merging PR #3. Inspect the PR before granting access. These commands run the PR source locally; they do not start any Actions workflow.

```sh
gh auth status >/dev/null 2>&1 || gh auth login --web --git-protocol https
xtr_auth_dir="$(mktemp -d "${TMPDIR:-/tmp}/xtr-auth.XXXXXX")"
gh repo clone coltonhavens/xbox-twitch-recorder "$xtr_auth_dir"
cd "$xtr_auth_dir"
gh pr checkout 3
bash scripts/authorize-drive-mac.sh
```

The launcher creates an isolated Python virtual environment and installs the pinned dependencies. It checks GitHub owner access before requesting Google consent. Select your existing client JSON in the Mac file dialog, enter the numeric project number, and enter the Picker API key when prompted (hidden). The browser opens automatically at `http://localhost:8765`.

Click **Authorize Google Drive**, sign in with the Google account that can upload into your archive folder, and select **1X9VfSes_byvkygreHfdvGNHzVXjvAYBG** in Picker. Other folder selections are rejected. Approve only the requested per-file scope. A fresh offline grant is requested; do not reuse a seven-day Testing-issued refresh configuration just because the app is now Production.

Success message: **Drive authorization saved as XTR_DRIVE_AUTH. Temporary setup copies removed. Recording remains disabled.** The helper creates/reuses one small recovery manifest in the existing folder and sends the refresh configuration plus manifest ID directly to the encrypted repository Actions secret using gh stdin. Refresh/client secrets are not printed, placed in command arguments, or passed through chat. It does not enable XTR_ARCHIVE_ENABLED, dispatch a workflow, merge, deploy, or change Google settings.

The downloaded source JSON remains where you selected it; private helper copies and the temporary Picker-key file are removed on success/error. No full VOD is downloaded during setup. The temporary checkout/venv can be deleted after success if desired. Never delete the OAuth client, recovery manifest or Drive archives as part of local-file cleanup. Your computer can be turned off afterward; eventual recording uses GitHub Actions, subject to separate activation approval.

## Security and verification boundaries

Local checks require Web type, exact existing project ID, callback, any supplied origin list, complete client fields, and Google's expected OAuth endpoints. The client's human-readable name is not in standard downloaded JSON; choose the correct existing named client yourself. No API call is made to inspect or edit Google Cloud settings.

Loopback-only listener, Host/Origin checks, state, PKCE, session cookie, nonce CSRF check, no-store/origin-only referrer headers, callback-log suppression, exact scope/folder checks, exclusive mode0600 temporary files, fifteen-minute consent deadline and bounded requests remain in force. The short-lived access token goes only to local Google Picker; refresh/client secrets remain server-side. GitHub owner permission is checked before consent. A gh failure never prints its captured token-related output. Actual browser integration, owner account consent, refresh and Drive writes cannot be certified by offline mocks; confirm the real success message, not merely a passing unit test.

Authorization may be revoked or expire later for normal Google reasons; Production does not guarantee a permanent token. If Google returns extra scopes or a restricted account blocks the grant, stop rather than adding broad Drive permissions. Existing Drive sharing settings apply; no permissions/sharing are changed.

Do not delete/overwrite the recovery manifest: it stores stable archive IDs. Reauthorization with the same client/folder reuses it; multiple manifests fail closed for review. This setup verifies folder write capability and creates/reuses metadata; it does not claim that VOD2917078189 or a full media upload has been tested.

## Portable advanced alternative

For non-Mac environments, the underlying helper still accepts explicit private files:

```sh
python -m recorder.authorize_drive \
  --client-file /path/to/existing-client.json \
  --picker-key-file /path/to/private-picker-key.txt \
  --project-number YOUR_NUMERIC_PROJECT_NUMBER \
  --github-secret --open-browser
```

`--output work/drive-auth.json` instead creates a new mode0600 configuration file for a secure manual secret upload; it never overwrites one. Do not store credentials in an Actions variable, issue, artifact, cache or repository file.

Sources: [Drive per-file scope](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [Google Picker](https://developers.google.com/workspace/drive/api/guides/picker), [OAuth web flow](https://developers.google.com/identity/protocols/oauth2/web-server), [refresh-token lifetime](https://developers.google.com/identity/protocols/oauth2#expiration).
