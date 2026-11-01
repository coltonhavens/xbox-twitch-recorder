# Scheduled Twitch VOD → Google Drive archive

Status: draft source, NOT deployed or operational. Channel: **MrHype420**. Destination: `1X9VfSes_byvkygreHfdvGNHzVXjvAYBG`. The owner confirmed microphone audio in VOD **2917078189**; this is owner-provided evidence for that VOD, not an independent listening test or a guarantee for every future broadcast.

## Scheduled self-stopping VM architecture

Cloud Scheduler starts a non-Spot **e2-small Compute Engine VM** hourly. A boot service runs the VOD archive, then powers off on success, no work or failure. Independent supervisor/systemd/guest/native Compute Engine limits stop a hung execution. No always-on recording server or Cloud Run job is proposed. The pipeline remains saved Twitch VOD → full audio/video MP4 → private regional GCS staging → owner Google Drive, with durable state and duplicate prevention.

Use two private same-region Standard buckets: small durable state and temporary media with separately reviewed retention. No full video needs to fit on the 20 GiB standard boot disk. Keep service code immutable/root-owned, credentials in Secret Manager loaded to tmpfs, no application inbound ports, no reserved static IP/NAT and no service-account keys.

**Authoritative VM installation, safeguards, alert templates, cost model and exact approvals:** [VM-DEPLOYMENT.md](VM-DEPLOYMENT.md). Review-only inputs: deploy/vm-intent.json, deploy/systemd/*, deploy/alerts/* and deploy/archive.env.example. The Cloud Run Dockerfile/job intent was removed. Source defaults are disabled and nothing is installed or provisioned.

## Detection and completion rules

Helix Get Users resolves MrHype420 to an immutable numeric user ID each execution. Get Streams tests whether the owner is offline; Get Videos paginates `type=archive` results. The implementation scans all available pages up to 10,000 entries, failing rather than silently truncating beyond the cap. It ignores highlights/clips, other owners, and video creation times earlier than the explicitly chosen `ARCHIVE_SINCE` cutoff. Select that cutoff before enabling; use an earlier date to include the supplied test VOD if needed. No ID or creation timestamp has been invented for the supplied video.

For a new VOD, persist its duration, observe it unchanged on another execution at least ten minutes later, require owner offline, then require yt-dlp's matching owner, VOD ID, known `is_live=false`, and matching duration. Helix does not expose a definitive finalized/download-ready flag; these are conservative completion heuristics, not a Twitch completion guarantee. Growing or processing metadata defers work rather than marking success. API errors fail the job; 401, 429 and transient API failures retry on the next schedule. API tokens are acquired freshly for each job, so no expired-token loop across executions. Two-phase staging already validated can finish uploading while the owner is live again.

The cutoff is an intentional first-run backfill control, not a substitute for durable deduplication. Keep state records indefinitely unless explicitly migrating them. A saved VOD may expire or be removed before successful staging; alert on failed executions and resolve quickly. Nothing can recover audio or video Twitch no longer provides.

## Download compatibility, full video and audio

The official [Get Videos API](https://dev.twitch.tv/docs/api/reference/#get-videos) supplies metadata, not a general VOD video-file download endpoint. The worker uses **yt-dlp 2026.10.26**'s [TwitchVodIE](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/extractor/twitch.py): playback metadata/token requests and HLS extraction. This is a maintained third-party extractor using Twitch playback interfaces; its presence was verified in that pinned release, but the supplied VOD's actual extraction is **not yet verified**. Twitch can change those interfaces or restrict access. Do not claim official API download support.

The downloader explicitly selects yt-dlp’s native HLS downloader so fragment retry/failure settings apply, then selects a full combined video+audio rendition, requests the whole VOD with no time range, retries fragments, and aborts on an unavailable fragment instead of silently skipping it. FFmpeg copies the streams, explicitly converts ADTS AAC framing for MP4, and produces a single fragmented MP4 without transcoding or splitting. This is one playable file, not separate archive segments. Fragmented MP4 supports a non-seekable output stream; Google Drive preview support must be checked separately from normal-player compatibility. No claim of preview support is made.

Source and FFmpeg must both exit successfully, an audio and a video stream are mandatory, and FFmpeg must report completion and duration within 0.5–5 seconds of expected duration (strict absolute maximum five seconds, not a percentage that loses minutes on long streams). Bytes and MD5 are computed during staging. This rejects truncation and missing tracks; it cannot prove that all speech or every source frame is present. The owner-confirmed VOD microphone should be preserved if present in the selected source audio. Muted portions and absent broadcast audio cannot be restored. Check future Xbox/VOD audio settings and listen to the final test copy.

A long stream is not constrained by local disk size. Transfers must fit the 5h30 worker supervisor and outer six-hour **VM** limit; download need not run at playback speed. If measurement shows a full transfer exceeds that timeout, review all runtime, lease and cost limits or a resumable fragment-download design before enabling for those workloads. Do not repeatedly bill a job that cannot finish. Five TB/file and user upload/storage quotas can still prevent a one-file upload; this worker fails and retains staging rather than silently splitting or reducing quality.

## Durable retries and duplicate prevention

A global generation-conditioned GCS state-bucket lease serializes scheduled executions. Per-VOD JSON stores stable observations, a **preallocated Drive file ID**, validated staging generation/size/MD5, and completion. The ID is persisted before create; expected checksum is persisted before any Drive upload. Retries query that same ID. A successful upload followed by a timeout or process crash is recognized and verified on the next run rather than creating a second file. Drive display names alone are never used for deduplication.

Uploads use seekable, generation-pinned GCS range reads through the Google Drive client, resumable 8 MiB chunks, request timeouts, and exponential request retries. Within an attempt, client retries can resume transfer. After process death, a not-yet-committed upload may restart from the staged object with the same preallocated ID; persistent resumable session URLs are deliberately not stored as bearer secrets. No second Twitch download is needed once validated media metadata is saved. A crash before that save can re-download and overwrite orphan staging on the next attempt.

Remote file must match expected MD5, size, destination parent, VOD ID and channel appProperties, and must not be trashed. Save completion durably before deleting the pinned staging generation; cleanup itself is idempotent after a crash. A mismatching or deleted remote archive needs operator review; a journaled completion is not continually reconciled against user deletion. No auto-restore or auto-delete in Drive, no sharing changes. Corrupted/missing state is an incident: do not clear it and rerun blindly, since its preallocated IDs enforce deduplication.

## Costs, limits and account approvals

Owner budget: **USD10/month maximum planned spending**. Normal planning range approximately **$1–$4/month**, with a conservative allowance model of **$9 including contingency**, described in [VM-DEPLOYMENT.md](VM-DEPLOYMENT.md). This is not a guaranteed invoice cap. No free-tier credits are required by the upper plan. Unlike the previous Cloud Run proposal, the chosen VM-to-Drive route has an explicit free-transfer statement in [official network pricing](https://cloud.google.com/vpc/network-pricing#vm-to-google-service). Same-region staging/VM traffic is also free; storage, operations, VM/IP runtime, disk and alerts still apply.

Implemented allowances: 120 reserved work hours and 250 GiB new staging per UTC month, 40 GiB maximum file, 100 GiB live temporary staging, five expensive attempts/VOD with exponential hourly backoff. Crashed attempts retain conservative reservations. Full validated media survives failed Drive uploads. Runtime, storage or attempt exhaustion alerts and pauses for review; the worker does not discard pending recordings or silently downgrade quality. Stage soft delete must be separately approved disabled for the planned storage bound; state remains in its own protected bucket.

Remaining account grants: existing Twitch app client credentials for public metadata, owner Google offline drive.file authorization plus app-specific access to the existing folder, and scoped GCP worker/Scheduler identities. No Twitch broadcaster-user OAuth is needed for the initial public VOD path; restricted playback requires separate owner approval, not a bypass. The secure Drive consent/Picker bootstrap still needs implementation against the actual existing OAuth client configuration; no permission or settings change is performed by this PR. See [the exact approval list](VM-DEPLOYMENT.md#exactly-what-still-requires-approval), including resource/IAM/retention/alerts/budget/controlled-test approvals and launch blockers.

## Safe verification and rollout

Offline: `python -m unittest discover -s tests -v` with FFmpeg/ffprobe. These tests need no API credentials.

After approved network access and installing requirements, metadata-only playback compatibility test (no Drive/cloud write):

```sh
python -m recorder.check_vod --vod-id 2917078189
```

Authorized full video/audio test to an adequately sized scratch disk (no upload):

```sh
python -m recorder.check_vod --vod-id 2917078189 --output work/MrHype420-2917078189.mp4
```

That command uses exclusive creation, does not overwrite files, and checks full-file duration plus audio/video presence. Failed downloads may leave a partial local file; inspect/remove it before retry. Never use a partial test file as proof of success. It is an explicit test tool, not the production home-computer dependency.

After explicit provisioning/installation and owner consent approvals: validate one controlled VM boot with only VOD 2917078189 selected, real Drive checksum/parent/audio checks, duplicate rerun and interruption recovery. Verify actual guest/native stop and ephemeral-IP release, seeded absence metric and notification delivery, long-VOD RAM/runtime and costs. Enable hourly scheduling only after separate approval. The systemd service powers off its host on exit: never start it in a development environment. No cloud, account, alert or paid API is created by the worker. Details: [VM-DEPLOYMENT.md](VM-DEPLOYMENT.md).
