# One-time owner Drive authorization

This is the only account authorization needed by the public-VOD recorder. No VM, Cloud Run, GCS, service-account key, Google Cloud IAM grant or Twitch app secret is required. Nothing below has been applied. The helper writes the Drive credential secret only when the owner explicitly runs it; it does not enable recording, change workflow variables, merge or deploy.

Current setup (owner-reported): External app in Testing; owner is a test user; Drive and Picker enabled; localhost origin/callback saved. Preserve those settings. No Google Cloud identity is connected for independent inspection. [Production-readiness preparation](OAUTH-PRODUCTION.md) separates non-sensitive scope rules, branding/personal-use review, seven-day Testing tokens, and the owner’s later publication decision. Nothing is published or changed automatically.

## Owner steps

1. In the existing Google project, check that **Google Drive API** and **Google Picker API** are enabled. These are API access prerequisites, not a request for paid compute/storage. Review any existing client first. Use a **Web application OAuth client** in that same project with authorized JavaScript origin `http://localhost:8765` and exact redirect URI `http://localhost:8765/callback`. Declare only `https://www.googleapis.com/auth/drive.file`. Do not request broad `drive` or `drive.readonly` access. Any client/consent settings changes require the owner's action; the helper cannot make them.
2. For persistent unattended refresh, use an appropriate Production consent configuration (or eligible Internal app). An External app left in Testing can issue refresh tokens that expire after seven days for this scope. Review the consent audience/publishing and existing grant rather than assuming a token lasts indefinitely. The owner signs in with the Google account that owns or can upload into folder **1X9VfSes_byvkygreHfdvGNHzVXjvAYBG**. Do not change that folder's sharing settings automatically.
3. Save the approved OAuth Web client JSON locally as `work/oauth-client.json`. Save a Google Picker API key as `work/picker-key.txt`, restricted to the Picker API and HTTP referrers `http://localhost:8765/*`. Use the same project's numeric project number for Picker. These local files are ignored by git; keep them private and never paste them into chat, PRs, logs or workflow variables. The browser key is used only for the local Picker; it is not needed by the scheduled recorder.
4. On a trusted computer **once**, install Python dependencies and sign into GitHub CLI with permission to set secrets on `coltonhavens/xbox-twitch-recorder`. Run from the reviewed checkout:

```sh
python -m pip install -r recorder/requirements.txt
python -m recorder.authorize_drive \
  --client-file work/oauth-client.json \
  --picker-key-file work/picker-key.txt \
  --project-number YOUR_NUMERIC_PROJECT_NUMBER \
  --github-secret
```

Open `http://localhost:8765`, consent to the per-file scope, and select **the exact existing archive folder** in Google Picker. The helper rejects a different folder and verifies it is writable. It creates or reuses the app's small recovery manifest in that folder and sends the OAuth refresh configuration plus manifest ID to GitHub **Actions secret `XTR_DRIVE_AUTH`**, through `gh secret set` stdin. No token is printed or passed in a command argument. Your computer is needed only for this one-time browser consent; it need not stay on for recordings.

Alternatively, use `--output work/drive-auth.json` instead of `--github-secret` to create a new mode-0600 credential file, then set the repository secret through GitHub's secure secret UI or `gh secret set XTR_DRIVE_AUTH --repo coltonhavens/xbox-twitch-recorder < work/drive-auth.json`. Never commit the file. Do not use an Actions variable, issue, artifact, cache or repository file for credentials. Delete temporary local copies when no longer needed, without deleting the OAuth client or Drive recovery manifest.

Successful setup leaves automation disabled. No manual token copying, service-account key, SSH server or deployed OAuth website is needed.

## What the helper protects, and what is still unverified

Loopback-only listener, Host and Origin validation, random state, PKCE, a session cookie, nonce-based CSRF check, no-store/origin-only referrer headers, no callback logging, strict scope/folder checks, exclusive mode-0600 file creation, and bounded session lifetime. Refresh/client secrets remain server-side; only the short-lived access token is supplied to Google's Picker in the local browser. The existing folder and new files inherit the owner's Drive sharing policy; no assumption of privacy is made from the folder ID alone.

The server uses the standard Google OAuth library. The code and offline PKCE/scope/persistence tests are prepared; actual consent, Picker rendering, folder grant, refresh and upload still require the owner account. No authorization is claimed before those succeed. If the existing client has a different type or unrelated scopes, inspect and approve the appropriate client setup rather than silently broadening access.

The recovery manifest is an app-created Drive file, not public repository state. Do not delete or manually overwrite it: it preserves stable Drive IDs. Reauthorizing with the same OAuth client and folder reuses the existing manifest; multiple matching manifests fail closed for owner review. Restoring a lost manifest or changing OAuth clients requires a migration/reconciliation review to prevent duplicates.

Sources: [Drive per-file scope](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [Google Picker](https://developers.google.com/workspace/drive/api/guides/picker), [OAuth web-server authorization](https://developers.google.com/identity/protocols/oauth2/web-server), [refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration).
