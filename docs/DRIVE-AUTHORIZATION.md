# Browser-only Drive connection — prepared, not deployed

**No Homebrew, Python or GitHub CLI is required on the owner's Mac.** The Mac launcher was removed. The intended owner experience is: open the approved HTTPS connection link → sign into Google → select the existing folder → approve access. No live link exists until the owner approves a trusted backend deployment. Do not pretend a repository URL or static homepage can already receive the refresh authorization.

Existing owner-reported setup is retained: Web OAuth client Xbox Twitch Recorder in project xbox-twitch-recorder, In production, drive.file, Drive/Picker enabled, localhost entries saved. No repeated publishing, duplicate client, broader Drive permission, Google billing or paid recording infrastructure is needed. The recorder itself still runs through inactive scheduled GitHub Actions, separately from this one-time setup service.

## Why a trusted backend is necessary

Google's [authorization code model](https://developers.google.com/identity/oauth2/web/guides/use-code-model) exchanges a code for access/refresh tokens **on the backend**. A static website can request a short-lived access token but cannot safely hold the existing Web client secret or a credential permitted to write GitHub Actions secrets. Public repository code, browser localStorage, URL fragments/query parameters, workflow inputs, logs or artifacts are not safe substitutes for a server-side receiver. Actions does not provide a public OAuth callback listener.

The prepared broker uses **popup mode**: Google's code arrives in a JS callback and is sent in an HTTPS POST body, not an application URL. Origin/custom-CSRF-header and Secure HttpOnly SameSite cookies bind it to a ten-minute session. The backend exchanges the code with Google's fixed token endpoint, checks exactly drive.file plus a refresh token, and verifies the signed-in owner's email via [Drive about.get](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get), which accepts drive.file. No extra email/openid/Gmail scope is added. The configured owner email is private setup configuration, not inferred or printed.

Only a short-lived access token reaches Picker in browser memory. The owner selects folder **1X9VfSes_byvkygreHfdvGNHzVXjvAYBG**, which must be writable. The server reuses or creates the same small recovery manifest and seals the refresh configuration with the target repository's public key using libsodium/PyNaCl before writing **XTR_DRIVE_AUTH**. GitHub receives `encrypted_value` and `key_id` over HTTPS; plaintext tokens never enter repo files. This follows [GitHub's encrypted-secret API](https://docs.github.com/en/rest/actions/secrets#create-or-update-a-repository-secret).

The server removes completed/expired in-memory sessions, rejects code replay and unknown owners, bounds session starts, never logs request bodies/query paths/token exceptions, and does not store refresh tokens on its filesystem. Final GitHub failure can retry the existing in-memory payload without re-creating the manifest. Browser responses contain neither refresh token, client secret nor GitHub token. Existing Drive sharing settings still apply; no sharing change is made.

## Simplest no-paid-hosting alternative to local software

Proposed: a **temporary Render Free web service**, used only for owner connection, then removed. [Official free-service documentation](https://render.com/docs/free) supports Python web services and managed TLS; 750 free service-hours are shared per workspace. Free services sleep after 15 idle minutes and can restart, so an interrupted setup must start again. This is a short personal setup session, not the long-running recorder or a production availability promise.

Require the Free instance type, no paid disk/database/add-on, and **no payment method**. Render documents suspension rather than paid bandwidth/build overages without a payment method. Confirm account eligibility and dashboard pricing before deployment; if a paid plan/card is required, stop for owner review rather than upgrade. No Render service/account connection has been created here. No deploy button, auto-deploy manifest or executable provisioning command is supplied to bypass approval.

A browser-only connection cannot be delivered with **no hosting/trusted backend at all** under these security requirements. The prepared free temporary broker is the alternative; moving the old localhost callback to a remote machine alone would not solve the origin and secret-handoff problems.

## Prepared implementation and later operator setup

Source: `broker/server.py`, `broker/static/*`, `broker/requirements.txt`, `broker/runtime.env.example`. Disabled by default with BROKER_ENABLED unset/false. No source or file contains real credentials. A future approved service would use Python3.12, build `pip install -r broker/requirements.txt`, and start `python -m broker.server` from the repository root. These are operator reference values, **not commands the Mac owner must run** and not actions performed in this PR.

Following explicit hosting approval, operator setup needs the owner-authorized provider connection and private runtime values:

- Exact new HTTPS broker origin. Add it to **the existing** Web client's authorized JavaScript origins, preserving localhost and all existing callbacks. Google popup code exchange uses this origin; no replacement client or redirect endpoint is needed. This settings update needs owner approval. The existing downloaded client JSON must include that approved origin; do not fabricate it as if the Console had changed.
- Existing Google Web client JSON/client secret, same-project numeric project number and Picker key via the provider's private environment dashboard, never repository files or chat. Add the approved HTTPS referrer to the existing Picker key restriction, preserving existing values. No scope/publishing change is requested.
- Owner's primary Google account email for the allowlist; not guessed from repository name or support fields.
- A short-lived **fine-grained GitHub token** selected only for coltonhavens/xbox-twitch-recorder with repository **Secrets: read/write** (and automatic Metadata read). No Contents write, workflow, Actions execution, administration or org access is needed. GitHub scopes cannot restrict this token to one secret name: the permission covers repository secrets, although this code targets only XTR_DRIVE_AUTH. Treat the backend as trusted, expire/revoke the token promptly after setup, and remove the service/private runtime credentials after success. Do not paste this token into chat. Existing connector access cannot currently perform this secret write for the owner.

The broker checks immutable repository/owner IDs and public-key access before the owner grants Google access. It never dispatches a workflow, changes XTR_ARCHIVE_ENABLED, merges a PR, modifies IAM/billing, or publishes the Google app. Finishing a session locks that running broker process against another connection; deleting the temporary service and revoking its short-lived GitHub token are still required cleanup. A provider restart resets process memory and requires a new session, not a persistent credential database.

If Google does not return offline refresh authorization, the broker refuses rather than silently saving an access-only token. An existing/incomplete grant may need owner-reviewed fresh consent; do not automatically revoke a working grant. Actual Google popup/Picker, hosted-origin approval, proxy headers/cookies and end-to-end secret write must be verified after approved deployment; offline tests cannot prove those account/provider integrations.

## Only next owner decision

**Approve or decline temporary Render Free authorization hosting, without a payment method or paid plan.** No live URL can be given honestly before that approval and provider access. If approved, remaining provider/OAuth-origin/GitHub-credential approvals must happen through their secure browser dashboards; none require installing local software. Do not send credentials in this chat. Recording remains a separate, disabled workflow and is not activated by setup.
