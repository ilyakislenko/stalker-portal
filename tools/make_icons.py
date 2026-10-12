"""Draws the mod's inventory icons into textures/ui/ui_icon_equipment_77.dds (icon_group = 77 in the ltx).

OGSR loads icon_group N from ui\\ui_icon_equipment_N; one grid cell is 50x50 px.
Cell (0,0): long fall boots.
  python tools/make_icons.py [--preview out.png]
"""
import argparse
import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "mod" / "gamedata" / "textures" / "ui" / "ui_icon_equipment_77.dds"
CELL = 50
SS = 4  # supersampling


def boots_icon():
    s = CELL * SS
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = s / 200.0

    def P(*pts):
        return [(x * k, y * k) for x, y in pts]

    outline = (25, 25, 28, 255)
    # calf brace
    d.rounded_rectangle(P((70, 18), (112, 104)), radius=10 * k, fill=(205, 207, 212, 255), outline=outline, width=int(4 * k))
    d.rectangle(P((70, 52), (112, 64)), fill=(60, 62, 68, 255))
    # shoe
    shoe = P((66, 98), (112, 98), (128, 122), (162, 132), (180, 146), (182, 164), (66, 164))
    d.polygon(shoe, fill=(72, 74, 80, 255), outline=outline, width=int(4 * k))
    d.rectangle(P((66, 156), (182, 166)), fill=(215, 216, 220, 255), outline=outline, width=int(3 * k))
    # the heel spring: down the back of the leg, round under the heel, ending under the arch
    blade = P((64, 24), (52, 60), (44, 100), (44, 140), (52, 170), (70, 186), (100, 190), (128, 186))
    d.line(blade, fill=outline, width=int(20 * k), joint="curve")
    d.line(blade, fill=(240, 241, 245, 255), width=int(12 * k), joint="curve")
    # orange Aperture accent
    d.ellipse(P((80, 30), (100, 50)), fill=(240, 140, 30, 255), outline=outline, width=int(3 * k))
    return im.resize((CELL, CELL), Image.LANCZOS)


def portalgun_icon():
    """3x2 cells (150x100): the Aperture handheld portal device, side view, muzzle to the right."""
    w, h = CELL * 3 * SS, CELL * 2 * SS
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = w / 300.0  # design space 300 x 200

    def P(*pts):
        return [(x * k, y * k) for x, y in pts]

    ol = (25, 25, 28, 255)
    lw = int(4 * k)
    # rear body: white rounded shell
    d.rounded_rectangle(P((22, 62), (170, 138)), radius=34 * k, fill=(236, 237, 240, 255), outline=ol, width=lw)
    # grip
    d.polygon(P((70, 130), (110, 130), (98, 182), (66, 182)), fill=(60, 62, 68, 255), outline=ol, width=lw)
    # black core section with glass
    d.rounded_rectangle(P((150, 72), (214, 128)), radius=12 * k, fill=(40, 42, 48, 255), outline=ol, width=lw)
    d.ellipse(P((160, 82), (204, 118)), fill=(150, 210, 255, 255), outline=ol, width=int(3 * k))
    # front claws
    for s in (1, -1):  # top prong, then its mirror around y = 100
        pts = [(206, 64), (268, 58), (280, 78), (214, 90)]
        d.polygon(P(*[(x, 100 + s * (y - 100)) for x, y in pts]), fill=(55, 57, 63, 255), outline=ol, width=lw)
    # blue glow at the muzzle
    d.ellipse(P((246, 84), (290, 116)), fill=(80, 170, 255, 255), outline=(20, 70, 160, 255), width=int(3 * k))
    # orange accent stripe
    d.rectangle(P((40, 92), (130, 104)), fill=(240, 140, 30, 255), outline=ol, width=int(2 * k))
    return im.resize((CELL * 3, CELL * 2), Image.LANCZOS)


def write_dds_bgra(img, path):
    img = img.convert("RGBA")
    w, h = img.size
    r, g, b, a = img.split()
    data = Image.merge("RGBA", (b, g, r, a)).tobytes()  # A8R8G8B8 = BGRA bytes
    pf = struct.pack("<II4sIIIII", 32, 0x41, b"\0\0\0\0", 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    hdr = struct.pack("<IIIIIII", 124, 0x100F, h, w, w * 4, 0, 0) + b"\0" * 44 + pf + struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"DDS " + hdr + data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    a = ap.parse_args()
    sheet = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    sheet.paste(boots_icon(), (0, 0))
    sheet.paste(portalgun_icon(), (CELL, 0))  # inv_grid_x = 1, inv_grid_y = 0, 3 x 2
    write_dds_bgra(sheet, OUT)
    print(f"wrote {OUT}")
    if a.preview:
        bg = Image.new("RGBA", sheet.size, (40, 44, 40, 255))
        bg.alpha_composite(sheet)
        bg.crop((0, 0, CELL * 4, CELL * 2)).resize((CELL * 12, CELL * 6), Image.NEAREST).save(a.preview)
        print(f"preview {a.preview}")


if __name__ == "__main__":
    main()
