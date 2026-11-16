#!/usr/bin/env python3
"""Tools for the daily Claude run.

  preview.py transcribe VOD OUT.json         whole-stream transcript (base.en) from audio only
  preview.py window VOD START END OUTDIR     720p window + accurate word timings (small.en, VOD seconds)
                                             + a contact sheet (one frame every 3 s) to check the gameplay
"""
import json, os, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))

def pcm(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768

def transcribe(vod, out):
    from faster_whisper import WhisperModel
    wav = out + ".wav"
    subprocess.run(["python3", os.path.join(HERE, "twitch_fetch.py"), "audio", vod, wav], check=True)
    segs, _ = WhisperModel("base.en", compute_type="int8").transcribe(pcm(wav), vad_filter=True, condition_on_previous_text=False)
    res = [{"s": round(s.start, 2), "e": round(s.end, 2), "t": s.text.strip()} for s in segs]
    json.dump(res, open(out, "w"))
    os.remove(wav)
    print(f"{len(res)} lines -> {out}")
    for x in res:
        print(f"{int(x['s']//60)}:{int(x['s']%60):02d} ({x['s']:.0f}s) {x['t']}")

def window(vod, start, end, outdir):
    from faster_whisper import WhisperModel
    os.makedirs(outdir, exist_ok=True)
    mp4 = os.path.join(outdir, "window.mp4")
    subprocess.run(["python3", os.path.join(HERE, "twitch_fetch.py"), "window", vod, str(start), str(end), mp4], check=True)
    # vad_filter=False on purpose: VAD dropped most of his lines over loud game audio
    segs, _ = WhisperModel("small.en", compute_type="int8").transcribe(pcm(mp4), word_timestamps=True, vad_filter=False)
    words = []
    for s in segs:
        print(f"{start + s.start:8.1f}-{start + s.end:8.1f} {s.text}")
        words += [{"w": w.word.strip(), "s": round(start + w.start, 2), "e": round(start + w.end, 2)} for w in s.words]
    json.dump(words, open(os.path.join(outdir, "words.json"), "w"))
    n = int((end - start) // 3) + 1
    cols = 6
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vf",
                    f"fps=1/3,scale=320:-1,drawtext=text='%{{pts\\:hms\\:{start}}}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black,"
                    f"tile={cols}x{(n + cols - 1) // cols}", "-frames:v", "1", os.path.join(outdir, "sheet.jpg")], check=False)
    print("words ->", os.path.join(outdir, "words.json"), "| sheet ->", os.path.join(outdir, "sheet.jpg"))

if __name__ == "__main__":
    if sys.argv[1] == "transcribe":
        transcribe(sys.argv[2], sys.argv[3])
    else:
        window(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5])
