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

## Personality clips — APPROVED by Colton Nov 21 ("yes this is good")
At least 2 of the 5 daily clips are personality moments: rants, roasts/trash talk, hype, laughing fits, sarcasm.
Personality beats skill for growth. ONE complete moment per clip: the setup on screen (what happened) + his
reaction + the payoff line at the end (e.g. bot_pistol_rant: dies to a bot's pistol → rant → "I'm so good, I'm the
best"). Never stitch single lines from different moments (Colton rejected that: "it has nothing in it").
Use `type: "talk"` (silences fast-forward), word timings from **medium.en** (small.en hallucinates on game audio),
moods following the moment (shocked → rage → laugh). Sarcastic "I'm so good" after losing counts as personality.
Saved candidates: 2930265100 2096–2132 sarcastic "I'm so good" after 12th place; 2935372195 ~5624–5640 "trying to
kill those bots huh, what are you trying to prove"; 2934307253 ~2310–2320 "go play a real game"; 2934307253 ~1022
"killed me with a pistol… dog water".
**If plans already exist for the date (added by hand), make only enough to reach 5 total.**

## Colton's favorites (use as the bar)
- **2026-11-19_rooftop_sniper_quad** ("Four downs from one roof, sniper QUAD", posted Nov 21 4 PM): "really good, love
  that clip". One spot, one continuous fight, four confirmed sniper downs building to a QUAD, real time, callouts.
- **bot_pistol_rant** (personality): "yes this is good".

## Full-game video format — APPROVED by Colton Nov 25 (20-kill win, VOD 2939971395, ~719–1601 s)
For a big game (personal best, 15+ kills, a win): 1) hook = the end screen (show the WHOLE stats screen, letterboxed,
so the kill count is readable) + his reaction line ("I have 20 kills, that's my personal best"); 2) a short
montage of the best 3–4 shots right after the hook; 3) his drop/landing talk (where to go, where the money is); 4)
EVERY kill in the order it happened, none skipped, ~4 s each (shot → down), with a counter (big yellow number + 'DOWNS' label, top-left of the gameplay square) that goes up on each down; get to the first kill fast (cut from 'where do y'all want to go' + the spots straight to the drop + money talk, then kill 1); 5) after every 3 kills, one of his lines
(callouts, laughing, trash talk); 6) end on the last kill + VICTORY. ~3 min. Show Colton the first 30 s before
rendering the rest. Builder used: clipper/examples_full_game_2939971395.py. Kill times = banner OCR at 4 fps.
Colton wants 10+ short clips cut from this game later (not done yet).

## The stranger test (Colton, Nov 25) — applies to EVERY clip
Only his voice is on the stream audio (teammates/randoms/enemies are not recorded). So:
- **Skip moments that only work as a two-sided conversation** (he answers someone we can't hear, asks a question
  and waits, reacts to a teammate's line). Exception: there's a cool kill in it — then it's a gameplay clip.
- **Keep** good-looking gameplay (multi-kills, clean snipes, wins) and **his lines that make sense to a stranger who
  wasn't on his team** — a rant, a roast, a reaction, a tip, a callout that explains itself.
- **Setup line** (Colton approved Nov 25): when his line needs a few words of context, add `"setup": "a bot just
pistoled me..."` to the plan (short, plain words, under ~6 words). It shows in yellow under the headline for the first
2.2 s, then his captions take over. Never put words in his mouth: the setup states what happened on screen.
- Test before picking: "If I scrolled past this with no context, would I get it in the first 2 seconds?" If no, skip.
- Colton rated the Nov 26 samples (tip, recap, sniper replay, business talk) 4–5/10: missing other voices made
  half-conversations fall flat. Prefer self-contained lines + strong gameplay.

## Old streams (Twitch deletes VODs after ~7 days) — Nov 26
`twitch_fetch.py window` falls back to the recorder's Drive copy `Xbox Game Recordings/MrHype420-<vod>.mp4`
(byte-range jump, ~25 s per clip) when Twitch no longer has the VOD. That fallback only works inside GitHub Actions
(it needs XTR_DRIVE_AUTH), so: plans for expired VODs still RENDER fine, but this session can't preview/transcribe
them. For backlog picks from expired VODs, rely on the saved transcripts + ledger notes, and keep windows generous.

## Breathing room (Colton, Nov 26: "too close to the action… jerky… I can't see what's going on")
Every kill/shot cut: start at least **1 s before the FIRST bullet** (not before the down banner — the down shows
~0.5–1 s after the shot) and end **1.5–2 s after the down**. Find the first bullet from the magazine count dropping
(crop 960,600 → 110x40, read at 6 fps). Never cut mid-recoil or on the banner frame. Full-game videos: ~4–5 s per kill.
Montages: same lead-in; fewer kills is better than jerky kills.

## Meme reactions — ON (Colton approved the corner style + timing, Nov 26)
Gameplay keeps playing in the center; the meme pops up SMALL in the top-left of the gameplay for ~1.8 s:
- hit (headshot / clean one-shot down): smoking cartoon (kit/k6) + "SMOKED" + chime (music/satisfying.wav)
- clear miss (sniper fires, mag count drops, no down within 2 s): blank-stare cartoon (kit/k8) + "BRO" + sad trombone
  (music/embarrassed.wav)
Add to a clip plan as `"memes": [{"t": <VOD seconds>, "kind": "smoked"|"bro"}]` (render_plan → make_continuous →
render_clip map the time, draw the meme and mix the sound). Pop the meme ~0.1 s after the down banner (SMOKED) or
~0.3 s after the missed shot (BRO). Use in kill-streak and sniper clips, about 1 in 3 clips, max 2 memes per clip;
only on a confirmed headshot/one-shot down or a confirmed miss (mag count drop, no down within 2 s).
## Caption colors (who is talking) — Colton, Nov 21
Every caption word carries `spk`: `me` (Colton: white, current word yellow), `team` (teammates: blue + small
TEAMMATE label), `enemy` (proximity chat: red + ENEMY label), `callout` (DOWN!/HEADSHOT! words we add: like `me`,
but they don't move the avatar's mouth). Default is `me`. Mark `team`/`enemy` only when it's clear from the
conversation who said it (answers to his questions, callouts about him, enemy trash talk on proximity). The voice
score (`kit/colton_voice.npy`, resemblyzer) is a hint only: game audio makes it unreliable. Unsure → leave `me`.

## Daily montage — ON for a 1-week test (Colton, Nov 21: "I like them all, let's run them for the next week")
Every night: 5 clips (≥2 personality) + **1 montage, 10–15 s** = 6 plans. The Mac poster has a 6th slot at 21:00.
Rotate the montage style by day: Mon/Thu triple-kill (kill-to-kill, `trap_slow_1`, each triple from ONE fight),
Tue/Fri sniper one-shot downs (confirmed downs, not finishers), Wed/Sat sniper headshot downs if the pool has 4+
unused (else one-shot), Sun best kills of the week. Captions/callouts on every kill. Title says what it is.
Name montage plans `5_<style>_montage.json`.
## (montage details)
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
  out right before, 808 hit on the down; NO zoom punch (it blurred the shot, Colton Nov 26)). `phonk_1` is too fast for this. Only cleared, commercial-use
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

## Kill montages v2 (Colton, Nov 26 night) — overrides the beat-synced montage rules above
- **No music.** Game audio only (`"music": false` plan, `make_montage.py no_music`). No zoom punch.
- Each shot plays in **real time**: ~2.4 s before the down (you see the shot), ~2 s after.
- **Never cut inside a run.** If he hits several shots in a row in one fight (plates breaking, a down, then another down), play the whole run as ONE unbroken piece. A run like that is worth more than separate scene-to-scene kills, so build montages around runs first. Hits within ~6 s of each other are merged automatically; for longer runs set the kill's "post" to cover it.
- **Sound bite about every 3 kills,** and it must come from a real fight on the montage's topic: him reacting to his own shot or talking trash to the enemy he just hit (e.g. "That's right... Clip that shot, dude"). Never lobby/pre-game talk, never a line about something else. Put it on that kill with "words" + a longer "post" so it plays straight through.
- Rough length 20-35 s.
- **Headline must match what's in the video (Colton Nov 26).** If the kills come from different games, the headline says it's a montage ("SNIPER MONTAGE", "HEADSHOT MONTAGE", "TRIPLE KILL MONTAGE"). Never a headline like "Five shots, FIVE DOWNS" that makes a viewer expect one game; save that kind for an unbroken run from ONE game.

## Personality in EVERY clip (Colton Nov 26 — top rule, overrides any older "2 of 5" rule)
"I'm not really that good. Personality is what makes me stand out."
- Every clip and every montage must have Colton's own voice in it: reacting to his shot, talking trash to the enemy, hyping, roasting himself, a funny line. A silent kill, however clean, is never a clip by itself.
- Pick moments by personality first, skill second. A messy fight with a great line beats a clean kill with no talking.
- Gameplay clips: include his reaction after the kill (let it play), with captions.
- Montages: a real-fight sound bite at least every 3 kills (more is better), plus silent kills only in between those.
- Still apply the stranger test: the line must make sense to someone who doesn't know him and wasn't in the party.

## THE GOAL of every edit (Colton Nov 26, after seeing the v2 clips)
"This type of editing is just better. Makes me feel like I'm watching the stream or shows what it's like playing the game with me, which is what we want."
- Edit like a viewer is sitting next to him: real time, his voice, unbroken runs, no music, no flashy effects.
- When in doubt, cut less, not more. Approved examples: 2026-11-27_two_downs_two_sit_downs, 2026-11-27_trash_talk_then_missed_easy_shots, 2026-11-27_zip_line_team_wipe, the no-music SNIPER MONTAGE.
- Stream quality: blocky scope shots are in the source (720p ~2.8 Mbps). Colton was told to raise the Xbox stream to 1080p / up to 6000 kbps; check a new stream's bitrate with ffprobe and report if it is still low.

## Second chances: repost low-view clips up to 5 times (Colton Nov 26)
"With them getting 4 or 6 views we don't know if it can get views." Every clip gets up to 5 tries to reach ~200 views.
- **Who qualifies:** a @mrhype4208 post that has been live 48 h+ and has fewer than 5 likes (GHL gives no per-video views; under 5 likes is the stand-in for under ~200 views). Skip the old-account weekly repeats.
- **How to find them:** GHL `social-media-posting_get-posts` (location 3GWBlKHTxotVFwehqNhh, TikTok account 6afa6587056a1e58e0327c12_3GWBlKHTxotVFwehqNhh_00083BtNWTFcRuTnAYcyj9g3Bcb26fW4Brs_business, type published, last 10 days), read `insights.like`. Match a post to its plan by the media file name (`2026-11-24-throwing-knife-then-headshot.mp4` = plan `2026-11-24_throwing_knife_then_headshot`), stripping any `_r2`..`_r5` suffix.
- **Never repost the identical file** (TikTok shows duplicates to almost nobody). Each try is a fresh cut from the same plan: copy the plan to `clipper/plans/<today>/r_<orig>_r<N>.json` with `"name": "<orig>_r<N>"` and change at least: a new headline (different words/angle), a new opening (start 1-3 s later so the first second is the action or his line, or add/change the setup line), and a new caption. Keep every other rule (his voice, real time, breathing room).
- **How many:** at most 2 reposts a night; they count toward the 5 daily clips (so 3 new + 2 reposts). Oldest/lowest first.
- **Track tries** in ledger.json under `"reposts": {"<orig name>": {"tries": N, "last": "YYYY-MM-DD", "likes": [..]}}` (the original post is try 1). Stop at 5 tries, or as soon as any version gets 5+ likes.
- Reposts are the one exception to "never re-clip a moment".
