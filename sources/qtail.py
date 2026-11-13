"""Own Q tail: a tapered blade that leaves the bowl at bottom centre, sweeps
right and ends in a crisp cut. Replaces the looped tail of the base design.

The tail is one closed quadratic contour of five points, so every master
gets the same point structure and the masters stay interpolable.
"""
import math

from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

# All ratios are relative to the O that the Q is built on.
START_X = 0.46  # where the tail leaves the bowl, fraction of bowl width
START_DEPTH = 0.55  # how deep inside the bottom stroke the root hides
TIP_OVERHANG = 0.03  # tip passes the right edge of the bowl by this much
TIP_DROP = 0.225  # tip depth below the baseline, fraction of cap height
CUT = 0.58  # height of the end cut, fraction of the thick stroke
BELLY = 1.0  # belly thickness control, fraction of the thick stroke
LEAD = (0.32, 0.78)  # control point of the upper edge, fraction of (run, drop)
ITALIC_REACH = 0.03  # extra overhang that keeps the slanted tail under the right half


def signed_area(points):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])) / 2


def contours(glyph, glyf):
    coords, ends, flags = glyph.getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        out.append((list(coords[start : end + 1]), list(flags[start : end + 1])))
        start = end + 1
    return out


def tail(outer, inner, cap, slant):
    xl, xr = min(p[0] for p in outer), max(p[0] for p in outer)
    yb, yi = min(p[1] for p in outer), min(p[1] for p in inner)
    width = xr - xl
    thin = yi - yb
    thick = min(p[0] for p in inner) - xl
    ax, ay = xl + START_X * width, yb + START_DEPTH * thin
    tx, ty = xr + (TIP_OVERHANG + (ITALIC_REACH if slant else 0.0)) * width, -TIP_DROP * cap
    run, drop = tx - ax, ay - ty
    cut = CUT * thick
    cux, cuy = ax + LEAD[0] * run, ay - LEAD[1] * drop
    chord = math.hypot(run, drop)
    nx, ny = -drop / chord, -run / chord  # normal that points down and left
    clx, cly = cux + BELLY * thick * nx, cuy + BELLY * thick * ny
    points = [
        (ax, ay),
        (cux, cuy),
        (tx, ty + cut / 2),
        (tx - 0.3 * cut, ty - cut / 2),
        (clx, cly),
    ]
    shear = math.tan(math.radians(slant))
    return [(round(x + (y - cap / 2) * shear), round(y)) for x, y in points], [1, 0, 1, 1, 0]


def redraw_q(font, slant=0.0):
    glyf = font["glyf"]
    glyph = glyf["Q"]
    parts = contours(glyph, glyf)
    if len(parts) != 3:
        raise ValueError(f"Q has {len(parts)} contours, expected bowl, counter and tail")
    (outer, outer_flags), (inner, inner_flags), (old_tail, _) = parts
    cap = glyf["H"].yMax
    points, flags = tail(outer, inner, cap, slant)
    if (signed_area(points) > 0) != (signed_area(old_tail) > 0):
        points = points[:1] + points[:0:-1]
        flags = flags[:1] + flags[:0:-1]
    glyph.coordinates = GlyphCoordinates(outer + inner + points)
    glyph.flags = bytearray(outer_flags + inner_flags + flags)
    glyph.endPtsOfContours = [len(outer) - 1, len(outer) + len(inner) - 1, len(outer) + len(inner) + len(points) - 1]
    glyph.recalcBounds(glyf)
    advance, _ = font["hmtx"]["Q"]
    font["hmtx"]["Q"] = (advance, glyph.xMin)
