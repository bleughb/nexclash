"""Olli and Lissa: The Ghost of Shilmoore Castle (Firebird, 1986; 48K code, a 128K snapshot) engine 'olli_and_lissa'.
Additive module: reachable only through is_olli_and_lissa(). Facts, design, results: games/olli_and_lissa.md.

The game never enables interrupts and draws every moving figure straight to the screen with one routine: the clean
room from its copy, AND the figure's mask, OR its graphic. The build changes nothing of the game: at each CALL of that
routine a hook puts the figure's picture into sprites that lie on the pixels the game then draws
(asm/olli_and_lissa_hooks.asm); the routine runs at 28 MHz and its own time is waited out.
"""
import collections
import hashlib
import json
import os

from . import hooklib

ROM_ORG = 0x2800
ALT_PAGE, WORK, CPAGE = 24, 26, 28
A_, F_, SP_, R_, PC_, T_, IFF_ = 0, 1, 12, 15, 24, 25, 26
CMP = list(hooklib.CMP_R)
T_LINE, LINES = 228, 311                # the 128K's frame
FIG, WIPE = 0x89DA, 0x82EB
SITES = {0x8C18: 'e_obj', 0x88B7: 'e_olli', 0x8946: 'e_caul', 0x8F51: 'e_big', 0x86B2: 'e_olli'}   # CALL 0x89DA
KIND = {0x8C18: 0, 0x88B7: 1, 0x8946: 2, 0x8F51: 3, 0x86B2: 1}       # (0x86B2: Olli in another pose, at his place)
WIPES = {0x82E0: 'e_room', 0x8F7E: 'e_wipe', 0x90A1: 'e_wipe', 0x90FA: 'e_wipe', 0xFB4B: 'e_wipe'}      # CALL 0x82EB
SIGNATURE = (FIG, bytes.fromhex('d55e2356ed53a08b235e2356ed53a28b7857c60747d6b0380a'))
NENT, E_SIZE, PER = 10, 24, 12          # figures at a time, bytes an entry, sprites a figure
SIZES = [(r, n) for r in range(8, 57, 8) for n in range(1, 6)]
FAST = 8.0
TAIL_ADDR = 0x7F80                      # 0x7F72-0x81D1 is zeros below the game's stack; no recording touches the tail's bytes
EVENT = 0x824D                          # the record of the scene when Olli is caught (the next is 0x8260): below the room's objects
STALE = 8                               # calls of the routine a figure may go undrawn before its sprite must still match the screen
WIPE_STACK = 4                          # bytes under SP the wipe's hook writes (AF twice)
BOTTOM = 175                            # the last line of the play area: the sprites' window ends there
COLOURS_NAME = 'olli_and_lissa_colours.json'    # the painted map, beside the snapshot (it holds the figures: not in the repo)
WHITE, BLACK = 0x1FF, 0x000
_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'olli_and_lissa.json'), os.path.join(_HERE, 'olli_and_lissa.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('olli_and_lissa.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def play_view(snap):
    """64K of a SkoolKit 128K snapshot as the game sees it (ROM zeros)."""
    from .simrun import addr_view
    return bytes(addr_view(snap))


def is_olli_and_lissa(snap):
    if getattr(snap, 'machine', '48K') == '48K':
        return False
    try:
        m = play_view(snap)
        return m[SIGNATURE[0]:SIGNATURE[0] + len(SIGNATURE[1])] == SIGNATURE[1]
    except Exception:
        return False


def load_colours(z80=None, path=None):
    """The painted map (the painting folder's sheet2colours.py). None when there is none beside the snapshot."""
    p = path or (os.path.join(os.path.dirname(os.path.abspath(str(z80))), COLOURS_NAME) if z80 else None)
    return json.load(open(p)) if p and os.path.exists(p) else None


# ---------------------------------------------------------------------------------------------
# A figure, as the game's routine draws it
# ---------------------------------------------------------------------------------------------

def tiles_of(rows, nb):
    """(sprites across, sprites down) for a figure: its mask is a pixel larger than the graphic on every side."""
    return (nb * 8 + 2 + 15) // 16, (rows + 2 + 15) // 16


def figure(mem, g, m, rows, nb):
    """{(column, row): 1 graphic | 2 cleared by the mask} in the mask's box: (nb + 1) * 8 across, rows + 2 down; the
    graphic sits one pixel right of and one row below the box's corner."""
    w = (nb + 1) * 8
    out = {}
    for r in range(rows + 2):
        mk = int.from_bytes(bytes(mem[m + r * (nb + 1):m + (r + 1) * (nb + 1)]), 'big')
        gr = int.from_bytes(bytes(mem[g + (r - 1) * nb:g + r * nb]), 'big') << 7 if 1 <= r <= rows else 0
        for c in range(w):
            bit = 1 << (w - 1 - c)
            if gr & bit:
                out[(c, r)] = 1
            elif not mk & bit:
                out[(c, r)] = 2
    return out


def fig_key(mem, g, rows, nb):
    """A graphic by its bytes (the painted map's key)."""
    return hashlib.md5(bytes(mem[g:g + rows * nb]) + bytes((rows, nb))).hexdigest()[:16]


def placed(shape, x, y):
    """A figure's pixels on the display: {(x, y): v}, inside the play area."""
    out = {}
    for (c, r), v in shape.items():
        px, py = x - 1 + c, BOTTOM - 1 - y + r + (y >= 169)     # (from y = 169 the routine draws a line lower)
        if 0 <= px < 256 and 0 <= py <= BOTTOM:
            out[(px, py)] = v
    return out


def fig_times(mem):
    """The routine's own time, T, for every size and shift: {(rows, nb, shift): T}. It runs the same instructions for
    a size and a shift wherever the figure is, but for a few T at a cell boundary."""
    out = {}
    m = bytearray(mem)
    desc, g = 0x7000, 0x7010
    m[desc:desc + 4] = bytes((g & 255, g >> 8, (g + 0x200) & 255, (g + 0x200) >> 8))
    for rows, nb in SIZES:
        for sh in range(8):
            regs = [0] * 30
            regs[SP_] = 0x81F0
            regs[PC_] = FIG
            regs[2], regs[3], regs[4], regs[5], regs[6], regs[7] = 100, 64 + sh, rows, nb, desc >> 8, desc & 255
            m2 = bytearray(m)
            m2[0x81F0:0x81F2] = b'\x00\x00'
            Ro, _ = run_orig(None, m2, regs, 0, 0x81F2)
            out[(rows, nb, sh)] = Ro[T_]
    return out


def colour_tables(cmap, mem, syms):
    """-> (index bytes for PIDX, {page: bytes}, palette (256 9-bit colours), want {graphic address: (line, {(c, r): nibble})}).
    A painted figure is known by its graphic's bytes; its tiles are stored as the sprites take them."""
    pal = [0] * 256
    pal[1], pal[2] = WHITE, BLACK
    for li, line in enumerate(cmap['lines']):
        for k, c in enumerate(line):
            pal[(li + 1) * 16 + 1 + k] = c
    by_key = {f['key']: f for f in cmap['figures']}
    index = bytearray()
    pages = {}
    want = {}
    page, at = CPAGE, 0
    for g in sorted(cmap.get('where', {}), key=lambda a: int(a)):
        for rows, nb in cmap['where'][g]:
            ga = int(g)
            f = by_key.get(fig_key(mem, ga, rows, nb))
            if f is None or len(index) >= 255 * 8:
                continue
            tx, ty = tiles_of(rows, nb)
            w = (nb + 1) * 8
            px = {}
            rowsdata = f['pixels']
            for r in range(rows + 2):
                for c in range(w):
                    v = int(rowsdata[r][c], 16)
                    if v:
                        px[(c, r)] = v
            blob = bytearray()
            for tr in range(ty):
                for tc in range(tx):
                    for r in range(16):
                        for c in range(0, 16, 2):
                            blob.append(px.get((tc * 16 + c, tr * 16 + r), 0) << 4 | px.get((tc * 16 + c + 1, tr * 16 + r), 0))
            if at + len(blob) > 8192:
                page, at = page + 1, 0
            pages.setdefault(page, bytearray(8192))[at:at + len(blob)] = blob
            index += bytes((ga & 255, ga >> 8, rows, nb, page)) + (0x4000 + at).to_bytes(2, 'little') + bytes((f['line'] + 1,))
            want[(ga, rows, nb)] = (f['line'] + 1, px)
            at += len(blob)
    return bytes(index), {p: bytes(b) for p, b in pages.items()}, pal, want


class Patch:
    name = 'Olli and Lissa: every moving figure as sprites on its own pixels (alt ROM hooks, the game unchanged)'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000
    tail_addr = TAIL_ADDR

    def __init__(self, z80=None, mem=None, colours=None, rom=None, times=None):
        self.prof = load_profile()
        h = self.prof['hooks']
        self.syms = sy = {k: int(v, 16) for k, v in h['syms'].items()}
        self.z80, self.colours = z80, colours
        if mem is None and z80 is not None:
            from skoolkit.snapshot import Snapshot
            mem = play_view(Snapshot.get(str(z80)))
        if mem is None or mem[SIGNATURE[0]:SIGNATURE[0] + len(SIGNATURE[1])] != SIGNATURE[1]:
            raise ValueError('not the supported Olli and Lissa: the figure routine is not where it is expected')
        self.mem = bytes(mem)
        self.rom_code = bytes.fromhex(h['rom']) if rom is None else bytes(rom)
        self.regblock = ROM_ORG + len(self.rom_code)
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        page = bytearray(rom48()[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        work = bytearray(8192)
        for i in range(256):            # (graphic nibble << 4 | mask nibble) -> two pattern bytes
            gn, mn = i >> 4, i & 15
            px = [1 if gn >> (3 - k) & 1 else 0 if mn >> (3 - k) & 1 else 2 for k in range(4)]
            work[sy['TLO'] + i] = px[0] << 4 | px[1]
            work[sy['THI'] + i] = px[2] << 4 | px[3]
        self.times = dict(fig_times(mem) if times is None else times)
        for k, (rows, nb) in enumerate(SIZES):
            for sh in range(8):
                o = sy['TT'] + (k * 8 + sh) * 2
                work[o:o + 2] = hooklib.lines16(self.times[(rows, nb, sh)], T_LINE).to_bytes(2, 'little')
        self.planes = {}
        self.want = {}
        pal = [0] * 256
        pal[1], pal[2] = WHITE, BLACK
        if colours:
            index, self.planes, pal, self.want = colour_tables(colours, mem, sy)
            work[sy['PIDX']:sy['PIDX'] + len(index)] = index
            work[sy['V_NP']] = len(index) // 8
        self.work = bytes(work)
        self.palette = pal
        st = bytearray(bytes.fromhex(h['setup']))
        o = sy['pal9'] - 0xD000
        for i, c in enumerate(pal):
            st[o + 2 * i], st[o + 2 * i + 1] = c >> 1, c & 1
        o = sy['pbuf'] - 0xD000
        st[o:o + 256] = mem[0x5B00:0x5C00]
        self.stub_extra = bytes(st)
        self.sites = [(a, b'\xcd\xda\x89', b'\xCD' + sy[s].to_bytes(2, 'little')) for a, s in SITES.items()]
        self.sites += [(a, b'\xcd\xeb\x82', b'\xCD' + sy[s].to_bytes(2, 'little')) for a, s in WIPES.items()]
        for t in (FIG, WIPE):           # every CALL or JP of the two routines is one of the sites
            lo, hi = t & 255, t >> 8
            for a in range(0x5B00, 0xFFFD):
                if mem[a] in (0xCD, 0xC3) and mem[a + 1] == lo and mem[a + 2] == hi and a not in SITES and a not in WIPES:
                    raise ValueError('a CALL of 0x%04X the build does not know, at 0x%04X' % (t, a))
        self.extra_banks = {12: self.page + bytes(8192), 13: self.work + bytes(8192)}
        for pg, data in self.planes.items():
            cur = self.extra_banks.get(pg // 2, bytes(16384))
            o = (pg & 1) * 8192
            self.extra_banks[pg // 2] = cur[:o] + data + cur[o + 8192:]

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('the Olli and Lissa patch expects the 128K snapshot')
        for a, old, new in self.sites:
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else snap.port7ffd & 7
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
    """What stays between hooks: the state page, the sprites' patterns and attributes, where the ports stand."""
    def __init__(self, patch):
        self.work = bytearray(patch.work)
        self.pattern = bytearray(b'\xEE' * 16384)       # (as anything left them)
        self.attrs = [[0] * 5 for _ in range(128)]      # the setup switches every sprite off
        self.ports = (0, 0, 0)
        self.t = collections.Counter()
        self.line = 0.0
        self.t_in = 0.0


class View:
    """64K as the hooks see it: the alt ROM image, the state page at slot 0, a painted page at slot 2, the game."""
    def __init__(self, mem, rom, st, planes):
        self.mem, self.rom, self.st, self.planes = mem, rom, st, planes
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        if a < 0x2000:
            return self.st.work[a] if self.model.nr.get(0x50, 255) == WORK else self.rom[a]
        if a < 0x4000:
            return self.rom[a]
        if a < 0x6000:
            p = self.model.nr.get(0x52, 10)
            if p != 10:
                return self.planes[p][a - 0x4000]
        return self.mem[a]

    def __setitem__(self, a, v):
        if a < 0x2000:
            if self.model.nr.get(0x50, 255) == WORK:
                self.st.work[a] = v
            return
        if a < 0x4000:
            return
        if a < 0x6000 and self.model.nr.get(0x52, 10) != 10:
            self.model.c['write to a painted page!'] += 1
            return
        self.mem[a] = v


class Model(hooklib.NextModel):
    """The shared model with the sprites carried from hook to hook, and a 4-bit pattern known by its own half."""
    def __init__(self, sim, st):
        super().__init__(sim, 0, t_line=T_LINE, lines=LINES)
        self.real = st.line
        self.pattern, self.attrs = st.pattern, st.attrs
        self.pidx, self.aidx, self.abyte = st.ports
        self.st = st

    def halves(self):
        return {(a[3] & 63) * 2 + (a[4] >> 6 & 1) for a in self.attrs if a[3] & 0x80}

    def write_port(self, regs, port, value, *x):
        if port & 255 == 0x5B and port != 0x243B and port != 0x253B and port != 0x303B:
            if self.pidx >> 7 in self.halves():
                self.c['upload into a shown pattern!'] += 1
            self.pattern[self.pidx] = value
            self.pidx = (self.pidx + 1) & 0x3FFF
            self.c['pattern bytes'] += 1
            return
        super().write_port(regs, port, value, *x)

    def keep(self):
        self.st.ports = (self.pidx, self.aidx, self.abyte)


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def run_hook(patch, st, rom, mem, regs, site, stop, sp_stop, limit=6000000):
    """Run the patched code from `site` on a copy of the game's memory until PC = stop with SP = sp_stop and the ROM back
    at slot 0. -> (registers, copy, model)."""
    from . import simpool
    m2 = bytearray(mem)
    for a, old, new in patch.sites:
        m2[a:a + len(new)] = new
    v = View(m2, rom, st, patch.planes)
    s = simpool.machine(_rw(), v, list(regs), 'olli-hook')
    model = Model(s, st)
    v.model = model
    R = s.registers
    R[PC_] = site
    n = 0
    while True:
        s.opcodes[v[R[PC_]]]()
        n += 1
        if R[PC_] == stop and R[SP_] == sp_stop and model.nr.get(0x50, 255) == 255:
            break
        if n > limit:
            raise AssertionError('hook at %04X did not end (PC %04X)' % (site, R[PC_]))
    st.t[site] += model.now() - st.line
    st.t_in = st.line
    st.line = model.now()
    model.keep()
    model.n = n
    for a, old, new in patch.sites:
        m2[a:a + len(old)] = old
    return list(R), m2, model


def run_orig(rom, mem, regs, stop, sp=None, limit=6000000):
    """The original from regs' PC until PC = stop (and SP = sp); with stop = 0, until SP = sp."""
    from . import simpool
    m2 = bytearray(mem) if rom is None else bytearray(rom[:0x4000]) + bytearray(mem[0x4000:])
    s = simpool.machine(_rw(), m2, list(regs), 'olli-orig')
    R = s.registers
    n = 0
    while True:
        s.opcodes[m2[R[PC_]]]()
        n += 1
        if (stop == 0 or R[PC_] == stop) and (sp is None or R[SP_] == sp):
            break
        if n > limit:
            raise AssertionError('original from %04X did not reach %04X' % (regs[PC_], stop))
    return list(R), m2


def entries(st, sy):
    """The figures the hooks hold: {key: (index, graphic, mask, rows, bytes, line, sprites, [patterns])}."""
    out = {}
    for i in range(NENT):
        e = st.work[sy['ENTS'] + i * E_SIZE:sy['ENTS'] + (i + 1) * E_SIZE]
        key = e[0] | e[1] << 8
        if key:
            out[key] = (i, e[2] | e[3] << 8, e[4] | e[5] << 8, e[6], e[7], e[8], e[9], list(e[10:10 + e[9]]))
    return out


def sprite_pixels(st, first, n=PER, c=None):
    """What sprites first..first+n-1 show on the display, inside their window: {(x, y): palette line * 16 + nibble}."""
    out = {}
    for i in range(first, first + n):
        a = st.attrs[i]
        if not a[3] & 0x80:
            continue
        if not a[3] & 0x40 or not a[4] & 0x80:
            if c is not None:
                c['a shown sprite is not a 4-bit one!'] += 1
            continue
        X, Y = a[0] | (a[2] & 1) << 8, a[1] | (a[4] & 1) << 8
        p = (a[3] & 63) * 2 + (a[4] >> 6 & 1)
        line = a[2] >> 4
        for r in range(16):
            y = Y - 32 + r
            if not 0 <= y <= BOTTOM:
                continue
            for k in range(16):
                b = st.pattern[p * 128 + r * 8 + k // 2]
                v = b >> 4 if k % 2 == 0 else b & 15
                x = X - 32 + k
                if v and 0 <= x < 256:
                    out[(x, y)] = line * 16 + v
    return out


def screen_bit(mem, x, y):
    return mem[0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x >> 3] >> (7 - (x & 7)) & 1


def flat(m):
    return m.memory[0] + m.memory[1] + m.memory[2] + m.memory[3] if hasattr(m, 'memory') else bytes(m)


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original (PLAYBOOK 6). At each CALL of the figure routine and of the wipe the patched code runs on a
    copy of the state, the Next side carried from site to site, and must leave every register (R too) and all the
    game's memory as the original does. After a figure's hook its sprites must show the figure as a model of the
    routine has it (or as the painted map has it), on the pixels the original's routine has just drawn; after a wipe
    no sprite is on. -> (Counter, examples, states)."""
    from . import rzx as RZ
    from .nextboot import alt_image
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    kept = collections.Counter()
    rom = bytes(alt_image(patch))
    st = State(patch)
    sy = patch.syms
    box = {'orig_t': 0, 'sizes': collections.Counter()}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(ex[key]) < 5:
            ex[key].append(detail)

    def same(name, Ro, mo, Rp, mp, below=0):
        """below: bytes under the stack pointer the hook may write (the wipe's two pushes; the wipe itself writes
        over them at once)."""
        bad = [(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]]
        if bad:
            fail('registers after %s' % name, bad)
        sp = Ro[SP_]
        if mp[0x4000:sp - below] != mo[0x4000:sp - below] or mp[sp:] != mo[sp:]:
            fail('%s writes game memory' % name, [hex(a) for a in range(0x4000, 65536) if mp[a] != mo[a] and not sp - below <= a < sp][:8])

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
        regs = list(R)
        mem = bytearray(flat(m))
        sp = regs[SP_]
        if regs[IFF_] and pc not in WIPES:
            fail('interrupts on at a figure', hex(pc))
        if collect and kept[pc] < collect:
            kept[pc] += 1
            states.append((pc, bytes(mem), tuple(regs), bytes(st.work)))
        if pc in WIPES:
            c['wipes'] += 1
            Ro, mo = run_orig(rom, mem, regs, WIPE, sp - 2)
            Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, WIPE, sp - 2)
            same('the wipe', Ro, mo, Rp, mp, below=WIPE_STACK)
            c['wipes with interrupts on'] += bool(regs[IFF_])
            if any(a[3] & 0x80 for a in st.attrs):
                fail('a sprite is on after a wipe', [i for i, a in enumerate(st.attrs) if a[3] & 0x80][:6])
            if entries(st, sy):
                fail('a figure is still held after a wipe', list(entries(st, sy))[:4])
            box['seen'] = {}
            return
        c['figures'] += 1
        Ro, mo = run_orig(rom, mem, regs, pc + 3, sp)
        Rp, mp, model = run_hook(patch, st, rom, mem, regs, pc, pc + 3, sp)
        same('the figure at %04X' % pc, Ro, mo, Rp, mp)
        t = Ro[T_] - regs[T_]
        box['orig_t'] += t
        d = (st.line - st.t_in) - t
        c['most T a figure takes over the original'] = max(c['most T a figure takes over the original'], int(d))
        c['most T a figure takes under the original'] = max(c['most T a figure takes under the original'], int(-d))
        c['figures more than 700 T off the original'] += abs(d) > 700
        if model.nr[7] & 3:
            fail('a figure leaves its speed', model.nr[7])
        if model.nr.get(0x52, 10) != 10:
            fail('a figure leaves a page mapped', model.nr.get(0x52))
        bad = {k: v for k, v in model.c.items() if k.endswith('!')}
        if bad:
            fail('a write where none may be', bad)
        # the figure's sprites
        hl = regs[6] << 8 | regs[7]
        y, x, rows, nb = regs[2], regs[3], regs[4], regs[5]
        g, mk = mem[hl] | mem[hl + 1] << 8, mem[hl + 2] | mem[hl + 3] << 8
        box['sizes'][(rows, nb)] += 1
        key = KIND[pc] or (regs[10] << 8 | regs[11])
        shape = figure(mem, g, mk, rows, nb)
        want = placed(shape, x, y)
        # the model against the game's own drawing: set where the graphic is, clear where only the mask is
        off = sum(1 for (px, py), v in want.items() if screen_bit(mo, px, py) != (v == 1))
        if off:
            c['figures the routine draws unlike the model'] += 1
            if len(ex['figures the routine draws unlike the model']) < 5:
                ex['figures the routine draws unlike the model'].append((c['figures'], hex(pc), x, y, rows, nb, off))
        ents = entries(st, sy)
        if key not in ents or not ents[key][6]:
            c['figures left as the game draws them'] += 1
            if key in ents and sprite_pixels(st, ents[key][0] * PER, c=c):
                fail('a figure left out still shows sprites', c['figures'])
            return
        i = ents[key][0]
        got = sprite_pixels(st, i * PER, c=c)
        painted = patch.want.get((g, rows, nb))
        if painted:
            line, px = painted
            want = {k: line * 16 + v for k, v in placed(px, x, y).items()}
            c['painted figures'] += 1
            c['painted sprite pixels'] += len(got)
        c['sprite pixels'] += len(got)
        if got != want:
            dk = [k for k in set(got) | set(want) if got.get(k) != want.get(k)]
            fail('a figure\'s sprites are not the figure', (c['figures'], hex(pc), x, y, rows, nb, len(dk), sorted(dk)[:3]))
        c['most figures at a time'] = max(c['most figures at a time'], len(ents))
        c['most sprites shown'] = max(c['most sprites shown'], sum(1 for a in st.attrs if a[3] & 0x80))
        seen = box.setdefault('seen', {})
        seen[key] = (c['figures'], g, mk, rows, nb, x, y)
        # a figure the game has not drawn again for a while (it draws each every 3 to 5 calls): still on the screen? One
        # another figure's routine has rubbed out is drawn again within those calls; one that stays gone has a stale sprite.
        for k2, (t2, g2, m2_, r2, n2, x2, y2) in seen.items():
            if k2 == key or k2 not in ents or not ents[k2][6] or c['figures'] - t2 <= STALE:
                continue
            ink = [p for p, v in placed(figure(mem, g2, m2_, r2, n2), x2, y2).items() if v == 1]
            if ink and sum(1 for (px, py) in ink if not screen_bit(mo, px, py)) > len(ink) // 2:
                c['calls a sprite shows a figure the screen has lost'] += 1
                if len(ex['a sprite shows a figure the screen has lost']) < 5:
                    ex['a sprite shows a figure the screen has lost'].append((c['figures'], hex(k2), c['figures'] - t2, x2, y2))

    fc, err = RZ.trace(rzx_path, set(SITES) | set(WIPES), on, stop=stop)
    c['frames'] = fc
    if err:
        c['replay stopped!'] += 1
        ex['replay'].append(err)
    c['T original figures'] = box['orig_t']
    c['T hooks'] = int(sum(st.t[k] for k in SITES))
    c['left for want of an entry or patterns'] = st.work[sy['V_FULL']]
    c['left for their size'] = st.work[sy['V_ODD']]
    if c['figures left as the game draws them']:
        fail('figures left as the game draws them', (c['figures left as the game draws them'], c['left for want of an entry or patterns'], c['left for their size']))
    if c['figures the routine draws unlike the model']:
        fail('the routine draws figures unlike the model', c['figures the routine draws unlike the model'])
    if c['calls a sprite shows a figure the screen has lost']:
        fail('a sprite shows a figure the screen has lost', c['calls a sprite shows a figure the screen has lost'])
    if c['figures']:
        full = stop is None or c['frames'] < stop           # the 0.5% endpoint is the whole recording's claim (Codex T4)
        if not full:
            c['prefix: hooks less the original, T'] = int(c['T hooks'] - box['orig_t'])
        if c['figures more than 700 T off the original'] > 0.03 * c['figures'] + 5 or (full and abs(c['T hooks'] - box['orig_t']) > 0.005 * fc * LINES * T_LINE):
            fail('the figures do not take the original\'s time', (c['figures more than 700 T off the original'], c['figures'], c['T hooks'], box['orig_t']))
    ex['sizes'] = sorted(box['sizes'].items())
    return c, dict(ex), states


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched
    snapshot, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites). -> problems."""
    from . import nextboot
    from . import z80tonex as zt
    s = zt.Z80Snapshot(str(z80))
    if patch is not None:
        patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, getattr(patch, 'slot1', None), patch is not None)[0])
    tail = zt.choose_tail_addr(s, size, TAIL_ADDR, False)[0]
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 65536):
            if tail <= a < tail + size or (nexload and patch is None and 0x5B00 <= a < 0x5C00):
                continue                # (a patched build's setup puts the printer buffer back: compared)
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def unit_tests(patch, states, neg=None):
    """The paths the recordings do not reach, from captured states (site, memory, registers, state page)."""
    from .nextboot import alt_image
    c = collections.Counter()
    rom = bytes(alt_image(patch))
    sy = patch.syms
    figs = [s for s in states if s[0] in SITES]

    def ok(name, cond):
        c[name] += 1
        if not cond:
            c[name + ' FAILED!'] += 1

    def both(st, pc, mem, regs):
        sp = regs[SP_]
        Ro, mo = run_orig(rom, mem, list(regs), pc + 3, sp)
        Rp, mp, model = run_hook(patch, st, rom, mem, list(regs), pc, pc + 3, sp)
        return ([(i, Ro[i], Rp[i]) for i in CMP if Ro[i] != Rp[i]] or mp[0x4000:] != mo[0x4000:]), model, mo

    def shown(st, pc, mem, regs):
        hl = regs[6] << 8 | regs[7]
        g, mk = mem[hl] | mem[hl + 1] << 8, mem[hl + 2] | mem[hl + 3] << 8
        key = KIND[pc] or (regs[10] << 8 | regs[11])
        e = entries(st, sy).get(key)
        want = placed(figure(mem, g, mk, regs[4], regs[5]), regs[3], regs[2])
        p = patch.want.get((g, regs[4], regs[5]))
        if p:
            want = {k: p[0] * 16 + v for k, v in placed(p[1], regs[3], regs[2]).items()}
        return e, (sprite_pixels(st, e[0] * PER) if e else {}), want

    for pc, mem, regs, work in figs[:6]:
        regs = list(regs)
        # the same picture twice: no pattern is sent again, the sprites follow the figure
        st = State(patch)
        bad, model, _ = both(st, pc, mem, regs)
        r2 = list(regs)
        r2[3] = (r2[3] + 3) & 255
        n0 = 0
        bad2, model2, _ = both(st, pc, mem, r2)
        e, got, want = shown(st, pc, mem, r2)
        ok('the same picture again: no pattern sent, the sprites move', not bad and not bad2 and model2.c['pattern bytes'] == n0 and got == want)
        # every entry taken by other figures: left as the game draws it
        st = State(patch)
        for i in range(NENT):
            st.work[sy['ENTS'] + i * E_SIZE] = 0xF0 + i
            st.work[sy['ENTS'] + i * E_SIZE + 1] = 0xFF
        bad, model, _ = both(st, pc, mem, regs)
        ok('no free entry: the figure is left to the game', not bad and st.work[sy['V_FULL']] == 1 and not any(a[3] & 0x80 for a in st.attrs)
           and not model.c['pattern bytes'])
        # no free pattern: the same, and its old sprites off
        st = State(patch)
        both(st, pc, mem, regs)
        for i in range(128):
            st.work[sy['PMAP'] + i] = 1
        hl = regs[6] << 8 | regs[7]
        m3 = bytearray(mem)
        m3[hl] ^= 1                     # (another picture: the entry's own is not kept)
        bad, model, _ = both(st, pc, bytes(m3), regs)
        ok('no free pattern: the figure is left to the game, its sprites off', not bad and st.work[sy['V_FULL']] == 1
           and not any(a[3] & 0x80 for a in st.attrs))
        # a size the table does not hold
        st = State(patch)
        r3 = list(regs)
        r3[4] = 12
        bad, model, _ = both(st, pc, mem, r3)
        ok('a size the table does not hold: left to the game', not bad and st.work[sy['V_ODD']] == 1 and not any(a[3] & 0x80 for a in st.attrs))
        # at the right edge: the ninth bit of x
        st = State(patch)
        r4 = list(regs)
        r4[3] = 236
        bad, model, _ = both(st, pc, mem, r4)
        e, got, want = shown(st, pc, mem, r4)
        ok('at the right edge', not bad and got == want and bool(want))
        # near the top of the screen the routine draws a line lower: the sprites with it, on the routine's own pixels
        for yy in (168, 169, 172):
            st = State(patch)
            r6 = list(regs)
            r6[2] = yy
            bad, model, mo = both(st, pc, mem, r6)
            e, got, want = shown(st, pc, mem, r6)
            g6, m6 = mem[hl] | mem[hl + 1] << 8, mem[hl + 2] | mem[hl + 3] << 8
            shape = placed(figure(mem, g6, m6, r6[4], r6[5]), r6[3], yy)
            ok('at the top of the screen (y = %d)' % yy, not bad and got == want and bool(want)
               and all(screen_bit(mo, px, py) == (v == 1) for (px, py), v in shape.items()))
        # a second picture for the same figure goes into other patterns and the first ones are free again
        st = State(patch)
        both(st, pc, mem, regs)
        first = set(entries(st, sy)[KIND[pc] or (regs[10] << 8 | regs[11])][7])
        r5 = list(regs)                 # (the next picture of the same figure: the pair of pointers after this one)
        r5[6], r5[7] = (hl + 4) >> 8, (hl + 4) & 255
        bad, model, _ = both(st, pc, mem, r5)
        e, got, want = shown(st, pc, mem, r5)
        used = {i for i in range(128) if st.work[sy['PMAP'] + i]}
        ok('a new picture: other patterns, the old ones free', not bad and got == want and not first & set(e[7]) and used == set(e[7])
           and not model.c['upload into a shown pattern!'])
    # a scene played over the room (Olli caught: an object's record below the room's): the figure under it goes back to
    # the game's drawing, one clear of it keeps its sprites
    for pc, mem, regs, work in [s for s in figs if not KIND[s[0]]][:3]:
        regs = list(regs)
        x0 = regs[3]
        near, far = (x0 + 6) & 255, (x0 + 120) & 255
        for name, xs, gone in (('a scene over a figure: its sprites off, its patterns free', near, True),
                               ('a scene clear of a figure: its sprites stay', far, False)):
            st = State(patch)
            both(st, pc, mem, regs)
            k1 = regs[10] << 8 | regs[11]
            r7 = list(regs)
            r7[3], r7[10], r7[11] = xs, EVENT >> 8, EVENT & 255
            bad, model, _ = both(st, pc, mem, r7)
            e1, e2 = entries(st, sy)[k1], entries(st, sy).get(EVENT)
            on1 = any(st.attrs[i][3] & 0x80 for i in range(e1[0] * PER, e1[0] * PER + PER))
            used = {i for i in range(128) if st.work[sy['PMAP'] + i]}
            ok(name, not bad and e2 and e2[6] and on1 != gone and bool(e1[6]) != gone
               and used == set(e2[7]) | (set() if gone else set(e1[7])))
    for pc, mem, regs, work in [s for s in states if s[0] in WIPES][:2]:
        st = State(patch)
        if figs:
            both(st, figs[0][0], figs[0][1], list(figs[0][2]))
        sp = regs[SP_]
        Ro, mo = run_orig(rom, mem, list(regs), WIPE, sp - 2)
        Rp, mp, model = run_hook(patch, st, rom, mem, list(regs), pc, WIPE, sp - 2)
        for iff in (0, 1):              # interrupts are on at the title's wipe: off inside the hook, on again after it
            st2 = State(patch)
            rg = list(regs)
            rg[IFF_] = rg[IFF_ + 1 - 1] = iff
            Ro2, mo2 = run_orig(rom, mem, rg, WIPE, sp - 2)
            Rp2, mp2, model2 = run_hook(patch, st2, rom, mem, rg, pc, WIPE, sp - 2)
            ok('a wipe with interrupts %s' % ('on' if iff else 'off'), not [i for i in CMP if Ro2[i] != Rp2[i]] and Rp2[IFF_] == iff)
        ok('a wipe: every sprite off, nothing held', not [i for i in CMP if Ro[i] != Rp[i]] and mp[0x4000:sp - 2 - WIPE_STACK] == mo[0x4000:sp - 2 - WIPE_STACK] and mp[sp - 2:] == mo[sp - 2:]
           and not any(a[3] & 0x80 for a in st.attrs) and not entries(st, sy) and not any(st.work[sy['PMAP']:sy['PMAP'] + 128]))
    return c


def _code_patch(patch, sym, new):
    rc = bytearray(patch.rom_code)
    a = patch.syms[sym] - ROM_ORG
    rc[a:a + len(new)] = new
    return Patch(z80=patch.z80, mem=patch.mem, colours=patch.colours, rom=bytes(rc), times=patch.times)


def negative_patches(patch):
    """Broken builds a verify run on a recording must catch: [(name, patch)]."""
    r = patch.rom_code[patch.syms['fig_end.n_rout'] - ROM_ORG + 1]
    return [('R one more after a figure', _code_patch(patch, 'fig_end.n_rout', bytes((0x3E, (r + 1) & 255)))),
            ('the sprites not at the figure\'s line', _code_patch(patch, 'attrs.n_y', b'\x00')),
            ('the ninth bit of x is not set', _code_patch(patch, 'attrs.n_x8', b'\x00')),
            ('a figure\'s sprites are not switched on', _code_patch(patch, 'attrs.n_vis', b'\xF6\x40')),
            ('a wipe leaves the sprites on', _code_patch(patch, 'alloff.n_off', b'\x00\x00\x00\x00')),
            ('a figure\'s old patterns are not freed', _code_patch(patch, 'free.n_fr', b'\x00')),
            ('a pattern byte is not sent', _code_patch(patch, 'one.n_o', b'\x00\x00')),
            ('the figure\'s time is not waited out', _code_patch(patch, 'fig_end.n_t', b'\x21\x00\x00')),
            ('a scene leaves the figure under it on', _code_patch(patch, 'sprite.n_ev', b'\x00\x00\x00'))]


NEG_UNIT = {'a scene leaves the figure under it on'}       # (reached far into a recording: caught by its unit case)


NEG_STOP = {}


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    os.makedirs(out, exist_ok=True)
    say('Game      : %s' % name)
    cmap = load_colours(z80)
    try:
        patch = Patch(z80=z80)
        enh = Patch(z80=z80, colours=cmap, times=patch.times) if cmap else None
    except ValueError as e:
        say('Engine    : olli_and_lissa: %s' % e)
        say('Result    : FAILED')
        return False
    say('Engine    : olli_and_lissa (nothing of the game changes; each figure its routine is about to draw -> sprites on the same '
        'pixels: 1 where the graphic is set, 2 where the mask clears)')
    ok = True
    plain = os.path.join(out, name + '.nex')
    zt.convert(str(z80), plain, TAIL_ADDR, quiet=True)
    bad = boot_check(plain, z80, None)
    ok = ok and not bad
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    builds = [('Sprites', '_sprites', patch, lambda: Patch(z80=z80, times=patch.times))]
    if enh:
        builds.append(('Enhanced', '_enhanced', enh, lambda: Patch(z80=z80, colours=cmap, times=patch.times)))
    for label, suffix, pt, mk in builds:
        nex = os.path.join(out, name + suffix + '.nex')
        zt.convert(str(z80), nex, patch=pt, quiet=True)
        bad = boot_check(nex, z80, mk())
        ok = ok and not bad
        say('%-10s: %s  %s  boot %s%s' % (label, os.path.basename(nex), md5(nex), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200],
                                         '' if pt is patch else '  (%d painted figures, %d palette lines, %d pages)' % (
                                             len(pt.want), len(cmap['lines']), len(pt.planes))))
    states = []
    quick = getattr(a, 'quick', None)
    for r in list(getattr(a, 'rzx', None) or []):
        for label, pt in [('Verify', patch)] + ([('Painted', enh)] if enh else []):
            cc, ex, st = verify(pt, r, stop=quick, collect=3 if pt is patch else 0)
            states += st
            fails = {k: v for k, v in cc.items() if k.endswith('!')}
            ok = ok and not fails
            say('%-10s: %s  %d frames, %d figures (%d painted), %d wipes, %d sprite pixels (%d painted), most figures at a time %d, most sprites '
                '%d, %d figures the routine draws unlike the model, %d calls a sprite shows a figure the screen has lost -> %s' % (
                    label, os.path.basename(r), cc['frames'], cc['figures'], cc['painted figures'], cc['wipes'], cc['sprite pixels'],
                    cc['painted sprite pixels'], cc['most figures at a time'], cc['most sprites shown'],
                    cc['figures the routine draws unlike the model'], cc['calls a sprite shows a figure the screen has lost'],
                    'IDENTICAL' if not fails else 'FAILED %s' % fails))
            say('Pace      : %s  the figures %d T in the original, the hooks %d T (%+.3f%% of the recording\'s time); a figure at most '
                '%d T over, %d T under; %d of %d more than 700 T (3 lines) off' % (
                    os.path.basename(r), cc['T original figures'], cc['T hooks'],
                    100.0 * (cc['T hooks'] - cc['T original figures']) / max(1, cc['frames'] * LINES * T_LINE),
                    cc['most T a figure takes over the original'], cc['most T a figure takes under the original'],
                    cc['figures more than 700 T off the original'], cc['figures']))
            for k, v in ex.items():
                if k != 'sizes':
                    say('            %s: %s' % (k, str(v)[:300]))
    if states:
        for label, pt in [('Verify', patch)] + ([('Painted', enh)] if enh else []):
            u = unit_tests(pt, states)
            uf = {k: v for k, v in u.items() if k.endswith('!')}
            ok = ok and not uf
            say('Unit      : %s: %s -> %s' % (label, ', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if not k.endswith('!')),
                                             'PASS' if not uf else 'FAIL %s' % uf))
    if getattr(a, 'rzx', None):
        r0 = list(a.rzx)[0]
        negs = negative_patches(patch)
        missed = []
        for nm, q in negs:
            if nm in NEG_UNIT:
                cc = unit_tests(q, states)
            else:
                cc, _, _ = verify(q, r0, stop=NEG_STOP.get(nm, quick or 2500))
            if not any(k.endswith('!') for k in cc):
                missed.append(nm)
        ok = ok and not missed
        say('Negative  : %d broken builds (%s), %d detected%s' % (len(negs), os.path.basename(r0), len(negs) - len(missed),
                                                                 '' if not missed else '; NOT detected: ' + ', '.join(missed)))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
