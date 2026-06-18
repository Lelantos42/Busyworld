#!/usr/bin/env python3
"""
Select & copy a curated subset of the LimeZu Modern Exteriors/Interiors asset
pack into the Godot project, and emit verification montages + a manifest.

Run:  python3 tools/select_assets.py
"""
import os, glob, shutil, json
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT32 = os.path.join(ROOT, "GameAssets/modernexteriors-win (1)/Modern_Exteriors_32x32/Modern_Exteriors_Complete_Singles_32x32")
PREMADE = os.path.join(ROOT, "GameAssets/moderninteriors-win (1)/2_Characters/Character_Generator/0_Premade_Characters/48x48")
OUT = os.path.join(ROOT, "godot/assets")
MONT = os.path.join(ROOT, "tools/_montages")
os.makedirs(MONT, exist_ok=True)

def S(name): return os.path.join(EXT32, name)
def exists(name): return os.path.exists(S(name))

# ---- Curated ground candidates (we'll pick finals after viewing the montage) ----
GROUND_GLOBS = {
    "grass":    "ME_Singles_Terrains_and_Fences_32x32_Grass_1_*.png",
    "sidewalk": "ME_Singles_City_Terrains_32x32_Sidewalk_1_*.png",
    "asphalt":  "ME_Singles_City_Terrains_32x32_Asphalt_1_Variation_*.png",
    "water":    "ME_Singles_Terrains_and_Fences_32x32_Deep_Water_1_*.png",
    "sand":     "ME_Singles_City_Terrains_32x32_Sand_1_*.png",
}

# ---- Curated props/buildings (logical name -> source basename or glob) ----
PROP_EXACT = {
    # hero buildings
    "house_victorian_1": "24_Additional_Houses_Victorian_House_1_32x32.png",
    "house_victorian_2": "24_Additional_Houses_Victorian_House_2_32x32.png",
    "house_victorian_3": "24_Additional_Houses_Victorian_House_3_32x32.png",
    "house_victorian_4": "24_Additional_Houses_Victorian_House_4_32x32.png",
    "house_victorian_5": "24_Additional_Houses_Victorian_House_5_32x32.png",
    "house_victorian_6": "24_Additional_Houses_Victorian_House_6_32x32.png",
    "house_victorian_7": "24_Additional_Houses_Victorian_House_7_32x32.png",
    "house_country":     "24_Additional_Houses_Country_House_32x32.png",
    # civic / commercial
    "fountain_1": "ME_Singles_City_Props_32x32_Fountain_1.png",
    "fountain_2": "ME_Singles_City_Props_32x32_Fountain_2.png",
    # furniture / street props
    "bench_1": "ME_Singles_City_Props_32x32_Bench_1.png",
    "bench_2": "ME_Singles_City_Props_32x32_Bench_2.png",
}
PROP_GLOBS = {
    "tree":      ("ME_Singles_Camping_32x32_Tree_*.png", 24),
    "flower":    ("ME_Singles_City_Props_32x32_Flower_Bush_*.png", 12),
    "lamp":      ("ME_Singles_City_Props_32x32_*Lamp*.png", 8),
    "streetlight": ("ME_Singles_City_Props_32x32_*Street_Light*.png", 8),
    "bush":      ("ME_Singles_City_Props_32x32_Bush_*.png", 10),
    "mall":      ("ME_Singles_Shopping_Center_and_Markets_32x32_Mall_1.png", 2),
    "market_stall": ("ME_Singles_Shopping_Center_and_Markets_32x32_*Stand*.png", 8),
    "car":       ("ME_Singles_Vehicles_32x32_*Car*.png", 8),
    "sign":      ("ME_Singles_City_Props_32x32_*Sign*.png", 10),
}

def copy_glob(pattern, dest_dir, limit=9999, prefix=""):
    os.makedirs(dest_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(EXT32, pattern)))[:limit]
    copied = []
    for f in files:
        b = os.path.basename(f)
        dst = os.path.join(dest_dir, b)
        shutil.copy2(f, dst)
        copied.append(b)
    return copied

manifest = {"ground": {}, "props": {}, "characters": []}

# Ground
for key, pat in GROUND_GLOBS.items():
    copied = copy_glob(pat, os.path.join(OUT, "ground"), limit=28)
    manifest["ground"][key] = copied
    print(f"ground/{key}: {len(copied)} tiles")

# Exact props/buildings
for logical, src in PROP_EXACT.items():
    if exists(src):
        dest = os.path.join(OUT, "buildings" if "house" in logical or "mall" in logical else "props")
        os.makedirs(dest, exist_ok=True)
        shutil.copy2(S(src), os.path.join(dest, logical + ".png"))
        w, h = Image.open(S(src)).size
        manifest["props"][logical] = {"file": logical + ".png", "w": w, "h": h,
                                      "dir": os.path.basename(dest), "src": src}
    else:
        print("  MISSING exact:", src)

# Glob props
for logical, (pat, lim) in PROP_GLOBS.items():
    files = sorted(glob.glob(os.path.join(EXT32, pat)))[:lim]
    dest = os.path.join(OUT, "props")
    os.makedirs(dest, exist_ok=True)
    items = []
    for i, f in enumerate(files):
        name = f"{logical}_{i+1}.png"
        shutil.copy2(f, os.path.join(dest, name))
        w, h = Image.open(f).size
        items.append({"file": name, "w": w, "h": h, "src": os.path.basename(f)})
    manifest["props"][logical] = items
    print(f"props/{logical}: {len(items)}")

# Characters: copy all 20 premade sheets
os.makedirs(os.path.join(OUT, "characters"), exist_ok=True)
for f in sorted(glob.glob(os.path.join(PREMADE, "Premade_Character_48x48_*.png"))):
    b = os.path.basename(f)
    shutil.copy2(f, os.path.join(OUT, "characters", b))
    manifest["characters"].append(b)
print(f"characters: {len(manifest['characters'])} sheets")

with open(os.path.join(ROOT, "godot/data/asset_manifest.json"), "w") as fh:
    json.dump(manifest, fh, indent=2)

# ---------- Montages for verification ----------
def montage(files, cols, cell, out_path, label=True, bg=(40,44,52)):
    from PIL import ImageDraw
    if not files: return
    rows = (len(files) + cols - 1)//cols
    pad = 14
    cw, ch = cell+pad, cell+pad+ (12 if label else 0)
    img = Image.new("RGBA", (cols*cw, rows*ch), bg+(255,))
    d = ImageDraw.Draw(img)
    for i, (path, name) in enumerate(files):
        r, c = divmod(i, cols)
        try: im = Image.open(path).convert("RGBA")
        except: continue
        # scale to fit cell
        s = min(cell/im.width, cell/im.height)
        im2 = im.resize((max(1,int(im.width*s)), max(1,int(im.height*s))), Image.NEAREST)
        x = c*cw + (cw-im2.width)//2
        y = r*ch + (cell-im2.height)//2 + 6
        img.alpha_composite(im2, (x, y))
        if label:
            d.text((c*cw+2, r*ch+ch-12), name[:18], fill=(220,220,120,255))
    img.save(out_path)
    print("montage:", out_path, img.size)

# ground montage
gfiles = []
for key, pat in GROUND_GLOBS.items():
    for f in sorted(glob.glob(os.path.join(OUT, "ground", os.path.basename(pat).replace("*", "*"))))[:14]:
        gfiles.append((f, key+"/"+os.path.basename(f).split("_")[-1].replace(".png","")))
montage(gfiles, 14, 48, os.path.join(MONT, "ground.png"))

# props montage
pfiles = []
for f in sorted(glob.glob(os.path.join(OUT, "props", "*.png"))) + sorted(glob.glob(os.path.join(OUT, "buildings", "*.png"))):
    pfiles.append((f, os.path.basename(f).replace(".png","")))
montage(pfiles, 12, 80, os.path.join(MONT, "props.png"))

# characters montage: down-facing idle frame (row pair 1 -> y=96..., dir DOWN cols 18-23 frame0 -> col18)
cfiles = []
cdir = os.path.join(OUT, "characters")
for f in sorted(glob.glob(os.path.join(cdir, "*.png"))):
    im = Image.open(f).convert("RGBA")
    # idle DOWN frame0: pair index1 -> y0 = 1*96+28 = 124 ; col 18
    frame = im.crop((18*48, 124, 19*48, 124+68))
    tmp = os.path.join(MONT, "_c_"+os.path.basename(f))
    frame.save(tmp)
    cfiles.append((tmp, os.path.basename(f).replace("Premade_Character_48x48_","P").replace(".png","")))
montage(cfiles, 10, 68, os.path.join(MONT, "characters.png"))

print("DONE")
