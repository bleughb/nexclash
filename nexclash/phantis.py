"""Phantis / Game Over 2 (Dinamic, 1987-88, 48K, two parts): clash removal by a Layer 2 figure overlay.

The ULA bitmap stays the original's byte for byte; the copy's table shows the clean attributes; figures' ink goes on a
double-buffered Layer 2 in plot order. See asm/phantis_core.inc.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
CMP = tuple(hooklib.CMP_R)
DECISIONS = {'figures': 'original bitmap on the ULA; figure ink in its own colour on Layer 2, in plot order',
             'scenery': 'keeps its own attributes', 'pace': 'original; hlib_pace K window on the plot', 'outline': 'none',
             'enhanced': 'waiting for the mock-up'}
PUBLISHER = 'Dinamic, 1988'
NEG_STOP = 3000


class Part:
    def __init__(self, n, md5, plot, plot_old, copy, copy_old, mid, mid_old, stop, live_table, table, table_rows, work_attr, clean_attr, cls, signature, gvars, bitmap, xoff=3, wide=26, stride=30, stars=0xD07B, shiftbuf=0xE9DE):
        self.xoff, self.wide, self.stride, self.stars, self.shiftbuf = xoff, wide, stride, stars, shiftbuf
        self.n, self.md5, self.plot, self.plot_old = n, md5, plot, plot_old
        self.copy, self.copy_old, self.mid, self.mid_old, self.stop, self.live_table = copy, copy_old, mid, mid_old, stop, live_table
        self.table, self.table_rows, self.work_attr, self.clean_attr = table, table_rows, work_attr, clean_attr
        self.cls, self.signature, self.g, self.bitmap = cls, signature, gvars, bitmap
        self.profile = ROOT / ('docs/profiles/phantis%d.json' % n)


P1 = Part(1, 'c39caed696ba547f693546b707c9cee8', 0xC6DF, '1103C9', 0xC92D, '31B8B5', 0xC976, 'ED7B14C9', 0xC97A, 0x5B00, 0xE9FC, 15, 0xFE00, 0xEE2E,
          (0xC602, 0xC612, 0xC6CE), {0xC6DF: '1103C9', 0xC976: 'ED7B14C9', 0xC6CE: '210040', 0xE9FC: 'F0EF'},
          dict(ptr=0xC903, rows=0xC905, cols=0xC906, x=0xC907, y=0xC908, skip=0xC84B, ink=0xC910, mask=0xC911, count=0xC90F, cells=0xE563), 0xEFF0)
P2 = Part(2, '55c89bb16ffde2f58a43ed3be7b95bcf', 0xC759, '1184C9', 0xC995, 'DD21A4B5', None, None, None, None, None, 0, 0xFE00, 0xEF3C,
          (0xC74B, 0xFBF5, 0xBA6F), {0xC759: '1184C9', 0xC995: 'DD21A4B5', 0xC74B: '210040', 0xFBF5: '210040', 0xBA6F: '210040'},
          dict(ptr=0xC984, rows=0xC986, cols=0xC987, x=0xC988, y=0xC989, skip=0xC8C5, ink=0xC991, mask=0xC992, count=0xC990, cells=None), 0xF0E0, xoff=2, wide=28, stride=28, stars=None)
PARTS = {1: P1, 2: P2}


def load_profile(part=P1):
    return json.loads(part.profile.read_text())


def _profile_path():
    return P1.profile


def part_of(snap):
    banks = getattr(snap, 'banks', None)
    for p in PARTS.values():
        try:
            if banks is None:
                if getattr(snap, 'machine', '48K') != '48K':
                    continue
                ok = all(bytes(snap.memory[a:a + len(v) // 2]) == bytes.fromhex(v) for a, v in p.signature.items())
            else:
                if getattr(snap, 'is128', False):
                    continue
                ok = all(_peek(banks, a, len(v) // 2) == bytes.fromhex(v) for a, v in p.signature.items())
        except (KeyError, TypeError, IndexError):
            continue
        if ok:
            return p
    return None


def is_phantis(snap):
    return part_of(snap) is not None


def _peek(banks, a, n):
    b = {0x4000: 5, 0x8000: 2, 0xC000: 0}[a & 0xC000]
    return bytes(banks[b][a & 0x3FFF:(a & 0x3FFF) + n])


class Patch:
    uses_printer_buffer = True
    keep_printer_buffer = True
    hook_page_data = b''
    setup_call = 0xD000
    tail_addr = 0x5D9F              # BASIC's leftovers below the low stack: the game never reads them

    def __init__(self, source=None, part=None, enhanced=None):
        self.source = str(source) if source else None
        self.enhanced = enhanced
        if part is None:
            part = part_of(zt.Z80Snapshot(str(source)))
            if part is None:
                raise ValueError('Not a supported Phantis / Game Over 2 part')
        self.part = part
        self.name = 'Phantis part %d: clash removed by a Layer 2 figure overlay' % part.n
        h = json.loads((ROOT / ('docs/profiles/phantis%de.json' % part.n)).read_text())['hooks'] if enhanced else load_profile(part)['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x1A00:0x1C00] = bytes(512)
        self.ram[0x1E00:0x2000] = bytes(512)
        self.colours = None
        if enhanced:
            from . import phantis_art
            self.colours = phantis_art.load(enhanced)
            setup = bytearray(self.stub_extra)
            at = self.syms['l2_pal256'] - 0xD000
            setup[at:at + 512] = self.colours['palette']
            self.stub_extra = bytes(setup)
            self.ram[self.syms['V_TN'] - 0x2000:self.syms['V_TN'] - 0x2000 + 2] = self.colours['n'].to_bytes(2, 'little')
            if len(self.colours['index']) > 0x800:
                raise ValueError('colour index too long')
            self.ram[0x1100:0x1100 + len(self.colours['index'])] = self.colours['index']
        self.ram[self.syms['V_BACK'] - 0x2000] = 16
        self.ram[self.syms['V_RECT'] - 0x2000:self.syms['V_RECT'] - 0x2000 + 2] = (0x3A00).to_bytes(2, 'little')
        p = part
        self.sites = [(p.plot, bytes.fromhex(p.plot_old), b'\xc3' + zt.w16(self.syms['h_plot'])),
                      (p.copy, bytes.fromhex(p.copy_old), b'\xc3' + zt.w16(self.syms['h_copy']) + b'\x00' * (len(p.copy_old) // 2 - 3))]
        if p.mid:
            self.sites.append((p.mid, bytes.fromhex(p.mid_old), b'\xc3' + zt.w16(self.syms['h_mid']) + b'\x00'))
        for i, a in enumerate(p.cls):
            self.sites.append((a, b'\x21\x00\x40', b'\xc3' + zt.w16(self.syms['h_cls%d' % (i + 1)])))
        self.table_sites = []
        self.live_table = []
        for r in range(p.table_rows):            # the copy's table: attribute rows from the clean buffer
            at = 2 * (8 + 9 * r)
            self.table_sites.append((p.table + at, zt.w16(p.work_attr + 30 * r), zt.w16(p.clean_attr + 30 * r)))
            self.live_table.append((p.live_table + at, zt.w16(p.clean_attr + 30 * r)))
        self._banks()

    def _banks(self):
        # Hidden ROM (page 25): tiny entry and return veneers only. Code and writable state: page 24.
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in [k for k in self.syms if k.startswith('h_')]:
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 8] = self.ram[at:at + 8]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}
        if self.colours:
            pages = self.colours['pages'] + ([b'\xff' * 8192] if len(self.colours['pages']) & 1 else [])
            for i in range(0, len(pages), 2):
                self.extra_banks[22 + i // 2] = pages[i] + pages[i + 1]

    def all_sites(self):
        return self.sites + self.table_sites

    def apply(self, snap):
        if part_of(snap) is not self.part:
            raise ValueError('Not the supported Phantis part %d release (MD5 %s)' % (self.part.n, self.part.md5))
        banks = {i: bytearray(snap.banks[i]) for i in (5, 2, 0)}
        for a, old, new in self.all_sites():
            b = banks[{0x4000: 5, 0x8000: 2, 0xC000: 0}[a & 0xC000]]
            at = a & 0x3FFF
            if bytes(b[at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            b[at:at + len(new)] = new
        snap.banks = type(snap.banks)(((i, bytes(banks[i])) if i in banks else (i, snap.banks[i])) for i in snap.banks)


def build(source, destination, enhanced=None):
    p = Patch(source, enhanced=enhanced)
    zt.convert(str(source), str(destination), patch=p, quiet=True, keep_printer_buffer=True)
    return p


class View:
    """64K view of the game RAM + the Next pages the hook can map, per the model's MMU."""
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
        return self.mem[a]

    def __setitem__(self, a, v):
        m = self._map(a)
        if a < 0x4000:
            if m == 24:
                self.page[a - 0x2000] = v
            elif m != 255:
                self.pages[m][a & 8191] = v
            return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line, lines=312, t_line=224)
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
    """What persists between hooks: the hook page, the L2 pages, the NextRegs that matter."""
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.pages = {p: bytearray(b'\xff' * 8192) for p in list(range(32, 36)) + list(range(38, 42))}
        if patch.colours:
            for i, d in enumerate(patch.colours['pages']):
                self.pages[44 + i] = d
        self.nr = {0x12: 16, 0x69: 0, 0x17: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'phantis-hook')
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
    for k in (0x12, 0x69, 0x17):
        if k in m.nr:
            st.nr[k] = m.nr[k]
    return list(R), v, m


class Overlay:
    """The expected picture, by an independent reading of what the original body left in its variables."""
    def __init__(self, part, colours=None):
        self.part = part
        self.table = None
        if colours:
            import struct
            self.pages = colours['pages']
            self.table = {}
            for i in range(colours['n']):
                p, page, off, w = struct.unpack('<HBHB', colours['index'][i * 6:i * 6 + 6])
                self.table[p] = (page, off, w)
        self.free = set()
        self.back = {}          # (x, y) -> colour, or 254: transparent, but earlier ink gone
        self.fresh = False
        self.plots = []
        self.paper = set()

    def plot_painted(self, mem, desc, shift):
        g = self.part.g
        page, off, w = self.table[desc]
        rows, cols, y0 = mem[g['rows']], mem[g['cols']], mem[g['y']]
        x0 = mem[g['x']] >> 1
        ptr = mem[g['ptr']] | mem[g['ptr'] + 1] << 8
        base = self.part.shiftbuf if shift else desc + 3
        r0, c0 = divmod(ptr - base, w + shift)
        s = w * 8 + 8
        data = self.pages[(page - 44)]
        for r in range(rows):
            y = y0 + r
            if y >= 120:
                break
            for c in range(cols):
                if x0 + self.part.xoff + c >= 32:
                    continue
                for b in range(8):
                    v = data[off + (r0 + r) * s + (0 if shift else 4) + (c0 + c) * 8 + b]
                    if v == 255:
                        continue
                    xy = ((x0 + self.part.xoff + c) * 8 + b, y + 8)
                    self.back[xy] = v
                    self.paper.discard(xy)
                    self.free.add(xy)

    def plot(self, mem, desc=0, shift=0):
        g = self.part.g
        if self.fresh:
            self.back = {}
            self.plots = []
            self.paper = set()
            self.free = set()
            self.fresh = False
        self.plots.append(tuple(mem[g[k]] for k in ('rows', 'cols', 'x', 'y', 'skip', 'ink')))
        if self.table is not None and desc in self.table:
            return self.plot_painted(mem, desc, shift)
        rows, cols = mem[g['rows']], mem[g['cols']]
        y0, x0, skip, inkv = mem[g['y']], mem[g['x']] >> 1, mem[g['skip']], mem[g['ink']]
        src = mem[g['ptr']] | mem[g['ptr'] + 1] << 8
        msk = mem[g['mask']] | mem[g['mask'] + 1] << 8
        col = lambda a: (a & 7) | (8 if a & 0x40 else 0)
        tbl = 0 if not g['cells'] else (mem[g['cells'] + 1] << 8 | ((mem[g['cells']] + skip) & 255))
        cr = rows >> 3
        for r in range(rows):
            y = y0 + r
            if y >= 120:
                break
            for c in range(cols):
                gb, mb = mem[(src + r * (cols + skip) + c) & 65535], mem[(msk + r * (cols + skip) + c) & 65535]
                paper = 254
                if inkv == 255 and g['cells']:
                    row = (y >> 3) - (y0 >> 3)
                    if row < cr:
                        a = mem[(tbl + row * (cols + skip) + c) & 65535]
                        ink = col(a)
                        if a & 0x38:
                            paper = ((a >> 3) & 7) | (8 if a & 0x40 else 0)
                    else:
                        ink = 254
                else:
                    ink = col(inkv)
                for b in range(8):
                    if x0 + self.part.xoff + c >= 32:
                        continue
                    xy = ((x0 + self.part.xoff + c) * 8 + b, y + 8)
                    if gb & (128 >> b):
                        self.back[xy] = ink
                        self.paper.discard(xy)
                        self.free.discard(xy)
                    elif mb & (128 >> b):
                        self.back[xy] = paper
                        self.paper.discard(xy)
                        self.free.discard(xy)
                        if paper != 254:
                            self.paper.add(xy)


def _flat(sim):
    m = sim.memory
    return bytes(m[0:65536])


def verify(patch, rzx_path, stop=None, collect=0, progress=None, compare_every=1):
    """Replay the original; at every changed site run the hook on a copy of the state and compare with the original's
    run: every register with R, all 48K RAM but the changed bytes and the dead stack. The Layer 2 picture is compared
    with an independent model at every publication, and every lit pixel with the work bitmap the copy just showed."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    p = patch.part
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    ov = Overlay(p, patch.colours)
    SP_A = patch.syms.get('V_SP')

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    kind_of = {p.plot: 'plot', p.copy: 'copy'}
    kind_of.update({a: 'cls' for a in p.cls})
    site_bytes = {a: (old, new) for a, old, new in patch.sites}

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        kind = kind_of[pc]
        old = site_bytes[pc][0]
        if mem[pc:pc + len(old)] != old:
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        patched = bytearray(mem)
        here = [(a, new) for a, o, new in patch.sites if mem[a:a + len(o)] == o]   # a site in a buffer the game has since overwritten is gone
        for a, new in here:
            patched[a:a + len(new)] = new
        for a, new in patch.live_table:
            patched[a:a + 2] = new
        ref = simpool.machine(Simulator, list(mem), regs, 'phantis-ref')
        sp = regs[12]
        if kind == 'plot':
            ret = mem[sp] | mem[(sp + 1) & 65535] << 8
            n = 0
            R = ref.registers
            while n == 0 or R[24] != ret or R[12] != (sp + 2) & 65535:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stop_pc, stop_sp = ret, (sp + 2) & 65535
            count0 = mem[p.g['count']]
            drawn = ref.memory[p.g['count']] != count0
            if drawn:
                hl = regs[6] << 8 | regs[7]
                ov.plot(ref.memory, mem[hl] | mem[hl + 1] << 8, mem[hl + 2] & 1)
        elif kind == 'copy' and p.stop:
            R = ref.registers
            while R[24] != p.stop:
                ref.opcodes[ref.memory[R[24]]]()
            stop_pc, stop_sp = p.stop, None
        elif kind == 'copy':
            ret = mem[sp] | mem[(sp + 1) & 65535] << 8
            n = 0
            R = ref.registers
            while n == 0 or R[24] != ret or R[12] != (sp + 2) & 65535:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stop_pc, stop_sp = ret, (sp + 2) & 65535
        else:
            ref.opcodes[mem[pc]]()
            stop_pc, stop_sp = ref.registers[24], None
        got, v, model = run_hook(patch, st, patched, regs, stop_pc, stop_sp)
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'kind': kind})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, new in here:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        for a, new in patch.live_table:
            expected[a - 0x4000:a - 0x4000 + 2] = new
        if kind == 'copy':
            # The attributes shown: the clean buffer's, every byte the copy writes.
            for r in range(15):
                at = 0x5820 + p.xoff + 32 * r - 0x4000
                want = bytes(mem[p.clean_attr + p.stride * r:p.clean_attr + p.stride * r + p.wide])
                if bytes(actual[at:at + p.wide]) != want:
                    fail('copy attributes are not the clean buffer', {'row': r})
                expected[at:at + p.wide] = want
        # The stack below SP: the original's call chain wrote it, the hook's ran on its own stack.
        for a in range(sp - 32, sp):
            expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'kind': kind, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255:
            fail('MMU not restored', {'pc': hex(pc)})
        if model.nr[7] != 0:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7]})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if kind == 'cls':
            if st.nr[0x69] != 0:
                fail('overlay not hidden', {})
        if kind == 'copy':
            c['publications'] += 1
            if st.nr[0x69] != 0x80:
                fail('overlay not on after publish', {})
            front = st.nr[0x12]
            picture = {}
            for y in range(8, 128):
                page = st.pages[front * 2 + (y >> 5)]
                row = (y & 31) << 8
                seg = page[row + p.xoff * 8:row + (p.xoff + p.wide) * 8]
                if seg.count(255) == p.wide * 8:
                    continue
                for xb, val in enumerate(seg):
                    if val != 255 and val != 254:
                        picture[(xb + p.xoff * 8, y)] = val
            want = {} if ov.fresh else {xy: val for xy, val in ov.back.items() if val != 254 and p.xoff * 8 <= xy[0] < (p.xoff + p.wide) * 8}
            if picture != want:
                diff = [k for k in set(picture) | set(want) if picture.get(k) != want.get(k)]
                fail('overlay differs from the model', {'pc': hex(pc), 'count': len(diff), 'ex': sorted(diff)[:6]})
            c['overlay pixels compared'] += len(picture)
            # Every pixel lit on Layer 2 is a set bit of the bitmap the copy has just shown.
            stars = set()
            if p.stars:
                for i in range(3):
                    s0 = mem[p.stars + 3 * i] | mem[p.stars + 3 * i + 1] << 8
                    stars.update((s0 - 1, s0, s0 + 1))
            cut = False
            for (x, y), val in picture.items():
                if (x, y) in ov.paper or (x, y) in ov.free:
                    continue
                at = p.bitmap + (y - 8) * p.stride + (x - p.xoff * 8) // 8
                if mem[at] & (128 >> (x & 7)):
                    continue
                if at in stars:    # a star's plot writes or clears the whole byte, after this figure
                    c['figure pixels under a star'] += 1
                    continue
                c['figure pixels cut by scenery drawn after them'] += 1
                cut = True
                if len(examples['figure pixels cut']) < 3:
                    examples['figure pixels cut'].append({'x': x, 'y': y, 'plots': ov.plots, 'byte': mem[at]})
            if cut:
                c['pictures with a figure cut'] += 1
            # The attributes shown: the work ones less the figures' paint must be the clean ones.
            n_attr = 15 * p.stride
            ca, wa = mem[p.clean_attr:p.clean_attr + n_attr], mem[p.work_attr:p.work_attr + n_attr]
            for i in range(n_attr):
                if ca[i] & 0x38 != wa[i] & 0x38:
                    c['paper differs from clean (cells)'] += 1
            ov.fresh = True
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), set(kind_of), on_pc, stop)
    c['frames'] = frames
    if c['pictures with a figure cut'] * 100 > c['publications']:
        fail('overlay pixels over clear bitmap bits in over 1% of pictures', {'pictures': c['pictures with a figure cut']})
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


def unit_tests(patch, states, neg=True):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R and the clock the
    caller had; the MMU restored."""
    from skoolkit.simulator import Simulator
    c = Counter()
    p = patch.part
    kind_of = {p.plot: 'plot', p.copy: 'copy'}
    kind_of.update({a: 'cls' for a in p.cls})
    for pc, regs, mem in states:
        kind = kind_of[pc]
        patched = bytearray(mem)
        for a, o, new in patch.sites:
            patched[a:a + len(new)] = new
        for a, new in patch.live_table:
            patched[a:a + 2] = new
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    sp = rr[12]
                    if kind == 'plot':
                        ret = mem[sp] | mem[(sp + 1) & 65535] << 8
                        n = 0
                        while n == 0 or ref.registers[24] != ret or ref.registers[12] != (sp + 2) & 65535:
                            ref.opcodes[ref.memory[ref.registers[24]]]()
                            n += 1
                        stop, ssp = ret, (sp + 2) & 65535
                    elif kind == 'copy' and p.stop:
                        while ref.registers[24] != p.stop:
                            ref.opcodes[ref.memory[ref.registers[24]]]()
                        stop, ssp = p.stop, None
                    elif kind == 'copy':
                        ret = mem[sp] | mem[(sp + 1) & 65535] << 8
                        n = 0
                        while n == 0 or ref.registers[24] != ret or ref.registers[12] != (sp + 2) & 65535:
                            ref.opcodes[ref.memory[ref.registers[24]]]()
                            n += 1
                        stop, ssp = ret, (sp + 2) & 65535
                    else:
                        ref.opcodes[mem[pc]]()
                        stop, ssp = ref.registers[24], None
                    st = State(patch)
                    got, v, model = run_hook(patch, st, patched, rr, stop, ssp, speed=speed)
                    if any((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    if model.nr[7] != speed:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x50] != 255:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def mutate(name, old, new):
        b = copy.deepcopy(patch)
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.find(old)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new)] = new
        b._banks()
        out[name] = b
    # R off by one at the plot's exit: delta -22 -> -21
    mutate('R off by one', bytes((0x3E, 0x100 - 22, 0xCD)), bytes((0x3E, 0x100 - 21)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('x off by one column', bytes((0xC6, patch.part.xoff, 0xFE, 0x20)), bytes((0xC6, patch.part.xoff + 1, 0xFE, 0x20)))
    mutate('wrong ink', bytes.fromhex('E607CB71'), bytes.fromhex('E603CB71'))
    mutate('MMU slot 0 left mapped', bytes.fromhex('ED9150FFC94FE607'), bytes.fromhex('00000000C94FE607'))
    mutate('stale figures never cleared', bytes.fromhex('3A373EB7C8AF'), bytes.fromhex('3A373EB7C9AF'))
    mutate('overlay never published', bytes.fromhex('ED916980'), bytes.fromhex('ED916900'))
    mutate('overlay not hidden', bytes.fromhex('ED916900') + bytes((0x3E,)), bytes.fromhex('ED916980') + bytes((0x3E,)))
    mutate('mask punches nothing', bytes.fromhex('CB10300172'), bytes.fromhex('CB10300100'))
    if patch.colours:
        mutate('colours: rows do not advance', bytes.fromhex('EDB02A5C3EED5B623E19'), bytes.fromhex('EDB02A5C3EED5B623E00'))
        mutate('colours: clipped rows not skipped', bytes.fromhex('ED5B623E19225C3E'), bytes.fromhex('ED5B623E00225C3E'))
        mutate('colours: pad ignored', bytes.fromhex('1104001922'), bytes.fromhex('1100001922'))
    if patch.part.n == 1:
        b = copy.deepcopy(patch)
        b.live_table = [(a, zt.w16(patch.part.work_attr + 30 * r)) for r, (a, new) in enumerate(patch.live_table)]
        out['clash left: work attributes shown'] = b
    else:
        mutate('clash left: work attributes shown', b'\x21' + zt.w16(patch.part.clean_attr), b'\x21' + zt.w16(patch.part.work_attr))
    return out


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched snapshot, bar the tail."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, patch.slot1, True)[0])
    tail = zt.choose_tail_addr(s, size, patch.tail_addr, True)[0]
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
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def auto(a, z80, name, out, say):
    """nexclash.py auto: the overlay build, its boot check, and with --rzx the replay proof and the ABI cases."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    patch = Patch(z80)
    say('Game      : Phantis / Game Over 2 part %d (Dinamic, 48K)' % patch.part.n)
    say('Engine    : phantis; original bitmap and clean attributes on the ULA, figures on a double-buffered Layer 2; original pace')
    nex = out / (name + '_sprites.nex')
    zt.convert(str(z80), str(nex), patch=patch, quiet=True, keep_printer_buffer=True)
    bad = boot_check(nex, z80, Patch(z80))
    ok = not bad
    say('Plain     : not built')
    say('Sprites   : %s' % nex.name)
    say('Boot      : %s' % ('simulated, OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    states = []
    for path in list(getattr(a, 'rzx', None) or []):
        c, ex, got = verify(Patch(z80), path, stop=getattr(a, 'quick', None), collect=1)
        states += got
        fail = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fail
        say('Verify    : %s %d frames, %d hooks: %s' % (Path(path).name, c['frames'], c['hooks'], 'IDENTICAL' if not fail else str(fail)))
    if states:
        u = unit_tests(Patch(z80), states)
        ok = ok and not [k for k in u if k.endswith('!')]
        say('Unit      : %s' % dict(u))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
