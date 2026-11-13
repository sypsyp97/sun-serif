"""Render specimen.png from the built variable fonts."""
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).parent.parent
ROMAN = ROOT / "fonts" / "variable" / "SunSerif[opsz,wght].ttf"
ITALIC = ROOT / "fonts" / "variable" / "SunSerif-Italic[opsz,wght].ttf"
PAPER, INK, SOFT, RULE = (245, 244, 239), (26, 26, 24), (112, 108, 100), (214, 210, 200)
WIDTH, HEIGHT, MARGIN = 2400, 1560, 150


def face(path, size, opsz, wght):
    font = ImageFont.truetype(str(path), size)
    font.set_variation_by_axes([opsz, wght])
    return font


image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
draw = ImageDraw.Draw(image)
label = face(ROMAN, 30, 18, 400)

draw.text((MARGIN, 330), "Sun Serif", font=face(ROMAN, 300, 21, 400), fill=INK, anchor="ls")
draw.text((WIDTH - MARGIN, 330), "Qu", font=face(ITALIC, 300, 21, 400), fill=SOFT, anchor="rs")
draw.line((MARGIN, 420, WIDTH - MARGIN, 420), fill=RULE, width=3)

draw.text((MARGIN, 480), "Display  ·  opsz 21", font=label, fill=SOFT, anchor="ls")
draw.text((MARGIN, 600), "Quiet letters for long reading", font=face(ROMAN, 112, 21, 400), fill=INK, anchor="ls")
draw.text((MARGIN, 730), "and for the headings above it", font=face(ITALIC, 112, 21, 400), fill=INK, anchor="ls")

draw.text((MARGIN, 850), "Text  ·  opsz 18", font=label, fill=SOFT, anchor="ls")
lines = [
    (ROMAN, 400, "The text master has sturdy stems and an even colour, so that a paragraph"),
    (ROMAN, 400, "at 18 px stays calm on a screen. The display master is lighter and sharper."),
    (ITALIC, 400, "A true italic follows the roman in x-height, weight and width."),
    (ROMAN, 700, "Weights run from Regular 400 to Bold 700 on one axis."),
]
for index, (path, wght, text) in enumerate(lines):
    draw.text((MARGIN, 940 + index * 84), text, font=face(path, 58, 18, wght), fill=INK, anchor="ls")

draw.line((MARGIN, 1270, WIDTH - MARGIN, 1270), fill=RULE, width=3)
draw.text((MARGIN, 1360), "ABCDEFGHIJKLMNOPQRSTUVWXYZ  &  0123456789", font=face(ROMAN, 66, 18, 400), fill=INK, anchor="ls")
draw.text((MARGIN, 1450), "abcdefghijklmnopqrstuvwxyz  äöüß éñç  fi fl  ?!()“”", font=face(ROMAN, 66, 18, 400), fill=INK, anchor="ls")
image.save(ROOT / "specimen" / "specimen.png", optimize=True)
