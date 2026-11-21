#!/usr/bin/env python3
"""Which downs were sniper HEADSHOTS? (and which ended in a squad wipe)
For each down time: reads the weapon box (must be a sniper) and the XP popup next to the crosshair
("HEADSHOT", "ONE SHOT ONE KILL", "LONGSHOT", "ARMOR BREAK", "ENEMY DOWNED") plus the kill banner ("SQUAD WIPED").
Only a down whose popup reads HEADSHOT counts as a headshot. Check every hit on a frame before using it.
usage: headshot_scan.py candidates.json out.json      candidates: [{"vod":..., "t": down_time}, ...]"""
import json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from down_check import frame, ocr, banner, weapon, SNIPERS, DOWN

HEAD = re.compile(r"HEAD ?SH|EADSH[O0]|HEADS[HN]", re.I)
ONESHOT = re.compile(r"NE SH[O0]T|[O0]NE K[IR]", re.I)
WIPE = re.compile(r"WIPE", re.I)
def popup(im): return ocr(im, (660, 270, 940, 400), scale=3)      # XP popup right of the crosshair

def scan(vod, t, d):
    w0 = t - 2.5; win = os.path.join(d, "w.mp4")
    subprocess.run(["python3", os.path.join(HERE, "twitch_fetch.py"), "window", str(vod), str(w0), str(t + 3.0), win],
                   check=True, capture_output=True)
    texts, first_down = [], None
    for k in range(int(4.5 / 0.25)):                                  # t-1.5 .. t+3.0 at 4 fps
        tt = t - 1.5 + k * 0.25
        im = frame(win, tt - w0)
        p, b = popup(im), banner(im)
        texts.append(p + " | " + b)
        if first_down is None and DOWN.search(p + b): first_down = tt
    wpn = " / ".join(weapon(frame(win, x - w0)) for x in (t - 1.2, t - 0.4))
    allt = " || ".join(texts)
    return {"vod": vod, "t": t, "down_at": first_down, "sniper": bool(SNIPERS.search(wpn)),
            "headshot": bool(HEAD.search(allt)), "one_shot": bool(ONESHOT.search(allt)),
            "wipe": bool(WIPE.search(allt)), "weapon": wpn[:40],
            "text": allt, "popups": sorted({x.split(" | ")[0] for x in texts if len(x.split(" | ")[0]) > 3})[:6]}

if __name__ == "__main__":
    cands = json.load(open(sys.argv[1])); res = []
    with tempfile.TemporaryDirectory() as d:
        for c in cands:
            try: r = scan(c["vod"], c["t"], d)
            except subprocess.CalledProcessError: continue
            res.append(r)
            print(f"{r['vod']} {r['t']:8.1f}  sniper={int(r['sniper'])} HS={int(r['headshot'])} 1shot={int(r['one_shot'])} "
                  f"wipe={int(r['wipe'])} | {r['weapon']} | {r['popups'][:3]}", flush=True)
    json.dump(res, open(sys.argv[2], "w"), indent=1)
