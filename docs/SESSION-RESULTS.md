# Self-stopping VM revision evidence — November 1, 2026

This supersedes the Cloud Run design in PR #3. Before revision the branch head was fea5afa2af2c75f0a489be5e71260258d4ac8fb9. Only the existing PR branch/source and description are updated; no merge or deployment is performed.

## What changed

- Scheduled non-Spot e2-small Compute Engine VM plan replaces Cloud Run/container/job inputs. Keep regional GCS full-MP4 staging, stable Drive IDs, checksum verification and recovery.
- Separate state and media buckets allow durable state retention while avoiding continued charges for soft-deleted temporary video; retention changes are proposals, not applied settings.
- Supervisor controls child process group and 5h30 runtime. Systemd templates add poweroff on every archive-service exit, 5h45 runtime, independent 5h50 boot watchdog, and a five-minute startup failure stop check. VM intent adds native six-hour GCE STOP and no automatic restart. No systemctl poweroff command was executed.
- Conservative GCS budget reservations enforce monthly work/download allowances, output/live-staging caps, backoff and five expensive VOD attempts. Remote reconciliation can still complete after a fifth ambiguous upload response. Full validated media and deduplication state survive errors.
- Root boot helper prepares two Secret Manager credentials in tmpfs with attached identity, no keys. Redacted Cloud Logging event writer and disabled error/absence/budget policy templates prepare alerts; no channels or policies are created.
- VM-DEPLOYMENT.md is the authoritative approval/install/runbook. Plan targets USD10 with a conservative USD9 model and normal estimated USD1–4 range; no hard invoice-cap claim.

## Verification executed locally

`python -m unittest discover -s tests -v`: **31 tests passed** on Python 3.12.14.

Actual local operations include FFmpeg synthetic H.264/AAC remux to one complete eight-second MP4 and ffprobe audio/video/duration checks; SQLite is no longer used. Actual supervised child processes tested successful exit, exit code 7, and a real timeout/termination. No cloud credentials or video download are used by these tests.

Other tests use fake cloud responses/stores to verify completion/owner/cutoff checks, fragment policy and truncation rejection, unchanged duplicate prevention/upload recovery, lease exclusion, monthly reservations and crash overcounting, UTC month rollover, corrupt ledger rejection, storage/download limits, five-attempt exponential backoff, stale staging warnings without deletion, file-size stop before write, final-attempt remote reconciliation, alert transport failure containment, VM/alert template gates, and static homepage/privacy/404/security checks. These do not validate actual GCP IAM, API schemas, generated services, billing or notification delivery.

`python -m compileall -q recorder` and `bash -n scripts/audit-deployment.sh` passed. Disabled worker invocation refused before cloud access. Disabled boot secret loader returned without credentials or network calls.

`systemd-analyze verify` was attempted on all five units but the sandbox returned `SO_PASSCRED failed: Operation not permitted`. Full unit validation and actual boot, secret loading, group termination under systemd, guest/native shutdown and ephemeral-IP release remain mandatory approved-VM checks. No host poweroff, service enablement, sudo operation or resource creation was tested.

Official native VM runtime-limit documentation was consulted: https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime . It documents maxRunDuration and STOP for standard VMs. Pricing sources from the preceding read-only review are cited with calculations in VM-DEPLOYMENT.md; no invoice or real transfer-speed measurement exists.

## Supplied VOD compatibility remains blocked

Owner confirmed microphone audio in VOD 2917078189 on MrHype420. The pinned yt-dlp 2026.10.26 Twitch extractor and native downloader/strict fragment options were inspected through GitHub in the preceding revision. The official Twitch metadata API is not assumed to be a VOD download endpoint.

Prior actual attempts: web open could not access the Twitch VOD; pip install failed through the configured proxy; `python -m recorder.check_vod --vod-id 2917078189` failed because yt-dlp was unavailable. No actual media, checksum or listening sample was retrieved from that VOD. This revision does not repeat those failures or relabel them as a successful download test. Public VOD test commands remain in RECORDING.md for an authorized environment.

## Explicitly not performed

No provisioning, service/billing API enablement, IAM grant, OAuth change, notification send, bucket/VM/Scheduler/budget/alert creation, deployment, Firebase enable variable change, DNS change or merge. No service-account key or credential value was created/read/exposed. No outbound Google Cloud identity or secrets are configured in this execution environment; the network remains restricted. Dependencies, real Twitch/Drive/GCS, root secret helper, actual service stop and cloud alert delivery remain unverified.

Existing homepage/privacy source checks passed; no emulator, browser visual or production check was repeated. Exact required approvals are listed in VM-DEPLOYMENT.md, including resources/install/IAM, retention/budget/alerts/channel, owner Drive/Twitch credentials, network access, controlled acceptance and later hourly enablement. No approval is inferred from the prior $10 budget or acknowledgment.
