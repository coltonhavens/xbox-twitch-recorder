# Revised VOD archive evidence — November 1, 2026

This supersedes the initial PR's live-recording design/results. The always-on worker, systemd service template, segmented archive output and SQLite journal were replaced by scheduled completed-VOD processing, one-file MP4 staging, Cloud Storage state/lease and owner-Drive upload. Nothing is deployed or enabled.

## Repository and compatibility inspection

- PR #3 was open/draft at head bfa7e8ceb1d39c9027f7abbc5f3098adc4a003f5 before revision; the changes update that branch, not main.
- Channel is MrHype420 and destination folder is the owner's existing 1X9VfSes_byvkygreHfdvGNHzVXjvAYBG. Owner confirmed microphone audio in VOD 2917078189. No independent listening claim is made.
- GitHub release API returned yt-dlp **2026.10.26**, published 2026-10-26. Read the pinned release's Twitch extractor: https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/extractor/twitch.py . TwitchVodIE matches `/videos/<id>` and uses metadata/token requests plus Twitch HLS extraction. Pinned options.py also defines the strict-fragment and HLS-MPEGTS options; downloader selection source was inspected and native HLS selection made explicit so the fragment policy is not delegated to a generic FFmpeg download. This is source-level support, not a successful VOD download test.
- Official Get Videos documentation provides metadata with app/user token authorization, not a general VOD download URL API. https://dev.twitch.tv/docs/api/reference/#get-videos . Cloud Run, Scheduler and Storage pricing were read through the web tool; formulas/sources are in RECORDING.md. No price guarantee or free-egress assumption.

## Tests actually executed

`python -m unittest discover -s tests -v`: **15 passed** on Python 3.12.14 with installed FFmpeg/ffprobe.

- Stable-duration observations, offline gating, cutoff, owner and archive-type filters.
- Extractor ID/owner/completion/duration validation; full-video/audio selection and strict fragment failure configuration.
- Duration validation rejecting truncated output.
- Failed upload retains validated staging; retry does not re-download.
- Ambiguous Drive success followed by restart reuses one persisted ID, verifies remote completion, and does not upload again; subsequent completed run is a no-op.
- Conflicting remote metadata is rejected with no completion or staging deletion.
- Simulated GCS generation-conditioned lease rejects overlap; stale holder cannot delete a replacement lease; expired worker cannot proceed.
- Homepage/privacy/404 local link checks and Hosting scope/security checks.
- **Actual FFmpeg test:** generated eight seconds of H.264 video and AAC audio, remuxed via the same non-seekable-output command as production, and ffprobe verified one MP4, both audio/video tracks, and full duration. This initially failed due to AAC framing; adding the AAC ADTS-to-ASC bitstream filter fixed it. No audio transcoding is used by the worker.

`python -m compileall -q recorder` and `bash -n scripts/audit-deployment.sh` passed. Disabled invocation refuses execution before accessing credentials/cloud. The cloud/API portions of the tests use fakes; no actual GCS generation precondition, Drive upload, Scheduler trigger, container build or OAuth flow has been tested.

## Supplied VOD test: blocked, NOT passed

- Web-tool open of https://www.twitch.tv/videos/2917078189 returned “not accessible via this tool.” This says nothing definitive about whether Twitch itself still serves the VOD.
- yt-dlp package installation attempted through the configured proxy failed: connection to proxy port 8080 was denied/unavailable. The initial attempted package version could not be resolved; it was not treated as a compatibility result. The PR now pins the release verified through GitHub, 2026.10.26.
- `python -m recorder.check_vod --vod-id 2917078189` was actually invoked and failed with `FileNotFoundError: yt-dlp`. No metadata, media bytes, full-file checksum, or playback sample was retrieved from that VOD. The implementation includes metadata-only and full-file no-upload test commands for the authorized environment.
- Managed network policy is enforced and does not include Twitch playback/API/CDN or Google API destinations. No outbound GCP identity or secrets are configured. No proxy bypass, cookie extraction, account login, paid-resource creation or token exposure was attempted.

## Not changed / remaining launch verification

No merge, Firebase deployment, FIREBASE_DEPLOY_ENABLED change, paid API enablement, IAM grant, cloud resource, credential key or OAuth permission change. Existing Hosting workflow and WIF intent/audit are preserved. Earlier GitHub observation that main was unprotected remains a hardening item, not a new settings change. GitHub environment/variable configuration remains unverified through the available connector.

Before unattended operation: restore permitted test access; install/build pinned dependencies; run actual full VOD test; inspect existing OAuth client and implement secure folder selection/consent bootstrap; obtain the exact owner grants listed in RECORDING.md; approve job/bucket/secrets/scheduler/monitoring cost and IAM plan; then test actual Drive final checksum/parent/audio, duplicate rerun, network/auth/quota errors, killed-job recovery and a long VOD. Homepage/privacy have source checks only; emulator, browser visual and production checks remain pending. Actual transfer throughput, RAM use, Google Drive preview behavior and network charge classification remain unknown.
