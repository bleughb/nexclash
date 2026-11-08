"""Game Over (Dinamic / Imagine, 1987, 128K, both worlds): clash removal by a Layer 2 figure overlay.

The ULA bitmap stays the original's byte for byte; the attributes shown come from the clean buffer;
figures' ink goes on a double-buffered Layer 2 in plot order. See asm/game_over_hooks.asm.
"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib, json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/game_over.json'
SOURCE_MD5 = 'e1c2ff3cfbd4f6f5a84034d57b666acf'
CMP = tuple(hooklib.CMP_R)
IMAGE_OFFSET = 0x5C6            # stored code image: bank offset = address - 0x8000 + this
W1, W2 = 1, 2
# site: (address, original CALL/JP target, hook symbol, kind). W1 lives in bank 2 and image bank 4, W2 in image bank 6.
CALLS = {W1: {0xB381: (0xB4EF, 'h_plot1', 'plot'), 0x962B: (0xAF4B, 'h_rest1', 'rest'), 0x966C: (0xAF4B, 'h_copy1', 'copy'),
              0x9FD3: (0xAF06, 'h_cell', 'cell'), 0xA49B: (0xAF06, 'h_cell', 'cell')},
         W2: {0xB3A9: (0xB517, 'h_plot2', 'plot'), 0x9306: (0xAF73, 'h_rest2', 'rest'), 0x9334: (0xAF73, 'h_copy2', 'copy')}}
ATTR_OPERAND = {W1: 0x964E, W2: 0x9329}
CLS = 0xBA63
IMAGE_BANK = {W1: 4, W2: 6}
SIGNATURE = {0xB381: 'CDEFB4', 0x966C: 'CD4BAF', 0x964D: '21C079', 0xBA63: '3A8F5C'}
DECISIONS = {'figures': 'original bitmap on the ULA; figure ink in its own colour on Layer 2, in plot order',
             'scenery': 'keeps its own attributes', 'pace': 'original; hlib_pace K windows', 'outline': 'none',
             'enhanced': 'waiting for the mock-up'}


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_game_over(snap):
    if not getattr(snap, 'is128', False) and getattr(snap, 'machine', '') != '128K':
        return False
    try:
        banks = snap.banks
        return all(bytes(banks[2][a - 0x8000:a - 0x8000 + len(bytes.fromhex(v))]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (AttributeError, KeyError, TypeError, IndexError):
        return False


class Patch:
    name = 'Game Over 128K: clash removed by a Layer 2 figure overlay'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000

    def __init__(self, source=None, enabled=True):
        self.source = str(source) if source else None
        self.enabled = enabled
        h = load_profile()['hooks']
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
        self.ram[self.syms['V_BACK'] - 0x2000] = 16
        self.ram[self.syms['V_RECT'] - 0x2000:self.syms['V_RECT'] - 0x2000 + 2] = (0x3A00).to_bytes(2, 'little')
        self.sites = []
        self.world_sites = {W1: [], W2: []}
        self.site_info = {}
        if enabled:
            for world in (W1, W2):
                for a, (target, sym, kind) in CALLS[world].items():
                    self.world_sites[world].append((a, b'\xcd' + zt.w16(target), b'\xcd' + zt.w16(self.syms[sym])))
                    self.site_info[(world, a)] = (target, sym, kind)
                a = ATTR_OPERAND[world]
                self.world_sites[world].append((a, b'\xc0\x79', b'\xe0\x6a'))
            self.cls_site = (CLS, b'\x3a\x8f\x5c', b'\xc3' + zt.w16(self.syms['h_cls']))
            self.sites = self.world_sites[W1] + [self.cls_site]
        self._banks()

    def _banks(self):
        # Hidden ROM (page 25): tiny entry and return veneers only. Code and writable state: page 24.
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_plot1', 'h_plot2', 'h_rest1', 'h_rest2', 'h_copy1', 'h_copy2', 'h_cell', 'h_cls'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}

    def apply(self, snap):
        if not is_game_over(snap):
            raise ValueError('Not the supported Game Over 128K release (MD5 %s)' % SOURCE_MD5)
        banks = {i: bytearray(snap.banks[i]) for i in range(8)}
        for a, old, new in self.world_sites[W1] + [self.cls_site] if self.enabled else []:
            at = a - 0x8000
            if bytes(banks[2][at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[2][at:at + len(new)] = new
        if self.enabled:
            for world in (W1, W2):
                b = banks[IMAGE_BANK[world]]
                for a, old, new in self.world_sites[world]:
                    at = a - 0x8000 + IMAGE_OFFSET
                    if bytes(b[at:at + len(old)]) != old:
                        raise ValueError('Original bytes differ in world %d image at %04X' % (world, a))
                    b[at:at + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in range(8))


def build(source, destination, enabled=True):
    p = Patch(source, enabled)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


class View:
    """64K view of the game RAM + the Next pages the hook can map, per the model's MMU."""
    def __init__(self, mem, patch, page, pages):
        self.mem = bytearray(mem)
        self.patch, self.page, self.pages = patch, page, pages
        self.model = None
        self.world_patched = {}

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
    """What persists between hooks: the hook page, the L2 pages, the NextRegs that matter."""
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.pages = {p: bytearray(b'\xff' * 8192) for p in list(range(32, 36)) + list(range(38, 42))}
        self.nr = {0x12: 16, 0x69: 0, 0x17: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'game-over-hook')
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
    """The expected picture, by an independent reading of the game's own plot state."""
    def __init__(self):
        self.back = {}          # (x, y) -> colour index, sets 0..15 or 'paper marker' 254; absent = transparent
        self.front = {}
        self.fresh = False
        self.paper = set()

    def _clear_if_new(self):
        if self.fresh:
            self.back = {}
            self.paper = set()
            self.fresh = False

    def plot(self, mem, flag_addr):
        self._clear_if_new()
        blk = 0xB342 if flag_addr == 0xB4A6 else 0xB31A
        row0, rows, col, cols, k = mem[blk], mem[blk + 1], mem[blk + 2], mem[blk + 3], mem[blk + 4]
        if not rows:
            return
        w = mem[blk - 5]
        n = w // 2
        src = mem[0xB736] | mem[0xB737] << 8
        shift = mem[0xB735] & 1
        paint = mem[flag_addr] != 0xC9
        attr = mem[0x5C8F]
        ink = (attr & 7) | (8 if attr & 0x40 else 0)
        for r in range(rows):
            g = list(mem[src + r * w + i] for i in range(n))
            m = list(mem[src + r * w + n + i] for i in range(n))
            if shift:
                gg = [0] * (n + 1)
                mm = [0] * (n + 1)
                prev = 0
                for i in range(n):
                    gg[i] = (prev << 4 | g[i] >> 4) & 255
                    prev = g[i] & 15
                gg[n] = (prev << 4) & 255
                prev = 15
                for i in range(n):
                    mm[i] = (prev << 4 | m[i] >> 4) & 255
                    prev = m[i] & 15
                mm[n] = (prev << 4 | 15) & 255
                g, m = gg, mm
            y = row0 + r + 8
            for c in range(cols):
                gb, mb = g[k + c], m[k + c]
                x0 = (col + 1 + c) * 8
                for b in range(8):
                    xy = (x0 + b, y)
                    if gb & (128 >> b):
                        if paint:
                            self.back[xy] = ink
                        else:
                            self.back.pop(xy, None)
                    elif not mb & (128 >> b):
                        if paint:
                            self.back[xy] = 254
                        else:
                            self.back.pop(xy, None)

    def cells(self, mem):
        self._clear_if_new()
        p = mem[0xB736] | mem[0xB737] << 8
        h, w = mem[p], mem[p + 1]
        row, col = mem[0xB734], mem[0xB735]
        for r in range(h):
            for c in range(w):
                a = mem[p + 2 + r * w + c]
                bright = 8 if a & 0x40 else 0
                ink, paper = (a & 7) | bright, ((a >> 3) & 7) | bright
                for yy in range(8):
                    for xx in range(8):
                        xy = ((col + c) * 8 + xx, (row + r) * 8 + 8 + yy)
                        v = self.back.get(xy)
                        if v is None:
                            continue
                        if v == 254:
                            self.paper.add(xy)
                            self.back[xy] = paper
                        else:
                            self.back[xy] = ink


def _flat(sim):
    m = sim.memory
    return bytes(16384) + bytes(m.memory[1]) + bytes(m.memory[2]) + bytes(m.memory[3])


def world_of(mem):
    for w in (W1, W2):
        if mem[0xB381 if w == W1 else 0xB3A9:(0xB381 if w == W1 else 0xB3A9) + 3] == (b'\xcd\xef\xb4' if w == W1 else b'\xcd\x17\xb5'):
            return w
    return None


def verify(patch, rzx_path, stop=None, collect=0, progress=None, compare_every=1):
    """Replay the original; at every changed CALL run the hook on a copy of the state and compare
    with the original's run to its return (or the body entry): every register with R, all 48K RAM
    except the attributes the copy shows, B740 and the dead stack the original's call chain wrote.
    The Layer 2 picture is compared with an independent model at every publication."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    ov = Overlay()
    fronts = {}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    pcs = {a for w in (W1, W2) for a in CALLS[w]} | {CLS}

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        w = world_of(mem)
        info = patch.site_info.get((w, pc)) if w else None
        if pc == CLS:
            if mem[CLS:CLS + 3] != b'\x3a\x8f\x5c':
                fail('original changed CLS site', {})
            patched = bytearray(mem)
            for a, old, new in patch.world_sites[w or W1] + [patch.cls_site]:
                patched[a:a + len(new)] = new
            ref = simpool.machine(Simulator, list(mem), regs, 'go-ref')
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched, regs, 0xBA66)
            for i in CMP:
                if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                    fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i]})
            if st.nr.get(0x69) != 0:
                fail('overlay not hidden at CLS', {})
            c['cls hooks'] += 1
            c['R comparisons'] += 1
            return
        if not info:
            return
        target, sym, kind = info
        call = bytes((0xCD, target & 255, target >> 8))
        if mem[pc:pc + 3] != call:
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc and x[3] == w) < collect:
            states.append((pc, regs, mem, w))
        patched = bytearray(mem)
        for a, old, new in patch.world_sites[w] + [patch.cls_site]:
            patched[a:a + len(new)] = new
        if kind == 'copy' and not getattr(patch, 'attr_broken', False):
            patched[0xB740:0xB742] = b'\xe0\x6a'
        ref = simpool.machine(Simulator, list(mem), regs, 'go-ref')
        ret = (pc + 3) & 0xFFFF
        if kind == 'cell':
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched, regs, target)
            ov.cells(mem)
        else:
            sp = regs[12]
            n = 0
            R = ref.registers
            while n == 0 or R[24] != ret or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            if kind == 'plot':
                ov.plot(mem, 0xB47E if w == W1 else 0xB4A6)
            got, v, model = run_hook(patch, st, patched, regs, ret, sp)
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.world_sites[w] + [patch.cls_site]:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        # The stack below SP: the original's call chain wrote it, the hook's ran on its own stack.
        sp = regs[12]
        for a in range(sp - 32, sp):
            expected[a - 0x4000] = actual[a - 0x4000]
        if kind == 'copy':
            expected[0xB740 - 0x4000:0xB742 - 0x4000] = b'\xe0\x6a'
            # Attributes shown: the clean buffer's, every byte.
            want = mem[0x6AE0:0x6AE0 + 448]
            shown = bytes(actual[0x5820 - 0x4000:0x5820 - 0x4000 + 448])
            if want != shown:
                fail('copy attributes are not the clean buffer', {'pc': hex(pc)})
            expected[0x5820 - 0x4000:0x5820 - 0x4000 + 448] = shown
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255:
            fail('MMU not restored', {'pc': hex(pc)})
        if model.nr[7] != 0:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7]})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        if kind == 'rest':
            ov.fresh = True  # a restore wipes the work buffer
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if kind == 'copy':
            c['publications'] += 1
            # Front buffer against the independent model, and against the bitmap the copy wrote.
            front = st.nr[0x12]
            work = v.mem
            if st.nr[0x69] != 0x80:
                fail('overlay not on after publish', {})
            lit = 0
            picture = {}
            for y in range(8, 120):
                page = st.pages[front * 2 + (y >> 5)]
                row = (y & 31) << 8
                seg = page[row + 8:row + 248]
                if seg.count(255) == 240:
                    continue
                for xb, val in enumerate(seg):
                    if val != 255 and val != 254:
                        picture[(xb + 8, y)] = val
            want = {} if ov.fresh else {xy: val for xy, val in ov.back.items() if val != 254}
            if picture != want:
                diff = [k for k in set(picture) | set(want) if picture.get(k) != want.get(k)]
                fail('overlay differs from the model', {'pc': hex(pc), 'count': len(diff), 'ex': sorted(diff)[:6]})
            c['overlay pixels compared'] += len(picture)
            # Every pixel lit on Layer 2 is a set bit of the bitmap the copy wrote (screen row, work row).
            shake = mem[0xBF20] if w == W1 else 0
            ref_mem = ref.memory
            for (x, y), val in picture.items():
                if not ov.fresh and (x, y) not in ov.paper and not ref_mem[0x6CA0 + (y - 8) * 30 + (x - 8) // 8] & (128 >> (x & 7)):
                    fail('overlay pixel over a clear bitmap bit', {'x': x, 'y': y, 'frame': pc})
                    break
            ov.front = want
            ov.fresh = True
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), pcs, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


OPERANDS = (b'\xc0\x79',)


def SCREEN_SITES(patch):
    return [patch.cls_site]


def _patched_mem(patch, mem, w):
    out = bytearray(mem)
    for a, old, new in patch.world_sites[w] + SCREEN_SITES(patch):
        out[a:a + len(new)] = new
    return out


def unit_tests(patch, states, neg=True):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R and the clock the
    caller had; the MMU restored. The negative R control is in negative_patches, run by replay."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem, w in states:
        target, sym, kind = patch.site_info[(w, pc)]
        ret = (pc + 3) & 0xFFFF
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    if kind in ('cell', 'show'):
                        ref.opcodes[mem[pc]]()
                        stop, sp = target, None
                    else:
                        sp = rr[12]
                        n = 0
                        while n == 0 or ref.registers[24] != ret or ref.registers[12] != sp:
                            ref.opcodes[ref.memory[ref.registers[24]]]()
                            n += 1
                        stop = ret
                    st = State(patch)
                    got, v, model = run_hook(patch, st, _patched_mem(patch, mem, w), rr, stop, sp, speed=speed)
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

    def mutate(name, old, new, count=0):
        b = copy.deepcopy(patch)
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.find(old) if not count else list(_finds(code, old))[count]
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new)] = new
        b._banks()
        out[name] = b
    mutate('R off by one', bytes((0x3E, 0x100 - 21, 0xCD)), bytes((0x3E, 0x100 - 20)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('x off by one column', bytes.fromhex('FD7E023C'), bytes.fromhex('FD7E0200'))
    mutate('wrong ink', bytes.fromhex('E607CB70'), bytes.fromhex('E603CB70'))
    mutate('MMU slot 0 left mapped', bytes.fromhex('ED9150FFDDE1C9'), bytes.fromhex('00000000DDE1C9'))
    mutate('stale figures never cleared', bytes.fromhex('3A373EB7C8AF'), bytes.fromhex('3A373EB7C9AF'))
    mutate('overlay never published', bytes.fromhex('ED926900') if False else bytes.fromhex('ED916980'), bytes.fromhex('ED916900'))
    mutate('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('ED916980'))
    b = copy.deepcopy(patch)
    for w in (W1, W2):
        b.world_sites[w] = [t if not (t[1][:2] in OPERANDS) else (t[0], t[1], t[1]) for t in b.world_sites[w]]
    b.attr_broken = True
    out['clash left: work attributes shown'] = b
    return out


def _finds(code, old):
    i = code.find(old)
    while i >= 0:
        yield i
        i = code.find(old, i + 1)


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}
