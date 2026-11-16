#!/usr/bin/env python3
"""Fast Twitch VOD fetching (parallel HLS fragments; yt-dlp alone was ~30 KB/s here).

  twitch_fetch.py list                          -> JSON list of archived VODs [{id, seconds, title}]
  twitch_fetch.py audio  VOD OUT.wav            -> whole VOD audio, mono 16 kHz (for transcription)
  twitch_fetch.py window VOD START END OUT.mp4  -> exact 720p video window, START/END in VOD seconds

Missing fragments are filled with silence/black of the same length, so timestamps stay true."""
import json, os, subprocess, sys, tempfile, urllib.request
from concurrent.futures import ThreadPoolExecutor

CHANNEL = "mrhype420"

def ytdlp(*args):
    return subprocess.run(["yt-dlp", *args], capture_output=True, text=True).stdout.strip()

def list_vods():
    out = ytdlp("--flat-playlist", "--print", "%(id)s|%(duration)s|%(title)s",
                f"https://www.twitch.tv/{CHANNEL}/videos?filter=archives&sort=time")
    vods = []
    for line in out.splitlines():
        vid, dur, title = line.split("|", 2)
        vods.append({"id": vid.lstrip("v"), "seconds": float(dur) if dur not in ("NA", "") else None, "title": title})
    return vods

def playlist(vod, fmt):
    url = ytdlp("-g", "-f", fmt, f"https://www.twitch.tv/videos/{vod}")
    if not url.startswith("http"):
        raise SystemExit(f"could not resolve {fmt} playlist for {vod}")
    text = urllib.request.urlopen(url, timeout=30).read().decode()
    base = url.rsplit("/", 1)[0]
    frags, dur, t = [], None, 0.0
    for line in text.splitlines():
        if line.startswith("#EXTINF:"):
            dur = float(line.split(":", 1)[1].split(",")[0])
        elif line and not line.startswith("#"):
            frags.append({"name": line, "start": t, "dur": dur}); t += dur
    live = "#EXT-X-ENDLIST" not in text
    return base, frags, live

def grab(base, frag, folder):
    path = os.path.join(folder, frag["name"].replace("/", "_"))
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return path
    for name in (frag["name"], frag["name"].replace(".ts", "-muted.ts"), frag["name"].replace(".ts", "-unmuted.ts")):
        for _ in range(4):
            try:
                data = urllib.request.urlopen(f"{base}/{name}", timeout=60).read()
                if len(data) > 10000:
                    open(path, "wb").write(data); return path
            except Exception:
                pass
    return None

def fetch(base, frags, folder, video):
    with ThreadPoolExecutor(24) as ex:
        paths = list(ex.map(lambda f: grab(base, f, folder), frags))
    lst = os.path.join(folder, "concat.txt")
    with open(lst, "w") as f:
        for frag, p in zip(frags, paths):
            if p is None:                                   # keep the timeline: same-length filler
                p = os.path.join(folder, "fill_" + frag["name"].replace("/", "_"))
                src = (["-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30"] if video else []) + \
                      ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-t", str(frag["dur"]), "-c:a", "aac",
                                *(["-c:v", "libx264"] if video else []), "-f", "mpegts", p], check=True)
            f.write(f"file '{os.path.abspath(p)}'\n")
    return lst, paths.count(None)

def audio(vod, out):
    base, frags, live = playlist(vod, "Audio_Only")
    with tempfile.TemporaryDirectory() as d:
        lst, missing = fetch(base, frags, d, video=False)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-ac", "1", "-ar", "16000", out], check=True)
    print(json.dumps({"vod": vod, "seconds": round(sum(f["dur"] for f in frags), 2), "missing_fragments": missing, "live": live}))

def window(vod, start, end, out):
    base, frags, _ = playlist(vod, "720p")
    sel = [f for f in frags if f["start"] + f["dur"] > start and f["start"] < end]
    if not sel:
        raise SystemExit("window outside VOD")
    with tempfile.TemporaryDirectory() as d:
        lst, missing = fetch(base, sel, d, video=True)
        offset = start - sel[0]["start"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-ss", f"{offset:.3f}", "-t", f"{end - start:.3f}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "160k", out], check=True)
    print(json.dumps({"vod": vod, "start": start, "end": end, "missing_fragments": missing}))

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "list":
        print(json.dumps(list_vods(), indent=1))
    elif cmd == "audio":
        audio(sys.argv[2], sys.argv[3])
    elif cmd == "window":
        window(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5])
