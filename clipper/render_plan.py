#!/usr/bin/env python3
"""Render one clip from a plan file (the daily Claude run writes these; GitHub Actions renders them).

plan JSON:
{ "vod": "2929897580", "start": 4521.2, "end": 4590.7,        # VOD seconds, one continuous moment
  "title": "Trying my absolute hardest\\nagainst BOTS",
  "meaning": "one sentence: what this clip is about",
  "type": "gameplay" | "talk",        # gameplay = always real time; talk = no-talk gaps fast-forwarded
  "words": [{"w","s","e","spk"}],     # VOD seconds (small.en word timings); spk: me (default) | team | enemy
  "fix": {"wrong": "right"},
  "moods": [[from, to, "calm|rage|shocked|sad|laugh"]],     # VOD seconds
  "name": "2026-11-16_tryhard_vs_bots" }
usage: render_plan.py PLAN.json OUTDIR   -> OUTDIR/<name>.mp4 (TikTok-ready, ~3 Mbps)"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
plan = json.load(open(sys.argv[1])); outdir = sys.argv[2]
os.makedirs(outdir, exist_ok=True)
if plan.get("type") == "montage":                      # beat-synced kill montage: its own renderer
    subprocess.run(["python3", os.path.join(HERE, "make_montage.py"), sys.argv[1], outdir], check=True)
    raise SystemExit(0)
S, E = float(plan["start"]), float(plan["end"])
if not [w for w in plan["words"] if S <= w["s"] < E]:
    raise SystemExit(f"{plan['name']}: no captions. Every clip needs on-screen captions (his words, or callouts like DOWN!/DOUBLE KILL!)")
with tempfile.TemporaryDirectory() as d:
    win = os.path.join(d, "window.mp4")
    subprocess.run(["python3", os.path.join(HERE, "twitch_fetch.py"), "window", str(plan["vod"]), str(S), str(E), win], check=True)
    cont = {
        "vod": win, "a": 0.0, "b": E - S, "title": plan["title"], "fix": plan.get("fix", {}), "setup": plan.get("setup"),
        "realtime": plan.get("type", "gameplay") == "gameplay",
        "words": [{"w": w["w"], "s": round(w["s"] - S, 2), "e": round(w["e"] - S, 2), "spk": w.get("spk", "me")} for w in plan["words"] if S <= w["s"] < E],
        "moods": [[lo - S, hi - S, m] for lo, hi, m in plan["moods"]],
        "memes": [{"t": round(m["t"] - S, 2), "kind": m["kind"]} for m in plan.get("memes", []) if S <= m["t"] < E],
        "out": os.path.join(d, "full.mp4"), "tmp": os.path.join(d, "c"),
    }
    json.dump(cont, open(os.path.join(d, "cont.json"), "w"))
    subprocess.run(["python3", os.path.join(HERE, "make_continuous.py"), os.path.join(d, "cont.json")], check=True)
    final = os.path.join(outdir, plan["name"] + ".mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cont["out"], "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-maxrate", "8M", "-bufsize", "16M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", final], check=True)
caption = plan.get("caption") or (" ".join(plan["title"].split()) + " #callofduty #warzone #mrhype420 #codclips #gaming")
open(os.path.join(outdir, plan["name"] + ".txt"), "w").write(caption + "\n")   # TikTok caption, read by the poster
print("rendered", final, os.path.getsize(final))
