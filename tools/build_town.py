#!/usr/bin/env python3
"""Town generator for Busyworld (4-citizen founding town).

Single source of truth for the layout. Bakes the ground texture, writes
godot/data/town_layout.json (buildings, props, places, collisions, doors,
interiors), and renders a composite preview for fast iteration.

The town: a central plaza, a grand Town Center (where the citizens meet), a Print
Shop (the print-on-demand venture they work), and four homes — one per citizen.

Run:  python3 tools/build_town.py
"""
import os, json, random, glob
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
random.seed(7)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "godot/assets")
GROUND = os.path.join(ASSETS, "ground")
OUTPNG = os.path.join(GROUND, "town_ground.png")
LAYOUT = os.path.join(ROOT, "godot/data/town_layout.json")
PREVIEW = os.path.join(ROOT, "tools/_montages/town_preview.png")

TILE = 32
MW, MH = 76, 54
W, H = MW * TILE, MH * TILE
CX, CY = 38, 27

def load(p): return Image.open(p).convert("RGBA")
def size(rel): return Image.open(os.path.join(ASSETS, rel)).size

grass_tiles = [load(os.path.join(GROUND, f"ME_Singles_Terrains_and_Fences_32x32_Grass_1_{i}.png"))
               for i in (9, 10, 11, 12, 13, 16, 17, 20)]
walk_tile = load(os.path.join(GROUND, "ME_Singles_City_Terrains_32x32_Sidewalk_1_25.png"))
walk_tile2 = load(os.path.join(GROUND, "ME_Singles_City_Terrains_32x32_Sidewalk_1_27.png"))
road_tiles = [load(os.path.join(GROUND, f"ME_Singles_City_Terrains_32x32_Asphalt_1_Variation_{i}.png"))
              for i in (16, 18, 20, 21)]

grid = [['g'] * MW for _ in range(MH)]
def fill_rect(tx0, ty0, tx1, ty1, mat):
    for ty in range(max(0, ty0), min(MH, ty1)):
        for tx in range(max(0, tx0), min(MW, tx1)):
            grid[ty][tx] = mat

# --- paths ---
PLAZA = (CX - 8, CY - 5, CX + 9, CY + 6)
fill_rect(*PLAZA, 's')
fill_rect(CX - 2, 2, CX + 2, MH - 2, 's')          # vertical avenue
fill_rect(3, CY - 2, MW - 3, CY + 2, 's')          # horizontal avenue
fill_rect(5, MH - 5, MW - 5, MH - 3, 'r')          # south road (cars)
fill_rect(5, MH - 6, MW - 5, MH - 5, 's')

def bake_ground():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    for ty in range(MH):
        for tx in range(MW):
            m = grid[ty][tx]
            if m == 'g':
                t = grass_tiles[(tx * 7 + ty * 13) % len(grass_tiles)]
                if (tx * 5 + ty * 3) % 2: t = t.transpose(Image.FLIP_LEFT_RIGHT)
                if (tx * 3 + ty * 7) % 2: t = t.transpose(Image.FLIP_TOP_BOTTOM)
            elif m == 's':
                t = walk_tile if (tx + ty) % 5 else walk_tile2
            else:
                t = road_tiles[(tx * 3 + ty) % len(road_tiles)]
            img.alpha_composite(t, (tx * TILE, ty * TILE))
    img.save(OUTPNG)
    print("baked ground:", OUTPNG, img.size)
    return img

# --- buildings ---
buildings, places, homes, collisions = [], [], [], []

def add_building(name, file, cx, by_ty, place=None, role=None, tags=None,
                 home=False, door_dx=0, door_type="door_1", interior=""):
    w, h = size(file)
    bx, by = cx * TILE, by_ty * TILE
    door_x = bx + door_dx
    buildings.append({"name": name, "file": file, "bx": bx, "by": by, "w": w, "h": h,
                      "place": place or name, "tags": tags or [], "role": role,
                      "door": [door_x, by], "door_type": door_type, "interior": interior})
    if place or role:
        places.append({"name": place or name, "x": door_x, "y": by + 24,
                       "type": "workplace" if role else "building", "tags": tags or [], "role": role})
    if home:
        homes.append({"x": door_x, "y": by + 26, "building": name})

# Town Center (grand civic hall) — north of the plaza
add_building("Town Center", "buildings/civic_townhall.png", CX, 23,
             place="Town Center", role="coordinator", door_type="door_big_1", interior="int_hall",
             tags=["a grand civic hall", "where the town meets to plan", "notice boards and a long table"])
# Print Shop (the print-on-demand venture) — south of the plaza
add_building("Print Shop", "buildings/work_printshop.png", CX, 47,
             place="Print Shop", role="designer", door_type="door_big_1", interior="int_studio",
             tags=["workstations and screens", "the hum of a printer", "racks of finished products"])
# Four homes, one per citizen
add_building("House 1", "buildings/house_onestory.png", 13, 20,
             place="House 1", home=True, interior="int_home1", tags=["a tidy one-storey home"])
add_building("House 2", "buildings/house_japanese.png", 63, 20,
             place="House 2", home=True, interior="int_japanese", tags=["a calm home with paper screens"])
add_building("House 3", "buildings/house_country.png", 13, 48,
             place="House 3", home=True, interior="int_condo", tags=["a cosy country house"])
add_building("House 4", "buildings/house_terraced.png", 63, 48,
             place="House 4", home=True, interior="int_home1", tags=["a snug terraced house"])

# --- carve sidewalk spurs to every door ---
def nearest_sidewalk(start, max_r=24):
    sx, sy = start
    for r in range(1, max_r):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if abs(dx) != r and abs(dy) != r: continue
                x, y = sx + dx, sy + dy
                if 0 <= x < MW and 0 <= y < MH and grid[y][x] == 's':
                    return (x, y)
    return None

def carve(a, b):
    (ax, ay), (bx_, by_) = a, b
    x, y = ax, ay
    while y != by_:
        if grid[y][x] != 'r': grid[y][x] = 's'
        y += 1 if by_ > y else -1
    while x != bx_:
        if grid[y][x] != 'r': grid[y][x] = 's'
        x += 1 if bx_ > x else -1

for b in buildings:
    dtx = int(b["door"][0] // TILE)
    dty = min(int(b["door"][1] // TILE) + 1, MH - 1)
    if grid[dty][dtx] != 's':
        near = nearest_sidewalk((dtx, dty))
        if near: carve((dtx, dty), near)
        grid[dty][dtx] = 's'

# --- props ---
props = []
def add_prop(rel, bx, by, collide=False, crad=10):
    w, h = size(rel)
    props.append({"file": rel, "bx": bx, "by": by, "w": w, "h": h, "collide": collide, "crad": crad})

tree_rel = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/tree_*.png"))]
flower_rel = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/flower_*.png"))]
lamp_rel = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/lamp_*.png"))]
bench_rel = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/bench_*.png"))]
car_left = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/car_left_*.png"))]
car_right = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/car_right_*.png"))]

def is_grass(tx, ty): return 0 <= tx < MW and 0 <= ty < MH and grid[ty][tx] == 'g'
def brects():
    return [(b["bx"] - b["w"]/2, b["by"] - b["h"], b["w"], b["h"]) for b in buildings]
def overlaps(x, y, pad, rects):
    return any((rx-pad) < x < (rx+rw+pad) and (ry-pad) < y < (ry+rh+pad) for rx, ry, rw, rh in rects)

add_prop("props/fountain_1.png", CX*TILE, CY*TILE + 8, collide=True, crad=22)
BR = brects()

# trees scattered on grass, off paths and buildings
for ty in range(2, MH-2, 3):
    for tx in range(2, MW-2, 3):
        x, y = tx*TILE + 16, ty*TILE + TILE
        if not is_grass(tx, ty) or overlaps(x, y, 26, BR): continue
        near_path = any(grid[min(MH-1,max(0,ty+dy))][min(MW-1,max(0,tx+dx))] in 'sr'
                        for dy in (-1,0,1) for dx in (-1,0,1))
        if (near_path and random.random() < 0.4) or (not near_path and random.random() < 0.25):
            add_prop(random.choice(tree_rel), x, y, collide=True, crad=12)

# plaza furnishings: benches, flowers, corner lamps
for tx in (CX-7, CX-2, CX+3, CX+8):
    for ty in (CY-4, CY+4):
        add_prop(random.choice(bench_rel), tx*TILE, ty*TILE+TILE, collide=True, crad=10)
for tx in range(CX-8, CX+9, 3):
    add_prop(random.choice(flower_rel), tx*TILE, (CY-5)*TILE+TILE, collide=False)
    add_prop(random.choice(flower_rel), tx*TILE, (CY+6)*TILE+TILE, collide=False)
for (lx, ly) in [(CX-8, CY-5), (CX+8, CY-5), (CX-8, CY+5), (CX+8, CY+5)]:
    add_prop(random.choice(lamp_rel), lx*TILE+16, ly*TILE+TILE, collide=True, crad=6)

# side-view cars along the south road
road_y = (MH-4) * TILE
for k, tx in enumerate(range(12, MW-12, 12)):
    pool = car_right if k % 2 else car_left
    if pool: add_prop(random.choice(pool), tx*TILE, road_y, collide=True, crad=20)

# --- named places ---
places.append({"name": "Town Plaza", "x": CX*TILE, "y": CY*TILE, "type": "plaza",
               "tags": ["sunlit", "a splashing fountain", "the heart of the town"], "role": None})
places.append({"name": "Market Road", "x": CX*TILE, "y": (MH-4)*TILE, "type": "road",
               "tags": ["the road out of town"], "role": None})
spawn = [CX*TILE, CY*TILE + 40]

# --- building collision slabs ---
for b in buildings:
    slab = min(int(b["h"] * 0.32), 130)
    collisions.append({"x": b["bx"] - b["w"]*0.42, "y": b["by"] - slab, "w": b["w"]*0.84, "h": slab})

layout = {"tile": TILE, "map_px": [W, H], "town_name": "Busyworld",
          "ground_texture": "ground/town_ground.png", "buildings": buildings, "props": props,
          "places": places, "homes": homes, "collisions": collisions, "spawn": spawn}

def render_preview(ground):
    img = ground.copy()
    items = [(b["by"], b["file"], b["bx"], b["by"], b["w"], b["h"]) for b in buildings]
    items += [(p["by"], p["file"], p["bx"], p["by"], p["w"], p["h"]) for p in props]
    items.sort(key=lambda t: t[0])
    for _, f, bx, by, w, h in items:
        img.alpha_composite(load(os.path.join(ASSETS, f)), (int(bx-w/2), int(by-h)))
    for b in buildings:                       # closed-door frame
        dp = os.path.join(ASSETS, "doors", b["door_type"] + ".png")
        if os.path.exists(dp):
            ds = load(dp); fw = 32
            fr = ds.crop((0, 0, fw, ds.height))
            img.alpha_composite(fr, (int(b["door"][0]-fw/2), int(b["door"][1]-ds.height)))
    img.resize((img.width//2, img.height//2), Image.NEAREST).convert("RGB").save(PREVIEW)
    print("preview:", PREVIEW)

if __name__ == "__main__":
    g = bake_ground()
    json.dump(layout, open(LAYOUT, "w"), indent=1)
    print("layout:", LAYOUT, "| buildings", len(buildings), "props", len(props), "homes", len(homes))
    render_preview(g)
