"""The Simpsons: Bart vs. the Space Mutants (Ocean, 1991, 128K) engine 'simpsons'. Additive module: reachable only through
is_simpsons(). Facts, design, results: games/simpsons.md.

The game runs in its interrupt handler, 50 times a second, on two screens it flips every frame; one routine draws every
figure from a pre-shifted shape of (mask, graphic) byte pairs. The build keeps the game's memory and both screens as the
original has them: four hooks (asm/simpsons_hooks.asm) wrap the draw routine at 28 MHz, note the shape, turn the clipped
figure into sprite patterns and list its sprites, and show the list at the flip. Each of the tape's five levels is its
own load with the same routines at other addresses: the sites are found by their bytes and written into the hook code.
"""
import collections
import hashlib
import json
import os
import re

from . import hooklib

ROM_ORG = 0x2000
ALT_PAGE, WORK, CPAGE = 24, 26, 28
A_, F_, SP_, R_, PC_, T_, IFF_ = 0, 1, 12, 15, 24, 25, 26
CMP = list(hooklib.CMP_R)
STACK = 2                               # bytes below SP a hook writes on the game's stack
T_LINE, LINES = 228, 311                # the 128K's frame
SIG_ENTRY = bytes.fromhex('DD5E00DD7E01E607')       # LD E,(IX+0) / LD A,(IX+1) / AND 7, 14 bytes after the entry
SIG_SHAPE = bytes.fromhex('E1D1F97BCB3FCB3F47')     # POP HL / POP DE / LD SP,HL / LD A,E / SRL A / SRL A / LD B,A
def _pat(*parts):
    """A byte pattern: hex strings are literal bytes, None is one operand word (a group)."""
    return re.compile(b''.join(b'(..)' if p is None else re.escape(bytes.fromhex(p)) for p in parts), re.S)


RE_NOTE = _pat('22', None, 'EB78D90203D9')       # LD (nn),HL / EX DE,HL / LD A,B / EXX / LD (BC),A / INC BC / EXX
RE_ALL = _pat('2A', None, '36003A')              # LD HL,(nn) / LD (HL),0 / LD A,(nn): the draw pass, after its counter
RE_FLIP = _pat('EE0132', None, '21')             # XOR 1 / LD (nn),A / LD HL,nn, after LD A,n whose operand it stores
WBYTES = (1, 2, 3, 4, 1, 2, 3, 4)       # bytes a row by width code; 5-7 are mirrored
_REV = bytes(int('{:08b}'.format(i)[::-1], 2) for i in range(256))
_HERE = os.path.dirname(os.path.abspath(__file__))
PLAIN_LINE = [0x000, 0x000, 0x1FF] + [0x000] * 13   # line 0: 1 the graphic's pixels black, 2 the mask's cleared pixels white
# The original's own time, T at 3.5 MHz. The width loops are the same code in every level: T a row by width code.
ROW_T = {0: 142, 1: 191, 2: 240, 3: 289, 4: 142, 5: 286, 6: 387, 7: 489}
# The rest by level (keyed by the draw pass's address): a draw's time before its rows (base), more for a mirrored figure,
# by the object's pre-shift kind, clipped at the top / bottom; a draw of nothing (off); the pass around its draws (loop).
# Made by fit_times() from a verify run with timing=True over the level's recording (games/simpsons.md).
TIMES = {
    0xB178: {'base': 945, 'mirror': 10, 'kind': {0: 0, 3: 96, 7: 88}, 'top': 175, 'bottom': 36, 'off': 579, 'loop': 1590},
    0x96FC: {'base': 922, 'mirror': 17, 'kind': {0: 0, 7: 88, 3: 96}, 'top': 179, 'bottom': 0, 'off': 554, 'loop': 1602},
    0x95FC: {'base': 946, 'mirror': 11, 'kind': {0: 0, 1: 72, 3: 96, 7: 88}, 'top': 175, 'bottom': 26, 'off': 564, 'loop': 1516},
    0x9704: {'base': 915, 'mirror': 8, 'kind': {0: 0, 3: 96, 7: 96}, 'top': 175, 'bottom': 36, 'off': 551, 'loop': 1510},
    0xAF04: {'base': 944, 'mirror': 8, 'kind': {0: 0, 7: 88, 3: 96}, 'top': 175, 'bottom': 0, 'off': 574, 'loop': 1526},
}


def fit_times(ex):
    """The level's timing constants from a timing run's examples (verify(..., timing=True)) -> dict for TIMES."""
    import statistics
    res = collections.defaultdict(list)
    for (code, rows, kind, mir, alt, top, bot), ts in ex['draw T by code and rows']:
        for t in ts:
            res[(kind, bool(mir), top, bot)].append(t - rows * ROW_T[code])
    med = {k: statistics.median(v) for k, v in res.items()}
    plain = [v for (kind, mir, top, bot), v in med.items() if not mir and not top and not bot]
    base = min(plain) if plain else min(med.values())
    kinds = {}
    for (kind, mir, top, bot), v in med.items():
        if not mir and not top and not bot:
            kinds[kind] = int(v - base)
    kinds.setdefault(7, max(kinds.values()) if kinds else 0)

    def extra(sel):
        d = [v - base - kinds.get(k[0], kinds[7]) for k, v in med.items() if sel(k)]
        return int(statistics.median(d)) if d else 0
    mirror = extra(lambda k: k[1] and not k[2] and not k[3])
    top = extra(lambda k: k[2]) - (mirror if all(k[1] for k in med if k[2]) else 0)
    bottom = extra(lambda k: k[3] and not k[1])
    off = ex['draw T when nothing is drawn']
    loop = ex['pass T around its draws']
    mean = lambda L: int(sum(t * n for t, n in L) / max(1, sum(n for t, n in L)))
    return {'base': int(base), 'mirror': mirror, 'kind': kinds, 'top': max(top, 0), 'bottom': max(bottom, 0), 'off': mean(off), 'loop': mean(loop)}


CH = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
COLOURS_NAME = 'simpsons_colours.json'     # the painted map, beside the snapshot (it holds the figures' outlines: not in the repo)
LEVEL_OF = {0xB178: 1, 0xAF04: 2, 0x96FC: 3, 0x95FC: 4, 0x9704: 5}                               # the draw pass's address -> the tape's level number (the painted map's key)


def load_colours(z80=None, path=None):
    """The painted map (made by the painting folder's sheet2colours.py): colours, pictures (a character a pixel) and, for
    each level, the stored shapes its recording drew: three keys of the shape's bytes, its size, its picture and the
    picture's place in it. None when there is none beside the snapshot."""
    p = path or (os.path.join(os.path.dirname(os.path.abspath(str(z80))), COLOURS_NAME) if z80 else None)
    return json.load(open(p)) if p and os.path.exists(p) else None


def shape_keys(g):
    """The hook's keys for a shape's bytes: the sum, and a 16-bit hash (hash * 3 + byte + 1) as two bytes."""
    a = h = 0
    for v in g:
        a = (a + v) & 255
        h = (h * 3 + v + 1) & 0xFFFF
    return a, h & 255, h >> 8


def rgb9(c):
    r, g, b = c
    return (r * 7 + 127) // 255 << 6 | (g * 7 + 127) // 255 << 3 | (b * 7 + 127) // 255


def palette_lines(cmap, level):
    """The level's pictures grouped into palette lines of at most 15 colours -> ([characters of each line], {picture: line})."""
    pics = sorted({e[4] for e in cmap['levels'][str(level)]})
    used = {p: {ch for row in cmap['pictures'][p]['rows'] for ch in row if ch != '.'} for p in pics}
    lines, line_of = [], {}
    for p in sorted(pics, key=lambda q: (-len(used[q]), q)):
        for li, ln in enumerate(lines):
            if len(set(ln) | used[p]) <= 15:
                ln += sorted(used[p] - set(ln))
                line_of[p] = li
                break
        else:
            if len(lines) == 15:
                raise ValueError('level %s needs more than 15 palette lines' % level)
            lines.append(sorted(used[p]))
            line_of[p] = len(lines) - 1
    return lines, line_of


def colour_tables(cmap, level):
    """-> ({page: 8K}, palette of 256 9-bit colours) for a painted map: the index page (256 chain heads by key 0, then an
    entry a shape) and the strips' pages: for a picture as stored and mirrored, each 16-pixel column's 8 bytes a line
    for every line of the shape."""
    lines, line_of = palette_lines(cmap, level)
    pal = list(PLAIN_LINE) * 16
    for li, ln in enumerate(lines):
        for k, ch in enumerate(ln):
            pal[(li + 1) * 16 + 1 + k] = rgb9(cmap['colours'][CH.index(ch)])
    blobs, where, pages = [bytearray()], {}, {}

    def strips(p, hh, y0, mir):
        key = (p, hh, y0, mir)
        if key not in where:
            pic = cmap['pictures'][p]
            w = pic['w']
            ncols = (w + 15) // 16
            out = bytearray(ncols * hh * 8)
            for y, row in enumerate(pic['rows']):
                for x, ch in enumerate(row):
                    if ch == '.':
                        continue
                    xx = w - 1 - x if mir else x
                    idx = 1 + lines[line_of[p]].index(ch)
                    o = (xx >> 4) * hh * 8 + (y0 + y) * 8 + ((xx & 15) >> 1)
                    out[o] |= idx << 4 if not xx & 1 else idx
            if len(blobs[-1]) + len(out) > 8192:
                blobs.append(bytearray())
            where[key] = (ncols, CPAGE + len(blobs), 0x4000 + len(blobs[-1]))
            blobs[-1] += out
        return where[key]

    index = bytearray(8192)
    at = 0x200
    for k0, k1, k2, size, p, dx, y0 in sorted(cmap['levels'][str(level)]):
        wb, hh = (size & 3) + 1, size >> 2
        w = cmap['pictures'][p]['w']
        ent = bytearray(index[2 * k0:2 * k0 + 2]) + bytes((k1, k2, size, (line_of[p] + 1) << 4))
        for mir, d in ((False, dx), (True, wb * 8 - dx - w)):
            ncols, pg, ad = strips(p, hh, y0, mir)
            ent += bytes((ncols, d, pg, ad & 255, ad >> 8))
        if at + len(ent) > 8192:
            raise ValueError('too many painted shapes for the index page')
        index[2 * k0:2 * k0 + 2] = (0x4000 + at).to_bytes(2, 'little')
        index[at:at + len(ent)] = ent
        at += len(ent)
    pages[CPAGE] = bytes(index)
    for i, b in enumerate(blobs):
        pages[CPAGE + 1 + i] = bytes(b).ljust(8192, b'\0')
    return pages, pal


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'simpsons.json'), os.path.join(_HERE, 'simpsons.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('simpsons.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def find_sites(mem):
    """The sites in a level's memory (64K as in play: banks 5, 2 and the paged one) -> dict, or None when the routines
    are not there. A the routine that draws every object, S the shape taken, N the width loop chosen, P the flip; F the
    draw routine's entry (not patched: the verifier times the original there)."""
    mem = bytes(mem)
    i = mem.find(SIG_ENTRY, 0x5B00)
    if i < 0 or mem.find(SIG_ENTRY, i + 1) >= 0:
        return None
    f = i - 14
    if mem[f:f + 2] != b'\xED\x73':
        return None
    s = mem.find(SIG_SHAPE, f, f + 0x200)
    n = RE_NOTE.search(mem, s, s + 0x200) if s >= 0 else None
    flips = [m for m in RE_FLIP.finditer(mem, 0x5B00) if int.from_bytes(m.group(1), 'little') == m.start() - 1 and mem[m.start() - 2] == 0x3E]
    alls = list(RE_ALL.finditer(mem, f - 0x80, f))
    if s < 0 or not n or len(flips) != 1 or len(alls) != 1:
        return None
    p = flips[0].start() + 2
    return {'A': alls[0].start(), 'F': f, 'S': s, 'N': n.start(), 'P': p, 'a_hl': int.from_bytes(alls[0].group(1), 'little'),
            'n_op': int.from_bytes(n.group(1), 'little'), 'p_op': int.from_bytes(flips[0].group(1), 'little')}


def play_view(snap):
    """64K of a SkoolKit 128K snapshot as the game sees it (ROM zeros)."""
    from .simrun import addr_view
    return bytes(addr_view(snap))


def is_simpsons(snap):
    if getattr(snap, 'machine', '48K') == '48K':
        return False
    try:
        return find_sites(play_view(snap)) is not None
    except Exception:
        return False


def work_page():
    """The state page as the build starts: the nibble tables, the bit-reverse table, an empty sprite list."""
    sy = {k: int(v, 16) for k, v in load_profile()['hooks']['syms'].items()}
    pg = bytearray(8192)
    pg[sy['V_ATP']:sy['V_ATP'] + 2] = sy['ATTRS'].to_bytes(2, 'little')
    for g in range(16):
        for m in range(16):
            px = [1 if g & (8 >> k) else 0 if m & (8 >> k) else 2 for k in range(4)]
            pg[sy['TLO'] + g * 16 + m] = px[0] << 4 | px[1]
            pg[sy['THI'] + g * 16 + m] = px[2] << 4 | px[3]
    pg[sy['REVT']:sy['REVT'] + 256] = _REV
    return pg


class Patch:
    name = 'The Simpsons figures -> hardware sprites (alt ROM hooks, state page at slot 0, colour pages at slot 2)'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000

    def __init__(self, z80=None, mem=None, colours=None, rom=None, work=None, times=None, level=None, blank=0, planes=None, palette=None):
        self.prof = load_profile()
        h = self.prof['hooks']
        self.syms = sy = {k: int(v, 16) for k, v in h['syms'].items()}
        self.z80, self.colours = z80, colours
        if mem is None and z80 is not None:
            from skoolkit.snapshot import Snapshot
            mem = play_view(Snapshot.get(str(z80)))
        self.lv = find_sites(mem) if mem is not None else None
        if self.lv is None:
            raise ValueError('not a level of The Simpsons: the draw routine is not found')
        lv = self.lv
        rc = bytearray(bytes.fromhex(h['rom']) if rom is None else rom)
        if rom is None:
            def put(sym, off, v):
                o = sy[sym] - ROM_ORG + off
                rc[o:o + 2] = v.to_bytes(2, 'little')
            put('fx_ahl', 1, lv['a_hl'])
            put('fx_ajp', 1, lv['A'] + 3)
            put('fx_sret', 1, lv['S'] + 3)
            put('fx_nop', 1, lv['n_op'])
            put('fx_nret', 1, lv['N'] + 3)
            put('fx_pop', 1, lv['p_op'])
            put('fx_pret', 1, lv['P'] + 3)
            tm = TIMES.get(lv['A']) if times is None else times
            if tm:
                for code, row in ROW_T.items():
                    for rows in range(64):
                        o = sy['TT'] - ROM_ORG + code * 128 + rows * 2
                        t = tm['base'] + (tm['mirror'] if code >= 5 else 0) + rows * row - tm['off']
                        rc[o:o + 2] = hooklib.lines16(max(t, 0), T_LINE).to_bytes(2, 'little')
                put('T_OFF', 0, hooklib.lines16(tm['off'], T_LINE))
                put('T_LOOP', 0, hooklib.lines16(tm['loop'], T_LINE))
                rc[sy['T_TOP'] - ROM_ORG] = hooklib.lines16(tm['top'], T_LINE)
                rc[sy['T_BOT'] - ROM_ORG] = hooklib.lines16(tm['bottom'], T_LINE)
                for k in range(8):
                    rc[sy['KT'] - ROM_ORG + k] = hooklib.lines16(tm['kind'].get(k, tm['kind'][7]), T_LINE)
        self.rom_code = bytes(rc)
        self.regblock = ROM_ORG + len(rc)
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = self.altrom0 = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        page = bytearray(rom48()[0x2000:0x4000])
        page[0:len(rc)] = rc
        self.page = bytes(page)
        self.stub_extra = bytes.fromhex(h['setup'])
        self.pbuf = bytes(mem[0x5B00:0x5C00])       # the game's data in the printer buffer, put back by the setup
        self.palette = list(PLAIN_LINE) * 16
        self._palette()
        self.work = bytes(work_page() if work is None else work)
        self.planes = {}
        self.level = level or LEVEL_OF.get(lv['A'])
        self.blank = blank              # empty colour pages, so the plain build has the banks the painted one has (.nxc sets)
        if colours:
            if self.level is None:
                raise ValueError('which level this is is not known: the painted map cannot be used')
            self.planes, self.palette = colour_tables(colours, self.level)
            rc = bytearray(self.rom_code)
            rc[sy['ENH'] - ROM_ORG] = 1
            self.rom_code = bytes(rc)
            page[0:len(rc)] = rc
            self.page = bytes(page)
            self._palette()
        elif blank:
            self.planes = {CPAGE + i: bytes(8192) for i in range(blank)}
        if planes is not None:          # (a negative control: the build's own tables, its code changed)
            self.planes = planes
            self.palette = list(palette)
            page[0:len(self.rom_code)] = self.rom_code
            self.page = bytes(page)
            self._palette()
        self.sites = [(lv['A'], bytes(mem[lv['A']:lv['A'] + 3]), b'\xC3' + sy['e_all'].to_bytes(2, 'little')),
                      (lv['S'], bytes(mem[lv['S']:lv['S'] + 3]), b'\xC3' + sy['e_shape'].to_bytes(2, 'little')),
                      (lv['N'], bytes(mem[lv['N']:lv['N'] + 3]), b'\xC3' + sy['e_note'].to_bytes(2, 'little')),
                      (lv['P'], bytes(mem[lv['P']:lv['P'] + 3]), b'\xC3' + sy['e_flip'].to_bytes(2, 'little'))]
        self._banks()

    def _palette(self):
        st = bytearray(self.stub_extra)
        if self.pbuf is not None:
            o = self.syms['pbuf'] - 0xD000
            st[o:o + 256] = self.pbuf
        o = self.syms['pal9'] - 0xD000
        for i, c in enumerate(self.palette):
            st[o + 2 * i], st[o + 2 * i + 1] = c >> 1, c & 1
        self.stub_extra = bytes(st)

    def _banks(self):
        self.extra_banks = {12: self.page + bytes(8192), 13: self.work + bytes(8192)}
        for pg, data in self.planes.items():
            cur = self.extra_banks.get(pg // 2, bytes(16384))
            o = (pg & 1) * 8192
            self.extra_banks[pg // 2] = cur[:o] + data + cur[o + 8192:]

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('The Simpsons patch expects the 128K snapshot')
        for a, old, new in self.sites:
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else None
            if bank is None:
                raise ValueError('site 0x%04X is in paged memory' % a)
            b = bytearray(snap.banks[bank])
            o = a & 0x3FFF
            if bytes(b[o:o + len(old)]) != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, bytes(b[o:o + len(old)]).hex(), old.hex()))
            b[o:o + len(new)] = new
            snap.banks[bank] = bytes(b)


# ---------------------------------------------------------------------------------------------
# The Next side, as a hook sees it
# ---------------------------------------------------------------------------------------------

class State:
    """What stays between hooks: the state page, sprite patterns and attributes."""
    def __init__(self, patch):
        self.work = bytearray(patch.work)
        self.pattern = bytearray(16384)
        self.attrs = [[0] * 5 for _ in range(128)]
        self.t = collections.Counter()  # real time in hooks by site, 3.5 MHz T
        self.line = 0.0                 # the video line's time carried from hook to hook
        self.pidx = 0                   # the pattern port's place, carried too
        self.aidx = self.abyte = 0      # and the attribute port's


class View:
    """64K as the hooks see it: the alt ROM image, the state page at slot 0 when NextReg 0x50 names it, a colour page
    at slot 2 when NextReg 0x52 names one, the game's memory."""
    def __init__(self, mem, rom, work, planes=None):
        self.mem, self.rom, self.work, self.planes = mem, rom, work, planes or {}
        self.model = None
        self.game_pc = None             # set while the game's own code runs: its reads of slot 0 are counted

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        if a < 0x2000:
            return self.work[a] if self.model.nr.get(0x50, 255) == WORK else self.rom[a]
        if a < 0x4000:
            return self.rom[a]
        if a < 0x6000 and self.model.nr.get(0x52, 10) != 10:
            return self.planes[self.model.nr[0x52]][a - 0x4000]
        return self.mem[a]

    def __setitem__(self, a, v):
        if a < 0x2000:
            if self.model.nr.get(0x50, 255) == WORK:
                self.work[a] = v
            return
        if a < 0x4000:
            return
        if a < 0x6000 and self.model.nr.get(0x52, 10) != 10:
            self.model.c['write to a colour page!'] += 1
            return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, st, speed=0):
        super().__init__(sim, speed, t_line=T_LINE, lines=LINES)
        self.pattern, self.attrs = st.pattern, st.attrs
        self.real = st.line
        self.pidx, self.aidx, self.abyte = st.pidx, st.aidx, st.abyte

    def nextreg(self, reg, v):
        if reg == 0x34:                 # without lockstep (NR 0x09 bit 4, off) this is not the attribute port's index
            self.nr[reg] = v
            return
        super().nextreg(reg, v)


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def run_hook(patch, st, rom, mem, regs, site, stop, sp_stop, limit=4000000):
    """Run the patched code from `site` (its JP into the hook) on a copy of the game's memory until PC = stop with
    SP = sp_stop and the ROM back at slot 0. -> (registers, the copy, model); model.n = instructions run."""
    from . import simpool
    m2 = bytearray(mem)
    for a, old, new in patch.sites:
        m2[a:a + len(new)] = new
    v = View(m2, rom, st.work, patch.planes)
    s = simpool.machine(_rw(), v, list(regs), 'simpsons-hook')
    model = Model(s, st)
    v.model = model
    R = s.registers
    R[PC_] = site
    n = 0
    while True:
        pc = R[PC_]
        if pc >= 0x4000 and model.nr.get(0x50, 255) == WORK and model.nr.get(0x52, 10) != 10:
            model.c['the game runs with a colour page mapped!'] += 1
        s.opcodes[v[pc]]()
        n += 1
        pc = R[PC_]
        if pc == stop and R[SP_] == sp_stop and model.nr.get(0x50, 255) == 255 and not v.work[patch.syms['V_IN']]:
            break
        if n > limit:
            raise AssertionError('hook at %04X did not end (PC %04X)' % (site, pc))
    st.t[site] += model.now() - st.line
    st.t_in = st.line
    st.line = model.now()
    st.pidx, st.aidx, st.abyte = model.pidx, model.aidx, model.abyte
    model.n = n
    for a, old, new in patch.sites:
        m2[a:a + len(old)] = old
    return list(R), m2, model


def run_orig(rom, mem, regs, stop, sp=None, limit=4000000):
    """The original from the registers' PC until PC = stop (and SP = sp when given), on a copy. -> (registers, the copy)."""
    from . import simpool
    m2 = bytearray(rom[:0x4000]) + bytearray(mem[0x4000:])
    s = simpool.machine(_rw(), m2, list(regs), 'simpsons-orig')
    R = s.registers
    n = 0
    while True:
        s.opcodes[m2[R[PC_]]]()
        n += 1
        if R[PC_] == stop and (sp is None or R[SP_] == sp):
            break
        if n > limit:
            raise AssertionError('original from %04X did not reach %04X' % (regs[PC_], stop))
    return list(R), m2


def sprite_bits(st):
    """{(x, y) on the screen: colour index | palette line << 4} from the shown sprites, in order (a later one on top)."""
    out = {}
    for n, a in enumerate(st.attrs):
        if not a[3] & 0x80:
            continue
        x = a[0] | (a[2] & 1) << 8
        y = a[1]
        if not a[3] & 0x40 or not a[4] & 0x80:
            raise AssertionError('sprite %d is not a 4-bit pattern' % n)
        q = (a[3] & 63) * 2 + (1 if a[4] & 0x40 else 0)
        pat = st.pattern[q * 128:q * 128 + 128]
        for py in range(16):
            for px in range(16):
                b = pat[py * 8 + px // 2]
                c = b >> 4 if not px & 1 else b & 15
                if c and 0 <= x + px - 32 < 256 and 0 <= y + py - 32 < 192:
                    out[(x + px - 32, y + py - 32)] = c | (a[2] >> 4) << 4
    return out


def sprite_colours(st, palette):
    """{(x, y): 9-bit colour} of the shown sprites."""
    return {k: palette[v] for k, v in sprite_bits(st).items()}


def figure_at(mem, regs, shape=None, shapes=None, cmap=None):
    """The figure the routine is about to draw at site N, by its own rule: -> {'px': {(x, y): 9-bit colour}, 'bit':
    {(x, y): the graphic's bit}, 'screen': 0x4000 or 0xC000, 'code', 'rows', 'data'} (an independent model of the width
    loops). Colours: the graphic's pixels black, the mask's cleared pixels white; with a painted map (shape = the
    shape's address and size, shapes = the level's {keys + size: entry}) the picture's colour for that pixel."""
    sp, rows, c = regs[SP_], regs[2], regs[3] >> 3
    de, ix = regs[4] << 8 | regs[5], regs[8] << 8 | regs[9]
    code = mem[ix] & 7
    wb, mir = WBYTES[code], code >= 5
    px, bits, screen, wrapped, past = {}, {}, None, 0, 0
    pic = None
    if cmap and shape:
        hh = shape[1] >> 2
        ent = shapes.get(shape_keys(mem[shape[0]:shape[0] + hh * wb * 2]) + (shape[1],))
        if ent and (sp - shape[0]) % (wb * 2) == 0:     # (the game's top clip steps 6 bytes a row whatever the width: a
            pic, dx, y0 = cmap['pictures'][ent[4]], ent[5], ent[6]      # figure drawn from the middle of its rows is left unpainted)
            skip = (sp - shape[0]) // (wb * 2)
    for y in range(rows):
        a = mem[de + 2 * y] | mem[de + 2 * y + 1] << 8
        for b in range(wb):
            mk, g = mem[sp + (y * wb + b) * 2], mem[sp + (y * wb + b) * 2 + 1]
            col = (a & 31) + c + (wb - 1 - b if mir else b)
            if mir:
                mk, g = _REV[mk], _REV[g]
            screen = a & 0xC000
            if col > 31:                # past the right edge the routine's 8-bit address wraps: those bytes stay
                wrapped += 1            # the game's own drawing on the screen, no sprite lies on them
                continue
            o = ((a & 0x3FE0) | col)
            if o >= 0x1800:
                continue
            sy = (o >> 5 & 0xC0) | (o >> 2 & 0x38) | (o >> 8 & 7)
            sx = (o & 31) * 8
            for k in range(8):
                bit = 0x80 >> k
                if not g & bit and mk & bit:
                    continue
                if pic and skip + y >= hh:      # clipped at the top the game draws on past the shape's last line:
                    past += 1                   # the painted build leaves those rows to the game's own drawing
                    continue
                bits[(sx + k, sy)] = 1 if g & bit else 0
                col = 0x000 if g & bit else 0x1FF
                if pic:
                    fx = (wb - 1 - b if mir else b) * 8 + k         # the pixel's place across the figure on the screen
                    px_, py_ = (wb * 8 - 1 - fx if mir else fx) - dx, skip + y - y0
                    ch = pic['rows'][py_][px_] if 0 <= py_ < pic['h'] and 0 <= px_ < pic['w'] else '.'
                    col = rgb9(cmap['colours'][CH.index(ch)]) if ch != '.' else -1
                px[(sx + k, sy)] = col
    kind = (mem[ix + 1] & 7, mem[ix] & 4, mem[ix] & 0x10)
    return {'px': px, 'bit': bits, 'screen': screen, 'code': code, 'rows': rows, 'data': sp, 'wrapped': wrapped, 'kind': kind, 'painted': bool(pic), 'past': past}


def isr_entry(z80):
    """Where the snapshot's IM 2 interrupt enters (the vector read with 0xFF on the bus)."""
    from skoolkit.snapshot import Snapshot
    sn = Snapshot.get(str(z80))
    mem = play_view(sn)
    v = (sn.i << 8) | 0xFF
    return mem[v] | mem[(v + 1) & 0xFFFF] << 8


def flat(m):
    """64K of the replay's memory as the game sees it now."""
    return b''.join(bytes(p) for p in m.memory)


def verify(patch, rzx_path, stop=None, collect=0, progress=None, timing=False, on_flip=None):
    """Replay the original (PLAYBOOK 6). At the draw routine's entry and at the flip the patched code runs on a copy of
    the state, the Next side carried from site to site, and must leave every register (R too) and all the game's memory
    as the original does. At every flip the sprites must be the figures drawn since the last one, by the width loops'
    rule (an independent model), and each sprite pixel must lie on its figure's pixel of the screen the flip shows.
    -> (Counter, examples, states)."""
    from . import rzx as RZ
    from .nextboot import alt_image0
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    kept = collections.Counter()
    rom = bytes(alt_image0(patch))
    st = State(patch)
    lv = patch.lv
    A, F, N, P = lv['A'], lv['F'], lv['N'], lv['P']
    shapes = {tuple(e[:4]): e for e in patch.colours['levels'][str(patch.level)]} if patch.colours else {}
    isr = isr_entry(patch.z80) if patch.z80 else None
    box = {'figs': [], 'pend': None, 'tt': collections.defaultdict(set), 'toff': collections.Counter(), 'orig_t': 0,
           'loop': collections.Counter(), 'sum': 0, 'shown': {}, 'shown_at': 0}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(ex[key]) < 5:
            ex[key].append(detail)

    def same(name, Ro, mo, Rp, mp, sp):
        bad = [(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]]
        if bad:
            fail('registers after %s' % name, (c['frames seen'], bad))
        if mp[0x4000:sp - STACK] != mo[0x4000:sp - STACK] or mp[sp:] != mo[sp:]:
            fail('%s writes game memory' % name, [hex(a) for a in range(0x4000, 65536) if mp[a] != mo[a] and not sp - STACK <= a < sp][:8])

    def on(pc, sim):
        if box.get('dead'):
            return
        try:
            on_(pc, sim)
        except AssertionError as e:
            box['dead'] = True
            fail('a hook does not end', str(e))

    def on_(pc, sim):
        m, R = sim.memory, sim.registers
        if pc == isr:                   # every frame: the shown sprites lie on their figures on the screen now shown
            c['frames checked'] += 1
            scr = m.banks[7] if m.o7ffd & 8 else m.banks[5]
            for (x, y), v in box['shown'].items():
                if scr[(y & 0xC0) << 5 | (y & 0x38) << 2 | (y & 7) << 8 | x >> 3] >> (7 - (x & 7)) & 1 != v:
                    c['frames a shown sprite is not on its figure on the visible screen'] += 1
                    if len(ex['frames a shown sprite is off its figure']) < 5:
                        ex['frames a shown sprite is off its figure'].append((box['shown_at'], c['frames checked'], x, y))
                    break
            return
        regs = list(R)
        mem = bytearray(flat(m))
        if bytes(mem[F:F + 2]) != b'\xED\x73' or mem[P] != 0x32:
            return                      # the level's code is not in place (never seen)
        sp = regs[SP_]
        if pc == lv['S']:               # the shape the routine takes: its address and size, as the table gives them
            box['shp'] = (mem[sp] | mem[sp + 1] << 8, mem[sp + 2])
            return
        if pc == N:
            f = figure_at(mem, regs, box.get('shp'), shapes, patch.colours)
            c['painted figures'] += f['painted']
            c['pixels of rows drawn past a shape\'s end (left on the screen)'] += f['past']
            if f['past'] and not c['first frame with a row past a shape\'s end']:
                c['first frame with a row past a shape\'s end'] = c['frames checked']
            box['figs'].append(f)
            if not box.get('in'):
                fail('a figure drawn outside the draw pass', hex(mem[sp] | mem[sp + 1] << 8))
            c['figure bytes wrapped past the right edge (left on the screen)'] += f['wrapped']
            if box['pend'] is not None:
                top = f['data'] != box['shape'][0]
                bot = not top and f['rows'] != box['shape'][1]
                box['tt'][(f['code'], f['rows']) + f['kind'] + (top, bot)].add(box['pend'])
                box['noted'] = True
            return
        if pc == F:                     # the original's own time for this draw (the hooks' table is made from these)
            if box['pend'] is not None and not box.get('noted'):
                box['toff'][box['pend']] += 1
            c['draws'] += 1
            box['pend'] = None
            if timing:
                ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF)
                Ro, mo = run_orig(rom, mem, regs, ret[0], ret[1])
                box['pend'], box['noted'] = Ro[T_] - regs[T_], False
                box['sum'] += Ro[T_] - regs[T_]
                box['shape'] = None
                Rs, ms = run_orig(rom, mem, regs, lv['S'] + 3)
                box['shape'] = (Rs[6] << 8 | Rs[7], Rs[5] >> 2) if Rs[PC_] == lv['S'] + 3 else (0, 0)
            return
        if collect and kept[pc] < collect:
            kept[pc] += 1
            states.append((pc, bytes(mem), tuple(regs), bytes(st.work)))
        if regs[IFF_]:
            fail('interrupts on at a hook', hex(pc))
        if pc == A:
            if box.get('in') and timing:
                box['loop'][box['pass_t'] - box['sum']] += 1
            c['draw passes'] += 1
            ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF)
            Ro, mo = run_orig(rom, mem, regs, ret[0], ret[1])
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, ret[0], ret[1])
            same('the draw pass', Ro, mo, Rp, mp, sp)
            box['orig_t'] += Ro[T_] - regs[T_]
            box['pass_t'], box['sum'], box['in'] = Ro[T_] - regs[T_], 0, True
            d = int(model.now() - st.t_in - (Ro[T_] - regs[T_]) + box.pop('flip_d', 0))     # with the flips since the last pass
            c['most T a pass takes over the original'] = max(c['most T a pass takes over the original'], d)
            c['most T a pass takes under the original'] = max(c['most T a pass takes under the original'], -d)
            c['passes more than 700 T off the original'] += abs(d) > 700
            if model.nr[7] & 3:
                fail('the draw pass leaves its speed', model.nr[7])
            if model.nr.get(0x52, 10) != 10:
                fail('the draw pass leaves a colour page mapped', model.nr.get(0x52))
            bad = {k: v for k, v in model.c.items() if k.endswith('!')}
            if bad:
                fail('a write where none may be', bad)
            return
        # the flip
        c['flips'] += 1
        figs, box['figs'] = box['figs'], []
        Ro, mo = run_orig(rom, mem, regs, P + 3)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, P + 3, sp)
        same('the flip', Ro, mo, Rp, mp, sp)
        box['flip_d'] = box.get('flip_d', 0) + model.now() - st.t_in - (Ro[T_] - regs[T_])
        if not box.get('in'):
            box['flip_d'] = 0           # (before the first pass: menus, where nothing repays a flip)
        if model.nr[7] & 3:
            fail('the flip leaves its speed', model.nr[7])
        if not model.burst_ok():
            fail('attributes split by pattern uploads', c['flips'])
        bad = {k: v for k, v in model.c.items() if k.endswith('!')}
        if bad:
            fail('a write where none may be', bad)
        want, bit = {}, {}
        for f in figs:
            want.update(f['px'])
            bit.update(f['bit'])
        got = sprite_colours(st, patch.palette)
        c['painted pixels'] += sum(1 for f in figs if f['painted'] for _ in f['px'])
        c['figures'] += len(figs)
        c['most figures'] = max(c['most figures'], len(figs))
        c['most sprites'] = max(c['most sprites'], sum(1 for a in st.attrs if a[3] & 0x80))
        c['sprite pixels compared'] += len(want)
        if want != got:
            d = [k for k in set(want) | set(got) if want.get(k) != got.get(k)]
            fail('the sprites are not the drawn figures', (c['flips'], len(d), sorted(d)[:4], [(f['code'], f['rows']) for f in figs]))
        screens = {f['screen'] for f in figs}
        box['shown'], box['shown_at'] = bit, c['flips']
        if on_flip:                     # (tools: a picture of the screen this flip shows, with its sprites)
            on_flip(c['flips'], mem, screens, got)
        if len(screens) > 1:
            fail('figures of both screens in one list', c['flips'])
        for scr in screens:
            base = 0x4000 if scr == 0x4000 else 0xC000
            if scr == 0xC000 and (m.o7ffd & 7) != 7:
                c['flips with bank 7 away'] += 1
                continue
            owner = {}
            for k, f in enumerate(figs):
                for xy in f['bit']:
                    owner[xy] = k
            over = set()
            for (x, y), v in bit.items():
                a = base + ((y & 0xC0) << 5 | (y & 0x38) << 2 | (y & 7) << 8 | x >> 3)
                if mem[a] >> (7 - (x & 7)) & 1 != v:
                    over.add(owner[(x, y)])
            # The game sometimes redraws scenery over a figure it has just drawn (level 5's belts): the original
            # shows the scenery for that frame, the build the figure. Counted, and limited below.
            c['figures the game drew scenery over before the flip (the sprite shows)'] += len(over)
            if over and len(ex['figures under scenery']) < 5:
                ex['figures under scenery'].append((c['flips'], sorted(over)))

    fc, err = RZ.trace(rzx_path, {A, F, N, P, lv['S']} | ({isr} if isr else set()), on, stop=stop)
    c['frames'] = fc
    if err:
        c['replay stopped!'] += 1
        ex['replay'].append(err)
    off = c['figures the game drew scenery over before the flip (the sprite shows)']
    if off > 0.001 * c['figures'] + 1:
        fail('sprites are not on their figures on the screen', (off, c['figures']))
    if c['frames a shown sprite is not on its figure on the visible screen'] > 0.001 * c['frames checked'] + 1:
        fail('shown sprites are not on the visible screen\'s figures', c['frames a shown sprite is not on its figure on the visible screen'])
    # Pace: the waits end on whole video lines and carry what is left, so a pass lands a few lines either side of the
    # original's time; over the recording the hooks must take the original's time to 0.5% of the frames' time.
    if TIMES.get(A) and c['draw passes'] and (c['passes more than 700 T off the original'] > 0.06 * c['draw passes'] + 10
                                             or abs(sum(st.t.values()) - box['orig_t']) > 0.005 * fc * LINES * T_LINE):
        fail('the draw passes do not take the original\'s time', (c['passes more than 700 T off the original'], c['draw passes'], int(sum(st.t.values())), box['orig_t']))
    c['T original draw passes'] = box['orig_t']
    c['T hooks'] = int(sum(st.t.values()))
    ex['draw T by code and rows'] = sorted((k, sorted(v)) for k, v in box['tt'].items())
    ex['draw T when nothing is drawn'] = sorted(box['toff'].items())
    ex['pass T around its draws'] = sorted(box['loop'].items())
    return c, dict(ex), states


def _differs(Ro, mo, Rp, mp, sp):
    """What a hook left unlike the original: registers, or game memory outside the dead stack."""
    bad = [(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]]
    return bad, [a for a in range(0x4000, 65536) if mp[a] != mo[a] and not sp - STACK <= a < sp][:6]


def unit_tests(patch, states, neg=None):
    """The paths the recordings do not reach, from captured states (site, memory, registers, state page)."""
    from .nextboot import alt_image0
    c = collections.Counter()
    rom = bytes(alt_image0(patch))
    sy, lv = patch.syms, patch.lv
    by = collections.defaultdict(list)
    for pc, mem, regs, work in states:
        by[pc].append((bytearray(mem), list(regs), work))

    def fresh(work):
        st = State(patch)
        st.work = bytearray(work)
        return st

    def ok(name, cond):
        c[name if cond else name + '!'] += 1

    def run_pass(st, mem, regs):
        sp = regs[SP_]
        ret = (mem[sp] | mem[sp + 1] << 8, (sp + 2) & 0xFFFF)
        Ro, mo = run_orig(rom, mem, regs, ret[0], ret[1])
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, lv['A'], ret[0], ret[1])
        return _differs(Ro, mo, Rp, mp, sp) == ([], []), model

    def run_flip(st, mem, regs):
        Ro, mo = run_orig(rom, mem, regs, lv['P'] + 3)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, lv['P'], lv['P'] + 3, regs[SP_])
        return _differs(Ro, mo, Rp, mp, regs[SP_]) == ([], []), model

    for mem, regs, work in by[lv['P']][-2:]:
        # nothing listed, nothing shown: the flip changes nothing on the Next side but the pattern set
        st = fresh(work)
        st.work[sy['V_N']] = st.work[sy['V_PREV']] = 0
        same, model = run_flip(st, mem, regs)
        ok('flip with no figures', same and not any(a[3] & 0x80 for a in st.attrs) and not model.c['pattern bytes'])
        # the figures left since the last flip: every sprite it showed goes off
        st = fresh(work)
        st.work[sy['V_N']], st.work[sy['V_PREV']] = 0, 30
        for k in range(30):
            st.attrs[k][3] = 0xC0 | k
        same, model = run_flip(st, mem, regs)
        ok('flip after the figures left', same and not any(a[3] & 0x80 for a in st.attrs) and st.work[sy['V_PREV']] == 0)
        # the sets change over at every flip
        st = fresh(work)
        before = st.work[sy['V_SET']]
        same, model = run_flip(st, mem, regs)
        ok('pattern sets change over', same and st.work[sy['V_SET']] == before ^ 64 == st.work[sy['V_Q']] and st.pidx == (before ^ 64) * 128)
    unknown = []
    for mem, regs, work in by[lv['A']][-3:]:
        # the sprite list nearly full: figures that do not fit are left out, the game is the same
        st = fresh(work)
        st.work[sy['V_N']] = sy['NSPR'] - 1
        st.work[sy['V_ATP']:sy['V_ATP'] + 2] = (sy['ATTRS'] + 5 * (sy['NSPR'] - 1)).to_bytes(2, 'little')
        same, model = run_pass(st, mem, regs)
        ok('sprite list full', same and st.work[sy['V_N']] <= sy['NSPR'])
        # the pattern set nearly full: nothing is uploaded past the set
        st = fresh(work)
        base = st.work[sy['V_SET']]
        st.work[sy['V_Q']] = base + 63
        st.pidx = (base + 63) * 128
        same, model = run_pass(st, mem, regs)
        ok('pattern set full', same and st.work[sy['V_Q']] <= base + 64 and st.pidx <= (base + 64) * 128)
        # a pass with every object off: no figure, the pass's own time only
        m2 = bytearray(mem)
        st = fresh(work)
        n0 = st.work[sy['V_N']]
        for a in OBJECTS(m2, lv):
            m2[a] &= 0x7F
        same, model = run_pass(st, m2, regs)
        ok('pass with no objects', same and st.work[sy['V_N']] == n0 and not model.c['pattern bytes'])
        if patch.colours:               # a shape the map does not know (one bit of it changed): drawn unpainted
            m2 = bytearray(mem)
            st = fresh(work)
            st.work[sy['V_N']] = 0
            st.work[sy['V_ATP']:sy['V_ATP'] + 2] = sy['ATTRS'].to_bytes(2, 'little')
            same0, model = run_pass(st, m2, regs)
            lines0 = [st.work[sy['ATTRS'] + 5 * k + 2] >> 4 for k in range(st.work[sy['V_N']])]
            for a in range(0x6000, 0x10000):
                m2[a] ^= 0x00
            shp = st.work[sy['V_N'] + 6] | st.work[sy['V_N'] + 7] << 8      # V_SHAPE: the last figure's shape
            m2[shp + 1] ^= 0x01         # a graphic bit of its first byte pair
            st = fresh(work)
            st.work[sy['V_N']] = 0
            st.work[sy['V_ATP']:sy['V_ATP'] + 2] = sy['ATTRS'].to_bytes(2, 'little')
            same, model = run_pass(st, m2, regs)
            lines = [st.work[sy['ATTRS'] + 5 * k + 2] >> 4 for k in range(st.work[sy['V_N']])]
            ok('unknown shape: the game the same', same and same0)
            unknown.append(any(lines0) and lines.count(0) > lines0.count(0))
    if unknown:                         # (the last figure of a captured pass is not always a painted one)
        ok('unknown shape drawn unpainted', any(unknown))
    return c


def OBJECTS(mem, lv):
    """Addresses of the object records the draw pass visits: the LD IX,nn operands between the pass and the draw."""
    out = []
    a = lv['A']
    while a < lv['F'] - 4:
        if mem[a] == 0xDD and mem[a + 1] == 0x21:
            out.append(mem[a + 2] | mem[a + 3] << 8)
            a += 4
        else:
            a += 1
    last = out[-1]
    return out + [last + 0x1C * k for k in range(1, 9)]


def _code_patch(patch, sym, new):
    """A copy of the build with bytes changed at a label of the hook code (negative controls)."""
    rc = bytearray(patch.rom_code)
    a = patch.syms[sym] - ROM_ORG
    rc[a:a + len(new)] = new
    return Patch(z80=patch.z80, colours=patch.colours, rom=bytes(rc), level=patch.level, blank=patch.blank,
                 planes=patch.planes if patch.colours else None, palette=patch.palette)


PAINTED_NEGATIVES = ('the shape\'s hash leaves a step out', 'a mirrored figure painted as a plain one', 'a painted figure\'s rows run past its shape')


def negative_patches(patch):
    """Broken builds a verify run on a recording must catch: [(name, patch)]."""
    r_n = patch.rom_code[patch.syms['fx_nop.n_r'] - ROM_ORG + 1]
    out = [('the attribute port\'s sprite is not selected', _code_patch(patch, 'show.n_sel', b'\x00\x00')),
           ('the pattern sets do not change over', _code_patch(patch, 'show.n_set', b'\xEE\x00')),
           ('a mirrored figure noted as a plain one', _code_patch(patch, 'noted.n_mir', b'\xFE\x08')),
           ('patterns with the low pixels of each byte wrong', _code_patch(patch, 'pxpair.n_lo', b'\xE6\x0F')),
           ('R one more after a figure', _code_patch(patch, 'fx_nop.n_r', bytes((0xC6, (r_n + 1) & 255)))),
           ('the pass\'s time is not waited out', _code_patch(patch, 'all_end.n_wait', b'\x00\x00\x00')),
           ('sprites left on when the figures go', _code_patch(patch, 'show.hide', b'\xAF\x00\x00')),
           ('sprites one line low', _code_patch(patch, 'n_y', b'\xC6\x21'))]
    if patch.colours:
        out.append(('a painted figure\'s rows run past its shape', _code_patch(patch, 'painted.n_rw', b'\x00')))
    if patch.colours:
        out += [('the shape\'s hash leaves a step out', _code_patch(patch, 'key.n_h', b'\x00')),
                ('a mirrored figure painted as a plain one', _code_patch(patch, 'painted.n_m', b'\x00'))]
    return out


class PlainPatch:
    """The plain .nex: no hooks. Alt ROM image 0 = the 128K ROM 0 the game reads bytes of (the Next's own ROM 0 has
    others), with the start-up's register block in it."""
    name = 'The Simpsons plain conversion, the 128K ROM 0 as alt ROM image 0'
    stub_extra = b''
    setup_call = None
    hook_page_data = b''
    uses_printer_buffer = False
    sites = []

    def __init__(self, z80=None):
        from .build import rom48
        if z80 is not None:             # the game's data in the printer buffer, put back by the setup
            from skoolkit.snapshot import Snapshot
            h = load_profile()['hooks']
            st = bytearray(bytes.fromhex(h['plain']))
            o = int(h['syms']['ppbuf'], 16) - 0xD000
            st[o:o + 256] = play_view(Snapshot.get(str(z80)))[0x5B00:0x5C00]
            self.stub_extra, self.setup_call = bytes(st), 0xD000
        self.regblock = ROM_ORG
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = self.altrom0 = (ROM_ORG, self.regblock + 20)
        self.page = bytes(rom48()[0x2000:0x4000])
        self.extra_banks = {12: self.page + bytes(8192)}

    def apply(self, snap):
        pass


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched
    snapshot, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites). -> problems."""
    from . import nextboot
    from . import z80tonex as zt
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, patch.slot1, True)[0])
    tail = zt.choose_tail_addr(s, size, None, False)[0]
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 65536):
            if tail <= a < tail + size:
                continue                # (the printer buffer is compared too: the setup puts the game's data back)
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    os.makedirs(out, exist_ok=True)
    say('Game      : %s' % name)
    try:
        patch = Patch(z80=z80)
    except ValueError as e:
        say('Engine    : simpsons: %s' % e)
        say('Result    : FAILED')
        return False
    cmap = load_colours(z80)
    ep = Patch(z80=z80, colours=cmap) if cmap and patch.level else None
    patch = Patch(z80=z80, blank=len(ep.planes) if ep else 0)
    say('Engine    : simpsons, level %s (the game\'s memory and both screens stay the original\'s; each figure the draw routine clips -> '
        'sprites at the screen flip); sites %s' % (patch.level or '?', ', '.join('%s 0x%04X' % (k, patch.lv[k]) for k in 'ASNP')))
    builds, ok = [], True
    for label, suffix, pt in (('Plain', '', PlainPatch(z80)), ('Sprites', '_sprites', patch), ('Enhanced', '_enhanced', ep)):
        if pt is None:
            continue
        nex = os.path.join(out, name + suffix + '.nex')
        zt.convert(str(z80), nex, patch=pt, quiet=True)
        bad = boot_check(nex, z80, PlainPatch(z80) if pt.sites == [] else Patch(z80=z80, colours=pt.colours, blank=pt.blank))
        ok = ok and not bad
        extra = ''
        if label == 'Enhanced':
            lines, _ = palette_lines(cmap, patch.level)
            extra = '  (%d painted shapes, %d palette lines, %d colour pages)' % (len(cmap['levels'][str(patch.level)]), len(lines), len(pt.planes))
        say('%-10s: %s  %s  boot %s%s' % (label, os.path.basename(nex), md5(nex), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], extra))
        if label != 'Plain':
            builds.append(('Verify' if label == 'Sprites' else 'Painted', pt))
    states = []
    past_at = 0
    quick = getattr(a, 'quick', None)
    for label, pt in builds:
        for r in list(getattr(a, 'rzx', None) or []):
            cc, ex, st = verify(pt, r, stop=quick, collect=3 if pt is patch else 0)
            states += st
            if pt is ep and r == list(a.rzx)[0]:
                past_at = cc['first frame with a row past a shape\'s end']
            fails = {k: v for k, v in cc.items() if k.endswith('!')}
            ok = ok and not fails
            say('%-10s: %s  %d frames, %d draw passes, %d draws, %d figures (%d painted), %d flips, most figures %d, most sprites %d, %d sprite pixels '
                '(%d painted), %d frames checked against the visible screen (%d off), %d figures under scenery the game drew after them, %d figure bytes left on the screen past the right edge -> %s' % (
                    label, os.path.basename(r), cc['frames'], cc['draw passes'], cc['draws'], cc['figures'], cc['painted figures'], cc['flips'],
                    cc['most figures'], cc['most sprites'], cc['sprite pixels compared'], cc['painted pixels'], cc['frames checked'], cc['frames a shown sprite is not on its figure on the visible screen'],
                    cc['figures the game drew scenery over before the flip (the sprite shows)'],
                    cc['figure bytes wrapped past the right edge (left on the screen)'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
            say('Pace      : %s  the draw passes %d T in the original, the hooks %d T (%+.3f%% of the recording\'s time); a pass with its flips at most '
                '%d T over, %d T under; %d of %d more than 700 T (3 lines) off' % (
                    os.path.basename(r), cc['T original draw passes'], cc['T hooks'], 100.0 * (cc['T hooks'] - cc['T original draw passes']) / max(1, cc['frames'] * LINES * T_LINE),
                    cc['most T a pass takes over the original'], cc['most T a pass takes under the original'], cc['passes more than 700 T off the original'], cc['draw passes']))
            for k, v in ex.items():
                if not k.startswith('draw T') and not k.startswith('pass T'):
                    say('            %s: %s' % (k, str(v)[:300]))
    if states:
        for label, pt in builds:
            u = unit_tests(pt, states)
            uf = {k: v for k, v in u.items() if k.endswith('!')}
            ok = ok and not uf
            say('Unit      : %s: %s -> %s' % (label, ', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.endswith('!')), 'PASS' if not uf else 'FAIL %s' % uf))
    if getattr(a, 'rzx', None):
        r0 = list(a.rzx)[0]
        negs = negative_patches(patch) + [n for n in (negative_patches(ep) if ep else []) if n[0] in PAINTED_NEGATIVES]
        missed = []
        for nm, q in negs:
            stop = quick or 1500
            if nm == PAINTED_NEGATIVES[2]:      # only a recording that clips a painted figure past its shape shows it
                if not past_at:
                    continue
                stop = None             # (the rows after a strip can be clear: the whole recording)
            cc, _, _ = verify(q, r0, stop=stop)
            if not any(k.endswith('!') for k in cc):
                missed.append(nm)
        ok = ok and not missed
        if not past_at:
            negs = [n for n in negs if n[0] != PAINTED_NEGATIVES[2]]
        say('Negative  : %d broken builds (%s), %d detected%s' % (len(negs), os.path.basename(r0), len(negs) - len(missed),
                                                                 '' if not missed else '; NOT detected: ' + ', '.join(missed)))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
