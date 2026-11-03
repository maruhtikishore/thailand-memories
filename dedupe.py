"""Remove duplicate photos from the gallery manifest (photos/photos.js).

Uses a perceptual hash (dHash) of the thumbnails, so the same picture saved twice
(e.g. HEIC + JPEG copy, re-sent/edited copy) is detected. Only the manifest changes:
original photos and the converted files are never deleted.
Usage: python dedupe.py [max_hamming_distance]   (default 3 = very conservative)
"""
import json
import os
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = os.path.join(HERE, "photos")
MAX_DIST = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def dhash(path, size=16):
    with Image.open(path) as im:
        im = im.convert("L").resize((size + 1, size), Image.LANCZOS)
        px = list(im.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (px[r * (size + 1) + c] > px[r * (size + 1) + c + 1])
    return bits


def main():
    src = open(os.path.join(PHOTOS, "photos.js"), encoding="utf-8").read()
    photos = json.loads(re.search(r"=\s*(\[.*\]);", src, re.S).group(1))
    for p in photos:
        p["h_"] = dhash(os.path.join(PHOTOS, "thumb", p["id"] + ".webp"))
        p["size_"] = os.path.getsize(os.path.join(PHOTOS, "full", p["id"] + ".webp"))

    # Bucket by hash prefix is unsafe for fuzzy matching, so compare against kept photos
    # within the same day (duplicates are almost always taken/saved close together).
    kept, dropped = [], []
    by_day = {}
    for p in sorted(photos, key=lambda p: -p["size_"]):  # prefer the sharper/larger copy
        day = p["t"][:10]
        group = by_day.setdefault(day, [])
        dup = next(
            (k for k in group
             if abs(k["w"] / k["h"] - p["w"] / p["h"]) < 0.05
             and bin(k["h_"] ^ p["h_"]).count("1") <= MAX_DIST),
            None,
        )
        if dup:
            dropped.append({"dropped": p["id"], "duplicate_of": dup["id"]})
        else:
            group.append(p)
            kept.append(p)

    kept.sort(key=lambda p: p["t"])
    for p in kept:
        p.pop("h_"); p.pop("size_")
    with open(os.path.join(PHOTOS, "photos.js"), "w", encoding="utf-8") as f:
        f.write("window.PHOTOS = " + json.dumps(kept, separators=(",", ":")) + ";\n")
    with open(os.path.join(HERE, "duplicates_removed.json"), "w", encoding="utf-8") as f:
        json.dump(dropped, f, indent=1)
    print(f"{len(photos)} photos -> kept {len(kept)}, removed {len(dropped)} duplicates")


if __name__ == "__main__":
    main()
