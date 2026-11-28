"""Diagnostic North Star build. Release blockers are recorded in games/north_star.md."""
import json
from pathlib import Path

from . import z80tonex

PROFILE = Path(__file__).resolve().parent.parent / 'docs/profiles/north_star.json'
ROM = 0x386e
# Address, whole displaced sequence, branch kind, destination.
SITES = (
    (0xad54, '32edfa', 0xcd, 'g_prepare'),
    (0xba89, '32edfa', 0xcd, 'g_prepare'),
    (0xfb2a, '16402680', 0xc3, 'g_begin'),
    (0xfc4d, 'e1d1c1', 0xc3, 'g_finish'),
    (0xad2e, 'cda9bf', 0xcd, 'g_reset'),
    (0xad5d, 'dd21c0ac', 0xc3, 'g_name'),
    (0xa676, '2a08a2', 0xc3, 'g_player'),
    (0xae22, 'e5d5210000', 0xc3, 'g_actor'),
    (0xab49, 'e501ff08', 0xc3, 'g_lance'),
    (0xbf93, '21cc98', 0xc3, 'g_caption'),
    (0xc06c, '218f40', 0xc3, 'g_wipe'),
    (0xc32a, '3e47cd2fc4', 0xc3, 'g_final'),
)


def word(value):
    return value.to_bytes(2, 'little')


def work_page(code):
    page = bytearray(8192)
    page[:len(code)] = code
    idx = 0x1b00
    for y in range(32, 160, 16):
        for col in range(2, 30, 2):
            offset = ((y & 0xc0) << 5) + ((y & 0x38) << 2) + col
            page[idx:idx + 2] = word(0xa000 + offset)
            idx += 2
    for mask_ink in range(256):
        alpha, ink = divmod(mask_ink, 16)
        pixels = [0 if not (alpha >> bit) & 1 else 2 if (ink >> bit) & 1 else 1
                  for bit in (3, 2, 1, 0)]
        page[0x1c00 + mask_ink] = pixels[0] * 16 + pixels[1]
        page[0x1d00 + mask_ink] = pixels[2] * 16 + pixels[3]
    return bytes(page)


class NorthStarPatch:
    name = 'North Star mirrored playfield and sprites'
    setup_call = 0xd000
    hook_page_data = b''
    uses_printer_buffer = False
    keep_printer_buffer = True
    tail_addr = 0x5b00
    max_tail = 0x54

    def __init__(self):
        hooks = json.loads(PROFILE.read_text())['hooks']
        self.syms = {k: int(v, 16) for k, v in hooks['syms'].items()}
        rom = bytes.fromhex(hooks['rom'])
        self.stub_extra = bytes.fromhex(hooks['setup'])
        self.slot1 = (24, ROM + len(rom))
        self.altrom = (ROM, self.slot1[1] + 20)
        page = bytearray(z80tonex.rom48()[8192:])
        page[ROM-8192:ROM-8192+len(rom)] = rom
        self.page = bytes(page)
        self.extra_banks = {12: self.page + bytes(8192),
                            13: work_page(bytes.fromhex(hooks['work'])) + bytes(8192)}
        self.sites = [(a, bytes.fromhex(old), bytes([op]) + word(self.syms[sym]))
                      for a, old, op, sym in SITES]

    def apply(self, snap):
        if snap.is128:
            raise ValueError('North Star expects a 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            i = a - 0x4000
            if ram[i:i+len(old)] != old:
                raise ValueError('unexpected North Star code at %04X' % a)
            ram[i:i+len(new)] = new
        for i, bank in enumerate((5, 2, 0)):
            snap.banks[bank] = bytes(ram[i*16384:(i+1)*16384])


def build(source, output):
    result = z80tonex.convert(source, output, patch=NorthStarPatch(), quiet=True)
    path = Path(output)
    path.write_bytes(z80tonex.automap_off(path.read_bytes()))
    return result
