"""Silkworm (Random Access / Virgin Games, 1989, 128K): the original game on the Next, no hooks.

The play area is monochrome and has no clash: every figure goes through the back buffer 8002-8DBF
and the blit A25E onto white-on-black rows 4-17; the coloured ground rows 18-19 are never in it.
So the default is the game itself. The only things a plain conversion gets wrong here are start-up:
SP is in the top 16K (no automatic tail) and the game keeps code at 5B00, where NEXLOAD writes.
"""
from . import z80tonex as zt

SOURCE_MD5 = '8fad50cd8c218ade32bf3c2332c8ee03'
SIGNATURE = {0x946B: 'CD5EA2', 0x9483: 'C32194', 0xA25E: 'F3ED738D9C313EA0', 0x5B00: 'F331FFFFCD039E'}
TAIL_ADDR = 0x90B0                 # zero bytes the game never reads or writes (all eleven waves, the ending)
TAIL_MAX = 0x50                    # 0x9000-0x901F takes writes past the back buffer; 0x9100 up is read
PRINTER = 0x5B00                   # game code; NEXLOAD leaves its own routines here
DECISIONS = {'figures': 'the original monochrome play area', 'scenery': 'the original attributes',
             'outline': 'none', 'enhanced': 'waiting for the mock-up'}


def is_silkworm(snap):
    """The 128K release at its title: zt.Z80Snapshot (banks) or skoolkit's Snapshot (memory)."""
    if getattr(snap, 'banks', None) is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    if not getattr(snap, 'is128', False):
        return False
    return all(bytes(snap.read(a + i) for i in range(len(v) // 2)) == bytes.fromhex(v) for a, v in SIGNATURE.items())


class Patch:
    name = 'Silkworm 128K: the original game, no hooks'
    uses_printer_buffer = True
    hook_page_data = b''
    extra_banks = {}
    sites = []
    slot1 = None
    setup_call = zt.STUB_ORG + 0x1000
    tail_addr = TAIL_ADDR
    max_tail = TAIL_MAX

    def __init__(self, source=None):
        self.source = str(source) if source else None
        self.stub_extra = b''

    def apply(self, snap):
        if not is_silkworm(snap):
            raise ValueError('not the Silkworm 128K release this engine was built for')
        if any(snap.read(a) for a in range(TAIL_ADDR, TAIL_ADDR + TAIL_MAX)):
            raise ValueError('the tail area is not empty')
        # Setup in the stub bank: put the game's code at 5B00 back, after NEXLOAD (the stub's own
        # printer option refuses 128K snapshots; this game's 128K ROM 1 and locked paging do not mind).
        printer = bytes(snap.read(PRINTER + i) for i in range(256))
        src = self.setup_call + 12
        code = (b'\x21' + zt.w16(src) + b'\x11' + zt.w16(PRINTER) + b'\x01' + zt.w16(256) + b'\xED\xB0' + b'\xC9')
        assert len(code) == 12
        self.stub_extra = code + printer


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p
