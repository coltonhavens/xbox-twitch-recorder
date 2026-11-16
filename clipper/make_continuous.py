#!/usr/bin/env python3
"""Continuous-gameplay clip: one unbroken window of the stream, nothing cut out.
Talking parts play at normal speed. Stretches with no talking are fast-forwarded
(2x for short gaps, 4x for long ones) so the viewer can still follow the gameplay.
plan = {"vod","words","a","b","title","moods":[[src_from,src_to,mood]],"fix":{},"out","tmp"}"""
import json, os, subprocess, sys
plan = json.load(open(sys.argv[1]))
A, B = plan["a"], plan["b"]; fix = plan.get("fix", {})
W = [w for w in plan["words"] if A <= w["s"] < B]
HOLD = 0.5 if not plan.get("realtime") else 1e9                                       # stay at 1x this long around speech

# build speed map: list of (src_a, src_b, speed)
spans, t = [], A
talk = []
for w in W:
    s, e = max(A, w["s"] - HOLD), min(B, w["e"] + HOLD)
    if talk and s <= talk[-1][1]:
        talk[-1][1] = max(talk[-1][1], e)
    else:
        talk.append([s, e])
for s, e in talk:
    if s > t:
        gap = s - t
        spans.append((t, s, 1.0 if gap < 3 else (2.0 if gap < 8 else 4.0)))
    spans.append((s, e, 1.0)); t = e
if t < B:
    gap = B - t; spans.append((t, B, 1.0 if gap < 3 else (2.0 if gap < 8 else 4.0)))
if plan.get("realtime"):
    spans = [(A, B, 1.0)]                            # gameplay clips: always real time, even with no talking
# merge neighbours with the same speed
merged = []
for sp in spans:
    if merged and merged[-1][2] == sp[2] and abs(merged[-1][1] - sp[0]) < 1e-3:
        merged[-1] = (merged[-1][0], sp[1], sp[2])
    else:
        merged.append(sp)

files, words, moods, out_t = [], [], [], 0.0
def mood_at(x):
    for lo, hi, m in plan["moods"]:
        if lo <= x < hi:
            return m
    return "calm"
for i, (a, b, sp) in enumerate(merged):
    d = b - a; od = d / sp
    vf = f"fps=30,scale=1280:720,setpts=PTS/{sp}" if sp != 1 else "fps=30,scale=1280:720"
    af = (f"atempo=2.0," * (2 if sp == 4 else 1) if sp != 1 else "") + f"afade=t=in:d=0.02,afade=t=out:st={max(0,od-0.02):.3f}:d=0.02"
    if sp != 1:
        af = "volume=0.6," + af
    f = f"{plan['tmp']}_{i}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", plan["vod"], "-vf", vf, "-af", af,
                    "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", f], check=True)
    files.append(f)
    for w in W:
        if a <= w["s"] < b:
            txt = fix.get(w["w"], w["w"])
            if txt.strip("-") == "":
                continue
            words.append({"w": txt, "s": round(out_t + (w["s"] - a) / sp, 2), "e": round(out_t + (w["e"] - a) / sp, 2)})
    # mood follows the source timeline
    step = 0.5
    x = a
    while x < b:
        y = min(b, x + step)
        m = mood_at(x)
        o0, o1 = out_t + (x - a) / sp, out_t + (y - a) / sp
        if moods and moods[-1][2] == m and abs(moods[-1][1] - o0) < 1e-3:
            moods[-1][1] = round(o1, 3)
        else:
            moods.append([round(o0, 3), round(o1, 3), m])
        x = y
    out_t += od

lst = plan["tmp"] + ".txt"
open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
src = plan["tmp"] + "_cont.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", src], check=True)
spec = {"src": src, "start": 0, "end": round(out_t, 2), "title": plan["title"], "words": words, "moods": moods, "out": plan["out"]}
json.dump(spec, open(plan["tmp"] + "_render.json", "w"))
subprocess.run(["python3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_clip.py"), plan["tmp"] + "_render.json"], check=True)
fast = sum((b - a) for a, b, s in merged if s != 1)
print(f"{plan['out']}  source {B-A:.0f}s -> {out_t:.1f}s  (fast-forwarded {fast:.0f}s of no-talk gameplay)")
