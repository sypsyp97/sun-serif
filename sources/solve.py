"""Solve Amstelvar parametric axis values that hit measured skeleton targets.

Usage: solve.py <roman|italic> name:key=value,... ...
Fixed keys (passed straight to the axes): opsz wght wdth YTLC YTUC YTAS YTDE YTFI GRAD
Required key: space (advance of the space glyph, 1/1000 em).
Target keys (solved): xh (via YTLC), stem (via XOPQ, or wght for italic), thin (via YOPQ),
text_w (via XTRA, or wdth for italic).
Prints one JSON object per master with the solved location and its measures.
"""
import json
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

import measure as M
from build import source_path

KNOB = {
    "roman": {"xh": "YTLC", "stem": "XOPQ", "thin": "YOPQ", "text_w": "XTRA"},
    "italic": {"xh": "YTLC", "stem": "wght", "thin": "YOPQ", "text_w": "wdth"},
}
MEASURED = {"xh": "xh", "stem": "stem", "thin": "o_thin", "text_w": "text_w"}


def small_source(style):
    font = TTFont(source_path(style))
    opts = subset.Options()
    opts.layout_features = ["kern"]
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text=M.SAMPLE + "xHlpnoI")
    sub.subset(font)
    return font


def measure_at(src, loc):
    import copy

    loc = dict(loc)
    space = loc.pop("space")
    full = {a.axisTag: a.defaultValue for a in src["fvar"].axes}
    full.update(loc)
    inst = instancer.instantiateVariableFont(copy.deepcopy(src), full)
    upm = inst["head"].unitsPerEm
    inst["hmtx"]["space"] = (round(space * upm / 1000), 0)
    return M.measure_font("", inst, M.to_pil(inst))


def solve(src, style, fixed, targets, rounds=3):
    axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in src["fvar"].axes}
    loc = dict(fixed)
    for _ in range(rounds):
        for key in ("xh", "stem", "thin", "text_w"):
            if key not in targets:
                continue
            knob = KNOB[style][key]
            lo, _, hi = axes[knob]
            for _ in range(11):
                mid = (lo + hi) / 2
                got = measure_at(src, {**loc, knob: mid})[MEASURED[key]]
                if got < targets[key]:
                    lo = mid
                else:
                    hi = mid
            loc[knob] = round((lo + hi) / 2, 1)
    return loc, measure_at(src, loc)


def main():
    style = sys.argv[1]
    src = small_source(style)
    for arg in sys.argv[2:]:
        name, _, body = arg.partition(":")
        fixed, targets = {}, {}
        for kv in body.split(","):
            k, v = kv.split("=")
            (targets if k in MEASURED else fixed)[k] = float(v)
        loc, got = solve(src, style, fixed, targets)
        got.pop("font")
        print(json.dumps({"name": name, "loc": loc, "measured": got}, default=float), flush=True)


if __name__ == "__main__":
    main()
