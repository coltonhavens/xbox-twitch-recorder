#!/usr/bin/env python3
"""Find THROWING KNIFE kills in a stretch of a VOD: reads the XP popup next to the crosshair at 2 fps.
usage: knife_scan.py VOD START END      -> prints each time the popup says THROWING KNIFE (check on a frame)"""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from down_check import frame, ocr
KNIFE = re.compile(r"THR[O0]W|R[O0]WING ?KN|KNIFE|KNTFE", re.I)
vod, A, B = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
with tempfile.TemporaryDirectory() as d:
    win = os.path.join(d, "w.mp4")
    subprocess.run(["python3", os.path.join(HERE, "twitch_fetch.py"), "window", vod, str(A), str(B), win], check=True, capture_output=True)
    last = -9
    t = A
    while t < B:
        txt = ocr(frame(win, t - A), (660, 270, 940, 420), scale=3)
        if KNIFE.search(txt) and t - last > 3:
            print(f"{vod} {t:.1f} KNIFE | {txt[:80]}", flush=True); last = t
        t += 0.5
