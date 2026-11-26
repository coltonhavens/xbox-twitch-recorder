#!/usr/bin/env python3
"""Fast Twitch VOD fetching (parallel HLS fragments; yt-dlp alone was ~30 KB/s here).

  twitch_fetch.py list                          -> JSON list of archived VODs [{id, seconds, title}]
  twitch_fetch.py audio  VOD OUT.wav            -> whole VOD audio, mono 16 kHz (for transcription)
  twitch_fetch.py window VOD START END OUT.mp4  -> exact 720p video window, START/END in VOD seconds

Missing fragments are filled with silence/black of the same length, so timestamps stay true."""
import os, json, os, subprocess, sys, tempfile, urllib.request
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

ARCHIVE_FOLDER = "1X9VfSes_byvkygreHfdvGNHzVXjvAYBG"   # Xbox Game Recordings (the recorder's Drive backups)

def _boxes(buf, off=0, end=None):
    end = len(buf) if end is None else end
    while off + 8 <= end:
        size = int.from_bytes(buf[off:off + 4], "big"); typ = buf[off + 4:off + 8]; hdr = 8
        if size == 1: size = int.from_bytes(buf[off + 8:off + 16], "big"); hdr = 16
        if size < 8: break
        yield typ, off, off + hdr, off + size
        off += size

def drive_window(vod, start, end, out):
    """Fallback when Twitch has deleted the VOD (~7 days): read just this window from the recorder's Drive copy
    MrHype420-<vod>.mp4 (a fragmented MP4, no index) using HTTP byte ranges: binary-search the fragments' tfdt times
    to find the right byte offset, download only that stretch, prepend the init segment, cut. Uses the recorder's
    drive.file credential (XTR_DRIVE_AUTH, only present in GitHub Actions)."""
    raw = os.environ.get("XTR_DRIVE_AUTH")
    if not raw:
        raise SystemExit(f"VOD {vod} is gone from Twitch and XTR_DRIVE_AUTH isn't set here (Drive fallback runs in GitHub Actions)")
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    import urllib.parse
    creds = Credentials.from_authorized_user_info(json.loads(raw)["oauth"]); creds.refresh(Request())
    H = {"Authorization": f"Bearer {creds.token}"}
    q = f"'{ARCHIVE_FOLDER}' in parents and name = 'MrHype420-{vod}.mp4' and trashed = false"
    req = urllib.request.Request("https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode({"q": q, "fields": "files(id,size)"}), headers=H)
    files = json.load(urllib.request.urlopen(req, timeout=60)).get("files", [])
    if not files:
        raise SystemExit(f"VOD {vod}: not on Twitch and no Drive backup MrHype420-{vod}.mp4")
    url = f"https://www.googleapis.com/drive/v3/files/{files[0]['id']}?alt=media"; size = int(files[0]["size"])
    def rng(a, b):
        r = urllib.request.Request(url, headers={**H, "Range": f"bytes={a}-{min(b, size - 1)}"})
        return urllib.request.urlopen(r, timeout=120).read()
    head = rng(0, 4 << 20)
    init_end = None; scales = {}
    for typ, o, c, e in _boxes(head):
        if typ == b"moov":
            init_end = e
            for t2, o2, c2, e2 in _boxes(head, c, e):
                if t2 != b"trak": continue
                tid = None; ts = None
                for t3, o3, c3, e3 in _boxes(head, c2, e2):
                    if t3 == b"tkhd":
                        v = head[c3]; tid = int.from_bytes(head[c3 + (20 if v == 1 else 12):c3 + (24 if v == 1 else 16)], "big")
                    if t3 == b"mdia":
                        for t4, o4, c4, e4 in _boxes(head, c3, e3):
                            if t4 == b"mdhd":
                                v = head[c4]; ts = int.from_bytes(head[c4 + (20 if v == 1 else 12):c4 + (24 if v == 1 else 16)], "big")
                if tid: scales[tid] = ts
    if not init_end:
        raise SystemExit("Drive copy: no moov at the start (not the expected fragmented MP4)")
    init = head[:init_end]
    def time_at(off):
        """seconds of the first fragment starting at/after byte off, and that fragment's byte offset"""
        for span in (2 << 20, 8 << 20, 32 << 20):     # fragments can be long; read more if none starts in 2 MB
            buf = rng(off, off + span); i = 0
            while True:
                i = buf.find(b"moof", i + 1)
                if i < 4: break
                m0 = i - 4; msize = int.from_bytes(buf[m0:m0 + 4], "big")
                if msize < 16 or m0 + msize + 8 > len(buf) or buf[m0 + msize + 4:m0 + msize + 8] != b"mdat": continue
                for t, o, c, e in _boxes(buf, m0 + 8, m0 + msize):
                    if t != b"traf": continue
                    tid = None
                    for t2, o2, c2, e2 in _boxes(buf, c, e):
                        if t2 == b"tfhd": tid = int.from_bytes(buf[c2 + 4:c2 + 8], "big")
                        if t2 == b"tfdt" and tid in scales and scales[tid]:
                            v = buf[c2]; val = int.from_bytes(buf[c2 + 4:c2 + (12 if v == 1 else 8)], "big")
                            return val / scales[tid], off + m0
            if off + len(buf) >= size: break
        return None, None
    lo, hi = init_end, size - (1 << 20); target = max(0.0, start - 3.0); best = init_end; t_best = 0.0
    samples = []
    for _ in range(40):
        if hi - lo < (4 << 20): break
        mid = (lo + hi) // 2; t, foff = time_at(mid)
        if t is None:                      # no fragment start found in this read: look a little further back
            hi = mid; continue
        samples.append((foff, t))
        if os.environ.get("DW_DEBUG"): print("mid", mid, "t", round(t, 1), "foff", foff, file=sys.stderr)
        if t > target: hi = mid
        else: lo = mid; best = foff; t_best = t
    t0, foff = time_at(best)
    if t0 is None: t0, foff = t_best, best
    # bytes per second from the search samples (fallback ~3 Mb/s), then fetch just enough to cover the window
    samples.sort()
    bps = ((samples[-1][0] - samples[0][0]) / (samples[-1][1] - samples[0][1])) if len(samples) > 1 and samples[-1][1] > samples[0][1] else 375000
    need = int((end + 4 - t0) * bps * 1.35) + (4 << 20)
    with tempfile.TemporaryDirectory() as d:
        part = os.path.join(d, "part.mp4")
        with open(part, "wb") as f:
            f.write(init); pos = foff; stop = min(size, foff + need)
            while pos < stop:
                data = rng(pos, min(stop, pos + (16 << 20)) - 1); f.write(data); pos += len(data)
        # the demuxer restarts timestamps at 0 for this piece, so seek relative to the fragment's own start time
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, start - t0):.3f}", "-i", part, "-t", f"{end - start:.3f}",
                        "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        "-c:a", "aac", "-b:a", "160k", out], check=True)
    st = t0
    print(json.dumps({"vod": vod, "start": start, "end": end, "source": "drive", "fragment_start": round(st, 2)}))

def window(vod, start, end, out):
    try:
        base, frags, _ = playlist(vod, "720p")
    except SystemExit:
        return drive_window(vod, start, end, out)
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
