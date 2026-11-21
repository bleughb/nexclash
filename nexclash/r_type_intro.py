"""R-Type intro: the animated R-9 specification screen in front of the game (games/r_type.md "Intro").

At build time: the owner's R-9 model (r_type_r9) is rendered into the ships' pictures; the title (red), logo (cyan)
and text (yellow) are read from the specification screen in the player's snapshot (it is the snapshot's own Spectrum
screen); asm/r_type_intro.asm is assembled in front of the game's banks. The tape's loading screen, beside the
snapshot (r_type.LOAD_SCREEN), is shown by the Next's loader while the file loads.

Flow (owner, 2026-11-22): loading screen at least 4 s, fade to the turning ships; a joystick move fades to the R-9
alone, turned by the stick (once per load); fire or a key fades back; then any key or stick move starts the game.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / 'asm' / 'r_type_intro.asm'
NAME = 'RTYPESPC.NEX'           # kept in the loader's data (the game is read through the handle the Next's loader leaves)
HOLD = 180                      # spare pages for the game's banks 0-7 while the file is open

STEPS = 175                     # pictures per turn: 2 video frames each at 50Hz = 7.0 s
LOGO_DOWN, WIN, RIGHT, PITCH = 5, (13, 73), 74, 7
FIRST_PAGE = 24                 # 8K page where the pictures start (bank 12, just after Layer 2)
VIEWS = {'side': ((0, 64, 0), 0), 'top': ((0, 128, 0), 1), 'front': ((64, 64, 0), 2)}
HOME = {'top': (91 - 45, 9 - 50), 'front': (5 - 82, 102 - 68), 'side': (91 - 45, 131 - 68)}
NEW = ['ENGINE/FUSION PULSE', 'THRUST/8.6E5kN', 'RANGE/4.1E6km', 'REACTOR/4 CORE', 'HULL/CERAMIC', 'ARMOUR/TITAN PLATE',
       'SHIELD/PLASMA 0.8m', 'WAVE CANNON/2.4MW', 'BEAM CHARGE/1.8sec', 'FORCE UNIT/1', 'RADAR/360 SCAN', 'TARGETING/LASER',
       'COOLANT/HELIUM 3']
ORIG_LINES = 11                 # the original screen's text lines; their letters make the font for NEW
HAND = {'V': ['#.#', '#.#', '#.#', '#.#', '.#.']}
GSTEP, GDY = 4, 0               # all-direction side ship: yaw -64..64, pitch 0..128 in steps of GSTEP
GN = 64 // GSTEP

PAL = [(0, 0, 0), (0, 0, 215), (215, 0, 0), (215, 0, 215), (0, 215, 0), (0, 215, 215), (215, 215, 0), (215, 215, 215)]
PALB = [(0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]


def screen_rgb(bank5):
    """The Spectrum screen in bank 5 as [row][column] RGB (no flash)."""
    out = []
    for y in range(192):
        row = []
        for x in range(256):
            a = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
            at = bank5[6144 + (y >> 3) * 32 + (x >> 3)]
            pal = PALB if at & 64 else PAL
            row.append(pal[at & 7] if bank5[a] & (0x80 >> (x & 7)) else pal[(at >> 3) & 7])
        out.append(row)
    return out


def spec_image(snap):
    """The original specification screen (the snapshot's screen) as a 256x192 PIL image."""
    from PIL import Image
    im = Image.new('RGB', (256, 192))
    im.putdata([c for row in screen_rgb(snap.banks[5]) for c in row])
    return im


def pack(pts):
    """A picture as rows of the bytes of a 1-bit Spectrum screen, skipping empty bytes."""
    rows = {}
    for x, y in pts:
        if 0 <= x < 256 and 0 <= y < 192:
            rows.setdefault(y, bytearray(32))[x // 8] |= 0x80 >> (x & 7)
    y0, y1 = min(rows), max(rows)
    out = bytearray([y0, y1 - y0 + 1])
    for y in range(y0, y1 + 1):
        b = rows.get(y, bytearray(32))
        pos = x = 0
        while x < 32:
            if not b[x]:
                x += 1
                continue
            e = x
            while e < 32 and b[e] and e - x < 15:
                e += 1
            skip = x - pos
            while skip > 15:
                out.append(0xF0)
                skip -= 15
            out += bytes([skip << 4 | (e - x)]) + b[x:e]
            pos = x = e
        out.append(0)
    return bytes(out)


def unpack(d):
    """The Z80 routine's steps, to check the packing."""
    scr = [bytearray(32) for _ in range(192)]
    y, n, i = d[0], d[1], 2
    for r in range(n):
        x = 0
        while d[i]:
            x += d[i] >> 4
            c = d[i] & 15
            i += 1
            for k in range(c):
                scr[y + r][x] |= d[i]
                x += 1
                i += 1
        i += 1
    assert i == len(d)
    return {(x * 8 + b, yy) for yy in range(192) for x in range(32) for b in range(8) if scr[yy][x] & (0x80 >> b)}


def data(snap, say=print):
    """{file name: bytes} for the assembly: spec_l2.bin, spec_frames.bin, spec_grid.bin, spec_data.inc."""
    from . import r_type_r9 as R
    scr = screen_rgb(snap.banks[5])
    col = lambda c: {(x, y) for y in range(192) for x in range(256) if scr[y][x] == c}
    red, yel, cyan = col((255, 0, 0)), col((255, 255, 0)), col((0, 255, 255))
    if not (red and yel and cyan):
        raise ValueError('the snapshot does not show the specification screen')
    logo = {(x, y + LOGO_DOWN) for x, y in cyan}
    # the text list: the original lines as they are, then NEW in their letters
    font = {}
    for k in range(ORIG_LINES):
        r0, segs, run = 13 + PITCH * k, [], None
        for x in range(0, RIGHT + 2):
            on = any((x, r0 + j) in yel for j in range(5))
            if on and run is None:
                run = x
            if not on and run is not None:
                segs.append((run, x - 1))
                run = None
        letters = ORIG_TEXT[k].replace(' ', '')
        for c, (a, b) in zip(letters, segs):
            font.setdefault(c, [''.join('#' if (x, r0 + j) in yel else '.' for x in range(a, b + 1)) for j in range(5)])
    font.update(HAND)

    def line(s):
        pts, x = [], 0
        for c in s:
            if c == ' ':
                x += 2
                continue
            g = font[c]
            pts += [(x + i, j) for j in range(5) for i in range(len(g[0])) if g[j][i] == '#']
            x += len(g[0]) + 1
        return [(RIGHT - (x - 1) + 1 + i, j) for i, j in pts]
    lines = [[(x, y - 13 - PITCH * k) for x, y in yel if 0 <= y - 13 - PITCH * k < 5] for k in range(ORIG_LINES)] + \
        [line(s) for s in NEW]
    nlist = PITCH * len(lines)
    textw = 10
    text = bytearray(nlist * textw)
    for k, pts in enumerate(lines):
        for x, j in pts:
            text[(PITCH * k + j) * textw + x // 8] |= 0x80 >> (x & 7)
    l2 = bytearray([0xE3]) * (256 * 192)
    for x, y in red:
        l2[y * 256 + x] = 0xE0
    for x, y in logo:
        l2[y * 256 + x] = 0x1F
    # the ships' pictures
    blob, index, order = bytearray(), [], ('side', 'top', 'front')
    for name in order:
        v, ax = VIEWS[name]
        for i in range(STEPS):
            a = list(v)
            a[ax] = (a[ax] + round(i * 256 / STEPS)) & 255
            pts = {(x + HOME[name][0], y + HOME[name][1]) for x, y in R.render(*a)}
            d = pack(pts)
            assert unpack(d) == {(x, y) for x, y in pts if 0 <= x < 256 and 0 <= y < 192}
            assert len(d) < 8192
            index.append((FIRST_PAGE + len(blob) // 8192, 0xC000 + len(blob) % 8192))
            blob += d
        say('Intro     : %s ship, %d pictures rendered' % (name, STEPS))
    pages = -(-len(blob) // 8192)
    blob += bytes(pages * 8192 - len(blob))
    # the side ship from every direction (the rest are these flipped: the ship is the same left and right)
    first_grid = FIRST_PAGE + pages
    gblob, gindex = bytearray(), []
    for p in range(2 * GN + 1):
        for ys in range(-GN, GN + 1):
            d = pack({(x, y + GDY) for x, y in R.render((ys * GSTEP) & 255, p * GSTEP, 0)})
            gindex.append((first_grid + len(gblob) // 8192, 0xC000 + len(gblob) % 8192))
            gblob += d
    gpages = -(-len(gblob) // 8192)
    gblob += bytes(gpages * 8192 - len(gblob))
    assert first_grid + gpages <= 224
    say('Intro     : all-direction ship, %d pictures rendered' % ((2 * GN + 1) ** 2))
    row = lambda y: 0x4000 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
    f = ['; made by make_spec_next.py - do not edit\n',
         'STEPS equ %d\nFIRST_PAGE equ %d\nFRAME_PAGES equ %d\nLIST_ROWS equ %d\nTEXTW equ %d\nWIN_TOP equ %d\nWIN_ROWS equ %d\n' % (
             STEPS, FIRST_PAGE, pages, nlist, textw, WIN[0], WIN[1] - WIN[0] + 1),
         '    macro DATA_TABLES\nrowtab:\n']
    for y in range(0, 192, 8):
        f.append('    dw ' + ','.join('$%04X' % row(y + k) for k in range(8)) + '\n')
    f.append('; one entry per picture: page, address.  %s, %d each\nframetab:\n' % (', '.join(order), STEPS))
    f += ['    db %d : dw $%04X\n' % pa for pa in index]
    f.append('textbits:\n')
    f += ['    db ' + ','.join('$%02X' % b for b in text[r * textw:(r + 1) * textw]) + '\n' for r in range(nlist)]
    f.append('    endm\n')
    f.append('GN equ %d\nGDY equ %d\nFIRST_GRID equ %d\nGRID_PAGES equ %d\n    macro GRID_TABLE\n; pitch 0..%d, and in each yaw -%d..%d\ngridtab:\n' % (
        GN, GDY, first_grid, gpages, 2 * GN, GN, GN))
    f += ['    db %d : dw $%04X\n' % pa for pa in gindex]
    f.append('    endm\n    macro REV_TABLE\nrevtab:\n')
    for i in range(0, 256, 16):
        f.append('    db ' + ','.join('$%02X' % int('{:08b}'.format(k)[::-1], 2) for k in range(i, i + 16)) + '\n')
    f.append('    endm\n')
    return {'spec_l2.bin': bytes(l2), 'spec_frames.bin': bytes(blob), 'spec_grid.bin': bytes(gblob),
            'spec_data.inc': ''.join(f).encode()}


# The original screen's text, for the letters (spaces are not drawn). Words of the game's screen, read from it.
ORIG_TEXT = ['CODE/R-9', 'CREW/1', 'WEIGHT/31.0t', 'LENGTH/16.2m', 'WIDTH/10.8m', 'HEIGHT/5.1m', 'MAX SPEED/200km/sec',
             'MAX POWER/3.2E14cr', 'SOFTWARE/B.C.PAPE', "GRAPHICS/'MAK'", 'HARDWARE/SPECTRUM']


def _sjasm():
    sys.path.insert(0, str(ROOT / 'tools' / 'sjasmplus'))
    import sjasm
    return sjasm.find()


def combine(game, files, load_screen=None):
    """The intro assembled in front of the game .nex (bytes). -> the whole .nex (bytes)."""
    h = game[:512]
    assert h[:4] == b'Next', 'not a NEX file'
    sp, pc = struct.unpack('<HH', h[12:16])
    entry = h[139]
    order = [5, 2, 0, 1, 3, 4, 6, 7] + list(range(8, 112))
    banks = [b for b in order if h[18 + b]]
    assert len(game) == 512 + 16384 * len(banks) and not h[10], 'unexpected NEX layout (loading screen or extra data)'
    bdata = {b: bytearray(game[512 + 16384 * i:512 + 16384 * (i + 1)]) for i, b in enumerate(banks)}
    # 1. no hold on the original specification screen: "pop bc / pop af / call spec_hold" in the hook page (bank 12)
    pat = bytes.fromhex('ED9205C1F1CD')
    at = bdata[12].find(pat)
    assert at >= 0 and bdata[12].find(pat, at + 1) < 0, 'spec_hold call not found once'
    bdata[12][at + 5:at + 8] = b'\x00\x00\x00'
    # 2. blank the original picture; 3. the loader's last step at 4000 (bank 5), invisible on black: put the game's
    #    bank 2 in place, page the entry bank at C000, start the game.
    assert all(2 * b + 1 < HOLD for b in banks), 'game uses pages the loader holds banks in'
    bdata[5][0:6912] = bytes(6912)
    h2 = HOLD + 4
    tramp = bytes([0xED, 0x91, 0x56, h2, 0xED, 0x91, 0x57, h2 + 1,
                   0x21, 0x00, 0xC0, 0x11, 0x00, 0x80, 0x01, 0x00, 0x40, 0xED, 0xB0,
                   0xED, 0x91, 0x56, entry * 2, 0xED, 0x91, 0x57, entry * 2 + 1,
                   0x31, sp & 255, sp >> 8, 0x01, 0, 0, 0xC3, pc & 255, pc >> 8])
    bdata[5][0:len(tramp)] = tramp
    payload = b''.join(bytes(bdata[b]) for b in banks)
    pages = []
    for b in banks:
        base = HOLD + 2 * b if b < 8 else 2 * b
        pages += [base, base + 1]
    place = [(HOLD + 2 * b + k, 2 * b + k) for b in range(8) if b != 2 and b in banks for k in (0, 1)]
    pics = files['spec_frames.bin'] + files['spec_grid.bin']
    sums = [sum(pics[i:i + 8192]) & 255 for i in range(0, len(pics), 8192)]      # the start-up memory check
    work = Path(tempfile.mkdtemp(prefix='r_type_intro_'))
    try:
        shutil.copy(ASM, work / 'specanim.asm')
        for n, d in files.items():
            (work / n).write_bytes(d)
        if load_screen is not None:
            (work / 'r_type_loading.scr').write_bytes(load_screen)

        def build(ofs):
            (work / 'game.inc').write_text(
                '; made by make_rtype_spec.py - do not edit\nRT_OFS equ %d\nRT_ENTRY_BANK equ %d\n'
                '    macro RT_FILE_NAME\n    db "%s",0\n    endm\n    macro RT_PAGES\n    db %s,$FF\n    endm\n    macro RT_PLACE\n'
                '    db %s,$FF\n    endm\n    macro RT_SUMS\n    db %s\n    endm\n' % (
                    ofs, entry, NAME, ','.join(map(str, pages)), ','.join('%d,%d' % p for p in place),
                    '\n    db '.join(','.join(map(str, sums[i:i + 32])) for i in range(0, len(sums), 32))), newline='\n')
            r = subprocess.run([_sjasm(), '--sym=rtype_spec.sym', '-DALLDIR', '-DGAME'] +
                               (['-DLOADSCR'] if load_screen is not None else []) + ['specanim.asm'],
                               cwd=work, capture_output=True, text=True)
            tail = [l for l in (r.stdout + r.stderr).splitlines() if 'include data' not in l]
            if not tail or 'Errors: 0' not in tail[-1]:
                raise RuntimeError('sjasmplus r_type_intro.asm:\n' + '\n'.join(tail[-12:]))
            return (work / 'rtype_spec_intro.nex').read_bytes()
        intro = build(0)
        intro = build(len(intro))                     # again, now that the game's place in the file is known
    finally:
        shutil.rmtree(work, ignore_errors=True)
    assert not intro[18 + 5] and not intro[18 + 7], 'the intro must not load banks 5 or 7 (system variables, disk system)'
    # The loading screen (SAVENEX SCREEN SCR) has no palette, but sjasmplus leaves the "no palette" flag clear and the
    # loader would read 512 bytes of palette that are not there. Set the flag.
    intro = bytearray(intro)
    if intro[10] & 0x7F:
        intro[10] |= 0x80
    return bytes(intro) + payload
