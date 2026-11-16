#!/usr/bin/env python3
"""Find LONGSHOT and THROWING KNIFE kills around confirmed downs.
For each down time, reads the HUD popups/medals a few seconds after it and the kill banner:
  - medal / score popup band (center, upper-middle of screen)  -> "LONGSHOT", "LONG SHOT", "THROWING KNIFE", "KNIFE"
  - kill banner top-right                                        -> some modes add the method/distance there
  - weapon box bottom-right at the down                          -> "THROWING KNIFE" / "KNIFE"
Every hit must be checked by eye on a contact sheet before it becomes a clip (HUD layout varies by mode).
usage: medal_scan.py VOD '[down_t, ...]'"""
import sys, json, re
from down_check import frame, ocr, banner, weapon

LONG = re.compile(r"L[O0]NG ?SH[O0]T|LONG ?RANGE", re.I)
KNIFE = re.compile(r"THR[O0]W(ING)? ?KN|KNIFE", re.I)

def medal(im):
    return ocr(im, (380, 150, 900, 330), scale=2)   # center popup / medal band

def scan(vod, t):
    texts = []
    for dt in (0.2, 0.6, 1.0, 1.5, 2.2):
        im = frame(vod, t + dt)
        texts += [medal(im), banner(im)]
    texts.append(weapon(frame(vod, t - 0.3)))
    joined = " | ".join(x for x in texts if x)
    return {"t": t, "longshot": bool(LONG.search(joined)), "knife": bool(KNIFE.search(joined)), "text": joined[:120]}

if __name__ == "__main__":
    vod, downs = sys.argv[1], json.loads(sys.argv[2])
    for t in downs:
        r = scan(vod, t)
        tags = [n for n, k in (("LONGSHOT", "longshot"), ("THROWING KNIFE", "knife")) if r[k]]
        print(f"{int(t//60)}:{t%60:04.1f}  {', '.join(tags) or '-':24} | {r['text']}", flush=True)
