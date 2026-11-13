"""Find glyph pairs that the design brought too close, and the kerning that opens them.

Lowering the capitals moves the arms of T, V, W and Y towards the dots and
accents of the lowercase, so pairs that are clear in the base design can touch.
For every pair this script measures the smallest distance between the two
outlines, at the tightest letter-spacing the family is set with, in a master and in the
base design at the same optical size and weight. A pair falls short when the
master is closer than the base design and closer than the minimum clearance.

Usage:
  clearance.py solve    write clearance.json, the extra kerning per master
  clearance.py refine   add what the built fonts still lack to clearance.json
  clearance.py check    measure the built fonts; exit status 1 on a shortfall
"""
import io
import json
import pathlib
import sys

import numpy as np
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

import build

HERE = pathlib.Path(__file__).parent
PX = 250  # pixels per em of the measuring bitmaps
PAD = 60
# Letters, digits and punctuation of Basic Latin and Latin-1.
CHARS = [chr(c) for c in range(0x21, 0x7F)] + [chr(c) for c in range(0xC0, 0x100) if c not in (0xD7, 0xF7)]
# Tightest letter-spacing in use and the smallest distance two outlines
# may have there, both in 1/1000 em, per optical size.
TRACKING = {"Text": 0, "Display": -35}
MINIMUM = {"Text": 30, "Display": 34}
TOLERANCE = 6  # measuring noise of the bitmaps, 1/1000 em


class Face:
    def __init__(self, font):
        font.flavor = None
        buf = io.BytesIO()
        font.save(buf)
        self.data = buf.getvalue()
        self.pil = ImageFont.truetype(io.BytesIO(self.data), PX)
        self.hb = hb.Font(hb.Face(self.data))
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.order = font.getGlyphOrder()
        self.ink = {}
        self.field = {}
        for ch in CHARS:
            if ord(ch) not in self.cmap:
                raise KeyError(f"font has no glyph for U+{ord(ch):04X}")
            width = int(self.pil.getlength(ch)) + 2 * PAD
            image = Image.new("L", (width + PX, 2 * PX + 2 * PAD), 0)
            ImageDraw.Draw(image).text((PAD, PAD + PX * 1.3), ch, font=self.pil, fill=255, anchor="ls")
            ink = np.asarray(image) > 127
            self.ink[ch] = np.argwhere(ink & ~ndimage.binary_erosion(ink))
            self.field[ch] = ndimage.distance_transform_edt(~ink)

    def advance(self, left, right):
        """Advance of the left glyph of the pair, kerning included, in 1/1000 em."""
        buf = hb.Buffer()
        buf.add_str(left + right)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": False})
        return buf.glyph_positions[0].x_advance * 1000 / self.upm

    def distance(self, left, right, advance):
        """Smallest distance between the outlines when the right glyph starts at advance."""
        field = self.field[left]
        rows = self.ink[right][:, 0]
        cols = self.ink[right][:, 1] + int(round(advance * PX / 1000))
        inside = cols < field.shape[1]
        if not inside.any():
            return 1000.0
        return float(field[rows[inside], cols[inside]].min()) * 1000 / PX

    def name(self, ch):
        return self.cmap[ord(ch)]


def shortfalls(face, base, size):
    """Yield (left, right, extra kerning in 1/1000 em) for every pair that falls short."""
    for left in CHARS:
        for right in CHARS:
            advance = face.advance(left, right) + TRACKING[size]
            intended = base.distance(left, right, base.advance(left, right) + TRACKING[size])
            target = min(intended, MINIMUM[size])
            if face.distance(left, right, advance) >= target - TOLERANCE:
                continue
            low, high = 0, 400
            while high - low > 2:
                mid = (low + high) / 2
                if face.distance(left, right, advance + mid) < target:
                    low = mid
                else:
                    high = mid
            yield left, right, high


def base_face(style, location):
    """The base design at the optical size and weight of a master."""
    font = TTFont(build.source_path(style))
    axes = {axis.axisTag: axis.defaultValue for axis in font["fvar"].axes}
    axes["opsz"] = location["opsz"]
    if "wght" in location:
        axes["wght"] = location["wght"]
    return Face(instancer.instantiateVariableFont(font, axes))


def solve():
    locations = json.loads((HERE / "masters.json").read_text())
    out = {}
    for style in ("roman", "italic"):
        out[style] = {}
        for master in build.MASTERS:
            face = Face(build.make_master(style, locations[style][master]))
            base = base_face(style, locations[style][master])
            size = "Text" if master.startswith("Text") else "Display"
            out[style][master] = {
                f"{face.name(left)} {face.name(right)}": round(extra * face.upm / 1000)
                for left, right, extra in shortfalls(face, base, size)
            }
            print(style, master, len(out[style][master]), "pairs", file=sys.stderr)
    (HERE / "clearance.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


def built_shortfalls():
    """Yield (style, master, face, shortfalls) for the corners of the built fonts."""
    locations = json.loads((HERE / "masters.json").read_text())
    for style in ("roman", "italic"):
        for master, (opsz, wght) in build.MASTERS.items():
            font = TTFont(build.variable_path(style))
            face = Face(instancer.instantiateVariableFont(font, {"opsz": opsz, "wght": wght}))
            base = base_face(style, locations[style][master])
            size = "Text" if master.startswith("Text") else "Display"
            yield style, master, face, list(shortfalls(face, base, size))


def refine():
    """Add what the built fonts still lack to clearance.json."""
    path = HERE / "clearance.json"
    out = json.loads(path.read_text())
    for style, master, face, found in built_shortfalls():
        for left, right, extra in found:
            pair = f"{face.name(left)} {face.name(right)}"
            before = out[style][master][pair] if pair in out[style][master] else 0
            out[style][master][pair] = before + round(extra * face.upm / 1000)
        print(style, master, len(found), "pairs refined", file=sys.stderr)
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


def check():
    failed = False
    for style, master, _, found in built_shortfalls():
        failed = failed or bool(found)
        print(style, master, len(found), "pairs fall short", [(left + right, round(extra)) for left, right, extra in found[:30]])
    return failed


if __name__ == "__main__":
    if sys.argv[1] == "solve":
        solve()
    elif sys.argv[1] == "refine":
        refine()
    elif sys.argv[1] == "check":
        sys.exit(1 if check() else 0)
    else:
        raise SystemExit(__doc__)
