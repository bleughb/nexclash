"""Jet Set Willy (Software Projects, 1984, 48K) engine 'jsw'. Additive module: reachable only through is_jsw().

Back-buffer composer, interrupts never on (DI at 0x8400, no EI anywhere). Main loop 0x89AD: 0x5E00 ->
0x5C00, 0x7000 -> 0x6000, figures into 0x6000 / paint 0x5C00, then 0x6000 -> 0x4000 (0x89F5) and 0x5C00 -> 0x5800
(0x8A26). The game logic reads only 0x5C00 and 0x6000, so those stay exactly as the original leaves them; the two
LDIRs change source to the clean room buffers and each plot also sets a hardware sprite. asm/jsw_hooks.asm.

Interrupts are off, so only the IN sequence decides the game: verify runs the whole patched game in lockstep with
the original on the recording's IN values (real hook bytes, whole recording), and compares at every pass.
The code sheet is bypassed at the owner's request: START_SITES run the game's own check against the right code at boot.
Details and results: games/jet_set_willy.md.
"""
import bisect
import collections
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00
HS = 0x5B60                 # hook state (27 bytes)
HS_END = HS + 30            # with S_R (+27) and S_SPD (+29), the caller's speed
NSPR = 64
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]

# (address, original bytes, symbol, first byte of the new instruction)
HOOKS = [(0x89AD, 'cd8b89', 'e_pass', 0xCD), (0x89F5, '210060', 'e_blit', 0xCD), (0x8912, '3a2084', 'e_room', 0xCD),
         (0x87CB, '32ce85', 'e_ttl', 0xCD), (0x8C4A, '210040', 'e_ovr', 0xCD), (0x8AE6, 'c4eb8a', 'e_pau', 0xC4),
         (0x8B07, '21009a', 'e_res', 0xCD), (0x9660, '06103ad385', 'e_wil', 0xCD), (0x95BB, 'cd6896', 'e_toi', 0xCD),
         (0x922E, 'cd5694', 'e_gua', 0xCD), (0x9563, 'cd5694', 'e_mar', 0xCD), (0x928E, 'dd7e06', 'e_arr', 0xCD),
         (0x930E, 'dd7e05', 'e_rop', 0xCD), (0x935E, '3ad685', 'e_rfl', 0xCD), (0x9449, '21e180', 'e_itm', 0xCD)]
DATA_SITES = [(0x8A26, '21005c', '21005e')]
KIND = {a: s[2:] for a, _, s, _ in HOOKS}
# second instruction of the 5-byte site: runs in the original after the first, never jumped to
SEQUELS = {0x9662: 0x9660}
INTERIORS = sorted({a + k for a, old, _, _ in HOOKS for k in range(1, len(old) // 2)} - set(SEQUELS))
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR
# stops both machines share: pass start, after the 0x7000 copy, pixel blit (before, after the site, after the LDIR),
# attribute blit done
PASS, CLEAN, BLIT, BLIT2, PIXELS, ATTRS = 0x89AD, 0x89C6, 0x89F5, 0x89F8, 0x8A00, 0x8A31
STOPS = frozenset((PASS, CLEAN, BLIT, BLIT2, PIXELS, ATTRS))

# The code sheet (owner's request): boot runs the game's own check. The snapshot stops in the sheet's input loop at
# 0x8791; that instruction jumps to the check's head 0x874F, past the ENTER test, and the four cells it reads hold the
# code a player enters for this snapshot (85E4 = 0x1D: 1, 2, 4, 2). Then POP HL / CP (HL) / RET as after a real entry.
# The Attic bug (owner's request, 2026-11-21): the Attic's arrow has y = 213 and writes outside the buffers, which
# corrupts other rooms; 59901 = 82 is the known fix (Software Projects' own POKE). Applied at boot with the bypass.
START_SITES = [(0x8791, 'ddcb21fe', 'c34f8700'), (0x5950, '87', '08'), (0x5953, '07', '10'), (0x5956, '07', '20'), (0x5959, '07', '10'),
               (0xE9FD, 'd5', '52')]
AFTER_CHECK = 0x86B3        # where the check returns
ATTIC_ROOM = 41             # The Attic: the original's arrow writes outside the buffers there, the build's does not
                            # (START_SITES' fix), so a comparison ends when a recording enters it (counted)
# colours: Next pages 28-33 (banks 14-16), never mapped by the game; asm/jsw_hooks.asm "Colour map"
COLOUR_BANKS = (14, 15, 16)
GFX_LO, GFX_HI = 0x9C00, 0xC000
ITEM_ROOMS = 0xC000         # an item's graphic: 0xC0E1 + room * 256, copied to 0x80E1 at the room load
RECORD = 'jet_set_willy'

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'jet_set_willy.json'),
              os.path.join(_HERE, 'jet_set_willy.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('jet_set_willy.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_jsw(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


class JswPatch:
    name = 'Jet Set Willy figures -> hardware sprites (altrom, blit sources changed)'

    def __init__(self, prof=None, rom_code=None, drop=(), data_sites=None, colours=None, start_sites=None):
        self.prof = prof or load_profile()
        self.cmap = load_colours() if colours is None else colours
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.keep_printer_buffer = True      # the snapshot's stack is at 0x5BFC: NEXLOAD overwrites the buffer, put it back
        self.tail_addr = TAIL_ADDR
        self.max_tail = HS - TAIL_ADDR
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.sites = []
        for a, old, sym, op in HOOKS:
            if a in drop:
                continue
            o = bytes.fromhex(old)
            new = bytes([op]) + self.syms[sym].to_bytes(2, 'little') + bytes(len(o) - 3)
            self.sites.append((a, o, new))
        for a, old, new in (DATA_SITES if data_sites is None else data_sites):
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(new)))
        self.start_sites = [(a, bytes.fromhex(o), bytes.fromhex(n)) for a, o, n in (START_SITES if start_sites is None else start_sites)]
        self.sites += self.start_sites
        self.game_sites = [x for x in self.sites if x not in self.start_sites]
        self.extra_banks = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Jet Set Willy patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        tables, self.cinfo = colour_tables(lambda a: ram[a - 0x4000], self.cmap)
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:HS_END - 0x4000]):
            raise ValueError('printer buffer is not empty in this snapshot (tail + hook state)')
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {12: self.page + bytes(8192)}
        self.extra_banks.update(colour_banks(tables))


class JswPlainPatch:
    """The plain build: only the code sheet's bypass, no sprites."""
    name = 'Jet Set Willy, code sheet bypassed'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = False
    keep_printer_buffer = True           # the snapshot's stack is at 0x5BFC: NEXLOAD overwrites the buffer, put it back
    tail_addr = TAIL_ADDR
    extra_banks = {}
    rom_code = b''
    cmap = {}

    def __init__(self, start_sites=None):
        self.sites = [(a, bytes.fromhex(o), bytes.fromhex(n)) for a, o, n in (START_SITES if start_sites is None else start_sites)]
        self.start_sites = list(self.sites)
        self.game_sites = []

    def apply(self, snap):
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            if bytes(ram[a - 0x4000:a - 0x4000 + len(old)]) != old:
                raise ValueError('unexpected code at 0x%04X' % a)
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


# ---------------------------------------------------------------------------------------------
# Colour map (docs/COLOURS.md, patch.runtime-colour-map): the hooks build patterns at each plot; a painting is tables
# in Next pages 28-33 the upload applies. Keys: graphics byte (hex address; check = its value), an ink pixel per bit.
# ---------------------------------------------------------------------------------------------

def _item_key(a):
    return a >= ITEM_ROOMS and 0xE1 <= (a & 0xFF) <= 0xE8


def colour_tables(get, cmap):
    """Colour map -> ({page 28..33: 8192 bytes}, info). An entry whose check byte differs, or for a byte no figure
    uses, is ignored; so is paint on a bit that is not ink (the sheet offers ink pixels only)."""
    pages = {p: bytearray(8192) for p in range(28, 34)}
    info = collections.Counter()
    for key, e in cmap.items():
        a = int(key, 16)
        if get(a) != e[0]:
            info['map entries ignored (check byte differs)'] += 1
            continue
        if not (GFX_LO <= a < GFX_HI or _item_key(a)):
            info['map entries for no figure'] += 1
            continue
        info['map entries used'] += 1
        for bit, n in enumerate(e[2]):
            if not n or not (e[0] >> (7 - bit)) & 1:
                continue
            if _item_key(a):
                room = (a >> 8) - 0xC0
                pg, off = 33, room * 32 + ((a & 0xFF) - 0xE1) * 4 + bit // 2
                pages[33][0x800 + room] = 1
            else:
                o = (a - GFX_LO) * 4 + bit // 2
                pg, off = 28 + (o >> 13), o & 0x1FFF
                pages[33][0x1000 + (a - GFX_LO) // 32] = 1
            pages[pg][off] |= n << 4 if not bit & 1 else n
    return pages, info


def colour_banks(pages):
    return {14: bytes(pages[28] + pages[29]), 15: bytes(pages[30] + pages[31]), 16: bytes(pages[32] + pages[33])}


def load_colours():
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(build_colours_path(COLOURS))


def colour_inputs_md5(get):
    """MD5 + count of the bytes the colour map is keyed by: figure graphics and every room's item graphic."""
    addrs = list(range(GFX_LO, GFX_HI)) + [ITEM_ROOMS + r * 256 + 0xE1 + i for r in range(64) for i in range(8)]
    return hashlib.md5(bytes(get(a) for a in addrs)).hexdigest(), len(addrs)


def colour_identity(peek):
    """What a colour map / sheet layout means for this build (docs/COLOURS.md "Identity")."""
    return {'schema': 1, 'game': RECORD, 'engine': 'jsw', 'keys': 'jsw-1: %04X graphics byte, bit = pixel (0 = leftmost)',
            'inputs': colour_inputs_md5(peek)[0], 'geometry': None}


NOTE = ('Jet Set Willy colour map (docs/COLOURS.md): key = graphics byte (hex address; check = its value); 8 nibbles, '
        '0 = default (the colour the game gives the figure), else sprite palette index 1-15. Arrows and ropes have no entries.')
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/' + RECORD + '_colours.json', 'clear': False, 'note': NOTE}


def recolour(nex, cmap):
    """Built sprite .nex bytes + colour map -> (new .nex bytes, info). Only banks 14-16 change; the game never maps
    them. Refuses a .nex that is not this engine's build of the expected snapshot."""
    from .recolour import banks, splice
    b = banks(nex)
    need = set(COLOUR_BANKS) | {5, 2, 0, 10, 12}
    if not need <= set(b):
        raise ValueError('not a Jet Set Willy sprite build: banks %s missing' % sorted(need - set(b)))
    ram = b[5] + b[2] + b[0]
    peek = lambda a: ram[a - 0x4000] if a >= 0x4000 else 0
    prof = load_profile()
    want = prof.get('colour_inputs', {})
    got = colour_inputs_md5(peek)
    if [want.get('md5'), want.get('bytes')] != list(got):
        raise ValueError('game graphics differ from the expected snapshot (%s / %d bytes)' % got)
    p = JswPatch(prof, colours=cmap)
    for a, old, new in p.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError('patch site 0x%04X does not hold this build\'s bytes' % a)
    if b[12] != p.page + bytes(8192):
        raise ValueError('alt ROM image / hook code differs from this version\'s (rebuild with nexclash.py auto)')
    if b[10][0x1000:0x1000 + len(p.stub_extra)] != p.stub_extra:
        raise ValueError('set-up code differs from this version\'s (rebuild with nexclash.py auto)')
    tables, ci = colour_tables(peek, cmap)
    out, changed = splice(nex, colour_banks(tables))
    info = {'banks changed': changed}
    info.update({k: v for k, v in ci.items() if v})
    return out, info


# ---------------------------------------------------------------------------------------------
# Next-side model
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self):
        self.nr = {}
        self.sel = 8            # NextReg select (port 0x243B): the stub's last read (NR 8) leaves it there; spdin selects 7
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pos = 0
        self.pal = {}
        self.palidx = 0
        self.mem = None         # the hooks' memory: what each sprite was plotted with; slot 7's pages
        self.tables = {}
        self.meta = {}
        self.saved = None

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            i = self.nr.get(0x34, 0) & 0x7F
            self.attr[i][reg - 0x35] = val
            if reg == 0x39 and self.mem is not None:
                self.meta[i] = (self.mem[HS + 5], self.mem[HS + 26])
        elif reg == 0x57:
            if val in self.tables:
                if self.saved is None:
                    self.saved = self.mem[0xE000:0x10000]
                self.mem[0xE000:0x10000] = list(self.tables[val])
            elif self.saved is not None:
                self.mem[0xE000:0x10000] = self.saved
                self.saved = None
        elif reg == 0x40:
            self.palidx = val
        elif reg == 0x41:
            self.pal[self.palidx] = val
            self.palidx = (self.palidx + 1) & 0xFF

    def out(self, port, val):
        if port == 0x243B:
            self.sel = val
        elif port == 0x303B:
            self.pos = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pos & 0x3FFF] = val
            self.pos += 1

    def sprites(self):
        """Visible sprites in order: (number, x, y, palette offset, pattern offset in bytes)."""
        out = []
        for i, a in enumerate(self.attr[:NSPR]):
            if a[3] & 0x80:
                out.append((i, a[0] + (a[2] & 1) * 256 - 32, a[1] + (a[4] & 1) * 256 - 32, a[2] >> 4,
                            (a[3] & 0x3F) * 256 + (128 if a[4] & 0x40 else 0)))
        return out


def compose(clean, ns, want=None):
    """0x6000 as the sprites say it should be: clean (4096 bytes, as copied) + sprites in order. See-through figure: an
    opaque nibble sets a pixel. Solid figure (paper index recorded at its plot): its paper nibble clears a pixel, others
    set it; where ink and paper are one index the pattern cannot say which bit it was, and the picture is one block
    of that colour as in the original: those bits are taken from want and counted.
    -> (bytearray, pixels outside the 128 rows, those of them where the HUD is, solid bits not comparable)"""
    same = 0
    out = bytearray(clean)
    pat = ns.pat
    off = hud = 0
    for i, x, y, _, base in ns.sprites():
        ink, pap = ns.meta.get(i, (1, 0))
        for j in range(16):
            row = pat[base + j * 8:base + j * 8 + 8]
            if not any(row):
                continue
            yy = y + j
            for k in range(16):
                b = row[k >> 1]
                v = (b >> 4) if not k & 1 else (b & 15)
                if not v:
                    continue
                xx = x + k
                if not (0 <= xx < 256 and 0 <= yy < 128):
                    off += 1
                    if 0 <= xx < 256 and 128 <= yy < 192:
                        hud += 1
                    continue
                a = ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2) | (xx >> 3)
                m = 0x80 >> (xx & 7)
                if pap and ink == pap and want is not None:
                    same += 1
                    out[a] = (out[a] & ~m & 0xFF) | (want[a] & m)
                elif v != pap:
                    out[a] |= m
                else:
                    out[a] &= ~m & 0xFF
    return out, off, hud, same


# ---------------------------------------------------------------------------------------------
# Lockstep: both whole games on one IN sequence
# ---------------------------------------------------------------------------------------------

class _End(Exception):
    pass


class _Ins:
    def __init__(self, ins, ns=None):
        self.ins, self.i, self.ns = ins, 0, ns

    def read_port(self, regs, port):
        if port == 0x253B and self.ns is not None:     # NextReg read (a hook's speed read): not a recorded IN
            return self.ns.nr.get(self.ns.sel, 0)
        if self.i >= len(self.ins):
            raise _End()
        v = self.ins[self.i]
        self.i += 1
        return v

    def write_port(self, regs, port, value, *x):
        if self.ns is not None:
            self.ns.out(port, value)


def _sim(snap_mem, regs, tracer, ns=None):
    """A Python simulator on its own 64K list."""
    from skoolkit.simulator import Simulator
    sim = Simulator(list(snap_mem), registers=dict(regs) if isinstance(regs, dict) else None)
    if not isinstance(regs, dict):
        sim.registers[:] = regs
    sim.set_tracer(tracer)
    if ns is not None:
        from . import z80n
        z80n.install(sim, ns.nextreg)
    return sim


def _load(snap):
    from skoolkit.simutils import from_snapshot
    from skoolkit.simulator import Simulator
    return from_snapshot(Simulator, snap, config={'int_active': 0})


def _segments(rzx_path, stop=None):
    """-> (Snapshot, IN values in order, cumulative IN count at each frame's end)."""
    from .rzx import read_segments
    segs = read_segments(rzx_path)
    if len(segs) != 1:
        raise ValueError('expected one segment in %s (record --script makes one)' % rzx_path)
    snap, rec, _ = segs[0]
    ins, ends = [], []
    for f in rec.frames[:stop] if stop else rec.frames:     # data also holds the frame headers
        ins.extend(rec.data[f.start:f.end])
        ends.append(len(ins))
    return snap, ins, ends


class Lock:
    """Original and patched machines, from one state, advanced stop by stop."""

    def __init__(self, patch, mem, regs, ins, ns=None, pstate=None):
        """pstate: the patched machine's own (memory, registers) when it does not start from the original's state."""
        self.patch = patch
        self.ns = ns or NextState()
        self.ti, self.tp = _Ins(ins), _Ins(ins, self.ns)
        self.o = _sim(mem, regs, self.ti)
        pm = list(pstate[0] if pstate else mem)
        if not pstate:
            for a, old, new in patch.sites:
                pm[a:a + len(new)] = list(new)
        pm[ROM_ORG:ROM_ORG + len(patch.rom_code)] = list(patch.rom_code)
        self.p = _sim(pm, pstate[1] if pstate else regs, self.tp, self.ns)
        self.ns.mem = self.p.memory
        self.spd = self.ns.nr.setdefault(0x07, 0)      # the caller's speed; lockstep turns it 0-3 at every stop
        self.ns.tables = {k: bytes(v) for k, v in colour_tables(lambda a: mem[a], patch.cmap)[0].items()} if patch.cmap else \
            {k: bytes(8192) for k in range(28, 34)}
        self.hooks = {a for a, _, _ in patch.sites if a in KIND}
        self.stops_p = STOPS | self.hooks
        self.watch_o = STOPS | set(INTERIORS)
        self.cnt = collections.Counter()
        self.jumps = collections.Counter()
        self.segs = self._segs(patch)
        self.t0 = (self.o.registers[25], self.p.registers[25])

    def _segs(self, patch):
        skip = set(range(0x4000, 0x5000)) | set(range(0x5800, 0x5A00)) | set(range(0x5B00, 0x5C00))
        for a, old, new in patch.sites:
            skip |= set(range(a, a + len(new)))
        out, a = [], 0x5000
        while a < 0x10000:
            if a in skip:
                a += 1
                continue
            b = a
            while b < 0x10000 and b not in skip:
                b += 1
            out.append((a, b))
            a = b
        return out

    def step_o(self):
        """Original to its next stop."""
        R, mem, ops, W = self.o.registers, self.o.memory, self.o.opcodes, self.watch_o
        ops[mem[R[24]]]()
        while True:
            pc = R[24]
            if pc in W:
                if pc in STOPS:
                    return pc
                self.jumps[pc] += 1
            ops[mem[pc]]()

    def step_p(self):
        R, mem, ops, W = self.p.registers, self.p.memory, self.p.opcodes, self.stops_p
        ops[mem[R[24]]]()
        while True:
            pc = R[24]
            if pc in W:
                if pc in self.hooks:
                    self.cnt[KIND[pc]] += 1
                if pc in STOPS:
                    return pc
            ops[mem[pc]]()

    def diff(self):
        """What differs between the machines at a shared stop: registers, memory, stack above SP."""
        ro, rp = self.o.registers, self.p.registers
        bad = []
        for i in CMP:
            if ro[i] != rp[i]:
                bad.append(('reg %d' % i, ro[i], rp[i]))
        mo, mp = self.o.memory, self.p.memory
        for a, b in self.segs:
            if mo[a:b] != mp[a:b]:
                x = next(k for k in range(a, b) if mo[k] != mp[k])
                bad.append(('mem 0x%04X' % x, mo[x], mp[x]))
                break
        sp = ro[12]
        if 0x5B00 <= sp < 0x5C00 and mo[sp:0x5C00] != mp[sp:0x5C00]:
            bad.append(('stack', sp))
        return bad


# register index of SP in SkoolKit's list: 12 (with PC 24, T 25); F, A etc. as simutils
def lockstep(patch, mem, regs, ins, ends=None, on_blit=None, stop_passes=None, first_only=True, ns=None, pstate=None):
    """Run both from one state on ins. -> (Counter, examples, Lock). Failure keys end in '!'."""
    c = collections.Counter()
    ex = collections.defaultdict(list)
    L = Lock(patch, mem, regs, ins, ns, pstate)
    fails = [0]

    def fail(k, *info):
        c[k + '!'] += 1
        fails[0] += 1
        fr = bisect.bisect_left(ends, L.ti.i) if ends else 0
        if len(ex[k]) < 5:
            ex[k].append((fr,) + info)

    clean = None
    tt = L.t0
    try:
        while True:
            po = L.step_o()
            pp = L.step_p()
            if po != pp:
                fail('machines stopped apart', hex(po), hex(pp))
                break
            mo, mp = L.o.memory, L.p.memory
            if po in (PASS, BLIT) and mo[0x8420] == ATTIC_ROOM:
                c['stopped at the Attic (its bug is fixed in the build)'] += 1
                break
            if po in (PASS, BLIT):
                if L.ti.i != L.tp.i:
                    fail('IN counts differ', L.ti.i, L.tp.i)
                bad = L.diff()
                if bad:
                    fail('state differs at 0x%04X' % po, bad[:3])
                if any(mo[TAIL_ADDR:HS_END]):
                    fail('game wrote the tail or hook state area', bytes(mo[TAIL_ADDR:HS_END]).hex()[:40])
                if mp[0xE9FD] != 0x52:
                    fail('the Attic fix is missing')
                for a, old, new in patch.game_sites:
                    if mo[a:a + len(old)] != list(old) or mp[a:a + len(new)] != list(new):
                        fail('a patch site changed', hex(a))
                if L.ns.nr.get(0x57, 1) != 1:
                    fail('slot 7 left on a colour page', L.ns.nr[0x57])
                if L.ns.nr.get(0x07, 0) != L.spd:
                    fail('CPU speed not the caller\'s', L.ns.nr.get(0x07, 0), L.spd)
                c['entry speed %d' % L.spd] += 1
                L.spd = L.ns.nr[0x07] = (L.spd + 1) % 4       # every hook entered at all four speeds in turn
                if po == PASS:
                    c['passes'] += 1
                    tt = (L.o.registers[25], L.p.registers[25])
                    if stop_passes and c['passes'] >= stop_passes:
                        break
            elif po == CLEAN:
                clean = bytes(mp[0x6000:0x7000])
            elif po == BLIT2 and clean is not None:
                c['pixel blits'] += 1
                c['room %d' % mo[0x8420]] += 1
                want = bytes(mo[0x6000:0x7000])
                got, off, hud, same = compose(clean, L.ns, want)
                c['solid bits where ink = paper, not comparable'] += same
                if off:
                    c['sprite pixels outside the play area'] += off
                    c['off area, room %d' % mo[0x8420]] += off
                if hud:
                    c['sprite pixels over the HUD'] += hud
                died = mo[0x85D1] == 0xFF
                if bytes(got) == want:
                    c['pictures identical'] += 1
                elif died and all((w & ~g & 0xFF) == 0 for w, g in zip(want, got)):
                    c['pictures cut short by a death (hold every pixel of the original)'] += 1
                else:
                    x = next(i for i in range(4096) if got[i] != want[i])
                    fail('picture differs', hex(0x6000 + x), got[x], want[x], 'room', mo[0x8420], 'died', died)
                vis = L.ns.sprites()
                c['sprites shown'] += len(vis)
                for i, x, y, o, base in vis:
                    if 0 <= y < 128:
                        at = mo[0x5C00 + (y >> 3) * 32 + (x >> 3)]
                        c['sprite ink same as the original cell' if (at & 7) == (L.ns.meta.get(i, (0, 0))[0] & 7) else
                          'sprite ink differs from the original cell'] += 1
                if on_blit:
                    on_blit(c['pixel blits'], mo, mp, L.ns)
            elif po == PIXELS:
                if mp[0x4000:0x5000] != mp[0x7000:0x8000]:
                    fail('ULA pixels are not the clean buffer', 'room', mo[0x8420])
                if mo[0x4000:0x5000] != mo[0x6000:0x7000]:
                    fail('original blit model wrong')
            elif po == ATTRS:
                if mp[0x5800:0x5A00] != mp[0x5E00:0x6000]:
                    fail('ULA attributes are not the clean buffer', 'room', mo[0x8420])
                c['attribute blits'] += 1
            if fails[0] and first_only:
                break
    except _End:
        pass
    c.update(L.cnt)
    for a, n in L.jumps.items():
        c['jump into a patched instruction 0x%04X!' % a] += n
    c['T original'] = tt[0] - L.t0[0]       # to the last pass start both reached
    c['T patched'] = tt[1] - L.t0[1]
    return c, dict(ex), L


def _rzx_state(snap):
    sim = _load(snap)
    return list(sim.memory), list(sim.registers)


def start_states(patch, mem, regs, ins):
    """The recordings begin at the code sheet, which the build no longer shows. The original runs the recording's own
    keys up to the check's return (AFTER_CHECK); the build runs from the snapshot with its START_SITES and no input to
    the same place. -> ((memory, registers) of each, INs the original used, differences)"""
    def run(m, r, tr):
        sim = _sim(m, r, tr)
        R, M, O = sim.registers, sim.memory, sim.opcodes
        for _ in range(50000000):
            if R[24] == AFTER_CHECK:
                return list(M), list(R)
            O[M[R[24]]]()
        raise ValueError('never reached the end of the code check')
    to = _Ins(ins)
    mo, ro = run(mem, regs, to)
    pm = list(mem)
    for a, old, new in patch.start_sites:
        pm[a:a + len(new)] = list(new)
    tp = _Ins([])
    try:
        mp, rp = run(pm, regs, tp)
    except _End:
        raise ValueError('the bypass read a port: it should run no input')
    sites = {a + k for a, _, new in patch.start_sites for k in range(len(new))}
    regs_d = [(i, ro[i], rp[i]) for i in CMP if ro[i] != rp[i]]
    mem_d = [a for a in range(0x4000, 0x10000) if mo[a] != mp[a] and a not in sites]
    for a, old, new in patch.sites:
        if a not in {x[0] for x in patch.start_sites}:
            mp[a:a + len(new)] = list(new)
    return (mo, ro), (mp, rp), to.i, regs_d, mem_d


# what a correct entry itself leaves different from one entry to the next (which cell the input loop had reached, the
# last key): anything else after the check, or any of these still different at the first pass start, is a failure.
ENTRY_REGS = {2, 3, 4, 5, 8, 9}      # B, C, D, E, IXh, IXl (none differs on these recordings; counted in the report)
ENTRY_MEM = (0x5950, 0x5980)         # the sheet's colour cells (the title rewrites the screen)


def verify(patch, rzx_path, stop=None, collect=0, progress=None, first_only=True):
    """Differential test (PLAYBOOK 6) by lockstep on the recording, from the state after the code sheet.
    -> (Counter, examples[, states])."""
    snap, ins, ends = _segments(rzx_path, stop)
    mem, regs = _rzx_state(snap)
    states = []

    def blit(n, mo, mp, ns):
        if progress and n % 1000 == 0:
            progress(n, None)
    (mo, ro), ps, used, regs_d, mem_d = start_states(patch, mem, regs, ins)
    c0 = collections.Counter()
    bad_r = [d for d in regs_d if d[0] not in ENTRY_REGS]
    bad_m = [a for a in mem_d if not ENTRY_MEM[0] <= a < ENTRY_MEM[1]]
    if bad_r:
        c0['after the check: registers differ from a real entry!'] = len(bad_r)
    if bad_m:
        c0['after the check: memory differs from a real entry!'] = len(bad_m)
    c, ex, L = lockstep(patch, mo, ro, ins[used:], [e - used for e in ends], on_blit=blit, first_only=first_only, pstate=ps)
    c.update(c0)
    if bad_r or bad_m:
        ex['start'] = [(bad_r[:4], [hex(a) for a in bad_m[:6]])]
    c['frames'] = len(ends)
    c['frames of code entry not compared'] = bisect.bisect_left(ends, used) + 1
    c['start: registers differing after the check'] = len(regs_d)
    c['start: memory bytes differing after the check'] = len(mem_d)
    if collect:
        states.append(('end', mem, regs, ins, ends))
    return (c, ex, states) if collect else (c, ex)


def verify_plain(rzx_path, stop=None, start_sites=None):
    """The plain build against the original from the state after the code sheet, screen included: all registers and
    every byte 0x4000-0xFFFF but the bypass's own code bytes, at every pass start and pixel blit, and at the first
    title. -> Counter (failure keys end in '!'). Nothing later can tell if this holds."""
    patch = JswPlainPatch(start_sites)
    snap, ins, ends = _segments(rzx_path, stop)
    mem, regs = _rzx_state(snap)
    (mo, ro), ps, used, regs_d, mem_d = start_states(patch, mem, regs, ins)
    c = collections.Counter()
    if [d for d in regs_d if d[0] not in ENTRY_REGS]:
        c['after the check: registers differ from a real entry!'] += 1
    if [a for a in mem_d if not ENTRY_MEM[0] <= a < ENTRY_MEM[1]]:
        c['after the check: memory differs from a real entry!'] += 1
    L = Lock(patch, mo, ro, ins[used:], pstate=ps)
    skip = {a + k for a in (0x8791,) for k in range(4)} | {0xE9FD}      # the bypass and the Attic fix
    first = True
    try:
        while True:
            po, pp = L.step_o(), L.step_p()
            if po != pp:
                c['machines stopped apart!'] += 1
                break
            if po in (PASS, BLIT) and L.o.memory[0x8420] == ATTIC_ROOM:
                c['stopped at the Attic'] += 1
                break
            if po in (PASS, BLIT):
                bad = [i for i in CMP if L.o.registers[i] != L.p.registers[i]]
                ma, mb = L.o.memory, L.p.memory
                if bad or ma[0x4000:] != mb[0x4000:]:
                    d = [a for a in range(0x4000, 0x10000) if ma[a] != mb[a] and a not in skip]
                    if bad or d:
                        c['differs from the original!'] += 1
                        c['first difference %s %s' % (bad[:3], [hex(a) for a in d[:4]])] = 1
                        break
                c['compares'] += 1
                if L.p.memory[0xE9FD] != 0x52:
                    c['the Attic fix is missing!'] += 1
                if first:
                    c['first pass: whole RAM and registers as after a real entry'] = 1
                    first = False
    except _End:
        pass
    return c


# ---------------------------------------------------------------------------------------------
# Cases the recordings do not reach, and the negative controls
# ---------------------------------------------------------------------------------------------

def game_state(z80):
    """A state in play: the snapshot, its code entered, title passed: memory and registers from a short free run."""
    from .recorder import Recorder, parse_inputs
    r = Recorder(z80)
    m = r.m
    M = m.sim.memory
    t = M[0x85E4]
    r.run(20)
    for d in ((t >> 6) & 3, (t >> 4) & 3, (t >> 2) & 3, t & 3):
        r.run(10, parse_inputs(str(d + 1)))
        r.run(10)
    r.run(5, parse_inputs('ENTER'))
    r.run(50)
    r.run(5, parse_inputs('ENTER'))
    r.run(50)
    return list(M), list(m.sim.registers)


def _at(mem, regs, addr, pokes=()):
    """State with PC at addr, memory poked."""
    m, r = list(mem), list(regs)
    for a, v in pokes:
        m[a] = v
    r[24] = addr
    return m, r


def _case(c, name, patch, mem, regs, passes, ins=None, want_hooks=()):
    ci, ex, L = lockstep(patch, mem, regs, ins if ins is not None else [0xFF] * (16 * passes), stop_passes=passes)
    fails = {k: v for k, v in ci.items() if k.endswith('!')}
    for k in want_hooks:
        if not ci[k]:
            fails['hook %s never ran in this case' % k] = 1
    if fails:
        c['%s!' % name] += 1
        c.setdefault('_ex', []).append((name, fails, ex))
    else:
        c['%s ok' % name] += 1
    for k in KIND.values():
        c['unit hook ' + k] += ci[k]
    return ci, L


def setup_check(patch):
    """The setup routine: palette, sprites hidden, sprites on."""
    ns = NextState()
    mem = [0] * 65536
    mem[0xD000:0xD000 + len(patch.stub_extra)] = list(patch.stub_extra)
    mem[0xCFFE:0xD000] = [0, 0]
    tr = _Ins([], ns)
    regs = None
    from skoolkit.simulator import Simulator
    sim = Simulator(mem, {'SP': 0xCFFE, 'PC': 0xD000})
    sim.set_tracer(tr)
    from . import z80n
    z80n.install(sim, ns.nextreg)
    R, ops = sim.registers, sim.opcodes
    for _ in range(100000):
        if R[24] == 0:
            break
        ops[mem[R[24]]]()
    else:
        return ['setup did not return']
    bad = []
    for i in range(1, 16):
        if ns.pal.get(i) != SPECCY[i]:
            bad.append(('palette', i))
    if ns.nr.get(0x15) != 1 or ns.nr.get(0x4B) != 0:
        bad.append('registers')
    if any(a[3] for a in ns.attr):
        bad.append('sprite left on')
    return bad


def unit_tests(patch, states=None, neg=None, z80=None):
    """Every room from a clean load; the end game (never reached by the recordings); slot guard; setup."""
    c = collections.Counter()
    mem, regs = states if states else game_state(z80)
    if setup_check(patch):
        c['setup!'] += 1
    else:
        c['setup ok'] += 1
    # every room, entered through the game's own room load, 30 passes
    for room in list(range(47)) + list(range(48, 61)):
        if room == ATTIC_ROOM:                     # differs by design (its fixed arrow): see START_SITES
            c['room: the Attic left out (its bug is fixed in the build)'] += 1
            continue
        m, r = _at(mem, regs, 0x8912, [(0x8420, room)])
        _case(c, 'room', patch, m, r, 30)
    # Maria at her three frames: Willy on the floor, on the first step, higher
    for y in (0xD0, 0xC8, 0xB0):
        m, r = _at(mem, regs, 0x8912, [(0x8420, 0x23), (0x85CF, y), (0x85D3, 0x14), (0x85D4, 0x5D)])
        _case(c, 'Maria', patch, m, r, 8, want_hooks=('mar',))
    # the end game: all items taken (85DF=1), Maria gone, past her door 85DF=2
    m, r = _at(mem, regs, 0x8912, [(0x8420, 0x23), (0x85DF, 1), (0x85D3, 0x04), (0x85D4, 0x5D)])
    _case(c, 'Maria gone', patch, m, r, 6)
    # 85DF=2: Willy walks by himself, on The Bathroom's toilet at 0x5DBC: 85DF=3, the toilet with his head in it
    m, r = _at(mem, regs, 0x8912, [(0x8420, 0x21), (0x85DF, 2), (0x85D3, 0xB8), (0x85D4, 0x5D), (0x85CF, 0xD0)])
    ci, L = _case(c, 'run to the toilet', patch, m, r, 200, want_hooks=('toi',))
    c['run to the toilet: 85DF at the end'] = L.o.memory[0x85DF]
    m, r = _at(mem, regs, 0x8912, [(0x8420, 0x21), (0x85DF, 3), (0x85D3, 0xBC), (0x85D4, 0x5D), (0x85CF, 0xD0)])
    ci, L = _case(c, 'toilet end', patch, m, r, 60, want_hooks=('toi',))
    # slot guard: table full, nothing changes, nothing breaks
    m, r = _at(mem, regs, 0x8912, [(0x8420, 0)])
    ci, ex, L = lockstep(patch, m, r, [0xFF] * 64, stop_passes=4)
    m2 = list(L.o.memory)
    r2 = list(L.o.registers)
    p2 = list(L.p.memory)
    c['slot guard'] += _guard(patch, m2, r2, c)
    bad, fails, ci = colour_cases(patch, mem, regs, c)
    if bad or fails or not ci['wil']:
        c['colour map!'] += 1
        c.setdefault('_ex', []).append(('colour map', dict(bad), fails))
    else:
        c['colour map ok'] += 1
    bad, fails, ci = colour_cases(patch, mem, regs, c, neg=True)
    if bad:
        c['colour map left out: detected'] = 1
    else:
        c['colour map left out: NOT DETECTED!'] += 1
    if neg:
        for name, np in neg:
            nc = collections.Counter()
            for room in (0x21, 0, 16, 7, 35):
                m, r = _at(mem, regs, 0x8912, [(0x8420, room)])
                _case(nc, 'x', np, m, r, 12)
            if nc['x!']:
                c['negative controls detected through the unit cases'] += 1
                c['negative: ' + name + ': detected'] = 1
            else:
                c['negative controls not seen by the unit cases'] += 1
                c['negative: ' + name + ': not seen'] = 1
    return c


def _guard(patch, mem, regs, c):
    """COUNT = 64 at pass start: begin refuses, no attribute moves; game state as the original."""
    m, r = _at(mem, regs, 0x89B0)   # just past the pass site: the hook's reset does not run this time
    ns = NextState()
    L = Lock(patch, m, r, [0xFF] * 64, ns)
    L.p.memory[HS] = 64
    L.p.memory[HS + 1] = 0
    # to the pixel blit
    while True:
        po = L.step_o()
        pp = L.step_p()
        if po != pp:
            c['slot guard: machines apart!'] += 1
            return 0
        if po == BLIT:
            break
    bad = L.diff()
    if bad:
        c['slot guard: state differs!'] += 1
        return 0
    if any(a[3] for a in ns.attr):
        c['slot guard: a sprite was set!'] += 1
        return 0
    return 1


def colour_cases(patch, mem, regs, c, neg=False):
    """A synthetic map through a real run: Willy's top 4 rows, one frame's entry with a wrong check byte (must be ignored),
    the room's guardian whole, the room's item. Every plotted pixel against the map; game and picture as the unpainted."""
    get = lambda a: mem[a]
    def ent(a, n, check=None):
        return [get(a) if check is None else check, 'g', [n if get(a) >> (7 - b) & 1 else 0 for b in range(8)]]
    cmap = {}
    for f in range(8):
        for r in range(8):
            a = 0x9D00 + f * 32 + r
            cmap['%04X' % a] = ent(a, 2, (get(a) ^ 0x55) if f == 2 else None)
    room = 0x21
    gp = None
    for i in range(8):
        e = mem[0xC000 + room * 256 + 0xF0 + 2 * i]
        if e and mem[0xA000 + (e & 0x7F) * 8] & 7 in (1, 2):
            gp = mem[0xA000 + (e & 0x7F) * 8 + 5]
            break
    for k in range(256):
        cmap['%04X' % (gp * 256 + k)] = ent(gp * 256 + k, 4)
    for k in range(8):
        a = 0xC000 + room * 256 + 0xE1 + k
        cmap['%04X' % a] = ent(a, 6)
    p = JswPatch(patch.prof, colours={} if neg else cmap)
    p.cmap = cmap if not neg else {}
    m, r = _at(mem, regs, 0x8912, [(0x8420, room)])
    bad = collections.Counter()

    def blit(n, mo, mp, ns):
        for i, x, y, _, base in ns.sprites():
            ink, pap = ns.meta[i]
            rows = [ns.pat[base + j * 8:base + j * 8 + 8] for j in range(16)]
            nib = [[(b >> 4 if not k & 1 else b & 15) for b in rw for k in (0, 1)] for rw in rows]
            if i == 0:                      # Willy
                frames = [f for f in range(8) if all(
                    ((mem[0x9D00 + f * 32 + 2 * j] << 8 | mem[0x9D00 + f * 32 + 2 * j + 1]) >> (15 - k)) & 1 == bool(nib[j][k])
                    for j in range(16) for k in range(16))]
                if not frames:
                    bad['Willy: no frame has this shape'] += 1
                    continue
                f = frames[0]
                for j in range(16):
                    for k in range(16):
                        v = nib[j][k]
                        if v and v != (2 if j < 4 and f != 2 else ink):
                            bad['Willy pixel'] += 1
            elif pap:                       # the item
                for j in range(8):
                    for k in range(8):
                        v = nib[j][k]
                        if v != pap and v != 6:
                            bad['item pixel'] += 1
            elif y < 96:                    # the guardian on the upper floor
                if any(v and v != 4 for rw in nib for v in rw):
                    bad['guardian pixel'] += 1
    ci, ex, L = lockstep(p, m, r, [0xFF] * 160, stop_passes=10, on_blit=blit)
    fails = {k: v for k, v in ci.items() if k.endswith('!')}
    return bad, fails, ci


def negative_patches(patch):
    """The broken builds. Each must be DETECTED on the real recording."""
    s = patch.syms
    def rom(a, *b):
        return patch.rom_code[:a - ROM_ORG] + bytes(b) + patch.rom_code[a - ROM_ORG + len(b):]
    out = [('pixel blit keeps the figures', JswPatch(patch.prof, rom(s['neg_blit'] + 2, 0x60))),
           ('attribute blit keeps the paint', JswPatch(patch.prof, data_sites=[])),
           ('sprites one row low', JswPatch(patch.prof, rom(s['neg_y'] + 1, 33))),
           ('patterns inverted', JswPatch(patch.prof, rom(s['out8'] + 6, 0x38))),
           ('Willy hook loses A', JswPatch(patch.prof, rom(s['neg_reg'] + 1, 0xD4))),
           ('Willy hook never runs', JswPatch(patch.prof, drop=(0x9660,))),
           ('guardian hook never runs', JswPatch(patch.prof, drop=(0x922E,))),
           ('arrow hook never runs', JswPatch(patch.prof, drop=(0x928E,))),
           ('rope hook never runs', JswPatch(patch.prof, drop=(0x930E,))),
           ('item hook never runs', JswPatch(patch.prof, drop=(0x9449,))),
           ('blit hook never hides', JswPatch(patch.prof, rom(s['e_blit'] + 5, 0, 0, 0))),
           ('hooks leave 28 MHz on', JswPatch(patch.prof, rom(s['spdout'], 0x3E, 3, 0))),
           ('hooks give back 3.5 MHz, not the caller\'s speed', JswPatch(patch.prof, rom(s['spdout'], 0xAF, 0, 0))),
           ('speed read without selecting NR 7 (the stub leaves NR 8)', JswPatch(patch.prof, rom(s['spdin'] + 6, 0, 0))),
           ('slot 7 left on a colour page', JswPatch(patch.prof, rom(s['ovfind'] + 0, 0xC3, *(s['ovbad'] + 0).to_bytes(2, 'little')))),
           ('bypass with a wrong code cell', JswPatch(patch.prof, start_sites=[x if x[0] != 0x5956 else (0x5956, '07', '18') for x in START_SITES]))]
    return out


def negative_patch(patch):
    return negative_patches(patch)[0][1]


HOOK_NAMES = ('pass', 'blit', 'room', 'ttl', 'ovr', 'pau', 'res', 'wil', 'toi', 'gua', 'mar', 'arr', 'rop', 'rfl', 'itm')


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : jsw (Jet Set Willy: blit sources 0x7000 / 0x5E00, figures -> sprites at their plot sites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=JswPlainPatch())
    bad = check(plain, z80, JswPlainPatch(), (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain),
                                                       'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = JswPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  tail %d bytes at 0x%04X' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200], len(conv[2]), conv[1]))
    ok = not bad and not bad2
    if not getattr(a, 'rzx', None):
        say('Verify    : no recording given: build only')
        say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
        return ok
    total = collections.Counter()
    quick = getattr(a, 'quick', None)
    for r in a.rzx:
        c, ex = verify(patch, r, stop=quick)
        total.update(c)
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d passes, %d blits, pictures %d identical + %d cut short -> %s' % (
            os.path.basename(r), c['frames'], c['passes'], c['pixel blits'], c['pictures identical'],
            c['pictures cut short by a death (hold every pixel of the original)'],
            'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            hooks: ' + ' '.join('%s=%d' % (k, c[k]) for k in HOOK_NAMES))
        say('            rooms %d; on-screen sprites %d; off-area pixels %d (%s), over the HUD %d; T +%.1f %%' % (
            sum(1 for k in c if k.startswith('room ')), c['sprites shown'], c['sprite pixels outside the play area'],
            ' '.join(k[9:] + '=%d' % v for k, v in c.items() if k.startswith('off area')), c['sprite pixels over the HUD'],
            100.0 * (c['T patched'] - c['T original']) / max(c['T original'], 1)))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
    never = [k for k in HOOK_NAMES if not total[k]]
    for r in a.rzx:
        pc = verify_plain(r, stop=quick)
        pf = {k: v for k, v in pc.items() if k.endswith('!')}
        ok = ok and not pf
        say('Plain     : %s against the original from after the code sheet, all registers and whole RAM + screen, %d compares -> %s' % (
            os.path.basename(r), pc['compares'], 'IDENTICAL' if not pf else 'FAILED %s' % dict(pc)))
    say('Start     : code entry not replayed (recordings begin at the sheet, the builds never show it): frames skipped %s; after the check, registers differing %s, memory bytes %s (the sheet\'s cells)' % (
        c['frames of code entry not compared'], c['start: registers differing after the check'], c['start: memory bytes differing after the check']))
    say('Coverage  : hooks that never ran in a recording: %s' % (', '.join(never) or 'none'))
    say('Speed     : hooks add %.2f %% of the T, estimated: (patched - original T) / 6, no real-machine timing' % (
        100.0 * (total['T patched'] - total['T original']) / 6 / max(total['T original'], 1)))
    say('Colours   : sprite ink vs the original cell at its top left, informational: %d same, %d not' % (
        total['sprite ink same as the original cell'], total['sprite ink differs from the original cell']))
    negs = negative_patches(patch)
    u = unit_tests(patch, None, negs if not quick else negs[:3], z80)
    ex_u = u.pop('_ex', [])
    uf = {k: v for k, v in u.items() if k.endswith('!')}
    ok = ok and not uf
    say('Unit      : %s -> %s' % (', '.join('%s %d' % (k[:-3], v) for k, v in sorted(u.items()) if k.endswith(' ok')),
                                  'PASS' if not uf else 'FAIL %s' % uf))
    say('            end game: 85DF at the end of the toilet run %d' % u['run to the toilet: 85DF at the end'])
    say('            slot guard %d; hooks in unit cases: %s' % (u['slot guard'], ' '.join(
        '%s=%d' % (k, u['unit hook ' + k]) for k in HOOK_NAMES)))
    for x in ex_u[:5]:
        say('            %s' % str(x)[:400])
    # negative controls on the first recording; each stops at its first failure
    if a.rzx:
        det = 0
        pc = verify_plain(a.rzx[0], stop=quick, start_sites=[x if x[0] != 0x5956 else (0x5956, '07', '18') for x in START_SITES])
        pd = any(k.endswith('!') for k in pc)
        ok = ok and pd
        say('Negative  : plain bypass with a wrong code cell: %s' % ('DETECTED %s' % [k for k in pc if k.endswith('!')][:1] if pd else 'NOT DETECTED!'))
        for nm, np in (negs if not quick else negs[:3]):
            nd = None
            for r in a.rzx:
                c, ex = verify(np, r, stop=quick)
                fails = [k for k, v in c.items() if k.endswith('!')]
                if fails:
                    nd = (os.path.basename(r), fails[0], next(iter(ex.values()), [None])[0])
                    break
            say('Negative  : %s: %s' % (nm, 'DETECTED %s' % str(nd)[:160] if nd else 'NOT DETECTED!'))
            det += bool(nd)
            ok = ok and bool(nd)
        say('Negative  : %d/%d detected on the real recordings; through the unit cases %d seen' % (
            det, len(negs if not quick else negs[:3]), u['negative controls detected through the unit cases']))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


# ---------------------------------------------------------------------------------------------
# Colour sheets (docs/COLOURS.md). Graphics never change, so the figures come from the code and one short run of every
# room: Willy and the pig all 8 frames, Maria's 4 frames, the toilet's 4, each room's item, every guardian frame drawn.
# ---------------------------------------------------------------------------------------------
GROUPS = ('willy', 'pig', 'maria', 'toilet', 'guardians', 'items')


def _part(get, g, group, inks, x=0, y=0, rows=16, width=2):
    """g: graphic address. inks: palette index by row. Ink pixels only: the sheet offers what can be painted."""
    px, ent = [], {}
    for r in range(rows):
        for b in range(width):
            a = g + r * width + b
            v = get(a)
            ent['%04X' % a] = [v, 'g']
            for k in range(8):
                if v >> (7 - k) & 1:
                    px.append((b * 8 + k, r, '%04X' % a, k, 1, inks[r]))
    return {'id': '%04X' % g, 'size': rows, 'w': width * 8, 'h': rows, 'x': x, 'y': y, 'mir': 0, 'pixels': px, 'entries': ent, 'group': group}


def _index(attr):
    i = attr & 7
    return 8 if not i else i | (8 if attr & 0x40 else 0)


def capture(z80):
    """-> (coloursheet composites, peek)."""
    from . import coloursheet as cs
    mem, regs = game_state(z80)
    get = mem.__getitem__
    col = cs.Collector(family=lambda p: None)
    parts = [_part(get, 0x9D00 + f * 32, 'willy', [7] * 16) for f in range(8)]
    parts += [_part(get, 0xB600 + f * 32, 'pig', [7] * 16) for f in range(8)]
    parts += [_part(get, 0x9C80 + f * 32, 'maria', [_index(0x45)] * 8 + [7] * 8) for f in range(4)]
    parts += [_part(get, 0xA600 + f * 32, 'toilet', [7] * 16) for f in range(4)]
    seen = set()
    for room in list(range(47)) + list(range(48, 61)):
        m, r = _at(mem, regs, 0x8912, [(0x8420, room)])
        tr = _Ins([0xFF] * 400)
        sim = _sim(m, r, tr)
        R, M, O = sim.registers, sim.memory, sim.opcodes
        try:
            for _ in range(6000000):
                if R[24] == 0x922E:
                    g = R[4] << 8 | R[5]
                    if g not in seen and GFX_LO <= g < GFX_HI:
                        seen.add(g)
                        ink = M[(R[8] << 8 | R[9]) + 1] & 15
                        parts.append(_part(get, g, 'guardians', [8 if not ink & 7 else ink] * 16))
                O[M[R[24]]]()
        except _End:
            pass
    items = {mem[0xA400 + i] & 0x3F for i in range(mem[0xA3FF], 256)}
    for room in sorted(items):
        a = 0xC000 + room * 256 + 0xE1
        parts.append(_part(get, a, 'items', [3] * 8, rows=8, width=1))
    for p in parts:
        col.add_frame([p])
    from skoolkit.snapshot import Snapshot
    snap = list(Snapshot.get(z80).memory)        # identity from the snapshot, as recolour reads it from the .nex
    return col.composites(list(GROUPS)), snap.__getitem__


def sheets(comps, prefix, colours=None, peek=None):
    from . import coloursheet as cs
    rgb16 = cs.palette_rgb(SPECCY)
    out = []
    for suffix in ('_PAINTING_SPRITES', '_REFERENCE_ALL_SPRITES'):
        png = prefix + suffix + '.png'
        n = cs.write(comps, png, os.path.splitext(png)[0] + '_layout.json', rgb16, colours, unique=False,
                     identity=colour_identity(peek) if peek else None)
        out.append((png, n))
    return out


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.jsw', description='Jet Set Willy colour sheets')
    ap.add_argument('cmd', choices=['sheet'])
    ap.add_argument('z80')
    ap.add_argument('prefix')
    a = ap.parse_args(argv)
    comps, get = capture(a.z80)
    for png, n in sheets(comps, a.prefix, None, get):
        print(png, n)


if __name__ == '__main__':
    _main()
