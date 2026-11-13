"""Measure skeleton numbers of serif fonts from rasterised glyphs.

Usage: measure.py <label>=<font path>[@axis=value,axis=value] ...
Every number is in 1/1000 em, measured on a 1000 px/em bitmap.
"""
import io
import sys

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageDraw, ImageFont

EM = 1000
PAD = 400
SAMPLE = (
    "I am a Senior Engineer, where I develop learning systems for embodied "
    "intelligence and generalizable robotic policies for long-horizon tasks. "
    "My research focuses on computed tomography and inverse problems."
)


def to_pil(font):
    font.flavor = None
    buf = io.BytesIO()
    font.save(buf)
    buf.seek(0)
    return ImageFont.truetype(buf, EM)


def load(spec):
    path, _, axes = spec.partition("@")
    font = TTFont(path)
    if "fvar" in font:
        loc = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
        if axes:
            for kv in axes.split(","):
                k, v = kv.split("=")
                if k not in loc:
                    raise KeyError(f"{path}: no axis {k}")
                loc[k] = float(v)
        font = instancer.instantiateVariableFont(font, loc)
    elif axes:
        raise ValueError(f"{path} is static, axes given")
    return font, to_pil(font)


def bitmap(pil, ch):
    adv = int(round(pil.getlength(ch)))
    img = Image.new("L", (adv + 2 * PAD, EM + 2 * PAD), 0)
    ImageDraw.Draw(img).text((PAD, PAD + EM), ch, font=pil, fill=255, anchor="ls")
    return np.asarray(img) > 127, adv


def runs(line):
    edges = np.flatnonzero(np.diff(np.concatenate(([0], line.astype(np.int8), [0]))))
    return list(zip(edges[::2], edges[1::2]))


def top_bottom(bm):
    rows = np.flatnonzero(bm.any(axis=1))
    base = PAD + EM
    return base - rows[0], base - rows[-1] - 1


def hrow(bm, y):
    return runs(bm[PAD + EM - int(round(y))])


def vcol(bm, x):
    return runs(bm[:, PAD + int(round(x))])


def measure(label, spec):
    font, pil = load(spec)
    return measure_font(label, font, pil)


def measure_font(label, font, pil):
    out = {"font": label}
    bx, _ = bitmap(pil, "x")
    xh = top_bottom(bx)[0]
    bh, _ = bitmap(pil, "H")
    cap = top_bottom(bh)[0]
    bl, _ = bitmap(pil, "l")
    asc = top_bottom(bl)[0]
    bp, _ = bitmap(pil, "p")
    desc = -top_bottom(bp)[1]
    out.update(xh=xh, cap=cap, asc=asc, desc=desc)

    bn, n_adv = bitmap(pil, "n")
    r = hrow(bn, xh * 0.45)
    stem = r[0][1] - r[0][0]
    out["stem"] = stem
    out["n_counter"] = r[-1][0] - r[0][1]
    out["n_adv"] = n_adv

    bo, o_adv = bitmap(pil, "o")
    cols = np.flatnonzero(bo.any(axis=0))
    thick = max(a[1] - a[0] for y in np.linspace(xh * 0.3, xh * 0.7, 9) for a in hrow(bo, y)[:1])
    thin = min(
        (a[1] - a[0])
        for x in np.linspace(cols[0] + (cols[-1] - cols[0]) * 0.35, cols[0] + (cols[-1] - cols[0]) * 0.65, 13)
        for a in vcol(bo, x - PAD)
    )
    out["o_thick"] = thick
    out["o_thin"] = thin
    out["o_adv"] = o_adv

    bi, _ = bitmap(pil, "I")
    r = hrow(bi, cap * 0.5)
    out["cap_stem"] = r[0][1] - r[0][0]
    foot = hrow(bi, 4)
    out["I_serif_w"] = foot[-1][1] - foot[0][0]
    cols = np.flatnonzero(bh.any(axis=0))
    mid = (cols[0] + cols[-1]) / 2 - PAD
    bar = [a for a in vcol(bh, mid)]
    out["H_bar"] = bar[0][1] - bar[0][0]

    # serif height at half the overhang of the lowercase l foot
    foot = hrow(bl, 3)
    lstem = hrow(bl, xh * 0.5)[0]
    over = lstem[0] - foot[0][0]
    col = vcol(bl, foot[0][0] - PAD + max(over * 0.5, 1))
    out["l_serif_over"] = over
    out["l_serif_h_mid"] = col[-1][1] - col[-1][0]

    out["text_w"] = round(pil.getlength(SAMPLE) / len(SAMPLE), 1)
    hhea = font["hhea"]
    upm = font["head"].unitsPerEm
    out["linegap_box"] = round((hhea.ascent - hhea.descent + hhea.lineGap) / upm * EM)
    return out


def main():
    rows = [measure(*arg.split("=", 1)) for arg in sys.argv[1:]]
    keys = list(rows[0])
    derived = [
        ("xh/cap", lambda r: r["xh"] / r["cap"]),
        ("stem/xh", lambda r: r["stem"] / r["xh"]),
        ("contrast", lambda r: r["o_thick"] / r["o_thin"]),
        ("n_adv/xh", lambda r: r["n_adv"] / r["xh"]),
    ]
    print("\t".join(keys + [d[0] for d in derived]))
    for r in rows:
        print("\t".join(str(r[k]) for k in keys) + "\t" + "\t".join(f"{f(r):.3f}" for _, f in derived))


if __name__ == "__main__":
    main()
