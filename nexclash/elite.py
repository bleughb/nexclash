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
             0x9215, 0x9261, 0xA84B, 0xB1B8, 0xB233, 0xB245, 0xB253, 0xD549,
             0x8C19, 0x8CBB, 0x8D1B, 0x8DB1, 0x90D0)        # planet / sun fills (buf_pcs.py, 2026-11-23)
WRITERS_B = (0x91CD, 0x91F1)
WRITERS_FF = (0x8B23, 0x8BC4, 0x8C22, 0x8CC4, 0x8D24, 0x8DBA, 0x8A78)
WRITERS_LDDR = (0x5E4B, 0x8A81)    # row fills (sun; 0x8A78 + LDDR)

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
    (0x759E, 'cdd086', 'h_sun', 0xCD),         # CALL 0x86D0: the filled body (sun) in its own colour
    (0x99D7, '21285a722372' '21485a722372', 'h_light', 0xCD),   # condition light attrs -> sprite 0 (+ 9 NOPs)
    (0x8BCD, '31b68f', 'pf_8BCD', 0xC3),       # LD SP,0x8FB6: the fills' stack blit
    (0x8CCD, '31b68f', 'pf_8CCD', 0xC3),
    (0x8DC3, '31b68f', 'pf_8DC3', 0xC3),
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
    for a in WRITERS_LDDR:
        out.append((a, b'\xED\xB8', b'\xEF\x00'))               # RST 28h, NOP
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
        self.rom_code, self.colour_info = _coloured_rom(bytes.fromhex(h['rom']), self.syms, _build_map())
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
                g = {'rst': set(WRITERS_A) | set(WRITERS_B) | set(WRITERS_FF) | set(WRITERS_LDDR),
                     'cat': {0x74EE, 0x74F1, 0x74F4, 0x74F7}, 'ship': {0x9E44, 0xF8D4},
                     'clear': {0x8080}, 'flip': {0x7FBE}, 'light': {0x99D7}, 'fill': {0x8BCD, 0x8CCD, 0x8DC3}}
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


COLOURS = 'docs/profiles/elite_colours.json'
RECOLOUR = {'game': 'elite', 'output': 'sprites', 'colours': COLOURS, 'clear': False,
            'note': 'One colour per ship model and per category (sun, planet, stars, messages, lasers, sights): '
                    'painting any pixel of a figure colours all of it. Colours from the 15 on the sheet.'}


def _build_map():
    from . import recolour as RC, coloursheet as cs
    p = RC.build_colours_path(os.path.join(_HERE, '..', COLOURS))
    return cs.load(p) if os.path.exists(p) else {}


def _coloured_rom(code, syms, cmap):
    """The assembled alt ROM code (from ROM_ORG) with cmap's colours -> (bytes, info)."""
    from . import elite_colours as EC
    img = bytearray(code)
    used, ignored = EC.apply(img, ROM_ORG, cmap, syms, EC.defaults_of(code, ROM_ORG, syms))
    return bytes(img), {'map entries used': used, 'map entries ignored': ignored}


def recolour(nex, cmap):
    """Rewrite the colour bytes of the alt ROM image (bank 12) only; refuses a .nex that is not this engine's build."""
    from . import recolour as RC, elite_colours as EC
    prof = load_profile()
    syms = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    code = bytes.fromhex(prof['hooks']['rom'])
    banks = RC.banks(nex)
    if 12 not in banks or 2 not in banks:
        raise ValueError('not an Elite build (no alt ROM bank 12)')
    if bytes(banks[2][0x9E44 - 0x8000:0x9E47 - 0x8000]) != bytes([0xC3]) + syms['h_ship'].to_bytes(2, 'little'):
        raise ValueError('Elite hook at 0x9E44 differs (another build or engine version)')
    b12 = bytearray(banks[12])
    off = ROM_ORG - 0x2000
    have = b12[off:off + len(code)]
    col = {a - ROM_ORG for addrs in EC.sites(syms).values() for a in addrs}
    if any(have[i] != code[i] for i in range(len(code)) if i not in col):
        raise ValueError('Elite alt ROM code differs from this engine version; rebuild first')
    img, info = _coloured_rom(code, syms, cmap)
    b12[off:off + len(code)] = img
    out, changed = RC.splice(nex, {12: bytes(b12)})
    info['banks changed'] = changed
    return out, info


def colour_identity(peek):
    from . import elite_colours as EC
    return EC.colour_identity(peek)


def sheets(source, out, name='ELITE', colours=None):
    """New colour sheets for the build's colours (never over an existing painting)."""
    from . import z80tonex as zt, elite_colours as EC
    png = os.path.join(out, name + '_PAINTING_SPRITES.png')
    if os.path.exists(png):
        raise FileExistsError('painting exists; keep it and use recolour: ' + png)
    snap = zt.Z80Snapshot(str(source))
    ram = bytes(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0]
    prof = load_profile()
    syms = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    code = bytes.fromhex(prof['hooks']['rom'])
    return EC.write_sheets(out, name, EC.defaults_of(code, ROM_ORG, syms), _build_map() if colours is None else colours,
                           EC.colour_identity(lambda a: ram[a]))


def build(z80, nex, quiet=False, control=False):
    from . import z80tonex
    return z80tonex.convert(z80, nex, patch=ElitePatch(control=control), quiet=quiet)


if __name__ == '__main__':
    import sys
    ctl = [a for a in sys.argv[3:] if a.startswith('--control')]
    build(sys.argv[1], sys.argv[2], control=(ctl[0].split('=', 1)[1] if '=' in ctl[0] else True) if ctl else False)
