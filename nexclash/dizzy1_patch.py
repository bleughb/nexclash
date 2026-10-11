#!/usr/bin/env python3
"""
dizzy1_patch.py - Dizzy: The Ultimate Cartoon Adventure (1987, 48K): replace the
software-drawn Dizzy with Spectrum Next hardware sprites, and write a .nex file.

    python dizzy1_patch.py dizzy1.z80 [-o dizzy1_sprites.nex]

Needs z80tonex.py in the same folder. It checks every byte it patches and stops
if the snapshot is a different version of the game.

What the patch does
  * Dizzy's XOR plotter (58113) still runs exactly as before, but its one screen
    write (58184) is a no-op, so Dizzy never reaches the ULA screen.
  * Just before each XOR draw (58159) a hook toggles "Dizzy drawn" parity, the
    same way XOR drawing does, and shows the sprite at the new position and frame,
    or hides it. So a double draw (which cancels on the original screen) hides him.
  * The object collision test (60228) sees the screen as the original would,
    screen XOR Dizzy's graphic, so objects still land on Dizzy exactly as before.
  * Room wipes (58634) hide the sprite.
  * All 39 frames (the game's pre-shifted copies are the same images 4 pixels
    right) use 88 four-bit patterns, uploaded once at start-up.

Memory used
  0x5B00-0x5B80  trampolines + state (printer buffer; the stack stays above 23503)
  0x5B81-0x5BD0  start-up tail (dead once the game runs)
  bank 10        start-up stub, pattern setup, hook code (paged in at 0x0000 only
                 while a hook runs, with interrupts disabled and restored)
  bank 11        sprite patterns (start-up only)

Source: tramp.asm, hooks.asm, setup.asm, defs.inc (sjasmplus --zxnext).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import z80tonex  # noqa: E402

TRAMP_ORG = 0x5B00
TRAMP = bytes.fromhex(
    '0000000000000000F5ED57EA105BED57F3F5ED915015CD0000ED9150FFF1E222'
    '5BFBF13A75E1C332E3C5E53A7FE74F0600A7ED42CB39380909CD4A5BE6F0E1C1'
    'C909CD4A5BE60FE1C1C93A005BB720027EC9C5ED57EA5A5BED57F3F5ED915015'
    'CD0300ED9150FF4FF1E26D5BFB79C1C9F5AF32005BED911500F1DD21D65CC30E'
    'E5')
HOOKS = bytes.fromhex(
    'C30600C3C600F5C5D5E5DD22015BED53035B3A70E132055B3A74E1CB3F32065B'
    '3A75E132075B3A005BEE0132005B28713A6DE10E00FE273804D6270E046F2600'
    '29292911100119E53A70E16F260029292906000901200009444DDD6E00DD6601'
    '7CE6075F7D0F0FE638B35F7C070707E6C0B3C62057E1AFCDAA0079C6104F3001'
    '043E01CDAA007AC610573E02CDAA0079D6104F3001053E03CDAA00ED91150118'
    '04ED911500E1D1C1F1C9ED923479ED92357AED923678E601ED92377E23ED9238'
    '7E23ED9239C9C5D5DDE5DD2A015BED5B035B3A075B47DD7E01BC20203A055BDD'
    '86004F7D9138154F3A065BB9380E280CEB7D816F3001247EEBAE180F3A065B83'
    '5F300114DD2BDD2B10CC7EDDE1D1C1C9')   # table appended at offset 272
SETUP = bytes.fromhex(
    'ED911500AF013B30ED79ED9157162100E01E20CD56D0ED9157172100E03A5FD0'
    '5FCD56D0ED915715ED914320ED914000ED914100ED914100ED9141B6ED914300'
    'ED914B000604AFED9234ED913800ED9139003C10F2C9015B00EDB31D20FBC900')
SETUP_ORG = 0xD000
SETUP_NBLOCKS2_OFF = 95
T_DREW, T_COLL, T_WIPE = 23304, 23337, 23408
TAIL_ADDR = TRAMP_ORG + len(TRAMP)

FRAME_TABLE = 24134
FRAME_BASE = 24290
NUM_FRAMES = 39


def site_patches():
    def w(v):
        return bytes([v & 255, v >> 8])
    return [
        (58159, b'\x3A\x75\xE1', b'\xC3' + w(T_DREW)),              # LD A,(57717) -> JP T_DREW
        (58184, b'\x77', b'\x00'),                                  # LD (HL),A -> NOP
        (60228, b'\xC5\xE5\x3A', b'\xC3' + w(T_COLL)),              # collision test -> JP
        (58634, b'\xDD\x21\xD6\x5C', b'\xC3' + w(T_WIPE) + b'\x00'),  # LD IX,23766 -> JP
    ]


def read_frames(peek):
    frames = []
    for n in range(NUM_FRAMES):
        off = peek(FRAME_TABLE + 2 * n) | peek(FRAME_TABLE + 2 * n + 1) << 8
        a = FRAME_BASE + off
        w, h = peek(a), peek(a + 1)
        wb = w // 2
        if not (1 <= h <= 32 and 1 <= wb <= 4):
            raise ValueError('frame %d has size %dx%d - not the expected game data' % (n, wb, h))
        px = set()
        for r in range(h):
            for b in range(wb):
                v = peek(a + 4 + r * wb + b)
                for bit in range(8):
                    if v >> (7 - bit) & 1:
                        px.add((b * 8 + bit, r))
        frames.append(px)
    return frames


QUADS = [(0, 0), (16, 0), (16, 16), (0, 16)]   # TL, TR, BR, BL (order used by hooks.asm)
WHITE = 2                                       # sprite palette index (set in setup.asm)


def build_patterns(frames):
    patterns, index, table = [], {}, bytearray()
    for px in frames:
        for qx, qy in QUADS:
            pix = [WHITE if (qx + x, qy + y) in px else 0 for y in range(16) for x in range(16)]
            if not any(pix):
                table += b'\x00\x00'
                continue
            key = bytes(pix)
            if key not in index:
                index[key] = len(patterns)
                patterns.append(bytes((pix[i] << 4) | pix[i + 1] for i in range(0, 256, 2)))
            p = index[key]
            table += bytes([0xC0 | (p >> 1), 0x80 | ((p & 1) << 6)])
    if len(patterns) > 128:
        raise ValueError('%d patterns needed, only 128 fit' % len(patterns))
    return b''.join(patterns), bytes(table), len(patterns)


class Dizzy1Patch:
    name = 'Dizzy 1 hardware sprite'
    uses_printer_buffer = True
    tail_addr = TAIL_ADDR

    def __init__(self):
        self.stub_extra = b''
        self.setup_call = SETUP_ORG
        self.hook_page_data = b''
        self.extra_banks = {}
        self.num_patterns = 0

    def apply(self, snap):
        if snap.is128:
            raise ValueError('this patch is for the 48K version')
        if TRAMP_ORG <= snap.sp < TAIL_ADDR + 96:
            raise ValueError('snapshot stack pointer (0x%04X) is inside the patch area; take the '
                             'snapshot at a different moment (e.g. the title screen)' % snap.sp)
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])

        def peek(a):
            return ram[a - 0x4000]

        for a, old, new in site_patches():
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s) - not the expected '
                                 'version of the game, or already patched' % (a, cur.hex(), old.hex()))
        pats, table, n = build_patterns(read_frames(peek))
        self.num_patterns = n
        for a, old, new in site_patches():
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        ram[TRAMP_ORG - 0x4000:TRAMP_ORG - 0x4000 + len(TRAMP)] = TRAMP
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.hook_page_data = HOOKS + table
        pats = pats + bytes(-len(pats) % 256)
        if len(pats) < 8192:
            pats = pats + bytes(8192 - len(pats))     # setup uploads a full first page
        setup = bytearray(SETUP)
        setup[SETUP_NBLOCKS2_OFF] = (len(pats) - 8192) // 256
        self.stub_extra = bytes(setup)
        self.extra_banks = {11: pats}


def main():
    ap = argparse.ArgumentParser(description='Dizzy 1: hardware sprite patch -> .nex')
    ap.add_argument('z80', help='48K .z80 snapshot of Dizzy: The Ultimate Cartoon Adventure')
    ap.add_argument('-o', '--output', help='output .nex (default: <name>_sprites.nex)')
    ap.add_argument('--allow-60hz', action='store_true', help='do not force 50Hz video')
    args = ap.parse_args()
    dst = args.output or os.path.splitext(args.z80)[0] + '_sprites.nex'
    patch = Dizzy1Patch()
    try:
        z80tonex.convert(args.z80, dst, None, not args.allow_60hz, patch=patch)
    except (ValueError, OSError) as e:
        sys.exit('Error: %s' % e)
    print('Sprites  : %d patterns for 39 frames' % patch.num_patterns)


if __name__ == '__main__':
    main()
