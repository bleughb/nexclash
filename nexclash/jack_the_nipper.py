"""Jack the Nipper (Gremlin Graphics, 1986, 48K) engine 'jack_the_nipper'. Additive module: reachable only through
is_jack_the_nipper().

Game facts (games/jack_the_nipper.md): the sprite routine 0x8009 draws each object masked (AND mask, OR graphics)
into a shadow screen at 0x6000-0x6FFF and marks its cells (0x7D00-0x7EFF); the copier 0x86F9 copies marked cells to
the display, and 0x8735 restores them from the tile map. Interrupts are off for the whole game; nothing syncs it to
the frame, so the work it does is its pace.

Hooks (asm/jack_the_nipper_hooks.asm, Next page JTN_PAGE at MMU slot 1 for the whole game; the game never reads the
ROM there): at the two returns from the address helper 0x87BB (0x80C9: 16-wide figures, 0x8273: 24-wide) the shadow
address moves to a scratch shadow at 0x2000-0x2FFF (RES 6,H), so the game's own draw runs unchanged (the same work,
so the same pace) and the real shadow keeps the background. The cell marks take only H bits 3 and 0-2 and L (0x8123),
so they mark the same cells.

The commit at the copier's entry 0x86F9 turns the recorded figures into 4-bit sprites: black lines, the body in the
paper of the cell under the figure's feet (one palette bank per Spectrum colour), mirrored by the sprite's X mirror.
Stage B (2026-11-23): sprites; the verifier checks the redirect so far (games/jack_the_nipper.md "Patch plan").
"""
import json
import os

JTN_PAGE = 24               # Next page at MMU slot 1 for the whole game (bank 12's first half)
CODE_ORG = 0x3600           # hook code in the page (asm ORG); state 0x3000-0x35FF below it
RESTORE = 0x3E00            # restore_tail: the tail's backup, then its code
REGBLOCK = 0x3F00           # the stub's register block (20 bytes)
SCRATCH = (0x2000, 0x3000)  # the scratch shadow the figure draws land in
SHADOW = (0x6000, 0x7000)   # the game's shadow screen
TAIL_ADDR = 0x6F00          # the start-up tail; restore_tail puts its bytes back before the game starts
SPACE_GLYPH = 0x5C00        # the font is at 0x5B00 (printers 0xFF32, 0xFF7D), so the space is where the ROM keeps KSTATE
DUMP_KSTATE = bytes.fromhex('00f7000000f70000')     # the TOSEC [a] dump's: the dumping emulator's ROM interrupt wrote it
SITES_ORIG = {0x80C9: 'e5f5a7', 0x8273: 'e5f5a7', 0x86F9: '21ff7c'}
SITE_OP = {0x80C9: (0xC3, 'e_d16'), 0x8273: (0xC3, 'e_d24'), 0x86F9: (0xC3, 'e_cmt')}
INTERIORS = (0x80CA, 0x80CB, 0x8274, 0x8275, 0x86FA, 0x86FB)
INTERIOR_PREV = {0x80CA: 0x80C9, 0x80CB: 0x80CA, 0x8274: 0x8273, 0x8275: 0x8274, 0x86FA: None, 0x86FB: None}
# the original reaches 0x80CA / 0x80CB (PUSH AF; AND A) only by running on from 0x80C9 (and 0x8274 / 0x8275 from
# 0x8273); 0x86FA / 0x86FB are LD HL,0x7CFF's operand: never an instruction

from .hooklib import CMP as _CMP

CMP = _CMP                  # every register but R, T, MEMPTR: R is never read (no LD A,R in the code; games/jack_the_nipper.md)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'jack_the_nipper.json'),
              os.path.join(_HERE, 'jack_the_nipper.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('jack_the_nipper.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_jack_the_nipper(snap):
    """True only for Jack the Nipper: 48K and the address helper 0x87BB's bytes."""
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    a, sig = int(sg['addr']), bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[a:a + len(sig)]) == sig


def restore_tail(p, s):
    """The start-up tail puts the snapshot's bytes back before the game starts (as Green Beret's): the tail jumps to
    code in the slot-1 page, which copies a backup over the tail and runs the tail's register restore again, so no
    game memory is assumed dead. Call before the page goes into extra_banks; idempotent (check() applies a copy
    again)."""
    from . import z80tonex as zt
    tail, _, restore, _ = zt.build_tail(s, p.tail_addr, p.slot1, False)
    entry = RESTORE + len(tail)
    code = (b'\xF3\x21' + zt.w16(RESTORE) + b'\x11' + zt.w16(p.tail_addr) + b'\x01' + zt.w16(len(tail)) + b'\xED\xB0'
            + tail[restore:])
    end = entry + len(code)
    if end > REGBLOCK:
        raise ValueError('tail restore 0x%04X-0x%04X runs into the register block' % (RESTORE, end))
    page = bytearray(p.page)
    page[RESTORE - 0x2000:entry - 0x2000] = bytes(s.read(p.tail_addr + i) for i in range(len(tail)))
    page[entry - 0x2000:end - 0x2000] = code
    p.page = bytes(page)
    p.original_pc, p.tail_restore_bytes, s.pc = s.pc, len(tail), entry


class _PagePatch:
    """What both builds share: the slot-1 page (scratch shadow, code, register block) and restore_tail."""
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = True
    keep_printer_buffer = True              # the game reads and runs code at 0x5B00-0x5BBC
    tail_addr = TAIL_ADDR

    code_org = CODE_ORG

    def __init__(self, code=b''):
        page = bytearray(8192)
        page[self.code_org - 0x2000:self.code_org - 0x2000 + len(code)] = code
        if self.code_org + len(code) > RESTORE:
            raise ValueError('hook code runs into the tail restore')
        self.page = bytes(page)
        self.slot1 = (JTN_PAGE, REGBLOCK)
        self.sites = []
        self.extra_banks = {JTN_PAGE // 2: self.page + bytes(8192)}

    def _check(self, ram):
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %04X (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Jack the Nipper patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        self._check(ram)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        g = SPACE_GLYPH - 0x4000                # the owner, 2026-11-26: print blank spaces again (dashes in the dump)
        if bytes(ram[g:g + 8]) == DUMP_KSTATE:
            ram[g:g + 8] = bytes(8)
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])
        restore_tail(self, snap)
        self.extra_banks = {JTN_PAGE // 2: self.page + bytes(8192)}


class PlainPatch(_PagePatch):
    """The plain .nex: no hooks; the slot-1 page holds only the tail restore."""
    name = 'Jack the Nipper plain conversion'


# Enhanced colours (docs/COLOURS.md): a painted colour per graphics pixel -----------------------------------------
# Shared with Jack the Nipper II: the table (4 bytes = 8 nibbles a graphics byte, 0 = the default) the hooks' ovr reads
# at slot 0, built from a colour map keyed by graphics byte.
RECORD = 'jack_the_nipper'
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')
PALETTE = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_palette.json')
V_OVR = 0x31E6
OVR_BASE, OVR_SPAN, OVR_PAGE0 = 0xE000, 0x2000, 40  # = the asm's: figure graphics 0xE000-0xFDF8 (2026-11-26 census; the image the game builds at 0x5B00 keeps its colours)
# 1 black, 2 the body (the cell's paper: varies, shown light grey on the sheets), 3-15 the painting palette (Next
# RRRGGGBB): greys, white, skin, brown, reds, orange, yellow, greens, blues, purple
PALETTE_DEFAULT = (0x00, 0x00, 0xB6, 0x49, 0x92, 0xFF, 0xF6, 0x88, 0xE0, 0xF0, 0xFC, 0x3C, 0x10, 0x0B, 0x77, 0x83)


def ovr_entries(get, cmap, base, span):
    """Colour map -> ({graphics byte address: 8 nibbles}, info): the entries the build uses (inside the table, the
    check byte equal to the game's)."""
    import collections
    out, info = {}, collections.Counter()
    for k, e in cmap.items():
        a = int(k, 16)
        if not base <= a < base + span:
            info['map entries outside the table'] += 1
            continue
        if e[0] is not None and e[0] != get(a):
            info['map entries ignored (check byte differs)'] += 1
            continue
        if any(e[2]):
            out[a] = list(e[2])
            info['graphics bytes with colours'] += 1
    return out, info


def ovr_pages(ovr, base, span, page0):
    """{address: 8 nibbles} -> {Next page: 8192 bytes} (page0..)."""
    pages = {page0 + i: bytearray(8192) for i in range(span * 4 // 8192)}
    for a, nib in ovr.items():
        o = (a - base) * 4
        pages[page0 + o // 8192][o % 8192:o % 8192 + 4] = bytes(nib[2 * i] << 4 | nib[2 * i + 1] for i in range(4))
    return {k: bytes(v) for k, v in pages.items()}


def add_pages(extra, pages):
    """Next pages {page: 8192 bytes} into an extra_banks dict {16K bank: bytes}."""
    for p, data in pages.items():
        b, half = p // 2, p % 2
        cur = extra.get(b, bytes(16384))
        extra[b] = cur[:half * 8192] + data + cur[half * 8192 + 8192:]


def palette():
    return list(json.load(open(PALETTE))) if os.path.exists(PALETTE) else list(PALETTE_DEFAULT)


def load_colours():
    from . import coloursheet as cs
    from .recolour import build_colours_path
    p = build_colours_path(COLOURS)
    return cs.load(p) if os.path.exists(p) else {}


def figure_keys(f):
    """{(x, y): (graphics byte address, bit)} for each pixel position of the figure (rows stored bottom first)."""
    out = {}
    w8 = f['width'] * 8
    for r in range(f['rows']):
        for b in range(f['width']):
            a = (f['gfx'] + r * f['width'] + b) & 0xFFFF
            for bit in range(8):
                c = b * 8 + bit
                out[f['x'] + (w8 - 1 - c if f['mirror'] else c), f['y'] - r] = (a, bit)
    return out


class JtnPatch(_PagePatch):
    name = 'Jack the Nipper figures -> hardware sprites (slot-1 page, scratch-shadow redirect)'

    def __init__(self, prof=None, colours=None, pal=None, enhanced=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        if self.syms['code_start'] != self.code_org:
            raise ValueError('hook code assembled at 0x%04X, not 0x%04X' % (self.syms['code_start'], self.code_org))
        super().__init__(bytes.fromhex(h['page']))
        self.stub_extra = bytes.fromhex(h['setup'])      # the sprite palette and NR 0x15, once (asm `setup`)
        self.setup_call = self.syms['setup']
        self.sites = [(a, bytes.fromhex(old), bytes([SITE_OP[a][0]]) + self.syms[SITE_OP[a][1]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]
        self.colours = colours or {}            # the Enhanced colour map
        self.enhanced = bool(self.colours) if enhanced is None else enhanced    # the Enhanced build (its banks, empty or not)
        self.pal = list(pal or palette()) if self.enhanced else [0] * 16
        self.ovr, self.cinfo = {}, {}
        pg = bytearray(self.page)
        pg[V_OVR - 0x2000] = 1 if self.enhanced else 0
        self.page = bytes(pg)
        st = bytearray(self.stub_extra)
        o = self.syms['setspare'] - self.setup_call
        st[o:o + 13] = bytes(self.pal[3:16])
        self.stub_extra = bytes(st)

    def apply(self, snap):
        super().apply(snap)
        if self.enhanced:
            self.ovr, self.cinfo = ovr_entries(snap.read, self.colours, OVR_BASE, OVR_SPAN)
            add_pages(self.extra_banks, ovr_pages(self.ovr, OVR_BASE, OVR_SPAN, OVR_PAGE0))


def build(z80, out, name, say=print):
    """Both builds with their boot checks. -> (plain path, sprites path, problems)"""
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    bad = []
    paths = []
    for label, patch, suffix in (('Plain', PlainPatch(), ''), ('Sprites', JtnPatch(), '_sprites'),
                                 ('Enhanced', JtnPatch(colours=load_colours(), enhanced=True), '_enhanced')):
        path = os.path.join(out, name + suffix + '.nex')
        conv = zt.convert(z80, path, None, True, quiet=True, patch=patch, keep_printer_buffer=True)
        b = check(path, z80, patch, (conv[1], conv[1] + len(conv[2])))
        b += restored_boot_check(path, z80, patch) + restored_boot_check(path, z80, patch, nexload=True)
        say('%-10s: %s  %s  boot %s  (tail 0x%04X, %d bytes, put back)' % (
            label, os.path.basename(path), md5(path), 'OK' if not b else 'MISMATCH %s' % str(b[:3])[:200],
            conv[1], len(conv[2])))
        bad += b
        paths.append(path)
    return paths[0], paths[1], bad


# ---------------------------------------------------------------------------------------------
# Verify (PLAYBOOK 6): at each site in the replay, the original code and the patched one from the same state
# ---------------------------------------------------------------------------------------------

DRAW = (0x8000, 0x8820)     # the sprite routine and its helpers: a draw ends back in the caller, below its stack frame
COPY = (0x86F9, 0x8735)     # the copier: it ends back in its caller
SITE_KIND = {0x80C9: 'draw16', 0x8273: 'draw24', 0x86F9: 'copy'}
STATE = (0x3000, 0x3600)    # the page's hook state and stack
PLAY = (256, 128)           # the play area: shadow / screen rows 0-127


def shadow_addr(x, y):
    return 0x6000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x >> 3


class NextSide:
    """The Next as the hooks drive it, across the whole replay: NextRegs (NR 7 read back as the hardware composes
    it), the sprite pattern port (0x303B selects, 0x5B writes on) and the attribute port (0x57: attribute 4 only when
    attribute 3 bit 6 is set)."""

    def __init__(s):
        s.nr = {}
        s.sel = 0
        s.pat = bytearray(16384)
        s.patp = 0
        s.attr = bytearray(640)
        s.an = s.ab = 0
        s.events = []

    def nextreg(s, r, v):
        s.nr[r] = v

    def read_port(s, regs, port):
        if port == 0x243B:
            return s.sel
        if port == 0x253B:
            v = s.nr.get(s.sel, 0)
            return (v & 3) << 4 | (v & 3) if s.sel == 0x07 else v
        s.events.append(('in', port))
        return 0xFF

    def write_port(s, regs, port, v, *x):
        lo = port & 0xFF
        if port == 0x243B:
            s.sel = v
        elif port == 0x253B:
            s.nextreg(s.sel, v)
        elif port == 0x303B:
            s.patp = (v & 0x3F) << 8 | (0x80 if v & 0x80 else 0)
            s.an, s.ab = v & 0x7F, 0
        elif lo == 0x5B:
            s.pat[s.patp & 0x3FFF] = v
            s.patp += 1
        elif lo == 0x57:
            s.attr[5 * s.an + s.ab] = v
            if s.ab == 3 and not v & 0x40:
                s.attr[5 * s.an + 4] = 0
                s.an, s.ab = (s.an + 1) & 127, 0
            elif s.ab == 4:
                s.an, s.ab = (s.an + 1) & 127, 0
            else:
                s.ab += 1
        else:
            s.events.append(('out', port, v))


def sprite127_on_top(setup):
    """The stacking order a build's setup bytes choose: NEXTREG 0x15,n (ED 91 15 n) with bit 6 clear puts sprite 127
    on top, set puts sprite 0 on top (Quazatron's hardware note); no such write: the reset value 0, sprite 127."""
    b = bytes(setup)
    i = b.rfind(b'\xED\x91\x15')
    return i < 0 or i + 3 >= len(b) or not b[i + 3] & 0x40


def render(ns, top127=True):
    """The visible sprites as {(X, Y): (pixel, bank)} in sprite coordinates (the screen's top-left = (32, 32)), the
    on-top sprite painted last (top127: sprite 127 on top, as sprite127_on_top(setup) says) -> (pixels, problems)."""
    px, bad = {}, []
    a, pat = ns.attr, ns.pat
    for n in (range(128) if top127 else range(127, -1, -1)):
        b0, b1, b2, b3, b4 = a[5 * n:5 * n + 5]
        if not b3 & 0x80:
            continue
        if not (b3 & 0x40 and b4 & 0x80):
            bad.append(('sprite %d is not a 4-bit anchor' % n, b3, b4))
            continue
        X, Y = b0 | (b2 & 1) << 8, b1 | (b4 & 1) << 8
        base, bank, xm = (b3 & 0x3F) << 8 | (b4 >> 6 & 1) << 7, b2 >> 4, b2 >> 3 & 1
        for r in range(16):
            for c in range(16):
                v = pat[base + r * 8 + c // 2]
                v = v >> 4 if c % 2 == 0 else v & 15
                if v:
                    px[(X + (15 - c if xm else c)) & 0x1FF, (Y + r) & 0x1FF] = (v, bank)
    return px, bad


def figure_of(pc, regs, get):
    """The figure a draw at site pc is about to make, from the original's state there."""
    ix = regs[8] << 8 | regs[9]
    t = get(ix + 2)
    width = 2 if pc == 0x80C9 else 3
    rows = (16 if t & 1 else 24) if pc == 0x80C9 else (24 if t & 4 else 32 if t & 8 else 40)
    h, l = regs[6], regs[7]
    x = (l & 31) * 8 + regs[0]
    y = (h & 0x18) << 3 | (l & 0xE0) >> 2 | (h & 7)
    attr = get(0x5800 + (y >> 3) * 32 + ((x + width * 4) >> 3 & 31))
    return dict(gfx=regs[20] << 8 | regs[21], mask=regs[4] << 8 | regs[5], rows=rows, width=width, x=x, y=y,
                mirror=not get(ix + 4) & 1, bank=(attr >> 3 & 7) | (8 if attr & 0x40 else 0))


def figure_pixels(f, get):
    """{(x, y): 1 graphics / 2 mask clear} of a figure on the screen (rows stored bottom first; the mirrored draw
    flips the image across its width, at the same place)."""
    out = {}
    w8 = f['width'] * 8
    for r in range(f['rows']):
        for b in range(f['width']):
            g = get((f['gfx'] + r * f['width'] + b) & 0xFFFF)
            m = get((f['mask'] + r * f['width'] + b) & 0xFFFF)
            for bit in range(8):
                gb, mb = g >> (7 - bit) & 1, m >> (7 - bit) & 1
                v = 1 if gb else 2 if not mb else 0
                if v:
                    c = b * 8 + bit
                    out[f['x'] + (w8 - 1 - c if f['mirror'] else c), f['y'] - r] = v
    return out


def _overlays(base, vpage, psite, state=STATE, scratch=SCRATCH):
    class O:
        """The original: ROM below 0x4000 (writes go nowhere), RAM from the replay."""
        def __init__(s):
            s.w = {}

        def __getitem__(s, a):
            v = s.w.get(a)
            return base[a] if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.w[a] = v

        def __len__(s):
            return 65536

    class P(O):
        """The patched build: its page at 0x2000-0x3FFF (RAM, kept across the replay), the sites' new bytes."""
        def __init__(s):
            O.__init__(s)
            s.page = vpage
            s.pw = {}
            s.err = []
            s.R = None

        def __getitem__(s, a):
            if 0x2000 <= a < 0x4000:
                return s.page[a - 0x2000]
            v = psite.get(a)
            if v is not None and a not in s.w:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if 0x2000 <= a < 0x4000:
                hook = s.R is not None and 0x2000 <= s.R[24] < 0x4000
                if state[0] <= a < state[1] and not hook:
                    s.err.append(('game code wrote the hook state', a, s.R[24] if s.R else None))
                if not state[0] <= a < state[1] and not scratch[0] <= a < scratch[1]:
                    s.err.append(('write to the page outside state and scratch', a))
                s.page[a - 0x2000] = v
                s.pw[a] = v
            elif a < 0x2000:
                s.err.append(('write to the ROM area', a))
            else:
                if a in psite:
                    s.err.append(('wrote a patch site', a))
                s.w[a] = v
    return O, P


def _writable_slot1(sim, store):
    """SkoolKit drops every write below 0x4000 (its opcodes test addr > 0x3FFF); on the Next slot 1 is this build's
    RAM page. Wrap the store opcodes the draw uses so a write into 0x2000-0x3FFF reaches the page: LD (HL),r,
    LD (HL),n, LD (DE),A, LD (BC),A, LD (IY+d),r / n. The hooks' own stores (LD (nn),A / rr, PUSH on the hook stack, LD (IX+d)) go
    through other opcodes: wrapped too where a hook uses them (_hook_stores)."""
    R, mem, ops = sim.registers, sim.memory, sim.opcodes

    def wrap(table, op, target, value):
        fn = table[op]

        def g():
            a = target()
            if 0x2000 <= a < 0x4000:
                v = value()
                fn()
                store(a, v)
            else:
                fn()
        table[op] = g
    hl = lambda: R[6] << 8 | R[7]
    for op, ri in {0x70: 2, 0x71: 3, 0x72: 4, 0x73: 5, 0x74: 6, 0x75: 7, 0x77: 0}.items():
        wrap(ops, op, hl, lambda ri=ri: R[ri])
    wrap(ops, 0x36, hl, lambda: mem[(R[24] + 1) & 0xFFFF])
    wrap(ops, 0x12, lambda: R[4] << 8 | R[5], lambda: R[0])
    wrap(ops, 0x02, lambda: R[2] << 8 | R[3], lambda: R[0])
    iyd = lambda: ((R[10] << 8 | R[11]) + ((mem[(R[24] + 2) & 0xFFFF] ^ 0x80) - 0x80)) & 0xFFFF
    fd = sim.after_FD                       # LD (IY+d),r / n: Jack the Nipper II's blits address the buffer through IY
    for op, ri in {0x70: 2, 0x71: 3, 0x72: 4, 0x73: 5, 0x74: 6, 0x75: 7, 0x77: 0}.items():
        wrap(fd, op, iyd, lambda ri=ri: R[ri])
    wrap(fd, 0x36, iyd, lambda: mem[(R[24] + 3) & 0xFFFF])
    _hook_stores(sim, store)


def _hook_stores(sim, store):
    """The stores the hook code makes in its page (state and stack): run each instruction, then write what the Next
    would have written, for the forms the hooks use: LD (nn),A; LD (nn),HL; LD (nn),rr (ED); LD (nn),SP (ED 73);
    PUSH rr, PUSH IX / IY, CALL and CALL cc (to the hook stack); LD (IX+d),r / n. A form missed here leaves the page short of a byte and the
    sprite check fails."""
    R, mem, ops, ed = sim.registers, sim.memory, sim.opcodes, sim.after_ED

    def pre(table, op, writes):
        fn = table[op]

        def g():
            ws = [(a, v) for a, v in writes() if 0x2000 <= a < 0x4000]
            fn()
            for a, v in ws:
                store(a, v)
        table[op] = g
    nn = lambda: mem[(R[24] + 1) & 0xFFFF] | mem[(R[24] + 2) & 0xFFFF] << 8
    nn_ed = lambda: mem[(R[24] + 2) & 0xFFFF] | mem[(R[24] + 3) & 0xFFFF] << 8
    pre(ops, 0x32, lambda: [(nn(), R[0])])
    pre(ops, 0x22, lambda: [(nn(), R[7]), ((nn() + 1) & 0xFFFF, R[6])])
    for op, (hi, lo) in {0x43: (2, 3), 0x53: (4, 5), 0x63: (6, 7)}.items():
        pre(ed, op, lambda hi=hi, lo=lo: [(nn_ed(), R[lo]), ((nn_ed() + 1) & 0xFFFF, R[hi])])
    pre(ed, 0x73, lambda: [(nn_ed(), R[12] & 255), ((nn_ed() + 1) & 0xFFFF, R[12] >> 8)])
    sp2 = lambda hi, lo: [((R[12] - 1) & 0xFFFF, R[hi]), ((R[12] - 2) & 0xFFFF, R[lo])]
    for op, (hi, lo) in {0xC5: (2, 3), 0xD5: (4, 5), 0xE5: (6, 7), 0xF5: (0, 1)}.items():
        pre(ops, op, lambda hi=hi, lo=lo: sp2(hi, lo))
    ret_to = lambda n: (R[24] + n) & 0xFFFF
    pre(ops, 0xCD, lambda: [((R[12] - 1) & 0xFFFF, ret_to(3) >> 8), ((R[12] - 2) & 0xFFFF, ret_to(3) & 255)])
    taken = {0xC4: lambda f: not f & 0x40, 0xCC: lambda f: f & 0x40, 0xD4: lambda f: not f & 1, 0xDC: lambda f: f & 1,
             0xE4: lambda f: not f & 4, 0xEC: lambda f: f & 4, 0xF4: lambda f: not f & 0x80, 0xFC: lambda f: f & 0x80}
    for op, cc in taken.items():            # CALL cc: the return address only when the call is taken
        pre(ops, op, lambda cc=cc: [((R[12] - 1) & 0xFFFF, ret_to(3) >> 8), ((R[12] - 2) & 0xFFFF, ret_to(3) & 255)]
            if cc(R[1]) else [])
    dd = sim.after_DD
    pre(dd, 0xE5, lambda: [((R[12] - 1) & 0xFFFF, R[8]), ((R[12] - 2) & 0xFFFF, R[9])])     # PUSH IX
    pre(sim.after_FD, 0xE5, lambda: [((R[12] - 1) & 0xFFFF, R[10]), ((R[12] - 2) & 0xFFFF, R[11])])     # PUSH IY
    ixd = lambda: ((R[8] << 8 | R[9]) + ((mem[(R[24] + 2) & 0xFFFF] ^ 0x80) - 0x80)) & 0xFFFF
    for op, ri in {0x70: 2, 0x71: 3, 0x72: 4, 0x73: 5, 0x74: 6, 0x75: 7, 0x77: 0}.items():
        pre(dd, op, lambda ri=ri: [(ixd(), R[ri])])
    pre(dd, 0x36, lambda: [(ixd(), mem[(R[24] + 3) & 0xFFFF])])


EXEC_PCS = set()            # every hook-page PC a patched run executed (store_form_problems checks them)


def _run(sim, sp0, span, limit=5000000, record=False):
    """Step until the code has returned to its caller: PC outside span with SP above the site's SP. record: note the
    hook-page PCs run (EXEC_PCS)."""
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    for _ in range(limit):
        pc = R[24]
        if 0x2000 <= pc < 0x4000:
            if record:
                EXEC_PCS.add(pc)
        elif not span[0] <= pc < span[1] and R[12] > sp0:
            return True
        ops[mem[pc]]()
    return False


# Memory-writing instructions by prefix, and those _writable_slot1 / _hook_stores model for the slot-1 page.
_W_MAIN = {0x02, 0x12, 0x22, 0x32, 0x34, 0x35, 0x36, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x77, 0xE3,
           0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC, 0xCD, 0xC5, 0xD5, 0xE5, 0xF5,
           0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}
_W_ED = {0x43, 0x53, 0x63, 0x73, 0x67, 0x6F, 0xA0, 0xA8, 0xB0, 0xB8, 0xA2, 0xAA, 0xB2, 0xBA}
_W_XY = {0x22, 0x34, 0x35, 0x36, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x77, 0xE3, 0xE5}
_M_MAIN = {0x02, 0x12, 0x22, 0x32, 0x36, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x77,
           0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC, 0xCD, 0xC5, 0xD5, 0xE5, 0xF5}
_M_ED = {0x43, 0x53, 0x63, 0x73}
_M_DD = {0x36, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x77, 0xE5}
_M_FD = {0x36, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x77, 0xE5}


def store_form_problems(get, pcs):
    """Hook-page instructions that write memory in a form the slot-1 model does not carry into the page (SkoolKit
    would drop the write silently): [(pc, bytes)]. get(addr) -> byte; pcs: the executed PCs (EXEC_PCS)."""
    out = []
    for pc in sorted(pcs):
        b0, b1, b3 = get(pc), get((pc + 1) & 0xFFFF), get((pc + 3) & 0xFFFF)
        if b0 == 0xCB:
            w, m = (b1 & 7) == 6 and not 0x40 <= b1 < 0x80, False
        elif b0 == 0xED:
            w, m = b1 in _W_ED, b1 in _M_ED
        elif b0 in (0xDD, 0xFD):
            if b1 == 0xCB:
                w, m = not 0x40 <= b3 < 0x80, False
            else:
                w, m = b1 in _W_XY, b1 in (_M_DD if b0 == 0xDD else _M_FD)
        else:
            w, m = b0 in _W_MAIN, b0 in _M_MAIN
        if w and not m:
            out.append(('%04X' % pc, bytes(get((pc + k) & 0xFFFF) for k in range(4)).hex()))
    return out


def restored_boot_check(path, z80, patch, nexload=False):
    """Boot the .nex on through the tail's restore (restore_tail) to the snapshot's own PC, and compare every register
    and RAM 0x4000-0xFFFF, the tail's bytes too, with the snapshot (its sites patched). nextboot.check stops at the
    restore's entry and leaves the tail out. -> problems"""
    import copy
    from . import z80tonex as zt, nextboot
    s = zt.Z80Snapshot(z80)
    p = copy.deepcopy(patch)
    p.apply(s)
    pc0 = getattr(p, 'original_pc', s.pc)
    try:
        st = nextboot.boot(path, pc0, nexload=nexload, sysrom=nextboot.system_rom3()[0])
    except (ValueError, RuntimeError) as e:
        return [('boot never reached the game start', '%04X' % pc0, str(e)[:120])]
    R, mem = st['R'], st['mem']
    w = lambda h, l: R[h] * 256 + R[l]
    got = {'BC': w(2, 3), 'DE': w(4, 5), 'HL': w(6, 7), 'AF': w(0, 1), 'IX': w(8, 9), 'IY': w(10, 11),
           "BC'": w(18, 19), "DE'": w(20, 21), "HL'": w(22, 23), "AF'": w(16, 17), 'SP': R[12], 'I': R[14],
           'IM': R[27], 'IFF': R[26]}
    exp = {'BC': s.bc, 'DE': s.de, 'HL': s.hl, 'AF': s.a * 256 + s.f, 'IX': s.ix, 'IY': s.iy,
           "BC'": s.bc_, "DE'": s.de_, "HL'": s.hl_, "AF'": s.a_ * 256 + s.f_, 'SP': s.sp, 'I': s.i,
           'IM': s.im, 'IFF': s.iff1}
    bad = [('register at the game start', k, got[k], exp[k]) for k in exp if got[k] != exp[k]]
    ram = s.banks[5] + s.banks[2] + s.banks[0]
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000]]
    if diffs:
        bad.append(('RAM at the game start differs (the tail too)', len(diffs), ['%04X' % a for a in diffs[:6]]))
    return bad


RUN_ON = 400000             # dead_after: at most this many (Jack's own draw, the last of a frame: up to ~185,000)
SOLO_ON = 40000000          # dead_after: one machine on to the next EXX (a 65,536 x 256 delay loop: ~33M)


def dead_after(base, writes, regs, idx, alt, n=RUN_ON):
    """Whether register idx (H') is dead after the draw: the original machine run on from its return state, once as
    it is and once with idx = alt, in lockstep. The difference may travel (EXX at 0x8014 swaps it into H, EX DE,HL
    at 0x8240 into D); it is dead when every register agrees again (overwritten, for H by the next CALL 0x87BB) and
    memory agrees then too, apart from popped bytes below SP (0x85D0 pushes HL), with both machines on the same PC at
    every step on the way. A different path, or no agreement within n instructions: live. An alternate register is
    read only by EXX, so one machine first runs on to the next EXX (SOLO_ON at most: a delay loop between)."""
    from skoolkit.simulator import Simulator
    from .hooklib import CMP
    mem = bytearray(base)
    for a, v in writes.items():
        mem[a] = v
    if idx in (18, 19, 20, 21, 22, 23):
        # An alternate register is read only through EXX (DD / FD EXX too): until the first one the two machines run
        # identically, so run one on to it (a delay loop can take millions of instructions), then compare in lockstep.
        one = Simulator(bytearray(mem), {})
        one.registers[:] = list(regs)
        r1, m1 = one.registers, one.memory
        for _ in range(SOLO_ON):
            pc = r1[24]
            op = m1[pc]
            if op == 0xD9 or (op in (0xDD, 0xFD) and m1[(pc + 1) & 0xFFFF] == 0xD9):
                break
            one.opcodes[op]()
        else:
            return False
        regs, mem = list(r1), bytearray(m1)
    sims = []
    for v in (regs[idx], alt):
        r = list(regs)
        r[idx] = v
        sim = Simulator(bytearray(mem), {})
        sim.registers[:] = r
        sims.append(sim)
    A, B = sims
    ra, rb = A.registers, B.registers
    for _ in range(n):
        A.opcodes[A.memory[ra[24]]]()
        B.opcodes[B.memory[rb[24]]]()
        if ra[24] != rb[24]:
            return False
        if all(ra[i] == rb[i] for i in CMP):
            if A.memory == B.memory:
                return True
            sp = ra[12]
            return all(sp - 0x100 <= a < sp for a in range(65536) if A.memory[a] != B.memory[a])
    return False


def pair(patch, regs, base, vpage, vns, span):
    """One site from one state, original and patched (the patched page and Next side carried across the replay).
    -> (failures, allowed, details, original writes, patched page writes)"""
    import collections
    from skoolkit.simulator import Simulator
    from .hooklib import CMP
    from .simpool import machine
    from . import z80n
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    O, P0 = _overlays(base, vpage, psite)
    banks = getattr(patch, 'extra_banks', {})

    class P(P0):
        """Slot 0 shows the Next page NR 0x50 names (the painted colours' table inside ovr), else the ROM."""
        def __getitem__(s, a):
            if a < 0x2000:
                pg = vns.nr.get(0x50, 0xFF)
                if pg != 0xFF:
                    d = banks.get(pg // 2)
                    return d[(pg % 2) * 8192 + a] if d else 0
            return P0.__getitem__(s, a)
    o, p = O(), P()
    so = machine(Simulator, o, list(regs), 'jo')
    sp = Simulator(p, {})                   # not pooled: its opcodes are wrapped for the slot-1 page
    sp.registers[:] = list(regs)
    p.R = sp.registers
    _writable_slot1(sp, p.__setitem__)
    z80n.install(sp, vns.nextreg)
    sp.set_tracer(vns)
    vns.events = []
    speed0 = vns.nr.get(0x07, 0)
    bad, ok, det = collections.Counter(), collections.Counter(), []
    sp0 = regs[12]
    shown0 = {vns.attr[5 * n + 3] & 0x3F for n in range(128) if vns.attr[5 * n + 3] & 0x80}   # on screen at entry
    pat0 = bytes(vns.pat)
    if not (_run(so, sp0, span) and _run(sp, sp0, span, record=True)):
        bad['did not return!'] += 1
        return bad, ok, det, o.w, p.pw
    if so.registers[24] != sp.registers[24]:
        bad['returned elsewhere!'] += 1
        det.append(('return PC', '%04X' % so.registers[24], '%04X' % sp.registers[24]))
    for e in p.err:
        bad[e[0] + '!'] += 1
        det.append(e)
    if vns.events:
        bad['port access outside the Next side!'] += 1
        det.append(('ports', vns.events[:4]))
    if vns.nr.get(0x07, 0) != speed0:
        bad['CPU speed not given back!'] += 1
    if vns.nr.get(0x50, 0xFF) != 0xFF:
        bad['slot 0 not given back to the ROM!'] += 1
    hit = sorted(n for n in shown0 if vns.pat[n * 256:n * 256 + 256] != pat0[n * 256:n * 256 + 256])
    if hit:                                 # a sprite still on screen (the last update's) shows the new image until the
        bad['pattern of a sprite on screen overwritten!'] += 1      # attributes are written (card optimise.pattern-cache)
        det.append(('pattern slots overwritten while shown', hit[:6]))
    ro, rp = so.registers, sp.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff == [22] and rp[22] == ro[22] - 0x40:
        # H' holds the draw's last address, moved like H: dead if the game overwrites it before reading it
        if dead_after(base, o.w, ro, 22, rp[22]):
            ok["H' moved address (dead)"] += 1
        else:
            bad["H' moved address read later!"] += 1
    elif diff:
        bad['registers differ!'] += 1
        det.append(('registers', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    shadow_o = {a: v for a, v in o.w.items() if SHADOW[0] <= a < SHADOW[1]} if span is DRAW else {}
    rest_o = {a: v for a, v in o.w.items() if a not in shadow_o}
    shadow_p = {a for a in p.w if SHADOW[0] <= a < SHADOW[1]} if span is DRAW else set()
    rest_p = {a: v for a, v in p.w.items() if a not in shadow_p}
    if shadow_p:
        bad['patched draw wrote the real shadow!'] += 1
        det.append(('shadow writes', sorted(shadow_p)[:6]))
    stack = {a for a in set(rest_o) | set(rest_p) if ro[12] - 0x100 <= a < ro[12] and rest_o.get(a) != rest_p.get(a)}
    if stack and all(rest_p.get(a) == rest_o.get(a, -1) - 0x40 for a in stack):
        ok['stack below SP: pushed address moved (dead)'] += 1      # popped bytes below the caller's SP
        for a in stack:
            rest_o.pop(a, None)
            rest_p.pop(a, None)
    if rest_o != rest_p:
        bad['memory differs!'] += 1
        ks = sorted(set(rest_o) ^ set(rest_p) | {a for a in rest_o if rest_p.get(a) != rest_o[a]})
        det.append(('memory', ['%04X' % a for a in ks[:8]]))
    if span is DRAW:
        moved = {a - 0x4000 for a in shadow_o}
        scratch = {a for a in p.pw if SCRATCH[0] <= a < SCRATCH[1]}
        if moved != scratch:
            bad['scratch writes are not the shadow writes moved by 0x4000!'] += 1
            det.append(('scratch', len(moved), len(scratch), sorted(moved ^ scratch)[:6]))
    return bad, ok, det, o.w, p.pw


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Differential test (PLAYBOOK 6). Figure sites: the redirect (pair). Copier entry: the commit, then the picture:
    the figures drawn since the last copy, modelled from their graphics and masks, must (1) give the original's shadow
    bytes over the background they were drawn on, and (2) be the visible sprites, pixel for pixel, with the colour
    bank and mirror the design gives and the later figure on top. -> (Counter, examples, states)"""
    import collections
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    vpage = bytearray(patch.page)
    vns = NextSide()
    upd = {'figs': [], 'pre': {}}
    last = [None]
    EXEC_PCS.clear()
    sites = {a: bytes.fromhex(o) for a, o in SITES_ORIG.items()}

    def fail(k, info):
        c[k] += 1
        if len(ex[k]) < 5:
            ex[k].append(info)

    def on(pc, sim):
        if not c['space glyph repaired (dump)'] and bytes(sim.memory[SPACE_GLYPH:SPACE_GLYPH + 8]) == DUMP_KSTATE:
            sim.memory[SPACE_GLYPH:SPACE_GLYPH + 8] = bytes(8)     # the original replayed with the build's repair
            c['space glyph repaired (dump)'] += 1                   # (only the text printers read it)
        if pc in INTERIOR_PREV:             # the patched bytes' insides: only by running on from the site itself
            if INTERIOR_PREV[pc] is None or last[0] != INTERIOR_PREV[pc]:
                fail('jump into a patched instruction!', hex(pc))
            last[0] = pc
            return
        last[0] = pc
        regs, base = list(sim.registers), bytes(sim.memory[:65536])
        get = base.__getitem__
        for a, o in sites.items():
            if base[a:a + len(o)] != o:
                fail('the game rewrote a patch site!', '%04X' % a)
        c[SITE_KIND[pc]] += 1
        if pc in (0x80C9, 0x8273):
            upd['figs'].append(figure_of(pc, regs, get))
            bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, DRAW)
            for a in ow:
                if SHADOW[0] <= a < SHADOW[1]:
                    upd['pre'].setdefault(a, base[a])
                    c['figure bytes redirected'] += 1
        else:
            bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, COPY)
            picture(get)
        for k, n in ok.items():
            c[k] += n
        for k, n in bad.items():
            for _ in range(n):
                fail(k, (hex(pc), det))
        if collect and sum(1 for x in states if x[0] == pc) < collect:      # up to collect states per site
            states.append((pc, regs, base))

    def picture(get):
        figs, pre = upd['figs'], upd['pre']
        exp = {}
        for f in figs:                      # later over earlier
            keys = figure_keys(f) if patch.ovr else None
            for (x, y), v in figure_pixels(f, get).items():
                n = patch.ovr.get(keys[x, y][0]) if keys else None
                pv = n[keys[x, y][1]] if n and n[keys[x, y][1]] else v      # a painted colour, else 1 black / 2 body
                exp[x, y] = (pv, f['bank'], v)                   # (sprite pixel, bank, 1 ink / 2 body)
        # (1) the model against the original's own drawing: every byte the draws touched
        for a, b0 in pre.items():
            y = (a >> 5 & 0xC0) | (a >> 8 & 7) | (a >> 2 & 0x38)
            x0 = (a & 31) * 8
            want = 0
            for bit in range(8):
                v = exp.get((x0 + bit, y))
                pb = b0 >> (7 - bit) & 1 if v is None else (1 if v[2] == 1 else 0)
                want |= pb << (7 - bit)
            if want != get(a):
                fail('figure model differs from the original drawing!', ('%04X' % a, want, get(a)))
        c['picture bytes checked'] += len(pre)
        # (2) the visible sprites against the model, in the play area
        got, bad = render(vns, sprite127_on_top(patch.stub_extra))
        for b in bad:
            fail('sprite attributes!', b)
        want = {(x + 32, y + 32): v[:2] for (x, y), v in exp.items() if 0 <= x < PLAY[0] and 0 <= y < PLAY[1]}
        have = {k: v for k, v in got.items() if 32 <= k[0] < 32 + PLAY[0] and 32 <= k[1] < 32 + PLAY[1]}
        if want != have:
            d = sorted(set(want) ^ set(have) | {k for k in want if have.get(k) != want[k]})
            fail('SPRITE PIXEL difference!', (len(d), d[:4], [(want.get(k), have.get(k)) for k in d[:4]]))
        c['sprite pixels compared'] += len(want)
        upd['figs'], upd['pre'] = [], {}

    frames, err = RZ.trace(rzx_path, set(SITE_KIND) | set(INTERIOR_PREV), on, stop=stop)
    probs = store_form_problems(lambda a: vpage[a - 0x2000] if 0x2000 <= a < 0x4000 else 0, EXEC_PCS)
    for pr in probs:
        fail('unmodelled store form in the hook page!', pr)
    c['frames'] = frames
    if err:
        fail('replay desync!', err)
    return c, dict(ex), states


# ---------------------------------------------------------------------------------------------
# Unit tests and negative controls (CLAUDE.md: paths the recording does not reach, and broken builds caught)
# ---------------------------------------------------------------------------------------------

def _sym(patch, name):
    return patch.syms[name] - 0x2000


def negative_patches(patch=None):
    """Broken builds the verifier must catch: {name: patch}."""
    import copy
    base = patch or JtnPatch()
    out = {}

    def make(name, edits):
        p = copy.deepcopy(base)
        pg = bytearray(p.page)
        for off, b in edits:
            pg[off:off + len(b)] = b
        p.page = bytes(pg)
        p.extra_banks = {JTN_PAGE // 2: p.page + bytes(8192)}
        out[name] = p
    make('no redirect (RES 6,H dropped)', [(_sym(base, 'e_d16.n_res16'), b'\x00\x00'), (_sym(base, 'e_d24.n_res24'), b'\x00\x00')])
    make('never mirrored', [(_sym(base, 'attrs.n_mir') + 1, b'\x00')])
    make('wrong colour bank (the mirror flag)', [(_sym(base, 'attrs.n_bank') + 2, b'\x08')])
    make('leftover sprites not hidden', [(_sym(base, 'commit.n_hide'), b'\x7A\x00\x00')])
    make("caller's speed not given back", [(_sym(base, 'e_cmt.n_spd') + 4, b'\x00\x00\x00')])
    make("a slot on screen from the last update taken", [(_sym(base, 'slot.n_prev'), b'\x18')])     # JR NZ -> JR
    p = copy.deepcopy(base)                 # the setup's NR 0x15 with bit 6 set: sprite 0 on top
    p.stub_extra = bytes(p.stub_extra).replace(b'\xED\x91\x15\x01', b'\xED\x91\x15\x41')
    out['later figures under earlier (NR 0x15 bit 6)'] = p
    return out


SPRITES_WRONG = 'SPRITE PIXEL difference!'
NEG_EXPECT = {                              # the failure each control must give (another one is not a detection)
    'no redirect (RES 6,H dropped)': {'patched draw wrote the real shadow!',
                                      'scratch writes are not the shadow writes moved by 0x4000!'},
    'never mirrored': {SPRITES_WRONG}, 'wrong colour bank (the mirror flag)': {SPRITES_WRONG},
    'leftover sprites not hidden': {SPRITES_WRONG}, "caller's speed not given back": {'CPU speed not given back!'},
    'later figures under earlier (NR 0x15 bit 6)': {SPRITES_WRONG},
    'a slot on screen from the last update taken': {'pattern of a sprite on screen overwritten!'}}


def negative_results(negs, rzx, frames, expect, verify_fn):
    """Each negative control's verify: 'DETECTED' only when it gives a failure it is expected to give. -> Counter"""
    import collections
    c = collections.Counter()
    for name, np_ in negs.items():
        cc, ex, _ = verify_fn(np_, rzx, stop=frames)
        got = {k for k in cc if k.endswith('!')}
        res = 'DETECTED' if got & expect.get(name, set()) else ('caught for another reason (%s)!' % sorted(got)[:2]
                                                                   if got else 'MISSED!')
        c['negative %s: %s' % (name, res)] += 1
    return c


def store_form_case():
    """store_form_problems on LD (0x3000),IX (DD 22 00 30: unmodelled, so a hook using it would pass blind) and on
    LD (0x3000),HL (22 00 30: modelled). -> 'ok' or a failure ending in '!'"""
    code = {0x3000: 0xDD, 0x3001: 0x22, 0x3002: 0x00, 0x3003: 0x30, 0x3004: 0x22, 0x3005: 0x00, 0x3006: 0x30}
    got = store_form_problems(lambda a: code.get(a, 0), {0x3000, 0x3004})
    return 'ok' if [g[0] for g in got] == ['3000'] else 'FAIL!'


def capture(rzx_path, stop=None):
    """Every figure image the game draws in a recording: {(gfx, mask, width, rows): {'count', 'frame'}}."""
    from . import rzx as RZ
    seen, n = {}, [0]

    def on(pc, sim):
        m = sim.memory
        f = figure_of(pc, list(sim.registers), lambda a: m[a])
        e = seen.setdefault((f['gfx'], f['mask'], f['width'], f['rows']), {'count': 0, 'frame': n[0]})
        e['count'] += 1
        n[0] += 1
    frames, err = RZ.trace(rzx_path, {0x80C9, 0x8273}, on, stop=stop)
    return seen, frames, err


def image_part(get, g, mk, w, rows):
    """The coloursheet part of image (g, mask, w, rows), top row first: ink (code 1, default 1 black) and body
    (code 2, default 2: the cell's paper) pixels keyed by the graphics byte; see-through pixels code 0."""
    px, ent = [], {}
    for y in range(rows):
        r = rows - 1 - y                    # memory row: the bottom row first
        for b in range(w):
            ga, ma = (g + r * w + b) & 0xFFFF, (mk + r * w + b) & 0xFFFF
            gb, m = get(ga), get(ma)
            key = '%04X' % ga
            ent[key] = [gb, 'g']
            for bit in range(8):
                c = 1 if gb >> (7 - bit) & 1 else 2 if not m >> (7 - bit) & 1 else 0
                px.append((b * 8 + bit, y, key, bit, c, c))
    return {'id': '%04X:%dx%d' % (g, w, rows), 'size': 1, 'w': 8 * w, 'h': rows, 'x': 0, 'y': 0, 'mir': 0,
            'pixels': px, 'entries': ent, 'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0, 'group': 0}


def colour_identity(peek, imgs=None):
    """What a colour map / sheet means for this build (docs/COLOURS.md "Identity"): key = graphics byte, bit = pixel;
    inputs = the game's bytes over the painted-colour table's range (no patch site or tail lies there)."""
    import hashlib
    return {'schema': 1, 'game': RECORD, 'engine': RECORD, 'keys': 'jack_the_nipper-gfx-1: %04X graphics byte, bit = pixel',
            'inputs': hashlib.md5(bytes(peek(a) for a in range(OVR_BASE, OVR_BASE + OVR_SPAN))).hexdigest(), 'geometry': None}


# nexclash/recolour.py: `python nexclash.py recolour <name>_enhanced.nex PAINTED.png` (seconds, no rebuild): only the
# painted-colour table's banks change; the game never reads them (slot 0 inside ovr).
NOTE = ('Jack the Nipper colour map (docs/COLOURS.md): key = graphics byte (hex address; check = its value); 8 nibbles, '
        '0 = the default (1 black lines, 2 the body: the paper of the cell under the figure), 3-15 the painting palette')
RECOLOUR = {'game': RECORD, 'output': 'enhanced', 'colours': 'docs/profiles/' + RECORD + '_colours.json', 'clear': False,
            'note': NOTE}


def recolour(nex, cmap):
    """This engine's Enhanced .nex bytes + colour map -> (new .nex bytes, info). Refuses anything else."""
    from .recolour import banks, splice
    have = banks(nex)
    pb = JTN_PAGE // 2
    tb = sorted({pg // 2 for pg in ovr_pages({}, OVR_BASE, OVR_SPAN, OVR_PAGE0)})
    need = {5, 2, 0, pb} | set(tb)
    if not need <= set(have):
        raise ValueError('not a Jack the Nipper Enhanced build: banks %s missing (recolour the _enhanced.nex)'
                         % sorted(need - set(have)))
    ram = have[5] + have[2] + have[0]
    peek = lambda a: ram[a - 0x4000]
    page = have[pb][(JTN_PAGE % 2) * 8192:(JTN_PAGE % 2) * 8192 + 8192]
    p0 = JtnPatch(enhanced=True)
    if page[V_OVR - 0x2000] != 1:
        raise ValueError('not an Enhanced build (recolour the _enhanced.nex)')
    o = CODE_ORG - 0x2000
    code = p0.page[o:o + len(bytes.fromhex(p0.prof['hooks']['page']))]
    if page[o:o + len(code)] != code:
        raise ValueError("hook code differs from this version's (rebuild with nexclash.py auto)")
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook jump" % a)
    ovr, info = ovr_entries(peek, cmap, OVR_BASE, OVR_SPAN)
    new = {b: have[b] for b in tb}
    add_pages(new, ovr_pages(ovr, OVR_BASE, OVR_SPAN, OVR_PAGE0))
    out, changed = splice(nex, new)
    info = dict(info)
    info['banks changed'] = changed
    return out, info


ENH_FRAMES = 6000                   # the Enhanced build's replay: its patterns differ from the default's only by the
                                    # painted table (asm ovr); the hooks are the same code


def enhanced_checks(z80, rzx, quick, say):
    """The Enhanced build with its colour map, replayed on the first ENH_FRAMES of the first recording (every sprite
    pixel the painted colour or 1 / 2, in the cell's bank); then a build painting every graphics byte of the table, and
    the same with the paint left out (its own failure). -> ok"""
    import copy
    from . import z80tonex as zt
    n = min(quick or ENH_FRAMES, ENH_FRAMES)
    pe = JtnPatch(colours=load_colours(), enhanced=True)
    pe.apply(zt.Z80Snapshot(z80))
    c, ex, _ = verify(pe, rzx, stop=n)
    fails = {k: v for k, v in c.items() if k.endswith('!')}
    say('Enhanced  : %s  %d frames, %d painted graphics bytes, sprite pixels %d -> %s' % (
        os.path.basename(rzx), c['frames'], len(pe.ovr), c['sprite pixels compared'],
        'IDENTICAL' if not fails else 'FAILED %s' % fails))
    ok = not fails
    get = zt.Z80Snapshot(z80).read
    cmap = {'%04X' % a: [get(a), 'g', [((a >> 3) + k) % 13 + 3 if (a + k) % 3 else 0 for k in range(8)]]
            for a in range(OVR_BASE, OVR_BASE + OVR_SPAN)}
    pt = JtnPatch(colours=cmap, enhanced=True)
    pt.apply(zt.Z80Snapshot(z80))
    m = min(n, 1500)
    c, ex, _ = verify(pt, rzx, stop=m)
    f2 = {k: v for k, v in c.items() if k.endswith('!')}
    q = copy.deepcopy(pt)
    pg = bytearray(q.page)
    pg[q.syms['ovr.n_ovr'] - 0x2000] = 0
    q.page = bytes(pg)
    q.extra_banks = dict(q.extra_banks)
    q.extra_banks[JTN_PAGE // 2] = q.page + bytes(8192)
    cq, _, _ = verify(q, rzx, stop=m)
    det = SPRITES_WRONG in cq
    say('Enh unit  : every graphics byte painted, %d frames -> %s; negative painted colours left out: %s' % (
        m, 'IDENTICAL' if not f2 else 'FAILED %s' % f2, 'DETECTED' if det else 'MISSED!'))
    return ok and not f2 and det


def sheets(rzx_path, z80, out_dir, prefix=RECORD, colours=None, stop=None, say=print):
    """<prefix>_PAINTING_SPRITES.png + _REFERENCE_ALL_SPRITES.png (every image) in the painting palette (index 2, the
    body, shown light grey: on the Next it is the paper of the cell under the figure), each with its _layout.json."""
    from . import coloursheet as cs
    from . import z80tonex as zt
    seen, frames, err = capture(rzx_path, stop)
    if err:
        say('capture   : stopped at frame %d: %s' % (frames, err))
    get = zt.Z80Snapshot(z80).read
    comps = []
    for (g, mk, w, rows), e in sorted(seen.items(), key=lambda t: t[1]['frame']):
        if not OVR_BASE <= g and g + w * rows <= OVR_BASE + OVR_SPAN:
            say('            image %04X (%d x %d) is outside the painted-colour table (built by the game at run time): '
                'not on the sheets' % (g, w, rows))
            continue
        part = image_part(get, g, mk, w, rows)
        if any(q[4] for q in part['pixels']):
            comps.append({'count': e['count'], 'group': 0, 'parts': [part]})
    pal = palette()
    cmap = load_colours() if colours is None else colours
    rgb = cs.palette_rgb(pal)
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(get)
    n1 = cs.write(cs.choose(comps, {}), pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb,
                  colours=cmap, identity=ident)
    n2 = cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb,
                  colours=cmap, identity=ident)
    say('Sheets    : %d images in %d frames; painting sheet %d figures, reference %d' % (len(seen), frames, n1, n2))
    return seen


def unit_tests(patch, states, negs=(), rzx=None, neg_frames=1500, full=False):
    """Every site at the four CPU speeds (hooklib.every_site), the copy as a hide (hooklib.hide_cases: every sprite
    shown, no figure recorded: all hidden), and the negative controls on the first neg_frames of rzx. -> Counter"""
    import collections
    from . import hooklib
    c = collections.Counter()
    first = {}
    for pc, regs, base in states:
        first.setdefault(pc, (regs, base))

    def run_at(pc, clock):
        regs, base = first[pc]
        vpage, vns = bytearray(patch.page), NextSide()
        vns.nr[0x07] = clock
        bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, DRAW if pc != 0x86F9 else COPY)
        for k in bad:                       # a failing run is a failure, whatever the other speeds give
            c['every site: %04X at speed %d: %s' % (pc, clock, k)] += 1
        state = (tuple(sorted(bad)), tuple(sorted(ow.items())), bytes(vns.attr), bytes(vns.pat))
        return vns.nr.get(0x07, 0), state
    missing = [a for a in SITE_KIND if a not in first]
    if missing:                             # a full run reaches every site; a quick one says which it did not
        c['every site: never reached %s%s' % (' '.join('%04X' % a for a in missing), '!' if full else ' (quick run)')] += 1
    cs, rows = hooklib.every_site([pc for pc in first], run_at)
    for k, v in cs.items():
        c['every site: ' + k] += v
    c['store-form check: ' + store_form_case()] += 1

    def hide_run(pc, st, speed):
        regs, base = st[1], st[2]
        vpage, vns = bytearray(patch.page), NextSide()
        vns.nr[0x07] = speed
        for n in range(16):                 # sprites on show from an earlier update
            vns.attr[5 * n:5 * n + 5] = bytes([40 + n, 40, 0, 0xC0, 0x80])
        vpage[0x31C1 - 0x2000] = 16         # V_SHOWN
        bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, COPY)
        shown = [n for n in range(128) if vns.attr[5 * n + 3] & 0x80]
        return [k for k in bad], shown
    if 0x86F9 in first:
        copies = [s for s in states if s[0] == 0x86F9]
        for k, v in hooklib.hide_cases(copies, {0x86F9: 'copy with no figure'}, hide_run).items():
            c[k] += v
    if rzx:
        c.update(negative_results(negs or negative_patches(patch), rzx, neg_frames, NEG_EXPECT, verify))
    return c


def auto(a, z80, name, out, say):
    """The whole run: plain + sprite builds with boot checks, verify each recording, unit tests + negative controls."""
    import os as _os
    say('Game      : %s' % name)
    say('Engine    : jack_the_nipper (the game\'s own figure draws into a scratch shadow; figures as 4-bit sprites)')
    plain, spr, bad = build(z80, out, name, say)
    ok = not bad
    from .recolour import banks as _banks
    for f in (plain, spr):
        b5 = _banks(open(f, 'rb').read())[5]
        blank = b5[SPACE_GLYPH - 0x4000:SPACE_GLYPH - 0x4000 + 8] == bytes(8)
        ok = ok and blank
        say('Repair    : %s: the space glyph at 0x%04X %s' % (_os.path.basename(f), SPACE_GLYPH, 'blank' if blank else 'NOT REPAIRED: FAIL'))
    patch = JtnPatch()
    from . import z80tonex as zt
    patch.apply(zt.Z80Snapshot(z80))
    states, first_rzx = [], None
    for r in list(getattr(a, 'rzx', None) or []):
        first_rzx = first_rzx or r
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=12)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails and c.get('copy', 0) > 0
        say('Verify    : %s  %d frames, draws %d (16-wide %d, 24-wide %d), copies %d, figure bytes redirected %d, '
            'picture bytes %d, sprite pixels %d -> %s' % (
                _os.path.basename(r), c['frames'], c['draw16'] + c['draw24'], c['draw16'], c['draw24'], c['copy'],
                c['figure bytes redirected'], c['picture bytes checked'], c['sprite pixels compared'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('Allowed   : %s  %s' % (_os.path.basename(r), {k: v for k, v in c.items() if '(dead)' in k}))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, rzx=first_rzx, full=not getattr(a, 'quick', None))
        ufail = [k for k in u if k.endswith('!')]
        ok = ok and not ufail
        say('Unit      : %s -> %s' % (', '.join('%s %d' % kv for kv in sorted(u.items())), 'FAIL' if ufail else 'PASS'))
    elif getattr(a, 'rzx', None):
        ok = False                          # a verify run that reached no site covers nothing
        say('Unit      : no states from the recordings: FAIL')
    else:
        say('Unit      : not run (no recording: a rebuild)')
    if first_rzx:
        ok = enhanced_checks(z80, first_rzx, getattr(a, 'quick', None), say) and ok
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
