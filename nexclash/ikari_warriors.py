"""Ikari Warriors (Elite Systems 1988, 48K form): every figure plotted into the back buffer -> hardware
sprites; the blit shows a clean copy of the window. Facts: games/ikari_warriors.md, hooks:
asm/ikari_warriors_hooks.asm. Verification: two machines in lockstep, the original under the RZX and the
patched build in the Python simulator with the original's IN values; at each blit the whole of game
memory and all registers must match, and ULA + sprite layer must reproduce the original's screen."""
import collections
import hashlib
import json
import os

RECORD = 'ikari_warriors'
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'ikari_warriors_colours.json')
TAIL_ADDR = 0x5F00              # stale code copy, never read or written in any recording (scan; games file)
ALT_PAGE, HPG, CPG, SPG, STORE = 24, 26, 27, 28, 29
GP4, GP6 = 4, 0
ROM_LO = 0x2000
CMP = list(range(0, 15)) + list(range(16, 25)) + [26, 27, 28]
SITES_ORIG = {            # address: (original bytes, opcode, symbol)
    0xEBAA: ('cdc8f8', 'cd', 'e_pre'),
    0xEBC5: ('cdb262', 'cd', 'e_bl'),
    0xEBC8: ('cd1167', 'cd', 'e_post'),
    0x6D0E: ('ed73b0', 'c3', 'e_k1'),
    0x67C5: ('dd6607', 'c3', 'e_k2'),
    0x6980: ('011e0c', 'c3', 'e_k3'),
    0x6B8D: ('0ec0a7', 'c3', 'e_k4'),
    0xF845: ('c3edf7', 'c3', 'e_k5'),
    0xF76A: ('dd5607', 'c3', 'e_k6'),
    0x6879: ('011f04', 'c3', 'e_k8'),
    0xA984: ('cdb262', 'cd', 'e_ab'),
    0xA9B1: ('cdb262', 'cd', 'e_ab'),
    0xEB38: ('cdb262', 'cd', 'e_ab'),
    0xEB13: ('ed7321', 'c3', 'e_h1'),
    0xEC0C: ('2120f9', 'c3', 'e_h2'),
    0xF214: ('2126f2', 'c3', 'e_h3'),
    0xAB7C: ('fd2166', 'c3', 'e_h4'),
}
SIG = (0x6D0E, bytes.fromhex('ed73b0e46f2600'))
# H page
V_N, V_PREV, V_COL, V_STOLEN, ENT, LOG = 0x000, 0x001, 0x006, 0x008, 0x100, 0x300
LINES = 0x1400                  # the private line table in page H
WIN = (40, 215, 16, 183)        # the play window on screen, = the sprite clip window
KIND = {1: 'figure', 2: 'bullet', 3: 'xor figure', 4: 'dot', 5: 'pick-up', 6: 'heavy', 8: 'debris'}
XOR_KINDS = (3, 4, 8)
FIX = [0, 0, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0x00, 0x00, 0xB4, 0xFF]
I_DET = 8
EXTRA = (13, 14, 15)            # fill black, fill paper, outline: not in the original's picture
COLS = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
# colour store: graphics byte -> 4 nibble bytes, three regions, 3 pages (24,576 bytes)
REGIONS = [(0xB700, 0xC000, 0), (0xAD00, 0xB700, 9216), (0x9500, 0x9900, 19456)]
STORE_SIZE = 24576


def is_ikari_warriors(snap):
    ram = snap.ram(-1)
    if len(ram) != 0xC000:
        return False
    a, b = SIG
    return bytes(ram[a - 0x4000:a - 0x4000 + len(b)]) == b


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'ikari_warriors.json')


def load_profile():
    return json.load(open(_profile_path()))


def load_colours(path=COLOURS):
    from . import coloursheet
    return coloursheet.load(path) if os.path.exists(path) else {}


def load_colours_build():
    from . import recolour
    p = recolour.build_colours_path(COLOURS)
    return load_colours(p) if p and os.path.exists(p) else {}


def store_offset(a):
    for lo, hi, off in REGIONS:
        if lo <= a < hi:
            return off + (a - lo) * 4
    return None


def store_pages(colours):
    """The colour map -> the store image (24,576 bytes)."""
    out = bytearray(STORE_SIZE)
    for key, ent in (colours or {}).items():
        o = store_offset(int(key, 16))
        if o is None:
            continue
        nib = ent[2]
        for k in range(4):
            out[o + k] = (nib[2 * k] & 15) << 4 | (nib[2 * k + 1] & 15)
    return bytes(out)


class IkariPatch:
    name = 'Ikari Warriors figures -> hardware sprites (alt ROM image 1, page 26 at slot 4, blit from a clean copy in page 27)'

    def __init__(self, prof=None, colours=None, rom_code=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.colours = dict(colours) if colours is not None else load_colours_build()
        self.regblock = 0x2400 + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hooks reach 0x3D00')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_LO, self.regblock + 20)
        pg = bytearray(8192)
        pg[0x400:0x400 + len(self.rom_code)] = self.rom_code
        self.page = pg
        self.hpage = bytearray(8192)
        self.hpage[V_COL] = 1 if self.colours else 0
        for i in range(168):            # the blit's line table, private: the game's is on KSTATE
            y = 16 + i
            a = 0x4005 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
            self.hpage[LINES + 2 * i], self.hpage[LINES + 2 * i + 1] = a & 255, a >> 8
        self.store = store_pages(self.colours)
        self.sites = [(a, bytes.fromhex(v[0]), bytes.fromhex(v[1]) + self.syms[v[2]].to_bytes(2, 'little'))
                      for a, v in SITES_ORIG.items()]
        self._banks()

    def _banks(self):
        self.extra_banks = {12: bytes(self.page) + bytes(8192),
                            13: bytes(self.hpage) + bytes(8192),           # H, C
                            14: bytes(8192) + self.store[:8192],           # S, store 0
                            15: self.store[8192:]}

    def apply(self, snap):
        from . import z80tonex as zt
        if snap.is128:
            raise ValueError('expects the 48K snapshot')
        ram = {5: bytearray(snap.banks[5]), 2: bytearray(snap.banks[2]), 0: bytearray(snap.banks[0])}

        def where(a):
            return (5, a - 0x4000) if a < 0x8000 else ((2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000))
        for a, old, new in self.sites:
            for k in range(len(old)):
                b, o = where(a + k)
                if ram[b][o] != old[k]:
                    raise ValueError('unexpected code at 0x%04X' % (a + k))
            for k, v in enumerate(new):
                b, o = where(a + k)
                ram[b][o] = v
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        self.page[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self._banks()
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[5]), bytes(ram[2]), bytes(ram[0])


# ---------------------------------------------------------------------------------------------
# Enhanced colours, a set of the .nxc, off by default: players stand apart from enemies. The base build stays byte for byte as
# it is: this build differs in the palette (indexes 3, 5, 6, 10), the colour store and a few hook bytes, calling a little code
# after the hooks. The game's own code and memory are as in every build.
# Players share graphics with enemies (0-15 player 1, 24-39 player 2, both used by enemies too; 16-23, the inverted wading
# frames drawn AND-only, and 40-48 by everybody), so K1's colour base is chosen by object, not frame:
#   enemy                                   0xB700 + 36 * frame   (the game's own graphics: the default route's keys)
#   player (flag 0x80)                      0xAD00 + 36 * frame   (K5's and K6's keys: those two stay unpainted here)
#   player 2 (object 0xE5A7), AND-only 16-23  0x92C0 + 36 * frame   (0x9500-0x961F)
#   any figure, 16-23 drawn the normal way  0x9524 + 36 * frame   (0x9764-0x9883): the AND-only store leaves lines 13-17, the
#                                                                  ripple, unpainted, while the normal way draws all 18
# Player 2 gets bit 1 of the cache key, or his frames would reuse player 1's patterns. The AND-only rotation codes
# (0x6D99 0x6E80 0x6E75 0x6E8D, table 0x6E30) map to their pixel shifts: the default build never keys AND-only images.
# Only the body is painted (work/enh2/paint3.py): the mask's clear pixels beyond the drawing are the game's paper border and
# keep the paper, exactly as in the default build (the 17:00 build cleared them and painted the blob: the owner's leak).
# Enemies carry no skin. Frames 49-57 (the tank's gun, the ripple) keep the default.
ENH_FIX = bytes([0x00, 0x49, 0xA0, 0xF6, 0x6E, 0x16, 0xB4, 0xB6, 0x0F, 0xE0])  # palette indexes 2-11
I_BLACK, I_TROUSERS, I_SKIN, I_UNIFORM, I_BLUE, I_RED = 2, 3, 5, 6, 10, 11
I_OUT_IDX = 15
P2_IXL = 0xA7
B_ENEMY, B_PLAYER, B_P2WADE, B_NORMWADE = 0xB700, 0xAD00, 0x92C0, 0x9524
SHIFT_AND = {0x99: 0, 0x80: 2, 0x75: 4, 0x8D: 6}


def _asm(org, items):
    """A tiny two-pass assembler: items are bytes, a label 'name:', or ('jr', cond_opcode, label)."""
    lab, out = {}, None
    for _ in range(2):
        out, a = bytearray(), org
        for it in items:
            if isinstance(it, str):
                lab[it[:-1]] = a
            elif isinstance(it, tuple):
                d = lab.get(it[2], a + 2) - (a + 2)
                if not -128 <= d <= 127:
                    raise ValueError('jr range')
                out += bytes([it[1], d & 255])
                a += 2
            else:
                out += bytes(it)
                a += len(it)
    return bytes(out)


O3_OUTLINE = 0x2EB5             # uploadn .o3: LD (HL),I_OUT, the only outline store (K1's upload; no other kind outlines)


def enhanced_patch(colours, prof=None, outline=False, border='clear'):
    """outline=False: the owner's verdict on 9b8d9497 (2026-11-03), no white ring in Enhanced: .o3 stores index 0 (transparent)
    instead of 15, one byte; a palette entry cannot do it, sprite transparency is by index (NR 0x4B = 0), not by colour.
    border='clear' (owner: "none of the yellow edge outside of the original character black outline and no white outline"):
    the mask's clear pixels left unpainted (its paper border beyond the black edge) are transparent on every K1 frame but the
    ripple (57), V_DET 0; the fill then gives the paper only to see-through pixels enclosed inside the figure (the gun's).
    'paper' keeps the border in the cell's paper as the default build does."""
    prof = prof or load_profile()
    y = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    base = bytearray(bytes.fromhex(prof['hooks']['rom']))
    vk = 0x8010
    w = lambda v: [v & 255, v >> 8]
    JRNZ, JRZ, JRNC, JRC, JR = 0x20, 0x28, 0x30, 0x38, 0x18
    org = 0x2400 + len(base)
    src = [
        'ext_b:', [0x11] + w(B_ENEMY),                  # ld de,B_ENEMY          (keeps HL = 36 * frame)
        [0x3A] + w(vk), [0xD6, 16, 0xFE, 8],           # ld a,(V_KEY): sub 16: cp 8
        ('jr', JRNC, 'nw'),
        [0xDD, 0xCB, 0x02, 0x46],                       # bit 0,(ix+2): AND-only?
        ('jr', JRNZ, 'and'),
        [0x11] + w(B_NORMWADE), [0xC9],                 # 16-23 drawn the normal way
        'and:', [0xDD, 0xCB, 0x02, 0x7E, 0xC8],         # bit 7,(ix+2): ret z
        [0x11] + w(B_PLAYER),
        [0xDD, 0x7D, 0xFE, P2_IXL, 0xC0],               # ld a,ixl: cp P2: ret nz
        [0x11] + w(B_P2WADE), [0xC9],
        'nw:', [0xDD, 0xCB, 0x02, 0x7E, 0xC8],          # bit 7,(ix+2): ret z
        [0x11] + w(B_PLAYER), [0xC9],
        'ext_key:', [0xDD, 0x7D, 0xFE, P2_IXL],         # ld a,ixl: cp P2
        [0xDD, 0x7E, 0x02],                             # ld a,(ix+2)
        ('jr', JRNZ, 'kn'),
        [0xE6, 0x89, 0xF6, 0x02], ('jr', JR, 'ks'),     # and 0x89: or 2
        'kn:', [0xE6, 0x89],
        'ks:', [0x32] + w(vk + 1), [0xC9],              # ld (V_KEY+1),a
        'ext_rot:', [0x3A] + w(vk + 2),                 # ld a,(V_KEY+2): AND-only codes -> the normal code of that shift
        [0xFE, 0x99], ('jr', JRNZ, 'r1'), [0x3E, 0x60, 0xC9],
        'r1:', [0xFE, 0x80], ('jr', JRNZ, 'r2'), [0x3E, 0x56, 0xC9],
        'r2:', [0xFE, 0x75, 0xC0, 0x3E, 0x4C, 0xC9],
    ]
    if border == 'clear':
        src += [
            'ext_det:', [0x21] + w(0x8034), [0x36, 0x01, 0xF5],  # ld hl,V_DET: ld (hl),1: push af
            [0x3A] + w(vk), [0xFE, 57],                 # the ripple (57) keeps the default
            ('jr', JRZ, 'dk'), [0x36, 0x00],            # every other frame: a hole left unpainted is clear (the border)
            'dk:', [0xF1, 0xC9],
        ]
    code = _asm(org, src)
    lab = {}
    a = org
    for it in src:                                      # label addresses
        if isinstance(it, str):
            lab[it[:-1]] = a
        else:
            a += 2 if isinstance(it, tuple) else len(it)

    def put(a, vals, old):
        o = a - 0x2400
        if bytes(base[o:o + len(old)]) != bytes(old):
            raise ValueError('hook bytes at 0x%04X' % a)
        base[o:o + len(vals)] = bytes(vals)
    call = lambda l: [0xCD] + w(lab[l])
    put(y['e_k1.c_b'], call('ext_b'), [0x11, 0x00, 0xB7])
    put(y['e_k1.c_key'], call('ext_key') + [0] * 5, [0xDD, 0x7E, 0x02, 0xE6, 0x89, 0x32, 0x11, 0x80])
    put(y['e_k1.c_ck'], [0x3E, 0x01, 0x00, 0x00], [0xE6, 0x01, 0xEE, 0x01])   # AND-only images take keys too
    put(y['e_k1.c_rot'], call('ext_rot'), [0x3A, 0x12, 0x80])
    if border == 'clear':
        put(y['e_k1.c_det'], call('ext_det') + [0, 0], [0x21, 0x34, 0x80, 0x36, 0x01])
    elif border != 'paper':
        raise ValueError('border')
    if not outline:
        put(O3_OUTLINE, [0x36, 0x00], [0x36, I_OUT_IDX])
    put(y['e_k5.c5'] + 1, [0], [5])
    put(y['e_k6.c6'] + 1, [0], [6])
    p = IkariPatch(prof, colours=colours, rom_code=bytes(base) + code)
    if p.stub_extra[-10:] != FIX_BYTES:
        raise ValueError('setup palette')
    p.stub_extra = p.stub_extra[:-10] + ENH_FIX
    p.name = IkariPatch.name + ', Enhanced colours'
    return p


FIX_BYTES = bytes([0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0])


# ---------------------------------------------------------------------------------------------
# Fifth pass, the default sprite build too (owner, 2026-11-03, Ikari only: "same on the non enhanced version, also the non
# enhanced version still has the outline"): no white outline, nothing outside the figure's black edge, the seams closed.
#   - outline: .o3 stores index 0, not 15 (one byte)
#   - edge: V_DET 0 on every K1 frame but the ripple (57): a mask hole is transparent; the hook's own fill then gives the paper
#     back to the pixels enclosed, in line and column, by the figure's opaque pixels: the body, as before
#   - seams (channels of at most 2 pixels between parts, open at one end; work/enh2/seams.py): black, through the colour route,
#     table docs/profiles/ikari_warriors_edges.json (0xB700 + 36 f, the default route's keys; AND-only images take no keys)
#   - K5 and K6 take no colour keys, so pick-ups and heavy objects stay as before
EDGES = os.path.join(_HERE, '..', 'docs', 'profiles', 'ikari_warriors_edges.json')
ENHANCED = os.path.join(_HERE, '..', 'docs', 'profiles', 'ikari_warriors_enhanced.json')   # sixth pass (runs/ikari_warriors work/enh2/colours6.json)


def edge_patch(colours=None, prof=None, outline=False, border='clear'):
    prof = prof or load_profile()
    y = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    base = bytearray(bytes.fromhex(prof['hooks']['rom']))
    w = lambda v: [v & 255, v >> 8]
    org = 0x2400 + len(base)
    src = []
    if border == 'clear':
        src = ['ext_det:', [0x21] + w(0x8034), [0x36, 0x01, 0xF5],   # ld hl,V_DET: ld (hl),1: push af
               [0x3A] + w(0x8010), [0xFE, 57], ('jr', 0x28, 'dk'), [0x36, 0x00],
               'dk:', [0xF1, 0xC9]]
    elif border != 'paper':
        raise ValueError('border')
    code = _asm(org, src)
    lab, a = {}, org
    for it in src:
        if isinstance(it, str):
            lab[it[:-1]] = a
        else:
            a += 2 if isinstance(it, tuple) else len(it)

    def put(a, vals, old):
        o = a - 0x2400
        if bytes(base[o:o + len(old)]) != bytes(old):
            raise ValueError('hook bytes at 0x%04X' % a)
        base[o:o + len(vals)] = bytes(vals)
    if border == 'clear':
        put(y['e_k1.c_det'], [0xCD] + w(lab['ext_det']) + [0, 0], [0x21, 0x34, 0x80, 0x36, 0x01])
    if not outline:
        put(O3_OUTLINE, [0x36, 0x00], [0x36, I_OUT_IDX])
    put(y['e_k5.c5'] + 1, [0], [5])
    put(y['e_k6.c6'] + 1, [0], [6])
    if colours is None:
        colours = json.load(open(EDGES))
    p = IkariPatch(prof, colours=colours, rom_code=bytes(base) + code)
    p.name = IkariPatch.name + ', figure edges'
    return p


def static_check(code, org):
    from .simrun import disasm
    mem = [0] * 65536
    mem[org:org + len(code)] = list(code)
    bad, a = [], org
    while a < org + len(code):
        t, n = disasm(mem, a)
        u = t.upper()
        if u in ('DI', 'EI', 'HALT') or u.startswith('IM ') or u.startswith('LD I,'):
            bad.append((hex(a), t))
        a += n
    if org + len(code) > 0x3D00:
        bad.append('code reaches 0x3D00')
    return bad


def build(z80, out, name, say=print):
    from . import z80tonex as zt, nextboot
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, tail_req=TAIL_ADDR, quiet=True)
    bad = nextboot.check(plain, z80, tail=(TAIL_ADDR, TAIL_ADDR + 96))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    patch = edge_patch()           # fifth pass: no outline, no paper edge, seams closed (IkariPatch(colours={}) = d6a6fce2)
    sc = static_check(patch.rom_code, 0x2400)
    say('Static    : hook code %d bytes at 0x2400-0x%04X: %s' % (len(patch.rom_code), patch.regblock + 20, 'PASS' if not sc else 'FAIL %s' % sc[:4]))
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = nextboot.check(spr, z80, edge_patch(), tail=(TAIL_ADDR, TAIL_ADDR + 96))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300]))
    say('Colours   : %s' % ('%d colour-map entries' % len(patch.colours) if patch.colours else "no colour map: black ink, holes in the paper under the figure's centre"))
    return (not bad and not bad2 and not sc), (plain, spr), patch


def build_enhanced(z80, out, name, say=print):
    """The Enhanced colour set (off by default; owner's sixth pass, 2026-11-03): enhanced_patch over the
    table docs/profiles/ikari_warriors_enhanced.json. -> (ok, path, patch)."""
    from . import z80tonex as zt, nextboot
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    cols = json.load(open(ENHANCED))
    patch = enhanced_patch(cols)
    sc = static_check(patch.rom_code, 0x2400)
    enh = os.path.join(out, name + '_enhanced.nex')
    zt.convert(z80, enh, quiet=True, patch=patch)
    bad = nextboot.check(enh, z80, enhanced_patch(cols), tail=(TAIL_ADDR, TAIL_ADDR + 96))
    say('Enhanced  : %s  %s  static %s, boot %s' % (os.path.basename(enh), md5(enh), 'PASS' if not sc else 'FAIL %s' % sc[:4],
                                                  'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    return not bad and not sc, enh, patch


# ---------------------------------------------------------------------------------------------
# The patched machine
# ---------------------------------------------------------------------------------------------
class NS:
    SLOT = {0x54: (0x8000, 4), 0x56: (0xC000, 6)}

    def __init__(self, patch, mem):
        self.mem = mem
        self.nr = {0x54: GP4, 0x56: GP6, 0x07: 0, 0x15: 1}
        self.pages = {HPG: bytearray(patch.hpage), CPG: bytearray(8192), SPG: bytearray(8192)}
        for n in range(3):
            self.pages[STORE + n] = bytearray(patch.store[8192 * n:8192 * (n + 1)])
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.ins = collections.deque()
        self.errs = []
        self.written = bytearray(128)

    def read(self, port):
        if not self.ins:
            self.errs.append('IN beyond the recording at port 0x%04X' % port)
            return 0xFF
        return self.ins.popleft()

    def nextreg(self, reg, val):
        if reg in self.SLOT:
            base, _ = self.SLOT[reg]
            cur = self.nr[reg]
            if cur != val:
                m = self.mem
                self.pages[cur] = bytearray(m[base:base + 8192])
                pg = self.pages.get(val)
                if pg is None:
                    self.errs.append('page %d not modelled' % val)
                    pg = bytearray(8192)
                m[base:base + 8192] = pg
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def out(self, port, val):
        if port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
        elif port & 0xFF == 0xFE:
            pass
        elif port & 0xFF == 0xFD or port & 0xC002 == 0x8000:
            pass
        else:
            self.errs.append('OUT port 0x%04X' % port)

    def H(self, off):
        p = self.pages[HPG] if self.nr[0x54] != HPG else None
        return (p[off] if p is not None else self.mem[0x8000 + off])

    def sprites(self):
        """[(x, y, pattern number, palette bank)] of visible sprites, in slot order."""
        out = []
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            x = a0 + (a2 & 1) * 256 - 32
            y = a1 + (a4 & 1) * 256 - 32
            out.append((x, y, (a3 & 0x3F) * 2 + (1 if a4 & 0x40 else 0), a2 >> 4, i))
        return out


class Tracer:
    def __init__(self, ns):
        self.ns = ns

    def read_port(self, regs, port):
        return self.ns.read(port)

    def write_port(self, regs, port, value, *x):
        self.ns.out(port, value)


def make_machine(patch, om, regs):
    """The patched machine from the original's memory and registers."""
    from skoolkit.simulator import Simulator
    from . import z80n
    mem = bytearray(om)
    lo, hi = patch.altrom
    mem[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
    for a, old, new in patch.sites:
        if bytes(mem[a:a + len(old)]) != old:
            raise ValueError('site 0x%04X' % a)
        mem[a:a + len(new)] = new
    ns = NS(patch, mem)
    sim = Simulator(mem, {})
    sim.registers[:] = list(regs)
    z80n.install(sim, ns.nextreg)
    sim.set_tracer(Tracer(ns))
    return sim, ns, mem


def run_to(sim, stop, hooks=None, counts=None, limit=8000000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    if R[24] == stop:           # leave the stop first: a sync site is reached again a whole frame on
        ops[mem[stop]]()
    if hooks:
        while True:
            pc = R[24]
            if pc == stop:
                return True
            if pc in hooks:
                counts[hooks[pc]] += 1
            ops[mem[pc]]()
            n += 1
            if n > limit:
                return False
    while R[24] != stop:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


def screen_bit(scr, x, y):
    a = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
    return (scr[a] >> (7 - (x & 7))) & 1


TORN_KINDS = (2, 3, 5, 6, 8)    # plotters that step two lines at a time and test the carry only on the second


def torn_offsets(low, n):
    """The original's line walk for those plotters: `low` = low address byte of the first byte; the step
    from an even to an odd line adds 32 to L with no carry into H, so across a 256-byte boundary the
    original draws that part 8 lines higher. -> [line offset per image line]. The sprite is whole."""
    off, out = 0, []
    for i in range(n):
        out.append(off)
        s = low + 32
        off += 1 - 8 if (i & 1 == 0 and s > 255) else 1
        low = s & 255
    return out


def compose(ns, scr, om=None):
    """ULA pixels of the window + the sprite layer -> {(x,y): bit} for pixels the sprites touch; hole = 0,
    ink = 1, an XOR kind inverts. om (the memory, for the buffer origin): lines placed as the original's
    plotters place them, so a torn plot compares true. Returns (bits, sprite pixels, kinds, torn lines)."""
    bits = {}
    nspx = 0
    torn = 0
    kinds = collections.Counter()
    org = None
    if om is not None:
        org = ((om[0xE460] | om[0xE461] << 8) + 0x700) & 0xFF
    for x0, y0, pn, bank, slot in ns.sprites():
        e = pn >> 2
        kind = ns.H(ENT + e * 16 + 7)
        fol = kind == 1 and ns.H(ENT + e * 16 + 1) & 1  # the AND-only variant: its cleared pixels are drawn in I_DET
        base = pn * 128
        kinds[kind] += 1
        offs = None
        tr = 16 if pn & 2 else 0
        if org is not None and kind in TORN_KINDS:
            xs = x0 - (16 if pn & 1 else 0)
            low = (org + (y0 - tr - 16) * 32 + (xs >> 3)) & 255
            offs = torn_offsets(low, 32)
            torn += sum(1 for j in range(16) if offs[tr + j] != tr + j)
        for j in range(16):
            y = y0 + j if offs is None else y0 - tr + offs[tr + j]
            if not WIN[2] <= y <= WIN[3]:
                continue
            for k in range(16):
                b = ns.pat[base + j * 8 + k // 2]
                c = (b >> 4) if k % 2 == 0 else (b & 15)
                if not c or c in EXTRA:
                    continue
                x = x0 + k
                if not WIN[0] <= x <= WIN[1]:
                    continue
                nspx += 1
                if kind in XOR_KINDS:
                    v = bits.get((x, y))
                    if v is None:
                        v = screen_bit(scr, x, y)
                    bits[(x, y)] = v ^ 1
                else:
                    bits[(x, y)] = 0 if c == 1 or (c == I_DET and fol) else 1
    return bits, nspx, kinds, torn


def verify(patch, rzx_path, stop=None, collect=0, progress=None, capture=None, picture=True, compose_fn=None):
    import skoolkit.rzxplay as rp
    from .rzx import trace
    c = collections.Counter()
    ex = collections.OrderedDict()
    states = []
    inlog = []
    st = {}
    hooks = {patch.syms[v[2]]: v[2] for v in SITES_ORIG.values()}
    hooks[patch.syms['k1back']] = 'k1 capture pass'
    hooks[patch.syms['upload']] = 'upload'
    site_ranges = [(a, len(n)) for a, o, n in patch.sites]

    def fail(key, info):
        c[key + '!'] += 1
        ex.setdefault(key + '!', [])
        if len(ex[key + '!']) < 5:
            ex[key + '!'].append(info)

    def compare(frame, O):
        sim, ns, mem = st['sim'], st['ns'], st['mem']
        om = bytes(O.memory[0:0x10000])
        pm = bytes(mem)
        if om[0x5B00:] != pm[0x5B00:]:
            diffs = [a for a in range(0x5B00, 0x10000) if om[a] != pm[a]]
            sk = {a + k for a, n in site_ranges for k in range(n)}
            diffs = [a for a in diffs if a not in sk]
            if diffs:
                fail('memory', (c['commits'], [hex(a) for a in diffs[:12]], len(diffs)))
        for a, o, n in patch.sites:
            if om[a:a + len(o)] != o:
                fail('site rewritten', hex(a))
        ore = list(O.registers)
        for i in CMP:
            if ore[i] != sim.registers[i]:
                # the blit's last LDI: flags 3 and 5 come from the byte copied, here clean scenery,
                # there a figure. Undocumented bits, overwritten by the next flag-setting instruction
                if i == 1 and (ore[i] ^ sim.registers[i]) & 0xD7 == 0:
                    c['F bits 3,5 after the blit (LDI of a figure byte)'] += 1
                    sim.registers[i] = ore[i]
                    continue
                fail('register', (c['commits'], i, ore[i], sim.registers[i]))
        if ns.nr[0x54] != GP4 or ns.nr[0x56] != GP6 or ns.nr[7] != 0:
            fail('paging', dict(ns.nr))
        if ns.ins:
            fail('IN not consumed', len(ns.ins))
            ns.ins.clear()
        for e in ns.errs:
            fail('machine', e)
        ns.errs.clear()
        if not picture:
            if capture is not None:
                capture(ns, om, pm)
            return
        # the picture
        o_scr, p_scr = om[0x4000:0x5B00], pm[0x4000:0x5B00]
        want = bytearray(o_scr[6144:])
        base = (om[0xE462] | om[0xE463] << 8) + 0xE5
        for r in range(21):
            for k in range(22):
                want[(r + 2) * 32 + 5 + k] = st['attr'][(base + r * 32 + k) & 0x3FF]
        if bytes(want) != p_scr[6144:]:
            fail('attributes', c['commits'])
        c['attribute cells the debris no longer toggles'] += sum(a != b for a, b in zip(o_scr[6144:], p_scr[6144:]))
        bits, nspx, kinds, torn = (compose_fn or compose)(ns, p_scr, pm)
        c['sprite pixels compared'] += nspx
        c['torn image lines (original glitch, sprite whole)'] += torn
        c['max sprites'] = max(c['max sprites'], sum(kinds.values()))
        for k, v in kinds.items():
            c['sprites ' + KIND.get(k, str(k))] += v
        bad = 0
        diffpix = 0
        # lines the original never refreshes: the ROM's keyboard scan has damaged its table (attract before play).
        # The patched machine must show them fresh, the clean copy's bytes.
        stale = set()
        for i in range(168):
            y = 16 + i
            if om[0x5B00 + 2 * i] | om[0x5B01 + 2 * i] << 8 != 0x4005 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2):
                stale.add(y)
                src = ((om[0xE460] | om[0xE461] << 8) + 0x705 - 0xC000 + i * 32) & 0x1FFF
                row = bytes(ns.pages[CPG][(src + k) & 0x1FFF] for k in range(22))
                b0 = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
                c['lines the original leaves stale, shown fresh'] += 1
                if bytes(p_scr[b0 + 5:b0 + 27]) != row:
                    fail('stale line not fresh', (c['commits'], y))
        for y in range(192):
            base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
            if o_scr[base:base + 32] != p_scr[base:base + 32] or WIN[2] <= y <= WIN[3]:
                inw = WIN[2] <= y <= WIN[3]
                for x in range(256) if not inw else range(0, 256):
                    b = (o_scr[base + (x >> 3)] >> (7 - (x & 7))) & 1
                    if inw and WIN[0] <= x <= WIN[1]:
                        if y in stale:
                            continue
                        v = bits.get((x, y))
                        if v is None:
                            v = (p_scr[base + (x >> 3)] >> (7 - (x & 7))) & 1
                        if v != b:
                            bad += 1
                    else:
                        if b != (p_scr[base + (x >> 3)] >> (7 - (x & 7))) & 1:
                            diffpix += 1
        if bad:
            fail('picture', (c['commits'], frame, bad))
            c['picture pixels wrong'] += bad
        if diffpix:
            fail('outside the window', (c['commits'], diffpix))
        c['stolen'] = ns.H(V_STOLEN)
        c['max log'] = max(c['max log'], ns.H(V_N))
        c['patched T per sync max'] = max(c['patched T per sync max'], 0)
        if capture is not None:
            capture(ns, om, pm)

    def on_pc(pc, O):
        if pc == 0xEBAA and 'sim' not in st:
            sim, ns, mem = make_machine(patch, bytes(O.memory[0:0x10000]), list(O.registers))
            st.update(sim=sim, ns=ns, mem=mem)
            inlog.clear()
            st['attr'] = bytes(O.memory[0xE000:0xE400])
            return
        if pc == 0xEBAA:
            st['attr'] = bytes(O.memory[0xE000:0xE400])
            return
        if pc == 0x6711 and 'sim' in st:
            sim, ns = st['sim'], st['ns']
            ns.ins.extend(inlog)
            inlog.clear()
            t0 = sim.registers[25]
            if not run_to(sim, 0x6711, hooks, c):
                fail('run', 'no sync')
                raise SystemExit('lost sync')
            c['commits'] += 1
            c['patched T'] += sim.registers[25] - t0
            compare(c['commits'], O)
            if progress and c['commits'] % 200 == 0:
                progress(c, ex)
            if collect and len(states) < collect and c['commits'] % 300 == 50:
                states.append((bytes(st['mem']), list(sim.registers)))

    old = rp.RZXTracer.read_port

    def rp_read(self, registers, port):
        v = old(self, registers, port)
        inlog.append(v)
        return v
    rp.RZXTracer.read_port = rp_read
    try:
        f, err = trace(rzx_path, {0xEBAA, 0x6711}, on_pc, stop=stop)
    finally:
        rp.RZXTracer.read_port = old
    c['frames'] = f
    if err:
        fail('replay', err)
    if 'sim' in st:
        ex['_ns'] = st['ns']
        # the way out of play: no sync after it, so run on with what is left of the recording's inputs
        sim, ns = st['sim'], st['ns']
        ns.ins.extend(inlog)
        ns.ins.extend([0xFF] * 200000)
        R, ops, mem = sim.registers, sim.opcodes, sim.memory
        n = 0
        out = {0xEC0F: 'game over', 0xF217: 'level end', 0xAB80: 'back from play'}
        while R[24] not in out and n < 3000000:
            ops[mem[R[24]]]()
            n += 1
        if R[24] in out:
            c['left play: ' + out[R[24]]] += 1
            left = ns.sprites()
            c['sprites still on after leaving play'] = len(left)
            if left:
                fail('sprites left on', len(left))
            if R[24] == 0xEC0F:          # on, through the game's wait, to the way back
                n = 0
                while R[24] != 0xAB80 and n < 8000000:
                    ops[mem[R[24]]]()
                    n += 1
                if R[24] == 0xAB80:
                    c['left play: back from play'] += 1
                    if ns.sprites():
                        fail('sprites left on', 'back from play')
        ns.errs.clear()
    return c, ex, states


def negative_patches():
    """(name, patch): broken builds the verify must catch."""
    prof = load_profile()
    y = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    code = bytes.fromhex(prof['hooks']['rom'])

    def mod(*edits):
        b = bytearray(code)
        for a, vals in edits:
            for k, v in enumerate(vals):
                b[a - 0x2400 + k] = v
        return IkariPatch(rom_code=bytes(b), colours={})
    return [
        ('blit from the figures', mod((y['neg_blit'], [0, 0, 0, 0]))),
        ('clean copy short by 68 lines', mod((y['neg_copy'] + 10, [100]))),
        ('K1 registers off by one', mod((y['neg_k1regs'] + 1, [(0x8700 - 16) & 255]))),
        ('dots dropped', mod((y['e_k4.neg'], [0x18]))),
        ('sprites one line low', mod((y['neg_pos'] - 1, [49]))),
        ('debris attributes left on the ULA', mod((y['neg_att'], [0, 0, 0]))),
        ('line table fix off (needs a recording through attract)', mod((y['neg_lines'], [0, 0, 0]))),
    ]


# ---------------------------------------------------------------------------------------------
# Colour route: keys = the graphics byte a pixel comes from. Figures (K1, not wading, not the AND-only
# variant), pick-ups, heavy objects. Bullets, XOR figures, dots and debris keep the default.
# ---------------------------------------------------------------------------------------------
NOTE = ('Ikari Warriors figure colours: key = hex address of a graphics byte -> [the byte (check), 1, 8 nibbles]; nibble 0 = default '
        '(ink black, a clear or hole pixel as drawn); 1 = the paper under the figure, 2-15 = fixed palette')
SHIFT = {0x60: 0, 0x56: 2, 0x4C: 4, 0x62: 6}
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/ikari_warriors_colours.json', 'clear': False, 'note': NOTE}
COLOUR_BANKS = (13, 14, 15)
GROUPS = ('Figures', 'Pick-ups', 'Heavy')


def image_map(key):
    """Entry key -> (kind, graphics base, rotation pixels, bytes per line, lines), or None: no colour keys."""
    kind = key[7]
    if kind == 1 and not key[1] & 1 and not key[6]:
        return kind, 0xB700 + 36 * key[0], SHIFT.get(key[2], 0), 2, 18
    if kind == 5:
        return kind, key[0] | key[1] << 8, 0, 2, 14
    if kind == 6:
        return kind, key[0] | key[1] << 8, 0, 4, 24
    return None


def canvas_pixel(pat, e, x, y, kind=0):
    """The pattern nibble at canvas pixel (x, y) of entry e. K1 has a margin of one pixel."""
    if kind == 1:
        x, y = x + 1, y + 1
    if x >= 32 or y >= 32:
        return 0
    b = pat[(e * 4 + (1 if x >= 16 else 0) + (2 if y >= 16 else 0)) * 128 + (y & 15) * 8 + (x & 15) // 2]
    return (b >> 4) if not x & 1 else (b & 15)


def sheet_part(pat, get, key, e, x, y, frame, idx):
    im = image_map(key)
    if im is None:
        return None
    kind, base, s, w, h = im
    pixels, entries = [], {}
    for line in range(h):
        for gb in range(w):
            a = base + line * w + gb
            if store_offset(a) is None:
                return None
            k = '%04X' % a
            entries.setdefault(k, [get(a), 1])
            for b in range(8):
                n = canvas_pixel(pat, e, s + gb * 8 + b, line, kind)
                code = 1 if n == 2 else (2 if n == 1 else 0)
                pixels.append((gb * 8 + b, line, k, b, code, n if code else 0))
    return dict(id=(kind,) + tuple(key[:7]), size=h, w=w * 8, h=h, x=x + s, y=y, mir=0,
                group=GROUPS[{1: 0, 5: 1, 6: 2}[kind]], fam=(frame, idx), role=None, pixels=pixels, entries=entries)


def capture_parts(rzx_paths, stop=None, patch=None):
    """Replay: every figure, frame by frame -> (Collector, memory of the game, ink-against-graphics check)."""
    from . import coloursheet as cs
    col = cs.Collector(family=lambda p: p['fam'])
    st = {'f': 0, 'mem': None, 'bad': 0, 'ok': 0}
    seen = {}

    def cap(ns, om, pm):
        st['f'] += 1
        h = ns.pages[HPG]
        get = lambda a: om[a]
        if st['mem'] is None:
            st['mem'] = om
        org = ((om[0xE460] | om[0xE461] << 8) + 0x700) & 0x1FFF
        parts = []
        for i in range(h[V_N]):
            e = h[LOG + 3 * i]
            key = bytes(h[ENT + e * 16:ENT + e * 16 + 8])
            d = (h[LOG + 1 + 3 * i] | h[LOG + 2 + 3 * i] << 8) & 0x1FFF
            off = (d - org) & 0x1FFF
            x, y = (off & 31) * 8, 16 + (off >> 5)
            sk = seen.get(key)
            if sk is None:
                sk = seen[key] = sheet_part(ns.pat, get, key, e, x, y, 0, 0) or False
                if sk:                       # the rotation table against the game's graphics
                    for c_, r, k, b, code, n in sk['pixels']:
                        bit = om[int(k, 16)] >> (7 - b) & 1
                        st['ok' if bit == (code == 1) else 'bad'] += 1
            if sk:
                parts.append(dict(sk, x=x + (sk['x'] - sk['x']), y=y, fam=(st['f'], i)))
        if parts:
            col.add_frame(parts)
    for r in ([rzx_paths] if isinstance(rzx_paths, str) else rzx_paths):
        verify(patch or IkariPatch(colours={}), r, stop=stop, capture=cap, picture=False)
    return col, st


def colour_inputs_md5(peek):
    """MD5 of the graphics the colour keys point at."""
    h = hashlib.md5()
    for lo, hi, _ in REGIONS:
        h.update(bytes(peek(a) for a in range(lo, hi)))
    return h.hexdigest()


def colour_identity(peek):
    return {'schema': 1, 'game': RECORD, 'engine': 'ikari_warriors', 'keys': 'ikari_warriors-1: %04X graphics byte, bit = stored pixel',
            'inputs': colour_inputs_md5(peek), 'geometry': None}


def sheets(col, prefix, peek, colours=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb([0, 0xB4] + FIX[2:])
    comps = list(col.comps.values())
    ident = colour_identity(peek)
    res = []
    paint = cs.choose(comps, col.maxsize, GROUPS)
    png = prefix + '_PAINTING_SPRITES.png'
    res.append((png, cs.write(paint, png, prefix + '_PAINTING_SPRITES_layout.json', rgb16, colours or {}, unique=False, paint_clear=True, identity=ident)))
    full = sorted(comps, key=lambda c: (GROUPS.index(c['group']), str(c['parts'][0]['id'])))
    png = prefix + '_REFERENCE_ALL_SPRITES.png'
    res.append((png, cs.write(full, png, prefix + '_REFERENCE_ALL_SPRITES_layout.json', rgb16, colours or {}, unique=False, paint_clear=True, identity=ident)))
    return res


def recolour(nex, cmap):
    from .recolour import nex_offsets, splice, nex_peek
    off = nex_offsets(bytes(nex))
    need = set(COLOUR_BANKS) | {5, 2, 0, 10, 12}
    if not need <= set(off):
        raise ValueError('not an Ikari Warriors sprite build: banks %s missing' % sorted(need - set(off)))
    bank = lambda b: bytes(nex[off[b]:off[b] + 16384])
    peek = nex_peek(nex)
    prof = load_profile()
    want = prof.get('colour_inputs')
    got = colour_inputs_md5(peek)
    if want and want != got:
        raise ValueError('game graphics differ from the expected snapshot (%s, expected %s)' % (got, want))
    # the default build is edge_patch() since the fifth pass (its seams through the colour route, EDGES): a map paints
    # over those (import 2026-11-04: recolour still checked against IkariPatch(colours={}) and refused e740ae71)
    p0 = edge_patch(prof=prof)
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
    b12 = bank(12)
    lo, hi = p0.regblock - 0x2000, p0.regblock - 0x2000 + 20
    if b12[:lo] != bytes(p0.page[:lo]) or b12[hi:8192] != bytes(p0.page[hi:8192]):
        raise ValueError("hook code differs from this version's (rebuild)")
    merged = dict(json.load(open(EDGES)))
    merged.update(cmap)
    p = edge_patch(colours=merged, prof=prof)
    out, changed = splice(nex, {b: p.extra_banks[b] for b in COLOUR_BANKS})
    return out, {'banks changed': changed, 'colour-map entries': len(cmap)}


def synthetic_colours(peek):
    """A nibble per pixel of every graphics byte of the three regions: 3 + (address + bit) % 13."""
    out = {}
    for lo, hi, _ in REGIONS:
        for a in range(lo, hi):
            out['%04X' % a] = [peek(a), 1, [3 + (a + b) % 13 for b in range(8)]]
    return out


def unit_tests(patch, rzx, stop=2500):
    """Colour map: a synthetic map must reach every pixel of the graphics bytes of real captures, and a build
    with the map left out (negative control) must be seen to differ. Game memory and registers stay checked."""
    c = collections.Counter()
    fails = []

    def run(pt, tag):
        seen = {}

        def cap(ns, om, pm):
            h = ns.pages[HPG]
            for i in range(h[V_N]):
                e = h[LOG + 3 * i]
                key = bytes(h[ENT + e * 16:ENT + e * 16 + 8])
                if key in seen or image_map(key) is None:
                    continue
                seen[key] = 1
                kind, base, s, w, n = image_map(key)
                for line in range(n):
                    for gb in range(w):
                        a = base + line * w + gb
                        if store_offset(a) is None:
                            continue
                        for b in range(8):
                            got = canvas_pixel(ns.pat, e, s + gb * 8 + b, line, kind)
                            want = 3 + (a + b) % 13
                            c[tag + ' pixels'] += 1
                            if got != want:
                                c[tag + ' differ'] += 1
                                if len(fails) < 5 and tag == 'map':
                                    fails.append((key.hex(), line, gb, b, got, want))
        cc, ex, _ = verify(pt, rzx, stop=stop, capture=cap, picture=False)
        bad = {k: v for k, v in cc.items() if k.endswith('!')}
        if bad:
            c[tag + ' verify failed!'] += 1
            fails.append((tag, bad))
    from skoolkit.snapshot import Snapshot
    from .simrun import addr_view
    from .rzx import read_segments
    import tempfile
    # the graphics as the snapshot holds them
    from .z80tonex import Z80Snapshot
    prof = load_profile()
    m = None
    p1 = IkariPatch(prof, colours=synthetic_colours(_peek()))
    run(p1, 'map')
    p2 = IkariPatch(prof, colours=synthetic_colours(_peek()))
    p2.hpage[V_COL] = 0
    run(p2, 'negative')
    if c['map differ']:
        c['map wrong!'] = c['map differ']
    if not c['negative differ']:
        c['negative undetected!'] = 1
    return c, fails


def _peek():
    from skoolkit.snapshot import Snapshot
    from .simrun import addr_view
    z = os.environ.get('IKARI_Z80')
    m = addr_view(Snapshot.get(z))
    return lambda a: m[a]


# ---------------------------------------------------------------------------------------------
# The colour-set checker (runs/ikari_warriors work/enh2/venh5.py, sixth pass; imported 2026-11-04): the approved default
# (edge_patch) and Enhanced builds in lockstep, their picture classed by the first default's (IkariPatch(colours={}),
# d6a6fce2) pattern of each image key, plus per-image checks: shape, outline gone, nothing outside the black edge, seams
# closed, enclosed pixels the paper (default) or painted (Enhanced), players and enemies in their colours, enemy faces.
# ---------------------------------------------------------------------------------------------
def seam_gaps(get, n, G):
    """positions in a line of length n in runs of <= G non-ink pixels bounded by ink on both sides (work/enh2/seams.py)"""
    out = set()
    i = 0
    while i < n:
        if get(i):
            i += 1
            continue
        j = i
        while j < n and not get(j):
            j += 1
        if i > 0 and j < n and j - i <= G:
            out |= set(range(i, j))
        i = j
    return out


def default_patterns(rzx, stop=None):
    """{image key: 512 pattern bytes} of the first default build (IkariPatch(colours={})) on a recording."""
    D = {}

    def capd(ns, om, pm):
        h = ns.pages[HPG]
        for i in range(h[V_N]):
            e = h[LOG + 3 * i]
            key = bytes(h[ENT + e * 16:ENT + e * 16 + 8])
            if key not in D:
                D[key] = bytes(ns.pat[e * 512:(e + 1) * 512])
    c0, _, _ = verify(IkariPatch(colours={}), rzx, stop=stop, capture=capd, picture=False)
    bad0 = {k: v for k, v in c0.items() if k.endswith('!')}
    if bad0:
        raise ValueError('default-pattern run failed %s' % bad0)
    return D


def set_patch(mode, neg=None, cols=None):
    cols = cols if cols is not None else json.load(open(EDGES if mode == 'default' else ENHANCED))
    if mode == 'default':
        if neg is None:
            return edge_patch(cols)
        if neg == 'old-default':          # the approved build before (d6a6fce2): outline and paper edge, seams open
            return IkariPatch(colours={})
        if neg == 'outline-on':
            return edge_patch(cols, outline=True)
        if neg == 'border-paper':
            return edge_patch(cols, border='paper')
        if neg == 'seam-open':
            return edge_patch({})
        raise ValueError('unknown negative')
    p = enhanced_patch(cols)
    if neg is None:
        return p
    if neg == 'outline-on':               # the white ring kept
        return enhanced_patch(cols, outline=True)
    if neg == 'border-paper':             # the yellow edge kept (the paper border beyond the black edge)
        return enhanced_patch(cols, border='paper')
    if neg == 'third-pass':               # 9b8d9497's Enhanced: outline and paper border
        return enhanced_patch(cols, outline=True, border='paper')
    rom = bytearray(p.rom_code)
    ext = len(bytes.fromhex(p.prof['hooks']['rom']))      # the extension follows the hook code

    def sub(old, new, count=None):
        s = bytes(rom[ext:])
        n = s.count(old)
        if not n or (count and n != count):
            raise ValueError('negative: pattern %s x%d' % (old.hex(), n))
        rom[ext:] = s.replace(old, new)
    if neg == 'player-test-off':          # every figure takes the enemy colours
        sub(bytes([0xDD, 0xCB, 0x02, 0x7E, 0xC8]), bytes([0xDD, 0xCB, 0x02, 0x7E, 0xC9]), 2)
    elif neg == 'p2-test-off':            # player 2 not told apart: his key and colours are player 1's
        sub(bytes([0xFE, P2_IXL]), bytes([0xFE, 0x00]), 2)
    elif neg == 'rotation-map-off':       # AND-only images keyed at the wrong shift
        sub(bytes([0xFE, 0x99]), bytes([0xC9, 0x99]), 1)
    elif neg == 'k5k6-keys-on':           # pick-ups and heavy objects read the players' keys
        y = {k: int(v, 16) for k, v in p.prof['hooks']['syms'].items()}
        for s_, v in (('e_k5.c5', 5), ('e_k6.c6', 6)):
            rom[y[s_] + 1 - 0x2400] = v
    elif neg == 'store-off':
        pass
    else:
        raise ValueError('unknown negative')
    q = IkariPatch(p.prof, colours=cols, rom_code=bytes(rom))
    q.stub_extra = p.stub_extra
    if neg == 'store-off':
        q.hpage[V_COL] = 0
    return q



def set_check(P, rzx, D, mode, stop=None):
    """One colour-set build (mode 'default' or 'enhanced') on a recording: verify() with the classed picture and the
    per-image checks. -> (verify counters, check counters, failures)."""
    MODE = mode
    gaps = seam_gaps
    st = collections.Counter()
    ex = collections.defaultdict(list)
    PAINTED = set(range(0, 49)) | set(range(58, 63))
    ENHC = {I_TROUSERS, I_SKIN, I_UNIFORM, I_BLUE, I_RED}
    def bad(k, info):
        st[k + '!'] += 1
        if len(ex[k]) < 4:
            ex[k].append(info)


    BC = {}
    EF = collections.Counter()
    SC = {}      # (key, entry) -> colour counts: a pattern is checked once while it stays cached under its key


    def nib(pat, pn, j, k):
        b = pat[pn * 128 + j * 8 + k // 2]
        return (b >> 4) if k % 2 == 0 else (b & 15)


    def mycompose(ns, scr, om=None):
        h = ns.pages[HPG]
        edest = collections.defaultdict(set)
        for i in range(h[V_N]):
            edest[h[LOG + 3 * i]].add(h[LOG + 1 + 3 * i] | h[LOG + 2 + 3 * i] << 8)
        p2 = (om[0xE5AA] | om[0xE5AB] << 8) if om[0xE5A9] & 0x80 else None
        bits, nspx, torn = {}, 0, 0
        last = [None]
        kinds = collections.Counter()
        org = ((om[0xE460] | om[0xE461] << 8) + 0x700) & 0xFF
        done = set()
        for x0, y0, pn, bank, slot in ns.sprites():
            e = pn >> 2
            key = bytes(ns.H(ENT + e * 16 + i) for i in range(8))
            kind = key[7]
            kd = key[:1] + bytes([key[1] & 0xFD]) + key[2:] if kind == 1 else key
            Pd = D.get(kd)
            if Pd is None:
                bad('no default image for the key', key.hex())
                continue
            if e not in done:            # once per image on show per commit; its pattern once per (key, entry)
                done.add(e)
                S = SC.get((key, e))
                if S is None:
                    S = SC[(key, e)] = collections.Counter()
                    for t in range(4):
                        for j in range(16):
                            for k in range(16):
                                c, cd = nib(ns.pat, e * 4 + t, j, k), nib(Pd, t, j, k)
                                S[c] += 1
                                if c != cd:
                                    st['pixel default %d -> %d' % (cd, c)] += 1
                                    if kind != 1:
                                        bad('non-figure differs', (key.hex(), cd, c))
                                    elif c == 0 and cd not in (1, 14, 15):
                                        bad('clear where the default is opaque', (key.hex(), t, j, k, cd))
                f = key[0]
                st['images checked'] += 1
                if kind == 1:
                    st['K1 images checked'] += 1
                    andonly = key[1] & 1
                    dests = edest.get(e, set())
                    isp = bool(key[1] & 0x80)
                    img = lambda pt, X, Y: nib(pt, (e * 4 if pt is ns.pat else 0) + (Y >> 4) * 2 + (X >> 4), Y & 15, X & 15)
                    Dg = [[img(Pd, X, Y) for X in range(32)] for Y in range(32)]
                    Eg = [[img(ns.pat, X, Y) for X in range(32)] for Y in range(32)]
                    key2 = (key, e)
                    if key2 not in BC:
                        BC[key2] = 1
                        INK = lambda Y, X: Dg[Y][X] == 2
                        sm = set()
                        if not andonly and f != 57:
                            for Y in range(32):
                                sm |= {(X, Y) for X in gaps(lambda X: INK(Y, X), 32, 2)}
                            for X in range(32):
                                sm |= {(X, Y) for Y in gaps(lambda Y: INK(Y, X), 32, 2)}
                            ie = lambda X, Y: any(INK(Y, a) for a in range(X)) and any(INK(Y, a) for a in range(X + 1, 32)) and \
                                any(INK(b, X) for b in range(Y)) and any(INK(b, X) for b in range(Y + 1, 32))
                            sm = {(X, Y) for (X, Y) in sm if not ie(X, Y)}      # a channel, not a hole the ink encloses
                        SS = lambda X, Y: INK(Y, X) or (X, Y) in sm
                        encset = set()
                        for Y in range(32):
                            for X in range(32):
                                cd, c = Dg[Y][X], Eg[Y][X]
                                if c == 15:
                                    bad('outline present', (key.hex(), X, Y))
                                if andonly or f == 57:     # no mask (the drawing is the light pixels) / the ripple: as before
                                    inside = cd not in (0, 15)
                                    if not inside:
                                        if c != 0:
                                            bad('opaque outside the black edge', (key.hex(), X, Y, cd, c))
                                    elif MODE == 'default' or f not in PAINTED:
                                        if c != cd:
                                            bad('AND-only or ripple changed', (key.hex(), X, Y, cd, c))
                                    elif cd == I_DET and 1 <= Y <= 13:
                                        st['body pixels'] += 1
                                        if c not in ENHC:
                                            bad('body pixel not painted', (key.hex(), X, Y, cd, c))
                                    elif c != cd and not (isp and c in (I_RED, I_BLUE) and Y == 2):
                                        bad('inside pixel changed', (key.hex(), X, Y, cd, c))
                                    continue
                                if INK(Y, X):
                                    if c != 2 and not (MODE != 'default' and isp and f in PAINTED and c in (I_RED, I_BLUE) and Y == 2):
                                        bad('ink changed', (key.hex(), X, Y, c))
                                    continue
                                if (X, Y) in sm:
                                    st['seam pixels'] += 1
                                    if MODE == 'default' or f not in PAINTED:
                                        if c != 2:
                                            bad('seam left open', (key.hex(), X, Y, cd, c))
                                    elif c not in ENHC and c != 2:
                                        bad('seam left open', (key.hex(), X, Y, cd, c))
                                    continue
                                enc = any(SS(a, Y) for a in range(X)) and any(SS(a, Y) for a in range(X + 1, 32)) and \
                                    any(SS(X, b) for b in range(Y)) and any(SS(X, b) for b in range(Y + 1, 32))
                                if enc:
                                    encset.add((X, Y))
                                    st['enclosed pixels'] += 1
                                    if MODE == 'default' or f not in PAINTED:
                                        if c not in (1, 14):
                                            bad('enclosed pixel not the paper', (key.hex(), X, Y, cd, c))
                                    elif c not in ENHC:
                                        bad('body pixel not painted', (key.hex(), X, Y, cd, c))
                                else:
                                    st['outside pixels'] += 1
                                    if c != 0:
                                        st['outside pixel %d -> %d' % (cd, c)] += 1
                                        bad('opaque outside the black edge', (key.hex(), X, Y, cd, c))
                        if MODE != 'default' and f in PAINTED and not isp:
                            if andonly:
                                fc = {(X, Y) for Y in range(1, 6) for X in range(32) if Dg[Y][X] == I_DET and not any(
                                    not (0 <= X + dx < 32 and 0 <= Y + dy < 32) or Dg[Y + dy][X + dx] in (0, 15)
                                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
                            else:
                                fc = set()
                                for (X, Y) in encset:
                                    if not 1 <= Y <= 5:
                                        continue
                                    four = all(0 <= X + dx < 32 and 0 <= Y + dy < 32 and INK(Y + dy, X + dx) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                                    diag = sum(1 for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)) if (X + dx, Y + dy) in encset)
                                    if not (four and diag >= 2):
                                        fc.add((X, Y))
                            sk = {(X, Y) for Y in range(32) for X in range(32) if Eg[Y][X] == I_SKIN}
                            st['enemy faces checked'] += 1
                            st['enemy face pixels'] += len(fc)
                            if not fc or not sk:
                                bad('enemy without a face', (key.hex(), len(fc), len(sk)))
                            elif fc - sk:
                                bad('enemy face not all skin', (key.hex(), sorted(fc - sk)[:4]))
                            if sk - fc:
                                bad('skin outside the face', (key.hex(), sorted(sk - fc)[:4]))
                if kind == 1 and f in PAINTED and MODE != 'default':
                    st['painted images checked'] += 1
                    if isp:
                        role = 'P2' if p2 is not None and p2 in dests else 'P1'
                        if p2 is not None and p2 in dests and len(dests) > 1:
                            bad('one image for both players', key.hex())
                        st['images ' + role] += 1
                        if not S[I_SKIN] or S[I_UNIFORM]:
                            bad('player not in player colours', (role, key.hex()))
                        want, other = (I_RED, I_BLUE) if role == 'P1' else (I_BLUE, I_RED)
                        if S[other]:
                            bad('the other player\'s band', (role, key.hex()))
                        if f < 40 and not S[want]:
                            bad('no band', (role, key.hex()))
                    else:
                        st['images enemy'] += 1
                        ef = (f, key[2])
                        EF[ef] += 1
                        if not S[I_UNIFORM] or S[I_RED] or S[I_BLUE]:
                            bad('enemy not in enemy colours', key.hex())
                elif kind == 1 and MODE != 'default':
                    st['default images checked (gun, ripple)'] += 1
                    if any(S[c] for c in ENHC):
                        bad('Enhanced colour on an unpainted frame', key.hex())
            # the picture, classed by the default pixel. A K1 image is composed whole from the default's own tiles at the
            # Enhanced image's place (first tile seen draws the image): with no border a tile can be empty and so not shown,
            # though the default shows it; the per-image check above proves the only differences are colour inside and
            # transparency outside the black edge, so this proves the place, the frame and the game's picture as before.
            fol = kind == 1 and key[1] & 1
            kinds[kind] += 1
            if kind == 1:
                ox, oy = x0 - (16 if pn & 1 else 0), y0 - (16 if pn & 2 else 0)
                if last[0] == (e, ox, oy):        # the image's tiles are consecutive slots; a later redraw is a new instance
                    continue
                last[0] = (e, ox, oy)
                tiles = [(t, ox + (16 if t & 1 else 0), oy + (16 if t & 2 else 0)) for t in range(4)
                         if any(nib(Pd, t, j, k) for j in range(16) for k in range(16))]
                if (pn & 3) not in [t for t, _, _ in tiles]:
                    bad('a tile shown that the default leaves empty', key.hex())
            else:
                last[0] = None
                tiles = [(pn & 3, x0, y0)]
            for t, tx, ty in tiles:
                offs = None
                tr = 16 if t & 2 else 0
                if kind in TORN_KINDS:
                    xs = tx - (16 if t & 1 else 0)
                    low = (org + (ty - tr - 16) * 32 + (xs >> 3)) & 255
                    offs = torn_offsets(low, 32)
                    torn += sum(1 for j in range(16) if offs[tr + j] != tr + j)
                for j in range(16):
                    y = ty + j if offs is None else ty - tr + offs[tr + j]
                    if not WIN[2] <= y <= WIN[3]:
                        continue
                    for k in range(16):
                        cd = nib(Pd, t, j, k)
                        if not cd or cd in EXTRA:
                            continue
                        x = tx + k
                        if not WIN[0] <= x <= WIN[1]:
                            continue
                        nspx += 1
                        if kind in XOR_KINDS:
                            v = bits.get((x, y))
                            if v is None:
                                v = screen_bit(scr, x, y)
                            bits[(x, y)] = v ^ 1
                        else:
                            bits[(x, y)] = 0 if cd == 1 or (cd == I_DET and fol) else 1
        return bits, nspx, kinds, torn

    c, exv, _ = verify(P, rzx, stop=stop, compose_fn=mycompose)
    fails = {k: v for k, v in c.items() if k.endswith('!')}
    fails.update({k: v for k, v in st.items() if k.endswith('!')})
    return c, st, fails


SET_NEGATIVES = {'default': ['old-default', 'outline-on', 'border-paper', 'seam-open'],
                 'enhanced': ['outline-on', 'border-paper', 'third-pass', 'player-test-off', 'p2-test-off',
                              'rotation-map-off', 'k5k6-keys-on', 'store-off']}


def auto(a, z80, name, out, say):
    say('Game      : %s' % name)
    say('Engine    : ikari_warriors (back-buffer composer; blit from a clean window copy; every figure -> sprites)')
    ok, (plain, spr), patch = build(z80, out, name, say)
    ok2, enh, epatch = build_enhanced(z80, out, name, say)
    ok = ok and ok2
    quick = getattr(a, 'quick', None)
    Ds = {}
    for r in list(a.rzx or []):
        Ds[r] = default_patterns(r, stop=quick)  # the classing reference: the first default's pattern per image key
        for mode, p in (('default', patch), ('enhanced', epatch)):
            c, st, fails = set_check(p, r, Ds[r], mode, stop=quick)
            ok = ok and not fails
            say('Verify    : %s %-8s %d frames, %d commits, %d images checked, seams %d, enclosed %d, faces %d -> %s' % (
                os.path.basename(r), mode, c['frames'], c['commits'], st['images checked'], st['seam pixels'],
                st['enclosed pixels'], st['enemy faces checked'], 'IDENTICAL' if not fails else 'FAILED %s' % str(fails)[:300]))
    rz = {os.path.splitext(os.path.basename(r))[0]: r for r in (a.rzx or [])}
    if 'ik_2pw' in rz:                          # the colour-set negatives (work/enh2/venh5.py), on ik_2pw as there
        n = d = 0
        for mode, negs in SET_NEGATIVES.items():
            for ng in negs:
                try:
                    _, _, fl = set_check(set_patch(mode, ng), rz['ik_2pw'], Ds[rz['ik_2pw']], mode, stop=quick)
                except BaseException as e:      # noqa: BLE001 - a broken build may lose sync: detected
                    fl = {'crash/lost sync': str(e)[:80]}
                n += 1
                d += bool(fl)
                say('Negative  : %-8s %-18s %s' % (mode, ng, 'DETECTED %s' % str(sorted(fl))[:100] if fl else 'NOT DETECTED!'))
        ok = ok and d == n
        say('Negatives : colour sets %d/%d detected' % (d, n))
    if 'ik_cheat1' in rz:                       # the engine's negatives (runs/ikari_warriors work/neg.py)
        n = d = 0
        for nm, p in negative_patches():
            r = rz.get('ik_att') if 'line table' in nm else rz['ik_cheat1']
            if r is None:
                say('Negative  : %-34s skipped: needs ik_att.rzx' % nm)
                continue
            try:
                c, ex, _ = verify(p, r, stop=None if r.endswith('ik_att.rzx') else 1800)
                fl = {k: v for k, v in c.items() if k.endswith('!')}
            except BaseException as e:          # noqa: BLE001 - a broken build may lose sync: detected
                fl = {'crash/lost sync': str(e)[:80]}
            n += 1
            d += bool(fl)
            say('Negative  : %-34s %s' % (nm, 'DETECTED %s' % str(fl)[:100] if fl else 'NOT DETECTED!'))
        ok = ok and d == n and n == len(negative_patches())
        say('Negatives : engine %d/%d detected' % (d, n))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
