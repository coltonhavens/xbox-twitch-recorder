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


## Automatic clip triggers (always clip these, talking or not)
Scan the game HUD, not just the transcript:
- **"Clip it" / "clip that"** (Whisper often hears "flip that"): clip the 30–60 s before it. Transcribe the whole
  stream once with base.en **without** VAD too — the VAD pass misses lines over loud game audio.
- **Multi-kills:** 2+ different enemy names in the top-right "ENEMY DOWNED" banner within ~10 s = double, 3 = triple,
  4 = quad. Scan the banner (crop 1000,80 → 280x60 on 1280x720) at 1 fps, OCR only frames that changed, ignore
  "TEAMMATE DOWN/DEAD/REVIVED". Verify names on a banner contact sheet before trusting OCR. Multi-kill clips are
  `type: "gameplay"` (real time), start ~10 s before the first down, end on the last down or his reaction.
- **Assassinations / finishing moves** (getting behind someone): always a clip on their own.
- **Longshots:** always a clip. Run `medal_scan.py VOD '[down times]'` on every confirmed down; it reads the
  center medal/popup band, the kill banner and the weapon box for "LONGSHOT". Also catch him saying "long shot",
  "from way over there", "how far was that". Confirm on a contact sheet (popup visible) before clipping.
- **Throwing knife kills:** always a clip. (The XP popup reads "THROWING KNIFE ELIMINATION"; seen on 2930265100 at ~1369.) Same scan looks for "THROWING KNIFE" / "KNIFE"; also catch him saying
  "knife", "threw it", "tomahawk". Confirm by eye: the knife throw is on screen and the banner shows the down.
  Start ~5 s before the throw, end on the down or his reaction.
- **Headshot montages (later):** only shots the scorecard / popup confirms (HEADSHOT, ONE SHOT ONE KILL), no misses.
- Small.en without VAD hallucinates filler ("death", "five", repeated lines) on game audio — keep only real lines
  you can match to his voice; drop the rest rather than caption garbage.

## Colton's feedback (Nov 16)
- **Keep intros short:** start ~5 s before the first real action (the first shot / the down), not 15-20 s.
- **Every clip has on-screen captions.** If he doesn't talk, add short callout words at the moments that matter
  (e.g. "DOWN!" at each down, "DOUBLE KILL!" on the second) using the banner times.

## Caption colors (who is talking) — Colton, Nov 21
Every caption word carries `spk`: `me` (Colton: white, current word yellow), `team` (teammates: blue + small
TEAMMATE label), `enemy` (proximity chat: red + ENEMY label), `callout` (DOWN!/HEADSHOT! words we add: like `me`,
but they don't move the avatar's mouth). Default is `me`. Mark `team`/`enemy` only when it's clear from the
conversation who said it (answers to his questions, callouts about him, enemy trash talk on proximity). The voice
score (`kit/colton_voice.npy`, resemblyzer) is a hint only: game audio makes it unreliable. Unsure → leave `me`.

## Daily montage (1 per day, on top of the 5 clips) — Colton, Nov 21
Write one plan with `"type": "montage"` (format at the top of `make_montage.py`). Rendered by the same push.
- **Current style: sniper HEADSHOT montage, 30 s max.** Only downs where the XP popup next to the crosshair reads
  HEADSHOT ELIMINATION (it can show ~2 s after ENEMY DOWNED, under ONE SHOT ONE KILL / LONGSHOT) and the weapon is a sniper (`headshot_scan.py` → check each one on a frame). No misses, no hitmarker-only.
- **The headshot must be the shot that DOWNS him** (Colton, Nov 21). Finishing someone already on the ground with a
  headshot does NOT count. Test: read the magazine count (bottom right, crop 960,600 → 110x40). The HEADSHOT popup
  must come from the same shot as ENEMY DOWNED: if the mag count drops again between the down and the HEADSHOT popup,
  it was a finisher → reject. (Nov 21 check: 2 of 4 "headshots" were finishers.)
- **Make it look like one clip:** cut scope-to-scope on the shot, same color grade on every cut, prefer kills from
  the same map/session, and hide cuts in the recoil/flash.
- **Cut shot to shot:** each kill = the shot and the down; nothing between (no reloads, walking, menus).
  Use the exact banner time (make_montage refines it at 8 fps).
- **Team wipes in slow motion:** put the wipe's index in `"slowmo"`; it plays 0.4x over a whole bar, then the next
  headshot snaps back to full speed.
- **Music:** slow, spacious half-time track (`trap_slow_1`). Every down lands on a beat with its own drop (music cuts
  out right before, 808 hit + zoom punch on the down). `phonk_1` is too fast for this. Only cleared, commercial-use
  tracks in `music/` (the TikTok account is a business account: no popular copyrighted songs).
- Keep a pool: add every confirmed sniper headshot / wipe to `ledger.json` → `"headshots"` so later montages have
  material. Don't reuse a headshot in two montages within 2 weeks.
- Other styles (later, when Colton asks): triple-kill fights kept whole (same fight, not stitched from different
  fights), squad wipes, every kill from last night, top 5 of the week, reaction first.

## Brother hello pool (Colton, Nov 21) — for the "me and my brother every morning" montage
Every stream where **Havens07** is in the squad list (bottom left, crop 20,590 → 280x120): find the moment he joins /
the first minute you two talk, and save the hello (2–4 s, both voices if audible, word timings from medium.en) to
`ledger.json` → `"brother_hellos"` as {vod, a, b, words}. Don't clip it on its own. When the pool has 5+ different
days, build one 10–15 s montage: one hello per day, back to back, day label on each ("MON", "TUE"...), short.
Nov 18 (2932398326) has his side only: "Oh buddy" 2.5–4.6, "Hey buddy" 45.4–46.6. Havens07's voice may not be on the
stream audio at all (party chat not captured): if a hello has only Colton, keep it but flag it.

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
