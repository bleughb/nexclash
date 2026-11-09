"""The Official Father Christmas Game (Enigma Variations / Alternative, 1989, 48K): clash removal on Layer 2, level 1.

The ULA stays the original's, every byte: the game reads its attributes for walls and ladders. In level 1 each figure's ink
goes on a double-buffered Layer 2 in bright white, its colour in the open. See asm/father_christmas_hooks.asm.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/father_christmas.json'
SOURCE_MD5 = '71dd57b2ece2787dfff915bf3ba50d3f'
CMP = tuple(hooklib.CMP_R)
SANTA, ELF, DRAW, ROOM = 0x7EE7, 0x8FEE, 0x90AB, 0x7FB4
CALLS = {0x893D: (SANTA, 'h_santa', 'santa'), 0x8F41: (ELF, 'h_elf', 'elf'), 0x8FE7: (ELF, 'h_elf', 'elf'),
         0x895A: (DRAW, 'h_draw', 'draw'), 0x88D4: (ROOM, 'h_room', 'room'),
         0x893A: (0x8E2E, 'h_rest_e', 'body'), 0x8951: (0x8E2E, 'h_rest_e', 'body'), 0x8954: (0x8E00, 'h_rest_s', 'body'), 0x8940: (0x8DD2, 'h_save_s', 'body')}
CLS, CLS_OLD, CLS_TO = 0x83A5, bytes.fromhex('210058'), 0x83A8
INK, CLEAR = 15, 255
DECISIONS = {'figures': 'the original bitmap and attributes on the ULA, every byte; figure ink on Layer 2 in bright white, in plot order',
             'scenery': 'the original', 'pace': 'original; the update is locked by HALTs', 'outline': 'none',
             'enhanced': 'waiting for the owner'}


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_father_christmas(snap):
    try:
        ram = bytes(16384) + bytes(snap.ram(-1))
    except (AttributeError, TypeError):
        return False
    return len(ram) == 65536 and all(ram[a:a + 3] == b'\xcd' + zt.w16(t) for a, (t, _, _) in CALLS.items()) and ram[CLS:CLS + 3] == CLS_OLD


class Patch:
    name = 'The Official Father Christmas Game: figures on Layer 2'
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
        self.ram[0x1900:0x1C00] = bytes(0x300)
        self.ram[self.syms['V_BACK'] - 0x2000] = 16
        self.ram[self.syms['V_RECT'] - 0x2000:self.syms['V_RECT'] - 0x2000 + 2] = (0x3900).to_bytes(2, 'little')
        self.ram[self.syms['V_FREEP'] - 0x2000] = 48
        self.sites = []
        if enabled:
            for a, (target, sym, kind) in CALLS.items():
                self.sites.append((a, b'\xcd' + zt.w16(target), b'\xcd' + zt.w16(self.syms[sym])))
            self.sites.append((CLS, CLS_OLD, b'\xc3' + zt.w16(self.syms['h_cls'])))
        self._banks()

    def _banks(self):
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_santa', 'h_elf', 'h_draw', 'h_room', 'h_cls', 'h_rest_e', 'h_rest_s', 'h_save_s'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        end = self.syms['veneers_end'] - 0x2800
        for i in range(end - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}

    def apply(self, snap):
        ram = bytearray(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0]
        if snap.is128:
            raise ValueError('Not the supported release (MD5 %s)' % SOURCE_MD5)
        for a, old, new in self.sites if self.enabled else []:
            if ram[a:a + len(old)] != old:
                raise ValueError('Original bytes differ at %04X' % a)
            ram[a:a + len(new)] = new
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
            s = a >> 13
            m = self.model.nr.get(0x50 + s, DEF[s])
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
        self.pages = Pages({p: bytearray(b'\xff' * 8192) for p in range(32, 44)})
        self.nr = {0x12: 16, 0x69: 0}
        self.line = 0


class _Ports:
    def __init__(self):
        self.io = []

    def write_port(self, regs, port, v, *args):
        self.io.append((port, v))

    def read_port(self, regs, port):
        return 255


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=6000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'father-christmas-hook')
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


def screen_y(addr):
    return ((addr >> 5) & 0xC0) | ((addr >> 8) & 7) | ((addr >> 2) & 0x38)


class Overlay:
    """The expected picture, read from the game's graphics by its own plot rules: (bg AND mask) OR data, in plot order."""
    def __init__(self):
        self.santa = None
        self.elves = []

    @staticmethod
    def stamp(pic, mem, src, y0, col, w, h):
        for line in range(h):
            for c in range(w):
                mask, data = mem[src], mem[src + 1]
                src += 2
                for b in range(8):
                    xy = ((col + c) * 8 + b, y0 + line)
                    if data & (128 >> b):
                        pic[xy] = INK
                    elif not mask & (128 >> b):
                        pic.pop(xy, None)

    def picture(self, mem):
        pic = {}
        if self.santa:
            self.stamp(pic, mem, *self.santa, 4, 40)
        for e in self.elves:
            self.stamp(pic, mem, *e, 3, 24)
        return {xy: v for xy, v in pic.items() if xy[1] < 192}


def front_picture(st):
    pic = {}
    bank = st.nr[0x12]
    for y in range(192):
        page = st.pages[bank * 2 + (y >> 5)]
        row = (y & 31) << 8
        seg = page[row:row + 256]
        if seg.count(CLEAR) == 256:
            continue
        for i, v in enumerate(seg):
            if v != CLEAR:
                pic[(i, y)] = v
    return pic


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original; at every changed site run the hook on a copy of the state to the game's own routine and compare with the
    original's there: every register with R, all 48K RAM. The Layer 2 picture is compared with an independent model at every flip,
    and every lit pixel with the bitmap on the ULA."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    ov = Overlay()

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)

    def on_pc(pc, sim):
        mem = bytes(sim.memory)
        regs = list(sim.registers)
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        c['site %04X' % pc] += 1
        if regs[26]:
            c['hooks with interrupts on'] += 1
        patched = bytearray(mem)
        for a, old, new in patch.sites:
            patched[a:a + len(new)] = new
        if pc == CLS:
            target, sym, kind = CLS_TO, 'h_cls', 'cls'
            if mem[pc:pc + 3] != CLS_OLD:
                fail('site bytes changed', {'pc': hex(pc)})
                return
        else:
            target, sym, kind = CALLS[pc]
            if mem[pc:pc + 3] != b'\xcd' + zt.w16(target):
                fail('site bytes changed', {'pc': hex(pc)})
                return
        ref = simpool.machine(Simulator, list(mem), regs, 'fc-ref')
        ref.opcodes[ref.memory[pc]]()
        if ref.registers[24] != target:
            fail('reference did not reach the routine', {'pc': hex(pc)})
            return
        whole = kind in ('santa', 'elf', 'body')
        ports = _Ports()
        if whole:                       # these hooks run the game's routine: compare at its return
            ref.set_tracer(ports)
            R = ref.registers
            ret, sp = (pc + 3) & 0xFFFF, regs[12]
            while R[24] != ret or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
        if kind == 'santa':
            off = mem[0xFA08] | mem[0xFA09] << 8
            line = mem[0xDE5C + off] | mem[0xDE5D + off] << 8
            ov.santa = (mem[0xFA04] | mem[0xFA05] << 8, screen_y(line), mem[0xFA0A])
            if off & 1 or screen_y(line) != (off >> 1) & 255:
                fail('Santa line is not the table index', {'off': off})
        elif kind == 'elf':
            hl, de = regs[6] << 8 | regs[7], regs[4] << 8 | regs[5]
            ov.elves.append((hl, screen_y(de), de & 31))
        elif kind in ('room', 'cls'):
            ov.santa = None
            ov.elves = []
        got, v, model = run_hook(patch, st, patched, regs, ret if whole else target, regs[12] if whole else None)
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ ' + sym, {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
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
        if model.io != ports.io:
            fail('game I/O differs', {'pc': hex(pc), 'orig': ports.io[:4], 'got': model.io[:4]})
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        if kind in ('room', 'cls') and st.nr.get(0x69) != 0:
            fail('overlay not hidden', {'pc': hex(pc)})
        if kind == 'draw':
            c['publications'] += 1
            if st.nr.get(0x69) != 0x80:
                fail('overlay not on after publish', {})
            pic = front_picture(st)
            want = ov.picture(mem)
            if pic != want:
                diff = [k for k in set(pic) | set(want) if pic.get(k) != want.get(k)]
                fail('overlay differs from the model', {'pc': hex(pc), 'count': len(diff), 'ex': sorted(diff)[:6], 'santa': ov.santa, 'elves': ov.elves})
            c['overlay pixels compared'] += len(pic)
            for (x, y) in pic:
                if y >= 144:                # below Layer 2's clip window: never on show
                    continue
                a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
                if not mem[a] & (128 >> (x & 7)):
                    fail('overlay pixel over a clear bitmap bit', {'x': x, 'y': y})
                    break
            ov.elves = []
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), set(CALLS) | {CLS}, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


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
        target = CLS_TO if pc == CLS else CALLS[pc][0]
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    ref.opcodes[ref.memory[pc]]()
                    whole = pc in CALLS and CALLS[pc][2] in ('santa', 'elf', 'body')
                    if whole:
                        ret, sp = (pc + 3) & 0xFFFF, rr[12]
                        while ref.registers[24] != ret or ref.registers[12] != sp:
                            ref.opcodes[ref.memory[ref.registers[24]]]()
                    st = State(patch)
                    got, v, model = run_hook(patch, st, _patched_mem(patch, mem), rr, ret if whole else target, rr[12] if whole else None, speed=speed)
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
    mutate('R off by one', bytes.fromhex('3EF4CD'), bytes.fromhex('3EF5'))
    mutate('clock left at 28 MHz', bytes.fromhex('F53AC03BED9207'), bytes.fromhex('F53E0300ED9207'))
    mutate('x wrong: Santa at his y', bytes.fromhex('3AD43B32E53B'), bytes.fromhex('3AD33B32E53B'))
    mutate('wrong ink', bytes.fromhex('3E0F32'), bytes.fromhex('3E0E32'))
    mutate('MMU slot 0 left mapped', bytes.fromhex('ED9150FFED91520A'), bytes.fromhex('00000000ED91520A'))
    mutate('MMU slot 2 left mapped', bytes.fromhex('ED91520AED91530B'), bytes.fromhex('00000000ED91530B'))
    mutate('stale figures never cleared', bytes.fromhex('3EFF32'), bytes.fromhex('3E0F32'))
    mutate('overlay never published', bytes.fromhex('ED916980'), bytes.fromhex('ED916900'))
    mutate('overlay not hidden', bytes.fromhex('ED916900AF'), bytes.fromhex('ED916980AF'))
    mutate('elves do not punch', bytes.fromhex('3AF23BB7C8'), bytes.fromhex('3E00B7C800'))
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
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


# ---- nexclash.py auto: the published build, boot-checked; with recordings the replay proof ---------------------------
import hashlib

PUBLISHER = 'Alternative Software, 1989'
NEG_RECORDING, NEG_STOP = 's1.rzx', 2500   # the broken builds and the ABI cases: this recording (else the first), these frames
# Tested in JNext (the review run's NOTES.md "Cheats"): the archive's one entry, as it is.
TRAINERS = '''NInfinite time
Z 8 33122 0 0
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
    """nexclash.py auto: the clash-fix build, as published (the snapshot stops at the game's menu: no loading screen),
    boot-checked with and without NEXLOAD. With --rzx the replay proof of each recording, the ABI cases and the broken
    builds. The pace, soak, flicker, beam and real loader proofs are the review run's (games/father_christmas.md
    "Evidence")."""
    import concurrent.futures, os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'pok', None):
        trainers = out / (name + '_verified.pok')
        trainers.write_text(TRAINERS)
        a.pok = str(trainers)
    say('Game      : The Official Father Christmas Game (Alternative Software, 1989, 48K)')
    say('Engine    : father_christmas; level 1\'s figures in their own white on a double-buffered Layer 2 over the '
        'original bitmap, clash removed; levels 2 and 3 as the original; original pace')
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
            say('Verify    : %s %d frames, %d hooks, %d R comparisons, %d Santa plots, %d elf plots, %d Layer 2 pictures, '
                '%d pixels: %s' % (Path(path).name, c['frames'], c['hooks'], c['R comparisons'], c['hooks santa'],
                                   c['hooks elf'], c['publications'], c['overlay pixels compared'],
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
