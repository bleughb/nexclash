"""Elite (Firebird 1985, Russian 128K hack) engine 'elite'. Additive module: reachable only through is_elite().

Milestone M1 (stage 2's early integrated diagnostic, games/elite.md "## Build plan"): the viewport is mirrored onto a
double-buffered Layer 2 in colour - per ship model (the blueprint in IY) and per draw category (planet, stars,
messages, combat). The game's mono back buffer and its ULA copy are unchanged: every buffer write instruction becomes
a one-byte RST (10h / 18h / 20h) into alt ROM image 1 (asm/elite_hooks.asm) that does the write and mirrors the changed bits.

Game facts (probes in C:\\1NEXT\\elite_work\\probe, games/elite.md ## Probe / ## Build plan):
  buffer bank 0 0xC000-0xCFDF, screen layout, copied to 0x4020 (rows 8-127) by 0x7FBE; cleared by 0x8080 every pass;
  writers (all OR / XOR byte writes): LD (HL),A at WRITERS_A, LD (HL),B at WRITERS_B, LD (HL),0xFF at WRITERS_FF.
  Snapshot: 128K, 7FFD 0x30 (ROM 1, bank 0 at 0xC000, paging locked), IM 2 (I = 0xFD).
Start-up tail at 0x4800: ULA viewport rows, written (by the copy) before any read in every recording scanned.
"""
import json
import os

ROM_ORG = 0x3000
ALT_PAGE = 24               # 8K page: alt ROM image of 0x2000-0x3FFF (bank 12 lower half)
LOW_PAGE = 25               # 8K page: alt ROM image of 0x0000-0x1FFF (bank 12 upper half)
TAIL_ADDR = 0x4800

WRITERS_A = (0x5E44, 0x8B15, 0x8B1A, 0x8BB6, 0x8BBB, 0x9083, 0x9119, 0x911E, 0x917D, 0x9182, 0x91BD, 0x91E2,
             0x9215, 0x9261, 0xA84B, 0xB1B8, 0xB233, 0xB245, 0xB253, 0xD549)
WRITERS_B = (0x91CD, 0x91F1)
WRITERS_FF = (0x8B23, 0x8BC4)

# (site, original bytes, symbol, opcode of the new instruction)
HOOK_SITES = (
    (0x74EE, 'cc8475', 'h_planet', 0xCC),      # CALL Z,0x7584
    (0x74F1, 'cd9878', 'h_stars', 0xCD),
    (0x74F4, 'cd3cd0', 'h_msg', 0xCD),
    (0x74F7, 'cd809c', 'h_combat', 0xCD),
    (0x9E44, 'c3b4f8', 'h_ship', 0xC3),        # JP 0xF8B4 (the hack's ship draw wrapper)
    (0xF8D4, 'c3479e', 'h_shipend', 0xC3),     # its exit, JP 0x9E47
    (0x8080, 'f3011e00', 'h_clear', 0xC3),     # DI / LD BC,30 (JP h_clear + one dead byte)
    (0x7FBE, '2100c0', 'h_flip', 0xC3),        # LD HL,0xC000
)
IM2_I = 0x39                # alt ROM 0x3900-0x3A00 all 0x3A: vector 0x3A3A = h_isr for any bus byte (asm im2tab)
DATA_SITES = ((0xFF4C, '3efd', '3e39'),)      # the game's "IM 2 on": LD A,0xFD / LD I,A -> I = IM2_I

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'elite.json'), os.path.join(_HERE, 'elite.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('elite.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_elite(snap):
    """The Russian 128K hack: 128K snapshot with the ship draw wrapper's JP at 0x9E44 and its body at 0xF8B4."""
    if not snap.is128:
        return False
    b2, b0 = snap.banks[2], snap.banks[0]
    return bytes(b2[0x9E44 - 0x8000:0x9E47 - 0x8000]) == bytes.fromhex('c3b4f8') and \
        bytes(b0[0xF8B4 - 0xC000:0xF8BB - 0xC000]) == bytes.fromhex('f347f1f5329da7')


def sites(syms):
    """[(address, original bytes, new bytes)] for every patch site."""
    out = []
    for a in WRITERS_A:
        out.append((a, b'\x77', b'\xDF'))                       # RST 18h (not 08h: CSpect's esxDOS trap)
    for a in WRITERS_B:
        out.append((a, b'\x70', b'\xD7'))                       # RST 10h
    for a in WRITERS_FF:
        out.append((a, b'\x36\xFF', b'\xE7\x00'))               # RST 20h, NOP
    for a, old, sym, op in HOOK_SITES:
        old = bytes.fromhex(old)
        new = (bytes([op]) + syms[sym].to_bytes(2, 'little')).ljust(len(old), b'\x00')
        out.append((a, old, new))
    for a, old, new in DATA_SITES:
        out.append((a, bytes.fromhex(old), bytes.fromhex(new)))
    return out


def _bank_of(a):
    return {1: 5, 2: 2, 3: 0}[a >> 14]


class ElitePatch:
    name = 'Elite: viewport on Layer 2 in colour (M1 diagnostic; altrom RST mirror)'

    def __init__(self, prof=None, control=False):
        """control=True: negative control build - the IM 2 fix and the alt ROM only, no draw hooks."""
        from .build import rom48
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.rom_code = bytes.fromhex(h['rom'])
        self.low_code = bytes.fromhex(h['low'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = self.syms['setup']
        self.hook_page_data = b''
        self.uses_printer_buffer = True        # the game's own data lives at 0x5B00
        self.tail_addr = TAIL_ADDR
        self.max_tail = 256
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long (0x3D00-0x3DFF must stay free: BRIEFING A1)')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        rom = rom48()
        hi = bytearray(rom[0x2000:0x4000])
        hi[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        lo = bytearray(rom[0x0000:0x2000])
        lo[0x0010:0x0010 + len(self.low_code)] = self.low_code
        self.altrom_low = (LOW_PAGE, bytes(lo))
        self.page = bytes(hi)
        self.extra_banks = {12: self.page + bytes(lo), 13: bytes(16384)}   # 13: state page 26 (asm STATE_PG), zero
        self.sites = sites(self.syms)
        if control:
            keep = {a for a, _, _ in DATA_SITES}
            if isinstance(control, str):        # diagnostic subsets: 'rst', 'cat', 'ship', 'clear', 'flip' (+-joined)
                g = {'rst': set(WRITERS_A) | set(WRITERS_B) | set(WRITERS_FF),
                     'cat': {0x74EE, 0x74F1, 0x74F4, 0x74F7}, 'ship': {0x9E44, 0xF8D4},
                     'clear': {0x8080}, 'flip': {0x7FBE}}
                for k in control.split('+'):
                    if k.startswith('w'):       # w<hex>: one writer site
                        keep.add(int(k[1:], 16))
                    else:
                        keep |= g[k]
            self.sites = [s for s in self.sites if s[0] in keep]

    def check_sites(self, banks):
        for a, old, new in self.sites:
            b = banks[_bank_of(a)]
            cur = bytes(b[(a & 0x3FFF):(a & 0x3FFF) + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('Elite patch expects the 128K snapshot')
        if snap.port7ffd & 0x17 != 0x10:
            raise ValueError('snapshot must select ROM 1 (48K BASIC) and bank 0 at C000')
        self.check_sites(snap.banks)
        if snap.i != 0xFD or snap.im != 2:
            raise ValueError('snapshot I / IM: expected 0xFD / 2, got 0x%02X / %d' % (snap.i, snap.im))
        snap.i = IM2_I
        for a, old, new in self.sites:
            k = _bank_of(a)
            b = bytearray(snap.banks[k])
            b[(a & 0x3FFF):(a & 0x3FFF) + len(new)] = new
            snap.banks[k] = bytes(b)


def build(z80, nex, quiet=False, control=False):
    from . import z80tonex
    return z80tonex.convert(z80, nex, patch=ElitePatch(control=control), quiet=quiet)


if __name__ == '__main__':
    import sys
    ctl = [a for a in sys.argv[3:] if a.startswith('--control')]
    build(sys.argv[1], sys.argv[2], control=(ctl[0].split('=', 1)[1] if '=' in ctl[0] else True) if ctl else False)
