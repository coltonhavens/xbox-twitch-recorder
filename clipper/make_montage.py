#!/usr/bin/env python3
"""Beat-synced kill montage (one per day), kill-to-kill style. Plan JSON:
{ "type": "montage",
  "style": "triple_kills | sniper_one_shots | squad_wipes | headshots | every_kill | top5 | reaction_first",
  "title": "Back to back\\nTRIPLE KILLS",
  "track": "trap_slow_1",                  # music/tracks.json key (cleared, commercial-use music only)
  "segments": [ {"vod": "2931992210", "hits": [1326.5, 1331.5, 1335.5],      # VOD seconds of each DOWN banner
                 "labels": ["DOWN!", "DOUBLE!", "TRIPLE!"]} , ... ],
  "name": "2026-11-21_triple_montage", "caption": "optional TikTok caption" }

Colton's rules (Nov 21):
- Cut straight from one shot to the next shot. Each cut = the shot and the down, nothing else
  (no reloads, no walking, no dead air). Every hit is a confirmed down, no misses.
- Slow, spacious beat. Every down lands ON a beat and gets its own "drop": the music cuts out for a
  split second before the down, then an 808 hit + zoom punch slam in on the down.
- The last kill of each fight (the TRIPLE) gets an extra beat to breathe; the final kill also flashes.
usage: make_montage.py PLAN.json OUTDIR"""
import json, math, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def refine(win, w0, h):
    """Banner times come from a 1 fps scan; find the exact first frame the DOWN banner shows (8 fps)."""
    from down_check import frame, banner, DOWN
    before = banner(frame(win, max(0.05, h - 1.1 - w0)))
    t = h - 1.0          # a 1 fps scan is never more than ~1 s late
    while t <= h + 0.6:
        b = banner(frame(win, t - w0))
        if DOWN.search(b) and b != before:
            return round(t, 3)
        t += 0.125
    return h
run = lambda *a: subprocess.run(list(a), check=True)

def personality(plan, outdir):
    """Personality montage: his best lines back to back (trash talk, screaming, laughing). Each line plays whole and
    in real time with its own captions; music sits low under his voice; every cut gets a bass hit + zoom punch and
    the last line (the payoff) gets the big hit. plan["lines"] = [{"vod","a","b","words":[{"w","s","e","spk"}]}]"""
    tr = json.load(open(os.path.join(HERE, "music", "tracks.json")))[plan["track"]]
    with tempfile.TemporaryDirectory() as d:
        parts, cuts, words, cum = [], [], [], 0.0
        for i, ln in enumerate(plan["lines"]):
            a, b = ln["a"], ln["b"]
            win = os.path.join(d, f"w{i}.mp4")
            run("python3", os.path.join(HERE, "twitch_fetch.py"), "window", str(ln["vod"]), str(a), str(b), win)
            f = os.path.join(d, f"p{i}.mp4")
            run("ffmpeg", "-v", "error", "-y", "-i", win, "-vf", "scale=1280:720,fps=30,setsar=1",
                "-af", "aresample=48000", "-ac", "2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", f)
            parts.append(f); cuts.append(round(cum, 3))
            words += [{"w": w["w"], "s": round(cum + w["s"] - a, 2), "e": round(cum + w["e"] - a, 2), "spk": w.get("spk", "me")}
                      for w in ln["words"] if a <= w["s"] < b]
            cum += b - a
        L = cum; final = cuts[-1]
        lst = os.path.join(d, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        raw = os.path.join(d, "raw.mp4")
        run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", raw)
        hits = cuts[1:] or [0.0]
        z = "+".join(f"if(gte(t,{h}),{0.18 if h == final else 0.08}*exp(-(t-{h})*7),0)" for h in hits)
        boom = "".join(f"[b{i}]" for i in range(len(hits)))
        chain = f"[2:a]asplit={len(hits)}{boom};" + ";".join(
            f"[b{i}]adelay={int(h * 1000)}|{int(h * 1000)},volume={0.9 if h == final else 0.45}[d{i}]" for i, h in enumerate(hits))
        duck = f"(1-0.9*between(t,{final - 0.25:.3f},{final:.3f}))"
        mont = os.path.join(d, "montage.mp4")
        run("ffmpeg", "-v", "error", "-y", "-i", raw, "-ss", f"{tr['first_beat']:.3f}", "-i", os.path.join(HERE, "music", tr["file"]),
            "-i", os.path.join(HERE, "music", "boom.wav"), "-filter_complex",
            f"[0:v]scale=w='trunc(1280*(1+{z})/2)*2':h='trunc(720*(1+{z})/2)*2':eval=frame,"
            f"crop=1280:720:(iw-1280)/2:(ih-720)/2,setsar=1[v];[0:a]volume=1.0[g];"
            f"[1:a]aresample=48000,volume='0.28*{duck}':eval=frame,afade=t=out:st={max(0, L - 0.6):.2f}:d=0.6[m];{chain};"
            f"[g][m]" + "".join(f"[d{i}]" for i in range(len(hits))) +
            f"amix=inputs={2 + len(hits)}:normalize=0:duration=first,alimiter=limit=0.95[a]",
            "-map", "[v]", "-map", "[a]", "-t", f"{L:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", mont)
        spec = {"src": mont, "start": 0, "end": round(L, 2), "title": plan["title"], "words": words,
                "moods": plan.get("moods") or [[0, L, "laugh"]], "out": os.path.join(d, "full.mp4")}
        json.dump(spec, open(os.path.join(d, "spec.json"), "w"))
        run("python3", os.path.join(HERE, "render_clip.py"), os.path.join(d, "spec.json"))
        out = os.path.join(outdir, plan["name"] + ".mp4")
        run("ffmpeg", "-v", "error", "-y", "-i", spec["out"], "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-maxrate", "5M", "-bufsize", "10M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", out)
    cap = plan.get("caption") or (" ".join(plan["title"].split()) + " #callofduty #warzone #mrhype420 #gaming #funny")
    open(os.path.join(outdir, plan["name"] + ".txt"), "w").write(cap + "\n")
    print("personality montage", out, f"{L:.1f}s", "cuts at", cuts)

def main(plan_path, outdir):
    plan = json.load(open(plan_path)); os.makedirs(outdir, exist_ok=True)
    if plan.get("style") == "personality":
        return personality(plan, outdir)
    tr = json.load(open(os.path.join(HERE, "music", "tracks.json")))[plan["track"]]
    P = 60.0 / tr["bpm"]
    step = P * tr.get("beats_per_kill", 2)          # time between downs
    pre = min(1.1, step - 0.35)                     # show the shot before the down
    kills = []                                      # (vod, down_t, label, last_of_fight, slowmo)
    for seg in plan["segments"]:
        labs = seg.get("labels") or ["DOWN!"] * len(seg["hits"])
        slow = set(seg.get("slowmo", []))           # indexes of hits shown in slow motion (team wipes)
        for j, (h, lab) in enumerate(zip(seg["hits"], labs)):
            kills.append((seg["vod"], h, lab, len(seg["hits"]) > 1 and j == len(seg["hits"]) - 1, j in slow))
    intro = 2 * P                                   # "go... go..." before the first down
    n = len(kills)
    with tempfile.TemporaryDirectory() as d:
        parts, downs, cum = [], [], 0.0
        for i, (vod, h, lab, last, slowmo) in enumerate(kills):
            gap = step + (P if last else 0)          # time to the next down (extra beat after a finished fight)
            if slowmo: gap = 4 * P                   # team wipe: slow motion over a whole bar, then back to speed
            w0 = h - 4.0
            win = os.path.join(d, f"w{i}.mp4")
            run("python3", os.path.join(HERE, "twitch_fetch.py"), "window", str(vod), str(w0), str(h + 5.0), win)
            h0, h = h, refine(win, w0, h); print(f"down {vod} {h0} -> {h}", flush=True)
            a = h - (intro if i == 0 else pre)
            post = gap - pre if i < n - 1 else (4 * P if slowmo else 2 * P) + 0.6   # output seconds after the down
            SL = 0.4
            if slowmo:   # real time up to just before the down, then 0.4x through the wipe
                pieces = [(a, h - 0.25, 1.0), (h - 0.25, h - 0.25 + (post + 0.25) * SL, SL)]
            else:
                pieces = [(a, h + post, 1.0)]
            for j, (pa, pb, sp) in enumerate(pieces):
                f = os.path.join(d, f"p{i}_{j}.mp4")
                at = "atempo=0.5,atempo=0.8" if sp == SL else "anull"
                run("ffmpeg", "-v", "error", "-y", "-ss", f"{pa - w0:.3f}", "-t", f"{pb - pa:.3f}", "-i", win,
                    "-vf", f"scale=1280:720,setpts=PTS/{sp},fps=30,setsar=1", "-af", f"{at},aresample=48000", "-ac", "2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", f)
                parts.append(f)
            downs.append((round(cum + (h - a), 3), lab)); cum += (h - a) + post
        L = cum
        lst = os.path.join(d, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        raw = os.path.join(d, "raw.mp4")
        run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", raw)
        hits = [x for x, _ in downs]; final = hits[-1]
        # music: a beat of the track (after its own intro) lines up with the first down
        b0 = tr["first_beat"]
        while b0 < max(hits[0], tr.get("start_after", 0)): b0 += P
        mstart = b0 - hits[0]
        duck = "*".join(f"(1-0.85*between(t,{h - 0.22:.3f},{h:.3f}))" for h in hits)    # silence right before each down
        z = "+".join(f"if(gte(t,{h}),{0.22 if h == final else 0.13}*exp(-(t-{h})*7),0)" for h in hits)
        flash = f"between(t,{final},{final + 0.07})"
        boom_chain = f"[2:a]asplit={len(hits)}" + "".join(f"[b{i}]" for i in range(len(hits))) + ";" + ";".join(
            f"[b{i}]adelay={int(h * 1000)}|{int(h * 1000)},volume={1.0 if h == final else 0.8}[d{i}]"
            for i, h in enumerate(hits))
        mont = os.path.join(d, "montage.mp4")
        run("ffmpeg", "-v", "error", "-y", "-i", raw, "-ss", f"{mstart:.3f}", "-i", os.path.join(HERE, "music", tr["file"]),
            "-i", os.path.join(HERE, "music", "boom.wav"), "-filter_complex",
            f"[0:v]scale=w='trunc(1280*(1+{z})/2)*2':h='trunc(720*(1+{z})/2)*2':eval=frame,"
            f"crop=1280:720:(iw-1280)/2:(ih-720)/2,eq=brightness='0.35*{flash}':eval=frame,setsar=1[v];"
            f"[0:a]volume=0.6[g];"
            f"[1:a]aresample=48000,volume='0.85*{duck}':eval=frame,afade=t=out:st={max(0, L - 0.6):.2f}:d=0.6[m];"
            f"{boom_chain};"
            f"[g][m]" + "".join(f"[d{i}]" for i in range(len(hits))) +
            f"amix=inputs={2 + len(hits)}:normalize=0:duration=first,alimiter=limit=0.95[a]",
            "-map", "[v]", "-map", "[a]", "-t", f"{L:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", mont)
        words = [{"w": lab, "s": h, "e": round(h + 0.8, 2), "spk": "callout"} for h, lab in downs]
        spec = {"src": mont, "start": 0, "end": round(L, 2), "title": plan["title"], "words": words,
                "moods": [[0, hits[0], "calm"], [hits[0], L, "shocked"]], "out": os.path.join(d, "full.mp4")}
        json.dump(spec, open(os.path.join(d, "spec.json"), "w"))
        run("python3", os.path.join(HERE, "render_clip.py"), os.path.join(d, "spec.json"))
        out = os.path.join(outdir, plan["name"] + ".mp4")
        run("ffmpeg", "-v", "error", "-y", "-i", spec["out"], "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-maxrate", "5M", "-bufsize", "10M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", out)
    cap = plan.get("caption") or (" ".join(plan["title"].split()) + " #callofduty #warzone #mrhype420 #codmontage #gaming")
    open(os.path.join(outdir, plan["name"] + ".txt"), "w").write(cap + "\n")
    print("montage", out, f"{L:.1f}s", "downs at", hits, "beat", round(P, 3))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
