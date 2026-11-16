# MrHype420 daily clipper — runbook for the daily Claude run

Goal: **5 new vertical Call of Duty clips per day** from Colton's Twitch streams (twitch.tv/mrhype420),
saved to Google Drive → stream archive folder → `Daily Clips/<date>/`. Not posted anywhere yet.

Division of work:
- **You (the daily Claude run):** find moments, check them, write 5 plan files, push them to the `clipper` branch.
- **GitHub Actions (`render-clips.yml`, runs on that push):** downloads only those stream windows, renders, uploads to Drive.

## Setup each run
```
pip install --break-system-packages -q faster-whisper yt-dlp numpy pillow
cd <repo>/clipper
```
`ledger.json` = what's already transcribed and clipped. Never clip the same seconds twice.

## 1. Pick streams
`python3 twitch_fetch.py list` → newest first. Skip a stream that is still live (`audio` prints `"live": true`).
Work newest unprocessed streams first, then the backlog, until you have 5 good clips.
Transcribe each new stream once: `python3 preview.py transcribe VOD transcripts/VOD.json` and record it in the ledger.

## 2. Find moments in the transcript
Look for one continuous stretch (usually 45–90 s, can be 20–40 s for a pure rant) with:
- **One clear meaning you can say in one sentence** ("trying my hardest against bots and still getting wrecked").
  If you can't, skip it.
- **What he says matches what's on screen.**
- **A payoff at the end** — best line, the down, the death after the brag. Clip ends right on it.
- If he says **"clip that"**, the 30–60 s before it is a candidate automatically.

Formats that work (from the top-50 CoD TikTok study): encounter stories (one fight / one player, setup → payoff),
relatable rants, reactions to new game content. ~60/40 personality to skill.

## 3. Check every candidate before planning it
`python3 preview.py window VOD START END /tmp/cand1` → accurate word timings + `sheet.jpg`.
**Look at sheet.jpg.** Confirm the gameplay is followable and matches the words. Tighten START/END so it opens
in the action and ends on the payoff.

## 4. Colton's rules (non-negotiable)
- **Continuous gameplay. No jump cuts inside a clip.** `type: "gameplay"` = real time throughout.
  `type: "talk"` only when the commentary is the point; no-talk gaps then play fast-forwarded, never cut.
- Full context: include the whole conversation around the moment, not a 15 s punchline.
- Captions sit under the headline, never over the gameplay (renderer already does this).
- **Highlights / snipe montages: only shots that DOWN the enemy** (read the kill banner "ENEMY DOWNED"/"ELIMINATION"
  with `down_check.py`), every shot a down, no misses. A hitmarker is not a good shot. For now: personality first.
- A clip where he plays badly needs a trending meme sound — there are no sound files yet, so **skip
  "I suck" clips** unless the commentary alone carries it.
- Don't reuse the same moment. Don't invent words — captions come from the transcript (fix obvious mishearings only).

## 5. Write the plan (one JSON per clip)
`plans/<YYYY-MM-DD>/<n>_<slug>.json` — format documented at the top of `render_plan.py`. All times are VOD seconds.
- `title`: 2 short lines, the meaning in plain words ("Trying my absolute hardest\nagainst BOTS").
- `moods` (MrHype420 face): calm, rage, shocked, sad, laugh — follow the moment.
- `name`: `<date>_<slug>`.

## 6. Push
Add the 5 plans + updated `ledger.json` + new transcripts in one commit to the `clipper` branch and push.
That push starts the render job. Then check the run: `Actions → Render daily MrHype420 clips to Drive`.
If GitHub access isn't available in the session, stop and report it — don't try other uploads.

## 7. Report (SendUserMessage)
For each clip: title, the one-sentence meaning, stream + timestamp, length. Plus the Drive folder.
