# Engineering evidence — November 1, 2026

## Independently observed

- GitHub repository ID 1442216654, owner ID 230064597, default branch main, admin/push access through connector.
- Main commit e4c2985888c11fa39e7d979117d1ab932578f12d contains merged PR #2 and the static site/deployment documentation.
- Workflow run https://github.com/coltonhavens/xbox-twitch-recorder/actions/runs/41353511592 concluded skipped. No deployment claimed.
- GitHub branch endpoint reports main protected=false. Branch review protection is a missing hardening item; no settings were changed.
- Deployment workflow restricts main, opts in only with FIREBASE_DEPLOY_ENABLED=true, uses firebase-production, job-scoped OIDC, pinned Actions and CLI, exact site/public directory, and verifies four live page responses after deployment.
- Existing provider condition in documentation already checks repository ID, owner ID, repository name, main ref, workflow_ref and environment subject. Added reviewable intent JSON and read-only audit; no WIF resource was created.

## Executed locally

`python -m unittest discover -s tests -v`: **9 tests passed** with Python 3.12.14 and installed FFmpeg/ffprobe.

1. Local homepage/privacy/404 links and assets resolve; no script tags.
2. Hosting public directory/site/security/clean URL settings checked; no SPA rewrite and no folder ID in policy.
3. Invalid video is quarantined without deleting its bytes.
4. Changed immutable chunk is rejected by journal.
5. Completed-upload restart does not call uploader again.
6. Remote verification requires size, MD5, SHA property and destination parent.
7. Failed upload retains bytes and reuses its durable Drive ID after reopening SQLite.
8. Publisher excludes the currently open last segment, then recovers it on finalization.
9. **Actual FFmpeg** generated four seconds of synthetic video plus sine-wave audio, remuxed it using the worker's stream-copy/segment settings, and ffprobe confirmed video and audio in at least three output segments.

`python -m compileall -q recorder` and `bash -n scripts/audit-deployment.sh` passed. Disabled worker invocation exited with `Recording disabled; explicit rollout required` before credentials/network access.

These tests use fake Drive responses, except for actual SQLite/filesystem/FFmpeg operations. They do not prove live Twitch or Drive compatibility, actual microphone speech, cloud durability, or gapless capture.

## Access and verification limits

Local checkout was stale (README-only initial commit); current source was retrieved through GitHub connector into an isolated working copy. Git fetch failed because the configured proxy was unreachable. No proxy bypass was attempted. No GCP outbound identity or secrets are configured; gcloud and Firebase CLI are absent. Network policy does not permit Google Cloud/Twitch/Drive/custom domain destinations. Dependency install was not attempted through a broken proxy. systemd-analyze verify failed with `SO_PASSCRED failed: Operation not permitted`; service runtime validation is pending.

No Firebase emulator or browser visual test was run in this session. Static source checks are not HTTP checks. Existing historical local results remain historical; they do not certify these edited pages. Homepage and privacy production responses, TLS, clean URL behavior, security headers, desktop/mobile rendering, and missing-route status remain pending emulator and approved deployment validation.

Environment branch restrictions and unset enable variable are owner-reported, not independently verified: connector lacks those settings APIs. No IAM, WIF, API enablement, secret, OAuth, billing, DNS, Hosting release, or deployment variable has been changed. No service account key was created or read.

## Remaining work and required owner input

- Connect an authorized Google Cloud identity for xbox-twitch-recorder and restore the managed environment's supported proxy/network access. Permit the specific GCP/Firebase/Twitch/Drive endpoints needed by the inspected configuration. No raw credentials in chat.
- Provide supported GitHub administration access, or run scripts/audit-deployment.sh in an already authorized environment and supply non-secret results. This verifies environment main-only rule, repository/environment variable precedence, Actions settings, branch/ruleset protection, SA roles/keys, project number and actual WIF state.
- Approve only the missing WIF/provider/SA impersonation binding after inspection. Dedicated Hosting SA needs only Hosting Admin, Service Usage Consumer; no SA recreation, extra broad roles, or keys.
- Approve first Hosting enable/deploy separately after page emulation and review. Main remains unchanged by this draft.
- Choose cloud region and a maximum monthly budget; approve proposed single non-Spot e2-small VM, 100 GiB persistent disk, outbound network, scoped worker IAM, secrets and monitoring. No cloud apply until a concrete priced plan is approved.
- Supply the owner's Twitch channel/login (to resolve immutable numeric ID) and approved app identity through secure configuration. Select/authorize the existing Drive folder through drive.file using the existing OAuth client. OAuth bootstrap/Picker UI is still missing and requires inspecting the existing client/consent settings before implementation and explicit approval before settings changes.
- Approve segmented TS archive output, or request a reviewed merge/remux addition. Production cannot be marked complete until worker dependency installation, actual Drive upload/revocation/retry, restart/disk/network/long-stream checks, monitoring, and short Xbox microphone test pass.
