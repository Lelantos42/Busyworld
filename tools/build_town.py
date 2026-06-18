#!/usr/bin/env python3
"""
Town generator for Busyworld.

Single source of truth for the town layout. It:
  1. Bakes a ground texture (grass + sidewalks + plaza + road) -> assets/ground/town_ground.png
  2. Emits godot/data/town_layout.json  (buildings, props, named places, collisions, homes)
  3. Renders a full composite preview -> tools/_montages/town_preview.png  (for fast iteration)

Godot reads town_layout.json and reproduces the same scene with Y-sorted sprites
and collisions, so the preview closely matches the in-engine result.

Run:  python3 tools/build_town.py
"""
import os, json, random
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
MW, MH = 104, 88                     # map size in tiles
W, H = MW * TILE, MH * TILE          # pixels

def load(path):
    return Image.open(path).convert("RGBA")

def size(rel):
    return Image.open(os.path.join(ASSETS, rel)).size

# ---- ground tiles (verified plain fills: uniform grass + light clean pavement) ----
grass_tiles = [load(os.path.join(GROUND, f"ME_Singles_Terrains_and_Fences_32x32_Grass_1_{i}.png"))
               for i in (9, 10, 11, 12, 13, 16, 17, 20)]
walk_tile = load(os.path.join(GROUND, "ME_Singles_City_Terrains_32x32_Sidewalk_1_25.png"))
walk_tile2 = load(os.path.join(GROUND, "ME_Singles_City_Terrains_32x32_Sidewalk_1_27.png"))
road_tiles = [load(os.path.join(GROUND, f"ME_Singles_City_Terrains_32x32_Asphalt_1_Variation_{i}.png"))
              for i in (16, 18, 20, 21)]

# material grid: 'g'=grass 's'=sidewalk 'r'=road
grid = [['g'] * MW for _ in range(MH)]

def fill_rect(tx0, ty0, tx1, ty1, mat):
    for ty in range(max(0, ty0), min(MH, ty1)):
        for tx in range(max(0, tx0), min(MW, tx1)):
            grid[ty][tx] = mat

# ---------- TOWN SPEC (tile coordinates) ----------
CX, CY = MW // 2, MH // 2            # (52, 44)  plaza center

# Central plaza (sidewalk) with fountain — kept open and visible
PLAZA = (CX - 10, CY - 8, CX + 10, CY + 8)       # tx0,ty0,tx1,ty1
fill_rect(*PLAZA, 's')

# Cross avenues of sidewalk through the plaza, reaching map edges
fill_rect(CX - 3, 2, CX + 3, MH - 2, 's')        # vertical avenue (main)
fill_rect(3, CY - 3, MW - 3, CY + 3, 's')        # horizontal avenue (main)

# Shop-front sidewalk (south of plaza, in front of the south shop row)
fill_rect(8, 58, MW - 8, 60, 's')
# South asphalt road for cars, with sidewalk edges
fill_rect(6, MH - 6, MW - 6, MH - 4, 'r')
fill_rect(6, MH - 7, MW - 6, MH - 6, 's')
# connectors: plaza -> shop-front sidewalk, and shop-front -> south road
for ax in (26, 52, 78):
    fill_rect(ax - 1, CY + 8, ax + 1, 60, 's')
for ax in (20, 52, 86):
    fill_rect(ax - 1, 60, ax + 1, MH - 7, 's')

# ---------- bake ground ----------
def bake_ground():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    for ty in range(MH):
        for tx in range(MW):
            m = grid[ty][tx]
            if m == 'g':
                t = grass_tiles[(tx * 7 + ty * 13) % len(grass_tiles)]
                # flip tiles pseudo-randomly to break the diagonal moire
                fx = (tx * 5 + ty * 3) % 2
                fy = (tx * 3 + ty * 7) % 2
                if fx: t = t.transpose(Image.FLIP_LEFT_RIGHT)
                if fy: t = t.transpose(Image.FLIP_TOP_BOTTOM)
            elif m == 's':
                t = walk_tile if (tx + ty) % 5 else walk_tile2
            else:
                t = road_tiles[(tx * 3 + ty) % len(road_tiles)]
            img.alpha_composite(t, (tx * TILE, ty * TILE))
    img.save(OUTPNG)
    print("baked ground:", OUTPNG, img.size)
    return img

# ---------- buildings & places ----------
buildings = []   # dicts: name, file, bx,by (baseline bottom-center px), w,h, place, tags, role
places = []
homes = []
collisions = []  # extra rect collisions [x,y,w,h]

def px(tx, ty):  # tile center-ish to px
    return tx * TILE, ty * TILE

def add_building(name, file, center_tx, base_ty, place=None, tags=None, role=None, home=False):
    rel = file
    w, h = size(rel)
    bx = center_tx * TILE
    by = base_ty * TILE
    b = {"name": name, "file": rel, "bx": bx, "by": by, "w": w, "h": h,
         "place": place or name, "tags": tags or [], "role": role}
    buildings.append(b)
    # named place at the door (bottom-center, a bit in front)
    if place or role:
        places.append({"name": place or name, "x": bx, "y": by + 18,
                       "type": "workplace" if role else "building",
                       "tags": tags or [], "role": role})
    if home:
        homes.append({"x": bx, "y": by + 22, "building": name})
    return b

# NORTH ROW: civic + residences (tall buildings ok, plaza sits in front/south) ---
add_building("Town Hall", "buildings/house_victorian_4.png", 52, 33,
             place="Town Hall", role="mayor",
             tags=["grand", "civic", "the seat of town government", "a clock tower"])
add_building("The Inn", "buildings/house_victorian_1.png", 28, 33,
             place="The Inn", role="innkeeper", home=True,
             tags=["lively", "the social heart of town", "music and chatter", "warm lamplight"])
add_building("Maple Residence", "buildings/house_victorian_3.png", 76, 33,
             place="Maple Residence", home=True, tags=["a tall townhouse", "flower boxes in the windows"])

# SOUTH SHOP ROW: workplaces facing the plaza (short buildings) ------------------
add_building("General Store", "props/mall_1.png", 26, 63,
             place="General Store", role="shopkeeper", home=True,
             tags=["busy", "shelves of goods", "a welcoming green shopfront"])
add_building("Bakery", "buildings/house_country.png", 52, 63,
             place="Bakery", role="baker", home=True,
             tags=["cozy", "smells of fresh bread", "warm light in the windows"])
add_building("Clinic", "buildings/house_victorian_5.png", 78, 63,
             place="Clinic", role="doctor", home=True,
             tags=["calm", "clean white walls", "a healing place"])

# FLANKING workplaces on the avenues / corners ----------------------------------
add_building("Workshop", "buildings/house_victorian_7.png", 9, 40,
             place="Workshop", role="builder", tags=["tools and timber", "the sound of sawing"])
add_building("Schoolhouse", "buildings/house_victorian_6.png", 95, 40,
             place="Schoolhouse", role="teacher", tags=["a small bell", "a chalkboard"])
add_building("Farmhouse", "buildings/house_country.png", 13, 80,
             place="Farm", role="farmer", home=True,
             tags=["fields of crops", "a red barn", "the smell of hay"])
add_building("Art Studio", "buildings/house_victorian_7.png", 92, 80,
             place="Art Studio", role="artist", home=True,
             tags=["colorful", "canvases drying", "paint-spattered floor"])

# ---------- scatter props (trees, lamps, flowers, benches, cars) ----------
props = []
import glob
tree_files = sorted(glob.glob(os.path.join(ASSETS, "props/tree_*.png")))
tree_rel = ["props/" + os.path.basename(f) for f in tree_files]
flower_rel = ["props/" + os.path.basename(f) for f in sorted(glob.glob(os.path.join(ASSETS, "props/flower_*.png")))]
lamp_rel = ["props/" + os.path.basename(f) for f in sorted(glob.glob(os.path.join(ASSETS, "props/lamp_*.png")))]
bench_rel = ["props/" + os.path.basename(f) for f in sorted(glob.glob(os.path.join(ASSETS, "props/bench_*.png")))]
car_rel = ["props/" + os.path.basename(f) for f in sorted(glob.glob(os.path.join(ASSETS, "props/car_*.png")))]
fountain_rel = "props/fountain_1.png"

def building_rects():
    rects = []
    for b in buildings:
        rects.append((b["bx"] - b["w"]/2, b["by"] - b["h"], b["w"], b["h"]))
    return rects

def overlaps_any(x, y, pad, rects):
    for rx, ry, rw, rh in rects:
        if (rx - pad) < x < (rx + rw + pad) and (ry - pad) < y < (ry + rh + pad):
            return True
    return False

def add_prop(rel, bx, by, collide=False, crad=10):
    w, h = size(rel)
    props.append({"file": rel, "bx": bx, "by": by, "w": w, "h": h,
                  "collide": collide, "crad": crad})

# Fountain at plaza center
fw, fh = size(fountain_rel)
add_prop(fountain_rel, CX * TILE, CY * TILE + 8, collide=True, crad=22)

brects = building_rects()

# Trees: line the avenues + scatter on grass
def is_grass(tx, ty):
    return 0 <= tx < MW and 0 <= ty < MH and grid[ty][tx] == 'g'

tree_spots = []
for ty in range(2, MH - 2, 3):
    for tx in range(2, MW - 2, 3):
        x, y = tx * TILE + TILE//2, ty * TILE + TILE
        if not is_grass(tx, ty):
            continue
        # keep near-but-not-on paths and off buildings
        near_path = any(grid[min(MH-1,max(0,ty+dy))][min(MW-1,max(0,tx+dx))] in 'sr'
                        for dy in (-1,0,1) for dx in (-1,0,1))
        if overlaps_any(x, y, 24, brects):
            continue
        r = random.random()
        if near_path and r < 0.45:
            tree_spots.append((x, y))
        elif (not near_path) and r < 0.30:
            tree_spots.append((x, y))
for (x, y) in tree_spots:
    add_prop(random.choice(tree_rel), x, y, collide=True, crad=12)

# Lamps along the main avenues
for ty in range(6, MH - 6, 6):
    for tx in (CX - 3, CX + 3):
        x, y = tx * TILE + 16, ty * TILE + TILE
        if grid[ty][tx] == 'g' and not overlaps_any(x, y, 12, brects):
            add_prop(random.choice(lamp_rel), x, y, collide=True, crad=6)
for tx in range(8, MW - 6, 8):
    for ty in (CY - 3, CY + 3):
        x, y = tx * TILE + 16, ty * TILE + TILE
        if grid[ty][tx] == 'g' and not overlaps_any(x, y, 12, brects):
            add_prop(random.choice(lamp_rel), x, y, collide=True, crad=6)

# Benches + flowers framing the plaza (plaza is CX+-10, CY+-8)
for tx in (CX - 8, CX + 7):
    for ty in (CY - 6, CY + 5):
        add_prop(random.choice(bench_rel), tx*TILE, ty*TILE+TILE, collide=True, crad=10)
for tx in range(CX - 9, CX + 10, 3):
    add_prop(random.choice(flower_rel), tx*TILE, (CY-8)*TILE+TILE, collide=False)
    add_prop(random.choice(flower_rel), tx*TILE, (CY+7)*TILE+TILE, collide=False)

# A few parked cars along the south road
for tx in range(14, MW - 14, 12):
    add_prop(random.choice(car_rel), tx*TILE, (MH-4)*TILE, collide=True, crad=14)

# ---------- named non-building places ----------
places.append({"name": "Town Plaza", "x": CX*TILE, "y": CY*TILE, "type": "plaza",
               "tags": ["sunlit", "a splashing fountain", "the gathering place of the town"], "role": None})
places.append({"name": "The Park", "x": 22*TILE, "y": 20*TILE, "type": "park", "role": "gardener",
               "tags": ["green and shady", "birdsong", "benches under the trees"]})
places.append({"name": "Market Road", "x": CX*TILE, "y": (MH-5)*TILE, "type": "road",
               "tags": ["the main road into town"], "role": None})

spawn = [CX*TILE, CY*TILE + 60]

# ---------- collisions for buildings (ground slab) ----------
for b in buildings:
    slab_h = min(int(b["h"] * 0.34), 150)
    collisions.append({"x": b["bx"] - b["w"]*0.42, "y": b["by"] - slab_h,
                       "w": b["w"]*0.84, "h": slab_h})

layout = {
    "tile": TILE, "map_px": [W, H], "town_name": "Busyworld",
    "ground_texture": "ground/town_ground.png",
    "buildings": buildings, "props": props, "places": places,
    "homes": homes, "collisions": collisions, "spawn": spawn,
}

def render_preview(ground):
    img = ground.copy()
    # composite buildings + props sorted by baseline y
    items = []
    for b in buildings:
        items.append((b["by"], b["file"], b["bx"], b["by"], b["w"], b["h"]))
    for p in props:
        items.append((p["by"], p["file"], p["bx"], p["by"], p["w"], p["h"]))
    items.sort(key=lambda t: t[0])
    for _, file, bx, by, w, h in items:
        im = load(os.path.join(ASSETS, file))
        img.alpha_composite(im, (int(bx - w/2), int(by - h)))
    # downscale for quick viewing
    prev = img.resize((img.width//2, img.height//2), Image.NEAREST)
    prev.convert("RGB").save(PREVIEW)
    print("preview:", PREVIEW, prev.size)

if __name__ == "__main__":
    ground = bake_ground()
    with open(LAYOUT, "w") as fh:
        json.dump(layout, fh, indent=1)
    print("layout:", LAYOUT, "| buildings", len(buildings), "props", len(props),
          "places", len(places), "homes", len(homes))
    render_preview(ground)
