#!/usr/bin/env python3
"""Compute correct walkable floors for each interior design.

Each LimeZu home design ships as a composite "preview" plus a furniture layer.
We derive a per-tile walkable grid:  walkable = inside the building footprint
(preview alpha) AND no furniture on it (furniture-layer alpha) AND not the top
wall band AND not the 1-tile edge.  This is what stops citizens walking on the
counter — they can only stand on actual floor.

Outputs godot/data/interiors.json and a verification montage.
"""
import os, json, glob
import numpy as np
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = os.path.join(ROOT, "godot/assets/interiors")
OUT = os.path.join(ROOT, "godot/data/interiors.json")
MONT = os.path.join(ROOT, "tools/_montages/interiors_walk.png")
TILE = 32

# per-design tuning: how many tile rows the top wall occupies
WALL_TOP = {
    "int_home1": 4, "int_japanese": 4, "int_condo": 5, "int_condo2": 4,
    "int_studio": 4, "int_hall": 6,
}
SIDE = 1     # tiles of side wall
BOTTOM = 1   # tiles of bottom wall

def tile_alpha(arr, tx, ty):
    sub = arr[ty*TILE:(ty+1)*TILE, tx*TILE:(tx+1)*TILE]
    return float((sub > 40).mean()) if sub.size else 0.0

def compute(name):
    prev = Image.open(os.path.join(AI, name + ".png")).convert("RGBA")
    furn = Image.open(os.path.join(AI, name + "_furn.png")).convert("RGBA")
    w, h = prev.size
    tw, th = w // TILE, h // TILE
    pa = np.array(prev)[..., 3]
    fa = np.array(furn.resize(prev.size))[..., 3]
    wall_top = WALL_TOP.get(name, 4)
    walk = []
    grid = [[False]*tw for _ in range(th)]
    for ty in range(th):
        for tx in range(tw):
            inside = tile_alpha(pa, tx, ty) > 0.55
            has_furn = tile_alpha(fa, tx, ty) > 0.22
            edge = tx < SIDE or tx >= tw-SIDE or ty < wall_top or ty >= th-BOTTOM
            if inside and not has_furn and not edge:
                grid[ty][tx] = True
                walk.append([tx, ty])
    # entry: a walkable tile nearest bottom-centre; door pixel at bottom-centre
    cx = tw // 2
    entry = min(walk, key=lambda c: (th-1-c[1]) + abs(c[0]-cx)) if walk else [cx, th-2]
    # spots: spread-out walkable tiles for citizens to occupy
    spots = []
    if walk:
        step = max(1, len(walk)//6)
        spots = [walk[i] for i in range(0, len(walk), step)][:6]
    return {
        "image": "interiors/%s.png" % name, "tile": TILE,
        "w": w, "h": h, "tw": tw, "th": th,
        "walkable": walk, "entry": entry, "spots": spots,
        "door_px": [cx*TILE + TILE//2, h - 4],
    }, grid

def main():
    designs = sorted(set(os.path.basename(f)[:-4] for f in glob.glob(AI + "/int_*.png")
                         if not f.endswith("_furn.png")))
    designs = [d for d in designs if not d.endswith("_furn")]
    data = {}
    previews = []
    for name in designs:
        info, grid = compute(name)
        data[name] = info
        # visualization
        im = Image.open(os.path.join(AI, name + ".png")).convert("RGBA")
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for ty in range(info["th"]):
            for tx in range(info["tw"]):
                col = (0, 220, 0, 90) if grid[ty][tx] else None
                if col:
                    d.rectangle([tx*TILE, ty*TILE, tx*TILE+TILE-1, ty*TILE+TILE-1], fill=col)
        im.alpha_composite(ov)
        d2 = ImageDraw.Draw(im)
        d2.text((4, 4), name, fill=(255, 235, 120, 255))
        previews.append(im)
    with open(OUT, "w") as fh:
        json.dump(data, fh)
    print("wrote", OUT, "designs:", list(data.keys()))
    for n, info in data.items():
        print(f"  {n}: {info['tw']}x{info['th']} tiles, {len(info['walkable'])} walkable")
    # montage of walkable overlays
    cols = 3
    cw = max(i.width for i in previews) + 12
    ch = max(i.height for i in previews) + 12
    rows = (len(previews)+cols-1)//cols
    M = Image.new("RGBA", (cols*cw, rows*ch), (30, 32, 38, 255))
    for i, im in enumerate(previews):
        r, c = divmod(i, cols)
        M.alpha_composite(im, (c*cw+6, r*ch+6))
    M.convert("RGB").save(MONT)
    print("montage:", MONT, M.size)

if __name__ == "__main__":
    main()
