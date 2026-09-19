"""Builds every generated file the Robot Guards mod ships.

Outputs, relative to the mod root (the parent of this tools/ folder):
  data/sprites.png                    the robots, a model a row, and the Robot Uplink
  data/people.png                     the game's people sheet with the stab vest taken off it
  data/materials.txt                  the game's Guard, Armed Guard and Dog Handler, redefined, and the uplink
  data/crookedguards_settings.txt     the game's own settings with corruption turned off
  data/language/base-language.txt     names, build-menu text and the tooltip
  thumbnail.png                       the mod's card image in the game's mod list

Usage: python gen_assets.py <the game's data folder, unpacked from main.dat>

The three guards are the game's own definitions read from its materials.txt,
so whatever the game says about a guard's speed, price or equipment is kept.
Three things change: the pictures, twice the Toughness, and DoesNotTire.
The script, data/scripts/RobotUplink.lua, is written by hand.
"""

import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import robots  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# The game measures a sprite sheet in 32-pixel cells. A person is two cells
# square, and its four pictures sit side by side: front, back, side, blink.
CELL = 32
KINDS = list(robots.KINDS)
GUARDS = ["Guard", "ArmedGuard", "DogHandler"]      # the kinds that are built tougher and never tire
MODELS = len(robots.MODELS)
ACROSS = 5                      # kinds to a row of the sheet
BLOCK = 8                       # cells a kind takes each way: four pictures across, four models down
# A save made with a mod that gave guards more pictures holds guards numbered
# past the four models, and a guard whose number has no picture is not drawn.
# So every number such a save can hold gets one, the four models in turn.
VARIANTS = 128
TOUGHER = 100000                # the game divides every blow by Toughness, so at this a blow does nothing that shows
UPLINK_AT = len(KINDS)          # the uplink's picture takes the slot after the last kind
UPLINK_PRICE = 1500

# The game draws a guard's stab vest over whatever the guard looks like, from a
# block of its people sheet cut to a person's shoulders, which on a robot is a
# dark bib across the chest and halfway up the head. Nobody but the three kinds
# of guard wears one, so the block is emptied: the vest still protects, and is
# still named on the guard, and nothing is drawn for it.
VEST_BLOCK = (1280, 384, 1536, 704)

# Every line of the game's settings that decides whether a guard turns. The
# counts are made too large to reach rather than zero, which the game may
# divide by.
NEVER = {
    "Minimum Gang Population (Cumulative)": "1000000",
    "Corrupt Every Nth Hired Guard": "1000000",
    "Chance to Corrupt One Guard Per Interval": "0.000000",
    "Minimum Wait Interval for Next Corruption (Days)": "1000000",
    "Crooked Guards to Normal Guards Ratio": "0.000000",
    "Crooked Guards to Normal Guards Ratio - with Staff Vetting": "0.000000",
}


def slot(k):
    """Where a kind's block starts on the sheet, in cells."""
    return (k % ACROSS) * BLOCK, (k // ACROSS) * BLOCK


def uplink_sprite():
    """A mast on a plinth with a dish and a cyan beacon, bottom-aligned."""
    up = 8
    im = Image.new("RGBA", (64 * up, 64 * up), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def box(x0, y0, x1, y1, fill, r=0):
        d.rounded_rectangle([x0 * up, y0 * up, x1 * up, y1 * up], radius=r * up, fill=fill)

    box(10, 57, 54, 62, (0, 0, 0, 90), 2)
    box(12, 46, 52, 60, robots.OUTLINE, 3)
    box(14, 48, 50, 58, robots.GUN, 2)
    box(14, 48, 50, 51, robots.GUN_HI, 2)
    for x in (18, 25, 32, 39):
        box(x, 53, x + 4, 55, robots.CYAN["core"])
    box(29, 14, 35, 48, robots.OUTLINE)
    box(30.5, 14, 33.5, 48, robots.STEEL)
    d.pieslice([14 * up, 12 * up, 50 * up, 48 * up], 200, 340, fill=robots.OUTLINE)
    d.pieslice([16.5 * up, 14.5 * up, 47.5 * up, 45.5 * up], 200, 340, fill=robots.STEEL_HI)
    d.ellipse([27 * up, 3 * up, 37 * up, 13 * up], fill=robots.OUTLINE)
    d.ellipse([28.8 * up, 4.8 * up, 35.2 * up, 11.2 * up], fill=robots.CYAN["core"])
    d.ellipse([30 * up, 5.5 * up, 32.5 * up, 8 * up], fill=robots.CYAN["hot"])
    return im.resize((64, 64), Image.LANCZOS)


def build_sprites():
    down = (len(KINDS) + 1 + ACROSS - 1) // ACROSS
    sheet = Image.new("RGBA", (ACROSS * BLOCK * CELL, down * BLOCK * CELL), (0, 0, 0, 0))
    for k, kind in enumerate(KINDS):
        x, y = slot(k)
        sheet.paste(robots.sheet(kind), (x * CELL, y * CELL))
    x, y = slot(UPLINK_AT)
    sheet.paste(uplink_sprite(), (x * CELL, y * CELL))
    return sheet


def build_thumbnail():
    im = Image.new("RGBA", (256, 256), (16, 18, 21, 255))
    for i, model in enumerate(robots.MODELS):
        big = model("front").resize((128, 128), Image.NEAREST)
        im.paste(big, ((i % 2) * 128, (i // 2) * 128), big)
    return im


def build_people(game):
    with Image.open(os.path.join(game, "people.png")) as sheet:
        sheet = sheet.convert("RGBA")
    box = VEST_BLOCK
    sheet.paste(Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0)), box[:2])
    return sheet


def game_object(materials, name):
    for block in re.findall(r"BEGIN Object\s.*?\nEND", materials, re.S):
        if re.search(r"^\s*Name\s+" + name + r"\s*$", block, re.M):
            return block
    raise SystemExit(f"the game's materials.txt has no {name}")


def robot_object(materials, kind, k):
    x, first_row = slot(k)
    lines = []
    for line in game_object(materials, kind).splitlines()[:-1]:
        tough = re.match(r"(\s*Toughness\s+)([\d.]+)", line)
        if tough and kind in GUARDS:
            line = f"{tough.group(1)}{float(tough.group(2)) * TOUGHER:.4f}"
        if re.match(r"\s*(Sprite|SpriteVariants)\s", line):
            continue
        lines.append(line.rstrip())
    if kind in GUARDS:
        lines.append("    Properties           DoesNotTire")
    lines.append(f"    SpriteVariants       {VARIANTS}")
    for v in range(VARIANTS):
        lines.append(f"    BEGIN Sprite x {x} y {first_row + 2 * (v % MODELS)} w 2 h 2 RotateType 1 END")
    lines.append("END")
    return "\n".join(lines) + "\n"


def materials_text(materials):
    out = [robot_object(materials, kind, k) for k, kind in enumerate(KINDS)]
    ux, uy = slot(UPLINK_AT)
    out.append(f"""BEGIN Object
    Name                 RobotUplink
    ConstructionTime     20.0000
    Toughness            200.000
    Price                -{UPLINK_PRICE}
    Filter               Security
    RenderDepth          1
    Group                StaticObject
    BlockedBy            Wall
    BlockedBy            UtilityStation
    BlockedBy            StaticObject
    MadeOf               SolidMetal
    Properties           StaticObject
    Properties           Scripted
    NumSprites           1
    BEGIN ToolbarSprite  x {ux}  y {uy}  w 2  h 2  END
    BEGIN Sprite         x {ux}  y {uy}  w 2  h 2  RotateType 0  TopAligned false  END
END
""")
    return "\n".join(out)


def settings_text(settings):
    out = []
    for line in settings.splitlines():
        m = re.match(r'("([^"]+)"\s+)\S+', line)
        if m and m.group(2) in NEVER:
            line = m.group(1) + NEVER[m.group(2)]
        out.append(line.rstrip())
    return "\n".join(out) + "\n"


def language_text():
    popup = ("Keeps your robot guards running. It tops up the charge of a robot that is flagging and wipes "
             "clean one that has been corrupted. Build one anywhere; it covers the whole prison.")
    rows = [
        ("object_RobotUplink", "Robot Uplink"),
        ("buildtoolbar_popup_obj_RobotUplink", popup),
        ("tooltip_RobotUplink", "*X robots online."),
    ]
    width = max(len(k) for k, _ in rows) + 4
    return "".join(f"{k:<{width}}{v}\n" for k, v in rows)


def save_image(im, path):
    """Writes a picture unless the file already holds the same pixels: a
    different version of the imaging library packs the same picture into
    different bytes, and that is not a change."""
    if os.path.exists(path):
        with Image.open(path) as old:
            if old.size == im.size and ImageChops.difference(old.convert("RGBA"), im.convert("RGBA")).getbbox() is None:
                return
    im.save(path)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    game = sys.argv[1]
    materials = ""
    for name in ("materials.txt", "materials_dlc.txt"):
        with open(os.path.join(game, name), errors="replace") as f:
            materials += f.read() + "\n"
    with open(os.path.join(game, "crookedguards_settings.txt"), errors="replace") as f:
        settings = f.read()
    os.makedirs(os.path.join(DATA, "language"), exist_ok=True)
    save_image(build_sprites(), os.path.join(DATA, "sprites.png"))
    save_image(build_people(game), os.path.join(DATA, "people.png"))
    with open(os.path.join(DATA, "materials.txt"), "w") as f:
        f.write(materials_text(materials))
    with open(os.path.join(DATA, "crookedguards_settings.txt"), "w") as f:
        f.write(settings_text(settings))
    with open(os.path.join(DATA, "language", "base-language.txt"), "w") as f:
        f.write(language_text())
    save_image(build_thumbnail(), os.path.join(ROOT, "thumbnail.png"))
    print("wrote sprites.png, people.png, materials.txt, crookedguards_settings.txt, base-language.txt, thumbnail.png")


if __name__ == "__main__":
    main()
