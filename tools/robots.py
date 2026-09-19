"""Draws the robot guards: four models, each seen from the front, the back
and the side, in the 64-pixel boxes the game keeps its guards in.

Every part of a robot, its body, its shoulders, its head, is painted on a
layer of its own at eight times its size with no outline at all. The outline
is then grown from the part's own edge and laid underneath it, which is what
gives every part the even dark line the game's own people have, and the whole
picture is brought down to size at the end.
"""

from PIL import Image, ImageDraw, ImageFilter

BOX = 64
UP = 8
LINE = 1.5                      # outline weight, in finished pixels

OUTLINE = (14, 16, 20, 255)
STEEL = (176, 184, 194, 255)
STEEL_HI = (222, 228, 235, 255)
STEEL_LO = (120, 128, 140, 255)
STEEL_DK = (82, 90, 102, 255)
GUN = (70, 76, 88, 255)
GUN_HI = (104, 112, 126, 255)
GUN_LO = (44, 48, 58, 255)
BLUE = (38, 84, 108, 255)       # the guards' own blue, so a robot still reads as a guard
BLUE_HI = (78, 134, 160, 255)
BLUE_LO = (24, 56, 74, 255)
NAVY = (30, 50, 78, 255)
NAVY_HI = (62, 90, 128, 255)
NAVY_LO = (18, 32, 52, 255)
GOLD = (236, 190, 70, 255)
HAZARD = (240, 196, 40, 255)
DARK = (26, 30, 36, 255)
RED = (255, 70, 60, 255)
SIREN_BLUE = (70, 130, 255, 255)

CYAN = dict(core=(96, 226, 255, 255), hot=(228, 251, 255, 255), dim=(24, 96, 124, 255))
AMBER = dict(core=(255, 176, 48, 255), hot=(255, 240, 200, 255), dim=(120, 70, 12, 255))
GREEN = dict(core=(110, 240, 130, 255), hot=(225, 255, 230, 255), dim=(26, 100, 48, 255))
CRIMSON = dict(core=(255, 72, 64, 255), hot=(255, 214, 208, 255), dim=(118, 22, 22, 255))

FACINGS = ["front", "back", "side", "blink"]
CX = BOX / 2


def s(*v):
    return [int(round(x * UP)) for x in v]


def pts(points):
    return [(int(round(x * UP)), int(round(y * UP))) for x, y in points]


class Robot:
    def __init__(self):
        self.im = Image.new("RGBA", (BOX * UP, BOX * UP), (0, 0, 0, 0))

    def part(self, paint):
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        paint(ImageDraw.Draw(layer))
        grow = int(LINE * UP) * 2 + 1
        edge = layer.getchannel("A").filter(ImageFilter.MaxFilter(grow))
        line = Image.new("RGBA", self.im.size, OUTLINE)
        line.putalpha(edge)
        self.im.alpha_composite(line)
        self.im.alpha_composite(layer)

    def done(self):
        return self.im.resize((BOX, BOX), Image.LANCZOS)


def bell(d, shoulder, hem, top, fill, hi, lo, bottom=61):
    """A body: narrow at the shoulder, wide at the hem, round underneath,
    lit from the left."""
    shape = [(CX - shoulder, top + 4), (CX - shoulder + 3, top), (CX + shoulder - 3, top), (CX + shoulder, top + 4),
             (CX + hem, bottom - 11), (CX + hem - 2, bottom - 4), (CX + hem - 8, bottom),
             (CX - hem + 8, bottom), (CX - hem + 2, bottom - 4), (CX - hem, bottom - 11)]
    d.polygon(pts(shape), fill=fill)
    d.polygon(pts([(CX - shoulder, top + 4), (CX - shoulder + 3, top), (CX - shoulder + 7, top),
                   (CX - hem + 6, bottom - 11), (CX - hem + 7, bottom - 3), (CX - hem + 2, bottom - 4),
                   (CX - hem, bottom - 11)]), fill=hi)
    d.polygon(pts([(CX + shoulder, top + 4), (CX + shoulder - 3, top), (CX + shoulder - 6, top),
                   (CX + hem - 5, bottom - 11), (CX + hem - 8, bottom), (CX + hem - 2, bottom - 4),
                   (CX + hem, bottom - 11)]), fill=lo)


def look(facing, glow):
    """The fourth picture is the game's blink: the front again with its
    lights down."""
    if facing == "blink":
        return "front", dict(core=glow["dim"], hot=glow["core"], dim=DARK)
    return facing, glow


def lamp(d, x, y, r, glow):
    d.ellipse(s(x - r, y - r, x + r, y + r), fill=glow["dim"])
    d.ellipse(s(x - r * 0.72, y - r * 0.72, x + r * 0.72, y + r * 0.72), fill=glow["core"])
    d.ellipse(s(x - r * 0.5, y - r * 0.55, x - r * 0.05, y - r * 0.1), fill=glow["hot"])


def antenna(d, x, top, glow, base=9):
    d.rectangle(s(x - 0.8, top + 2, x + 0.8, base), fill=STEEL_DK)
    lamp(d, x, top + 1.6, 1.9, glow)


# ------------------------------------------------------------------ patrol
# The standard unit. A rounded head under a peaked cap plate with a gold
# badge, a slim visor, a core in the chest and a badge beside it.

def patrol(facing, kit=None):
    r = Robot()
    facing, glow = look(facing, CYAN)

    def body(d):
        bell(d, 17, 24, 31, BLUE, BLUE_HI, BLUE_LO)
        d.rectangle(s(CX - 20, 53, CX + 20, 54.5), fill=BLUE_LO)
        if facing == "back":
            d.rounded_rectangle(s(CX - 8, 38, CX + 8, 52), radius=2 * UP, fill=GUN)
            for y in (41, 45, 49):
                d.rectangle(s(CX - 5, y, CX + 5, y + 1.4), fill=GUN_LO)
        else:
            off = -3 if facing == "side" else 0
            d.rounded_rectangle(s(CX - 9 + off, 37, CX + 9 + off, 51), radius=3 * UP, fill=BLUE_HI)
            lamp(d, CX + off - (0 if facing == "side" else 3), 44, 4, glow)
            if facing != "side":
                d.polygon(pts([(CX + 3.5, 40.5), (CX + 7.5, 40.5), (CX + 7.5, 45), (CX + 5.5, 47.5), (CX + 3.5, 45)]), fill=GOLD)
    r.part(body)

    def shoulders(d):
        for side in (-1, 1):
            x = CX + side * 16
            d.ellipse(s(x - 4.5, 30, x + 4.5, 38.5), fill=STEEL)
            d.pieslice(s(x - 4.5, 30, x + 4.5, 38.5), 180, 300, fill=STEEL_HI)
    r.part(shoulders)

    def neck(d):
        d.rectangle(s(CX - 3.5, 26, CX + 3.5, 33), fill=STEEL_DK)
    r.part(neck)

    def head(d):
        d.rounded_rectangle(s(CX - 12, 10, CX + 12, 28), radius=6 * UP, fill=STEEL)
        d.rounded_rectangle(s(CX - 12, 10, CX - 7, 28), radius=4 * UP, fill=STEEL_HI)
        d.rectangle(s(CX - 9, 24.5, CX + 12, 26), fill=STEEL_LO)
        if facing == "back":
            for y in (16, 19.5, 23):
                d.rectangle(s(CX - 6, y, CX + 6, y + 1.3), fill=STEEL_LO)
        elif facing == "side":
            d.rounded_rectangle(s(CX - 12, 15.5, CX + 2, 21.5), radius=2 * UP, fill=glow["dim"])
            d.rounded_rectangle(s(CX - 11, 16.8, CX - 3, 20.2), radius=1 * UP, fill=glow["core"])
            d.ellipse(s(CX + 5, 15, CX + 10, 22), fill=STEEL_LO)
        else:
            d.rounded_rectangle(s(CX - 9, 15.5, CX + 9, 21.5), radius=2 * UP, fill=glow["dim"])
            d.rounded_rectangle(s(CX - 7.5, 16.8, CX + 7.5, 20.2), radius=1 * UP, fill=glow["core"])
            d.rectangle(s(CX - 6, 17.3, CX - 1.5, 18.3), fill=glow["hot"])
    r.part(head)

    def cap(d):
        d.rounded_rectangle(s(CX - 12.5, 5, CX + 12.5, 13), radius=3 * UP, fill=NAVY)
        d.rectangle(s(CX - 12.5, 10.5, CX + 12.5, 13), fill=NAVY_LO)
        d.rounded_rectangle(s(CX - 12.5, 5, CX + 12.5, 7.5), radius=2 * UP, fill=NAVY_HI)
        if facing == "front":
            d.polygon(pts([(CX - 2.5, 6.5), (CX + 2.5, 6.5), (CX + 2.5, 9.5), (CX, 11.5), (CX - 2.5, 9.5)]), fill=GOLD)
        if facing == "side":
            d.polygon(pts([(CX - 12.5, 11), (CX - 19, 13.5), (CX - 12.5, 14)]), fill=NAVY_LO)
            d.polygon(pts([(CX - 10, 6.5), (CX - 6.5, 6.5), (CX - 6.5, 9.5), (CX - 8.2, 11), (CX - 10, 9.5)]), fill=GOLD)
    r.part(cap)
    wear(r, kit, facing, 17)
    return r.done()


# ------------------------------------------------------------------- heavy
# The riot-line unit. A squat head sunk between big pauldrons that carry a
# red and a blue siren, slanted amber eyes, and a vented chest.

def heavy(facing, kit=None):
    r = Robot()
    facing, glow = look(facing, AMBER)

    def body(d):
        bell(d, 21, 29, 32, GUN, GUN_HI, GUN_LO)
        d.rectangle(s(CX - 25, 54, CX + 25, 56), fill=HAZARD)
        for x in range(-24, 25, 6):
            d.polygon(pts([(CX + x, 56), (CX + x + 3, 54), (CX + x + 5, 54), (CX + x + 2, 56)]), fill=DARK)
        if facing == "back":
            d.rounded_rectangle(s(CX - 10, 38, CX + 10, 51), radius=2 * UP, fill=GUN_LO)
            lamp(d, CX - 5, 44.5, 2.6, glow)
            lamp(d, CX + 5, 44.5, 2.6, glow)
        else:
            off = -4 if facing == "side" else 0
            d.rounded_rectangle(s(CX - 11 + off, 38, CX + 11 + off, 51), radius=2 * UP, fill=BLUE)
            for x in (-7, -3, 1, 5):
                d.rounded_rectangle(s(CX + x + off, 40.5, CX + x + 2 + off, 48.5), radius=1 * UP, fill=DARK)
    r.part(body)

    def head(d):
        d.rounded_rectangle(s(CX - 11, 13, CX + 11, 31), radius=4 * UP, fill=GUN_HI)
        d.rounded_rectangle(s(CX - 11, 13, CX + 11, 18), radius=3 * UP, fill=STEEL_LO)
        d.rectangle(s(CX - 11, 27, CX + 11, 31), fill=GUN)
        if facing == "back":
            d.rounded_rectangle(s(CX - 6, 19, CX + 6, 26), radius=1 * UP, fill=GUN_LO)
        elif facing == "side":
            d.polygon(pts([(CX - 11, 19.5), (CX - 2, 21), (CX - 2, 24.5), (CX - 11, 24.5)]), fill=glow["dim"])
            d.polygon(pts([(CX - 10, 21), (CX - 4, 22), (CX - 4, 23.6), (CX - 10, 23.6)]), fill=glow["core"])
            for y in (27.5, 29.2):
                d.rectangle(s(CX - 10, y, CX - 2, y + 0.9), fill=GUN_LO)
        else:
            for side in (-1, 1):
                d.polygon(pts([(CX + side * 9, 19), (CX + side * 2, 21.5), (CX + side * 2, 25), (CX + side * 9, 25)]), fill=glow["dim"])
                d.polygon(pts([(CX + side * 8, 20.8), (CX + side * 3, 22.4), (CX + side * 3, 24), (CX + side * 8, 24)]), fill=glow["core"])
            for y in (27.5, 29.2):
                d.rectangle(s(CX - 6, y, CX + 6, y + 0.9), fill=GUN_LO)
    r.part(head)

    def pauldrons(d):
        for side, colour in ((-1, RED), (1, SIREN_BLUE)):
            x = CX + side * 19
            d.rounded_rectangle(s(x - 8, 27, x + 8, 39), radius=4 * UP, fill=BLUE)
            d.rounded_rectangle(s(x - 8, 27, x + 8, 31), radius=3 * UP, fill=BLUE_HI)
            d.rectangle(s(x - 8, 36.5, x + 8, 38), fill=BLUE_LO)
            d.rounded_rectangle(s(x - 3.5, 22.5, x + 3.5, 28), radius=2 * UP, fill=colour)
            d.rectangle(s(x - 2, 23.5, x - 0.5, 26), fill=(255, 255, 255, 170))
    r.part(pauldrons)
    wear(r, kit, facing, 21)
    return r.done()


# ------------------------------------------------------------------- scout
# The slim unit. A tall drum of a head on a thin neck with one big green
# lens, a long whip antenna, and a striped sash across a narrow body.

def scout(facing, kit=None):
    r = Robot()
    facing, glow = look(facing, GREEN)

    def body(d):
        bell(d, 12, 18, 33, NAVY, NAVY_HI, NAVY_LO)
        if facing == "back":
            d.rounded_rectangle(s(CX - 5, 39, CX + 5, 54), radius=2 * UP, fill=STEEL_DK)
            d.rectangle(s(CX - 1, 41, CX + 1, 52), fill=glow["core"])
        else:
            off = -2 if facing == "side" else 0
            d.polygon(pts([(CX - 12 + off, 38), (CX - 7 + off, 36), (CX + 14 + off, 53), (CX + 10 + off, 56)]), fill=STEEL_HI)
            d.polygon(pts([(CX - 10 + off, 38.4), (CX - 8 + off, 37.6), (CX + 12.5 + off, 54), (CX + 11 + off, 55)]), fill=glow["core"])
            lamp(d, CX - 5 + off, 50, 2.4, glow)
    r.part(body)

    def shoulders(d):
        for side in (-1, 1):
            x = CX + side * 12
            d.rounded_rectangle(s(x - 3.5, 32, x + 3.5, 40), radius=2 * UP, fill=STEEL)
            d.rectangle(s(x - 3.5, 32, x - 1.5, 40), fill=STEEL_HI)
    r.part(shoulders)

    def neck(d):
        d.rectangle(s(CX - 2, 27, CX + 2, 34), fill=STEEL_DK)
        d.rectangle(s(CX - 3.5, 29.5, CX + 3.5, 31), fill=STEEL_LO)
    r.part(neck)

    def whip(d):
        antenna(d, CX + (7 if facing != "side" else 5), 1.4, glow, base=8)
    r.part(whip)

    def head(d):
        d.rounded_rectangle(s(CX - 9, 6, CX + 9, 28), radius=5 * UP, fill=STEEL)
        d.rounded_rectangle(s(CX - 9, 6, CX - 5, 28), radius=3 * UP, fill=STEEL_HI)
        d.rounded_rectangle(s(CX + 5.5, 6, CX + 9, 28), radius=3 * UP, fill=STEEL_LO)
        d.rectangle(s(CX - 9, 9.5, CX + 9, 10.8), fill=STEEL_LO)
        d.rectangle(s(CX - 9, 24, CX + 9, 25.3), fill=STEEL_LO)
        if facing == "back":
            d.rounded_rectangle(s(CX - 4, 13, CX + 4, 22), radius=1 * UP, fill=STEEL_DK)
        elif facing == "side":
            d.ellipse(s(CX - 13, 12, CX - 3, 23), fill=GUN)
            lamp(d, CX - 9, 17.5, 4.2, glow)
        else:
            d.ellipse(s(CX - 7, 11, CX + 7, 24), fill=GUN)
            lamp(d, CX, 17.5, 5.4, glow)
    r.part(head)
    wear(r, kit, facing, 12)
    return r.done()


# ---------------------------------------------------------------- enforcer
# The heavy-hitter. A wedge of a head, wider at the brow, with a red T
# visor, twin stub antennae, plated shoulders and a gold chevron on the chest.

def enforcer(facing, kit=None):
    r = Robot()
    facing, glow = look(facing, CRIMSON)

    def body(d):
        bell(d, 20, 27, 32, NAVY, NAVY_HI, NAVY_LO)
        d.polygon(pts([(CX - 22, 50), (CX + 22, 50), (CX + 24, 53), (CX - 24, 53)]), fill=GUN_LO)
        if facing == "back":
            d.polygon(pts([(CX - 9, 37), (CX + 9, 37), (CX + 6, 49), (CX - 6, 49)]), fill=GUN)
            d.rectangle(s(CX - 1, 39, CX + 1, 47), fill=glow["core"])
        else:
            off = -4 if facing == "side" else 0
            d.polygon(pts([(CX - 11 + off, 37), (CX + 11 + off, 37), (CX + 8 + off, 49), (CX - 8 + off, 49)]), fill=GUN)
            d.polygon(pts([(CX - 7 + off, 39), (CX + off, 43), (CX + 7 + off, 39), (CX + 7 + off, 42), (CX + off, 46), (CX - 7 + off, 42)]), fill=GOLD)
    r.part(body)

    def shoulders(d):
        for side in (-1, 1):
            x = CX + side * 19
            d.polygon(pts([(x - 7, 38), (x - 6, 30), (x + 6, 30), (x + 7, 38)]), fill=STEEL)
            d.polygon(pts([(x - 6, 30), (x + 6, 30), (x + 6.4, 32.5), (x - 6.4, 32.5)]), fill=STEEL_HI)
            d.rectangle(s(x - 7, 35.5, x + 7, 36.8), fill=STEEL_LO)
    r.part(shoulders)

    def stubs(d):
        for side in (-1, 1):
            x = CX + side * (9 if facing != "side" else 6)
            d.rectangle(s(x - 1.2, 2, x + 1.2, 10), fill=GUN)
            d.rectangle(s(x - 1.2, 2, x + 1.2, 4), fill=glow["core"])
    r.part(stubs)

    def head(d):
        d.polygon(pts([(CX - 14, 8), (CX + 14, 8), (CX + 9, 30), (CX - 9, 30)]), fill=GUN_HI)
        d.polygon(pts([(CX - 14, 8), (CX - 9, 8), (CX - 5.5, 30), (CX - 9, 30)]), fill=STEEL_LO)
        d.polygon(pts([(CX + 14, 8), (CX + 10, 8), (CX + 6, 30), (CX + 9, 30)]), fill=GUN)
        d.polygon(pts([(CX - 14, 8), (CX + 14, 8), (CX + 13.3, 11), (CX - 13.3, 11)]), fill=STEEL)
        if facing == "back":
            for y in (15, 19, 23):
                d.rectangle(s(CX - 5, y, CX + 5, y + 1.3), fill=GUN_LO)
        elif facing == "side":
            d.polygon(pts([(CX - 13, 14), (CX - 1, 14), (CX - 1, 18.5), (CX - 8, 18.5), (CX - 8, 27), (CX - 10.5, 27), (CX - 12, 18.5)]), fill=glow["dim"])
            d.polygon(pts([(CX - 12, 15.2), (CX - 3, 15.2), (CX - 3, 17.3), (CX - 11.6, 17.3)]), fill=glow["core"])
        else:
            d.polygon(pts([(CX - 11, 14), (CX + 11, 14), (CX + 10, 18.5), (CX + 2, 18.5), (CX + 1.6, 27),
                           (CX - 1.6, 27), (CX - 2, 18.5), (CX - 10, 18.5)]), fill=glow["dim"])
            d.polygon(pts([(CX - 9.5, 15.2), (CX + 9.5, 15.2), (CX + 9, 17.3), (CX - 9, 17.3)]), fill=glow["core"])
            d.rectangle(s(CX - 0.7, 17.3, CX + 0.7, 25.5), fill=glow["core"])
            d.rectangle(s(CX - 8, 15.6, CX - 3, 16.3), fill=glow["hot"])
    r.part(head)
    wear(r, kit, facing, 20)
    return r.done()


MODELS = [patrol, heavy, scout, enforcer]

def shades(colour):
    """A colour with its lit and its shaded version."""
    r, g, b = colour
    hi = tuple(min(255, int(c + (255 - c) * 0.32)) for c in colour) + (255,)
    lo = tuple(int(c * 0.62) for c in colour) + (255,)
    return (r, g, b, 255), hi, lo


def uniform(coat, trim, plate, kit=None, band=None):
    """The colours of one kind of staff: the coat the Patrol and the Heavy's
    pauldrons wear, the trim the Scout and the Enforcer wear and the Patrol's
    cap is cut from, the plate the Heavy is built from, and what is worn over
    the top."""
    out = dict(kit=kit, band=band)
    for name, colour in (("BLUE", coat), ("NAVY", trim), ("GUN", plate)):
        out[name], out[name + "_HI"], out[name + "_LO"] = shades(colour)
    return out


# Every kind of staff is the same four models in its own uniform, the colours
# the game dresses that kind in, with its own mark over the top.
KINDS = {
    "Guard": dict(),
    "ArmedGuard": uniform((62, 66, 76), (48, 50, 58), (40, 42, 50), kit="shells"),
    "DogHandler": uniform((30, 44, 74), (24, 34, 60), (44, 56, 84), kit="k9"),
    "Sniper": uniform((78, 96, 58), (56, 72, 44), (66, 74, 56), kit="band", band=(38, 48, 30, 255)),
    "Workman": uniform((226, 214, 72), (206, 190, 52), (92, 96, 104), kit="stripes"),
    "Foreman": uniform((236, 150, 40), (214, 128, 30), (92, 96, 104), kit="stripes"),
    "Cook": uniform((232, 232, 226), (208, 208, 200), (120, 124, 132), kit="apron"),
    "Janitor": uniform((96, 128, 184), (74, 104, 160), (84, 96, 120), kit="band", band=(40, 60, 110, 255)),
    "Gardener": uniform((86, 150, 70), (64, 124, 54), (80, 100, 76), kit="band", band=(150, 108, 60, 255)),
    "Farmer": uniform((176, 126, 62), (150, 102, 46), (96, 88, 72), kit="band", band=(86, 150, 70, 255)),
    "Doctor": uniform((236, 240, 242), (210, 218, 222), (128, 140, 148), kit="cross"),
    "Orderly": uniform((96, 190, 176), (70, 162, 150), (96, 128, 124), kit="cross"),
    "Psychiatrist": uniform((150, 120, 170), (124, 96, 146), (104, 96, 116), kit="cross"),
    "Psychologist": uniform((150, 110, 78), (124, 88, 60), (104, 92, 84), kit="band", band=GOLD),
    "Warden": uniform((56, 58, 66), (40, 42, 50), (70, 72, 82), kit="band", band=GOLD),
    "Chief": uniform((38, 84, 108), (30, 50, 78), (70, 76, 88), kit="band", band=GOLD),
    "Accountant": uniform((120, 124, 132), (96, 100, 110), (84, 88, 98), kit="band", band=GOLD),
    "Lawyer": uniform((34, 34, 40), (24, 24, 30), (56, 58, 66), kit="band", band=GOLD),
}

# K, a dash and 9 on a three by five grid.
LETTERS = {"K": ["1.1", "1.1", "11.", "1.1", "1.1"], "-": ["...", "...", "11.", "...", "..."],
           "9": ["111", "1.1", "111", "..1", "111"]}


def wear(r, kit, facing, half):
    """Lays a kind's mark over a finished robot. half is how wide the body is
    where the mark sits."""
    band = None
    if isinstance(kit, tuple):
        kit, band = kit
    if kit == "shells" and facing != "back":
        def shells(d):
            d.rectangle(s(CX - half, 47, CX + half, 51.5), fill=DARK)
            for i, x in enumerate(range(int(-half) + 2, int(half) - 1, 3)):
                d.rectangle(s(CX + x, 48, CX + x + 1.6, 50.5), fill=RED if i % 2 else HAZARD)
        r.part(shells)
    if kit == "k9" and facing != "side":
        def plate(d):
            d.rounded_rectangle(s(CX - 9, 52, CX + 9, 60), radius=1 * UP, fill=DARK)
            x = CX - 6.5
            for ch in "K-9":
                for row, line in enumerate(LETTERS[ch]):
                    for col, bit in enumerate(line):
                        if bit == "1":
                            d.rectangle(s(x + col * 1.2, 53.2 + row * 1.2, x + col * 1.2 + 1.2, 53.2 + row * 1.2 + 1.2), fill=(240, 244, 248, 255))
                x += 4.6
        r.part(plate)
    if kit == "stripes":
        def stripes(d):
            for y in (50.5, 55):
                d.rectangle(s(CX - half - 1, y, CX + half + 1, y + 2.2), fill=(226, 230, 236, 255))
                d.rectangle(s(CX - half - 1, y + 1.5, CX + half + 1, y + 2.2), fill=(150, 156, 166, 255))
        r.part(stripes)
    if kit == "band":
        def sash(d):
            d.rectangle(s(CX - half - 2, 55.5, CX + half + 2, 58), fill=band)
        r.part(sash)
    if kit == "apron" and facing != "back":
        def apron(d):
            off = -3 if facing == "side" else 0
            d.rounded_rectangle(s(CX - half + 5 + off, 50, CX + half - 5 + off, 61), radius=2 * UP, fill=(250, 250, 246, 255))
            d.rectangle(s(CX - half + 5 + off, 50, CX + half - 5 + off, 51.5), fill=(200, 200, 194, 255))
        r.part(apron)
    if kit == "cross" and facing != "back":
        def cross(d):
            x = CX + (-4 if facing == "side" else 0)
            d.rounded_rectangle(s(x - 5, 51, x + 5, 61), radius=1.5 * UP, fill=(250, 252, 252, 255))
            d.rectangle(s(x - 1.2, 52.5, x + 1.2, 59.5), fill=(222, 50, 46, 255))
            d.rectangle(s(x - 3.5, 54.8, x + 3.5, 57.2), fill=(222, 50, 46, 255))
        r.part(cross)


def sheet(kind="Guard"):
    """The sixteen pictures of one kind in the game's own arrangement: a model
    a row, then front, back, side and the blink."""
    theme = dict(KINDS[kind])
    kit = theme.pop("kit", None)
    band = theme.pop("band", None)
    if kit == "band":
        kit = ("band", band)
    saved = {k: globals()[k] for k in theme}
    globals().update(theme)
    try:
        im = Image.new("RGBA", (BOX * 4, BOX * 4), (0, 0, 0, 0))
        for row, model in enumerate(MODELS):
            for col, facing in enumerate(FACINGS):
                im.paste(model(facing, kit), (col * BOX, row * BOX))
        return im
    finally:
        globals().update(saved)
