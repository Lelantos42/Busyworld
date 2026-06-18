#!/usr/bin/env python3
"""Copy the extra assets for the town-fix pass: side-view cars, animated door
spritesheets, and pre-made interior room designs."""
import os, glob, shutil
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INT = os.path.join(ROOT, "GameAssets/moderninteriors-win (1)")
EXT = os.path.join(ROOT, "GameAssets/modernexteriors-win (1)/Modern_Exteriors_32x32")
SING = os.path.join(EXT, "Modern_Exteriors_Complete_Singles_32x32")
ASSETS = os.path.join(ROOT, "godot/assets")

def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)

# 1) side-view cars
n = 0
for side in ("Left", "Right"):
    for i in range(1, 7):
        src = os.path.join(SING, f"ME_Singles_Vehicles_32x32_Car_{side}_{i}.png")
        if os.path.exists(src):
            cp(src, os.path.join(ASSETS, "props", f"car_{side.lower()}_{i}.png")); n += 1
print("side cars copied:", n)

# 2) animated door spritesheets (5 frames, 32x64 each for the single doors)
door_src = os.path.join(INT, "3_Animated_objects/32x32/spritesheets")
doors = ["animated_door_1_32x32.png", "animated_door_2_32x32.png",
         "animated_door_3_32x32.png", "animated_door_big_1_32x32.png",
         "animated_door_condominium_1_32x32.png"]
dn = 0
for d in doors:
    src = os.path.join(door_src, d)
    if os.path.exists(src):
        cp(src, os.path.join(ASSETS, "doors", d.replace("_32x32", "")))
        print("  door:", d, Image.open(src).size); dn += 1
print("doors copied:", dn)

# 3) interior room designs (the furnished "preview" images, 32x32)
designs = {
    "home_generic": "Generic_Home_Designs",
    "home_japanese": "Japanese_Interiors_Home_Designs",
    "home_condo": "Condominium_Designs",
    "shop_icecream": "Ice-Cream_Shop_Designs",
    "shop_gym": "Gym_Designs",
    "shop_museum": "Museum_Designs",
    "shop_tvstudio": "TV_Studio_Designs",
}
inn = 0
for name, folder in designs.items():
    previews = sorted(glob.glob(os.path.join(INT, "6_Home_Designs", folder, "32x32", "*preview*.png")))
    if not previews:
        # some folders name the combined image differently; grab first 32x32 png
        previews = sorted(glob.glob(os.path.join(INT, "6_Home_Designs", folder, "32x32", "*.png")))
    if previews:
        cp(previews[0], os.path.join(ASSETS, "interiors", name + ".png"))
        print(f"  interior {name}: {os.path.basename(previews[0])} {Image.open(previews[0]).size}")
        inn += 1
print("interiors copied:", inn)
