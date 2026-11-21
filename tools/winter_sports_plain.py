"""Winter Sports (Electric Dreams, 1985, 48K): ONE self-contained plain .nex with all six events.

    python tools/winter_sports_plain.py MENU.z80 GAME.tap [-o OUT.nex]

MENU.z80 = the 48K snapshot at the main menu (the game's menu code loaded, no event yet); GAME.tap = the
original (or the Bleepload re-release: the six 32,824-byte event blocks are byte-identical in every release) tape.
Game data stays on the user's machine; only the builder is in the repo (no sprite build, no RZX: see games/winter_sports.md).

How it works (verified in JNext 1.2.0, all six events load and play):
  - the six event blocks sit in banks 12..26 (40,960 bytes each, 5 x 8K pages); the menu's screen backup in bank 27;
  - the menu's own LD-BYTES wrapper (0x627E, which calls ROM 0x0562) becomes JP 0x6C00: a 127-byte hook in the
    menu's unused tail (0x6C00; the game never reads it). A header request (DE=22, flag FF) returns the menu's
    own wanted header (table 0x63C0 + 22 k) and notes the event k; a data request (DE=0x8038) copies event k from
    its banks to IX through MMU0 (NextReg 0x50), interrupts off, then restores NextReg 0x50 = 0xFF, the border
    and EI, with carry set, as the ROM's return does;
  - loading screen: the tape's SCREEN$ is the NEX header's ULA loading screen AND the content of bank 5's screen, and the stub's
    setup routine waits 260 frames (5.2 s) counting raster line 192 before copying the menu screen back, so the
    picture shows from launch for at least 5.2 s on top of the load time.
"""
import sys, os, struct
sys.path.insert(0, r'C:\1NEXT\nexclash')
import nexclash
from nexclash import z80tonex as Z, tapeset

HERE = os.path.dirname(os.path.abspath(__file__))
TAP = os.path.join(HERE, 'ws.tap')
Z80 = os.path.join(HERE, 'ws.z80')
HOOK = 0x6C00
PG, REM, EVT = 0x6D00, 0x6D01, 0x6D03
EVENT_BANK0 = 12                 # event k: pages 24+5k .. 28+5k (8K pages), banks 12..26
SCR_BANK = 27                    # menu screen backup (page 54)
WAIT_FRAMES = 260                # 5.2 s of loading screen after the load, before the menu appears


def asm_hook():
    code = bytearray(); lab = {}; fix = []
    def L(n): lab[n] = HOOK + len(code)
    def e(*b): code.extend(b)
    def w(v): return [v & 255, v >> 8]
    def jr(op, n): e(op, 0); fix.append((len(code) - 1, n))
    e(0xF3)                                  # di
    e(0x7A, 0xB7); jr(0x20, 'data')          # ld a,d / or a / jr nz,data
    e(0x2A, *w(0x6296))                      # ld hl,(0x6296)   desired header payload (22 bytes)
    e(0xDD, 0xE5, 0xD1)                      # push ix / pop de
    e(0x01, 22, 0, 0xED, 0xB0)               # ld bc,22 / ldir
    e(0x2A, *w(0x6296), 0x11, *w(0x63C0), 0xB7, 0xED, 0x52)   # hl = ptr - 0x63C0
    e(0x0E, 0x00, 0x11, 22, 0)               # ld c,0 / ld de,22
    L('dv'); e(0xB7, 0xED, 0x52); jr(0x38, 'dvd'); e(0x0C); jr(0x18, 'dv')
    L('dvd'); e(0x79, 0x32, *w(EVT)); jr(0x18, 'ok')
    L('data'); e(0x3A, *w(EVT), 0x4F, 0x87, 0x87, 0x81, 0xC6, 24, 0x32, *w(PG))
    e(0xED, 0x53, *w(REM))                   # ld (REM),de   (de = length)
    e(0xDD, 0xE5, 0xD1)                      # de = dest
    L('next'); e(0x2A, *w(REM), 0x7C, 0xB5); jr(0x28, 'fin')
    e(0x3A, *w(PG), 0xED, 0x92, 0x50, 0x3C, 0x32, *w(PG))   # page -> MMU0, pg++
    e(0x01, 0x00, 0x20, 0x7C, 0xFE, 0x20); jr(0x30, 'full'); e(0x44, 0x4D)
    L('full'); e(0xB7, 0xED, 0x42, 0x22, *w(REM), 0x21, 0, 0, 0xED, 0xB0); jr(0x18, 'next')
    L('fin'); e(0x3E, 0xFF, 0xED, 0x92, 0x50, 0xD5, 0xDD, 0xE1, 0x11, 0, 0)
    L('ok'); e(0x3A, 0x48, 0x5C, 0xE6, 0x38, 0x0F, 0x0F, 0x0F, 0xD3, 0xFE, 0xFB, 0x37, 0xC9)
    for pos, n in fix:
        d = lab[n] - (HOOK + pos + 1)
        assert -128 <= d <= 127, (n, d)
        code[pos] = d & 255
    return bytes(code)


def asm_setup(wait):
    """stub-bank routine (0xD000): wait `wait` frames on the loading screen, then show the menu screen."""
    c = bytearray()
    def e(*b): c.extend(b)
    e(0x21, wait & 255, wait >> 8)            # ld hl,wait
    # frame = wait for raster line 192 to come round: NextReg 0x1F = line LSB, 0x1E bit0 = MSB
    top = len(c)
    e(0x01, 0x3B, 0x24, 0x3E, 0x1F, 0xED, 0x79, 0x04, 0xED, 0x78)    # ld bc,243B / ld a,1F / out (c),a / inc b / in a,(c)
    e(0xFE, 0xC0)                             # cp 192
    e(0x20, 0)                                # jr nz,top (patched)
    j1 = len(c) - 1
    c[j1] = (top - (j1 + 1)) & 255
    # wait until the line moves off 192
    t2 = len(c)
    e(0x01, 0x3B, 0x24, 0x3E, 0x1F, 0xED, 0x79, 0x04, 0xED, 0x78, 0xFE, 0xC0)
    e(0x28, 0); j2 = len(c) - 1
    c[j2] = (t2 - (j2 + 1)) & 255
    e(0x2B, 0x7C, 0xB5)                       # dec hl / ld a,h / or l
    e(0x20, 0); j3 = len(c) - 1
    c[j3] = (top - (j3 + 1)) & 255
    # menu screen back
    e(0xED, 0x91, 0x57, 2 * SCR_BANK)         # nextreg 0x57, page
    e(0x21, 0, 0xE0, 0x11, 0, 0x40, 0x01, 0, 0x1B, 0xED, 0xB0)
    e(0xED, 0x91, 0x57, Z.STUB_PAGE_HI)
    e(0xC9)
    return bytes(c)


class Patch:
    name = 'winter sports: six events in banks, RAM loader hook, loading screen'
    uses_printer_buffer = False
    setup_call = 0xD000
    hook_page_data = b''

    def __init__(self):
        B = tapeset.data_blocks(open(TAP, 'rb').read(), 'tap')
        self.scr = B[3][1:-1]
        assert len(self.scr) == 6912
        ev = [B[11 + 2 * k][1:-1] for k in range(6)]
        assert all(len(x) == 32824 for x in ev)
        self.extra_banks = {}
        blob = b''.join(x + bytes(40960 - len(x)) for x in ev)
        for i in range(15):
            self.extra_banks[EVENT_BANK0 + i] = blob[i * 16384:(i + 1) * 16384]
        self.stub_extra = asm_setup(WAIT_FRAMES)
        self.menu_scr = None

    def apply(self, snap):
        b5 = bytearray(snap.banks[5])
        self.menu_scr = bytes(b5[:6912])
        # patch site check: the menu's LD-BYTES wrapper
        assert bytes(b5[0x227E:0x2282]) == bytes([0x14, 0x08, 0x15, 0xF3]), 'not the Winter Sports menu snapshot: ' + bytes(b5[0x227E:0x2282]).hex()
        h = asm_hook()
        b5[HOOK - 0x4000:HOOK - 0x4000 + len(h)] = h
        b5[0x227E:0x2281] = bytes([0xC3, HOOK & 255, HOOK >> 8])
        b5[0:6912] = self.scr                 # the loading screen is what the game memory shows first
        snap.banks[5] = bytes(b5)
        self.extra_banks[SCR_BANK] = self.menu_scr + bytes(16384 - 6912)
        self.hook_len = len(h)


def build(out):
    p = Patch()
    z = Z.convert(Z80, out, patch=p)
    d = bytearray(open(out, 'rb').read())
    d[10] = 0x82                         # ULA loading screen, no palette
    d = bytes(d[:512]) + p.scr + bytes(d[512:])
    open(out, 'wb').write(d)
    return p


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Winter Sports: one self-contained plain .nex with all six events')
    ap.add_argument('menu_z80'); ap.add_argument('tap'); ap.add_argument('-o', '--output')
    a = ap.parse_args(argv)
    global TAP, Z80
    TAP, Z80 = a.tap, a.menu_z80
    out = a.output or os.path.splitext(a.menu_z80)[0] + '.nex'
    p = build(out)
    print('hook %d bytes at 0x%04X, setup %d bytes, loading screen %d frames' % (p.hook_len, HOOK, len(p.stub_extra), WAIT_FRAMES))


if __name__ == '__main__':
    main()
