#!/usr/bin/env python3
"""Build editable, furniture-node interiors for Busyworld.

The old interiors were single flattened LimeZu "Home Design" renders — you
couldn't move anything. This rebuilds each room from individual furniture
*singles* so every piece is a draggable Godot node with its own collision,
over a paintable floor TileMapLayer (same approach as the town ground).

Per design it writes:
  godot/scenes/interiors/<design>.tscn   — Shell (TileMapLayer) + Furniture nodes
  godot/data/interiors.json              — what World.gd needs (floor cells, door…)
and shared shell art:
  godot/assets/interiors/int_atlas.png + godot/data/int_tileset.tres
  godot/assets/interiors/furniture/<name>.png   (curated singles)

Run:  python3 tools/build_interior_scenes.py
"""
import os, json, struct, shutil
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = os.path.join(ROOT, "godot/assets/interiors")
FURN = os.path.join(AI, "furniture")
SRC = os.path.join(ROOT, "GameAssets/moderninteriors-win (1)/1_Interiors/32x32")
SINGLES = os.path.join(SRC, "Theme_Sorter_Shadowless_Singles_32x32")
SUB = os.path.join(SRC, "Room_Bulder_subfiles_32x32")
ATLAS = os.path.join(AI, "int_atlas.png")
TILESET = os.path.join(ROOT, "godot/data/int_tileset.tres")
SCENES = os.path.join(ROOT, "godot/scenes/interiors")
IJSON = os.path.join(ROOT, "godot/data/interiors.json")
TILE = 32

# ---------------------------------------------------------------- shell tiles
# (col,row) picks from the LimeZu Room_Builder sheets -> our small floor/wall atlas
FLOOR_SHEET = os.path.join(SUB, "Room_Builder_Floors_32x32.png")
WALL_SHEET = os.path.join(SUB, "Room_Builder_3d_walls_32x32.png")
#   atlas index -> (sheet, col, row)
SHELL = [
    ("floor_wood",  FLOOR_SHEET, 4, 8),
    ("floor_cream", FLOOR_SHEET, 4, 2),
    ("floor_gray",  FLOOR_SHEET, 12, 4),
    ("floor_tan",   FLOOR_SHEET, 0, 6),
    ("floor_white", FLOOR_SHEET, 0, 4),
    ("wall",        WALL_SHEET,  4, 4),   # brown wall face + baseboard (meets floor)
    ("wall_top",    WALL_SHEET,  4, 0),   # north wall cap
]
SHELL_IDX = {name: i for i, (name, *_ ) in enumerate(SHELL)}

def crop_tile(sheet_path, col, row):
    im = Image.open(sheet_path).convert("RGBA")
    return im.crop((col * TILE, row * TILE, col * TILE + TILE, row * TILE + TILE))

def build_atlas():
    atlas = Image.new("RGBA", (len(SHELL) * TILE, TILE), (0, 0, 0, 0))
    for i, (_, sheet, col, row) in enumerate(SHELL):
        atlas.alpha_composite(crop_tile(sheet, col, row), (i * TILE, 0))
    atlas.save(ATLAS)
    print("atlas:", ATLAS, atlas.size)

def write_tileset():
    lines = ['[gd_resource type="TileSet" format=3 load_steps=3]', "",
             '[ext_resource type="Texture2D" path="res://assets/interiors/int_atlas.png" id="1_atlas"]', "",
             '[sub_resource type="TileSetAtlasSource" id="atlas0"]',
             'texture = ExtResource("1_atlas")',
             "texture_region_size = Vector2i(%d, %d)" % (TILE, TILE)]
    for i in range(len(SHELL)):
        lines.append("%d:0/0 = 0" % i)
    lines += ["", "[resource]", "tile_size = Vector2i(%d, %d)" % (TILE, TILE),
              'sources/0 = SubResource("atlas0")', ""]
    open(TILESET, "w").write("\n".join(lines))
    print("tileset:", TILESET)

def tile_map_data(cells):
    out = bytearray(struct.pack("<H", 0))
    for tx, ty, col in cells:
        out += struct.pack("<hhHHHH", tx, ty, 0, col, 0, 0)
    return ", ".join(str(b) for b in out)

# ---------------------------------------------------------------- furniture catalog
# name -> (theme folder, single index, collides?)
TH_LIVING = "2_Living_Room_Singles_Shadowless_32x32"
TH_JP = "20_Japanese_Interiors_Singles_Shadowless_32x32"
TH_STUDIO = "23_Television_and_Film_Studio_Singles_Shadowless_32x32"
CATALOG = {
    # living room / generic home
    "sofa":        (TH_LIVING, 22, True),
    "armchair":    (TH_LIVING, 19, True),
    "console":     (TH_LIVING, 52, True),
    "tv_console":  (TH_LIVING, 29, True),
    "bookshelf":   (TH_LIVING, 90, True),
    "plant_lg":    (TH_LIVING, 16, True),
    "plant_sm":    (TH_LIVING, 13, True),
    "floor_lamp":  (TH_LIVING, 79, True),
    "rug":         (TH_LIVING, 28, False),
    "wood_chair":  (TH_LIVING, 117, True),
    "side_table":  (TH_LIVING, 45, True),
    # japanese
    "jp_table":    (TH_JP, 19, True),
    "jp_futon":    (TH_JP, 77, True),
    "jp_shoji":    (TH_JP, 61, True),
    "jp_bonsai":   (TH_JP, 56, True),
    "jp_lantern":  (TH_JP, 17, True),
    "jp_cabinet":  (TH_JP, 69, True),
    "jp_scroll":   (TH_JP, 105, False),
    "jp_sofa":     (TH_JP, 48, True),
    "jp_zabuton":  (TH_JP, 41, False),
    # studio / print shop
    "printer":     (TH_STUDIO, 56, True),
    "printer2":    (TH_STUDIO, 60, True),
    "monitor":     (TH_STUDIO, 41, True),
    "server_rack": (TH_STUDIO, 75, True),
    "desk_chair":  (TH_STUDIO, 28, True),
    "stool":       (TH_STUDIO, 32, True),
    "camera":      (TH_STUDIO, 1, True),
    "studio_light":(TH_STUDIO, 5, True),
    "green_screen":(TH_STUDIO, 25, True),
    "prod_rack":   (TH_STUDIO, 76, True),
}

def single_path(theme, idx):
    folder = os.path.join(SINGLES, theme)
    # singles are named <Theme>_<n>.png; find by trailing index
    for f in os.listdir(folder):
        if f.endswith("_%d.png" % idx):
            return os.path.join(folder, f)
    raise FileNotFoundError("%s #%d" % (theme, idx))

def curate_furniture():
    os.makedirs(FURN, exist_ok=True)
    meta = {}     # name -> {w,h, foot:(rx,ry,fw,fh), collide}
    for name, (theme, idx, collide) in CATALOG.items():
        im = Image.open(single_path(theme, idx)).convert("RGBA")
        im.save(os.path.join(FURN, name + ".png"))
        w, h = im.size
        a = np.array(im)[..., 3]
        ys, xs = np.where(a > 30)
        if len(xs) == 0:
            foot = (-w / 2.0, -h, w, h)
        else:
            ox0, oy0, ox1, oy1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
            # footprint = alpha bbox, but no taller than ~2 tiles up from the base
            top = max(oy0, oy1 - 2 * TILE)
            foot = (ox0 - w / 2.0, top - h, ox1 - ox0, oy1 - top)
        meta[name] = {"w": w, "h": h, "foot": foot, "collide": collide}
    print("furniture:", len(meta), "items ->", FURN)
    return meta

# ---------------------------------------------------------------- room layouts
# design -> dict(floor, tw, th, items[(name,tx,ty)], entry(tx,ty), spots[(tx,ty)])
# items are placed by the bottom-centre of tile (tx,ty); walls ring the room.
LAYOUTS = {
    "int_home1": {  # generic family living room
        "floor": "floor_wood", "tw": 14, "th": 11,
        "items": [
            ("rug", 6, 6), ("sofa", 6, 2), ("console", 6, 8), ("tv_console", 11, 8),
            ("armchair", 2, 5), ("armchair", 10, 5), ("bookshelf", 1, 2),
            ("plant_lg", 12, 2), ("plant_sm", 1, 9), ("floor_lamp", 12, 9),
            ("side_table", 9, 2),
        ],
        "entry": (6, 9), "spots": [(4, 6), (8, 6), (6, 4), (3, 8), (9, 8)],
    },
    "int_japanese": {  # calm tatami home
        "floor": "floor_tan", "tw": 14, "th": 11,
        "items": [
            ("jp_zabuton", 6, 6), ("jp_table", 6, 6), ("jp_sofa", 6, 3),
            ("jp_futon", 11, 3), ("jp_cabinet", 1, 3), ("jp_shoji", 3, 1),
            ("jp_shoji", 9, 1), ("jp_bonsai", 12, 2), ("jp_bonsai", 1, 9),
            ("jp_lantern", 2, 6), ("jp_lantern", 11, 6), ("jp_scroll", 6, 1),
        ],
        "entry": (6, 9), "spots": [(4, 6), (8, 6), (6, 5), (3, 8), (9, 8)],
    },
    "int_condo": {  # Town Center — meeting commons
        "floor": "floor_cream", "tw": 16, "th": 11,
        "items": [
            ("rug", 8, 6), ("sofa", 5, 3), ("sofa", 11, 3), ("console", 8, 8),
            ("armchair", 3, 7), ("armchair", 13, 7), ("plant_lg", 1, 2),
            ("plant_lg", 14, 2), ("bookshelf", 8, 1), ("floor_lamp", 1, 9),
            ("floor_lamp", 14, 9),
        ],
        "entry": (8, 9), "spots": [(5, 6), (11, 6), (8, 4), (4, 8), (12, 8)],
    },
    "int_studio": {  # Print Shop — the venture
        "floor": "floor_gray", "tw": 14, "th": 11,
        "items": [
            ("console", 3, 3), ("monitor", 3, 3), ("desk_chair", 3, 5),
            ("console", 7, 3), ("monitor", 7, 3), ("desk_chair", 7, 5),
            ("printer", 11, 2), ("printer2", 11, 5), ("server_rack", 1, 2),
            ("prod_rack", 12, 8), ("prod_rack", 2, 8), ("green_screen", 6, 8),
            ("studio_light", 1, 6),
        ],
        "entry": (7, 9), "spots": [(3, 4), (7, 4), (10, 6), (5, 7), (9, 8)],
    },
}

def room_cells(floor_idx, tw, th, door_tx=None):
    """Floor inside a uniform 1-tile wall ring; north wall gets a cap row above.
    The bottom-wall tile under door_tx is left as floor so the exit door reads as
    an opening."""
    cells = []
    floor_tiles = []
    for ty in range(th):
        for tx in range(tw):
            border = tx == 0 or tx == tw - 1 or ty == 0 or ty == th - 1
            doorway = ty == th - 1 and tx == door_tx
            if border and not doorway:
                col = SHELL_IDX["wall"]
            else:
                col = floor_idx
                if 0 < tx < tw - 1 and 0 < ty < th - 1:
                    floor_tiles.append([tx, ty])
            cells.append((tx, ty, col))
    # a wall-top cap row sitting just above the north wall, for a bit of height
    for tx in range(tw):
        cells.append((tx, -1, SHELL_IDX["wall_top"]))
    return cells, floor_tiles

def qstr(s): return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
def vec2(x, y): return "Vector2(%s, %s)" % (_n(x), _n(y))
def rect2(x, y, w, h): return "Rect2(%s, %s, %s, %s)" % (_n(x), _n(y), _n(w), _n(h))
def _n(v):
    f = float(v); return str(int(f)) if f == int(f) else ("%g" % f)

def write_scene(design, lay, fmeta):
    tw, th = lay["tw"], lay["th"]
    cells, floor_tiles = room_cells(SHELL_IDX[lay["floor"]], tw, th, lay["entry"][0])
    used = sorted({n for n, *_ in lay["items"]})
    texid = {n: "f%d" % i for i, n in enumerate(used)}

    ext = ['[ext_resource type="TileSet" path="res://data/int_tileset.tres" id="ts"]']
    for n in used:
        ext.append('[ext_resource type="Texture2D" path="res://assets/interiors/furniture/%s.png" id="%s"]'
                    % (n, texid[n]))

    L = ['[gd_scene load_steps=%d format=3 uid="uid://busyworld_%s"]' % (len(ext) + 1, design), ""]
    L += ext + [""]
    L += ['[node name="%s" type="Node2D"]' % design,
          "metadata/tile = %d" % TILE, "metadata/tw = %d" % tw, "metadata/th = %d" % th,
          "metadata/entry = %s" % vec2(*lay["entry"]), ""]
    # paintable floor + walls
    L += ['[node name="Shell" type="TileMapLayer" parent="."]',
          "z_index = -20",
          "tile_map_data = PackedByteArray(%s)" % tile_map_data(cells),
          'tile_set = ExtResource("ts")', ""]
    # draggable furniture (Y-sorted among themselves, kept behind citizens via z)
    L += ['[node name="Furniture" type="Node2D" parent="."]',
          "y_sort_enabled = true", "z_index = -10", ""]
    nm = {}
    for (n, tx, ty) in lay["items"]:
        m = fmeta[n]
        i = nm.get(n, 0) + 1; nm[n] = i
        node = n if i == 1 else "%s%d" % (n, i)
        px = tx * TILE + TILE / 2.0
        py = (ty + 1) * TILE
        rx, ry, fw, fh = m["foot"]
        L += ['[node name="%s" type="Sprite2D" parent="Furniture"]' % node,
              "position = %s" % vec2(px, py),
              "centered = false",
              "offset = %s" % vec2(-m["w"] / 2.0, -m["h"]),
              'texture = ExtResource("%s")' % texid[n],
              'metadata/kind = "furniture"',
              "metadata/collide = %s" % ("true" if m["collide"] else "false"),
              "metadata/foot = %s" % rect2(rx, ry, fw, fh), ""]
    os.makedirs(SCENES, exist_ok=True)
    open(os.path.join(SCENES, design + ".tscn"), "w").write("\n".join(L))
    return floor_tiles

def main():
    build_atlas()
    write_tileset()
    fmeta = curate_furniture()
    data = {}
    for design, lay in LAYOUTS.items():
        floor_tiles = write_scene(design, lay, fmeta)
        tw, th = lay["tw"], lay["th"]
        data[design] = {
            "scene": "scenes/interiors/%s.tscn" % design, "tile": TILE,
            "tw": tw, "th": th, "floor": floor_tiles, "entry": list(lay["entry"]),
            "door_px": [int(lay["entry"][0] * TILE + TILE / 2), (th - 1) * TILE + TILE // 2],
            "spots": [list(s) for s in lay["spots"]],
        }
        print("scene:", design, "%dx%d" % (tw, th), "items:", len(lay["items"]))
    json.dump(data, open(IJSON, "w"))
    print("wrote", IJSON, "designs:", list(data.keys()))

if __name__ == "__main__":
    main()
