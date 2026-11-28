"""Build the Green Beret 4-bit arcade painting kit: python -m nexclash.green_beret_art SNAPSHOT DIRECTORY."""
import argparse
from pathlib import Path

# Each row is a distinct 16-entry hardware bank. RGB333 digits are written R,G,B.
# 0 transparent, 1 light fill, 2 outline, 15 grey edge. Rows follow the draw tables.
GROUPS = [
    ('Player', '000 776 002 230 120 341 452 563 210 431 642 753 764 554 222 444'),
    ('Weapons and mines', '000 776 002 222 332 553 664 430 650 760 710 600 034 047 455 444'),
    ('Infantry', '000 776 002 210 320 430 541 652 120 230 642 753 764 554 222 444'),
    ('Riflemen', '000 776 002 013 025 036 047 600 710 430 642 753 764 554 222 444'),
    ('Mortar crew', '000 776 002 210 320 430 541 652 222 343 642 753 764 554 665 444'),
    ('Jump-kickers', '000 776 002 120 230 341 452 563 665 554 642 753 764 210 222 444'),
    ('Officers', '000 776 002 013 025 046 057 600 710 430 642 753 764 554 222 444'),
    ('Blasts', '000 776 002 222 333 555 666 667 777 620 740 760 770 700 410 444'),
    ('Dogs', '000 776 002 210 320 430 540 650 661 662 653 754 764 554 222 444'),
]
RGB333 = [[int(v, 8) for v in row.split()] for _, row in GROUPS]
RGB = [[tuple(((v >> s) & 7) * 255 // 7 for s in (6, 3, 0)) for v in row] for row in RGB333]


def group(gfx):
    if gfx < 0xC7F6:
        return 0
    if gfx < 0xD602:
        return 1
    if gfx < 0xE2C2:
        return 2
    if gfx < 0xE8C2 or 0xF1C2 <= gfx < 0xF4C2:
        return 3
    if gfx < 0xEEC2:
        return 4
    if gfx < 0xF1C2:
        return 5
    if gfx < 0xF7C2:
        return 6
    return 7 if gfx < 0xF942 else 8


def palette_data():
    words = [v for row in RGB333 for v in row]
    return bytes([len(words)] + [b for v in words for b in (v >> 1, v & 1)])


def build(z80, directory):
    from . import green_beret as gb, z80tonex as zt
    from .nextboot import check
    out = Path(directory)
    out.mkdir(exist_ok=True, parents=True)
    path = str(out / 'green_beret_arcade.nex')
    patch = gb.GreenBeretPatch(banked=True)
    conv = zt.convert(str(z80), path, None, True, quiet=True, patch=patch, keep_printer_buffer=True)
    errors = check(path, str(z80), patch, (conv[1], conv[1] + len(conv[2])))
    if errors:
        raise ValueError(f'Arcade build failed the boot check: {errors}')
    gb.sheets(str(z80), str(out), prefix='green_beret_arcade', colours=patch.colours, banked=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot')
    parser.add_argument('directory')
    args = parser.parse_args()
    build(args.snapshot, args.directory)
