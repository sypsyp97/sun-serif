"""Build the family.

The family is cut from the parametric design space of Amstelvar (SIL OFL 1.1).
Each master in masters.json is a location in that space, solved by solve.py so
that x-height, stem, hairline and set width hit the targets of the design.
This script instantiates the eight masters, applies the changes that the
design space cannot express (word space, the Q tail, line metrics, kerning of
pairs that the new proportions bring too close), and merges
them into one roman and one italic variable font with the axes opsz and wght.

Usage: uv run --with 'fonttools[woff]' python sources/build.py
"""
import copy
import hashlib
import json
import pathlib
import urllib.parse
import urllib.request

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, InstanceDescriptor, SourceDescriptor
from fontTools.misc.timeTools import timestampFromString
from fontTools.otlLib.builder import buildLookup, buildPairPosGlyphs, buildStatTable, buildValue
from fontTools.ttLib import TTFont, newTable
from fontTools.varLib import build as build_variable
from fontTools.varLib import instancer

import qtail

HERE = pathlib.Path(__file__).parent
CACHE = HERE / ".cache"
OUT = HERE.parent / "fonts"

# Family name, version, copyright notice and description.
IDENTITY = json.loads((HERE / "family.json").read_text())
FAMILY = IDENTITY["family"]
VERSION = IDENTITY["version"]
TIMESTAMP = timestampFromString("Fri Nov 13 00:00:00 2026")

SOURCE_REPO = "https://raw.githubusercontent.com/googlefonts/amstelvar/f44f670affec72a37c69a1bf103bddc044020f49/"
SOURCES = {
    "roman": (
        "fonts/Amstelvar-Roman[GRAD,XOPQ,XTRA,YOPQ,YTAS,YTDE,YTFI,YTLC,YTUC,wdth,wght,opsz].ttf",
        "5b0708fbbb069e127ae62d017bd03beb9dd9dd61bc07b748f6508a7fcd901662",
    ),
    "italic": (
        "fonts/Amstelvar-Italic[GRAD,YOPQ,YTAS,YTDE,YTFI,YTLC,YTUC,wdth,wght,opsz].ttf",
        "e410c84e2b3d210b7524a08fe16a458247321691086a8d4ef3fb024fd44ab192",
    ),
    "license": ("OFL.txt", "06c79c896894160a5810d869a822fa7d02a0e2ccffd97920b8cf3b880380f6e5"),
}

# Design location of each master on the axes of the family.
# The display master sits at opsz 21, the smallest heading size the family is made for.
OPSZ_TEXT, OPSZ_DISPLAY = 18, 21
WGHT_REGULAR, WGHT_BOLD = 400, 700
MASTERS = {
    "TextRegular": (OPSZ_TEXT, WGHT_REGULAR),
    "TextBold": (OPSZ_TEXT, WGHT_BOLD),
    "DisplayRegular": (OPSZ_DISPLAY, WGHT_REGULAR),
    "DisplayBold": (OPSZ_DISPLAY, WGHT_BOLD),
}
NAMED_WEIGHTS = {"Regular": 400, "Medium": 500, "Semibold": 600, "Bold": 700}
ITALIC_ANGLE = 11.0

# Line metrics in 1/1000 em.
ASCENT, DESCENT = 1036, -335

LICENSE = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at: https://openfontlicense.org"
)


def source_path(key):
    """Return the local path of a pinned upstream file. Download it on first use."""
    name, digest = SOURCES[key]
    path = CACHE / pathlib.PurePosixPath(name).name
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        with urllib.request.urlopen(SOURCE_REPO + urllib.parse.quote(name)) as response:
            path.write_bytes(response.read())
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != digest:
        raise ValueError(f"{path} has sha256 {found}, expected {digest}")
    return path


def upstream_notice():
    return source_path("license").read_text().splitlines()[0]


def make_master(style, location):
    """Instantiate one master and apply the changes the design space cannot express."""
    location = dict(location)
    font = TTFont(source_path(style))
    upm = font["head"].unitsPerEm
    space = round(location.pop("space") * upm / 1000)
    axes = {axis.axisTag: axis.defaultValue for axis in font["fvar"].axes}
    for tag, value in location.items():
        if tag not in axes:
            raise KeyError(f"{style} source has no axis {tag}")
        axes[tag] = value
    font = instancer.instantiateVariableFont(font, axes, overlap=instancer.OverlapMode.KEEP_AND_DONT_SET_FLAGS)
    for glyph in ("space", "nbspace"):
        font["hmtx"][glyph] = (space, 0)
    qtail.redraw_q(font, ITALIC_ANGLE if style == "italic" else 0.0)
    ascent, descent = round(ASCENT * upm / 1000), round(DESCENT * upm / 1000)
    hhea, os2 = font["hhea"], font["OS/2"]
    hhea.ascent, hhea.descent, hhea.lineGap = ascent, descent, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ascent, descent, 0
    os2.usWinAscent, os2.usWinDescent = ascent, -descent
    return font


def open_tight_pairs(font, pairs, extra):
    """Append a kerning lookup that adds extra[pair] font units to each pair.

    Every master gets the same pairs, with 0 where it needs nothing, so the
    lookups of the masters have one structure and can be merged.
    """
    values = {tuple(pair.split()): (buildValue({"XAdvance": extra[pair] if pair in extra else 0}), None) for pair in pairs}
    table = font["GPOS"].table
    table.LookupList.Lookup.append(buildLookup(buildPairPosGlyphs(values, font.getReverseGlyphMap())))
    table.LookupList.LookupCount = len(table.LookupList.Lookup)
    kern = [record.Feature for record in table.FeatureList.FeatureRecord if record.FeatureTag == "kern"]
    if not kern:
        raise ValueError("font has no kern feature")
    for feature in kern:
        feature.LookupListIndex.append(table.LookupList.LookupCount - 1)
        feature.LookupCount = len(feature.LookupListIndex)


def build_style(style, locations):
    masters_dir = CACHE / "masters"
    masters_dir.mkdir(parents=True, exist_ok=True)
    fonts = {name: make_master(style, locations[name]) for name in MASTERS}
    # clearance.py writes the extra kerning that each master needs.
    clearance = json.loads((HERE / "clearance.json").read_text())[style]
    pairs = sorted({pair for name in MASTERS for pair in clearance[name]})
    for name, font in fonts.items():
        open_tight_pairs(font, pairs, clearance[name])
        # The bold masters carry a weight-conditional substitution of currency
        # signs. Every master must have the same features, so all use the
        # feature table of the regular text master.
        if name != "TextRegular":
            font["GSUB"] = copy.deepcopy(fonts["TextRegular"]["GSUB"])
        font.save(masters_dir / f"{style}-{name}.ttf")

    doc = DesignSpaceDocument()
    for tag, name, low, high in (
        ("opsz", "Optical Size", OPSZ_TEXT, OPSZ_DISPLAY),
        ("wght", "Weight", WGHT_REGULAR, WGHT_BOLD),
    ):
        axis = AxisDescriptor()
        axis.tag, axis.name, axis.minimum, axis.default, axis.maximum = tag, name, low, low, high
        doc.addAxis(axis)
    for name, (opsz, wght) in MASTERS.items():
        source = SourceDescriptor()
        source.path = str(masters_dir / f"{style}-{name}.ttf")
        source.name = name
        source.location = {"Optical Size": opsz, "Weight": wght}
        doc.addSource(source)
    for weight_name, wght in NAMED_WEIGHTS.items():
        instance = InstanceDescriptor()
        instance.familyName = FAMILY
        if style == "roman":
            instance.styleName = weight_name
        elif wght == WGHT_REGULAR:
            instance.styleName = "Italic"
        else:
            instance.styleName = f"{weight_name} Italic"
        instance.location = {"Optical Size": OPSZ_TEXT, "Weight": wght}
        doc.addInstance(instance)

    font, _, _ = build_variable(doc)
    finish(font, style)
    return font


def finish(font, style):
    """Set names, style bits and the style attributes table of a merged font."""
    italic = style == "italic"
    subfamily = "Italic" if italic else "Regular"
    postscript = FAMILY.replace(" ", "") + "-" + subfamily
    name = font["name"]
    name.names = [record for record in name.names if record.nameID >= 256]
    for name_id, text in {
        0: f"{upstream_notice()}. {IDENTITY['copyright']}.",
        1: FAMILY,
        2: subfamily,
        3: f"{VERSION};{postscript}",
        4: FAMILY + (" Italic" if italic else ""),
        5: f"Version {VERSION}",
        6: postscript,
        10: IDENTITY["description"],
        13: LICENSE,
        14: "https://openfontlicense.org",
        25: FAMILY.replace(" ", "") + ("Italic" if italic else ""),
    }.items():
        name.setName(text, name_id, 3, 1, 0x409)

    weights = [{"value": value, "name": label} for label, value in NAMED_WEIGHTS.items()]
    weights[0].update(flags=0x2, linkedValue=WGHT_BOLD)
    buildStatTable(
        font,
        [
            {
                "tag": "opsz",
                "name": "Optical Size",
                "ordering": 0,
                "values": [
                    {"value": OPSZ_TEXT, "name": "Text", "flags": 0x2},
                    {"value": OPSZ_DISPLAY, "name": "Display"},
                ],
            },
            {"tag": "wght", "name": "Weight", "ordering": 1, "values": weights},
            {
                "tag": "ital",
                "name": "Italic",
                "ordering": 2,
                "values": [{"value": 1, "name": "Italic"}]
                if italic
                else [{"value": 0, "name": "Roman", "flags": 0x2, "linkedValue": 1}],
            },
        ],
        elidedFallbackName=2,
    )

    os2, head = font["OS/2"], font["head"]
    os2.achVendID = "NONE"
    os2.usWeightClass = WGHT_REGULAR
    # Bit 7 makes every platform use the typo line metrics.
    os2.fsSelection = (0x01 if italic else 0x40) | 0x80
    head.macStyle = 0x02 if italic else 0
    head.fontRevision = float(VERSION)
    head.created = head.modified = TIMESTAMP
    font["post"].italicAngle = -ITALIC_ANGLE if italic else 0.0
    gasp = newTable("gasp")
    gasp.version = 1
    gasp.gaspRange = {0xFFFF: 0x000F}
    font["gasp"] = gasp
    font.recalcTimestamp = False


def variable_path(style):
    name = FAMILY.replace(" ", "") + ("-Italic" if style == "italic" else "") + "[opsz,wght]"
    return OUT / "variable" / f"{name}.ttf"


def write_fonts(font, style):
    """Write the variable font as TrueType and as woff2."""
    font.save(variable_path(style))
    font.flavor = "woff2"
    font.save(OUT / "webfonts" / (variable_path(style).stem + ".woff2"))


def main():
    locations = json.loads((HERE / "masters.json").read_text())
    for style in ("roman", "italic"):
        write_fonts(build_style(style, locations[style]), style)
    license_text = source_path("license").read_text()
    notice = upstream_notice()
    (HERE.parent / "OFL.txt").write_text(license_text.replace(notice, f"{notice}\n{IDENTITY['copyright']}", 1))


if __name__ == "__main__":
    main()
