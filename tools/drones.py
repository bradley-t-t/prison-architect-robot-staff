"""Draws the drones and their landing pad, in the boxes the game keeps its
people and its objects in.

Every part is painted the way robots.py paints one: on a layer of its own at
eight times its size, with the outline grown from the part's own edge and laid
underneath it, so a drone carries the same even dark line as the robots that
work beside it.

A drone flies, so it is drawn a little above the middle of its box with its
shadow laid on the ground below, and the blades inside its ducts are drawn as
the blur of something turning. The two models read apart at a glance: the
Hauler is a wide lifter, amber, with a cradle and claws slung underneath; the
Predator is a narrow swept hull, crimson, with a prod at the nose.
"""

from PIL import Image, ImageDraw

import robots
from robots import (AMBER, CRIMSON, CX, DARK, GOLD, GUN, GUN_HI, GUN_LO, HAZARD,
                    OUTLINE, Robot, STEEL, STEEL_DK, STEEL_HI, STEEL_LO, UP,
                    lamp, look, pts, s)

BOX = robots.BOX
FACINGS = robots.FACINGS

BLUR = (198, 206, 220, 150)      # the blades, seen turning
STREAK = (238, 243, 250, 195)
SHADE = (0, 0, 0, 90)            # what a flying thing puts on the floor


def duct(d, x, y, r, squash=0.82):
    """A ducted rotor: a rim, the blur of the blades inside it and a hub."""
    d.ellipse(s(x - r, y - r * squash, x + r, y + r * squash), fill=STEEL_DK)
    d.ellipse(s(x - r, y - r * squash, x + r * 0.2, y - r * squash + 2.4), fill=STEEL)
    d.ellipse(s(x - r + 1.7, y - (r - 1.7) * squash, x + r - 1.7, y + (r - 1.7) * squash), fill=GUN_LO)
    d.ellipse(s(x - r + 2.4, y - (r - 2.4) * squash, x + r - 2.4, y + (r - 2.4) * squash), fill=BLUR)
    for dx, dy in ((-1, -0.5), (1, 0.5)):
        reach = r - 2.6
        d.polygon(pts([(x, y - 1.2), (x + dx * reach, y + dy * reach * squash - 0.9),
                       (x + dx * reach, y + dy * reach * squash + 0.9), (x, y + 1.2)]), fill=STREAK)
    d.ellipse(s(x - 1.9, y - 1.7, x + 1.9, y + 1.7), fill=STEEL)
    d.ellipse(s(x - 1.9, y - 1.7, x + 0.3, y - 0.1), fill=STEEL_HI)


def shadow(r, half, y, height=4.6):
    def paint(d):
        d.ellipse(s(CX - half, y - height, CX + half, y + height), fill=SHADE)
    layer = Image.new("RGBA", r.im.size, (0, 0, 0, 0))
    paint(ImageDraw.Draw(layer))
    r.im.alpha_composite(layer)


# ------------------------------------------------------------------ hauler
# The lifter. Four ducts on stubby outriggers round a flat hull, with a cradle
# and a pair of claws slung under it. What it carries rides in the cradle.

def hauler(facing, kit=None):
    r = Robot()
    facing, glow = look(facing, AMBER)
    shadow(r, 17 if facing != "side" else 14, 57)

    def arms(d):
        if facing == "side":
            d.rounded_rectangle(s(CX - 15, 30, CX + 15, 34), radius=1.6 * UP, fill=STEEL_DK)
        else:
            for dy in (25.5, 41.5):
                d.rounded_rectangle(s(CX - 19, dy - 2, CX + 19, dy + 2), radius=1.6 * UP, fill=STEEL_DK)
                d.rounded_rectangle(s(CX - 19, dy - 2, CX + 19, dy - 0.6), radius=0.8 * UP, fill=STEEL_LO)
    r.part(arms)

    def rotors(d):
        if facing == "side":
            duct(d, CX - 15, 26, 8.5)
            duct(d, CX + 15, 26, 8.5)
        else:
            for x in (-19, 19):
                duct(d, CX + x, 24, 9)
            for x in (-19, 19):
                duct(d, CX + x, 41, 9)
    r.part(rotors)

    def hull(d):
        if facing == "side":
            d.polygon(pts([(CX - 12, 28), (CX + 11, 28), (CX + 13, 42), (CX - 14, 42)]), fill=STEEL)
            d.polygon(pts([(CX - 12, 28), (CX + 11, 28), (CX + 11, 30.6), (CX - 12.4, 30.6)]), fill=STEEL_HI)
        else:
            d.rounded_rectangle(s(CX - 13, 27, CX + 13, 45), radius=4 * UP, fill=STEEL)
            d.rounded_rectangle(s(CX - 13, 27, CX + 13, 31), radius=3 * UP, fill=STEEL_HI)
            d.polygon(pts([(CX + 9, 28), (CX + 13, 31), (CX + 13, 42), (CX + 9, 44)]), fill=STEEL_LO)
            # the hazard band that marks a machine cleared to carry a load
            d.rectangle(s(CX - 12.6, 36, CX + 12.6, 38.6), fill=HAZARD)
            for x in range(-12, 13, 5):
                d.polygon(pts([(CX + x, 36), (CX + x + 2.5, 36), (CX + x, 38.6), (CX + x - 2.5, 38.6)]), fill=DARK)
    r.part(hull)

    def cradle(d):
        wide = 11 if facing != "side" else 10
        d.polygon(pts([(CX - wide, 44), (CX + wide, 44), (CX + wide - 1.5, 52), (CX - wide + 1.5, 52)]), fill=GUN)
        d.polygon(pts([(CX - wide, 44), (CX - wide + 2.5, 44), (CX - wide + 4, 52), (CX - wide + 1.5, 52)]), fill=GUN_HI)
        for side in (-1, 1):
            x = CX + side * (wide + 2.5)
            d.rounded_rectangle(s(x - 2.6, 45, x + 2.6, 54), radius=1.2 * UP, fill=STEEL_DK)
            # the jaw, open, which is how a hauler is drawn with nothing in it
            d.polygon(pts([(x - 5, 54), (x - 1, 57.5), (x + 1, 57.5), (x + 5, 54),
                           (x + 2.6, 53.4), (x, 55.4), (x - 2.6, 53.4)]), fill=STEEL)
    r.part(cradle)

    def face(d):
        if facing == "back":
            for y in (33, 37, 41):
                d.rectangle(s(CX - 7, y, CX + 7, y + 1.4), fill=GUN_LO)
            lamp(d, CX, 30, 1.7, glow)
        elif facing == "side":
            d.rounded_rectangle(s(CX - 13, 32, CX - 4, 37), radius=1.4 * UP, fill=glow["dim"])
            d.rectangle(s(CX - 12.2, 33, CX - 5, 35.4), fill=glow["core"])
            lamp(d, CX + 8, 31, 1.9, glow)
        else:
            # the amber band a hauler carries where a robot has its visor
            d.rounded_rectangle(s(CX - 10, 29, CX + 10, 34.5), radius=1.6 * UP, fill=glow["dim"])
            d.rectangle(s(CX - 9, 30.2, CX + 9, 32.8), fill=glow["core"])
            d.rectangle(s(CX - 8, 30.4, CX - 3, 31.2), fill=glow["hot"])
            for side in (-1, 1):
                lamp(d, CX + side * 10.5, 42, 2, glow)
    r.part(face)

    def plate(d):
        if facing == "front":
            d.rounded_rectangle(s(CX - 5, 40, CX + 5, 43.4), radius=0.8 * UP, fill=DARK)
            for x in (-3.4, -0.6, 2.2):
                d.rectangle(s(CX + x, 41, CX + x + 1.2, 42.6), fill=GOLD)
    r.part(plate)
    return r.done()


# ---------------------------------------------------------------- predator
# The guard. A swept hull on two big forward ducts and two small aft ones, a
# crimson eye under a brow, a stun prod at the nose and a strobe above.

def predator(facing, kit=None):
    r = Robot()
    facing, glow = look(facing, CRIMSON)
    shadow(r, 13 if facing != "side" else 11, 57, 4)

    def arms(d):
        if facing == "side":
            d.rounded_rectangle(s(CX - 13, 31, CX + 12, 34.5), radius=1.5 * UP, fill=STEEL_DK)
        else:
            d.polygon(pts([(CX - 17, 26), (CX + 17, 26), (CX + 12, 43), (CX - 12, 43)]), fill=STEEL_DK)
            d.polygon(pts([(CX - 17, 26), (CX + 17, 26), (CX + 16.2, 28.4), (CX - 16.2, 28.4)]), fill=STEEL_LO)
    r.part(arms)

    def rotors(d):
        if facing == "side":
            duct(d, CX - 13, 27, 7.5)
            duct(d, CX + 12, 29, 6)
        else:
            for x in (-17, 17):
                duct(d, CX + x, 25, 8)
            for x in (-15, 15):
                duct(d, CX + x, 43, 6)
    r.part(rotors)

    def hull(d):
        if facing == "side":
            d.polygon(pts([(CX - 13, 29), (CX + 10, 31), (CX + 11, 42), (CX - 12, 44)]), fill=GUN_HI)
            d.polygon(pts([(CX - 13, 29), (CX - 9, 29.4), (CX - 9, 43.4), (CX - 12, 44)]), fill=STEEL_LO)
        else:
            d.polygon(pts([(CX - 11, 27), (CX + 11, 27), (CX + 7, 48), (CX - 7, 48)]), fill=GUN_HI)
            d.polygon(pts([(CX - 11, 27), (CX - 7, 27), (CX - 3.5, 48), (CX - 7, 48)]), fill=STEEL_LO)
            d.polygon(pts([(CX + 11, 27), (CX + 8, 27), (CX + 4, 48), (CX + 7, 48)]), fill=GUN)
            d.polygon(pts([(CX - 11, 27), (CX + 11, 27), (CX + 10.6, 29.4), (CX - 10.6, 29.4)]), fill=STEEL)
    r.part(hull)

    def brow(d):
        if facing == "back":
            return
        wide = 11 if facing != "side" else 8
        d.polygon(pts([(CX - wide, 30), (CX + wide, 30), (CX + wide - 1.6, 34), (CX - wide + 1.6, 34)]), fill=STEEL_DK)
        d.polygon(pts([(CX - wide, 30), (CX + wide, 30), (CX + wide - 0.5, 31.4), (CX - wide + 0.5, 31.4)]), fill=STEEL)
    r.part(brow)

    def face(d):
        if facing == "back":
            for y in (34, 38, 42):
                d.rectangle(s(CX - 6, y, CX + 6, y + 1.4), fill=GUN_LO)
            lamp(d, CX, 31, 1.6, glow)
        elif facing == "side":
            d.polygon(pts([(CX - 12, 34.5), (CX - 4, 34.5), (CX - 4, 39.5), (CX - 11, 39.5)]), fill=glow["dim"])
            d.rectangle(s(CX - 11.4, 35.5, CX - 4.8, 38), fill=glow["core"])
        else:
            d.polygon(pts([(CX - 9.5, 34.5), (CX + 9.5, 34.5), (CX + 8, 40.5), (CX - 8, 40.5)]), fill=glow["dim"])
            d.rectangle(s(CX - 8.2, 35.6, CX + 8.2, 38.4), fill=glow["core"])
            d.rectangle(s(CX - 7.4, 35.8, CX - 2.6, 36.7), fill=glow["hot"])
    r.part(face)

    def prod(d):
        if facing == "back":
            return
        x = CX + (-6 if facing == "side" else 0)
        d.polygon(pts([(x - 3.4, 46), (x + 3.4, 46), (x + 2, 53), (x - 2, 53)]), fill=STEEL_DK)
        # the two prongs, lit when the drone's lamps are up
        for side in (-1, 1):
            d.rectangle(s(x + side * 1.4 - 0.7, 52, x + side * 1.4 + 0.7, 58), fill=STEEL)
            d.rectangle(s(x + side * 1.4 - 0.7, 56.4, x + side * 1.4 + 0.7, 58), fill=glow["core"])
        d.rectangle(s(x - 2.4, 57.4, x + 2.4, 58.2), fill=glow["dim"])
    r.part(prod)

    def strobe(d):
        x = CX + (7 if facing != "side" else 4)
        d.rectangle(s(x - 1, 20, x + 1, 29), fill=STEEL_DK)
        lamp(d, x, 19, 2.4, glow)
    r.part(strobe)

    def chevron(d):
        if facing != "front":
            return
        for i, y in enumerate((42, 45)):
            d.polygon(pts([(CX - 6, y + 2.4), (CX, y), (CX + 6, y + 2.4), (CX + 6, y + 3.5),
                           (CX, y + 1.1), (CX - 6, y + 3.5)]), fill=HAZARD if i == 0 else DARK)
    r.part(chevron)
    return r.done()


MODELS = {"HaulerDrone": hauler, "PredatorDrone": predator}
GLOW = {"HaulerDrone": AMBER, "PredatorDrone": CRIMSON}


def sheet(model):
    """One drone's four pictures in the game's own arrangement: front, back,
    side and the blink, side by side."""
    draw = MODELS[model]
    im = Image.new("RGBA", (BOX * len(FACINGS), BOX), (0, 0, 0, 0))
    for col, facing in enumerate(FACINGS):
        im.paste(draw(facing), (col * BOX, 0))
    return im


# ----------------------------------------------------------------- charger
# The pad a drone is built on and comes home to. Seen from above, like every
# object the game draws on the floor: a plated square with a landing circle
# marked on it, four bollards and a contact plate. Two pictures, dark and
# live, so a pad with its drone home reads as charging from across the prison.

def charger(model, live):
    glow = GLOW[model]
    im = Image.new("RGBA", (BOX * UP, BOX * UP), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def box(x0, y0, x1, y1, fill, r=0):
        d.rounded_rectangle([x0 * UP, y0 * UP, x1 * UP, y1 * UP], radius=r * UP, fill=fill)

    def ring(x0, y0, x1, y1, fill, width):
        d.ellipse([x0 * UP, y0 * UP, x1 * UP, y1 * UP], outline=fill, width=int(width * UP))

    box(4, 6, 60, 62, (0, 0, 0, 80), 4)
    box(3, 3, 61, 59, OUTLINE, 4)
    box(5, 5, 59, 57, GUN, 3)
    box(5, 5, 59, 12, GUN_HI, 3)
    box(5, 53, 59, 57, GUN_LO, 3)
    # the landing circle, and the touchdown cross inside it
    ring(13, 15, 51, 53, OUTLINE, 2.2)
    ring(14.2, 16.2, 49.8, 51.8, glow["core"] if live else glow["dim"], 1.6)
    box(31, 22, 33, 46, STEEL_DK)
    box(20, 33, 44, 35, STEEL_DK)
    for cx, cy in ((22, 24), (42, 24), (22, 44), (42, 44)):
        d.ellipse([(cx - 2.6) * UP, (cy - 2.6) * UP, (cx + 2.6) * UP, (cy + 2.6) * UP],
                  fill=glow["core"] if live else STEEL_DK)
    # the contact plate the drone settles onto
    box(25, 30, 39, 38, OUTLINE, 1.5)
    box(26.2, 31.2, 37.8, 36.8, glow["core"] if live else STEEL_DK, 1)
    # four bollards, the two at the foot carrying the pad's lamps
    for cx, cy in ((9, 9), (55, 9), (9, 49), (55, 49)):
        d.ellipse([(cx - 4) * UP, (cy - 4) * UP, (cx + 4) * UP, (cy + 4) * UP], fill=OUTLINE)
        d.ellipse([(cx - 3) * UP, (cy - 3) * UP, (cx + 3) * UP, (cy + 3) * UP], fill=STEEL)
        d.ellipse([(cx - 3) * UP, (cy - 3) * UP, (cx + 1) * UP, (cy + 1) * UP], fill=STEEL_HI)
    for cx in (9, 55):
        lamp(d, cx, 49, 2.2, glow if live else dict(core=glow["dim"], hot=glow["core"], dim=DARK))
    # the model's mark on the head of the pad, so two pads never read alike
    if model == "HaulerDrone":
        for x in (20, 30, 40):
            box(x, 7.4, x + 6, 10, HAZARD)
            box(x + 3, 7.4, x + 6, 10, DARK)
    else:
        d.polygon([((32 - 9) * UP, 11 * UP), (32 * UP, 7 * UP), ((32 + 9) * UP, 11 * UP),
                   ((32 + 9) * UP, 12.6 * UP), (32 * UP, 8.6 * UP), ((32 - 9) * UP, 12.6 * UP)],
                  fill=glow["core"])
    return im.resize((BOX, BOX), Image.LANCZOS)
