"""Ruff and Reddy Enhanced: the play window and panel on a full Layer 2, from the Spec256 set, the player's own file, never in this repo. The
default (ruff_and_reddy.Patch) is not touched by this module. See asm/ruff_and_reddy_enh_hooks.asm."""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import ruff_and_reddy as A, hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/ruff_and_reddy_enh.json'
CMP = tuple(hooklib.CMP_R)
BANK, MEM = 16384, 131072 * 9
SKIP, CLEAR = 0xFE, 0xFF
L2_A, L2_B = 16, 19
CLEAN_PAGE, TILE_PAGE, FIRST_ART_PAGE = 44, 50, 58
TILES = 0xDDA7
BIG_TABLE, SMALL_TABLE, N_BIG, N_SMALL = 0xA034, 0xA05E, 21, 45
X_LEFT, ROW_FIRST = 24, 32
V_Q, V_QBUF, V_SPEED, V_RECT = 0x3E42, 0x3E80, 0x3E30, 0x3E3A
BIG, SMALL = 0xA66C, 0xA867
CALLS = {0xA468: (BIG, 'h_big', 'big'), 0xA484: (BIG, 'h_big', 'big'), 0xA4A0: (BIG, 'h_big', 'big'),
         0xA4BC: (SMALL, 'h_small', 'small'), 0xA4D8: (SMALL, 'h_small', 'small'), 0xA4F4: (SMALL, 'h_small', 'small'),
         0x8B45: (0xAC70, 'h_over', 'hide'), 0x8B79: (0xAC70, 'h_over', 'hide'), 0xFD75: (0xAC70, 'h_over', 'hide')}
ROOM_SITE, MSG_SITE, TITLE_SITE = 0x818B, 0xD42B, 0xD332
COPY_IN, COPY_OUT, COPY_RET, RENDER, WAIT, HALT = 0xA506, 0xA5E6, 0xA5E9, 0x81B2, 0xA4F7, 0xA4F8
# Panel cells (rows from 20) the game draws over in play, left to the ULA: lives, the item boxes, score, time.
HOLES = [(1, 7)] + [(r, c) for r in (1, 2) for c in range(9, 17)] + [(1, c) for c in range(20, 26)] + [(3, 13), (3, 15), (3, 16)]


class Set256:
    def __init__(self, path):
        self.d = open(path, 'rb').read()

    def word(self, addr):
        return (5 if addr < 0x8000 else 2 if addr < 0xC000 else 0) * BANK + (addr & 0x3FFF)

    def master(self, addr):
        return self.d[self.word(addr) * 9 + 8]

    def pixels(self, addr):
        w = self.word(addr) * 9
        p = self.d[w:w + 8]
        out = []
        for k in range(8):
            bit = 0x80 >> k
            v = 0
            for i in range(8):
                if p[i] & bit:
                    v |= 1 << i
            out.append(v)
        return out


def palette(rgb):
    out = bytearray()
    moved = []
    for i, c in enumerate(rgb):
        r, g, b = c >> 16 & 255, c >> 8 & 255, c & 255
        hi = (r >> 5) << 5 | (g >> 5) << 2 | b >> 6
        lo = (b >> 5) & 1
        if i == CLEAR:
            hi, lo = 0xE3, 0
        elif hi == 0xE3:
            hi = 0xE2
            moved.append(i)
        out += bytes((hi, lo))
    return bytes(out), moved


def compile_art(setpath, mem):
    s = Set256(setpath)
    w = lambda a: mem[a] | mem[a + 1] << 8
    stats = Counter()
    pages = {}
    for a in range(TILES, TILES + 256 * 32):
        if a < 0x10000 and s.master(a) != mem[a]:
            stats['tile master differs'] += 1
    for t in range(256):
        out = bytearray()
        for r in range(16):
            a = TILES + t * 32 + r * 2
            for b in (a, a + 1):
                out += bytes(s.pixels(b)) if b < 0x10000 else bytes(8)
        page = TILE_PAGE + (t >> 5)
        pages.setdefault(page, bytearray(8192))[(t & 31) << 8:((t & 31) << 8) + 256] = out
    page, at = FIRST_ART_PAGE, 0
    index = bytearray()
    images = {}

    def figure(base, wide, rows):
        out = bytearray()
        for r in range(rows):
            for c in range(wide):
                ma = base + r * 2 * wide + c
                ga = ma + wide
                if ga >= 0x10000:
                    out += bytes((SKIP,)) * 8
                    continue
                if s.master(ma) != mem[ma] or s.master(ga) != mem[ga]:
                    stats['figure master differs'] += 1
                mk, g = s.pixels(ma), s.pixels(ga)
                for k in range(8):
                    m, v = mk[k], g[k]
                    if m == 255 and v == 0:
                        out.append(SKIP)
                        continue
                    if m not in (0, 255):
                        stats['mask not 0 or 255'] += 1
                    if m == 255:
                        stats['paint under an open mask'] += 1
                    if v == SKIP:
                        stats['value FE used'] += 1
                        v = 0xFD
                    out.append(v)
        return bytes(out)
    for kind, table, n, wide, rows in (('big', BIG_TABLE, N_BIG, 3, 32), ('small', SMALL_TABLE, N_SMALL, 2, 16)):
        for f in range(n):
            base = w(table + 2 * f)
            img = figure(base, wide, rows) if 0x8000 <= base <= 0xFF00 else bytes((SKIP,)) * (wide * 8 * rows)
            if at + len(img) > 8192:
                page, at = page + 1, 0
            pages.setdefault(page, bytearray(8192))[at:at + len(img)] = img
            index += bytes((page, at & 255, 0x40 + (at >> 8)))
            images[(kind, f)] = (page, at, wide * 8, rows, base)
            at += len(img)
    return {p: bytes(b) for p, b in pages.items()}, bytes(index), images, stats


def panel_pages(shots, holes):
    size = 256 * 32 + 768
    all_ = [shots[i:i + size] for i in range(0, len(shots), size)]
    modal = bytearray(256 * 32)
    for i in range(256 * 32):
        modal[i] = Counter(s[i] for s in all_).most_common(1)[0][0]
    play = [s for s in all_ if sum(a == b for a, b in zip(s[:256 * 32], modal)) > 0.9 * 256 * 32]
    changed = set()
    for s_ in play:
        for i in range(256 * 32):
            if s_[i] != modal[i]:
                changed.add((i // 256 // 8, (i % 256) // 8))
    if changed - set(holes):
        raise ValueError('panel cells change that are not holes: %s' % sorted(changed - set(holes)))
    out = bytearray(modal)
    for r, c in holes:
        for y in range(8):
            for x in range(8):
                out[(r * 8 + y) * 256 + c * 8 + x] = CLEAR
    return bytes(out), len(play), len(all_)


class Patch:
    name = 'Ruff and Reddy 128K: Enhanced colours on a full Layer 2'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000

    def __init__(self, source, setpath, panelpath, palettepath, keep_art=None):
        self.source = str(source)
        h = json.loads(PROFILE.read_text())['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        pal, self.moved = palette(json.loads(Path(palettepath).read_text()))
        self.stub_extra = bytes.fromhex(h['setup']) + pal
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        s = zt.Z80Snapshot(str(source))
        mem = bytearray(65536)
        mem[0x4000:0x8000] = s.banks[5]
        mem[0x8000:0xC000] = s.banks[2]
        mem[0xC000:] = s.banks[0]
        self.art = keep_art or compile_art(setpath, mem)
        self.pages, self.index, self.images, self.stats = self.art
        self.panel, self.play_shots, self.all_shots = panel_pages(Path(panelpath).read_bytes(), HOLES)
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x1900:0x1C00] = bytes(0x300)
        self.ram[0x1A00:0x1A00 + len(self.index)] = self.index
        self.ram[0x1E00:0x2000] = bytes(512)
        self.ram[self.syms['V_BACK'] - 0x2000] = L2_A
        self.ram[V_RECT - 0x2000:V_RECT - 0x2000 + 2] = (0x3900).to_bytes(2, 'little')
        self.ram[V_Q - 0x2000:V_Q - 0x2000 + 2] = V_QBUF.to_bytes(2, 'little')
        self.sites = []
        self.site_info = {}
        for a, (target, sym, kind) in CALLS.items():
            self.sites.append((a, b'\xcd' + zt.w16(target), b'\xcd' + zt.w16(self.syms[sym])))
            self.site_info[a] = (target, sym, kind)
        y = self.syms
        self.sites += [(ROOM_SITE, b'\xcd\xdd\xaa', b'\xcd' + zt.w16(y['h_room'])),
                       (RENDER, b'\xc3\x1e\xa3', b'\xc3' + zt.w16(y['h_render'])),
                       (WAIT, b'\xfb\x76\xf3', b'\xc3' + zt.w16(y['h_render_end'])),
                       (COPY_IN, b'\x31\xa4\x9e', b'\xc3' + zt.w16(y['h_copy'])),
                       (COPY_OUT, b'\x31\xbf\x5d', b'\xc3' + zt.w16(y['h_copy_end'])),
                       (MSG_SITE, b'\xed\x73\xa0', b'\xc3' + zt.w16(y['h_msg'])),
                       (TITLE_SITE, b'\xaf\xd3\xfe', b'\xc3' + zt.w16(y['h_title']))]
        self._banks()

    def _banks(self):
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_big', 'h_small', 'h_copy', 'h_room', 'h_title', 'h_over', 'h_msg', 'h_render', 'h_render_end'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        extra = {12: bytes(self.ram) + bytes(self.page)}
        panel = self.panel + bytes(8192 - len(self.panel))
        extra[18] = bytes(8192) + panel
        extra[21] = bytes(8192) + panel
        for p, data in self.pages.items():
            b = p // 2
            cur = bytearray(extra.get(b, bytes(16384)))
            cur[(p & 1) * 8192:(p & 1) * 8192 + 8192] = data
            extra[b] = bytes(cur)
        self.extra_banks = extra
        self.top_page = max(self.pages)

    def apply(self, snap):
        if not A.is_ruff_and_reddy(snap):
            raise ValueError('Not the supported Ruff and Reddy 128K release (MD5 %s)' % A.SOURCE_MD5)
        banks = {i: bytearray(b) for i, b in snap.banks.items()}
        for a, old, new in self.sites:
            bank, at = (0, a - 0xC000) if a >= 0xC000 else (2, a - 0x8000)
            if bytes(banks[bank][at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[bank][at:at + len(new)] = new
        snap.banks = type(snap.banks)(sorted((i, bytes(b)) for i, b in banks.items()))


def build(source, destination, p):
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


class View:
    def __init__(self, mem, patch, page, pages):
        self.mem = bytearray(mem)
        self.patch, self.page, self.pages = patch, page, pages
        self.model = None

    def __len__(self):
        return 65536

    def _map(self, a):
        s = a >> 13
        return self.model.nr.get(0x50 + s, (255, 255, 10, 11, 4, 5, 0, 1)[s])

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        m = self._map(a)
        if a < 0x4000:
            if m == 255:
                if a >= 0x2000:
                    return self.patch.page[a - 0x2000]
                return self.mem[a]
            if m == 24:
                return self.page[a - 0x2000]
            return self.pages[m][a & 8191]
        if a < 0x6000 and m != 10:
            return self.pages[m][a & 8191] if m in self.pages else self.patch.pages[m][a & 8191]
        return self.mem[a]

    def __setitem__(self, a, v):
        m = self._map(a)
        if a < 0x4000:
            if m == 24:
                self.page[a - 0x2000] = v
            elif m != 255:
                self.pages[m][a & 8191] = v
            return
        if a < 0x6000 and m != 10:
            raise AssertionError('write to art page %d' % m)
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line, lines=311, t_line=228)
        self.nr.update({0x50 + i: p for i, p in enumerate((255, 255, 10, 11, 4, 5, 0, 1))})
        self.nr[1] = 0x32
        self.io = []

    def write_port(self, regs, port, v, *args):
        if port in (0x243B, 0x253B) or port & 255 == 0x6B:
            return super().write_port(regs, port, v, *args)
        self.io.append((port, v))


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class State:
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.pages = {p: bytearray(b'\xff' * 8192) for p in list(range(32, 37)) + list(range(38, 43)) + list(range(CLEAN_PAGE, CLEAN_PAGE + 5))}
        self.nr = {0x12: L2_A, 0x69: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=12000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'ruff-enh-hook')
    m = Model(s, speed, st.line)
    m.nr.update(st.nr)
    v.model = m
    n = 0
    R = s.registers
    while n == 0 or R[24] != stop_pc or (stop_sp is not None and R[12] != stop_sp):
        s.opcodes[v[R[24]]]()
        n += 1
        if n > limit:
            raise AssertionError('hook did not terminate at %04X' % R[24])
    st.line = m.line()
    for k in (0x12, 0x69):
        if k in m.nr:
            st.nr[k] = m.nr[k]
    return list(R), v, m


class Picture:
    """The expected picture and the game's own buffer, from the room map and the plots, read from the game's state."""
    def __init__(self, patch):
        self.patch = patch
        self.clean = [bytearray(b'\xff' * 256) for _ in range(160)]
        self.mono0 = bytearray(26 * 160)
        self.begin()

    def begin(self):
        self.pic = [bytearray(r) for r in self.clean]
        self.mono = bytearray(self.mono0)

    def room(self, mem):
        rm = mem[0xAB04]
        ptr = mem[0xAA65 + 2 * rm] | mem[0xAA65 + 2 * rm + 1] << 8
        pages = self.patch.pages
        self.clean = [bytearray(b'\xff' * 256) for _ in range(160)]
        self.mono0 = bytearray(26 * 160)
        for band in range(10):
            for col in range(13):
                t = mem[ptr + band * 130 + col]
                page = pages[TILE_PAGE + (t >> 5)]
                base = (t & 31) << 8
                for r in range(16):
                    y = band * 16 + r
                    self.clean[y][X_LEFT + col * 16:X_LEFT + col * 16 + 16] = page[base + r * 16:base + r * 16 + 16]
                    a = TILES + t * 32 + r * 2
                    self.mono0[y * 26 + col * 2] = mem[a] if a < 0x10000 else 0
                    self.mono0[y * 26 + col * 2 + 1] = mem[a + 1] if a + 1 < 0x10000 else 0

    def plot(self, mem, kind):
        if kind == 'big':
            x, y, n, table, h, wide = mem[0xA671], mem[0xA69B], mem[0xA68F], BIG_TABLE, 32, 3
        else:
            x, y, n, table, h, wide = mem[0xA86C], mem[0xA896], mem[0xA88A], SMALL_TABLE, 16, 2
        img = self.patch.images.get((kind, n))
        src = mem[table + 2 * n] | mem[table + 2 * n + 1] << 8
        data = self.patch.pages[img[0]] if img else None
        shift = x & 7
        col = x >> 3
        for r in range(h):
            row = y + r - ROW_FIRST
            if not 0 <= row < 160:
                continue
            at = src + r * 2 * wide
            m = int.from_bytes(mem[at:at + wide], 'big')
            g = int.from_bytes(mem[at + wide:at + 2 * wide], 'big')
            bits = (wide + 1) * 8
            m2 = ((m << 8) | 0xFF) >> shift | ((1 << shift) - 1) << (bits - shift)
            g2 = (g << 8) >> shift
            o = row * 26 + col
            for i in range(wide + (1 if shift else 0)):
                sh = (wide - i) * 8
                if o + i < len(self.mono):
                    self.mono[o + i] = (self.mono[o + i] & ((m2 >> sh) & 255)) | ((g2 >> sh) & 255)
            if data is None:
                continue
            base = img[1] + r * wide * 8
            for i in range(wide * 8):
                xx = X_LEFT + x + i
                if xx >= 232:
                    break
                v = data[base + i]
                if v != SKIP:
                    self.pic[row][xx] = v


def _flat(sim):
    m = sim.memory
    return bytes(16384) + bytes(m.memory[1]) + bytes(m.memory[2]) + bytes(m.memory[3])


def _patched(patch, mem):
    out = bytearray(mem)
    for a, old, new in patch.sites:
        if a < 0xC000 or mem[a:a + len(old)] == old:
            out[a:a + len(new)] = new
    return out


def verify(patch, rzx_path, stop=None, collect=0):
    """Replay the original; at every changed site run the hook on a copy of the state and compare with the original's run: every register with R,
    all 48K RAM. At every copy: Layer 2 against a picture built from the room map and the plots, and the game's own buffer against the same model
    in mono, so a writer the hooks missed fails."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    pic = Picture(patch)
    fresh = [True]

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    pcs = set(CALLS) | {ROOM_SITE, MSG_SITE, TITLE_SITE, COPY_IN, RENDER, WAIT}

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        if pc >= 0xC000:
            want = {MSG_SITE: b'\xed\x73\xa0', TITLE_SITE: b'\xaf\xd3\xfe', 0xFD75: b'\xcd\x70\xac'}[pc]
            if mem[pc:pc + 3] != want:
                return                          # another bank at C000: not this site
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        patched = _patched(patch, mem)
        ref = simpool.machine(Simulator, list(mem), regs, 'rr-ref')
        R = ref.registers
        expect_clock = 0
        speed = 0
        allow_io = []
        if pc == ROOM_SITE:
            kind = 'room'
            sp = regs[12]
            n = 0
            while n == 0 or R[24] != pc + 3 or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stop_pc, stop_sp = pc + 3, sp
        elif pc == COPY_IN:
            kind = 'copy'
            sp = 0x5DBF
            n = 0
            while n == 0 or R[24] != COPY_RET or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stop_pc, stop_sp = COPY_RET, sp
        elif pc == RENDER:
            kind = 'render'
            ref.opcodes[mem[pc]]()
            stop_pc, stop_sp = 0xA31E, None
            expect_clock = 3
            pic.begin()
        elif pc == WAIT:
            kind = 'wait'
            ref.opcodes[mem[pc]]()
            stop_pc, stop_sp = patch.syms['h_halt'], None
            speed = 3
        elif pc == MSG_SITE:
            kind = 'msg'
            ref.opcodes[0xED]()
            stop_pc, stop_sp = 0xD42F, None
        elif pc == TITLE_SITE:
            kind = 'title'
            ref.opcodes[mem[pc]]()
            ref.opcodes[ref.memory[R[24]]]()
            stop_pc, stop_sp = 0xD335, None
            allow_io = [(regs[0] * 0 + 0x00FE, 0)]
        else:
            target, sym, kind = patch.site_info[pc]
            ref.opcodes[mem[pc]]()
            stop_pc, stop_sp = target, None
            if kind in ('big', 'small'):
                pic.plot(mem, kind)
                c['figures %s' % kind] += 1
                speed = 3
                expect_clock = 3
        if kind in ('big', 'small', 'render', 'wait', 'copy') and regs[26]:
            fail('interrupts on at a hook', {'pc': hex(pc)})
        got, v, model = run_hook(patch, st, patched, regs, stop_pc, stop_sp, speed=speed)
        for i in CMP:
            if kind == 'wait' and i == 24:
                continue
            if (bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': R[i], 'got': got[i], 'kind': kind})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.sites:
            if a < 0xC000 or mem[a:a + len(old)] == old:
                expected[a - 0x4000:a - 0x4000 + len(new)] = new
        if kind == 'room':
            sp0 = regs[12]
            for a in range(sp0 - 32, sp0):
                expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'kind': kind, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x52] != 10:
            fail('MMU not restored', {'pc': hex(pc), 'kind': kind})
        if model.nr[7] != expect_clock:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7], 'kind': kind})
        if kind == 'title':
            if [v_ for p_, v_ in model.io] != [0] or len(model.io) != 1:
                fail('title I/O differs', {'io': model.io[:4]})
        elif model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        if kind in ('hide', 'msg', 'title', 'room') and st.nr[0x69] != 0:
            fail('overlay not hidden', {'pc': hex(pc)})
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['R comparisons'] += 1
        if kind == 'room':
            pic.room(mem)
            pic.begin()
            # the clean canvas
            bad = 0
            for y in range(160):
                page = st.pages[CLEAN_PAGE + (y >> 5)]
                at = (y & 31) << 8
                if page[at:at + 256] != pic.clean[y]:
                    bad += 1
            if bad:
                fail('clean canvas differs from the map', {'rows': bad})
        if kind == 'copy':
            c['publications'] += 1
            if st.nr[0x69] != 0x80:
                fail('overlay not on after publish', {})
            front = st.nr[0x12]
            bad = 0
            first = None
            for y in range(160):
                page = st.pages[front * 2 + (y >> 5)]
                at = (y & 31) << 8
                row = page[at:at + 256]
                if row != pic.pic[y]:
                    bad += sum(1 for a, b in zip(row, pic.pic[y]) if a != b)
                    if first is None:
                        first = (y, [i for i in range(256) if row[i] != pic.pic[y][i]][:6])
            if bad:
                fail('Layer 2 differs from the model', {'count': bad, 'first': first, 'pub': c['publications']})
            c['pixels compared'] += 40960
            buf = mem[0x8C90:0x8C90 + 26 * 160]
            if buf != bytes(pic.mono):
                n = sum(1 for a, b in zip(buf, pic.mono) if a != b)
                i = [j for j in range(len(buf)) if buf[j] != pic.mono[j]][0]
                fail('game buffer differs from the mono model', {'bytes': n, 'first': (i // 26, i % 26), 'pub': c['publications']})
    frames, err = trace(str(rzx_path), pcs, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


def unit_tests(patch, states):
    """Every hook at the four incoming clocks, both IFF values and eight R phases."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    R = ref.registers
                    st = State(patch)
                    want_clock, run_speed, skip_pc = speed, speed, False
                    if pc == ROOM_SITE or pc == COPY_IN:
                        sp = rr[12] if pc == ROOM_SITE else 0x5DBF
                        ret = pc + 3 if pc == ROOM_SITE else COPY_RET
                        n = 0
                        while n == 0 or R[24] != ret or R[12] != sp:
                            ref.opcodes[ref.memory[R[24]]]()
                            n += 1
                        stop, stop_sp = ret, sp
                    elif pc == RENDER:
                        ref.opcodes[mem[pc]]()
                        stop, stop_sp = 0xA31E, None
                        want_clock = 3
                    elif pc == WAIT:
                        ref.opcodes[mem[pc]]()
                        stop, stop_sp = patch.syms['h_halt'], None
                        st.page[V_SPEED - 0x2000] = speed
                        run_speed = 3
                        skip_pc = True
                    elif pc == MSG_SITE:
                        ref.opcodes[0xED]()
                        stop, stop_sp = 0xD42F, None
                    elif pc == TITLE_SITE:
                        ref.opcodes[mem[pc]]()
                        ref.opcodes[ref.memory[R[24]]]()
                        stop, stop_sp = 0xD335, None
                    else:
                        target = patch.site_info[pc][0]
                        ref.opcodes[mem[pc]]()
                        stop, stop_sp = target, None
                    got, v, model = run_hook(patch, st, _patched(patch, mem), rr, stop, stop_sp, speed=run_speed)
                    if any((bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i] for i in CMP if not (skip_pc and i == 24)):
                        c['ABI registers differ!'] += 1
                    if model.nr[7] != want_clock:
                        c['incoming clock wrong!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x52] != 10:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def mutate(name, old, new, last=False):
        b = copy.copy(patch)
        b.ram = bytearray(patch.ram)
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.rfind(old) if last else code.find(old)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new)] = new
        b._banks()
        out[name] = b
    mutate('R off by one', bytes((0x3E, 0x100 - 12, 0xCD)), bytes((0x3E, 0x100 - 11)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('figure x off by one', bytes.fromhex('C618'), bytes.fromhex('C619'), last=True)
    mutate('skip pixels drawn', bytes.fromhex('FEFE2801'), bytes.fromhex('FEFD2801'))
    mutate('figures never drawn', bytes.fromhex('ED5B423EB7E5ED52E128'), bytes.fromhex('ED5B423EB7E5ED52E118'))
    mutate('old figures never restored', bytes.fromhex('2A3A3E7DB7C8'), bytes.fromhex('2A3A3E7DB7C9'))
    mutate('MMU slot 2 left mapped', bytes.fromhex('ED91520AC9'), bytes.fromhex('00000000C9'), last=True)
    mutate('overlay never published', bytes.fromhex('ED916980'), bytes.fromhex('ED916900'))
    mutate('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('ED916980'))
    return out


def boot_check(nex, z80, patch):
    from . import nextboot
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
            if tail <= a < tail + size or (nexload and 0x5B00 <= a < 0x5C00):
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad
