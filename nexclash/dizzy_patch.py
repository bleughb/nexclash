#!/usr/bin/env python3
"""
dizzy_patch.py - Treasure Island Dizzy (48K): replace the software-drawn Dizzy
with Spectrum Next hardware sprites, and write a .nex file.

    python dizzy_patch.py dizzy2_game.z80 [-o dizzy2_sprites.nex]

Needs z80tonex.py in the same folder. Works with any .z80 snapshot of the 48K
Codemasters release taken after loading (title screen or in game); it checks
the code it patches and stops if anything doesn't match.

What the patch does
  * The plotter (39774) and eraser (40087) still run exactly as before and
    still build the undo buffer, but their 11 screen writes are no-ops, so
    Dizzy is never drawn into the ULA screen.
  * Each plot positions four 16x16 hardware sprites (4-bit colour) at Dizzy's
    position with the current frame. All 39 frames are uploaded once at start
    (103 unique patterns).
  * Dizzy is hidden when the play area is wiped, and at the end of any
    in-game interrupt where he was erased and not redrawn. The title-screen
    interrupt handler is left untouched: its music depends on exact timing.
  * The bubble collision test sees the screen as the original would (with
    Dizzy's pixels), rebuilt from the undo buffer, so bubbles behave exactly
    as in the original.

Memory used
  0x5B00-0x5B50   trampolines (printer buffer, never used by the game)
  bank 10         start-up stub, pattern setup, hook code (paged in at 0x0000
                  only while a hook runs, with interrupts disabled)
  bank 11         sprite patterns (only used at start-up)
  The start-up tail goes just below the snapshot's stack pointer.

Source: tramp.asm, hooks.asm, setup.asm (sjasmplus --zxnext).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import z80tonex  # noqa: E402

# ---- assembled patch code (from tramp.asm / hooks.asm / setup.asm) ----
TRAMP_ORG = 0x5B00
TRAMP = bytes.fromhex(
    '00F3ED915015CD0000ED9150FFC35E9BED915015CD0300ED9150FFC9F5AF3200'
    '5BF1F3ED73CE9CC39C9CF5AF32005BED911500F1DD218174C387AFF53A005BB7'
    '2004ED911500F1C30272')
HOOKS = bytes.fromhex(
    'C30600C37600F5C5D5E5556F260029292901EA00094B0600CB21CB10CB21CB10'
    '79C6204F300104AFCD5A0079C6104F3001043E01CD5A007AC610573E02CD5A00'
    '79D6104F3001053E03CD5A00ED9115013E0132005BE1D1C1F1C9ED923479ED92'
    '357AED923678E601ED92377E23ED92387E23ED9239C94F0600CB39F509CD8D00'
    '47F17806003803E6F0C9E60FC93A005BB72855C5D57CE6075F7D0F0FE638B35F'
    '7C070707E6C0B35FE52AD79C012174B7ED42CB3CCB1D7B9557E1382A3AD69C5F'
    '7ABB30223AD59C4F7DE61F913818FE043014E55F6A2600292916001911D99C19'
    '7EE1AED1C1C9D1C17EC9')   # table appended at offset 234
SETUP = bytes.fromhex(
    'ED911500AF013B30ED79ED9157162100E01E20CD56D0ED9157172100E03A5FD0'
    '5FCD56D0ED915715ED914320ED914000ED914100ED914100ED9141B6ED914300'
    'ED914B000604AFED9234ED913800ED9139003C10F2C9015B00EDB31D20FBC900')
SETUP_ORG = 0xD000
SETUP_NBLOCKS2_OFF = 95

T_PLOT, T_BUB, T_ERASE, T_WIPE, T_ISR = 23297, 23312, 23324, 23338, 23355

# ---- game data ----
FRAME_TABLE = 40249      # 39 word offsets relative to FRAME_BASE
FRAME_BASE = 40327
NUM_FRAMES = 39

# (address, original bytes, new bytes)
def site_patches():
    def w(v):
        return bytes([v & 255, v >> 8])
    p = [
        (61578, b'\xCD\x5E\x9B', b'\xCD' + w(T_PLOT)),        # CALL 39774 -> plot hook
        (63000, b'\xCD\x7D\xF3', b'\xCD' + w(T_BUB)),         # CALL 62333 -> bubble test
        (40087, b'\xF3\xED\x73', b'\xC3' + w(T_ERASE)),       # DI / LD (40142),SP -> JP
        (44931, b'\xDD\x21\x81\x74', b'\xC3' + w(T_WIPE) + b'\x00'),  # LD IX,29825 -> JP
        (61362, b'\xCD\x02\x72', b'\xCD' + w(T_ISR)),         # CALL 29186 in game ISR
    ]
    for a in (39895, 39906, 39917, 40032, 40043, 40054, 40068):   # plotter LD (HL),B
        p.append((a, b'\x70', b'\x00'))
    for a in (40115, 40119, 40124, 40128):                        # eraser LD (HL),A
        p.append((a, b'\x77', b'\x00'))
    return p


def read_frames(peek):
    """Return a list of (height, {(x, y): 'T'|'K'|'W'}) for the 39 frames."""
    frames = []
    for n in range(NUM_FRAMES):
        off = peek(FRAME_TABLE + 2 * n) | peek(FRAME_TABLE + 2 * n + 1) << 8
        a = FRAME_BASE + off
        h = peek(a)
        if not 1 <= h <= 32:
            raise ValueError('frame %d has height %d - not the expected game data' % (n, h))
        px = {}
        for r in range(h):
            for bx in range(3):
                mk = peek(a + 2 + r * 6 + bx * 2)
                gf = peek(a + 3 + r * 6 + bx * 2)
                for bit in range(8):
                    m = (mk >> (7 - bit)) & 1
                    g = (gf >> (7 - bit)) & 1
                    if m and g:
                        raise ValueError('frame %d uses inverted pixels (not supported)' % n)
                    px[(bx * 8 + bit, r)] = 'T' if m else ('W' if g else 'K')
        frames.append((h, px))
    return frames


COLOUR = {'T': 0, 'K': 1, 'W': 2}      # sprite palette indices (set in setup.asm)
QUADS = [(0, 0), (16, 0), (16, 16), (0, 16)]   # TL, TR, BR, BL (order used by hooks.asm)


def build_patterns(frames):
    """Frames are bottom-aligned in a 32x32 box. Returns (pattern bytes, table)."""
    patterns = []
    index = {}
    table = bytearray()
    for h, px in frames:
        top = 32 - h
        for qx, qy in QUADS:
            pix = []
            for y in range(16):
                for x in range(16):
                    pix.append(COLOUR[px.get((qx + x, qy + y - top), 'T')])
            if not any(pix):
                table += b'\x00\x00'
                continue
            key = bytes(pix)
            if key not in index:
                index[key] = len(patterns)
                patterns.append(bytes((pix[i] << 4) | pix[i + 1] for i in range(0, 256, 2)))
            p = index[key]
            table += bytes([0xC0 | (p >> 1), 0x80 | ((p & 1) << 6)])  # visible+ext, 4-bit
    if len(patterns) > 128:
        raise ValueError('%d patterns needed, only 128 fit' % len(patterns))
    return b''.join(patterns), bytes(table), len(patterns)


class DizzyPatch:
    name = 'Dizzy hardware sprite'
    uses_printer_buffer = True

    def __init__(self):
        self.stub_extra = b''
        self.setup_call = SETUP_ORG
        self.hook_page_data = b''
        self.extra_banks = {}
        self.num_patterns = 0

    def apply(self, snap):
        if snap.is128:
            raise ValueError('this patch is for the 48K version')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])

        def peek(a):
            return ram[a - 0x4000]

        def poke(a, data):
            ram[a - 0x4000:a - 0x4000 + len(data)] = data

        for a, old, new in site_patches():
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s) - not the expected '
                                 'version of the game, or already patched' % (a, cur.hex(), old.hex()))
        if any(ram[TRAMP_ORG - 0x4000:TRAMP_ORG - 0x4000 + len(TRAMP)]):
            raise ValueError('printer buffer at 0x5B00 is not empty in this snapshot')

        frames = read_frames(peek)
        pats, table, n = build_patterns(frames)
        self.num_patterns = n

        for a, old, new in site_patches():
            poke(a, new)
        poke(TRAMP_ORG, TRAMP)
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])

        self.hook_page_data = HOOKS + table
        pats = pats + bytes(-len(pats) % 256)          # whole 256-byte blocks for OTIR
        if len(pats) > 16384:
            raise ValueError('pattern data too large')
        setup = bytearray(SETUP)
        setup[SETUP_NBLOCKS2_OFF] = max(0, len(pats) - 8192) // 256
        if len(pats) < 8192:
            raise ValueError('pattern data smaller than expected')
        self.stub_extra = bytes(setup)
        self.extra_banks = {11: pats}


def main():
    ap = argparse.ArgumentParser(description='Treasure Island Dizzy: hardware sprite patch -> .nex')
    ap.add_argument('z80', help='48K .z80 snapshot of Treasure Island Dizzy')
    ap.add_argument('-o', '--output', help='output .nex (default: <name>_sprites.nex)')
    ap.add_argument('--allow-60hz', action='store_true', help='do not force 50Hz video')
    args = ap.parse_args()
    dst = args.output or os.path.splitext(args.z80)[0] + '_sprites.nex'
    patch = DizzyPatch()
    try:
        z80tonex.convert(args.z80, dst, None, not args.allow_60hz, patch=patch)
    except (ValueError, OSError) as e:
        sys.exit('Error: %s' % e)
    print('Sprites  : %d patterns for 39 frames' % patch.num_patterns)


if __name__ == '__main__':
    main()
