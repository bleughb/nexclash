"""Flying Shark (Graftgold / Firebird, 1987, 48K): a one-pixel outline on Layer 2.

The play area is monochrome by design: no colour clash to fix, and the ULA bitmap and attributes stay the original's, every
byte. Figures lost against the scenery get the standard outline, white, on a double-buffered Layer 2. See
asm/flying_shark_hooks.asm. The snapshot stops at the loader's PAUSE 0 with the game packed: every site is in the packed
stream, so the game unpacks with the hooks in place.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/flying_shark.json'
SOURCE_MD5 = 'c545645a8688f24428492937125fbfcd'
CMP = tuple(hooklib.CMP_R)
STREAM = 0x9E86                 # the loader's packed stream (word zero run, word literal run, ...)
DEST = 0x5B00
TAIL_ADDR = 0x7000              # a 16,005-byte zero run in the snapshot; the unpack writes over it
TABLE = 0xA000                  # the threaded plot steps' routine table
STEPS = {0x00: 0xAFC3, 0x02: 0xB121, 0x04: 0xB005, 0x06: 0xB12B, 0x08: 0xB072, 0x0A: 0xB13F, 0x0C: 0xB0B4, 0x0E: 0xB14A,
         0x10: 0xB3FE, 0x12: 0xB1BE, 0x14: 0xB452, 0x16: 0xB24A, 0x18: 0xB4AA, 0x1A: 0xB2DA, 0x1C: 0xB502, 0x1E: 0xB36A}
BLIT, PLOT, IDLE = 0xC772, 0xAC8D, 0xA0B0
CALLS = {0xA112: (BLIT, 'h_blit', 'blit'), 0x6A9A: (BLIT, 'h_blit', 'blit'), 0x64C4: (BLIT, 'h_blank', 'blank'),
         0xA124: (PLOT, 'h_plot', 'plot'), 0x6A97: (PLOT, 'h_plot', 'plot')}
IDLE_OLD = bytes.fromhex('F5E521')
IDLE_BODY = 0xA0B5
PLAY_X0, PLAY_X1 = 56, 199
Y_OFFSET = 24
REV = 0x9A00
INK, CLEAR = 15, 255
DECISIONS = {'figures': 'the original bitmap on the ULA, every byte; a white one-pixel outline on Layer 2 in plot order',
             'scenery': 'the original', 'pace': 'original; the blit and the plot run whole at 28 MHz in their own time',
             'outline': 'white, one pixel, none on 8-line plots (bullets)', 'enhanced': 'waiting for the owner'}


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def stream_map(ram):
    """{live address: stream address} of the literal bytes of the loader's stream; ram is 64K."""
    out = {}
    src, dst = STREAM, DEST
    while True:
        n = ram[src] | ram[src + 1] << 8
        src += 2
        dst += n
        n = ram[src] | ram[src + 1] << 8
        src += 2
        if not n:
            return out, dst, src
        for i in range(n):
            out[(dst + i) & 0xFFFF] = src + i
        src += n
        dst += n


def is_flying_shark(snap):
    try:
        ram = bytes(16384) + bytes(snap.ram(-1))
    except (AttributeError, TypeError):
        return False
    if len(ram) != 65536 or ram[0x9E3A:0x9E3E] != bytes.fromhex('F3210058'):
        return False
    try:
        where = stream_map(ram)[0]
        return all(ram[where[a + i]] == b for a, (t, _, _) in CALLS.items() for i, b in enumerate(b'\xcd' + zt.w16(t)))
    except (KeyError, IndexError):
        return False


class Patch:
    name = 'Flying Shark: a one-pixel outline on Layer 2'
    uses_printer_buffer = True
    hook_page_data = b''
    setup_call = 0xD000
    tail_addr = TAIL_ADDR

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
        self.ram[0x1400:0x1B00] = bytes(0x700)      # the grid, the captures, the rectangle lists
        self.ram[0x1B00:0x1C00] = bytes(256)        # stack and state
        self.ram[self.syms['V_BACK'] - 0x2000] = 16
        self.ram[self.syms['V_RECT'] - 0x2000:self.syms['V_RECT'] - 0x2000 + 2] = (0x3900).to_bytes(2, 'little')
        self.ram[self.syms['V_FREEP'] - 0x2000] = 48
        self.sites = []
        if enabled:
            for a, (target, sym, kind) in CALLS.items():
                self.sites.append((a, b'\xcd' + zt.w16(target), b'\xcd' + zt.w16(self.syms[sym])))
            self.sites.append((IDLE, IDLE_OLD, b'\xc3' + zt.w16(self.syms['h_idle'])))
            for idx, target in STEPS.items():
                self.sites.append((TABLE + idx, zt.w16(target), zt.w16(self.syms['cap_%02x' % idx])))
        self._banks()

    def _banks(self):
        # Hidden ROM (page 25): tiny entry and return veneers only; BASIC runs from the ROM before the game starts.
        # Code and writable state: page 24.
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_plot', 'h_blit', 'h_blank', 'h_idle'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        end = self.syms['veneers_end'] - 0x2800
        for i in range(end - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 9] = self.ram[at:at + 9]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}

    def apply(self, snap):
        ram = bytearray(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0]
        if snap.is128 or ram[0x9E3A:0x9E3E] != bytes.fromhex('F3210058'):
            raise ValueError('Not the supported Flying Shark release (MD5 %s)' % SOURCE_MD5)
        where = stream_map(ram)[0]
        for a, old, new in self.sites if self.enabled else []:
            for i, (o, n) in enumerate(zip(old, new)):
                if ram[where[a + i]] != o:
                    raise ValueError('Original bytes differ at %04X' % (a + i))
                ram[where[a + i]] = n
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[0x4000:0x8000]), bytes(ram[0x8000:0xC000]), bytes(ram[0xC000:])


def build(source, destination, enabled=True):
    p = Patch(source, enabled)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


DEF = (255, 255, 10, 11)


class Pages(dict):
    def __missing__(self, k):
        self[k] = bytearray(8192)
        return self[k]


class View:
    """64K view of the game RAM + the Next pages the hook can map, per the model's MMU."""
    def __init__(self, mem, patch, page, pages):
        self.mem = bytearray(mem)
        self.patch, self.page, self.pages = patch, page, pages
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        if a < 0x8000:
            nr = self.model.nr
            s = a >> 13
            m = nr.get(0x50 + s, DEF[s])
            if m != DEF[s]:
                if m == 24:
                    return self.page[a - 0x2000]
                return self.pages[m][a & 8191]
            if a < 0x4000:
                return self.patch.page[a - 0x2000] if a >= 0x2000 else self.mem[a]
        return self.mem[a]

    def __setitem__(self, a, v):
        if a < 0x8000:
            s = a >> 13
            m = self.model.nr.get(0x50 + s, DEF[s])
            if m != DEF[s]:
                if m == 24:
                    self.page[a - 0x2000] = v
                else:
                    self.pages[m][a & 8191] = v
                return
            if a < 0x4000:
                return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line, lines=312, t_line=224)
        self.nr.update({0x50 + i: p for i, p in enumerate((255, 255, 10, 11, 4, 5, 0, 1))})
        self.nr[1] = 0x32
        self.io = []
        self.speed0 = speed & 3
        self.io_clock_wrong = 0

    def write_port(self, regs, port, v, *args):
        if port in (0x243B, 0x253B) or port & 255 == 0x6B:
            return super().write_port(regs, port, v, *args)
        self.io.append((port, v))
        if self.nr[7] & 3 != self.speed0:
            self.io_clock_wrong += 1


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class State:
    """What persists between hooks: the hook page, the L2 pages, the NextRegs that matter."""
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.pages = Pages({p: bytearray(b'\xff' * 8192) for p in range(32, 44)})
        self.nr = {0x12: 16, 0x69: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=12000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'flying-shark-hook')
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


def shape(mem, plot):
    """A plot's pixels in cell terms, read from the game's own graphics by the step's own rules: {(column, line): (opaque, ink)}."""
    step, d, e, src, cols, h = plot
    out = {}
    xf, yf = bool(step & 4), bool(step & 8)
    first_stage = step < 0x10 and not step & 2
    rev = mem[REV:REV + 256]
    for c in range(cols):
        for l in range(h):
            data, mask = mem[src], mem[src + 1]
            src += 2
            if xf:
                m, ink, cc = mask, rev[data], cols - 1 - c
            else:
                m, ink, cc = rev[mask], data, c
            if first_stage:
                m = 255
            out[(cc, h - 1 - l if yf else l)] = ((~m & 255) | ink, ink)
    return out


class Overlay:
    """The expected picture, by an independent reading of the game's own plot state."""
    def __init__(self):
        self.pending = []
        self.mem = None

    def picture(self, mem):
        pic = {}
        plots = self.pending
        for i, plot in enumerate(plots):
            step, d, e, src, cols, h = plot
            if not (cols and h) or cols >= 5 or h >= 17 or h == 8:
                continue
            if step < 0x10 and not step & 2 and i + 1 < len(plots) and plots[i + 1][0] < 0x10 and plots[i + 1][0] & 2:
                continue                                # a first stage with its second to come: one figure
            solid = set()
            for (c, l), (o, _) in shape(mem, plot).items():
                for b in range(8):
                    if o & (128 >> b):
                        solid.add(((d - 0x88 + 7 + c) * 8 + b, (e + l - Y_OFFSET) & 255))
            for x, y in solid:
                for n in ((x - 1, y), (x + 1, y), (x, (y - 1) & 255), (x, (y + 1) & 255)):
                    if n not in solid:
                        pic[n] = INK
        ymax = 184 + (mem[0x9C00] & 7)              # the blit shows lines up to 183 + the fine scroll
        return {xy: v for xy, v in pic.items() if PLAY_X0 <= xy[0] <= PLAY_X1 and xy[1] < ymax}


def front_picture(st):
    pic = {}
    bank = st.nr[0x12]
    for y in range(192):
        page = st.pages[bank * 2 + (y >> 5)]
        row = (y & 31) << 8
        seg = page[row + PLAY_X0:row + PLAY_X1 + 1]
        if seg.count(CLEAR) == len(seg):
            continue
        for i, v in enumerate(seg):
            if v != CLEAR:
                pic[(PLAY_X0 + i, y)] = v
    return pic


class _Ports:
    """The original's port writes, to compare with the hook's: they are the game's beeper."""
    def __init__(self):
        self.io = []

    def write_port(self, regs, port, v, *args):
        self.io.append((port, v))

    def read_port(self, regs, port):
        return 255


def _flat(sim):
    return bytes(sim.memory)


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original; at every changed call run the hook on a copy of the state and compare with the original's run
    to its return: every register with R, all 48K RAM but the return address on the dead stack. The Layer 2 picture is
    compared with an independent model at every publication, and the last figure's ink with the bitmap the blit wrote."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    ov = Overlay()
    plotted = [False]
    steps = set(STEPS.values())

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)

    def compare(pc, sym, ref, got, v, model, regs, ref_io):
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x52] != 10 or model.nr[0x53] != 11:
            fail('MMU not restored', {'pc': hex(pc), 'sym': sym})
        if model.nr[7] != 0:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7]})
        if model.io != ref_io:
            fail('game I/O differs', {'pc': hex(pc), 'orig': ref_io[:4], 'got': model.io[:4]})
        if model.io_clock_wrong:
            fail('beeper at the wrong clock', {'pc': hex(pc), 'writes': model.io_clock_wrong})
        c['port writes compared'] += len(ref_io)
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        c['hooks'] += 1

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        if regs[26]:
            fail('a hook with interrupts on', {'pc': hex(pc)})
        patched = bytearray(mem)
        for a, old, new in patch.sites:
            patched[a:a + len(new)] = new
        ref = simpool.machine(Simulator, list(mem), regs, 'fs-ref')
        if pc == IDLE:
            if mem[pc:pc + 3] != IDLE_OLD:
                fail('site bytes changed', {'pc': hex(pc)})
                return
            if collect and sum(1 for x in states if x[0] == pc) < collect:
                states.append((pc, regs, mem))
            n = 0
            while ref.registers[24] != IDLE_BODY:
                ref.opcodes[ref.memory[ref.registers[24]]]()
                n += 1
            got, v, model = run_hook(patch, st, patched, regs, IDLE_BODY)
            compare(pc, 'h_idle', ref, got, v, model, regs, [])
            if st.nr.get(0x69) != 0:
                fail('overlay not hidden', {})
            plotted[0] = False
            c['hooks idle'] += 1
            return
        target, sym, kind = CALLS[pc]
        if mem[pc:pc + 3] != b'\xcd' + zt.w16(target):
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        ret = (pc + 3) & 0xFFFF
        sp = regs[12]
        n = 0
        R = ref.registers
        plots = []
        ports = _Ports()
        ref.set_tracer(ports)
        while n == 0 or R[24] != ret or R[12] != sp:
            at = R[24]
            if kind == 'plot' and at in steps:
                m = ref.memory
                plots.append(((TABLE_BY[at]), m[0x9C14], m[0x9C13], m[0x9C15] | m[0x9C16] << 8, m[0x9C1A], m[0x9C1B]))
            ref.opcodes[ref.memory[at]]()
            n += 1
        got, v, model = run_hook(patch, st, patched, regs, ret, sp)
        compare(pc, sym, ref, got, v, model, regs, ports.io)
        c['hooks ' + kind] += 1
        if kind == 'plot':
            ov.pending = plots
            ov.mem = bytes(ref.memory)
            plotted[0] = True
            c['plots'] += len(plots)
            for p in plots:
                if p[4] >= 5:
                    fail('a plot wider than the grid', {'plot': p})
                if p[5] > 16:
                    fail('a plot taller than the grid', {'plot': p})
                if p[5] not in (8, 16):
                    c['height %d' % p[5]] += 1
        else:
            if kind == 'blank':
                plotted[0] = False
            if plotted[0]:
                c['publications'] += 1
                if st.nr.get(0x69) != 0x80:
                    fail('overlay not on after publish', {})
                pic = front_picture(st)
                want = ov.picture(ov.mem)
                if pic != want:
                    diff = [k for k in set(pic) | set(want) if pic.get(k) != want.get(k)]
                    fail('overlay differs from the model', {'pc': hex(pc), 'count': len(diff), 'ex': sorted(diff)[:6]})
                c['overlay pixels compared'] += len(pic)
                # the last figure's ink, wherever on the play area, is set in the bitmap the blit wrote
                if ov.pending:
                    plot = ov.pending[-1]
                    if plot[0] >= 0x10:
                        m = ref.memory
                        for (cc, l), (o, ink) in shape(ov.mem, plot).items():
                            if not ink:
                                continue
                            y = (plot[2] + l - Y_OFFSET) & 255
                            x = plot[1] - 0x88 + 7 + cc
                            if y < 184 + (ov.mem[0x9C00] & 7) and 7 <= x <= 24:
                                a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | x
                                if (m[a] & ink) != ink:
                                    # an XOR pixel of the figure may cut the ink: only opaque ink counts
                                    solid = ink & o & ~(mem_mask(ov.mem, plot, cc, l))
                                    if (m[a] & solid) != solid:
                                        fail('overlay away from the figure in the bitmap', {'plot': plot, 'x': x, 'y': y})
                                        break
                        c['bitmap checks'] += 1
            elif kind != 'blank' and st.nr.get(0x69) not in (0, None):
                fail('overlay on with nothing plotted', {'pc': hex(pc)})
            plotted[0] = False
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), set(CALLS) | {IDLE}, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


TABLE_BY = {v: k for k, v in STEPS.items()}


def mem_mask(mem, plot, cc, l):
    """The transparent bits of one byte of a plot (its mask's 1s), for the XOR-ink test."""
    step, d, e, src, cols, h = plot
    xf, yf = bool(step & 4), bool(step & 8)
    c = cols - 1 - cc if xf else cc
    ln = h - 1 - l if yf else l
    mask = mem[src + (c * h + ln) * 2 + 1]
    return mask if xf else mem[REV + mask]


def _patched_mem(patch, mem):
    out = bytearray(mem)
    for a, old, new in patch.sites:
        out[a:a + len(new)] = new
    return out


def unit_tests(patch, states, neg=True):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R and the clock the
    caller had; the MMU restored. The negative R control is in negative_patches, run by replay."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        idle = pc == IDLE
        ret = IDLE_BODY if idle else (pc + 3) & 0xFFFF
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    sp = None if idle else rr[12]
                    n = 0
                    while n == 0 or ref.registers[24] != ret or (sp is not None and ref.registers[12] != sp):
                        ref.opcodes[ref.memory[ref.registers[24]]]()
                        n += 1
                    st = State(patch)
                    got, v, model = run_hook(patch, st, _patched_mem(patch, mem), rr, ret, sp, speed=speed)
                    if any((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    if model.nr[7] != speed:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x50] != 255:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def _finds(code, old):
    i = code.find(old)
    while i >= 0:
        yield i
        i = code.find(old, i + 1)


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
    mutate('R off by one', bytes.fromhex('3EE8CD'), bytes.fromhex('3EE9'))
    mutate('veneer M1s miscounted', bytes.fromhex('8087' '4F') if False else bytes.fromhex('80814732C43B') if False else bytes.fromhex('87878787' '8081'), bytes.fromhex('87878787' '8000'))
    # the last speed restore in h_plot: the first HLIB_SPEED_OUT after its R calls
    b = copy.deepcopy(patch)
    code = bytes(b.ram[0x800:0x800 + len(b.code)])
    all_out = list(_finds(code, bytes.fromhex('3AC03BED9207')))
    i = all_out[1]
    b.ram[0x800 + i:0x800 + i + 3] = bytes.fromhex('3E0300')
    b._banks()
    out['clock left at 28 MHz'] = b
    b = copy.deepcopy(patch)
    i = all_out[0]
    b.ram[0x800 + i:0x800 + i + 3] = bytes.fromhex('3E0300')
    b._banks()
    out['plot pass at 28 MHz (the beeper at the wrong clock)'] = b
    mutate('y off by one', bytes.fromhex('D619'), bytes.fromhex('D618'))
    mutate('x off by one column', bytes.fromhex('D682'), bytes.fromhex('D681'))
    mutate('first stage outlined too', bytes.fromhex('E602C0'), bytes.fromhex('E60000'))
    mutate('bottom line limit off', bytes.fromhex('C6B8'), bytes.fromhex('C6C0'))
    mutate('MMU slot 0 left mapped', bytes.fromhex('ED9150FFED91520A'), bytes.fromhex('00000000ED91520A'))
    mutate('MMU slot 2 left mapped', bytes.fromhex('ED91520AED91530B'), bytes.fromhex('00000000ED91530B'))
    mutate('stale figures never cleared', bytes.fromhex('3EFF32'), bytes.fromhex('3E0F32'))
    mutate('overlay never published', bytes.fromhex('ED916980'), bytes.fromhex('ED916900'))
    mutate('overlay not hidden', bytes.fromhex('ED916900AF'), bytes.fromhex('ED916980AF'))
    mutate('bullets outlined', bytes.fromhex('FE08C8'), bytes.fromhex('FEFFC8'))
    return out


def run_negative(broken, rzx, stop):
    c, ex = verify(broken, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched
    snapshot, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites). -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    size = len(zt.build_tail(s, 0x8000, patch.slot1, True)[0])
    tail = TAIL_ADDR
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


# ---- nexclash.py auto: the published build, boot-checked; with recordings the replay proof ---------------------------
import hashlib

PUBLISHER = 'Firebird, 1987'
NEG_RECORDING, NEG_STOP = 's1.rzx', 1300   # the broken builds and the ABI cases: this recording (else the first), these frames
# Each tested alone in JNext (the review run's NOTES.md "Cheats"); the published patch's three, as snapshot addresses:
# 54462 is in the packed stream, 60126 and 60430 are the archive's live addresses translated through stream_map.
TRAINERS = '''NInfinite lives
Z 8 54462 201 0
NImmunity
Z 8 60126 24 0
NInfinite bombs
Z 8 60430 126 0
Y
'''


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
    """nexclash.py auto: the outline build, as published (the snapshot holds the game's own loading screen), boot-checked
    with and without NEXLOAD. With --rzx the replay proof of each recording, the ABI cases and the broken builds. The
    pace, soak, flicker, beam and real loader proofs are the review run's (games/flying_shark.md "Evidence")."""
    import concurrent.futures, os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'pok', None):
        trainers = out / (name + '_verified.pok')
        trainers.write_text(TRAINERS)
        a.pok = str(trainers)
    say('Game      : Flying Shark (Graftgold / Firebird, 1987, 48K)')
    say('Engine    : flying_shark; the original look (no clash to remove), a white one-pixel outline on figures on '
        'a double-buffered Layer 2; original pace')
    nex = out / (name + '_sprites.nex')
    zt.convert(str(z80), str(nex), patch=Patch(z80), quiet=True)
    bad = boot_check(nex, z80, Patch(z80))
    ok = not bad
    say('%-10s: %s  %s' % ('Sprites', nex.name, hashlib.md5(nex.read_bytes()).hexdigest()))
    say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM; converter loader and NEXLOAD)'
                            if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    if rzxs:
        quick = getattr(a, 'quick', None)
        neg_rzx = next((r for r in rzxs if Path(r).name == NEG_RECORDING), rzxs[0])
        collect = [1 if r == neg_rzx else 0 for r in rzxs]
        with concurrent.futures.ProcessPoolExecutor(min(len(rzxs), os.cpu_count() or 1)) as pool:
            done = list(pool.map(_replay, [z80] * len(rzxs), rzxs, [quick] * len(rzxs), collect))
        states = []
        for path, (c, ex, got) in zip(rzxs, done):
            states += got
            fail = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fail
            say('Verify    : %s %d frames, %d hooks, %d R comparisons, %d port writes, %d plots, %d Layer 2 pictures, '
                '%d pixels, %d bitmap checks: %s' % (Path(path).name, c['frames'], c['hooks'], c['R comparisons'],
                                                     c['port writes compared'], c['plots'], c['publications'],
                                                     c['overlay pixels compared'], c['bitmap checks'],
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
