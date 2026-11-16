#!/usr/bin/env python3
"""Render one clip from a plan file (the daily Claude run writes these; GitHub Actions renders them).

plan JSON:
{ "vod": "2929897580", "start": 4521.2, "end": 4590.7,        # VOD seconds, one continuous moment
  "title": "Trying my absolute hardest\\nagainst BOTS",
  "meaning": "one sentence: what this clip is about",
  "type": "gameplay" | "talk",        # gameplay = always real time; talk = no-talk gaps fast-forwarded
  "words": [{"w","s","e"}],           # VOD seconds (small.en word timings)
  "fix": {"wrong": "right"},
  "moods": [[from, to, "calm|rage|shocked|sad|laugh"]],     # VOD seconds
  "name": "2026-11-16_tryhard_vs_bots" }
usage: render_plan.py PLAN.json OUTDIR   -> OUTDIR/<name>.mp4 (TikTok-ready, ~3 Mbps)"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
plan = json.load(open(sys.argv[1])); outdir = sys.argv[2]
os.makedirs(outdir, exist_ok=True)
S, E = float(plan["start"]), float(plan["end"])
with tempfile.TemporaryDirectory() as d:
    win = os.path.join(d, "window.mp4")
    subprocess.run(["python3", os.path.join(HERE, "twitch_fetch.py"), "window", str(plan["vod"]), str(S), str(E), win], check=True)
    cont = {
        "vod": win, "a": 0.0, "b": E - S, "title": plan["title"], "fix": plan.get("fix", {}),
        "realtime": plan.get("type", "gameplay") == "gameplay",
        "words": [{"w": w["w"], "s": round(w["s"] - S, 2), "e": round(w["e"] - S, 2)} for w in plan["words"] if S <= w["s"] < E],
        "moods": [[lo - S, hi - S, m] for lo, hi, m in plan["moods"]],
        "out": os.path.join(d, "full.mp4"), "tmp": os.path.join(d, "c"),
    }
    json.dump(cont, open(os.path.join(d, "cont.json"), "w"))
    subprocess.run(["python3", os.path.join(HERE, "make_continuous.py"), os.path.join(d, "cont.json")], check=True)
    final = os.path.join(outdir, plan["name"] + ".mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cont["out"], "-c:v", "libx264", "-preset", "medium", "-crf", "24",
                    "-maxrate", "4M", "-bufsize", "8M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", final], check=True)
print("rendered", final, os.path.getsize(final))
