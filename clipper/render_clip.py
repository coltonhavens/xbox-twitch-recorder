#!/usr/bin/env python3
"""Render one vertical MrHype420 clip from a JSON spec.

spec = {"src": video, "start": s, "end": s, "title": "line1\\nline2",
        "words": [{"w","s","e"}...]  (times in source seconds),
        "moods": [[from_s, to_s, "calm|rage|shocked"]...], "out": path}
Mouth follows the voice: band-passed loudness per frame, gated to word timings."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

spec = json.load(open(sys.argv[1]))
SRC, START, END, OUT, TITLE = spec["src"], spec["start"], spec["end"], spec["out"], spec["title"]
FPS, W, H, GAME_Y = 30, 1080, 1920, 520
_nl = spec["title"].count("\n") + 1
TITLE_Y = 190 if _nl > 1 else 250            # title box top
CAP_Y = TITLE_Y + 74 * _nl + 40 + 4          # captions sit right under the title, above the gameplay
KIT = os.path.join(HERE, "kit", "k{}.png")
# mood -> (mouth closed face, mouth open face)
MOODS = {"calm": (0, 1), "rage": (7, 4), "shocked": (8, 3), "sad": (5, 5), "laugh": (2, 2)}
CENSOR = {"fuck": "F**K", "fucking": "F***ING", "fuckin": "F***IN", "bitch": "B*TCH", "bitches": "B*TCHES",
          "shit": "SH*T", "dick": "D*CK"}

words = [w for w in spec["words"] if START <= w["s"] < END]
import re
BAD = re.compile(r"(fuck|shit|bitch|dick|cunt|pussy|nigg)", re.I)
def censor(word):
    word = word.strip(",.?!").upper()
    m = BAD.search(word)
    if not m:
        return word
    root = m.group(0).upper()
    return word.replace(root, root[0] + "*" * (len(root) - 2) + root[-1])
for w in words:
    w["t"] = censor(w["w"])
# caption groups: max 3 words, never across a sentence end, a comma, or a pause/cut
g, n, prev = 0, 0, None
for w in words:
    if prev is not None and (n >= 3 or prev["w"][-1:] in ".?!," or w["s"] - prev["e"] > 0.6):
        g, n = g + 1, 0
    w["g"], n, prev = g, n + 1, w

pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(START), "-t", str(END - START), "-i", SRC,
                      "-ac", "1", "-ar", "16000", "-af", "highpass=f=250,lowpass=f=3500", "-f", "s16le", "-"],
                     capture_output=True).stdout
a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
spf = 16000 // FPS
NF = len(a) // spf
env = np.array([np.sqrt((a[i * spf:(i + 1) * spf] ** 2).mean()) for i in range(NF)])
env = np.convolve(env, [0.5, 0.5], mode="same")
env = np.append(env[1:], 0)                       # open 1 frame before the sound
in_word = np.array([any(w["s"] - 0.08 <= START + i / FPS < w["e"] + 0.08 for w in words) for i in range(NF)])
hi = max(0.020, float(np.percentile(env[in_word], 40))) if in_word.any() else 0.02
mouth, state, held = np.zeros(NF, bool), False, 0
for i in range(NF):
    want = in_word[i] and (env[i] > hi or (state and env[i] > hi * 0.6))
    if want != state and held >= 2:
        state, held = want, 0
    held += 1
    mouth[i] = state

title_font = ImageFont.truetype(os.path.join(HERE, "fonts", "Inter-ExtraBold.otf"), 58)
cap_font = ImageFont.truetype(os.path.join(HERE, "fonts", "Poppins-Bold.ttf"), 92)
name_font = ImageFont.truetype(os.path.join(HERE, "fonts", "Inter-ExtraBold.otf"), 34)
need = {i for pair in MOODS.values() for i in pair}
faces = {i: Image.open(KIT.format(i)).convert("RGBA").resize((470, 470), Image.LANCZOS) for i in need}

def mood_at(T):
    for lo, hi_, m in spec["moods"]:
        if lo <= T < hi_:
            return m
    return "calm"

def face_for(f):
    closed, opened = MOODS[mood_at(START + f / FPS)]
    return opened if (f < NF and mouth[f]) else closed

def draw_title(img):
    d = ImageDraw.Draw(img)
    lines = TITLE.split("\n")
    widths = [d.textlength(l, font=title_font) for l in lines]
    bw, bh = max(widths) + 70, 74 * len(lines) + 40
    x0, y0 = (W - bw) // 2, TITLE_Y
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], 26, fill=(255, 255, 255, 255))
    for i, l in enumerate(lines):
        d.text(((W - widths[i]) / 2, y0 + 22 + i * 74), l, font=title_font, fill=(0, 0, 0, 255))

def draw_caption(img, T):
    cur = [w for w in words if w["s"] <= T < w["e"] + 0.25]
    if not cur:
        return
    group = [w for w in words if w["g"] == cur[-1]["g"]]
    d = ImageDraw.Draw(img)
    parts = [w["t"] for w in group]
    total = sum(d.textlength(p, font=cap_font) for p in parts) + 28 * (len(parts) - 1)
    while total > W - 60 and len(parts) > 1:              # long words: show fewer
        group, parts = group[-1:] if cur[-1] is group[-1] else [cur[-1]], [cur[-1]["t"]]
        total = d.textlength(parts[0], font=cap_font)
    x, y = (W - total) / 2, CAP_Y
    for w, p in zip(group, parts):
        col = (255, 221, 0, 255) if w is cur[-1] else (255, 255, 255, 255)
        d.text((x, y), p, font=cap_font, fill=col, stroke_width=9, stroke_fill=(0, 0, 0, 255))
        x += d.textlength(p, font=cap_font) + 28

n = int((END - START) * FPS)
ff = subprocess.Popen([
    "ffmpeg", "-loglevel", "error", "-y", "-ss", str(START), "-t", str(END - START), "-i", SRC,
    "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
    "-filter_complex",
    f"[0:v]fps={FPS},scale=1280:720,split[a][b];"
    f"[a]scale=-2:{H},crop={W}:{H},gblur=sigma=30,eq=brightness=-0.15[bg];"
    f"[b]crop=720:720:280:0,scale={W}:{W}:flags=lanczos[fg];"
    f"[bg][fg]overlay=0:{GAME_Y}[base];[base][1:v]overlay=0:0:format=auto[v]",
    "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", OUT], stdin=subprocess.PIPE)
for f in range(n):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_title(layer)
    fid = face_for(f)
    bob = -6 if (f < NF and mouth[f]) else 0
    layer.alpha_composite(faces[fid], (W - 470 - 10, GAME_Y + 1080 - 360 + bob))
    d = ImageDraw.Draw(layer)
    d.text((W - 245 - d.textlength("MrHype420", font=name_font) / 2, GAME_Y + 1080 + 105), "MrHype420",
           font=name_font, fill=(57, 255, 20, 255), stroke_width=5, stroke_fill=(0, 0, 0, 255))
    draw_caption(layer, START + f / FPS)
    ff.stdin.write(layer.tobytes())
ff.stdin.close(); ff.wait()
print("done", n, "frames ->", OUT)
