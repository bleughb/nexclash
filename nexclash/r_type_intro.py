"""R-Type intro: the animated R-9 specification screen in front of the game (games/r_type.md "Intro").

At build time: the owner's R-9 model (r_type_r9) is rendered into the ships' pictures; the title (red), logo (cyan)
and text (yellow) are read from the specification screen in the player's snapshot (it is the snapshot's own Spectrum
screen); asm/r_type_intro.asm is assembled in front of the game's banks. The tape's loading screen, beside the
snapshot (r_type.LOAD_SCREEN), is shown by the Next's loader while the file loads.

Flow (owner, 2026-11-22): loading screen at least 4 s, fade to the turning ships; a joystick move fades to the R-9
alone, turned by the stick (once per load); fire or a key fades back; then any key or stick move starts the game.
"""
import hashlib
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


def data(snap, say=print, gstep=GSTEP, pages=None):
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
    pages = list(pages) if pages is not None else list(range(FIRST_PAGE, 224))
    gn = 64 // gstep
    pics, order = [], ('side', 'top', 'front')
    for name in order:
        v, ax = VIEWS[name]
        for i in range(STEPS):
            a = list(v)
            a[ax] = (a[ax] + round(i * 256 / STEPS)) & 255
            pts = {(x + HOME[name][0], y + HOME[name][1]) for x, y in R.render(*a)}
            d = pack(pts)
            assert unpack(d) == {(x, y) for x, y in pts if 0 <= x < 256 and 0 <= y < 192}
            assert len(d) < 8192
            pics.append(d)
        say('Intro     : %s ship, %d pictures rendered' % (name, STEPS))
    index, fpages, at = place(pics, pages, 0)
    # the side ship from every direction (the rest are these flipped: the ship is the same left and right)
    gpics = [pack({(x, y + GDY) for x, y in R.render((ys * gstep) & 255, p * gstep, 0)})
             for p in range(2 * gn + 1) for ys in range(-gn, gn + 1)]
    gindex, gpages, _ = place(gpics, pages, at)
    say('Intro     : all-direction ship, %d pictures rendered (every %d of 256)' % (len(gpics), gstep))
    first_grid = gpages[0][0]
    blob = b''.join(d for _, d in fpages)
    gblob = b''.join(d for _, d in gpages)
    row = lambda y: 0x4000 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
    f = ['; made by make_spec_next.py - do not edit\n',
         'STEPS equ %d\nFIRST_PAGE equ %d\nFRAME_PAGES equ %d\nLIST_ROWS equ %d\nTEXTW equ %d\nWIN_TOP equ %d\nWIN_ROWS equ %d\n' % (
             STEPS, fpages[0][0], len(fpages), nlist, textw, WIN[0], WIN[1] - WIN[0] + 1),
         '    macro DATA_TABLES\nrowtab:\n']
    for y in range(0, 192, 8):
        f.append('    dw ' + ','.join('$%04X' % row(y + k) for k in range(8)) + '\n')
    f.append('; one entry per picture: page, address.  %s, %d each\nframetab:\n' % (', '.join(order), STEPS))
    f += ['    db %d : dw $%04X\n' % pa for pa in index]
    f.append('textbits:\n')
    f += ['    db ' + ','.join('$%02X' % b for b in text[r * textw:(r + 1) * textw]) + '\n' for r in range(nlist)]
    f.append('    endm\n')
    f.append('GN equ %d\nGDY equ %d\nFIRST_GRID equ %d\nGRID_PAGES equ %d\n    macro GRID_TABLE\n; pitch 0..%d, and in each yaw -%d..%d\ngridtab:\n' % (
        gn, GDY, first_grid, len(gpages), 2 * gn, gn, gn))
    f += ['    db %d : dw $%04X\n' % pa for pa in gindex]
    f.append('    endm\n    macro REV_TABLE\nrevtab:\n')
    for i in range(0, 256, 16):
        f.append('    db ' + ','.join('$%02X' % int('{:08b}'.format(k)[::-1], 2) for k in range(i, i + 16)) + '\n')
    f.append('    endm\n')
    return {'spec_l2.bin': bytes(l2), 'spec_frames.bin': bytes(blob), 'spec_grid.bin': bytes(gblob),
            'spec_data.inc': ''.join(f).encode(), 'pages': fpages + gpages}


def place(pics, pages, at):
    """Pictures back to back from pages[at] on. A picture may run into the next page only when that is the next
    listed page (open_picture maps a page and the one after it). -> ([(page, address)], [(page, 8192 bytes)], next
    index into pages)."""
    index, out, i, off, cur = [], [], at, 0, None

    def fits(i, off, n):
        last = (off + n - 1) // 8192
        return i + last < len(pages) and all(pages[i + k] == pages[i] + k for k in range(last + 1))
    for d in pics:
        while not fits(i, off, len(d)):
            if off == 0:
                raise ValueError('intro pictures do not fit the pages given')
            i, off = i + 1, 0
        index.append((pages[i], 0xC000 + off))
        while d:
            while len(out) <= i - at:
                out.append(bytearray(8192))
            n = min(len(d), 8192 - off)
            out[i - at][off:off + n] = d[:n]
            d, off = d[n:], off + n
            if off == 8192:
                i, off = i + 1, 0
    if off:
        i += 1
    return index, [(pages[at + k], bytes(b)) for k, b in enumerate(out)], i


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
            if n != 'pages':
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


# ---------------------------------------------------------------- the intro inside the game's own .nex (the .nxc option)
# The game's .nex is left as it is and the intro goes into banks it does not list: its code in INTRO_BANK (run at
# 8000-BFFF), Layer 2's picture in L2_BANK..+2, the pictures in PICTURE_PAGES, the work page BUF_PAGE. The option
# ("Show advanced intro screen") changes only bytes: the converter stub's first instructions jump to the intro,
# and the start-up specification screen hold is taken out (the intro replaces it). The intro returns to the stub.
INGAME_GSTEP = 8                  # stored angles of the stick-turned ship: every 8 of 256 (owner trial, 2026-11-22)
INTRO_BANK = 8
BUF_PAGE_INGAME = 18              # bank 9, low page
L2_BANK = 28                      # 28-30
PICTURE_PAGES = list(range(144, 224)) + list(range(106, 116)) + [28, 29, 30, 31, 22, 23, 62, 63, 19]
ORDER = [5, 2, 0, 1, 3, 4, 6, 7] + list(range(8, 112))
_DATA = {}
OPTION = 'Advanced intro screen'   # the .nxc menu line (25 characters at most)


def _nex_banks(nex):
    """-> (header 512 bytes, screen bytes, {bank: 16K})"""
    h = nex[:512]
    scr = 6912 if h[10] == 2 else 0
    if h[10] not in (0, 2):
        raise ValueError('unexpected .nex screen flags %02X' % h[10])
    off, out = 512 + scr, {}
    for b in ORDER:
        if h[18 + b]:
            out[b] = nex[off:off + 16384]
            off += 16384
    assert off == len(nex), 'data past the banks'
    return bytearray(h), nex[512:512 + scr], out


def _nex(h, scr, banks):
    h = bytearray(h)
    for b in range(112):
        h[18 + b] = 1 if b in banks else 0
    h[9] = len(banks)
    return bytes(h) + scr + b''.join(banks[b] for b in ORDER if b in banks)


def ingame(game, snap, say=print, load_screen=None):
    """The game .nex (bytes, with or without its loading screen) -> (with the intro's banks, the option on). The
    first is the build without the intro; the second differs from it only in bytes of the stub and the hook page, and,
    with load_screen (the tape's 6,912 bytes, also in the file's header for the Next's loader), the Spectrum screen in
    bank 5: so the loading screen stays up while the intro checks its pages and holds it 4 s."""
    h, scr, banks = _nex_banks(game)
    entry = h[139]
    pages = [p for p in PICTURE_PAGES if p // 2 not in banks]
    assert len(pages) == len(PICTURE_PAGES), 'the game uses a bank the intro needs'
    for b in [INTRO_BANK, BUF_PAGE_INGAME // 2, L2_BANK, L2_BANK + 1, L2_BANK + 2]:
        assert b not in banks, 'the game uses bank %d' % b
    key = (hashlib.md5(bytes(snap.banks[5])).hexdigest(), tuple(pages))
    if key not in _DATA:
        _DATA[key] = data(snap, say, gstep=INGAME_GSTEP, pages=pages)
    files = _DATA[key]
    used = [p for p, _ in files['pages']]
    sums = [sum(d) & 255 for _, d in files['pages']]
    stub = bytes(banks[entry][0:12])
    work = Path(tempfile.mkdtemp(prefix='r_type_ingame_'))
    try:
        shutil.copy(ASM, work / 'specanim.asm')
        (work / 'spec_data.inc').write_bytes(files['spec_data.inc'])
        nl = '\n    db '
        (work / 'game.inc').write_text(
            '; made by r_type_intro.ingame - do not edit\nRT_ENTRY_BANK equ %d\nBUF_PAGE equ %d\nL2_PAGE equ %d\n'
            '    macro RT_SUMS\n    db %s\n    endm\n    macro RT_PAGE_LIST\n    db %s\n    endm\n'
            '    macro RT_STUB_ORIG\n    db %s\n    endm\n' % (
                entry, BUF_PAGE_INGAME, L2_BANK * 2,
                nl.join(','.join(map(str, sums[i:i + 32])) for i in range(0, len(sums), 32)),
                nl.join(','.join(map(str, used[i:i + 32])) for i in range(0, len(used), 32)),
                ','.join('$%02X' % v for v in stub)), newline='\n')
        r = subprocess.run([_sjasm(), '--sym=intro.sym', '-DALLDIR', '-DGAME', '-DINGAME', 'specanim.asm'],
                           cwd=work, capture_output=True, text=True)
        tail = [l for l in (r.stdout + r.stderr).splitlines() if 'include data' not in l]
        if not tail or 'Errors: 0' not in tail[-1]:
            raise RuntimeError('sjasmplus r_type_intro.asm (INGAME):\n' + '\n'.join(tail[-12:]))
        code = (work / 'intro_code.bin').read_bytes()
        syms = {}
        for line in (work / 'intro.sym').read_text().splitlines():
            parts = line.replace(':', ' ').split()
            if len(parts) >= 3 and parts[1].upper() == 'EQU':
                syms[parts[0]] = int(parts[2].lstrip('$').rstrip('hH'), 16) if parts[2].startswith('$') or parts[2][-1:] in 'hH' else int(parts[2], 0)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    out = dict(banks)
    out[INTRO_BANK] = code
    out[L2_BANK], out[L2_BANK + 1], out[L2_BANK + 2] = (files['spec_l2.bin'][i:i + 16384] for i in (0, 16384, 32768))
    pg = {}
    for p, d in files['pages']:
        pg[p] = d
    for b in sorted({p // 2 for p in pg}):
        out[b] = pg.get(2 * b, bytes(8192)) + pg.get(2 * b + 1, bytes(8192))
    off = _nex(h, scr, out)
    # the option: the stub's first bytes jump to the intro; no start-up specification screen hold in the game
    on = {b: bytearray(d) for b, d in out.items() if b in (entry, 12, 5)}
    if load_screen is not None:
        on[5][0:6912] = load_screen
    jump = bytes([0xF3, 0xED, 0x91, 0x54, INTRO_BANK * 2, 0xED, 0x91, 0x55, INTRO_BANK * 2 + 1, 0xC3,
                  syms['start'] & 255, syms['start'] >> 8])
    assert len(jump) == len(stub)
    on[entry][0:12] = jump
    pat = bytes.fromhex('ED9205C1F1CD')
    at = on[12].find(pat)
    assert at >= 0 and on[12].find(pat, at + 1) < 0, 'spec_hold call not found once'
    on[12][at + 5:at + 8] = bytes(3)
    out_on = {**out, **{b: bytes(d) for b, d in on.items()}}
    return off, _nex(h, scr, out_on), dict(pages=len(used), code=len(code.rstrip(bytes(1))), start=syms['start'], syms={k: syms[k] for k in ('fakestick', 'state', 'handdone', 'badpage') if k in syms})
