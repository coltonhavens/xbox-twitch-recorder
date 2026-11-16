#!/usr/bin/env python3
"""A sniper shot only counts if the enemy goes DOWN.
Reads two things from the game HUD:
  - kill banner top-right ("ENEMY DOWNED <name>" / "ELIMINATION")  -> must appear after the shot and not before it
  - weapon name bottom-right ("MOSIN-NAGANT", etc.)                -> must be a sniper
usage: down_check.py VOD '[shot_t, ...]'"""
import subprocess, io, re, sys, json
from PIL import Image, ImageOps
import pytesseract
SNIPERS = re.compile(r"[MH]OS[IT]N|AGANT|NAGA|KATT|LONGBOW|XRK|KAR98|SPR|FJX|LOCKWOOD|SVD|HDR|AMR|LR 7|VICTUS|ZRG|LA-B|MCPR|SP-X|TYPE 63|SNIPER", re.I)
DOWN = re.compile(r"D[O0]WNED|ELIMINAT|WIPED", re.I)

def frame(vod, t):
    png = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", vod, "-frames:v", "1", "-vf", "scale=1280:720",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert("L")

def ocr(im, box, scale=3):
    c = im.crop(box); c = ImageOps.autocontrast(c.resize((c.width * scale, c.height * scale)))
    return " ".join(pytesseract.image_to_string(c, config="--psm 6").split())

def banner(im):   return ocr(im, (1000, 80, 1280, 140))
def weapon(im):   return ocr(im, (900, 625, 1120, 665))

def check(vod, t):
    before = banner(frame(vod, t - 0.3))
    if DOWN.search(before):
        before_name = before
    else:
        before_name = ""
    near = [weapon(frame(vod, t + d)) for d in (-0.3, 0.3)]          # weapon in hand at the shot
    readable = [x for x in near if re.search(r"[A-Z]{4,}", x)]
    w = " / ".join(readable) if readable else weapon(frame(vod, t - 1.2))
    for dt in [0.3, 0.7, 1.1, 1.6, 2.2, 3.0]:
        b = banner(frame(vod, t + dt))
        if DOWN.search(b) and b != before_name:
            return {"t": t, "down": True, "sniper": bool(SNIPERS.search(w)), "banner": b, "weapon": w}
    return {"t": t, "down": False, "sniper": bool(SNIPERS.search(w)), "banner": "", "weapon": w}

if __name__ == "__main__":
    vod, shots = sys.argv[1], json.loads(sys.argv[2])
    for t in shots:
        r = check(vod, t)
        tag = "SNIPE DOWN" if r["down"] and r["sniper"] else ("down (not sniper)" if r["down"] else "no down")
        print(f"{int(t//60)}:{t%60:04.1f}  {tag:18} | {r['banner'][:40]:40} | {r['weapon'][:30]}", flush=True)
