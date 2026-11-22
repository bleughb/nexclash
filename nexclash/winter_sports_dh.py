"""Winter Sports, Downhill / Slalom / Giant Slalom (event 0): the panorama on Layer 2, the poles left on the ULA.
GPL-3.0-or-later. Facts, decisions and evidence: games/winter_sports.md "Downhill stage 2".

The event's left view (character cells 1-14 x 5-20) is a static 256 x 128 monochrome panorama (0xA000, 32 bytes a row) scrolled one pixel
per change of the heading (0x82DC) by 0x8C16 into a 14-byte-wide buffer (0xB207) that the renderer 0x8954 draws the gate poles into
(SET n,(HL) lines) and copies to the screen with the attribute cells of the map at 0xB000. Nothing reads the pane back (traced), so:
  - the panorama is painted (winter_sports_paint) and kept on Layer 2 (banks L2_BANK.., 256 x 192, rows 40-167), shown through a clip
    window over the pane (x 8-119, y 40-167) and scrolled by hardware: NextReg 0x16 = 120 - view, where view is the number of
    pixel steps the original's scroll has taken (it moves ONE pixel per call whatever the heading change, so it can lag the heading: the
    hook keeps the same count, 0x82DC stays the game's);
  - the event's copy of the panorama is zeroed, so the buffer holds only the poles and the ULA copy draws only them; the pane's attribute cells
    are made ink black on BRIGHT white paper, and the ULA palette entry for bright paper 7 is the global transparent colour (NextReg 0x14 = 0xE3)
    while the view runs, so the panorama shows through and the black poles stay; ULA over Layer 2 (NextReg 0x15 = 0x08, "SUL");
  - 0x8C16 (the scroll, 50,232-53,881 T for a one-pixel step, by the original's shift counter) becomes `JP HOOK`: the hook sets the register, keeps that counter and pads
    each step back to the original's time from a table, so the game's pace is unchanged; the init at 0x8BF6 (the heading's start value, once per run) gets `CALL INIT`, which also resets the hook's count;
  - the menu's loader hook (winter_sports.asm_hook) puts the display back (Layer 2 off, the palette entry white) before any event loads.
The hook code lives in the event's own free bytes (0x9400-0x95FF, inside a 3,285-byte zero run of the tape block that no run touched); every patched site is checked against its original bytes.
"""
import os
import sys

from . import winter_sports_paint as paint

PANO, PANO_LEN = 0xA000, 0x1000             # 128 rows x 32 bytes (the bottom 32 rows are all zero: the slope)
ATTR_MAP, ATTR_LEN = 0xB000, 0x0200         # 16 rows x 32 cells
SITE_SCROLL, SITE_SCROLL_ORIG = 0x8C16, bytes.fromhex('3aea8b47')
SITE_INIT, SITE_INIT_ORIG = 0x8BF6, bytes.fromhex('3e3832ea8b')
HOOK, VAR = 0x9400, 0x9500                  # hook code; VAR = initialised flag, VAR+1 = view (0x932B-0x9FFF: zero in the tape block, untouched in the runs)
HEADING, SEEN = 0x82DC, 0x8BEA              # the game's heading variable and its "last seen heading" (35818)
L2_BANK = 28                                # Layer 2: banks 28-30 (256 x 192, one byte a pixel)
PANE = (8, 119, 40, 167)                    # the clip window x1, x2, y1, y2 (Layer 2 / ULA coordinates)
STEP_COUNTER = 0x8BE7                       # the original's shift counter (35815), kept by the hook: the original's step costs 50,232-53,881 T by its value
STEP_RIGHT = (53304, 52792, 52280, 51768, 51256, 50744, 50232, 53833)     # T of the original's step, heading up, by the counter before it (measured)
STEP_LEFT = (53881, 53321, 52809, 52297, 51785, 51273, 50761, 50249)      # heading down
OVERHEAD = 220                              # T the hook itself takes in a step, before its pad loop (26 T per pass)
TABLE = VAR + 8                             # 16 pad counts: right 0-7, left 0-7
BRIGHT_PAPER7 = 0x78                        # ink 0, paper 7, bright: palette index 31
TRANSPARENT = 0xE3


def _nr(reg, val):
    return [0xED, 0x91, reg, val]


def enable_code():
    """Layer 2 on over the pane, ULA over it, the bright-white paper entry transparent."""
    c = []
    c += _nr(0x12, L2_BANK)
    c += _nr(0x15, 0x08)
    c += _nr(0x1C, 0x01)                    # reset the Layer 2 clip index
    for v in PANE:
        c += _nr(0x18, v)
    c += _nr(0x17, 0x00)
    c += _nr(0x14, TRANSPARENT)             # the global transparent colour (the default, set so)
    c += _nr(0x43, 0x00)                    # palette control: the ULA's first palette, auto-increment on
    c += _nr(0x40, 31)
    c += _nr(0x41, TRANSPARENT)
    c += _nr(0x69, 0x80)
    return c


def disable_code():
    """What the menu's loader hook runs before any event loads (winter_sports.asm_hook)."""
    return _nr(0x69, 0x00) + _nr(0x15, 0x00) + _nr(0x43, 0x00) + _nr(0x40, 31) + _nr(0x41, 0xFF)


def asm_hook():
    code = bytearray()
    lab = {}
    fix = []

    def L(n):
        lab[n] = HOOK + len(code)

    def e(*b):
        code.extend(b)

    def w(v):
        return [v & 255, v >> 8]

    def jr(op, n):
        e(op, 0)
        fix.append((len(code) - 1, n))
    e(0x3A, *w(VAR))                        # ld a,(VAR)
    e(0xB7)
    jr(0x20, 'on')                          # jr nz,on
    e(0x3E, 0x01, 0x32, *w(VAR))            # first call: ld a,1 / ld (VAR),a
    e(*enable_code())
    L('on')
    e(0x3A, *w(SEEN), 0x47)                 # ld a,(last seen) / ld b,a
    e(0x3A, *w(HEADING), 0x32, *w(SEEN))    # ld a,(heading) / ld (last seen),a  (as the original)
    e(0xB8)                                 # cp b
    jr(0x28, 'show')                        # jr z,show: unchanged
    jr(0x38, 'left')                        # carry: heading < last seen
    e(0x3A, *w(STEP_COUNTER), 0x4F, 0x3C, 0xE6, 0x07, 0x32, *w(STEP_COUNTER))   # right: c = counter; counter = (c + 1) & 7
    e(0x3A, *w(VAR + 1), 0x3C, 0x32, *w(VAR + 1))                               # view + 1
    e(0x79)                                 # ld a,c
    jr(0x18, 'pad')
    L('left')
    e(0x3A, *w(STEP_COUNTER), 0x4F, 0x3D, 0xE6, 0x07, 0x32, *w(STEP_COUNTER))   # left: counter = (c - 1) & 7
    e(0x3A, *w(VAR + 1), 0x3D, 0x32, *w(VAR + 1))                               # view - 1
    e(0x79, 0xC6, 0x08)                     # ld a,c / add a,8
    L('pad')
    e(0x87, 0x6F, 0x26, 0x00, 0x11, *w(TABLE), 0x19)   # add a,a / ld l,a / ld h,0 / ld de,TABLE / add hl,de
    e(0x4E, 0x23, 0x46)                     # ld c,(hl) / inc hl / ld b,(hl)
    L('padl')
    e(0x0B, 0x78, 0xB1)                     # dec bc / ld a,b / or c
    jr(0x20, 'padl')                        # jr nz,padl
    L('show')
    e(0x3A, *w(VAR + 1), 0x47, 0x3E, 120, 0x90)   # ld a,(view) / ld b,a / ld a,120 / sub b
    e(0xED, 0x92, 0x16)                     # nextreg 0x16,a
    e(0xC9)                                 # ret
    for pos, n in fix:
        d = lab[n] - (HOOK + pos + 1)
        assert -128 <= d <= 127, (n, d)
        code[pos] = d & 255
    init = HOOK + len(code)                 # INIT: the original's LD A,56 / LD (35818),A, and view = 56
    code += bytes([0x3E, 56, 0x32, SEEN & 255, SEEN >> 8, 0x32, (VAR + 1) & 255, (VAR + 1) >> 8, 0xC9])
    assert len(code) <= 0x100, len(code)
    return bytes(code), init


def l2_image(pix):
    """3 banks x 16,384 bytes of the 256 x 192 Layer 2 picture: panorama row r at y = 40 + r; the rest 0."""
    img = bytearray(3 * 16384)
    for r in range(128):
        y = PANE[2] + r
        img[y * 256:y * 256 + 256] = bytes(pix[r])
    return {L2_BANK + i: bytes(img[i * 16384:(i + 1) * 16384]) for i in range(3)}


def patch_event(block):
    """The event-0 block (32,824 bytes, loaded at 0x7500) -> (patched block, {bank: Layer 2 bytes}). ValueError on any original-byte mismatch."""
    base = 0x7500
    b = bytearray(block)

    def at(a, n):
        return bytes(b[a - base:a - base + n])

    def put(a, d):
        b[a - base:a - base + len(d)] = d
    if at(SITE_SCROLL, 4) != SITE_SCROLL_ORIG:
        raise ValueError('Downhill: bytes at 0x%04X are %s, not the scroll routine' % (SITE_SCROLL, at(SITE_SCROLL, 4).hex()))
    if at(SITE_INIT, 5) != SITE_INIT_ORIG:
        raise ValueError('Downhill: bytes at 0x%04X are %s, not the heading init' % (SITE_INIT, at(SITE_INIT, 5).hex()))
    if any(at(HOOK, 0x200)):
        raise ValueError('Downhill: 0x%04X-0x%04X is not free in this event block' % (HOOK, HOOK + 0x1FF))
    if any(at(ATTR_MAP, 0x200)[i] not in (0x3C, 0x3D, 0x38) for i in range(0x200)):
        raise ValueError('Downhill: the attribute map at 0xB000 is not the expected one')
    pano = at(PANO, PANO_LEN)
    B = paint.bits(pano)
    pix = paint.paint(paint.classify(B), B)
    code, init = asm_hook()
    put(PANO, bytes(PANO_LEN))
    put(ATTR_MAP, bytes([BRIGHT_PAPER7]) * ATTR_LEN)
    put(HOOK, code)
    put(TABLE, b''.join(((t - OVERHEAD) // 26).to_bytes(2, 'little') for t in STEP_RIGHT + STEP_LEFT))
    put(SITE_SCROLL, bytes([0xC3, HOOK & 255, HOOK >> 8]))
    put(SITE_INIT, bytes([0xCD, init & 255, init >> 8, 0x00, 0x00]))
    return bytes(b), l2_image(pix), pix
