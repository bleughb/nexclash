"""Winter Sports, Downhill / Slalom / Giant Slalom (event 0): the panorama on Layer 2, the poles left on the ULA, even pacing.
GPL-3.0-or-later. Facts, decisions and evidence: games/winter_sports.md "Downhill stage 2" and "Event plugins".

The event's left view (character cells 1-14 x 5-20) is a static 256 x 128 monochrome panorama (0xA000, 32 bytes a row) scrolled one pixel
per change of the heading (0x82DC) by 0x8C16 into a 14-byte-wide buffer (0xB207) that the renderer 0x8954 draws the gate poles into
(SET n,(HL) lines) and copies to the screen with the attribute cells of the map at 0xB000. Nothing reads the pane back (traced), so:
  - the panorama is kept on Layer 2 (banks L2_BANK.., 256 x 192, rows 40-167), shown through a clip window over the pane (x 8-119, y 40-167) and scrolled by
    hardware: NextReg 0x16 = 120 - view, where view is the number of pixel steps the original's scroll has taken (it moves ONE pixel per call whatever
    the heading change, so it can lag the heading: the hook keeps the same count, 0x82DC stays the game's);
  - DEFAULT colours = the original 16 only: sky cyan, the paper white, forest and ridge lines green, picked per PIXEL from the bitmap (the game's attribute
    cells stepped them 8 x 8 and turned forest pixels black inside the black-ink cells). ENHANCED (the colour set) = the painted panorama (winter_sports_paint);
  - the event's copy of the panorama is zeroed, so the buffer holds only the poles and the ULA copy draws only them; the pane's attribute cells are made ink black on
    BRIGHT white paper and the ULA palette entry for bright paper 7 is the global transparent colour while the view runs, so the panorama shows through and
    the black poles stay; ULA over Layer 2 (NextReg 0x15 = 0x08, "SUL");
  - PACE: the game's main loop is free-running (update interval 1.24-5.66 frames, mean 2.14; 75 % of an update is the drawing). The one drawing call of the
    loop (0x83AB, CALL 0x84B0) becomes a wrapper: halt for the cadence's next 2 or 3 frames (mean 2.14: the same speed of play, evenly), draw at 28 MHz
    inside the vertical blank (tear-free), back to 3.5 MHz. MODE = 1 (the toggle "Original pace") skips the wrapper and pads each scroll step back to the
    original's measured time instead (50,232-53,881 T by its shift counter), so the free-running pace is the original's;
  - 0x8C16 (the scroll) becomes `JP HOOK`; the init at 0x8BF6 (the heading's start value, once per run) gets `CALL INIT`, which also resets the view;
  - the menu's loader hook (winter_sports.asm_hook) puts the display back (Layer 2 off, the palette entry white) before any event loads.
The hook code lives in the event's own free bytes (0x9400-0x95FF, inside a 3,285-byte zero run of the tape block that no run touched); every patched
site is checked against its original bytes.
"""
from . import winter_sports_common as C
from . import winter_sports_paint as paint

INDEX = 0
PANO, PANO_LEN = 0xA000, 0x1000             # 128 rows x 32 bytes (the bottom 32 rows are all zero: the slope)
ATTR_MAP, ATTR_LEN = 0xB000, 0x0200         # 16 rows x 32 cells
SITE_SCROLL, SITE_SCROLL_ORIG = 0x8C16, bytes.fromhex('3aea8b47')
SITE_INIT, SITE_INIT_ORIG = 0x8BF6, bytes.fromhex('3e3832ea8b')
SITE_DRAW, SITE_DRAW_ORIG = 0x83AB, bytes.fromhex('cdb084')       # CALL 0x84B0: the loop's one drawing call
DRAW = 0x84B0
HOOK, WRAP = 0x9400, 0x94C0
VAR = 0x9500                                # +0 started flag, +1 view, +2 MODE (0 smooth, 1 original pace), +3 cadence index; TABLE at +8
V_STARTED, V_VIEW, V_MODE, V_CAD = VAR, VAR + 1, VAR + 2, VAR + 3
HEADING, SEEN = 0x82DC, 0x8BEA              # the game's heading variable and its "last seen heading" (35818)
L2_BANK = 28                                # Layer 2: banks 28-30 (256 x 192, one byte a pixel)
BANKS = (28, 29, 30)
PANE = (8, 119, 40, 167)                    # the clip window x1, x2, y1, y2 (Layer 2 / ULA coordinates)
STEP_COUNTER = 0x8BE7                       # the original's shift counter (35815), kept by the hook: the original's step costs 50,232-53,881 T by its value
STEP_RIGHT = (53304, 52792, 52280, 51768, 51256, 50744, 50232, 53833)     # T of the original's step, heading up, by the counter before it (measured)
STEP_LEFT = (53881, 53321, 52809, 52297, 51785, 51273, 50761, 50249)      # heading down
OVERHEAD = 220                              # T the hook itself takes in a step, before its pad loop (26 T per pass)
TABLE = VAR + 8                             # 16 pad counts: right 0-7, left 0-7
BRIGHT_PAPER7 = 0x78                        # ink 0, paper 7, bright: palette index 31
TRANSPARENT = C.TRANSPARENT


def enable_code():
    """Layer 2 on over the pane, ULA over it, the bright-white paper entry transparent."""
    a = C.Asm(0)
    a.nr(0x12, L2_BANK)
    a.nr(0x15, 0x08)
    a.nr(0x1C, 0x01)                        # reset the Layer 2 clip index
    for v in PANE:
        a.nr(0x18, v)
    a.nr(0x17, 0x00)
    a.nr(0x14, TRANSPARENT)                 # the global transparent colour (the default, set so)
    a.nr(0x43, 0x00)                        # palette control: the ULA's first palette, auto-increment on
    a.nr(0x40, 31)
    a.nr(0x41, TRANSPARENT)
    a.nr(0x69, 0x80)
    return list(a.done())


def disable_code():
    """What the menu's loader hook runs before any event loads (winter_sports.asm_hook)."""
    a = C.Asm(0)
    a.nr(0x69, 0x00)
    a.nr(0x15, 0x00)
    a.nr(0x43, 0x00)
    a.nr(0x40, 31)
    a.nr(0x41, 0xFF)
    a.nr(0x07, 0x00)                        # 3.5 MHz, whatever the drawing was doing
    return list(a.done())


def asm_hook():
    a = C.Asm(HOOK)
    w = a.w
    a.e(0x3A, w(V_STARTED), 0xB7)           # ld a,(started) / or a
    a.jr(0x20, 'on')
    a.e(0x3E, 0x01, 0x32, w(V_STARTED))     # first call: ld a,1 / ld (started),a
    a.e(enable_code())
    a.L('on')
    a.e(0x3A, w(SEEN), 0x47)                # ld a,(last seen) / ld b,a
    a.e(0x3A, w(HEADING), 0x32, w(SEEN))    # ld a,(heading) / ld (last seen),a  (as the original)
    a.e(0xB8)                               # cp b
    a.jr(0x28, 'show')                      # unchanged
    a.jr(0x38, 'left')                      # carry: heading < last seen
    a.e(0x3A, w(STEP_COUNTER), 0x4F, 0x3C, 0xE6, 0x07, 0x32, w(STEP_COUNTER))   # right: c = counter; counter = (c + 1) & 7
    a.e(0x3A, w(V_VIEW), 0x3C, 0x32, w(V_VIEW))                                 # view + 1
    a.e(0x79)                               # ld a,c
    a.jr(0x18, 'pad')
    a.L('left')
    a.e(0x3A, w(STEP_COUNTER), 0x4F, 0x3D, 0xE6, 0x07, 0x32, w(STEP_COUNTER))   # left: counter = (c - 1) & 7
    a.e(0x3A, w(V_VIEW), 0x3D, 0x32, w(V_VIEW))                                 # view - 1
    a.e(0x79, 0xC6, 0x08)                   # ld a,c / add a,8
    a.L('pad')
    a.e(0x47)                               # ld b,a  (the index)
    a.e(0x3A, w(V_MODE), 0xB7)              # ld a,(mode) / or a
    a.jr(0x20, 'padgo')                     # original pace: pad the step back to the original's time
    a.jr(0x18, 'show')                      # smooth: no pad (the wrapper's cadence paces the loop)
    a.L('padgo')
    a.e(0x78, 0x87, 0x6F, 0x26, 0x00, 0x11, w(TABLE), 0x19)   # ld a,b / add a,a / ld l,a / ld h,0 / ld de,TABLE / add hl,de
    a.e(0x4E, 0x23, 0x46)                   # ld c,(hl) / inc hl / ld b,(hl)
    a.L('padl')
    a.e(0x0B, 0x78, 0xB1)                   # dec bc / ld a,b / or c
    a.jr(0x20, 'padl')
    a.L('show')
    a.e(0x3A, w(V_VIEW), 0x47, 0x3E, 120, 0x90)   # ld a,(view) / ld b,a / ld a,120 / sub b
    a.nr_a(0x16)                            # nextreg 0x16,a
    a.e(0xC9)
    init = a.pc                             # INIT: the original's LD A,56 / LD (35818),A, and view = 56
    a.e(0x3E, 56, 0x32, w(SEEN), 0x32, w(V_VIEW), 0xC9)
    code = a.done()
    assert len(code) <= WRAP - HOOK, len(code)
    return code, init


def asm_wrap():
    a = C.Asm(WRAP)
    C.pace_wrapper(a, DRAW, V_MODE, V_CAD)
    code = a.done()
    assert len(code) <= VAR - WRAP, len(code)
    return code


def l2_image(pix):
    """3 banks x 16,384 bytes of the 256 x 192 Layer 2 picture: panorama row r at y = 40 + r; the rest 0."""
    img = bytearray(3 * 16384)
    for r in range(128):
        y = PANE[2] + r
        img[y * 256:y * 256 + 256] = bytes(pix[r])
    return {L2_BANK + i: bytes(img[i * 16384:(i + 1) * 16384]) for i in range(3)}


def original_pixels(B):
    """The panorama in the ORIGINAL 16 colours, per pixel: ink above row 24 cyan, below it green; paper white (normal)."""
    S = C.SPECCY
    return [[(S[C.CYAN] if y < 24 else S[C.GREEN]) if B[y][x] else S[C.WHITE] for x in range(256)] for y in range(128)]


def pixels(block_bytes, enhanced):
    """(the panorama's L2 pixels) from the event block: original colours, or painted when `enhanced`."""
    pano = block_bytes[PANO - C.Block.BASE:PANO - C.Block.BASE + PANO_LEN]
    B = paint.bits(pano)
    return paint.paint(paint.classify(B), B) if enhanced else original_pixels(B)


def patch_event(block, enhanced=False, original_pace=False):
    """The event-0 block (32,824 bytes, loaded at 0x7500) -> (patched block, {bank: Layer 2 bytes}). ValueError on any original-byte mismatch."""
    b = C.Block(block)
    b.expect(SITE_SCROLL, SITE_SCROLL_ORIG, 'Downhill scroll routine')
    b.expect(SITE_INIT, SITE_INIT_ORIG, 'Downhill heading init')
    b.expect(SITE_DRAW, SITE_DRAW_ORIG, 'Downhill drawing call')
    b.free(HOOK, 0x200, 'Downhill')
    if any(b.at(ATTR_MAP, 0x200)[i] not in (0x3C, 0x3D, 0x38) for i in range(0x200)):
        raise ValueError('Downhill: the attribute map at 0xB000 is not the expected one')
    if b.bytes().count(SITE_DRAW_ORIG) != 1:
        raise ValueError('Downhill: the drawing call 0x84B0 is called from more than one place')
    pix = pixels(b.bytes(), enhanced)
    code, init = asm_hook()
    b.put(PANO, bytes(PANO_LEN))
    b.put(ATTR_MAP, bytes([BRIGHT_PAPER7]) * ATTR_LEN)
    b.put(HOOK, code)
    b.put(WRAP, asm_wrap())
    b.put(V_MODE, bytes([1 if original_pace else 0]))
    b.put(TABLE, b''.join(((t - OVERHEAD) // 26).to_bytes(2, 'little') for t in STEP_RIGHT + STEP_LEFT))
    b.put(SITE_SCROLL, bytes([0xC3, HOOK & 255, HOOK >> 8]))
    b.put(SITE_INIT, bytes([0xCD, init & 255, init >> 8, 0x00, 0x00]))
    b.put(SITE_DRAW, bytes([0xCD, WRAP & 255, WRAP >> 8]))
    return b.bytes(), l2_image(pix)


def tests(patch, z80, say=print):
    """The plugin's checks (winter_sports_dh_test): (ok, [lines])."""
    from . import winter_sports_dh_test as T
    return T.tests(patch, z80, say)
