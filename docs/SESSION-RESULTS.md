# GitHub Actions simplification evidence — November 1, 2026

This supersedes the VM/Cloud Run design in PR #3. Prior head a22fa47ab13c0b6391916c640ecd510cc387f753. Only the existing PR branch/source and description are updated; no merge, activation, permission/configuration change or deployment is performed.

## Current implementation

- One scheduled GitHub Actions workflow discovers completed MrHype420 ARCHIVE VODs and streams combined video/audio through yt-dlp + FFmpeg into one Drive MP4 using bounded buffering. The recording path requires no paid infrastructure, Firebase deployment, Google IAM, VM, GCS, Cloud Run or always-on personal computer.
- Removed VM runtime/supervisor/secret-loader/cloud-alert/budget inputs and obsolete tests/docs. Kept unrelated static website, Hosting configuration/workflow and Hosting WIF documentation intact. Recording does not depend on them.
- Drive-only recovery manifest stores preallocated file IDs and expected full-file size/MD5 before final upload commit. Retries query acknowledged offsets and reconcile uncertain final success without duplicate IDs. No full local video, media artifacts, credential cache or repository state branch.
- Implemented one-time loopback OAuth PKCE/state/cookie/CSRF + Picker folder grant helper, exact drive.file scope, narrow folder validation and secure stdin-based GitHub secret storage. No actual OAuth client modification, login, consent, secret write or Drive file creation was performed. Browser/Google account integration remains unverified.

## Runner and source inspection

Repository metadata independently reported **public**. Official GitHub documentation confirms standard public runners free independently of included private compute usage, Ubuntu 4CPU/16GB RAM/14GB SSD specifications, six-hour job maximum, scheduler delay/drop behavior and 60-day public inactivity disablement. Sources linked in RECORDING.md. Actual owner billing balances/private plan are not inspected or assumed; job refuses private repository execution. Proposed cron every two hours at minute17; main-only enable-variable gate remains unset by this work.

Pinned yt-dlp 2026.10.26 TwitchVodIE/TwitchVideosIE and native HLS/strict-fragment options were inspected. Channel discovery is a public ARCHIVE playlist, not an assumed official VOD-download API. The playlist extractor has historical TODO notes, so source-level support is not treated as tested channel compatibility. Worker additionally checks selected media HLS ENDLIST and stable duration before capture. Account-restricted extraction is not implemented and must not bypass Twitch access restrictions.

## Dependencies and actual offline tests

Pinned dependencies were **successfully installed** in an isolated work directory using authorized package-network access. Installation initially found a real version conflict: google-auth-oauthlib1.2.3 requires google-auth<2.42. The requirements now pin compatible google-auth2.41.1; the complete installation succeeded. No service was enabled or billed cloud resource created.

`python -m unittest discover -s tests -v`: **26 tests passed**, using the installed dependencies through the isolated PYTHONPATH.

Actual FFmpeg test generated eight seconds H.264 video + AAC sine audio, ran the production pipe/remux path, streamed through a fake Drive session, then ffprobe verified one full-duration MP4 with video/audio. The process temporary directory was removed after exit. No Twitch video or actual Drive upload was used by this synthetic test.

Other tests verify multiple chunk ranges, expected size/MD5 persisted before completion, final source truncation withholding commit, partial acknowledgements, status query after timeout, final ambiguous success, conflicting completed files, preallocated ID saved before create, stable-duration scans, explicit ENDLIST requirement, paused expensive attempts, unfinished-video deferral, mode0600/exclusive credential files, stdin-only secret write, installed OAuth library's state/PKCE without client-secret exposure, trusted session-host/redirect checks, workflow permissions/gates/no artifacts, and static website links/security. Cloud HTTP/API/secret-write behavior is simulated; no browser consent or real API write is claimed.

Python compilation passed. Disabled worker exits before reading credentials. No Actions run was dispatched, and no main-branch changes were made by this work. New workflow has no PR/push trigger and stays guarded by XTR_ARCHIVE_ENABLED even after a future merge.

## VOD 2917078189 — actual attempt, not a successful test

The owner confirmed microphone audio in this saved VOD. yt-dlp2026.10.26 was installed and public metadata extraction was attempted with socket/request limits. It raised DownloadError and identified a proxy/HTTP403 denial. The supported environment policy does not permit Twitch playback/API destinations; no bypass was attempted. The prepared command `python -m recorder.check_vod --vod-id 2917078189` was then run with the installed yt-dlp on PATH and failed with sanitized CalledProcessError. No source bytes, selected playlist, complete VOD, microphone listening sample, checksum or Drive copy was obtained.

Dependency installation and synthetic media success therefore do **not** verify actual Twitch VOD download compatibility. Actual public channel pagination and final Drive file/audio/duplicate-rerun/interruption checks remain acceptance tasks in an authorized network/account environment. No extra Twitch user login/cookies are requested by this public implementation.

## Remaining ownership boundary

Owner must perform only the Google Drive authorization setup detailed in DRIVE-AUTHORIZATION.md to provide the app's folder grant, long-lived refresh configuration and recovery-manifest ID through Actions secret XTR_DRIVE_AUTH. The one-time local helper is not an ongoing computer dependency. Google client/API/consent changes, actual owner consent and secret creation were not performed. No credentials were exposed, notifications sent, paid services enabled, permissions granted, workflows activated, deployments run or PR merged. Existing website files were preserved with copy updated to the current inactive recording plan; no emulator/browser/production revalidation is claimed.

## Drive connection preparation follow-up

Owner reports the existing Web client now has the correct localhost origin/callback saved. No Google Cloud outbound identity is connected, so the app publishing status is **unknown**, not inferred as Testing or Production. No client, consent, publishing or test-user settings were read or changed. Next owner read-only check: Google Auth Platform → Audience → Publishing status.

Additional offline tests passed: a real loopback helper HTTP server with dummy credentials rejects an invalid Host, incorrect callback state/session and cross-origin completion POST, sets no-store/HttpOnly/origin-only referrer protections and never exposes the dummy client secret. No request reached Google and no authorization output was created. Fake Drive tests verify manifest reuse rather than duplication, access-token omission, and rejection of missing refresh tokens/broader scopes **before any Drive request or file creation**. The authorization helper now validates those credentials before touching the folder/manifest. Actual Picker/Google consent/refresh/upload remains owner-account acceptance, not an offline test result.

## Branding and Testing-to-Production preparation

Owner now reports External/Testing, existing owner test user, APIs enabled and saved localhost settings. This supersedes the earlier unknown-status note as an owner report, not independent Console access. No connected GCP identity is available to inspect actual Branding or identify confirmed missing fields. Official Drive/branding/refresh-token documentation was reviewed: drive.file is non-sensitive; sensitive/restricted scope verification and security assessment are not required for that scope. Basic branding requirements are separate and Google documents a personal-use exception. No blanket verified/production-approved claim is made.

Prepared OAUTH-PRODUCTION.md with the existing homepage/policy values, authorized root domain, unknown contact fields, verified-vs-owner-reported boundaries, live-URL checks and explicit no-publish/no-deploy limits. Updated existing pages in place to reflect the current inactive implementation, exact drive.file request, Picker, encrypted Actions authorization, Drive manifest, actual planned retention and Google Limited Use commitment. No duplicate website/client/page was created. Both existing HTTPS URLs were attempted via the web tool but inaccessible there; live hosting/deployment/HTTP status is not established. Local source and permission-boundary tests are rerun for this revision. No publishing, scope change, permissions, DNS, billing, deployment, activation or merge performed.
