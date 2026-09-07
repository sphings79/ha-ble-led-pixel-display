"""Draw the bundled gallery motifs.

Every picture the integration ships is generated here rather than checked in as
opaque artwork: the source stays reviewable, the licence stays unambiguous, and
the whole set can be re-rendered at another panel geometry later.

    python tools/build_gallery.py [--sheet /tmp/sheet.png]

Writes 32x32 PNGs and GIFs into custom_components/ble_led_pixel/gallery/ plus
an index.json describing them.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from pixelart import PALETTE as P
from pixelart import Canvas, contact_sheet, text_width

OUT = Path(__file__).resolve().parent.parent / "custom_components" / "ble_led_pixel" / "gallery"

# Motifs register themselves here in declaration order.
MOTIFS: list[dict] = []


def motif(motif_id: str, name: str, category: str):
    """Register a drawing function as a still motif."""

    def wrap(fn):
        MOTIFS.append({"id": motif_id, "name": name, "category": category, "fn": fn, "frames": None})
        return fn

    return wrap


def animation(motif_id: str, name: str, category: str, frames: int, duration_ms: int):
    """Register a drawing function called once per frame as an animated motif."""

    def wrap(fn):
        MOTIFS.append(
            {
                "id": motif_id,
                "name": name,
                "category": category,
                "fn": fn,
                "frames": frames,
                "duration_ms": duration_ms,
            }
        )
        return fn

    return wrap


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------


@motif("door-open", "Door open", "Status")
def door_open() -> Canvas:
    c = Canvas()
    c.frect(9, 2, 27, 31, P["G"])            # frame
    c.frect(11, 4, 25, 31, P["A"])           # light falling through the opening
    c.line(11, 4, 11, 31, P["Y"])            # bloom along the inner edges
    c.line(11, 4, 25, 4, P["Y"])
    c.fpoly([(1, 8), (8, 3), (8, 31), (1, 31)], P["C"])   # leaf swung open
    c.line(8, 3, 8, 31, P["b"])
    c.line(1, 8, 1, 31, P["b"])
    c.frect(5, 18, 6, 20, P["G"])            # handle
    return c


@motif("water-leak", "Water leak", "Status")
def water_leak() -> Canvas:
    c = Canvas()
    c.amap(
        [
            ".....d.....",
            "....dcd....",
            "...dcccd...",
            "...dcccd...",
            "..dcccccd..",
            "..dcWcccd..",
            ".dccWccccd.",
            ".dcccccccd.",
            ".dcccccccd.",
            "..dcccccd..",
            "..ddcccdd..",
            "...ddddd...",
        ],
        ox=10,
        oy=3,
    )
    c.fellipse(16, 27, 8, 3.4, P["d"])       # puddle
    c.fellipse(16, 26.8, 6, 2.3, P["B"])
    return c


# --------------------------------------------------------------------------
# Energy
# --------------------------------------------------------------------------


@motif("solar-power", "Solar power", "Energy")
def solar_power() -> Canvas:
    c = Canvas()
    c.fdisc(23, 7, 5, P["A"])                # sun, tucked into the top right
    c.fdisc(23, 7, 3, P["Y"])
    for a in range(0, 360, 45):              # rays
        rad = math.radians(a)
        for step in (7, 8):
            c.px(round(23 + step * math.cos(rad)), round(7 + step * math.sin(rad)), P["A"])
    panel = [(2, 30), (9, 15), (30, 15), (23, 30)]        # tilted module
    c.fpoly(panel, P["K"])
    inner = [(5, 28), (11, 17), (28, 17), (22, 28)]
    c.fpoly(inner, P["d"])
    for i in range(1, 4):                    # cell divisions
        t = i / 4
        c.line(round(5 + (22 - 5) * t), 28, round(11 + (28 - 11) * t), 17, P["B"])
    c.line(8, 22, 26, 22, P["B"])
    return c


# --------------------------------------------------------------------------
# Weather
# --------------------------------------------------------------------------


@motif("rain", "Rain", "Weather")
def rain() -> Canvas:
    c = Canvas()
    for cx, cy, r in ((11, 11, 5), (18, 8, 6), (24, 12, 5)):
        c.fdisc(cx, cy, r, P["W"])
    c.frect(7, 11, 28, 16, P["W"])
    c.frect(7, 15, 28, 16, P["G"])           # shaded underside
    for x0, y0 in ((9, 20), (16, 19), (23, 20)):
        c.line(x0, y0, x0 - 2, y0 + 6, P["c"])
        c.line(x0 + 1, y0, x0 - 1, y0 + 6, P["B"])
    return c


# --------------------------------------------------------------------------
# Occasions
# --------------------------------------------------------------------------


@motif("christmas-tree", "Christmas tree", "Occasion")
def christmas_tree() -> Canvas:
    c = Canvas()
    c.frect(13, 27, 18, 31, P["b"])          # trunk
    c.fpoly([(16, 14), (3, 27), (28, 27)], P["n"])
    c.fpoly([(16, 8), (6, 20), (26, 20)], P["g"])
    c.fpoly([(16, 3), (9, 13), (23, 13)], P["n"])
    for x, y, col in ((12, 11, "R"), (20, 10, "B"), (9, 18, "A"), (23, 18, "p"), (16, 24, "R"), (7, 25, "c")):
        c.fdisc(x, y, 1.4, P[col])
    c.amap([".Y.", "YYY", ".Y."], ox=15, oy=1)   # star
    return c


# --------------------------------------------------------------------------
# Notification
# --------------------------------------------------------------------------


@motif("doorbell", "Doorbell", "Notification")
def doorbell() -> Canvas:
    c = Canvas()
    c.amap(
        [
            ".......A.......",
            "......AAA......",
            "......AAA......",
            ".....AAAAA.....",
            "....AAAAAAA....",
            "...AAAAAAAAA...",
            "...AAAAAAAAA...",
            "..AAAAAAAAAAA..",
            "..AAAAAAAAAAA..",
            ".AAAAAAAAAAAAA.",
            ".AAAAAAAAAAAAA.",
            "AAAAAAAAAAAAAAA",
            "OOOOOOOOOOOOOOO",
            "......OOO......",
            ".....OOOOO.....",
            "......OOO......",
        ],
        ox=9,
        oy=4,
    )
    for radius in (11, 14):                  # sound ringing out to both sides
        for deg in range(-24, 25, 2):
            dy = math.sin(math.radians(deg)) * radius
            dx = math.cos(math.radians(deg)) * radius
            c.px(round(16 - dx), round(15 + dy), P["W"])
            c.px(round(16 + dx), round(15 + dy), P["W"])
    return c


# --------------------------------------------------------------------------
# Decoration
# --------------------------------------------------------------------------


@motif("heart", "Heart", "Decoration")
def heart() -> Canvas:
    c = Canvas()
    for y in range(32):
        for x in range(32):
            nx = (x - 15.5) / 14.5
            ny = -(y - 18.0) / 13.5
            if (nx * nx + ny * ny - 1) ** 3 - nx * nx * ny ** 3 <= 0:
                c.px(x, y, P["R"])
    body = [[c.pixels[y][x] == P["R"] for x in range(32)] for y in range(32)]
    for y in range(32):                       # one-pixel darker outline all round
        for x in range(32):
            if not body[y][x]:
                continue
            edge = any(
                not (0 <= x + dx < 32 and 0 <= y + dy < 32 and body[y + dy][x + dx])
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            if edge:
                c.px(x, y, P["r"])
    c.amap([".WW.", "WWWW", ".WW."], ox=9, oy=10)   # specular highlight
    return c


# --------------------------------------------------------------------------
# Animated
# --------------------------------------------------------------------------


@animation("washing-machine", "Washing machine", "Status", frames=8, duration_ms=110)
def washing_machine(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.frect(3, 2, 28, 31, P["W"])            # body
    c.rect(3, 2, 28, 31, P["G"])
    c.frect(4, 3, 27, 9, P["G"])             # control panel
    c.fdisc(8, 6, 2, P["K"])
    c.frect(14, 5, 24, 7, P["K"])
    c.fdisc(16, 20, 9, P["G"])               # door ring
    c.fdisc(16, 20, 7.5, P["d"])             # water
    c.fdisc(16, 20, 6.5, P["B"])
    angle = 2 * math.pi * frame / total
    for i, col in enumerate(("Y", "R", "c")):     # laundry tumbling round
        a = angle + i * 2 * math.pi / 3
        c.fdisc(16 + 3.6 * math.cos(a), 20 + 3.6 * math.sin(a), 1.8, P[col])
    return c


# --------------------------------------------------------------------------
# Status, continued
# --------------------------------------------------------------------------


@motif("door-closed", "Door closed", "Status")
def door_closed() -> Canvas:
    c = Canvas()
    c.frect(6, 2, 26, 31, P["G"])            # frame
    c.frect(8, 4, 24, 31, P["C"])            # leaf
    c.rect(11, 8, 21, 20, P["b"])            # panel moulding
    c.fdisc(20, 24, 1.6, P["A"])             # handle
    return c


@motif("window-open", "Window open", "Status")
def window_open() -> Canvas:
    c = Canvas()
    c.frect(11, 4, 29, 28, P["G"])
    c.frect(13, 6, 27, 26, P["A"])           # lit room behind
    c.fpoly([(1, 9), (11, 5), (11, 27), (1, 31)], P["G"])  # sash swung open
    c.fpoly([(3, 11), (9, 8), (9, 26), (3, 28)], P["c"])
    return c


@motif("window-closed", "Window closed", "Status")
def window_closed() -> Canvas:
    c = Canvas()
    c.frect(4, 4, 27, 28, P["G"])
    c.frect(6, 6, 25, 26, P["c"])
    c.frect(15, 6, 16, 26, P["G"])           # glazing bars
    c.frect(6, 15, 25, 16, P["G"])
    return c


@motif("motion", "Motion", "Status")
def motion() -> Canvas:
    c = Canvas()
    c.fdisc(19, 6, 3, P["Y"])                # head
    c.fpoly([(16, 10), (23, 10), (21, 20), (17, 20)], P["Y"])   # torso
    c.line(16, 12, 10, 16, P["Y"]); c.line(16, 13, 10, 17, P["Y"])
    c.line(23, 12, 28, 9, P["Y"]); c.line(23, 13, 28, 10, P["Y"])
    c.line(18, 20, 14, 30, P["Y"]); c.line(19, 20, 15, 30, P["Y"])
    c.line(21, 20, 25, 30, P["Y"]); c.line(22, 20, 26, 30, P["Y"])
    for i, x in enumerate((6, 4, 2)):        # speed lines
        c.frect(x, 8 + i * 5, x + 3, 9 + i * 5, P["G"])
    return c


@motif("lock-locked", "Locked", "Status")
def lock_locked() -> Canvas:
    c = Canvas()
    c.arc(16, 14, 8, 180, 360, P["G"], thickness=3)       # shackle, both legs down
    c.frect(8, 14, 10, 18, P["G"])
    c.frect(22, 14, 24, 18, P["G"])
    c.frect(4, 17, 28, 30, P["A"])                        # body
    c.frect(4, 17, 28, 18, P["O"])
    c.fdisc(16, 22, 2.4, P["b"])                          # keyhole
    c.fpoly([(15, 23), (18, 23), (17, 28), (16, 28)], P["b"])
    return c


@motif("lock-unlocked", "Unlocked", "Status")
def lock_unlocked() -> Canvas:
    c = Canvas()
    c.arc(8, 10, 7, 180, 360, P["G"], thickness=3)        # shackle lifted clear
    c.frect(0, 10, 2, 17, P["G"])                         # only this leg re-enters
    c.frect(13, 10, 15, 12, P["G"])
    c.frect(4, 17, 28, 30, P["g"])                        # body
    c.frect(4, 17, 28, 18, P["n"])
    c.fdisc(16, 22, 2.4, P["n"])
    c.fpoly([(15, 23), (18, 23), (17, 28), (16, 28)], P["n"])
    return c


@motif("alarm-armed", "Alarm armed", "Status")
def alarm_armed() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 2), (29, 7), (29, 18), (16, 30), (3, 18), (3, 7)], P["n"])
    c.fpoly([(16, 5), (26, 9), (26, 17), (16, 27), (6, 17), (6, 9)], P["g"])
    c.line(11, 16, 15, 21, P["W"]); c.line(11, 17, 15, 22, P["W"])
    c.line(15, 21, 22, 11, P["W"]); c.line(15, 22, 22, 12, P["W"])
    return c


@motif("alarm-triggered", "Alarm triggered", "Status")
def alarm_triggered() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 2), (29, 7), (29, 18), (16, 30), (3, 18), (3, 7)], P["r"])
    c.fpoly([(16, 5), (26, 9), (26, 17), (16, 27), (6, 17), (6, 9)], P["R"])
    c.frect(14, 9, 18, 19, P["W"])
    c.frect(14, 22, 18, 25, P["W"])
    return c


@motif("smoke", "Smoke", "Status")
def smoke() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 19), (10, 26), (11, 31), (21, 31), (22, 26)], P["O"])   # flame
    c.fpoly([(16, 23), (13, 28), (14, 31), (19, 31), (19, 28)], P["Y"])
    for cx, cy, r, col in ((11, 14, 4, "K"), (19, 12, 5, "G"), (12, 8, 4, "G"), (21, 5, 4, "K")):
        c.fdisc(cx, cy, r, P[col])
    c.fdisc(15, 11, 3, P["K"])
    return c


@motif("presence-home", "Someone home", "Status")
def presence_home() -> Canvas:
    c = Canvas()
    c.fpoly([(1, 15), (16, 3), (31, 15)], P["g"])
    c.frect(5, 15, 27, 30, P["W"])
    c.fdisc(16, 20, 3, P["n"])                            # head
    c.fpoly([(10, 30), (13, 24), (19, 24), (22, 30)], P["n"])   # shoulders
    return c


@motif("presence-away", "Nobody home", "Status")
def presence_away() -> Canvas:
    c = Canvas()
    c.fpoly([(2, 15), (16, 3), (30, 15)], P["K"])
    c.frect(6, 15, 26, 30, P["G"])
    c.line(10, 19, 22, 29, P["r"]); c.line(10, 20, 22, 30, P["r"])
    c.line(22, 19, 10, 29, P["r"]); c.line(22, 20, 10, 30, P["r"])
    return c


@motif("light-on", "Light on", "Status")
def light_on() -> Canvas:
    c = Canvas()
    for a in range(0, 360, 45):              # rays
        rad = math.radians(a)
        for step in (12, 13, 14):
            c.px(round(16 + step * math.cos(rad)), round(13 + step * math.sin(rad)), P["A"])
    c.fdisc(16, 13, 8, P["Y"])               # glass
    c.fdisc(16, 13, 6, P["W"])
    c.frect(13, 20, 19, 22, P["G"])          # cap
    c.frect(13, 23, 19, 25, P["K"])
    c.frect(14, 26, 18, 28, P["G"])
    return c


@motif("light-off", "Light off", "Status")
def light_off() -> Canvas:
    c = Canvas()
    c.fdisc(16, 13, 8, P["K"])
    c.fdisc(16, 13, 6, P["G"])
    c.frect(13, 20, 19, 22, P["K"])
    c.frect(13, 23, 19, 25, P["K"])
    c.frect(14, 26, 18, 28, P["K"])
    return c


@motif("heating", "Heating", "Status")
def heating() -> Canvas:
    c = Canvas()
    c.frect(4, 14, 28, 30, P["G"])           # radiator
    for x in range(6, 27, 5):
        c.frect(x, 16, x + 2, 28, P["W"])
    for i, x in enumerate((9, 16, 23)):      # rising heat
        c.line(x, 12, x - 2, 8, P["O"])
        c.line(x - 2, 8, x, 4, P["O"])
        c.line(x + 1, 12, x - 1, 8, P["R"])
        c.line(x - 1, 8, x + 1, 4, P["R"])
    return c


@motif("cooling", "Cooling", "Status")
def cooling() -> Canvas:
    c = Canvas()
    for a in range(0, 360, 60):
        rad = math.radians(a)
        c.line(16, 16, round(16 + 13 * math.cos(rad)), round(16 + 13 * math.sin(rad)), P["c"])
        for t in (7, 10):                    # barbs
            bx, by = 16 + t * math.cos(rad), 16 + t * math.sin(rad)
            for da in (-40, 40):
                r2 = math.radians(a + da)
                c.line(round(bx), round(by), round(bx + 3.5 * math.cos(r2)), round(by + 3.5 * math.sin(r2)), P["c"])
    c.fdisc(16, 16, 2, P["W"])
    return c


@motif("dishwasher", "Dishwasher", "Status")
def dishwasher() -> Canvas:
    c = Canvas()
    c.frect(3, 2, 28, 31, P["W"])
    c.rect(3, 2, 28, 31, P["G"])
    c.frect(4, 3, 27, 8, P["G"])
    c.frect(7, 5, 17, 6, P["K"])
    c.frect(5, 11, 26, 29, P["c"])           # window
    c.fdisc(12, 20, 5, P["W"])               # plates
    c.fdisc(12, 20, 3, P["c"])
    c.fdisc(21, 22, 4, P["W"])
    c.fdisc(21, 22, 2, P["c"])
    for x, y in ((8, 13), (17, 14), (25, 16), (14, 27)):
        c.fdisc(x, y, 1.2, P["B"])
    return c


@motif("mailbox", "Mail", "Status")
def mailbox() -> Canvas:
    c = Canvas()
    c.frect(3, 12, 25, 27, P["B"])           # box
    c.fpoly([(3, 12), (14, 12), (14, 5), (3, 5)], P["B"])
    c.frect(5, 15, 23, 25, P["W"])           # letter
    c.line(5, 15, 14, 21, P["G"]); c.line(23, 15, 14, 21, P["G"])
    c.frect(27, 4, 29, 20, P["G"])           # post flag
    c.frect(23, 4, 29, 9, P["R"])
    return c


@motif("garage-open", "Garage open", "Status")
def garage_open() -> Canvas:
    c = Canvas()
    c.fpoly([(1, 12), (16, 3), (31, 12)], P["R"])
    c.frect(3, 12, 28, 31, P["G"])
    c.frect(5, 14, 26, 31, (0, 0, 0))        # opening
    c.frect(5, 14, 26, 18, P["W"])           # door rolled up
    for y in range(14, 19, 2):
        c.frect(5, y, 26, y, P["G"])
    return c


@motif("garage-closed", "Garage closed", "Status")
def garage_closed() -> Canvas:
    c = Canvas()
    c.fpoly([(1, 12), (16, 3), (31, 12)], P["R"])
    c.frect(3, 12, 28, 31, P["G"])
    c.frect(5, 14, 26, 31, P["W"])
    for y in range(17, 31, 4):
        c.frect(5, y, 26, y, P["G"])
    return c


@motif("wifi-offline", "No connection", "Status")
def wifi_offline() -> Canvas:
    c = Canvas()
    for radius, col in ((13, P["K"]), (9, P["K"]), (5, P["K"])):
        for deg in range(200, 341, 3):
            rad = math.radians(deg)
            c.px(round(16 + radius * math.cos(rad)), round(24 + radius * math.sin(rad)), col)
            c.px(round(16 + radius * math.cos(rad)), round(24 + radius * math.sin(rad)) + 1, col)
    c.fdisc(16, 24, 2, P["K"])
    c.line(5, 5, 27, 27, P["R"]); c.line(6, 5, 28, 27, P["R"])
    return c


@animation("dryer", "Tumble dryer", "Status", frames=8, duration_ms=110)
def dryer(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.frect(2, 2, 29, 31, P["W"])                         # body
    c.rect(2, 2, 29, 31, P["G"])
    c.frect(3, 3, 28, 8, P["G"])                          # control panel
    c.frect(5, 5, 15, 6, P["K"])
    c.fdisc(24, 5.5, 2, P["O"])                           # heater lamp
    c.fdisc(16, 20, 11, P["G"])                           # door, wider than the washer's
    c.fdisc(16, 20, 9.5, P["K"])
    c.fdisc(16, 20, 8.5, P["O"])                          # warm air, not water
    angle = -2 * math.pi * frame / total                  # tumbles the other way
    for i, col in enumerate(("W", "R", "c", "Y")):
        a = angle + i * math.pi / 2
        c.fdisc(16 + 4.6 * math.cos(a), 20 + 4.6 * math.sin(a), 2, P[col])
    for i, x in enumerate((8, 16, 24)):                   # vent slots
        c.frect(x - 2, 30, x + 2, 30, P["K"])
    return c


@animation("fan", "Fan", "Status", frames=6, duration_ms=90)
def fan(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.fdisc(16, 16, 14, P["K"])
    angle = 2 * math.pi * frame / total
    for i in range(3):
        a = angle + i * 2 * math.pi / 3
        tip = (16 + 11 * math.cos(a), 16 + 11 * math.sin(a))
        side = (16 + 8 * math.cos(a + 0.9), 16 + 8 * math.sin(a + 0.9))
        c.fpoly([(16, 16), (round(tip[0]), round(tip[1])), (round(side[0]), round(side[1]))], P["c"])
    c.fdisc(16, 16, 3, P["G"])
    c.fdisc(16, 16, 1.5, P["W"])
    return c


@animation("robot-vacuum", "Robot vacuum", "Status", frames=8, duration_ms=130)
def robot_vacuum(frame: int, total: int) -> Canvas:
    c = Canvas()
    x = 9 + round(14 * abs(frame / (total - 1) * 2 - 1))
    c.frect(0, 29, 31, 31, P["K"])                        # floor
    for dx in (2, 9, 16, 23, 29):                         # dust still ahead of it
        if dx > x + 9:
            c.px(dx, 27, P["G"])
            c.px(dx + 1, 28, P["G"])
    c.fellipse(x, 24, 10, 7, P["W"])                      # low dome, seen from the side
    c.frect(x - 10, 25, x + 10, 28, P["W"])
    c.frect(x - 10, 26, x + 10, 27, P["c"])               # bumper stripe
    c.frect(x - 10, 28, x + 10, 28, P["K"])
    c.fdisc(x + 1, 15, 2.5, P["K"])                       # lidar turret
    c.frect(x, 17, x + 2, 19, P["K"])
    c.fdisc(x - 5, 21, 1.4, P["B"])                       # status light
    for i in range(3):                                    # suction, drawn in
        c.px(x - 12 - i * 2, 27 - (frame + i) % 2, P["G"])
    return c


# --------------------------------------------------------------------------
# Energy
# --------------------------------------------------------------------------


def _battery(level: float, colour: str) -> Canvas:
    """Horizontal cell with a fill bar. Shared by the battery states."""
    c = Canvas()
    c.frect(2, 10, 27, 24, P["G"])
    c.frect(4, 12, 25, 22, (0, 0, 0))
    c.frect(28, 14, 30, 20, P["G"])                       # terminal
    if level > 0:
        c.frect(4, 12, 4 + round(21 * level), 22, P[colour])
    return c


@motif("battery-full", "Battery full", "Energy")
def battery_full() -> Canvas:
    return _battery(1.0, "g")


@motif("battery-half", "Battery half", "Energy")
def battery_half() -> Canvas:
    return _battery(0.5, "A")


@motif("battery-low", "Battery low", "Energy")
def battery_low() -> Canvas:
    return _battery(0.18, "R")


@motif("grid-import", "Grid import", "Energy")
def grid_import() -> Canvas:
    c = Canvas()
    c.fpoly([(2, 16), (16, 5), (30, 16)], P["G"])         # house
    c.frect(6, 16, 26, 30, P["W"])
    c.frect(13, 8, 19, 15, P["R"])                        # arrow pointing in
    c.fpoly([(9, 15), (23, 15), (16, 23)], P["R"])
    return c


@motif("grid-export", "Grid export", "Energy")
def grid_export() -> Canvas:
    c = Canvas()
    c.fpoly([(2, 16), (16, 5), (30, 16)], P["G"])
    c.frect(6, 16, 26, 30, P["W"])
    c.frect(13, 13, 19, 23, P["g"])                       # arrow pointing out
    c.fpoly([(9, 14), (23, 14), (16, 5)], P["g"])
    return c


@motif("power-plug", "Power plug", "Energy")
def power_plug() -> Canvas:
    c = Canvas()
    c.frect(10, 2, 13, 11, P["G"])                        # prongs
    c.frect(18, 2, 21, 11, P["G"])
    c.frect(6, 11, 25, 22, P["W"])                        # body
    c.frect(6, 11, 25, 13, P["G"])
    c.fdisc(9, 17, 1.4, P["G"])                           # earth clips
    c.fdisc(22, 17, 1.4, P["G"])
    c.frect(13, 22, 18, 27, P["K"])                       # strain relief
    c.frect(14, 27, 17, 31, P["K"])
    return c


@motif("high-load", "High consumption", "Energy")
def high_load() -> Canvas:
    c = Canvas()
    c.fpoly([(19, 2), (8, 18), (15, 18), (12, 30), (25, 13), (17, 13), (22, 2)], P["A"])
    c.fpoly([(18, 5), (11, 16), (17, 16), (15, 25), (22, 15), (16, 15), (20, 5)], P["Y"])
    return c


@motif("energy-meter", "Energy meter", "Energy")
def energy_meter() -> Canvas:
    c = Canvas()
    c.fdisc(16, 17, 13, P["G"])
    c.fdisc(16, 17, 11, P["K"])
    c.arc(16, 17, 9, 180, 360, P["g"], thickness=2)
    c.arc(16, 17, 9, 300, 360, P["R"], thickness=2)
    c.line(16, 17, 24, 11, P["W"])                        # needle
    c.line(16, 17, 23, 11, P["W"])
    c.fdisc(16, 17, 2, P["W"])
    return c


@motif("eco", "Eco", "Energy")
def eco() -> Canvas:
    c = Canvas()
    for y in range(32):                                   # lens of two circles = leaf
        for x in range(32):
            if (x - 8) ** 2 + (y - 8) ** 2 <= 17 ** 2 and (x - 23) ** 2 + (y - 23) ** 2 <= 17 ** 2:
                c.px(x, y, P["g"])
    c.line(6, 25, 25, 6, P["n"])                          # midrib
    c.line(7, 26, 26, 7, P["n"])
    for t in (0.3, 0.5, 0.7):                             # veins
        x, y = round(7 + 18 * t), round(26 - 18 * t)
        c.line(x, y, x + 5, y - 2, P["n"])
    c.frect(2, 26, 7, 29, P["b"])                         # stalk
    return c


@animation("battery-charging", "Battery charging", "Energy", frames=6, duration_ms=200)
def battery_charging(frame: int, total: int) -> Canvas:
    c = _battery((frame + 1) / total, "g")
    c.fpoly([(18, 8), (11, 19), (16, 19), (14, 27), (21, 16), (16, 16), (20, 8)], P["Y"])
    return c


@animation("car-charging", "Car charging", "Energy", frames=6, duration_ms=200)
def car_charging(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.fpoly([(4, 20), (9, 12), (23, 12), (28, 20)], P["B"])   # cabin
    c.frect(2, 20, 30, 26, P["B"])
    c.frect(10, 14, 22, 19, P["c"])                       # windows
    c.fdisc(8, 27, 3, P["K"])
    c.fdisc(24, 27, 3, P["K"])
    for i in range(4):                                    # charge bar above the roof
        col = P["g"] if i <= frame % 5 else P["K"]
        c.frect(9 + i * 4, 5, 11 + i * 4, 9, col)
    c.fpoly([(16, 0), (13, 5), (16, 5), (14, 10), (19, 4), (16, 4), (18, 0)], P["Y"])
    return c


# --------------------------------------------------------------------------
# Weather
# --------------------------------------------------------------------------


def _cloud(c: Canvas, ox: int = 0, oy: int = 0, col: str = "W", shade: str = "G") -> None:
    """Standard cloud, so every weather motif shares one silhouette."""
    for cx, cy, r in ((11, 11, 5), (18, 8, 6), (24, 12, 5)):
        c.fdisc(cx + ox, cy + oy, r, P[col])
    c.frect(7 + ox, 11 + oy, 28 + ox, 16 + oy, P[col])
    c.frect(7 + ox, 15 + oy, 28 + ox, 16 + oy, P[shade])


@motif("sunny", "Sunny", "Weather")
def sunny() -> Canvas:
    c = Canvas()
    for a in range(0, 360, 30):
        rad = math.radians(a)
        for step in (12, 13, 14):
            c.px(round(16 + step * math.cos(rad)), round(16 + step * math.sin(rad)), P["A"])
    c.fdisc(16, 16, 9, P["A"])
    c.fdisc(16, 16, 7, P["Y"])
    return c


@motif("cloudy", "Cloudy", "Weather")
def cloudy() -> Canvas:
    c = Canvas()
    for cx, cy, r in ((16, 8, 5), (22, 10, 5)):           # smaller cloud behind
        c.fdisc(cx, cy, r, P["G"])
    c.frect(13, 8, 27, 13, P["G"])
    _cloud(c, ox=-2, oy=6)                                # front cloud, unbroken white
    return c


@motif("partly-cloudy", "Partly cloudy", "Weather")
def partly_cloudy() -> Canvas:
    c = Canvas()
    for a in range(0, 360, 45):
        rad = math.radians(a)
        for step in (9, 10):
            c.px(round(11 + step * math.cos(rad)), round(10 + step * math.sin(rad)), P["A"])
    c.fdisc(11, 10, 6.5, P["A"])
    c.fdisc(11, 10, 5, P["Y"])
    _cloud(c, ox=1, oy=8)
    return c


@motif("fog", "Fog", "Weather")
def fog() -> Canvas:
    c = Canvas()
    _cloud(c, oy=-3, col="G", shade="K")
    for i, y in enumerate((19, 23, 27)):
        x0 = 2 + (i % 2) * 4
        c.frect(x0, y, x0 + 18, y + 1, P["W"])
        c.frect(x0 + 21, y, min(29, x0 + 26), y + 1, P["W"])
    return c


@motif("moon", "Clear night", "Weather")
def moon() -> Canvas:
    c = Canvas()
    c.fdisc(15, 16, 11, P["Y"])
    c.fdisc(21, 12, 10, (0, 0, 0))                        # bite out of it
    for x, y, r in ((26, 22, 1.4), (23, 27, 1), (28, 8, 1)):
        c.fdisc(x, y, r, P["W"])
    return c


@motif("rainbow", "Rainbow", "Weather")
def rainbow() -> Canvas:
    c = Canvas()
    for i, col in enumerate(("R", "O", "Y", "g", "c", "B", "P")):
        c.arc(16, 30, 15 - i * 2, 180, 360, P[col], thickness=2)
    return c


@motif("hot", "Hot", "Weather")
def hot() -> Canvas:
    c = Canvas()
    c.frect(11, 2, 17, 22, P["W"])                        # tube
    c.fdisc(14, 25, 6, P["W"])
    c.frect(13, 8, 15, 22, P["R"])                        # mercury
    c.fdisc(14, 25, 4, P["R"])
    for y in (5, 9, 13, 17):                              # scale
        c.frect(17, y, 19, y, P["G"])
    c.fdisc(26, 7, 4, P["A"])                             # little sun
    c.fdisc(26, 7, 2.5, P["Y"])
    return c


@motif("cold", "Cold", "Weather")
def cold() -> Canvas:
    c = Canvas()
    c.frect(11, 2, 17, 22, P["W"])
    c.fdisc(14, 25, 6, P["W"])
    c.frect(13, 17, 15, 22, P["c"])
    c.fdisc(14, 25, 4, P["c"])
    for y in (5, 9, 13, 17):
        c.frect(17, y, 19, y, P["G"])
    for a in range(0, 360, 60):                           # little snowflake
        rad = math.radians(a)
        c.line(26, 7, round(26 + 5 * math.cos(rad)), round(7 + 5 * math.sin(rad)), P["c"])
    return c


@motif("sunrise", "Sunrise", "Weather")
def sunrise() -> Canvas:
    c = Canvas()
    for a in range(190, 351, 20):
        rad = math.radians(a)
        for step in (12, 13, 14):
            c.px(round(16 + step * math.cos(rad)), round(22 + step * math.sin(rad)), P["A"])
    c.fdisc(16, 22, 8, P["A"])
    c.fdisc(16, 22, 6, P["Y"])
    c.frect(0, 23, 31, 31, (0, 0, 0))                     # horizon cuts it in half
    c.frect(0, 23, 31, 24, P["O"])
    c.frect(0, 27, 31, 28, P["b"])
    return c


@animation("heavy-rain", "Heavy rain", "Weather", frames=4, duration_ms=120)
def heavy_rain(frame: int, total: int) -> Canvas:
    c = Canvas()
    _cloud(c, oy=-3, col="G", shade="K")
    for i, x in enumerate((6, 12, 18, 24, 29)):
        off = (frame + i) % total * 3
        for k in range(2):
            y = 16 + off + k * 6
            if y < 31:
                c.line(x, y, x - 2, y + 4, P["c"])
    return c


@animation("snow", "Snow", "Weather", frames=6, duration_ms=200)
def snow(frame: int, total: int) -> Canvas:
    c = Canvas()
    _cloud(c, oy=-4)
    for i, x in enumerate((7, 13, 19, 25)):
        y = 15 + ((frame + i * 2) % total) * 3
        if y < 31:
            c.px(x, y, P["W"]); c.px(x - 1, y, P["W"]); c.px(x + 1, y, P["W"])
            c.px(x, y - 1, P["W"]); c.px(x, y + 1, P["W"])
    return c


@animation("thunderstorm", "Thunderstorm", "Weather", frames=6, duration_ms=140)
def thunderstorm(frame: int, total: int) -> Canvas:
    c = Canvas()
    _cloud(c, oy=-4, col="G", shade="K")
    if frame % 3 != 2:                                    # the bolt strikes, then rests
        c.fpoly([(18, 15), (11, 25), (16, 25), (13, 31), (22, 22), (16, 22), (20, 15)], P["Y"])
    for x in (7, 26):
        c.line(x, 18 + (frame % 3) * 3, x - 2, 22 + (frame % 3) * 3, P["c"])
    return c


@animation("wind", "Wind", "Weather", frames=4, duration_ms=150)
def wind(frame: int, total: int) -> Canvas:
    c = Canvas()
    gusts = ((8, 16, 4), (16, 22, 3), (24, 12, 5))        # y, length, hook radius
    for i, (y, length, hook) in enumerate(gusts):
        off = ((frame + i) % total) * 2
        x0 = 1 + off
        x1 = x0 + length
        c.frect(x0, y, x1, y + 1, P["W"])                 # gust line
        c.arc(x1, y + hook, hook, -90, 170, P["W"], thickness=2)
    return c


# --------------------------------------------------------------------------
# Occasions
# --------------------------------------------------------------------------


def _star_points(cx: float, cy: float, r_out: float, r_in: float, rot: float = -90) -> list[tuple[int, int]]:
    pts = []
    for i in range(10):
        a = math.radians(rot + i * 36)
        r = r_out if i % 2 == 0 else r_in
        pts.append((round(cx + r * math.cos(a)), round(cy + r * math.sin(a))))
    return pts


@motif("alarm-clock", "Alarm clock", "Occasion")
def alarm_clock() -> Canvas:
    c = Canvas()
    c.fdisc(8, 6, 4, P["G"])                              # bells
    c.fdisc(24, 6, 4, P["G"])
    c.fdisc(16, 18, 12, P["G"])
    c.fdisc(16, 18, 10, P["W"])
    c.line(16, 18, 16, 11, P["K"]); c.line(17, 18, 17, 11, P["K"])
    c.line(16, 18, 22, 21, P["R"]); c.line(16, 19, 22, 22, P["R"])
    c.fdisc(16, 18, 1.6, P["K"])
    c.frect(4, 28, 8, 31, P["G"])                         # feet
    c.frect(23, 28, 27, 31, P["G"])
    return c


@motif("calendar", "Calendar", "Occasion")
def calendar() -> Canvas:
    c = Canvas()
    c.frect(3, 5, 28, 30, P["W"])
    c.frect(3, 5, 28, 12, P["R"])
    c.frect(7, 1, 10, 8, P["G"])                          # rings
    c.frect(21, 1, 24, 8, P["G"])
    for row in range(3):
        for col in range(4):
            x, y = 6 + col * 6, 16 + row * 5
            c.frect(x, y, x + 3, y + 2, P["B"] if (row, col) == (1, 2) else P["G"])
    return c


@motif("birthday-cake", "Birthday", "Occasion")
def birthday_cake() -> Canvas:
    c = Canvas()
    for i, (x, col) in enumerate(((9, "R"), (16, "c"), (23, "p"))):        # candles
        c.frect(x - 1, 9, x + 1, 16, P[col])
        c.fpoly([(x, 3), (x - 2, 8), (x + 2, 8)], P["O"])
        c.fpoly([(x, 5), (x - 1, 8), (x + 1, 8)], P["Y"])
    c.frect(2, 17, 29, 22, P["W"])                        # icing
    for x in range(3, 30, 5):                             # drips
        c.fdisc(x, 22, 2.5, P["W"])
    c.frect(2, 22, 29, 29, P["C"])                        # sponge
    c.frect(2, 25, 29, 26, P["p"])                        # jam layer
    c.frect(0, 29, 31, 31, P["G"])                        # plate
    return c


@motif("gift", "Gift", "Occasion")
def gift() -> Canvas:
    c = Canvas()
    c.frect(3, 12, 29, 30, P["R"])                        # box
    c.frect(3, 12, 29, 16, P["r"])                        # lid
    c.frect(14, 12, 18, 30, P["Y"])                       # ribbon
    c.fdisc(11, 9, 4.5, P["Y"])                           # bow
    c.fdisc(21, 9, 4.5, P["Y"])
    c.fdisc(11, 9, 2, P["A"])
    c.fdisc(21, 9, 2, P["A"])
    c.frect(14, 7, 18, 12, P["Y"])
    return c


@motif("halloween-pumpkin", "Halloween", "Occasion")
def halloween_pumpkin() -> Canvas:
    c = Canvas()
    c.frect(14, 2, 18, 8, P["n"])                         # stalk
    c.fellipse(16, 19, 14, 12, P["O"])
    c.fellipse(8, 19, 5, 11, P["A"])                      # lobes
    c.fellipse(24, 19, 5, 11, P["A"])
    c.fpoly([(8, 12), (14, 12), (11, 18)], (0, 0, 0))     # eyes
    c.fpoly([(18, 12), (24, 12), (21, 18)], (0, 0, 0))
    c.fpoly([(16, 18), (13, 22), (19, 22)], (0, 0, 0))    # nose
    c.frect(8, 24, 24, 27, (0, 0, 0))                     # mouth
    for x in (11, 16, 21):
        c.frect(x - 1, 22, x + 1, 24, (0, 0, 0))
    return c


@motif("easter-egg", "Easter", "Occasion")
def easter_egg() -> Canvas:
    c = Canvas()
    for y in range(32):                                   # egg: narrower at the top
        for x in range(32):
            ry = 14.0
            rx = 9.0 * (1.0 + 0.22 * (y - 17) / ry)
            if ((x - 16) / rx) ** 2 + ((y - 17) / ry) ** 2 <= 1:
                c.px(x, y, P["W"])
    for y0, col in ((8, "R"), (14, "c"), (20, "Y"), (26, "P")):
        for y in range(y0, y0 + 3):
            for x in range(32):
                if c.pixels[y][x] == P["W"]:
                    c.px(x, y, P[col])
    return c


@motif("snowman", "Snowman", "Occasion")
def snowman() -> Canvas:
    c = Canvas()
    c.fdisc(16, 24, 8, P["W"])                            # body
    c.fdisc(16, 12, 6, P["W"])                            # head
    c.frect(9, 3, 23, 6, P["K"])                          # hat
    c.frect(12, 0, 20, 4, P["K"])
    c.fdisc(13, 11, 1.2, P["K"])                          # eyes
    c.fdisc(19, 11, 1.2, P["K"])
    c.fpoly([(16, 13), (16, 16), (24, 15)], P["O"])       # carrot
    for y in (20, 24, 28):
        c.fdisc(16, y, 1.3, P["K"])                       # buttons
    return c


@motif("ghost", "Ghost", "Occasion")
def ghost() -> Canvas:
    c = Canvas()
    c.fdisc(16, 14, 11, P["W"])
    c.frect(5, 14, 27, 26, P["W"])
    for i, x in enumerate(range(5, 28, 7)):               # scalloped hem
        c.fdisc(x + 3, 26, 3.6, P["W"])
    c.frect(0, 30, 31, 31, (0, 0, 0))
    c.fdisc(12, 13, 2.4, P["K"])                          # eyes
    c.fdisc(21, 13, 2.4, P["K"])
    c.fdisc(16, 19, 2, P["K"])                            # mouth
    return c


@motif("star", "Star", "Occasion")
def star() -> Canvas:
    c = Canvas()
    c.fpoly(_star_points(16, 17, 15, 6), P["A"])
    c.fpoly(_star_points(16, 17, 10, 4), P["Y"])
    return c


@animation("hourglass", "Timer", "Occasion", frames=6, duration_ms=280)
def hourglass(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.frect(5, 2, 27, 5, P["C"])                          # frames
    c.frect(5, 26, 27, 29, P["C"])
    c.fpoly([(7, 6), (25, 6), (17, 16), (15, 16)], P["W"])
    c.fpoly([(15, 16), (17, 16), (25, 25), (7, 25)], P["W"])
    top = 1.0 - frame / (total - 1)
    if top > 0:                                           # sand still up top
        h = round(9 * top)
        c.fpoly([(7 + (9 - h), 15 - h), (25 - (9 - h), 15 - h), (17, 15), (15, 15)], P["A"])
    fill = round(8 * (1 - top))
    if fill > 0:
        c.fpoly([(9, 25), (23, 25), (23 - (8 - fill), 25 - fill), (9 + (8 - fill), 25 - fill)], P["A"])
    if 0 < frame < total - 1:
        c.frect(16, 17, 16, 23, P["A"])                   # the stream
    return c


@animation("advent-candle", "Candle", "Occasion", frames=4, duration_ms=180)
def advent_candle(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.frect(11, 12, 21, 29, P["R"])                       # candle
    c.frect(11, 12, 13, 29, P["r"])
    c.frect(4, 29, 28, 31, P["n"])                        # wreath
    for x in (7, 13, 19, 25):
        c.fdisc(x, 29, 2.5, P["n"])
    c.frect(15, 9, 17, 12, P["K"])                        # wick
    wobble = (0, 1, 0, -1)[frame]
    c.fpoly([(16 + wobble, 1), (12, 8), (16, 11), (20, 8)], P["O"])
    c.fpoly([(16 + wobble, 4), (14, 8), (16, 10), (18, 8)], P["Y"])
    return c


@animation("fireworks", "Fireworks", "Occasion", frames=6, duration_ms=140)
def fireworks(frame: int, total: int) -> Canvas:
    c = Canvas()
    r = 4 + frame * 4
    for i, col in enumerate(("R", "Y", "c", "p")):
        for a in range(i * 11, 360, 45):
            rad = math.radians(a)
            inner = max(1, r - 7)                         # streaks, not a ring
            c.line(
                round(16 + inner * math.cos(rad)), round(15 + inner * math.sin(rad)),
                round(16 + r * math.cos(rad)), round(15 + r * math.sin(rad)), P[col],
            )
    if frame < 2:
        c.fdisc(16, 15, 2, P["W"])
    return c


# --------------------------------------------------------------------------
# Notification
# --------------------------------------------------------------------------


def _badge(c: Canvas, ring: str, fill: str) -> None:
    c.fdisc(16, 16, 14, P[ring])
    c.fdisc(16, 16, 12, P[fill])


@motif("ok", "All good", "Notification")
def ok() -> Canvas:
    c = Canvas()
    _badge(c, "n", "g")
    for d in range(3):
        c.line(9, 16 + d, 14, 21 + d, P["W"])
        c.line(14, 21 + d, 23, 10 + d, P["W"])
    return c


@motif("error", "Error", "Notification")
def error() -> Canvas:
    c = Canvas()
    _badge(c, "r", "R")
    for d in range(3):
        c.line(10, 9 + d, 22, 21 + d, P["W"])
        c.line(22, 9 + d, 10, 21 + d, P["W"])
    return c


@motif("warning", "Warning", "Notification")
def warning() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 1), (31, 29), (1, 29)], P["O"])
    c.fpoly([(16, 6), (27, 27), (5, 27)], P["A"])
    c.frect(14, 12, 18, 21, P["K"])
    c.frect(14, 23, 18, 26, P["K"])
    return c


@motif("info", "Info", "Notification")
def info() -> Canvas:
    c = Canvas()
    _badge(c, "d", "B")
    c.frect(14, 8, 18, 12, P["W"])
    c.frect(14, 14, 18, 24, P["W"])
    return c


@motif("question", "Question", "Notification")
def question() -> Canvas:
    c = Canvas()
    _badge(c, "p", "P")
    c.amap(
        [
            "....WWWWWW....",
            "..WWWWWWWWWW..",
            ".WWWW....WWWW.",
            "WWW........WWW",
            "WWW........WWW",
            "..........WWWW",
            ".......WWWWWW.",
            "....WWWWWWW...",
            "....WWWWW.....",
            "....WWWW......",
            "....WWWW......",
            "..............",
            "....WWWW......",
            "....WWWW......",
        ],
        ox=9,
        oy=7,
    )
    return c


@motif("message", "Message", "Notification")
def message() -> Canvas:
    c = Canvas()
    c.frect(2, 5, 29, 23, P["W"])
    c.fpoly([(8, 23), (18, 23), (9, 30)], P["W"])
    for y in (11, 16):
        c.frect(7, y, 24, y + 2, P["B"])
    c.frect(7, 6, 24, 8, P["B"])
    return c


@motif("envelope", "E-mail", "Notification")
def envelope() -> Canvas:
    c = Canvas()
    c.frect(2, 8, 29, 26, P["W"])
    c.rect(2, 8, 29, 26, P["G"])
    c.line(2, 8, 16, 19, P["G"]); c.line(3, 8, 17, 19, P["G"])
    c.line(29, 8, 16, 19, P["G"]); c.line(28, 8, 15, 19, P["G"])
    c.line(2, 26, 12, 18, P["G"])
    c.line(29, 26, 20, 18, P["G"])
    return c


@motif("mute", "Muted", "Notification")
def mute() -> Canvas:
    c = Canvas()
    c.amap(
        [
            ".......W.......",
            "......WWW......",
            "......WGW......",
            ".....WGGGW.....",
            "....WGGGGGW....",
            "...WGGGGGGGW...",
            "...WGGGGGGGW...",
            "..WGGGGGGGGGW..",
            "..WGGGGGGGGGW..",
            ".WGGGGGGGGGGGW.",
            ".WGGGGGGGGGGGW.",
            "WWWWWWWWWWWWWWW",
            "......WWW......",
            ".....WGGGW.....",
            "......WWW......",
        ],
        ox=9,
        oy=5,
    )
    for d in (-1, 0, 1, 2):                               # slash, cut free of the bell
        c.line(4 + d, 26, 27 + d, 3, (0, 0, 0))
    for d in (0, 1):
        c.line(5 + d, 26, 28 + d, 3, P["R"])
    return c


@animation("phone-call", "Incoming call", "Notification", frames=4, duration_ms=130)
def phone_call(frame: int, total: int) -> Canvas:
    c = Canvas()
    tilt = (-1, 0, 1, 0)[frame]
    c.fpoly(
        [(6 + tilt, 6), (13 + tilt, 4), (16 + tilt, 11), (12 + tilt, 14),
         (18 + tilt, 20), (24 + tilt, 16), (28 + tilt, 23), (22 + tilt, 28), (10 + tilt, 20)],
        P["g"],
    )
    for radius in (11, 14):                               # ringing
        if frame % 2 == 0:
            c.arc(20, 8, radius, -80, -10, P["W"], thickness=2)
    return c


# --------------------------------------------------------------------------
# Decoration
# --------------------------------------------------------------------------


def _face(c: Canvas, base: str = "Y", rim: str = "A") -> None:
    c.fdisc(16, 16, 14, P[rim])
    c.fdisc(16, 16, 12.5, P[base])


@motif("smiley-happy", "Happy", "Decoration")
def smiley_happy() -> Canvas:
    c = Canvas()
    _face(c)
    c.fdisc(11, 12, 2, P["K"])
    c.fdisc(21, 12, 2, P["K"])
    c.arc(16, 17, 7, 25, 155, P["K"], thickness=3)
    return c


@motif("smiley-sad", "Sad", "Decoration")
def smiley_sad() -> Canvas:
    c = Canvas()
    _face(c)
    c.fdisc(11, 12, 2, P["K"])
    c.fdisc(21, 12, 2, P["K"])
    c.arc(16, 27, 7, 205, 335, P["K"], thickness=3)
    return c


@motif("smiley-wink", "Wink", "Decoration")
def smiley_wink() -> Canvas:
    c = Canvas()
    _face(c)
    c.fdisc(11, 12, 2, P["K"])
    c.frect(18, 12, 24, 14, P["K"])
    c.arc(16, 17, 7, 25, 155, P["K"], thickness=3)
    return c


@motif("smiley-cool", "Cool", "Decoration")
def smiley_cool() -> Canvas:
    c = Canvas()
    _face(c)
    c.frect(4, 10, 28, 12, P["K"])                        # shades
    c.frect(5, 12, 14, 17, P["K"])
    c.frect(18, 12, 27, 17, P["K"])
    c.arc(16, 18, 7, 25, 155, P["K"], thickness=3)
    return c


@motif("cat", "Cat", "Decoration")
def cat() -> Canvas:
    c = Canvas()
    c.fpoly([(5, 12), (7, 2), (14, 8)], P["G"])           # ears
    c.fpoly([(27, 12), (25, 2), (18, 8)], P["G"])
    c.fpoly([(7, 11), (8, 5), (12, 9)], P["p"])
    c.fpoly([(25, 11), (24, 5), (20, 9)], P["p"])
    c.fellipse(16, 18, 12, 10, P["G"])                    # head
    c.fdisc(11, 16, 2.2, P["g"])                          # eyes
    c.fdisc(21, 16, 2.2, P["g"])
    c.fpoly([(16, 20), (13, 22), (19, 22)], P["p"])       # nose
    for y, x0, x1 in ((21, 1, 8), (23, 1, 8), (21, 24, 31), (23, 24, 31)):
        c.frect(x0, y, x1, y, P["W"])                     # whiskers
    return c


@motif("dog", "Dog", "Decoration")
def dog() -> Canvas:
    c = Canvas()
    c.fellipse(4, 18, 4, 10, P["b"])                      # floppy ears
    c.fellipse(28, 18, 4, 10, P["b"])
    c.fellipse(16, 17, 11, 11, P["C"])                    # head
    c.fdisc(11, 15, 2.4, P["K"])                          # eyes
    c.fdisc(21, 15, 2.4, P["K"])
    c.fellipse(16, 22, 3.5, 2.5, P["K"])                  # nose
    c.line(16, 24, 16, 26, P["K"])
    c.arc(13, 25, 3, 0, 160, P["K"], thickness=2)         # mouth
    c.arc(19, 25, 3, 20, 180, P["K"], thickness=2)
    return c


@motif("coffee", "Coffee", "Decoration")
def coffee() -> Canvas:
    c = Canvas()
    for x in (11, 16, 21):                                # steam
        c.line(x, 10, x - 2, 6, P["G"])
        c.line(x - 2, 6, x, 2, P["G"])
    c.arc(23, 20, 6, 285, 75, P["W"], thickness=3)        # handle
    c.fpoly([(5, 14), (21, 14), (19, 28), (7, 28)], P["W"])    # tapered mug
    c.frect(4, 14, 22, 16, P["W"])                        # rim
    c.frect(6, 19, 20, 22, P["R"])                        # band
    c.frect(2, 29, 24, 31, P["G"])                        # saucer
    return c


@motif("pizza", "Pizza", "Decoration")
def pizza() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 1), (2, 29), (30, 29)], P["A"])         # slice
    c.fpoly([(16, 5), (5, 27), (27, 27)], P["O"])
    c.frect(2, 27, 30, 30, P["C"])                        # crust
    for x, y in ((16, 12), (11, 21), (21, 20), (16, 25)):
        c.fdisc(x, y, 2.2, P["R"])                        # salami
    return c


@motif("beer", "Beer", "Decoration")
def beer() -> Canvas:
    c = Canvas()
    c.frect(6, 8, 22, 30, P["A"])                         # glass
    c.frect(6, 4, 22, 9, P["W"])                          # head
    for x in (8, 13, 18):
        c.fdisc(x, 4, 3, P["W"])
    c.arc(23, 17, 5, 270, 90, P["W"], thickness=3)        # handle
    for x, y in ((10, 16), (16, 21), (12, 26)):
        c.fdisc(x, y, 1.2, P["Y"])                        # bubbles
    return c


@motif("game-controller", "Gaming", "Decoration")
def game_controller() -> Canvas:
    c = Canvas()
    c.fellipse(8, 20, 8, 8, P["K"])
    c.fellipse(24, 20, 8, 8, P["K"])
    c.frect(8, 13, 24, 25, P["K"])
    c.frect(6, 18, 12, 20, P["W"])                        # d-pad
    c.frect(8, 16, 10, 22, P["W"])
    c.fdisc(22, 17, 1.8, P["R"])                          # buttons
    c.fdisc(26, 21, 1.8, P["g"])
    c.fdisc(22, 24, 1.8, P["c"])
    return c


@motif("rocket", "Rocket", "Decoration")
def rocket() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 1), (10, 12), (10, 24), (22, 24), (22, 12)], P["W"])
    c.fpoly([(16, 4), (13, 12), (19, 12)], P["R"])        # nose band
    c.fdisc(16, 16, 3.2, P["c"])                          # window
    c.fdisc(16, 16, 2, P["B"])
    c.fpoly([(10, 17), (4, 27), (10, 25)], P["R"])        # fins
    c.fpoly([(22, 17), (28, 27), (22, 25)], P["R"])
    c.fpoly([(13, 24), (19, 24), (16, 31)], P["O"])       # flame
    return c


@motif("skull", "Skull", "Decoration")
def skull() -> Canvas:
    c = Canvas()
    c.fellipse(16, 14, 12, 11, P["W"])
    c.frect(9, 20, 23, 26, P["W"])
    c.fdisc(11, 14, 3.6, P["K"])                          # sockets
    c.fdisc(21, 14, 3.6, P["K"])
    c.fpoly([(16, 18), (13, 23), (19, 23)], P["K"])       # nose
    for x in (11, 15, 19):                                # teeth
        c.frect(x, 26, x + 2, 30, P["W"])
    c.frect(9, 25, 23, 26, P["G"])
    return c


@motif("invader", "Invader", "Decoration")
def invader() -> Canvas:
    c = Canvas()
    c.amap(
        [
            "..g.....g..",
            "...g...g...",
            "..ggggggg..",
            ".gg.ggg.gg.",
            "ggggggggggg",
            "g.ggggggg.g",
            "g.g.....g.g",
            "...gg.gg...",
        ],
        ox=0,
        oy=0,
    )
    big = Canvas()
    for y in range(8):
        for x in range(11):
            col = c.pixels[y][x]
            if col != (0, 0, 0):
                big.frect(2 + x * 3 - 1, 4 + y * 3, 2 + x * 3 + 1, 4 + y * 3 + 2, col)
    return big


@motif("flower", "Flower", "Decoration")
def flower() -> Canvas:
    c = Canvas()
    c.frect(15, 16, 17, 31, P["n"])                       # stem
    c.fellipse(9, 24, 6, 3, P["g"])                       # leaves
    c.fellipse(23, 27, 6, 3, P["g"])
    for a in range(0, 360, 60):
        rad = math.radians(a)
        c.fdisc(16 + 6 * math.cos(rad), 12 + 6 * math.sin(rad), 4, P["p"])
    c.fdisc(16, 12, 4, P["Y"])
    return c


@motif("key", "Key", "Decoration")
def key() -> Canvas:
    c = Canvas()
    c.fdisc(9, 16, 8, P["A"])                             # bow
    c.fdisc(9, 16, 4, (0, 0, 0))
    c.frect(15, 14, 30, 18, P["A"])                       # shaft
    c.frect(23, 18, 25, 24, P["A"])                       # teeth
    c.frect(28, 18, 30, 22, P["A"])
    return c


@motif("arrow-up", "Arrow up", "Symbol")
def arrow_up() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 2), (2, 17), (31, 17)], P["g"])
    c.frect(11, 17, 21, 30, P["g"])
    return c


@motif("arrow-down", "Arrow down", "Symbol")
def arrow_down() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 30), (2, 15), (31, 15)], P["R"])
    c.frect(11, 2, 21, 15, P["R"])
    return c


@motif("arrow-left", "Arrow left", "Symbol")
def arrow_left() -> Canvas:
    c = Canvas()
    c.fpoly([(2, 16), (17, 2), (17, 31)], P["c"])
    c.frect(17, 11, 30, 21, P["c"])
    return c


@motif("arrow-right", "Arrow right", "Symbol")
def arrow_right() -> Canvas:
    c = Canvas()
    c.fpoly([(30, 16), (15, 2), (15, 31)], P["c"])
    c.frect(2, 11, 15, 21, P["c"])
    return c


@motif("bluetooth", "Bluetooth", "Symbol")
def bluetooth() -> Canvas:
    c = Canvas()
    for d in range(3):
        c.line(15 + d, 2, 15 + d, 30, P["c"])
        c.line(15 + d, 2, 24 + d, 10, P["c"])
        c.line(24 + d, 10, 15 + d, 17, P["c"])
        c.line(15 + d, 15, 24 + d, 22, P["c"])
        c.line(24 + d, 22, 15 + d, 30, P["c"])
        c.line(7 + d, 9, 17 + d, 17, P["c"])
        c.line(7 + d, 23, 17 + d, 15, P["c"])
    return c


@motif("wifi", "Connected", "Symbol")
def wifi() -> Canvas:
    c = Canvas()
    for radius in (5, 10, 15):
        c.arc(16, 26, radius, 205, 335, P["c"], thickness=3)
    c.fdisc(16, 26, 2.5, P["c"])
    return c


@animation("fire", "Fire", "Decoration", frames=6, duration_ms=110)
def fire(frame: int, total: int) -> Canvas:
    c = Canvas()
    wob = (0, 1, 2, 1, 0, -1)[frame]
    c.fpoly([(16 + wob, 1), (6, 15), (8, 26), (16, 31), (24, 26), (26, 15)], P["R"])
    c.fpoly([(16 + wob, 7), (10, 18), (11, 26), (16, 30), (21, 26), (22, 18)], P["O"])
    c.fpoly([(16 - wob, 15), (13, 22), (14, 28), (18, 28), (19, 22)], P["Y"])
    return c


@animation("equalizer", "Music", "Decoration", frames=6, duration_ms=120)
def equalizer(frame: int, total: int) -> Canvas:
    c = Canvas()
    heights = ((22, 10, 26, 14, 18), (12, 24, 14, 26, 8), (26, 16, 8, 20, 24),
               (10, 28, 20, 12, 16), (20, 12, 24, 8, 26), (16, 20, 12, 24, 10))
    for i, h in enumerate(heights[frame % len(heights)]):
        x = 2 + i * 6
        col = ("R", "O", "Y", "g", "c")[i]
        c.frect(x, 30 - h, x + 4, 30, P[col])
    return c


@animation("heartbeat", "Heartbeat", "Decoration", frames=6, duration_ms=110)
def heartbeat(frame: int, total: int) -> Canvas:
    c = Canvas()
    scale = (1.0, 1.12, 1.0, 0.92, 1.0, 1.06)[frame]
    for y in range(32):
        for x in range(32):
            nx = (x - 15.5) / (14.5 * scale)
            ny = -(y - 18.0) / (13.5 * scale)
            if (nx * nx + ny * ny - 1) ** 3 - nx * nx * ny ** 3 <= 0:
                c.px(x, y, P["R"])
    c.amap([".WW.", "WWWW", ".WW."], ox=9, oy=10)
    return c


@animation("spinner", "Working", "Symbol", frames=8, duration_ms=100)
def spinner(frame: int, total: int) -> Canvas:
    c = Canvas()
    for i in range(8):
        a = math.radians(i * 45 - 90)
        fade = (i - frame) % 8
        col = P["W"] if fade == 0 else (P["c"] if fade == 1 else (P["B"] if fade == 2 else P["K"]))
        c.fdisc(16 + 11 * math.cos(a), 16 + 11 * math.sin(a), 3, col)
    return c


@animation("pacman", "Pac-Man", "Decoration", frames=4, duration_ms=130)
def pacman(frame: int, total: int) -> Canvas:
    c = Canvas()
    mouth = (5, 22, 38, 22)[frame]
    c.fdisc(13, 16, 12, P["Y"])
    if mouth > 5:
        c.fpoly([(13, 16), (31, round(16 - 18 * math.tan(math.radians(mouth)))),
                 (31, round(16 + 18 * math.tan(math.radians(mouth))))], (0, 0, 0))
    c.fdisc(13, 9, 1.8, P["K"])
    for i, x in enumerate((27, 31)):                      # pellets ahead
        if (frame + i) % 2 == 0:
            c.fdisc(x, 16, 2, P["W"])
    return c


# --------------------------------------------------------------------------
# Home, continued
# --------------------------------------------------------------------------


@motif("humidity", "Humidity", "Weather")
def humidity() -> Canvas:
    c = Canvas()
    c.amap(
        [
            ".....d.....",
            "....dcd....",
            "...dcccd...",
            "..dcccccd..",
            "..dcWcccd..",
            ".dccWccccd.",
            ".dcccccccd.",
            ".dcccccccd.",
            "..dcccccd..",
            "...ddddd...",
        ],
        ox=2,
        oy=4,
    )
    c.fdisc(21, 10, 3.5, P["W"])                          # per-cent sign
    c.fdisc(21, 10, 1.6, (0, 0, 0))
    c.fdisc(28, 22, 3.5, P["W"])
    c.fdisc(28, 22, 1.6, (0, 0, 0))
    c.line(29, 6, 20, 26, P["W"]); c.line(30, 6, 21, 26, P["W"])
    return c


@motif("air-quality", "Air quality", "Status")
def air_quality() -> Canvas:
    c = Canvas()
    for i, (y, col) in enumerate(((7, "g"), (16, "A"), (25, "R"))):
        c.frect(3, y - 3, 3 + (8 + i * 8), y + 3, P[col])
    c.fdisc(27, 7, 2, P["g"])
    c.fdisc(27, 16, 2, P["A"])
    c.fdisc(27, 25, 2, P["R"])
    return c


@motif("blinds", "Blinds", "Status")
def blinds() -> Canvas:
    c = Canvas()
    c.frect(3, 2, 28, 30, P["K"])
    c.frect(5, 4, 26, 28, P["c"])                         # window behind
    for y in range(4, 18, 3):                             # slats, half lowered
        c.frect(5, y, 26, y + 1, P["W"])
    c.frect(5, 18, 26, 19, P["G"])
    c.frect(15, 19, 16, 24, P["G"])                       # pull cord
    return c


@motif("tv", "TV", "Status")
def tv() -> Canvas:
    c = Canvas()
    c.frect(2, 4, 29, 24, P["K"])
    c.frect(4, 6, 27, 22, P["B"])
    c.fpoly([(12, 10), (12, 18), (20, 14)], P["W"])       # play triangle
    c.frect(13, 25, 18, 28, P["K"])                       # stand
    c.frect(8, 28, 23, 30, P["K"])
    return c


@motif("speaker", "Speaker", "Status")
def speaker() -> Canvas:
    c = Canvas()
    c.fpoly([(4, 12), (12, 12), (20, 4), (20, 28), (12, 20), (4, 20)], P["W"])
    for radius in (6, 10, 14):
        c.arc(21, 16, radius, -55, 55, P["c"], thickness=2)
    return c


@motif("plant-water", "Water the plants", "Status")
def plant_water() -> Canvas:
    c = Canvas()
    c.fpoly([(9, 20), (23, 20), (21, 31), (11, 31)], P["C"])   # pot
    c.frect(8, 18, 24, 21, P["b"])
    c.frect(15, 8, 17, 19, P["n"])                        # stem
    c.fellipse(9, 12, 6, 3.5, P["g"])                     # leaves
    c.fellipse(23, 15, 6, 3.5, P["g"])
    c.fellipse(16, 6, 4, 3, P["g"])
    for i, x in enumerate((5, 27)):                       # drops
        c.fdisc(x, 4 + i * 4, 1.6, P["c"])
    return c


@motif("shower", "Shower", "Status")
def shower() -> Canvas:
    c = Canvas()
    c.frect(15, 1, 17, 6, P["G"])
    c.fpoly([(6, 12), (26, 12), (22, 6), (10, 6)], P["G"])     # head
    for i, x in enumerate(range(7, 27, 4)):
        for k in range(3):
            y = 15 + k * 6 + (i % 2) * 3
            if y < 31:
                c.line(x, y, x - 1, y + 3, P["c"])
    return c


@motif("sleep", "Sleeping", "Status")
def sleep() -> Canvas:
    c = Canvas()
    c.frect(1, 20, 30, 24, P["W"])                        # mattress
    c.frect(1, 24, 30, 28, P["B"])                        # blanket
    c.frect(1, 13, 6, 24, P["G"])                         # headboard
    c.frect(26, 18, 30, 24, P["G"])                       # footboard
    c.fdisc(11, 18, 3.5, P["A"])                          # head on the pillow
    c.frect(7, 18, 16, 20, P["W"])
    c.frect(1, 28, 4, 31, P["K"])                         # legs
    c.frect(27, 28, 30, 31, P["K"])
    for x, y, sz in ((16, 9, 4), (22, 4, 5), (26, 0, 4)):      # Z Z Z
        c.frect(x, y, x + sz, y + 1, P["W"])
        c.frect(x, y + sz, x + sz, y + sz + 1, P["W"])
        for d in (0, 1):
            c.line(x + sz + d, y, x + d, y + sz, P["W"])
    return c


@motif("trash-day", "Bin day", "Occasion")
def trash_day() -> Canvas:
    c = Canvas()
    c.frect(6, 8, 26, 11, P["K"])                         # lid
    c.frect(13, 5, 19, 8, P["K"])                         # handle
    c.fpoly([(7, 11), (25, 11), (23, 31), (9, 31)], P["g"])
    for x in (13, 19):
        c.frect(x, 14, x + 1, 28, P["n"])
    return c


@motif("recycling", "Recycling", "Occasion")
def recycling() -> Canvas:
    c = Canvas()
    corners = [(16, 3), (28, 25), (4, 25)]
    for i in range(3):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 3]
        sx, sy = ax + (bx - ax) * 0.24, ay + (by - ay) * 0.24      # leave gaps at the corners
        ex, ey = ax + (bx - ax) * 0.72, ay + (by - ay) * 0.72
        for d in (-1, 0, 1):
            c.line(round(sx) + d, round(sy), round(ex) + d, round(ey), P["g"])
            c.line(round(sx), round(sy) + d, round(ex), round(ey) + d, P["g"])
        ang = math.atan2(by - ay, bx - ax)                # arrowhead pointing on round
        tip = (ex + 6 * math.cos(ang), ey + 6 * math.sin(ang))
        left = (ex + 4 * math.cos(ang + 2.3), ey + 4 * math.sin(ang + 2.3))
        right = (ex + 4 * math.cos(ang - 2.3), ey + 4 * math.sin(ang - 2.3))
        c.fpoly([(round(tip[0]), round(tip[1])), (round(left[0]), round(left[1])),
                 (round(right[0]), round(right[1]))], P["g"])
    return c


@motif("shopping", "Shopping", "Occasion")
def shopping() -> Canvas:
    c = Canvas()
    c.arc(16, 10, 7, 180, 360, P["G"], thickness=3)       # handle
    c.frect(4, 10, 28, 30, P["A"])
    c.frect(4, 10, 28, 13, P["O"])
    for x in (11, 21):
        c.frect(x, 17, x + 1, 26, P["O"])
    return c


@motif("car", "Car", "Symbol")
def car() -> Canvas:
    c = Canvas()
    c.fpoly([(4, 18), (9, 9), (23, 9), (28, 18)], P["R"])
    c.frect(2, 18, 30, 24, P["R"])
    c.frect(10, 11, 15, 17, P["c"])
    c.frect(17, 11, 22, 17, P["c"])
    c.fdisc(8, 25, 4, P["K"])
    c.fdisc(24, 25, 4, P["K"])
    c.fdisc(8, 25, 1.8, P["G"])
    c.fdisc(24, 25, 1.8, P["G"])
    return c


@motif("bike", "Bike", "Symbol")
def bike() -> Canvas:
    c = Canvas()
    for cx in (8, 24):
        c.fdisc(cx, 22, 8, P["W"])
        c.fdisc(cx, 22, 6, (0, 0, 0))
    c.line(8, 22, 15, 12, P["R"]); c.line(9, 22, 16, 12, P["R"])
    c.line(15, 12, 24, 22, P["R"]); c.line(16, 12, 25, 22, P["R"])
    c.line(8, 22, 20, 22, P["R"]); c.line(8, 23, 20, 23, P["R"])
    c.line(15, 12, 20, 22, P["R"])
    c.frect(12, 9, 18, 11, P["K"])                        # saddle
    c.frect(22, 10, 28, 12, P["K"])                       # bars
    return c


@motif("plane", "Flight", "Symbol")
def plane() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 1), (12, 10), (12, 20), (20, 20), (20, 10)], P["W"])
    c.fpoly([(12, 13), (1, 22), (1, 25), (12, 21)], P["W"])    # wings
    c.fpoly([(20, 13), (31, 22), (31, 25), (20, 21)], P["W"])
    c.fpoly([(13, 25), (7, 30), (7, 31), (13, 29)], P["W"])    # tailplane
    c.fpoly([(19, 25), (25, 30), (25, 31), (19, 29)], P["W"])
    c.frect(13, 20, 19, 29, P["c"])
    return c


@motif("train", "Train", "Symbol")
def train() -> Canvas:
    c = Canvas()
    c.frect(5, 4, 27, 24, P["R"])
    c.frect(5, 4, 27, 7, P["r"])
    c.frect(8, 9, 24, 16, P["c"])                         # windscreen
    c.frect(15, 9, 17, 16, P["r"])
    c.fdisc(11, 20, 2, P["Y"])                            # lamps
    c.fdisc(21, 20, 2, P["Y"])
    c.frect(3, 24, 29, 27, P["K"])
    c.fdisc(10, 29, 2.5, P["G"])
    c.fdisc(22, 29, 2.5, P["G"])
    return c


@animation("clock", "Clock", "Occasion", frames=12, duration_ms=250)
def clock(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.fdisc(16, 16, 15, P["G"])
    c.fdisc(16, 16, 13, P["W"])
    for i in range(12):                                   # hour ticks
        a = math.radians(i * 30 - 90)
        c.px(round(16 + 11 * math.cos(a)), round(16 + 11 * math.sin(a)), P["K"])
    a_min = math.radians(frame * 30 - 90)
    a_hour = math.radians(frame * 2.5 - 90)
    c.line(16, 16, round(16 + 10 * math.cos(a_min)), round(16 + 10 * math.sin(a_min)), P["K"])
    c.line(16, 16, round(16 + 6 * math.cos(a_hour)), round(16 + 6 * math.sin(a_hour)), P["K"])
    c.line(17, 16, round(17 + 6 * math.cos(a_hour)), round(16 + 6 * math.sin(a_hour)), P["K"])
    c.fdisc(16, 16, 2, P["R"])
    return c


SERVICES_YAML = OUT.parent / "services.yaml"
OPTIONS_START = "          # gallery-options-start"
OPTIONS_END = "          # gallery-options-end"


def _write_service_options(index: list[dict]) -> None:
    """Keep the dropdown in services.yaml in step with what was just drawn.

    Home Assistant reads services.yaml statically, so the motif list has to be
    written into it rather than looked up at call time. Doing it here means the
    two can never drift apart.
    """
    if not SERVICES_YAML.is_file():
        print(f"note: {SERVICES_YAML} not found, dropdown not updated")
        return
    text = SERVICES_YAML.read_text()
    if OPTIONS_START not in text or OPTIONS_END not in text:
        print("note: option markers missing from services.yaml, dropdown not updated")
        return

    lines = [
        f'          - label: "{m["category"]} - {m["name"]}"\n            value: "{m["id"]}"'
        for m in sorted(index, key=lambda m: (m["category"], m["name"]))
    ]
    head, rest = text.split(OPTIONS_START, 1)
    _, tail = rest.split(OPTIONS_END, 1)
    SERVICES_YAML.write_text(
        head + OPTIONS_START + " -- written by tools/build_gallery.py\n"
        + "\n".join(lines) + "\n" + OPTIONS_END + tail
    )
    print(f"services.yaml dropdown updated with {len(lines)} options")


# --------------------------------------------------------------------------
# Road signs
# --------------------------------------------------------------------------


@motif("stop", "Stop", "Sign")
def stop() -> Canvas:
    c = Canvas()
    oct_pts = [(11, 2), (21, 2), (30, 11), (30, 21), (21, 30), (11, 30), (2, 21), (2, 11)]
    c.fpoly(oct_pts, P["W"])
    c.fpoly([(12, 4), (20, 4), (28, 12), (28, 20), (20, 28), (12, 28), (4, 20), (4, 12)], P["r"])
    c.text_centred(16, 14, "STOP", P["W"])
    return c


@motif("no-entry", "No entry", "Sign")
def no_entry() -> Canvas:
    c = Canvas()
    c.fdisc(16, 16, 15, P["W"])
    c.fdisc(16, 16, 13, P["r"])
    c.frect(6, 14, 26, 19, P["W"])
    return c


@motif("give-way", "Give way", "Sign")
def give_way() -> Canvas:
    c = Canvas()
    c.fpoly([(1, 4), (31, 4), (16, 30)], P["r"])
    c.fpoly([(7, 8), (25, 8), (16, 24)], P["W"])
    return c


@motif("speed-30", "Speed limit", "Sign")
def speed_30() -> Canvas:
    c = Canvas()
    c.fdisc(16, 16, 15, P["r"])
    c.fdisc(16, 16, 10, P["W"])
    c.text_centred(16, 14, "30", P["K"])
    return c


@motif("pedestrian-crossing", "Crossing", "Sign")
def pedestrian_crossing() -> Canvas:
    c = Canvas()
    c.frect(2, 2, 29, 29, P["W"])
    c.frect(4, 4, 27, 27, P["d"])
    for x in range(6, 26, 5):                             # zebra stripes
        c.frect(x, 22, x + 2, 26, P["W"])
    c.fdisc(15, 9, 2.4, P["W"])                           # walker
    c.fpoly([(13, 12), (18, 12), (17, 19), (14, 19)], P["W"])
    c.line(13, 13, 9, 17, P["W"]); c.line(18, 13, 21, 16, P["W"])
    c.line(14, 19, 11, 25, P["W"]); c.line(17, 19, 20, 25, P["W"])
    return c


@motif("no-parking", "No parking", "Sign")
def no_parking() -> Canvas:
    c = Canvas()
    c.fdisc(16, 16, 15, P["r"])
    c.fdisc(16, 16, 12, P["d"])
    for d in (-1, 0, 1, 2):
        c.line(6 + d, 24, 25 + d, 6, P["R"])
    return c


@motif("roadworks", "Roadworks", "Sign")
def roadworks() -> Canvas:
    c = Canvas()
    c.fpoly([(16, 1), (31, 29), (1, 29)], P["r"])
    c.fpoly([(16, 6), (27, 27), (5, 27)], P["W"])
    c.fdisc(16, 12, 2.4, P["K"])                          # worker
    c.frect(14, 15, 18, 22, P["K"])
    c.line(18, 16, 24, 22, P["K"]); c.line(19, 15, 25, 21, P["K"])
    c.fpoly([(22, 20), (27, 20), (25, 25), (21, 24)], P["K"])   # spoil heap
    return c


@animation("traffic-light", "Traffic light", "Sign", frames=8, duration_ms=450)
def traffic_light(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.frect(8, 1, 24, 27, P["K"])                         # housing
    c.rect(8, 1, 24, 27, P["G"])
    c.frect(14, 28, 18, 31, P["G"])                       # post
    # red, red-amber, green, amber -- the German sequence, held for four,
    # one, four and one steps of the cycle
    stage = (0, 0, 0, 1, 2, 2, 2, 3)[frame]
    lamps = (
        ("R" if stage in (0, 1) else None, 6),
        ("A" if stage in (1, 3) else None, 14),
        ("g" if stage == 2 else None, 22),
    )
    for colour, cy in lamps:
        c.fdisc(16, cy, 4, P["K"] if colour is None else P[colour])
        c.arc(16, cy, 4.5, 0, 360, P["G"], thickness=1)
    return c


# --------------------------------------------------------------------------
# Home office
# --------------------------------------------------------------------------


@motif("meeting", "In a meeting", "Office")
def meeting() -> Canvas:
    c = Canvas()
    c.fellipse(16, 22, 14, 4, P["C"])                     # table
    for x, col in ((6, "B"), (16, "g"), (26, "p")):       # three round the table
        c.fdisc(x, 9, 3.2, P[col])
        c.fpoly([(x - 5, 19), (x - 3, 13), (x + 3, 13), (x + 5, 19)], P[col])
    c.text_centred(16, 26, "MEET", P["W"])
    return c


@motif("do-not-disturb", "Do not disturb", "Office")
def do_not_disturb() -> Canvas:
    c = Canvas()
    c.fdisc(16, 16, 15, P["W"])
    c.fdisc(16, 16, 13, P["R"])
    c.frect(5, 14, 27, 18, P["W"])
    return c


@motif("free", "Free", "Office")
def free() -> Canvas:
    c = Canvas()
    c.fdisc(16, 16, 15, P["n"])
    c.fdisc(16, 16, 13, P["g"])
    c.text_centred(16, 13, "FREE", P["W"])
    return c


@motif("headset", "Headset", "Office")
def headset() -> Canvas:
    c = Canvas()
    c.arc(16, 15, 12, 180, 360, P["K"], thickness=4)      # band
    c.frect(2, 14, 9, 25, P["K"])                         # cups
    c.frect(23, 14, 30, 25, P["K"])
    c.frect(4, 16, 7, 23, P["G"])
    c.frect(25, 16, 28, 23, P["G"])
    c.arc(21, 24, 7, 300, 60, P["K"], thickness=3)        # boom, curving forward
    c.line(21, 31, 15, 31, P["K"])
    c.line(21, 30, 15, 30, P["K"])
    c.fdisc(13, 30, 2.6, P["R"])                          # mic capsule
    return c


@motif("video-call", "Video call", "Office")
def video_call() -> Canvas:
    c = Canvas()
    c.frect(2, 9, 21, 24, P["W"])                         # body
    c.fpoly([(22, 13), (30, 8), (30, 25), (22, 20)], P["W"])    # lens barrel
    c.fdisc(11, 16, 4.5, P["K"])
    c.fdisc(11, 16, 2.5, P["c"])
    c.fdisc(28, 6, 2, P["R"])                             # recording dot
    return c


@motif("mic-muted", "Microphone muted", "Office")
def mic_muted() -> Canvas:
    c = Canvas()
    c.frect(12, 3, 20, 17, P["G"])                        # capsule
    c.fdisc(16, 3, 4, P["G"])
    c.fdisc(16, 17, 4, P["G"])
    c.arc(16, 17, 9, 0, 180, P["G"], thickness=2)         # cradle
    c.frect(15, 25, 17, 30, P["G"])
    c.frect(10, 30, 22, 31, P["G"])
    for d in (0, 1):
        c.line(4 + d, 27, 27 + d, 3, P["R"])
    return c


@motif("laptop", "Desk", "Office")
def laptop() -> Canvas:
    c = Canvas()
    c.frect(5, 5, 26, 21, P["G"])                         # lid
    c.frect(7, 7, 24, 19, P["B"])
    c.frect(1, 22, 30, 26, P["W"])                        # base
    c.frect(1, 26, 30, 27, P["G"])
    c.frect(12, 23, 19, 25, P["G"])                       # trackpad
    return c


@animation("on-air", "On air", "Office", frames=4, duration_ms=450)
def on_air(frame: int, total: int) -> Canvas:
    c = Canvas()
    c.frect(1, 8, 30, 24, P["K"])
    c.rect(1, 8, 30, 24, P["G"])
    lit = frame % 2 == 0                                  # a sign that blinks
    colour = P["R"] if lit else P["r"]
    c.text_centred(16, 11, "ON", colour)
    c.text_centred(16, 18, "AIR", colour)
    if lit:
        c.frect(1, 6, 30, 6, P["r"])
        c.frect(1, 26, 30, 26, P["r"])
    return c


# --------------------------------------------------------------------------
# Christmas
# --------------------------------------------------------------------------


@motif("santa-hat", "Santa hat", "Occasion")
def santa_hat() -> Canvas:
    c = Canvas()
    c.fpoly([(4, 22), (10, 6), (22, 4), (27, 12)], P["R"])
    c.fdisc(27, 12, 4.5, P["W"])                          # bobble
    c.frect(2, 21, 27, 27, P["W"])                        # brim
    c.fdisc(3, 24, 3, P["W"])
    c.fdisc(27, 24, 3, P["W"])
    return c


@motif("santa", "Santa", "Occasion")
def santa() -> Canvas:
    c = Canvas()
    c.fellipse(16, 27, 12, 6, P["W"])                     # beard, drawn first so it
    c.fdisc(6, 22, 5, P["W"])                             # wraps the face rather than
    c.fdisc(26, 22, 5, P["W"])                            # sitting under it
    c.fellipse(16, 18, 8, 5, P["A"])                      # face
    c.fpoly([(4, 12), (12, 0), (26, 4)], P["R"])          # hat
    c.fdisc(27, 5, 3, P["W"])                             # bobble
    c.frect(3, 10, 27, 13, P["W"])                        # brim
    for x in (12, 13, 19, 20):                            # eyes, a pixel each
        c.px(x, 17, P["K"])
    c.fdisc(16, 20, 1.8, P["R"])                          # nose
    c.fellipse(16, 23, 6, 1.6, P["W"])                    # moustache
    return c


@motif("reindeer", "Reindeer", "Occasion")
def reindeer() -> Canvas:
    c = Canvas()
    for sx in (-1, 1):                                    # antlers
        base = 16 + sx * 6
        c.line(base, 12, base + sx * 4, 3, P["b"])
        c.line(base + sx, 12, base + sx * 5, 3, P["b"])
        c.line(base + sx * 2, 8, base + sx * 7, 6, P["b"])
        c.line(base + sx * 3, 5, base + sx * 8, 6, P["b"])
    c.fellipse(16, 20, 9, 10, P["C"])                     # head
    c.fellipse(5, 17, 3, 5, P["C"])                       # ears
    c.fellipse(27, 17, 3, 5, P["C"])
    c.fdisc(12, 18, 1.8, P["K"])
    c.fdisc(20, 18, 1.8, P["K"])
    c.fdisc(16, 26, 3.5, P["R"])                          # the nose
    return c


@motif("candy-cane", "Candy cane", "Occasion")
def candy_cane() -> Canvas:
    c = Canvas()
    c.arc(16, 11, 8, 180, 360, P["W"], thickness=5)       # hook
    c.frect(20, 11, 24, 31, P["W"])                       # shaft
    for y in range(32):                                   # stripes, clipped to the cane
        for x in range(32):
            if c.pixels[y][x] == P["W"] and ((x + y) // 3) % 2 == 0:
                c.px(x, y, P["R"])
    return c


@motif("bauble", "Bauble", "Occasion")
def bauble() -> Canvas:
    c = Canvas()
    c.arc(16, 4, 4, 200, 340, P["A"], thickness=2)        # hanger
    c.frect(13, 5, 19, 9, P["A"])                         # cap
    c.fdisc(16, 20, 11, P["R"])
    c.fdisc(16, 20, 9, P["r"])
    for i in range(-2, 3):                                # glitter band
        c.frect(6, 19 + i * 4, 26, 19 + i * 4, P["A"])
    for y in range(32):
        for x in range(32):
            if c.pixels[y][x] == P["A"] and (x - 16) ** 2 + (y - 20) ** 2 > 81:
                if y > 10:
                    c.px(x, y, (0, 0, 0))
    c.fdisc(12, 15, 2, P["W"])                            # highlight
    return c


@motif("stocking", "Stocking", "Occasion")
def stocking() -> Canvas:
    c = Canvas()
    c.frect(6, 2, 24, 8, P["W"])                          # cuff
    c.frect(9, 8, 21, 22, P["R"])                         # leg
    c.fpoly([(9, 22), (21, 22), (28, 26), (28, 30), (9, 30)], P["R"])   # foot
    c.fdisc(26, 28, 3, P["R"])
    c.frect(9, 24, 26, 26, P["r"])
    return c


# --------------------------------------------------------------------------
# Easter
# --------------------------------------------------------------------------


@motif("bunny", "Bunny", "Occasion")
def bunny() -> Canvas:
    c = Canvas()
    c.fellipse(11, 8, 3, 7, P["W"])                       # ears
    c.fellipse(21, 8, 3, 7, P["W"])
    c.fellipse(11, 8, 1.4, 4.5, P["p"])
    c.fellipse(21, 8, 1.4, 4.5, P["p"])
    c.fellipse(16, 21, 10, 9, P["W"])                     # head
    c.fdisc(12, 19, 1.8, P["K"])
    c.fdisc(20, 19, 1.8, P["K"])
    c.fpoly([(16, 23), (14, 25), (18, 25)], P["p"])       # nose
    c.line(16, 25, 16, 27, P["K"])
    for y, x0, x1 in ((24, 1, 8), (26, 1, 8), (24, 24, 31), (26, 24, 31)):
        c.frect(x0, y, x1, y, P["G"])                     # whiskers
    return c


@motif("chick", "Chick", "Occasion")
def chick() -> Canvas:
    c = Canvas()
    c.fellipse(16, 22, 10, 8, P["Y"])                     # body
    c.fdisc(16, 11, 7, P["Y"])                            # head
    c.fdisc(13, 10, 1.6, P["K"])
    c.fdisc(19, 10, 1.6, P["K"])
    c.fpoly([(16, 13), (12, 15), (16, 17), (20, 15)], P["O"])   # beak
    c.fpoly([(6, 20), (2, 24), (7, 26)], P["Y"])          # wing
    c.frect(12, 29, 14, 31, P["O"])                       # feet
    c.frect(18, 29, 20, 31, P["O"])
    c.px(16, 3, P["Y"]); c.px(16, 4, P["Y"]); c.px(15, 4, P["Y"])
    return c


@motif("easter-basket", "Easter basket", "Occasion")
def easter_basket() -> Canvas:
    c = Canvas()
    c.arc(16, 16, 11, 180, 360, P["C"], thickness=2)      # handle
    for x, col in ((9, "R"), (16, "c"), (23, "Y")):       # eggs peeking out
        c.fellipse(x, 18, 4, 5, P[col])
    c.fpoly([(3, 19), (29, 19), (25, 31), (7, 31)], P["C"])     # basket
    for x in range(5, 28, 4):
        c.line(x, 20, x - 2, 30, P["b"])
    c.frect(3, 19, 29, 21, P["b"])
    return c


@motif("lamb", "Lamb", "Occasion")
def lamb() -> Canvas:
    c = Canvas()
    for x in (6, 11, 16, 21):                             # legs, behind the fleece
        c.frect(x, 22, x + 2, 30, P["K"])
    for cx, cy in ((9, 14), (15, 11), (21, 14), (10, 19), (16, 20), (21, 19)):
        c.fdisc(cx, cy, 5, P["W"])                        # fleece
    c.fellipse(27, 12, 4.5, 5, P["K"])                    # head, clear of the body
    c.fellipse(31, 9, 2.5, 3.5, P["K"])                   # ear
    c.fdisc(28, 11, 1.3, P["W"])                          # eye
    c.px(29, 15, P["W"])
    return c


# --------------------------------------------------------------------------
# Halloween
# --------------------------------------------------------------------------


@motif("spider", "Spider", "Occasion")
def spider() -> Canvas:
    c = Canvas()
    c.line(16, 0, 16, 10, P["G"])                         # thread
    c.fellipse(16, 20, 8, 7, P["K"])                      # abdomen
    c.fdisc(16, 12, 4.5, P["K"])                          # head
    c.fdisc(14, 11, 1.4, P["R"])
    c.fdisc(18, 11, 1.4, P["R"])
    for sx in (-1, 1):                                    # eight legs
        for i, (y0, y1) in enumerate(((14, 10), (18, 14), (22, 20), (26, 26))):
            c.line(16 + sx * 6, y0, 16 + sx * 12, y1, P["K"])
            c.line(16 + sx * 12, y1, 16 + sx * 14, y1 + 5, P["K"])
    return c


@motif("witch-hat", "Witch hat", "Occasion")
def witch_hat() -> Canvas:
    c = Canvas()
    c.fpoly([(19, 1), (9, 22), (26, 22)], P["P"])         # cone, leaning
    c.fellipse(16, 24, 15, 4, P["p"])                     # brim
    c.fellipse(16, 23, 15, 3.5, P["P"])
    c.frect(9, 18, 26, 21, P["A"])                        # band
    c.fdisc(20, 19.5, 2.5, P["Y"])                        # buckle
    c.fdisc(20, 19.5, 1.2, P["A"])
    return c


@motif("gravestone", "Gravestone", "Occasion")
def gravestone() -> Canvas:
    c = Canvas()
    c.frect(1, 27, 30, 31, P["n"])                        # ground
    c.fdisc(16, 11, 9, P["G"])
    c.frect(7, 11, 25, 28, P["G"])
    c.text_centred(16, 12, "RIP", P["K"])
    c.frect(3, 26, 29, 28, P["g"])
    return c


@motif("candy", "Sweets", "Occasion")
def candy() -> Canvas:
    c = Canvas()
    c.fellipse(16, 16, 8, 8, P["p"])                      # wrapped sweet
    c.fellipse(16, 16, 8, 3, P["P"])
    c.fpoly([(8, 16), (1, 9), (2, 23)], P["p"])           # twisted ends
    c.fpoly([(24, 16), (31, 9), (30, 23)], P["p"])
    c.fdisc(13, 13, 2, P["W"])
    return c


@animation("bat", "Bat", "Occasion", frames=4, duration_ms=160)
def bat(frame: int, total: int) -> Canvas:
    c = Canvas()
    lift = (0, -3, 0, 3)[frame]                           # wings beating
    c.fellipse(16, 18, 4, 6, P["K"])                      # body
    c.fdisc(16, 12, 4, P["K"])                            # head
    c.fpoly([(13, 8), (12, 3), (16, 7)], P["K"])          # ears
    c.fpoly([(19, 8), (20, 3), (16, 7)], P["K"])
    for sx in (-1, 1):                                    # membranes
        c.fpoly(
            [
                (16 + sx * 3, 14),
                (16 + sx * 14, 12 + lift),
                (16 + sx * 11, 19 + lift),
                (16 + sx * 14, 22 + lift),
                (16 + sx * 5, 23),
            ],
            P["K"],
        )
    c.fdisc(14, 11, 1.2, P["R"])
    c.fdisc(18, 11, 1.2, P["R"])
    return c


def build(sheet_path: str | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    preview = []

    for m in MOTIFS:
        if m["frames"] is None:
            img = m["fn"]().to_image()
            filename = f"{m['id']}.png"
            img.save(OUT / filename)
            preview.append((m["id"], img))
        else:
            frames = [m["fn"](i, m["frames"]).to_image() for i in range(m["frames"])]
            filename = f"{m['id']}.gif"
            frames[0].save(
                OUT / filename,
                save_all=True,
                append_images=frames[1:],
                duration=m["duration_ms"],
                loop=0,
                optimize=False,
            )
            preview.append((m["id"], frames[0]))

        entry = {
            "id": m["id"],
            "name": m["name"],
            "category": m["category"],
            "file": filename,
            "animated": m["frames"] is not None,
        }
        index.append(entry)

    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    _write_service_options(index)
    print(f"{len(index)} motifs written to {OUT}")

    if sheet_path:
        contact_sheet(preview).save(sheet_path)
        print(f"contact sheet: {sheet_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", help="also write a scaled-up contact sheet here")
    build(ap.parse_args().sheet)
