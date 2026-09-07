"""A tiny drawing kit for hand-controlled pixel art.

Pillow's own primitives anti-alias, which turns a 32x32 icon to mush. Every
routine here sets whole pixels and nothing else, so what the code says is
exactly what lands on the panel.

Coordinates are inclusive on both ends: rect(0, 0, 31, 31) covers the whole
32x32 canvas.
"""
from __future__ import annotations

import math

from PIL import Image

Color = tuple[int, int, int]

# One palette for the whole gallery, so the motifs read as a set rather than as
# a pile of separate drawings. LED panels show saturated colour well and dark
# tones poorly, so the darks here are still fairly bright.
PALETTE: dict[str, Color] = {
    ".": (0, 0, 0),
    "W": (255, 255, 255),
    "G": (150, 158, 168),
    "K": (72, 80, 92),
    "R": (255, 56, 56),
    "r": (170, 26, 26),
    "O": (255, 136, 0),
    "A": (255, 190, 0),
    "Y": (255, 238, 70),
    "g": (64, 216, 88),
    "n": (26, 140, 56),
    "c": (80, 222, 240),
    "B": (52, 122, 255),
    "d": (26, 66, 170),
    "P": (176, 84, 255),
    "p": (255, 112, 180),
    "C": (154, 94, 52),
    "b": (100, 60, 32),
}


# A 3x5 uppercase face. Road signs and office signs need a word or two, and at
# 32 pixels nothing taller fits inside a shape and still leaves the shape
# readable. Legibility beats fidelity here: several glyphs are squarer than
# their real counterparts because a diagonal in three columns reads as noise.
FONT_3X5: dict[str, tuple[str, str, str, str, str]] = {
    "A": (".W.", "W.W", "WWW", "W.W", "W.W"),
    "B": ("WW.", "W.W", "WW.", "W.W", "WW."),
    "C": (".WW", "W..", "W..", "W..", ".WW"),
    "D": ("WW.", "W.W", "W.W", "W.W", "WW."),
    "E": ("WWW", "W..", "WW.", "W..", "WWW"),
    "F": ("WWW", "W..", "WW.", "W..", "W.."),
    "G": (".WW", "W..", "W.W", "W.W", ".WW"),
    "H": ("W.W", "W.W", "WWW", "W.W", "W.W"),
    "I": ("WWW", ".W.", ".W.", ".W.", "WWW"),
    "J": ("..W", "..W", "..W", "W.W", ".W."),
    "K": ("W.W", "W.W", "WW.", "W.W", "W.W"),
    "L": ("W..", "W..", "W..", "W..", "WWW"),
    "M": ("W.W", "WWW", "WWW", "W.W", "W.W"),
    "N": ("W.W", "WWW", "WWW", "WWW", "W.W"),
    "O": ("WWW", "W.W", "W.W", "W.W", "WWW"),
    "P": ("WW.", "W.W", "WW.", "W..", "W.."),
    "Q": (".W.", "W.W", "W.W", "WW.", ".WW"),
    "R": ("WW.", "W.W", "WW.", "W.W", "W.W"),
    "S": ("WWW", "W..", "WWW", "..W", "WWW"),
    "T": ("WWW", ".W.", ".W.", ".W.", ".W."),
    "U": ("W.W", "W.W", "W.W", "W.W", "WWW"),
    "V": ("W.W", "W.W", "W.W", "W.W", ".W."),
    "W": ("W.W", "W.W", "WWW", "WWW", "W.W"),
    "X": ("W.W", "W.W", ".W.", "W.W", "W.W"),
    "Y": ("W.W", "W.W", ".W.", ".W.", ".W."),
    "Z": ("WWW", "..W", ".W.", "W..", "WWW"),
    "0": ("WWW", "W.W", "W.W", "W.W", "WWW"),
    "1": (".W.", "WW.", ".W.", ".W.", "WWW"),
    "2": ("WWW", "..W", "WWW", "W..", "WWW"),
    "3": ("WWW", "..W", "WWW", "..W", "WWW"),
    "4": ("W.W", "W.W", "WWW", "..W", "..W"),
    "5": ("WWW", "W..", "WWW", "..W", "WWW"),
    "6": ("WWW", "W..", "WWW", "W.W", "WWW"),
    "7": ("WWW", "..W", "..W", "..W", "..W"),
    "8": ("WWW", "W.W", "WWW", "W.W", "WWW"),
    "9": ("WWW", "W.W", "WWW", "..W", "WWW"),
    "!": (".W.", ".W.", ".W.", "...", ".W."),
    "-": ("...", "...", "WWW", "...", "..."),
    " ": ("...", "...", "...", "...", "..."),
}


def text_width(s: str, spacing: int = 1) -> int:
    """Pixel width of `s` in the 3x5 face, for centring it by hand."""
    return max(0, len(s) * (3 + spacing) - spacing)


class Canvas:
    """A fixed-size RGB pixel buffer with non-anti-aliased primitives."""

    def __init__(self, width: int = 32, height: int = 32, bg: Color = (0, 0, 0)):
        self.width = width
        self.height = height
        self.pixels = [[bg for _ in range(width)] for _ in range(height)]

    def px(self, x: int, y: int, color: Color | None) -> None:
        """Set one pixel. Out-of-bounds writes and None are ignored."""
        if color is None:
            return
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color

    def frect(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        """Filled rectangle, corners inclusive."""
        for y in range(min(y0, y1), max(y0, y1) + 1):
            for x in range(min(x0, x1), max(x0, x1) + 1):
                self.px(x, y, color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        """One-pixel rectangle outline."""
        for x in range(min(x0, x1), max(x0, x1) + 1):
            self.px(x, y0, color)
            self.px(x, y1, color)
        for y in range(min(y0, y1), max(y0, y1) + 1):
            self.px(x0, y, color)
            self.px(x1, y, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        """Bresenham line."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.px(x0, y0, color)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def fdisc(self, cx: float, cy: float, r: float, color: Color) -> None:
        """Filled circle. Fractional centres allow even-diameter discs."""
        for y in range(self.height):
            for x in range(self.width):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.px(x, y, color)

    def fellipse(self, cx: float, cy: float, rx: float, ry: float, color: Color) -> None:
        """Filled ellipse."""
        for y in range(self.height):
            for x in range(self.width):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    self.px(x, y, color)

    def arc(
        self,
        cx: float,
        cy: float,
        r: float,
        deg0: float,
        deg1: float,
        color: Color,
        thickness: int = 1,
    ) -> None:
        """Arc segment. Degrees run clockwise from east, matching screen axes."""
        steps = max(8, int(abs(deg1 - deg0) * max(r, 1) / 12))
        for i in range(steps + 1):
            a = math.radians(deg0 + (deg1 - deg0) * i / steps)
            for t in range(thickness):
                rr = r - t
                self.px(round(cx + rr * math.cos(a)), round(cy + rr * math.sin(a)), color)

    def fpoly(self, points: list[tuple[int, int]], color: Color) -> None:
        """Filled polygon by scanline, no anti-aliasing."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        for y in range(min(ys), max(ys) + 1):
            crossings: list[float] = []
            for i in range(len(points)):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % len(points)]
                if y0 == y1:
                    continue
                if min(y0, y1) <= y < max(y0, y1):
                    crossings.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            crossings.sort()
            for i in range(0, len(crossings) - 1, 2):
                for x in range(round(crossings[i]), round(crossings[i + 1]) + 1):
                    self.px(x, y, color)

    def amap(self, rows: list[str], ox: int = 0, oy: int = 0) -> None:
        """Stamp an ASCII map. '.' leaves the pixel untouched.

        Every row must be the same length -- a ragged map is a typo, not a
        shape, so it raises rather than drawing something subtly wrong.
        """
        widths = {len(r) for r in rows}
        if len(widths) != 1:
            raise ValueError(f"ragged ASCII map, row widths: {sorted(widths)}")
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch == ".":
                    continue
                if ch not in PALETTE:
                    raise ValueError(f"unknown palette char {ch!r}")
                self.px(ox + dx, oy + dy, PALETTE[ch])

    def text(self, x: int, y: int, s: str, color: Color, spacing: int = 1) -> None:
        """Draw `s` in the 3x5 face with its top-left corner at (x, y)."""
        for i, ch in enumerate(s.upper()):
            glyph = FONT_3X5.get(ch)
            if glyph is None:
                raise ValueError(f"no 3x5 glyph for {ch!r}")
            ox = x + i * (3 + spacing)
            for dy, row in enumerate(glyph):
                for dx, cell in enumerate(row):
                    if cell != ".":
                        self.px(ox + dx, y + dy, color)

    def text_centred(self, cx: int, y: int, s: str, color: Color, spacing: int = 1) -> None:
        """Draw `s` centred horizontally on `cx`."""
        self.text(cx - text_width(s, spacing) // 2, y, s, color, spacing)

    def to_image(self) -> Image.Image:
        img = Image.new("RGB", (self.width, self.height))
        img.putdata([px for row in self.pixels for px in row])
        return img


def contact_sheet(images: list[tuple[str, Image.Image]], scale: int = 6, cols: int = 4) -> Image.Image:
    """Lay motifs out on one grid, scaled up, for reviewing the set at a glance."""
    from PIL import ImageDraw

    cell_w, cell_h = 32 * scale, 32 * scale + 14
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w + 8, rows * cell_h + 8), (26, 26, 30))
    draw = ImageDraw.Draw(sheet)
    for i, (name, img) in enumerate(images):
        x = 4 + (i % cols) * cell_w
        y = 4 + (i // cols) * cell_h
        sheet.paste(img.resize((32 * scale, 32 * scale), Image.NEAREST), (x, y))
        draw.text((x + 2, y + 32 * scale + 2), name, fill=(190, 195, 205))
    return sheet
