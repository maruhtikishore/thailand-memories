"""Pick a spread of short clips from the Thailand videos and compress them for the web.

Originals are only read. Output: videos/clips/*.mp4, videos/poster/*.jpg, videos/videos.js
Usage: python build_videos.py [max_clips]
"""
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SRC = r"K:\Memories Daries\OG BOYS\Thailand Vedio"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "videos")
MAX_CLIPS = int(sys.argv[1]) if len(sys.argv) > 1 else 48
MIN_DUR, MAX_DUR, CLIP_LEN = 4.0, 90.0, 30  # source length window; output trimmed to CLIP_LEN s
EXTS = {".mov", ".mp4"}
COPY_NAME = re.compile(r"\(\d+\)")  # "IMG_1 (2).mov" are copies of IMG_1


def probe(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0
    return dur


def encode(item):
    src, base = item["src"], item["id"]
    clip = os.path.join(OUT, "clips", base + ".mp4")
    poster = os.path.join(OUT, "poster", base + ".jpg")
    if not os.path.exists(clip):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src, "-t", str(CLIP_LEN),
                        "-vf", "scale='if(gt(iw,ih),-2,540)':'if(gt(iw,ih),540,-2)',format=yuv420p",
                        "-c:v", "libx264", "-crf", "29", "-preset", "veryfast", "-r", "30",
                        "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", clip], check=True)
    if not os.path.exists(poster):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "0.5", "-i", clip, "-frames:v", "1",
                        "-vf", "scale=480:-2", "-q:v", "5", poster], check=True)
    # actual output size
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", clip], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    d = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else item["dur"]
    s = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", r.stderr)
    return {"id": base, "t": item["t"], "dur": round(d, 1),
            "w": int(s[1]) if s else 0, "h": int(s[2]) if s else 0,
            "mb": round(os.path.getsize(clip) / 1048576, 1)}


def main():
    for sub in ("clips", "poster"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    files = [n for n in os.listdir(SRC)
             if os.path.splitext(n)[1].lower() in EXTS and not COPY_NAME.search(n)]
    print(f"{len(files)} unique videos, probing...", flush=True)

    def info(n):
        p = os.path.join(SRC, n)
        return {"src": p, "id": re.sub(r"[^\w\-]", "_", os.path.splitext(n)[0]),
                "t": datetime.fromtimestamp(os.path.getmtime(p)).isoformat(), "dur": probe(p)}

    with ThreadPoolExecutor(6) as ex:
        items = [i for i in ex.map(info, files) if MIN_DUR <= i["dur"] <= MAX_DUR]
    print(f"{len(items)} clips in {MIN_DUR}-{MAX_DUR}s range", flush=True)

    # spread evenly over the trip days
    by_day = defaultdict(list)
    for i in items:
        by_day[i["t"][:10]].append(i)
    days = [d for d in sorted(by_day) if len(by_day[d]) >= 3]  # real trip days
    per_day = max(1, MAX_CLIPS // max(1, len(days)))
    chosen = []
    for d in days:
        arr = sorted(by_day[d], key=lambda x: x["t"])
        step = len(arr) / min(per_day, len(arr))
        chosen += [arr[int(k * step)] for k in range(min(per_day, len(arr)))]
    print(f"encoding {len(chosen)} clips across {len(days)} days...", flush=True)

    results = []
    with ThreadPoolExecutor(4) as ex:
        for n, r in enumerate(ex.map(encode, chosen), 1):
            results.append(r)
            if n % 5 == 0:
                print(f"{n}/{len(chosen)}", flush=True)
    results.sort(key=lambda r: r["t"])
    with open(os.path.join(OUT, "videos.js"), "w", encoding="utf-8") as f:
        f.write("window.VIDEOS = " + json.dumps(results, separators=(",", ":")) + ";\n")
    print(f"done: {len(results)} clips, {sum(r['mb'] for r in results):.0f} MB")


if __name__ == "__main__":
    main()
