"""Builds every generated file the Robot Staff mod ships.

Outputs, relative to the mod root (the parent of this tools/ folder):
  data/sprites.png                    the robots, a model a row, the Robot Uplink, the drones and their pad
  data/sprite_replacement/            empty pictures for the stab vest, in every uniform pack that draws one
  data/materials.txt                  the game's staff, redefined with the game's own markers on the robots' pictures, and the uplink
  data/crookedguards_settings.txt     the game's own settings with corruption turned off
  data/needs-staff.txt                the game's own staff needs, switched off
  data/language/base-language.txt     names, build-menu text and the tooltip
  tools/card-art.png                  the art on the mod's Workshop card; thumbnail.png is exported from Figma

Usage: python gen_assets.py <the game's data folder, unpacked from main.dat>

The three guards are the game's own definitions read from its materials.txt,
so whatever the game says about a guard's speed, price or equipment is kept.
Three things change: the pictures, twice the Toughness, and DoesNotTire.
The scripts, data/scripts/RobotUplink.lua, data/scripts/DroneCharger.lua and
data/world.lua, are written by hand.
"""

import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drones  # noqa: E402
import robots  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# The game measures a sprite sheet in 32-pixel cells. A person is two cells
# square, and its four pictures sit side by side: front, back, side, blink.
CELL = 32
KINDS = list(robots.KINDS)
GUARDS = ["Guard", "ArmedGuard", "DogHandler"]      # the kinds that cannot be killed
MODELS = len(robots.MODELS)
ACROSS = 6                      # eighteen kinds fill three rows of six with no block left over
BLOCK = 8                       # cells a kind takes each way: four pictures across, four models down
# A save made with a mod that gave guards more pictures holds guards numbered
# past the four models, and a guard whose number has no picture is not drawn.
# So every number such a save can hold gets one, the four models in turn.
VARIANTS = 128
TOUGHER = 100000                # the game divides every blow by Toughness, so at this a blow does nothing that shows
UPLINK_AT = len(KINDS)          # the uplink's picture takes the slot after the last kind
UPLINK_PRICE = 1500

# The drones and their pad go in their own columns past the uplink. A drone is
# an entity, so its four pictures sit side by side the way a person's do, two
# cells each; the pad is an object with a picture per state.
DRONE_AT = ACROSS * BLOCK + 2                   # cell column the drones start at
PAD_AT = DRONE_AT + 4 * 2                       # and the column the pads start at
DRONE_MODELS = ("HaulerDrone", "PredatorDrone")
PAD_PRICE = 3000
DRONE_TOUGH = 100000            # a drone is a robot, and takes a blow the way one does
# Where a hauler's load is drawn. The game's own Guard markers put what a
# person carries at their head and hands; a drone carries it in the cradle
# slung underneath, which is most of a tile lower.
CRADLE_DROP = 0.25              # as far down as the lowest of the game's markers can go
CRADLE_FLOOR = 1.90             # tiles; a marker past this falls outside the picture

# The game draws a guard's stab vest over whatever the guard looks like, cut to
# a person's shoulders, which on a robot is a dark bib across the chest and
# halfway up the head. It takes the vest's pictures from its uniform packs, in
# data/sprite_replacement, and stamps them over the people sheet as it loads,
# so emptying the sheet itself does nothing. The mod ships an empty picture in
# place of each one: the vest still protects, and is still named on the guard,
# and nothing is drawn for it. A pack with no vest of its own uses the default.
VEST_PACKS = ("default", "GraveyardShift")
VEST_SPRITES = ("GuardArmour", "GuardArmour2", "GuardArmour3", "GuardArmour4", "GuardArmour5")
VEST_SIZE = (256, 64)

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
    """Where a kind's block starts on the sheet, in cells. The uplink is one
    picture two cells wide, so it stands in a column of its own past the last
    block rather than taking a whole block's room. Every mod's sprites share
    one atlas in the game, and both sides of a sheet are kept a multiple of
    64 px, two cells."""
    if k == UPLINK_AT:
        return ACROSS * BLOCK, 0
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


def drone_slot(m):
    """Where a drone's strip of four pictures starts, in cells."""
    return DRONE_AT, m * 2


def pad_slot(m, live):
    """Where a pad's picture starts, in cells: a column a state, a row a model."""
    return PAD_AT + (2 if live else 0), m * 2


def build_sprites():
    down = (len(KINDS) + ACROSS - 1) // ACROSS
    sheet = Image.new("RGBA", ((PAD_AT + 4) * CELL, down * BLOCK * CELL), (0, 0, 0, 0))
    for k, kind in enumerate(KINDS):
        x, y = slot(k)
        sheet.paste(robots.sheet(kind), (x * CELL, y * CELL))
    x, y = slot(UPLINK_AT)
    sheet.paste(uplink_sprite(), (x * CELL, y * CELL))
    for m, model in enumerate(DRONE_MODELS):
        x, y = drone_slot(m)
        sheet.paste(drones.sheet(model), (x * CELL, y * CELL))
        for live in (False, True):
            x, y = pad_slot(m, live)
            sheet.paste(drones.charger(model, live), (x * CELL, y * CELL))
    return sheet


def build_thumbnail():
    im = Image.new("RGBA", (256, 256), (16, 18, 21, 255))
    for i, model in enumerate(robots.MODELS):
        big = model("front").resize((128, 128), Image.NEAREST)
        im.paste(big, ((i % 2) * 128, (i // 2) * 128), big)
    return im


def write_empty_vests():
    for pack in VEST_PACKS:
        folder = os.path.join(DATA, "sprite_replacement", pack)
        os.makedirs(folder, exist_ok=True)
        for sprite in VEST_SPRITES:
            Image.new("RGBA", VEST_SIZE, (0, 0, 0, 0)).save(os.path.join(folder, f"{pack}_{sprite}.png"))


def game_object(materials, name):
    for block in re.findall(r"BEGIN Object\s.*?\nEND", materials, re.S):
        if re.search(r"^\s*Name\s+" + name + r"\s*$", block, re.M):
            return block
    raise SystemExit(f"the game's materials.txt has no {name}")


def game_markers(game, materials, kind):
    """The markers the game keeps on a kind's own pictures, measured from the
    picture's corner: the head and hands, which is where whatever the kind
    carries is drawn. A sprite with none has what it holds put at the edges of
    its picture instead. A kind the game gives no markers takes the Guard's."""
    named = re.search(r"^\s*Sprite\s+(\S+)", game_object(materials, kind), re.M)
    name = named.group(1) if named else kind
    for bank in sorted(os.listdir(game)):
        if not bank.endswith(".spritebank"):
            continue
        with open(os.path.join(game, bank), errors="replace") as f:
            text = f.read()
        at = re.search(r'Name ' + re.escape(name) + r'\s+x (\S+)\s+y (\S+)\s+w (\S+)\s+h (\S+)', text)
        if not at:
            continue
        x, y, w, h = map(float, at.groups())
        found = []
        for m in re.finditer(r"x (\S+)\s+y (\S+)\s+orientation\.x (\S+)\s+orientation\.y (\S+)\s+Index (\d+)",
                             text[text.find("BEGIN Markers"):]):
            mx, my, ox, oy = map(float, m.groups()[:4])
            if x <= mx < x + 4 * w and y <= my < y + h:
                found.append((mx - x, my - y, ox, oy, int(m.group(5))))
        if found:
            return found
    if kind == "Guard":
        raise SystemExit("the game's objects.spritebank has no markers for the Guard")
    return game_markers(game, materials, "Guard")


def robot_object(game, materials, kind, k):
    x, first_row = slot(k)
    markers = "".join(
        f"\n        BEGIN Marker x {mx:.6f} y {my:.6f} orientation.x {ox:.6f} orientation.y {oy:.6f} Index {i} END"
        for mx, my, ox, oy, i in game_markers(game, materials, kind))
    lines = []
    for line in game_object(materials, kind).splitlines()[:-1]:
        tough = re.match(r"(\s*Toughness\s+)([\d.]+)", line)
        if tough and kind in GUARDS:
            line = f"{tough.group(1)}{float(tough.group(2)) * TOUGHER:.4f}"
        if re.match(r"\s*(Sprite|SpriteVariants)\s", line):
            continue
        lines.append(line.rstrip())
    if not re.search(r"Properties\s+DoesNotTire", "\n".join(lines)):
        lines.append("    Properties           DoesNotTire")
    lines.append(f"    SpriteVariants       {VARIANTS}")
    for v in range(VARIANTS):
        lines.append(f"    BEGIN Sprite x {x} y {first_row + 2 * (v % MODELS)} w 2 h 2 RotateType 1{markers}\n    END")
    lines.append("END")
    return "\n".join(lines) + "\n"


def marker_lines(markers, drop=0.0):
    return "".join(
        f"\n        BEGIN Marker x {mx:.6f} y {min(my + drop, CRADLE_FLOOR):.6f}"
        f" orientation.x {ox:.6f} orientation.y {oy:.6f} Index {i} END"
        for mx, my, ox, oy, i in markers)


def drone_objects(game, materials):
    """The two drones and the pad that builds them.

    A drone is an entity with no BlockedBy of its own, the shape the game gives
    its Visitors and Actors, so nothing standing in a room turns a flying
    machine back. It is as tough as a robot guard, which is to say a blow on it
    does nothing that shows. It is never built from the toolbar; the pad spawns
    it and data/scripts/DroneCharger.lua flies it.
    """
    guard = game_markers(game, materials, "Guard")
    out = []
    for m, model in enumerate(DRONE_MODELS):
        x, y = drone_slot(m)
        # only the hauler carries anything, so only the hauler's load is moved
        # down into the cradle
        drop = CRADLE_DROP if model == "HaulerDrone" else 0.0
        out.append(f"""BEGIN Object
    Name                 {model}
    MoveSpeedFactor      {1.15 if model == "HaulerDrone" else 1.35:.5f}
    Toughness            {DRONE_TOUGH}.0000
    RenderDepth          3
    ViewRange            10
    NumSlots             1
    Properties           Entity
    Properties           DoesNotTire
    NumSprites           1
    BEGIN Sprite x {x} y {y} w 2 h 2 RotateType 1{marker_lines(guard, drop)}
    END
END
""")
    # The pad's pictures in the order its script picks them: a model's dark pad
    # then its live one, the Hauler's pair first.
    states = [pad_slot(m, live) for m in range(len(DRONE_MODELS)) for live in (False, True)]
    sprites = "".join(f"    BEGIN Sprite x {px} y {py} w 2 h 2 RotateType 0 TopAligned false END\n"
                      for px, py in states)
    tx, ty = states[0]
    out.append(f"""BEGIN Object
    Name                 DroneCharger
    Width                2
    Height               2
    ConstructionTime     20.0000
    MoveSpeedFactor      0.500000
    Toughness            200.000
    Price                -{PAD_PRICE}
    Filter               Security
    RenderDepth          1
    Group                StaticObject
    BlockedBy            Wall
    BlockedBy            StaticObject
    BlockedBy            UtilityStation
    MadeOf               SolidMetal
    Properties           StaticObject
    Properties           RoomSpecific
    Properties           Scripted
    NumSprites           {2 * len(DRONE_MODELS)}
    BEGIN ToolbarSprite  x {tx}  y {ty}  w 2  h 2  END
{sprites}END

BEGIN Room
    Name                 DroneBay
    BEGIN Requirement Type MinimumSize  x 3  y 3  END
    BEGIN Requirement Type Object  Id DroneCharger  END
    BEGIN LikelyObject Id DroneCharger  END
END
""")
    return out


def materials_text(game, materials):
    out = [robot_object(game, materials, kind, k) for k, kind in enumerate(KINDS)]
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
    out.extend(drone_objects(game, materials))
    return "\n".join(out)


def settings_text(settings):
    out = []
    for line in settings.splitlines():
        m = re.match(r'("([^"]+)"\s+)\S+', line)
        if m and m.group(2) in NEVER:
            line = m.group(1) + NEVER[m.group(2)]
        out.append(line.rstrip())
    return "\n".join(out) + "\n"


def needs_text(needs):
    """The game's staff needs with nothing left to drive them. The game raises
    a need over time only while its definition carries AutoCharge, and it reads
    that from the definition every tick rather than from the save, so taking
    the property away stops the toilet, the canteen and the rest for the staff
    a prison already has. Chance is how likely a new member of staff is to be
    given the need at all, and at nought nobody hired from then on has any."""
    out, inside = [], False
    for line in needs.splitlines():
        if re.match(r"\s*BEGIN\s+Need\b", line):
            inside = True
        elif re.match(r"\s*END\b", line):
            inside = False
        if inside and re.match(r"\s*Properties\s+AutoCharge\b", line):
            continue
        chance = re.match(r"(\s*Chance\s+)\S+", line)
        if inside and chance:
            line = chance.group(1) + "0.000000"
        out.append(line.rstrip())
    return "\n".join(out) + "\n"


def language_text():
    popup = ("Services your robot staff. It recharges any robot that is running low, and it repairs the robots "
             "that guard and wipes clean any of them that has been corrupted. Build one anywhere; it covers the "
             "whole prison.")
    pad = ("Builds one drone and keeps it charged. The button on the pad switches its drone between the two "
           "models. A Hauler carries the dead to the morgue and clears rubbish when there are no dead; a "
           "Predator patrols, or holds station on the pad, and shocks any prisoner it catches in misconduct. "
           "A drone works within thirty tiles of its pad, so put a pad in each part of the prison you want "
           "covered. It must stand in a Drone Bay.")
    bay = ("Where drones are built and charged. Put a Drone Charger in it. It needs three tiles by three, "
           "and nothing else.")
    rows = [
        ("object_RobotUplink", "Robot Uplink"),
        ("buildtoolbar_popup_obj_RobotUplink", popup),
        ("tooltip_RobotUplink", "*X robots online."),
        ("object_DroneCharger", "Drone Charger"),
        ("buildtoolbar_popup_obj_DroneCharger", pad),
        ("object_HaulerDrone", "Hauler Drone"),
        ("object_PredatorDrone", "Predator Drone"),
        ("room_dronebay", "Drone Bay"),
        ("buildtoolbar_popup_room_dronebay", bay),
        ("button_DroneRole_Hauler", "Model: Hauler"),
        ("button_DroneRole_Predator", "Model: Predator"),
        ("button_DroneDuty_Patrol", "Duty: Patrol"),
        ("button_DroneDuty_Post", "Duty: Guard Post"),
        ("tooltip_DroneCharger_Building", "Building its drone."),
        ("tooltip_DroneCharger_Charging", "Drone docked. Charge *C%."),
        ("tooltip_DroneCharger_Idle", "Drone standing by. Charge *C%."),
        ("tooltip_DroneCharger_Returning", "Drone coming home to charge. *C%."),
        ("tooltip_DroneCharger_Fetching", "Drone on its way to a body. Charge *C%."),
        ("tooltip_DroneCharger_Carrying", "Drone carrying a body to the morgue. Charge *C%."),
        ("tooltip_DroneCharger_Nowhere", "No morgue slab free. The drone has set the body down. Charge *C%."),
        ("tooltip_DroneCharger_Clearing", "Drone clearing rubbish. Charge *C%."),
        ("tooltip_DroneCharger_Chasing", "Drone closing on a prisoner. Charge *C%."),
        ("tooltip_DroneCharger_Holding", "Drone holding station. Charge *C%."),
        ("tooltip_DroneCharger_Patrolling", "Drone on patrol. Charge *C%."),
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
    write_empty_vests()
    with open(os.path.join(DATA, "materials.txt"), "w") as f:
        f.write(materials_text(game, materials))
    with open(os.path.join(DATA, "crookedguards_settings.txt"), "w") as f:
        f.write(settings_text(settings))
    with open(os.path.join(game, "needs-staff.txt"), errors="replace") as f:
        needs = f.read()
    with open(os.path.join(DATA, "needs-staff.txt"), "w") as f:
        f.write(needs_text(needs))
    with open(os.path.join(DATA, "language", "base-language.txt"), "w") as f:
        f.write(language_text())
    save_image(build_thumbnail(), os.path.join(ROOT, "tools", "card-art.png"))
    print("wrote sprites.png, sprite_replacement, materials.txt, crookedguards_settings.txt, base-language.txt, tools/card-art.png")


if __name__ == "__main__":
    main()
