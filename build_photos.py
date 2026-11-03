"""Convert the Thailand photos into web-friendly WebP files + a photos.js manifest.

Originals are only read, never modified or moved.
Usage: python build_photos.py
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()

SRC = r"K:\Memories Daries\OG BOYS\Thailand 2026\Thai Photos"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")
FULL, THUMB = 1600, 480
EXTS = {".jpeg", ".jpg", ".heic", ".png"}


def taken_at(img, path):
    try:
        exif = img.getexif()
        ifd = exif.get_ifd(0x8769)
        raw = ifd.get(0x9003) or exif.get(0x0132)
        if raw:
            return datetime.strptime(str(raw)[:19], "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        pass
    return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()


def convert(name):
    base = os.path.splitext(name)[0]
    src = os.path.join(SRC, name)
    full_p = os.path.join(OUT, "full", base + ".webp")
    thumb_p = os.path.join(OUT, "thumb", base + ".webp")
    try:
        with Image.open(src) as img:
            when = taken_at(img, src)
            img = ImageOps.exif_transpose(img).convert("RGB")
            w, h = img.size
            if not os.path.exists(full_p):
                big = img.copy()
                big.thumbnail((FULL, FULL), Image.LANCZOS)
                big.save(full_p, "WEBP", quality=78, method=4)
            if not os.path.exists(thumb_p):
                small = img.copy()
                small.thumbnail((THUMB, THUMB), Image.LANCZOS)
                small.save(thumb_p, "WEBP", quality=70, method=4)
        return {"id": base, "t": when, "w": w, "h": h}
    except Exception as e:
        print("skip", name, e, file=sys.stderr)
        return None


def main():
    os.makedirs(os.path.join(OUT, "full"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "thumb"), exist_ok=True)
    names = sorted(n for n in os.listdir(SRC) if os.path.splitext(n)[1].lower() in EXTS)
    print(f"{len(names)} photos to process", flush=True)
    results = []
    with ProcessPoolExecutor() as ex:
        for i, r in enumerate(ex.map(convert, names, chunksize=8), 1):
            if r:
                results.append(r)
            if i % 100 == 0:
                print(f"{i}/{len(names)}", flush=True)
    results.sort(key=lambda r: r["t"])
    with open(os.path.join(OUT, "photos.js"), "w", encoding="utf-8") as f:
        f.write("window.PHOTOS = " + json.dumps(results, separators=(",", ":")) + ";\n")
    print(f"done: {len(results)} photos")


if __name__ == "__main__":
    main()
