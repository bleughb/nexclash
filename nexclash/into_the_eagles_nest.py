"""Into the Eagle's Nest (Pandora, 1987, 128K): the original game on the Next, no hooks.

No colour clash: the play area is whole 8x8 tiles, each with its own attribute (8500, tile sets
D200 / DB00, attributes DA00 / E300); figures are blocks of tiles and replace the cells they stand on.
So the default is the game itself. Target: the [a][a] dump, already running at its menu: the plain
(128K) dump stops in 128K BASIC, whose statements page ROM 0.
"""
from . import z80tonex as zt

SOURCE_MD5 = '0566e3b37d49c6fa6f62e81eb883ad0c'
SIGNATURE = {0x8500: '4F3A50BF477B90FE18', 0x8152: 'CD22A6', 0x83AB: 'F53A4CBF', 0x8729: '28F8'}
TAIL_ADDR = 0xB980                 # zero bytes the game never reads or writes (floors 0-4, 6, 7)
TAIL_MAX = 0x80
PRINTER = 0x5B00                   # zero and unused in play; put back after NEXLOAD so the start is exact
DECISIONS = {'figures': 'the original tiles and attributes', 'scenery': 'the original tiles and attributes',
             'outline': 'none', 'enhanced': 'waiting for the mock-up'}


def is_into_the_eagles_nest(snap):
    """The 128K [a][a] dump at its menu: zt.Z80Snapshot (banks) or skoolkit's Snapshot (memory)."""
    if getattr(snap, 'banks', None) is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    if not getattr(snap, 'is128', False):
        return False
    return all(bytes(snap.read(a + i) for i in range(len(v) // 2)) == bytes.fromhex(v) for a, v in SIGNATURE.items())


class Patch:
    name = "Into the Eagle's Nest 128K: the original game, no hooks"
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
        if not is_into_the_eagles_nest(snap):
            raise ValueError("not the Into the Eagle's Nest 128K dump this engine was built for")
        if any(snap.read(a) for a in range(TAIL_ADDR, TAIL_ADDR + TAIL_MAX)):
            raise ValueError('the tail area is not empty')
        printer = bytes(snap.read(PRINTER + i) for i in range(256))
        src = self.setup_call + 12
        code = (b'\x21' + zt.w16(src) + b'\x11' + zt.w16(PRINTER) + b'\x01' + zt.w16(256) + b'\xED\xB0' + b'\xC9')
        assert len(code) == 12
        self.stub_extra = code + printer


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p
