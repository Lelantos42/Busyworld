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
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
random.seed(7)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "godot/assets")
GROUND = os.path.join(ASSETS, "ground")
OUTPNG = os.path.join(GROUND, "town_ground.png")
LAYOUT = os.path.join(ROOT, "godot/data/town_layout.json")
SCENE = os.path.join(ROOT, "godot/scenes/Main.tscn")
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
DOORS = json.load(open(os.path.join(ROOT, "godot/data/doors.json"))) if \
    os.path.exists(os.path.join(ROOT, "godot/data/doors.json")) else {}

def add_building(name, file, cx, by_ty, place=None, role=None, tags=None,
                 home=False, interior=""):
    w, h = size(file)
    bx, by = cx * TILE, by_ty * TILE
    # matched animated door for this building
    da = DOORS.get(file, {})
    door_anim = {}
    if da:
        door_anim = {"sheet": da["sheet"], "fw": da["fw"], "fh": da["fh"], "n": da["n"],
                     "ox": da["ox"], "oy": da["oy"]}
        door_x = bx + da["ox"] + da["fw"] / 2.0       # ground point at the door
    else:
        door_x = bx
    buildings.append({"name": name, "file": file, "bx": bx, "by": by, "w": w, "h": h,
                      "place": place or name, "tags": tags or [], "role": role,
                      "door": [door_x, by], "door_anim": door_anim, "interior": interior})
    if place or role:
        places.append({"name": place or name, "x": door_x, "y": by + 24,
                       "type": "workplace" if role else "building", "tags": tags or [], "role": role})
    if home:
        homes.append({"x": door_x, "y": by + 26, "building": name})

# Town Center (the civic building where the citizens gather) — north of the plaza
add_building("Town Center", "buildings/civic_townhall.png", CX, 21,
             place="Town Center", role="coordinator", interior="int_condo",
             tags=["a civic building", "where the town meets to plan", "open and welcoming"])
# Print Shop (the print-on-demand venture) — south of the plaza
add_building("Print Shop", "buildings/work_printshop.png", CX, 47,
             place="Print Shop", role="designer", interior="int_studio",
             tags=["workstations and screens", "the hum of a printer", "racks of finished products"])
# Four homes — identical garage-free townhouses, mirror-placed for symmetry
add_building("House 1", "buildings/house_japanese.png", 14, 20,
             place="House 1", home=True, interior="int_japanese", tags=["a calm home with paper screens"])
add_building("House 2", "buildings/house_japanese.png", 62, 20,
             place="House 2", home=True, interior="int_japanese", tags=["a calm home with paper screens"])
add_building("House 3", "buildings/house_japanese.png", 14, 47,
             place="House 3", home=True, interior="int_home1", tags=["a calm home with paper screens"])
add_building("House 4", "buildings/house_japanese.png", 62, 47,
             place="House 4", home=True, interior="int_home1", tags=["a calm home with paper screens"])

# ---- per-building geometry: solid wall footprint + the door's front tile ----
def opaque_bbox(file):
    a = np.array(load(os.path.join(ASSETS, file)))[..., 3]
    ys, xs = np.where(a > 40)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1

for b in buildings:
    da = DOORS.get(b["file"], {})
    ol, otp, orr, obt = opaque_bbox(b["file"])
    ground_img = int(da.get("ground_y", b["h"]))            # door bottom (image coords)
    left, top = b["bx"] - b["w"] / 2, b["by"] - b["h"]
    # SOLID = full wall footprint, top down to the door's ground; the porch /
    # threshold below the door stays walkable so citizens can reach the door.
    collisions.append({"x": left + ol, "y": top + otp,
                       "w": orr - ol, "h": max(TILE, ground_img - otp)})
    door_cx = left + int(da.get("cx", b["w"] / 2))
    front_y = top + ground_img + TILE                       # walkable tile in front of door
    b["_front"] = (door_cx, front_y)
    # the same geometry, but stored *relative to the baseline* so the scene nodes
    # (which the founder can drag in the editor) carry it and the game recomputes
    # collision / door / entry from each node's live position.
    b["_foot"] = (ol - b["w"] / 2.0, otp - b["h"], orr - ol, max(TILE, ground_img - otp))
    b["_front_rel"] = (door_cx - b["bx"], front_y - b["by"])
    for p in places:                                        # enter at the door, not the base
        if p["name"] == b["place"]:
            p["x"], p["y"] = door_cx, front_y
    for hm in homes:
        if hm["building"] == b["name"]:
            hm["x"], hm["y"] = door_cx, front_y + 4

# ---- carve a clean sidewalk from each door straight to the network ----
def nearest_path(start, max_r=30):
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

door_corridors = []     # (tx, ty0, ty1) keep-clear strips in front of each door
for b in buildings:
    fx, fy = b["_front"]
    dtx, fty = int(fx // TILE), int(fy // TILE)
    if grid[fty][dtx] != 's':
        near = nearest_path((dtx, fty))
        if near:
            carve((dtx, fty), near)
    grid[fty][dtx] = 's'
    door_corridors.append((dtx, fty - 1, fty + 2))

# ---- props: deliberate + symmetric, never blocking paths or doors ----
props = []
def add_prop(rel, bx, by, collide=False, crad=10):
    w, h = size(rel)
    props.append({"file": rel, "bx": bx, "by": by, "w": w, "h": h, "collide": collide, "crad": crad})

trees = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/tree_*.png"))]
flowers = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/flower_*.png"))]
lamp, bench = "props/lamp_1.png", "props/bench_1.png"
car_left = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/car_left_*.png"))]
car_right = ["props/" + os.path.basename(f) for f in sorted(glob.glob(ASSETS + "/props/car_right_*.png"))]

def is_grass(tx, ty): return 0 <= tx < MW and 0 <= ty < MH and grid[ty][tx] == 'g'
BR = [(b["bx"]-b["w"]/2, b["by"]-b["h"], b["w"], b["h"]) for b in buildings]
def on_building(px, py, pad):
    return any((rx-pad) < px < (rx+rw+pad) and (ry-pad) < py < (ry+rh+pad) for rx, ry, rw, rh in BR)
def TP(tx, ty): return tx*TILE + TILE//2, ty*TILE + TILE     # prop baseline at a tile

# fountain dead-centre
add_prop("props/fountain_1.png", CX*TILE, CY*TILE + 8, collide=True, crad=22)

# plaza benches — one per quadrant, facing the fountain (symmetric)
for sx in (-5, 5):
    for sy in (-3, 3):
        add_prop(bench, *TP(CX+sx, CY+sy), collide=True, crad=12)

# plaza flowers — neat rows along the top & bottom edges (planters only, symmetric)
planters = [f for f in flowers if not f.endswith("flower_7.png")] or flowers
for tx in (CX-7, CX-5, CX-3, CX+3, CX+5, CX+7):
    fl = planters[abs(tx-CX) % len(planters)]       # mirror sides use the same planter
    add_prop(fl, *TP(tx, CY-5), collide=False)
    add_prop(fl, *TP(tx, CY+5), collide=False)

# lamps — symmetric: 4 plaza corners + evenly spaced pairs along the avenues
def put_lamp(tx, ty):
    bx, by = tx*TILE+16, ty*TILE+TILE
    if is_grass(tx, ty) and not on_building(bx, by, 6):
        add_prop(lamp, bx, by, collide=True, crad=6)
for (lx, ly) in [(CX-9, CY-6), (CX+9, CY-6), (CX-9, CY+6), (CX+9, CY+6)]:
    put_lamp(lx, ly)
for ly in (10, 16, 38, 44):
    put_lamp(CX-4, ly); put_lamp(CX+4, ly)
for lx in (10, 22, 54, 66):
    put_lamp(lx, CY-4); put_lamp(lx, CY+4)

# trees — symmetric, framing the town; sparse, never on paths/doors/buildings,
# and kept a couple of tiles back from the plaza so it stays open
def near_path(tx, ty):
    return any(0 <= tx+dx < MW and 0 <= ty+dy < MH and grid[ty+dy][tx+dx] in 'sr'
               for dy in (-1, 0, 1) for dx in (-1, 0, 1))
def in_corridor(tx, ty):
    return any(abs(tx-cx) <= 1 and y0-1 <= ty <= y1 for (cx, y0, y1) in door_corridors)
def tree_ok(tx, ty):
    if not is_grass(tx, ty) or near_path(tx, ty) or in_corridor(tx, ty):
        return False
    if on_building(*TP(tx, ty), 14):
        return False
    return abs(tx-CX) > 6 or abs(ty-CY) > 8        # keep the plaza surroundings open
placed = set()
for ty in range(3, MH-2, 4):
    for tx in range(3, CX-1, 4):
        rx = 2*CX - tx
        if tree_ok(tx, ty) and tree_ok(rx, ty) and (tx, ty) not in placed:
            idx = (tx*5 + ty*7) % len(trees)
            add_prop(trees[idx], *TP(tx, ty), collide=True, crad=13)
            add_prop(trees[idx], *TP(rx, ty), collide=True, crad=13)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    placed.add((tx+dx, ty+dy))

# side-view cars parked along the south road (symmetric)
road_y = (MH-4) * TILE
for tx in (12, 24):
    add_prop(car_right[tx % len(car_right)], tx*TILE, road_y, collide=True, crad=20)
    add_prop(car_left[tx % len(car_left)], (MW-tx)*TILE, road_y, collide=True, crad=20)

# --- named places ---
places.append({"name": "Town Plaza", "x": CX*TILE, "y": CY*TILE, "type": "plaza",
               "tags": ["sunlit", "a splashing fountain", "the heart of the town"], "role": None})
places.append({"name": "Market Road", "x": CX*TILE, "y": (MH-4)*TILE, "type": "road",
               "tags": ["the road out of town"], "role": None})
spawn = [CX*TILE, CY*TILE + 40]

layout = {"tile": TILE, "map_px": [W, H], "town_name": "Busyworld",
          "ground_texture": "ground/town_ground.png", "buildings": buildings, "props": props,
          "places": places, "homes": homes, "collisions": collisions, "spawn": spawn}

# --- editable Godot scene ---------------------------------------------------
# Emit scenes/Main.tscn with a real, hand-editable node for every building and
# prop (a Sprite2D placed at its baseline). The game (World.gd) reads each node's
# live position + metadata, so the founder can nudge anything in the Godot editor
# and it takes effect on the next run — no need to touch Python for fine placement.
def _num(v):
    f = float(v)
    return str(int(f)) if f == int(f) else ("%g" % f)
def _vec2(x, y): return "Vector2(%s, %s)" % (_num(x), _num(y))
def _rect2(x, y, w, h): return "Rect2(%s, %s, %s, %s)" % (_num(x), _num(y), _num(w), _num(h))
def _qs(s): return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
def _qarr(items): return "[" + ", ".join(_qs(i) for i in items) + "]"

def _prop_base(rel):
    stem = os.path.splitext(os.path.basename(rel))[0]
    for key, name in (("tree", "Tree"), ("flower", "Flower"), ("lamp", "Lamp"),
                      ("bench", "Bench"), ("car", "Car"), ("fountain", "Fountain")):
        if stem.startswith(key):
            return name
    return "".join(c for c in stem.title() if c.isalnum()) or "Prop"

def _sanitize(name):
    out = name
    for ch in '.:@/"%':
        out = out.replace(ch, "_")
    return out.strip() or "Node"

def write_scene():
    # unique textures -> ext_resource ids (ground first, then buildings, then props)
    texids, order = {}, []
    def texid(rel):
        if rel not in texids:
            texids[rel] = "tex%d" % len(texids)
            order.append(rel)
        return texids[rel]
    gid = texid("ground/town_ground.png")
    for b in buildings: texid(b["file"])
    for p in props: texid(p["file"])

    ext = ['[ext_resource type="Script" path="res://scripts/World.gd" id="1_world"]']
    for rel in order:
        ext.append('[ext_resource type="Texture2D" path="res://assets/%s" id="%s"]'
                    % (rel, texids[rel]))

    used = {}
    def uniq(base):
        base = _sanitize(base)
        n = used.get(base, 0); used[base] = n + 1
        return base if n == 0 else "%s%d" % (base, n + 1)

    L = ['[gd_scene load_steps=%d format=3 uid="uid://busyworld_main"]' % (len(ext) + 1), ""]
    L += ext + [""]

    # root World node carries the map-wide constants
    L += ['[node name="World" type="Node2D"]',
          'script = ExtResource("1_world")',
          "metadata/tile = %d" % TILE,
          "metadata/map_px = %s" % _vec2(W, H),
          "metadata/town_name = %s" % _qs("Busyworld"),
          "metadata/spawn = %s" % _vec2(spawn[0], spawn[1]), ""]

    # baked ground (paths/roads/grass) sits behind everything
    L += ['[node name="Ground" type="Sprite2D" parent="."]',
          "z_index = -100", "centered = false",
          'texture = ExtResource("%s")' % gid, ""]

    # Y-sorted layer holding every building, prop and (at runtime) citizen
    L += ['[node name="Entities" type="Node2D" parent="."]', "y_sort_enabled = true", ""]

    home_names = set(hm["building"] for hm in homes)
    bld_places = set(b["place"] for b in buildings)
    for b in buildings:
        rx, ry, fw, fh = b["_foot"]
        frx, fry = b["_front_rel"]
        da = b.get("door_anim", {})
        L += ['[node name="%s" type="Sprite2D" parent="Entities"]' % uniq(b["place"]),
              "position = %s" % _vec2(b["bx"], b["by"]),
              "centered = false",
              "offset = %s" % _vec2(-b["w"] / 2.0, -b["h"]),
              'texture = ExtResource("%s")' % texids[b["file"]],
              'metadata/kind = "building"',
              "metadata/place = %s" % _qs(b["place"]),
              "metadata/role = %s" % _qs(b.get("role") or ""),
              "metadata/interior = %s" % _qs(b.get("interior", "")),
              "metadata/home = %s" % ("true" if b["name"] in home_names else "false"),
              "metadata/w = %s" % _num(b["w"]),
              "metadata/h = %s" % _num(b["h"]),
              "metadata/foot = %s" % _rect2(rx, ry, fw, fh),
              "metadata/front = %s" % _vec2(frx, fry),
              "metadata/tags = %s" % _qarr(b.get("tags", []))]
        if da:
            L += ["metadata/door_sheet = %s" % _qs(da["sheet"]),
                  "metadata/door_fw = %s" % _num(da["fw"]),
                  "metadata/door_fh = %s" % _num(da["fh"]),
                  "metadata/door_n = %s" % _num(da["n"]),
                  "metadata/door_ox = %s" % _num(da["ox"]),
                  "metadata/door_oy = %s" % _num(da["oy"])]
        L.append("")

    for p in props:
        L += ['[node name="%s" type="Sprite2D" parent="Entities"]' % uniq(_prop_base(p["file"])),
              "position = %s" % _vec2(p["bx"], p["by"]),
              "centered = false",
              "offset = %s" % _vec2(-p["w"] / 2.0, -p["h"]),
              'texture = ExtResource("%s")' % texids[p["file"]],
              'metadata/kind = "prop"',
              "metadata/collide = %s" % ("true" if p.get("collide") else "false"),
              "metadata/crad = %s" % _num(p.get("crad", 10)), ""]

    # standalone named places (plaza, roads…) — Marker2D the founder can move too
    L += ['[node name="Places" type="Node2D" parent="."]', ""]
    for p in places:
        if p["name"] in bld_places:
            continue
        L += ['[node name="%s" type="Marker2D" parent="Places"]' % uniq(p["name"]),
              "position = %s" % _vec2(p["x"], p["y"]),
              'metadata/kind = "place"',
              "metadata/place = %s" % _qs(p["name"]),
              "metadata/ptype = %s" % _qs(p.get("type", "")),
              "metadata/role = %s" % _qs(p.get("role") or ""),
              "metadata/tags = %s" % _qarr(p.get("tags", [])), ""]

    open(SCENE, "w").write("\n".join(L))
    print("scene:", SCENE, "| (overwrites hand edits — re-run resets placement)")

def render_preview(ground):
    img = ground.copy()
    items = [(b["by"], b["file"], b["bx"], b["by"], b["w"], b["h"]) for b in buildings]
    items += [(p["by"], p["file"], p["bx"], p["by"], p["w"], p["h"]) for p in props]
    items.sort(key=lambda t: t[0])
    for _, f, bx, by, w, h in items:
        img.alpha_composite(load(os.path.join(ASSETS, f)), (int(bx-w/2), int(by-h)))
    # (doors are drawn into the building images; the animated overlays match them)
    img.resize((img.width//2, img.height//2), Image.NEAREST).convert("RGB").save(PREVIEW)
    print("preview:", PREVIEW)

if __name__ == "__main__":
    import sys
    g = bake_ground()
    json.dump(layout, open(LAYOUT, "w"), indent=1)
    print("layout:", LAYOUT, "| buildings", len(buildings), "props", len(props), "homes", len(homes))
    if "--no-scene" not in sys.argv:        # pass --no-scene to keep your editor edits
        write_scene()
    render_preview(g)
