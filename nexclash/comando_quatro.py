"""Comando Quatro (Zigurat / GameSoft, 1989, 48K): clash removal by a Layer 2 figure overlay.

The ULA bitmap stays the original's byte for byte; the attributes shown come from a private copy taken before
each pass's plots; figures' ink goes on a double-buffered Layer 2 in plot order. See asm/comando_quatro_hooks.asm.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/comando_quatro.json'
SOURCE_MD5 = '47ff99afedc9f0af0030b63d1fa4d098'
CMP = tuple(hooklib.CMP_R)
# site: (address, original bytes' opcode, original target, hook symbol, kind)
SITES = {0xB602: (0xCD, 0xB663, 'h_plot', 'plot'), 0xB657: (0xCD, 0xEB0A, 'h_copy', 'copy'), 0xB65E: (0xC4, 0xB830, 'h_rest', 'rest'),
         0xC761: (0xCD, 0xEB0A, 'h_wcopy', 'wcopy'), 0xDD1C: (0xCD, 0xEB0A, 'h_dcopy', 'dcopy'),
         0xC554: (0xCD, 0xB549, 'h_rend', 'rend'), 0xC7D0: (0xCD, 0xB549, 'h_rend', 'rend'), 0xC748: (0xCD, 0xB54C, 'h_rend4', 'rend'),
         0xC775: (0xCD, 0xB177, 'h_wrow', 'wrow'), 0xC786: (0xCD, 0xB177, 'h_wrow', 'wrow')}
CLS = 0xB153
# The game reads Kempston at port 0xDF (a real interface decodes A5 only); the Next answers at 0x1F. One operand.
KEMPSTON_SITE = (0xB253, b'\xdf', b'\x1f')
SIGNATURE = {0xB602: 'CD63B6', 0xB657: 'CD0AEB', 0xB65E: 'C430B8', 0xC554: 'CD49B5', 0xB153: '210058'}
ATTRS, N_ATTRS, PIXELS = 0xFCF0, 392, 0xF0B0
ROW0, COL0 = 40, 2
# The cells the copy writes: (row in the window, first column, columns).
SHOWN = [(0, 2, 24), (1, 1, 26)] + [(r, 0, 28) for r in range(2, 12)] + [(12, 1, 26), (13, 2, 24)]
DECISIONS = {'figures': 'original bitmap on the ULA; figure ink in the colour the game paints, on Layer 2, in plot order',
             'scenery': 'keeps its own attributes', 'pace': 'original; hlib_pace K windows', 'outline': 'none',
             'enhanced': 'no source exists: potential rated only'}
PUBLISHER = 'Zigurat / GameSoft, 1989'
NEG_RECORDING, NEG_STOP = 'a1.rzx', 5000   # the broken builds and the ABI cases: this recording (else the first), these frames


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_comando_quatro(snap):
    banks = getattr(snap, 'banks', None)
    mem = bytes(16384) + banks[5] + banks[2] + banks[0] if banks is not None else bytes(snap.memory)
    try:
        return all(mem[a:a + len(v) // 2] == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (TypeError, IndexError):
        return False


def _bank(a):
    return (5, a - 0x4000) if a < 0x8000 else (2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000)


class Patch:
    name = 'Comando Quatro: clash removed by a Layer 2 figure overlay'
    uses_printer_buffer = False
    keep_printer_buffer = True
    hook_page_data = b''
    setup_call = 0xD000
    tail_addr = 0xB950          # variables the game writes before it reads (scan of three recordings; checked by rom_paths)

    def __init__(self, source=None):
        self.source = str(source) if source else None
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0:N_ATTRS] = bytes(N_ATTRS)
        self.ram[0x1A00:0x1C00] = bytes(512)
        self.ram[0x1E00:0x2000] = bytes(512)
        self.ram[self.syms['V_BACK'] - 0x2000] = 16
        self.ram[self.syms['V_RECT'] - 0x2000:self.syms['V_RECT'] - 0x2000 + 2] = (0x3A00).to_bytes(2, 'little')
        self.sites = [(a, bytes((op,)) + zt.w16(t), bytes((op,)) + zt.w16(self.syms[s])) for a, (op, t, s, k) in SITES.items()]
        self.cls_site = (CLS, bytes.fromhex('210058'), b'\xc3' + zt.w16(self.syms['h_cls']))
        self.sites.append(self.cls_site)
        self.sites.append(KEMPSTON_SITE)
        self._banks()

    def _banks(self):
        # Hidden ROM (page 25): tiny entry and return veneers only. Code and writable state: page 24.
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_plot', 'h_rest', 'h_copy', 'h_wcopy', 'h_dcopy', 'h_rend', 'h_rend4', 'h_wrow', 'h_cls'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}

    def apply(self, snap):
        if not is_comando_quatro(snap):
            raise ValueError('Not the supported Comando Quatro release (MD5 %s)' % SOURCE_MD5)
        banks = {i: bytearray(snap.banks[i]) for i in snap.banks}
        for a, old, new in self.sites:
            b, at = _bank(a)
            if bytes(banks[b][at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[b][at:at + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in banks)


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
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
                return self.patch.page[a - 0x2000] if a >= 0x2000 else self.mem[a]
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
        super().__init__(sim, speed, line=line)
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
        self.pages = {p: bytearray(b'\xff' * 8192) for p in list(range(32, 38)) + list(range(38, 44))}
        self.nr = {0x12: 16, 0x69: 0, 0x17: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'comando-quatro-hook')
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
        self.back = {}          # (x, y) -> ink 0..15; absent = transparent
        self.front = {}
        self.fresh = False

    def plot(self, mem, ix):
        if self.fresh:
            self.back, self.fresh = {}, False
        flags = mem[ix + 5]
        paint = not (flags & 0x10 and not mem[0xB9AF])
        c = flags & 0x47
        if not flags & 0x20 and mem[ix + 9] & 0x80:
            c = 1
        ink = (c & 7) | (8 if c & 0x40 else 0)
        w0, rows, cols, y0, col, skip = mem[ix + 3], mem[0xB9E8], mem[0xB9E6], mem[0xB9E7], mem[0xB9E5], mem[0xB9E9]
        s = mem[0xB9E0] & 7
        gp, mp = mem[0xB673] | mem[0xB674] << 8, mem[0xB681] | mem[0xB682] << 8
        for r in range(rows):
            g = int.from_bytes(bytes(mem[gp + r * w0 + i] for i in range(w0)) + b'\x00', 'big') >> s
            m = int.from_bytes(b'\xff' + bytes(mem[mp + r * w0 + i] for i in range(w0)) + b'\xff', 'big') >> s
            g = g.to_bytes(w0 + 1, 'big')
            m = (m & ((1 << 8 * (w0 + 1)) - 1)).to_bytes(w0 + 1, 'big')
            for c_ in range(cols):
                gb, mb = g[skip + c_], m[skip + c_]
                x0 = (col - 0x72 + COL0 + c_) * 8
                for b in range(8):
                    xy = (x0 + b, y0 + r + ROW0)
                    if gb & (128 >> b):
                        if paint:
                            self.back[xy] = ink
                        else:
                            self.back.pop(xy, None)
                    elif not mb & (128 >> b):
                        self.back.pop(xy, None)

    def publish(self):
        if self.fresh:
            self.back = {}
        self.front = self.back
        self.back = {}
        self.fresh = False

    def wrow(self, y):
        self.front = {k: v for k, v in self.front.items() if k[1] != y}


def _flat(sim):
    return bytes(sim.memory)


def _picture(st, bank):
    out = {}
    for y in range(ROW0, ROW0 + 112):
        page = st.pages[bank * 2 + (y >> 5)]
        row = (y & 31) << 8
        seg = page[row:row + 256]
        if seg.count(255) == 256:
            continue
        for x, val in enumerate(seg):
            if val not in (254, 255):
                out[(x, y)] = val
    return out


def verify(patch, rzx_path, stop=None, collect=0, progress=None, keep=None):
    """Replay the original; at every changed CALL run the hook on a copy of the state and compare with the original's
    run to its return (or the body entry): every register with R, all 48K RAM except the attribute cells the copy shows
    and 32 bytes of dead stack the original's call chain wrote. The Layer 2 picture is compared with an independent
    model at every publication and wipe copy; attributes shown against the attributes at the pass's start, and those
    against what the game's own restore brings back."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    ov = Overlay()
    clean = [None]
    site_bytes = patch.sites

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    pcs = set(SITES) | {CLS}

    def patched_mem(mem):
        p = bytearray(mem)
        for a, old, new in site_bytes:
            p[a:a + len(new)] = new
        return p

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        if pc == CLS:
            ref = simpool.machine(Simulator, list(mem), regs, 'cq-ref')
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched_mem(mem), regs, 0xB156)
            for i in CMP:
                if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                    fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i]})
            if st.nr.get(0x69) != 0:
                fail('overlay not hidden', {})
            c['cls hooks'] += 1
            c['R comparisons'] += 1
            return
        op, target, sym, kind = SITES[pc]
        if mem[pc:pc + 3] != bytes((op, target & 255, target >> 8)):
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        ref = simpool.machine(Simulator, list(mem), regs, 'cq-ref')
        ret = (pc + 3) & 0xFFFF
        if kind in ('rend', 'wrow'):
            ref.opcodes[mem[pc]]()
            if kind == 'rend':
                clean[0] = mem[ATTRS:ATTRS + N_ATTRS]
            else:
                ov.wrow(ROW0 + ((regs[6] << 8 | regs[7]) - PIXELS) // 28)
            got, v, model = run_hook(patch, st, patched_mem(mem), regs, target)
        else:
            sp = regs[12]
            n = 0
            R = ref.registers
            while n == 0 or R[24] != ret or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            if kind == 'plot':
                ov.plot(mem, regs[8] << 8 | regs[9])
            got, v, model = run_hook(patch, st, patched_mem(mem), regs, ret, sp)
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in site_bytes:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        if kind not in ('rend', 'wrow'):
            sp = regs[12]
            for a in range(sp - 32, sp):
                expected[a - 0x4000] = actual[a - 0x4000]
        if kind in ('copy', 'wcopy') and mem[0xB9B3] and clean[0] is not None:
            for row, col0, n_ in SHOWN:
                d = 0x5800 + (row + 5) * 32 + col0 + COL0 - 0x4000
                want = clean[0][row * 28 + col0:row * 28 + col0 + n_]
                shown = bytes(actual[d:d + n_])
                if want != shown:
                    fail('copy attributes are not the clean copy', {'pc': hex(pc), 'row': row})
                expected[d:d + n_] = shown
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
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
        if kind == 'rest' and mem[0xB9BF] and clean[0] is not None:
            if bytes(ref.memory[ATTRS:ATTRS + N_ATTRS]) != clean[0]:
                fail('the game\'s restore disagrees with the clean copy', {'pc': hex(pc)})
            c['restores against the clean copy'] += 1
        if kind == 'dcopy':
            if st.nr.get(0x69) != 0:
                fail('overlay not hidden', {'pc': hex(pc)})
            ov.front = {}
        if kind in ('copy', 'wcopy'):
            if kind == 'copy':
                c['publications'] += 1
                ov.publish()
                if st.nr[0x69] != 0x80:
                    fail('overlay not on after publish', {})
            if st.nr.get(0x69):
                picture = _picture(st, st.nr[0x12])
                if picture != ov.front:
                    diff = [k for k in set(picture) | set(ov.front) if picture.get(k) != ov.front.get(k)]
                    fail('overlay differs from the model', {'pc': hex(pc), 'count': len(diff), 'ex': sorted(diff, key=lambda k: (k[1], k[0]))[:40], 'in_picture': sum(k in picture for k in diff)})
                c['overlay pixels compared'] += len(picture)
                bm = ref.memory
                for (x, y), val in picture.items():
                    cx = (x >> 3) - COL0
                    if not bm[PIXELS + (y - ROW0) * 28 + cx] & (128 >> (x & 7)):
                        fail('overlay pixel over a clear bitmap bit', {'x': x, 'y': y, 'pc': hex(pc)})
                        break
            if kind == 'copy':
                ov.fresh = False
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), pcs, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


def unit_tests(patch, states, neg=True):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R and the clock the
    caller had; the MMU restored."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        op, target, sym, kind = SITES[pc]
        ret = (pc + 3) & 0xFFFF
        patched = bytearray(mem)
        for a, old, new in patch.sites:
            patched[a:a + len(new)] = new
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    if kind in ('rend', 'wrow'):
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
                    st.page[0:N_ATTRS] = mem[ATTRS:ATTRS + N_ATTRS]     # the clean copy the pass's hook would have taken
                    got, v, model = run_hook(patch, st, patched, rr, stop, sp, speed=speed)
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
    mutate('R off by one', bytes((0x3E, 0x100 - 21, 0xCD)), bytes((0x3E, 0x100 - 20)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('x off by one column', bytes.fromhex('D670'), bytes.fromhex('D66F'))
    mutate('wrong ink', bytes.fromhex('E607CB70'), bytes.fromhex('E603CB70'))
    mutate('MMU slot 0 left mapped', bytes.fromhex('ED9150FFDDE1C9'), bytes.fromhex('00000000DDE1C9'))
    mutate('stale figures never cleared', bytes.fromhex('3A373EB7C8AF'), bytes.fromhex('3A373EB7C9AF'))
    mutate('overlay never published', bytes.fromhex('ED916980'), bytes.fromhex('ED916900'))
    mutate('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('00000000'))
    mutate('clash left: work attributes shown', bytes.fromhex('21002011F0FC'), bytes.fromhex('21002211F0FC'))
    mutate('work attributes not put back', bytes.fromhex('21002211F0FC01880 1EDB0'.replace(' ', '')), bytes.fromhex('21002211F0FC018801 0000'.replace(' ', '')))
    mutate('wipe row left on the overlay', bytes.fromhex('3A363EEE03'), bytes.fromhex('3A363E0000'))
    mutate('shadow never taken', bytes.fromhex('EDB03E08'), bytes.fromhex('00003E08'))
    return out


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}


# ---- nexclash.py auto: the published builds, boot-checked; with recordings the replay proof ---------------------------
import hashlib

LOAD_SCREEN = 'comando_quatro_loading.scr'   # the plain .tap's 6,912-byte screen block, beside the snapshot: game data, never in this repo
LOAD_MD5 = 'd5f1b3bd3e27d3920f8d253883fc6b26'
STOPS = {'a2.rzx': 22000}                 # frames replayed where the review run stopped short of a recording's end
# Each tested in the simulator, 3 seeds x 12,000 frames (games/comando_quatro.md "Cheats"); the archive's two, as they are.
TRAINERS = '''NInfinite Energy
Z 8 51483 201 0
NInfinite Time
Z 8 50693 0 0
Y
'''


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2), as the published .nxc."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


def _beside(z80, file, md5, what):
    """A private input beside the snapshot -> its path, or None. A different file there is refused."""
    path = Path(z80).resolve().parent / file
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not %s (MD5 %s)' % (file, what, md5))
    return path


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched
    snapshot, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites). -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, patch.slot1, True)[0])
    tail = patch.tail_addr
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
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def _replay(z80, rzx, stop, collect):
    """One recording's replay (a process of its own) -> (counts, examples, states)."""
    got = verify(Patch(z80), rzx, stop=stop, collect=collect)
    return got if collect else (got[0], got[1], [])


def _negative(z80, name, rzx, stop):
    """One deliberately broken build's replay (a process of its own): -> (name, its failure keys)."""
    try:
        return name, sorted(run_negative(negative_patches(Patch(z80))[name], rzx, stop))
    except Exception as e:                  # noqa: BLE001 - a broken hook that runs off into data is caught too
        return name, ['exception ' + type(e).__name__]


def auto(a, z80, name, out, say):
    """nexclash.py auto: the clash-fix build and, with the loading screen beside the snapshot, the published build
    (the screen in the .nex); each boot-checked with and without NEXLOAD. With --rzx the replay proof of each recording,
    the ABI cases and the broken builds. The pace, soak, flicker, beam and real loader proofs are the review run's
    (games/comando_quatro.md "Evidence")."""
    import concurrent.futures, os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'pok', None):
        trainers = out / (name + '_verified.pok')
        trainers.write_text(TRAINERS)
        a.pok = str(trainers)
    say('Game      : Comando Quatro (Zigurat / GameSoft, 1989, 48K)')
    say('Engine    : comando_quatro; clash removed: figures\' ink on a double-buffered Layer 2 over the original bitmap, '
        'scenery in its own attributes; Kempston at 0x1F; original pace')
    ok = True
    screen = _beside(z80, LOAD_SCREEN, LOAD_MD5, 'the original loading screen')
    if screen is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    nex = out / (name + '_sprites.nex')
    zt.convert(str(z80), str(nex), patch=Patch(z80), quiet=True)
    nexes = [('Sprites', nex)]
    if screen is not None:
        loading = out / (name + '_sprites_loading.nex')
        loading.write_bytes(loading_nex(nex.read_bytes(), screen.read_bytes()))
        nexes.append(('Spr+scr', loading))
    for lab, path in nexes:
        bad = boot_check(path, z80, Patch(z80))
        ok = ok and not bad
        say('%-10s: %s  %s' % (lab, path.name, hashlib.md5(path.read_bytes()).hexdigest()))
        say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM; converter loader and NEXLOAD)'
                                if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    if rzxs:
        quick = getattr(a, 'quick', None)
        stops = [min(x for x in (quick, STOPS.get(Path(r).name)) if x) if (quick or STOPS.get(Path(r).name)) else None
                 for r in rzxs]
        neg_rzx = next((r for r in rzxs if Path(r).name == NEG_RECORDING), rzxs[0])
        collect = [1 if r == neg_rzx else 0 for r in rzxs]
        with concurrent.futures.ProcessPoolExecutor(min(len(rzxs), os.cpu_count() or 1)) as pool:
            done = list(pool.map(_replay, [z80] * len(rzxs), rzxs, stops, collect))
        states = []
        for path, stop, (c, ex, got) in zip(rzxs, stops, done):
            states += got
            fail = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fail
            say('Verify    : %s %d frames%s, %d hooks, %d R comparisons, %d Layer 2 pictures, %d pixels, %d restores '
                'against the clean copy: %s' % (Path(path).name, c['frames'], ' (stop %d)' % stop if stop else '',
                                                c['hooks'], c['R comparisons'], c['publications'],
                                                c['overlay pixels compared'], c['restores against the clean copy'],
                                                'IDENTICAL' if not fail else str(fail)))
            for k, v in ex.items():
                say('            %s: %s' % (k, v))
        counts = unit_tests(Patch(z80), states)
        fail = {k: v for k, v in counts.items() if k.endswith('!')}
        ok = ok and not fail and bool(counts.get('ABI cases'))
        say('Unit      : %s (states of %s)' % (dict(counts), Path(neg_rzx).name))
        names = list(negative_patches(Patch(z80)))
        stop = min(x for x in (quick, NEG_STOP) if x)
        with concurrent.futures.ProcessPoolExecutor(min(len(names), os.cpu_count() or 1)) as pool:
            neg = list(pool.map(_negative, [z80] * len(names), names, [neg_rzx] * len(names), [stop] * len(names)))
        missed = [n for n, keys in neg if not keys]
        ok = ok and not missed
        say('Negatives : %d of %d broken builds caught (%s, %d frames)%s' % (
            len(neg) - len(missed), len(neg), Path(neg_rzx).name, stop, '; MISSED %s' % missed if missed else ''))
    else:
        say('Verify    : not requested; boot evidence only')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
