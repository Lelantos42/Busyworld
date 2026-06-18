#!/usr/bin/env python3
"""Match each building's animated door to its drawn door position.

Each LimeZu building already has its door drawn into the facade. The matching
animated door sheet's first frame IS that same door, so we template-match frame 0
against the building image to find the exact pixel position, then the animated
door overlays the drawn one seamlessly and opens when triggered.

Writes godot/data/doors.json: building_file -> {sheet, fw, fh, n, ox, oy}
where (ox, oy) is the door's top-left offset from the building baseline (bottom-
centre).  Also a verification montage.
"""
import os, json, glob
import numpy as np
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB = os.path.join(ROOT, "godot/assets/buildings")
AD = os.path.join(ROOT, "godot/assets/doors")
OUT = os.path.join(ROOT, "godot/data/doors.json")
MONT = os.path.join(ROOT, "tools/_montages/doors_match.png")
FW = 64    # all these animated doors are 2 tiles wide

# building file -> door sheet file (both relative to assets/)
PAIRS = {
    "buildings/house_onestory.png": "doors/door_onestory.png",
    "buildings/house_japanese.png": "doors/door_japanese.png",
    "buildings/house_modern.png":   "doors/door_modern.png",
    "buildings/civic_townhall.png": "doors/door_civic.png",
    "buildings/work_printshop.png": "doors/door_shopping.png",
}

def match(bld, f0):
    """Find (x,y) top-left in bld minimizing SSD over f0's opaque pixels.
    Search the lower-middle of the building (where doors live)."""
    bw, bh = bld.size
    fw, fh = f0.size
    ba = np.asarray(bld).astype(int)
    fa = np.asarray(f0).astype(int)
    mask = fa[..., 3] > 60
    frgb = fa[..., :3]
    best = (1e18, bw//2 - fw//2, bh - fh)
    x0, x1 = 0, bw - fw
    y0, y1 = int(bh * 0.35), bh - fh        # doors sit in the lower part
    for y in range(y0, y1 + 1, 1):
        for x in range(x0, x1 + 1, 1):
            win = ba[y:y+fh, x:x+fw, :3]
            diff = (win - frgb)
            sse = float((diff[mask] ** 2).mean())
            if sse < best[0]:
                best = (sse, x, y)
    return best

def main():
    data = {}
    previews = []
    for bfile, dfile in PAIRS.items():
        bld = Image.open(os.path.join(ROOT, "godot/assets", bfile)).convert("RGBA")
        sheet = Image.open(os.path.join(ROOT, "godot/assets", dfile)).convert("RGBA")
        fh = sheet.height
        n = sheet.width // FW
        f0 = sheet.crop((0, 0, FW, fh))
        sse, mx, my = match(bld, f0)
        bw, bh = bld.size
        ox = mx - bw // 2          # offset from baseline (bottom-centre)
        oy = my - bh
        data[bfile] = {"sheet": dfile, "fw": FW, "fh": fh, "n": n, "ox": ox, "oy": oy,
                       "cx": mx + FW // 2, "ground_y": my + fh}
        print(f"{os.path.basename(bfile):22s} door@({mx},{my}) sse={sse:.0f} n={n} fh={fh}")
        # preview: building with frame0 outlined at the match
        pv = bld.copy()
        d = ImageDraw.Draw(pv)
        d.rectangle([mx, my, mx+FW-1, my+fh-1], outline=(0, 255, 0, 255), width=2)
        d.text((4, 4), os.path.basename(bfile), fill=(255, 235, 120, 255))
        previews.append(pv)
    json.dump(data, open(OUT, "w"), indent=1)
    print("wrote", OUT)
    # montage
    cw = max(p.width for p in previews) + 10
    ch = max(p.height for p in previews) + 10
    cols = 3
    rows = (len(previews) + cols - 1)//cols
    M = Image.new("RGBA", (cols*cw, rows*ch), (28, 30, 36, 255))
    for i, p in enumerate(previews):
        r, c = divmod(i, cols)
        M.alpha_composite(p, (c*cw+5, r*ch+5))
    M.convert("RGB").save(MONT)
    print("montage:", MONT, M.size)

if __name__ == "__main__":
    main()
