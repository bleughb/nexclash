"""Mad Mix 2 - en el Castillo de los Fantasmas (Topo Soft, 1990, 128K): the original look, made to display on a Next.

The play area is one attribute per stage, so there is no clash to remove. The copy to the screen writes 2, then 3, to port
0xFF: nothing on a 128K, Timex hi-colour in a Next .nex (the picture is garbage; NextZXOS's snapshot loader shows it fine). Both writes become IN A,(0xFF): same bytes,
same T states, same R; A is reloaded before anything reads it. No hooks, no Layer 2, no sprites.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/mad_mix_2.json'
SOURCE_MD5 = 'f5f5262f7a41d3c55408b45878c31d00'
CMP = tuple(hooklib.CMP_R)
SITES = ((0xABEF, b'\xd3\xff', b'\xdb\xff'), (0xAC43, b'\xd3\xff', b'\xdb\xff'))
A_RELOAD = {0xABEF: 0xABF4, 0xAC43: 0xAA62}     # where each site's A dies: LD A,$90 and the handler's next LD A,(6001)
REGBLOCK = 0x3900                               # Sinclair's unused 0xFF fill; the game reads ROM only at 0000-015F
SIGNATURE = {0xABEF: 'D3FF', 0xAC43: 'D3FF', 0x6001: '01', 0x8818: 'CD76A7'}
DECISIONS = {'figures': 'the original look: no clash to remove, one attribute per stage', 'outline': 'none: figures have their own black edge and white fill',
             'pace': 'unchanged code at the game clock', 'enhanced': 'waiting for the mock-up'}
PUBLISHER = 'Topo Soft, 1990'


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_mad_mix_2(snap):
    banks = getattr(snap, 'banks', None)
    if banks is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    if not getattr(snap, 'is128', False):
        return False
    bank = {0x4000: 5, 0x8000: 2}
    try:
        return all(bytes(banks[bank[a & 0xC000]][a & 0x3FFF:(a & 0x3FFF) + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (KeyError, TypeError, IndexError):
        return False


class Patch:
    name = 'Mad Mix 2 128K: the copy no longer switches a Next into Timex hi-colour'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = None
    stub_extra = b''

    def __init__(self, source=None, sites=SITES):
        from .build import rom48
        self.source = str(source) if source else None
        self.sites = [tuple(s) for s in sites]
        self.slot1 = (25, REGBLOCK)
        self.altrom = self.altrom0 = (REGBLOCK, REGBLOCK + 20)    # the alt ROM holds only the start-up's register block, over Sinclair's ROM
        self.page = bytearray(rom48()[0x2000:0x4000])
        self.extra_banks = {12: bytes(0x2000) + bytes(self.page)}

    def apply(self, snap):
        if not is_mad_mix_2(snap):
            raise ValueError('Not the supported Mad Mix 2 128K release (MD5 %s)' % SOURCE_MD5)
        b = bytearray(snap.banks[2])
        for a, old, new in self.sites:
            at = a - 0x8000
            if bytes(b[at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            b[at:at + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(b) if i == 2 else bytes(snap.banks[i])) for i in range(8))


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


class _Machine:
    """A 128K machine fed an RZX frame's port readings. Port 0xFF reads are the patch's, so they take no reading."""
    FRAME_T = 70908

    def __init__(self, z80, sites=()):
        from skoolkit import CSimulator
        from skoolkit.simutils import from_snapshot
        from skoolkit.snapshot import Snapshot
        s = Snapshot.get(z80)
        self.sim = from_snapshot(CSimulator, s, config={'int_active': 0})
        self.mem = self.sim.memory
        for a, old, new in sites:
            for i, v in enumerate(new):
                self.mem[a + i] = v
        self.out7ffd = s.out7ffd
        self.ins = iter(())
        self.ports = Counter()
        self.sim.set_tracer(self)

    def read_port(self, registers, port):
        if port & 0xFF == 0xFF:
            self.ports['in ff'] += 1
            return 0xFF
        return next(self.ins, 0xFF)

    def write_port(self, registers, port, value, offset=0):
        if port & 0xFF == 0xFF:
            self.ports['out ff'] += 1
        if port & 0x8002 == 0 and self.out7ffd & 32 == 0:
            self.mem.out7ffd(value)
            self.out7ffd = value

    def frame(self, ins, watch=None):
        from skoolkit.simutils import T, IFF, PC
        self.ins = iter(ins)
        regs = self.sim.registers
        left = [0, regs[PC]]

        class End(Exception):
            pass

        def tr(fc, at):
            if regs[T] >= self.FRAME_T:
                left[:] = [fc, at]
                raise End()
            if watch is not None and at in watch:
                watch[at](self)
        try:
            self.sim.exec_frame(65535, None, tr)
        except End:
            pass
        else:
            raise RuntimeError('frame over the fetch budget')
        regs[T] = 0
        if regs[IFF]:
            if self.mem[left[1]] == 0x76:
                regs[PC] = (regs[PC] + 1) % 65536
            self.sim.accept_interrupt(regs, self.mem, 0)
        return 65535 - left[0]

    def state(self):
        return [bytes(b) for b in self.mem.banks], list(self.sim.registers)


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Original and patched machines fed the same recording: at the end of every frame every register with R, all eight RAM
    banks and the frame's fetch count must match, A aside between a site and the point its value dies. Port 0xFF: the patched
    machine must never write it. -> (Counter, examples, states)."""
    from .rzx import read_segments
    from skoolkit.simutils import PC, A
    c, examples = Counter(), defaultdict(list)

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    states = []
    for snap, rec, _ in read_segments(rzx_path):
        break
    from tempfile import NamedTemporaryFile
    from .rzx import extract
    with NamedTemporaryFile(suffix='.z80') as t:
        extract(rzx_path, t.name)
        orig, new = _Machine(t.name), _Machine(t.name, patch.sites)
    live_a = [False]
    passes = Counter()

    def enter(a):
        def f(m):
            passes[a] += 1
            live_a[0] = True
        return f

    def die(m):
        live_a[0] = False
    watch = {s[0]: enter(s[0]) for s in patch.sites}
    watch.update({A_RELOAD[s[0]]: die for s in patch.sites if s[0] in A_RELOAD})
    for n, frame in enumerate(rec.frames):
        if stop is not None and n >= stop:
            break
        ins = rec.data[frame.start:frame.end]
        fo = orig.frame(ins)
        fn = new.frame(ins, watch)
        c['frames'] += 1
        if fo != fn:
            fail('fetch count differs', {'frame': n, 'orig': fo, 'new': fn})
        bo, ro = orig.state()
        bn, rn = new.state()
        c['R comparisons'] += 1
        for i in CMP:
            if i == A and live_a[0]:
                continue
            if ro[i] != rn[i]:
                fail('registers differ', {'frame': n, 'reg': i, 'orig': ro[i], 'new': rn[i], 'pc': hex(ro[PC])})
        for b in range(8):
            if bo[b] != bn[b]:
                diff = [i for i in range(16384) if bo[b][i] != bn[b][i]]
                diff = [i for i in diff if not (b == 2 and any(0 <= (0x8000 + i) - s[0] < len(s[1]) for s in SITES))]
                if diff:
                    fail('RAM differs', {'frame': n, 'bank': b, 'at': hex(diff[0]), 'count': len(diff)})
        if collect and len(states) < collect and passes:
            states.append((bn, rn))
        if progress and n % 2000 == 0:
            progress(n)
    c['original port FF writes'] = orig.ports['out ff']
    c['build port FF writes'] = new.ports['out ff']
    c['site passes'] = sum(passes.values())
    if new.ports['out ff']:
        fail('the build still writes port FF', {'count': new.ports['out ff']})
    if not orig.ports['out ff'] and c['frames'] > 1000:
        fail('the recording never reached the copy', {})
    return c, examples, states


def unit_tests(patch, states, neg=True):
    """The sites alone from every A: only A may change, with the same T, R and flags as the OUT they replace."""
    from skoolkit import CSimulator
    from skoolkit.simutils import A, R, T, PC, F
    from skoolkit.snapshot import Snapshot
    c = Counter()

    class Ports:
        def __init__(self):
            self.out = 0

        def read_port(self, regs, port):
            return 0xFF

        def write_port(self, regs, port, value, offset=0):
            self.out += 1
    for a, old, new in patch.sites:
        for av in range(256):
            res = []
            for code in (old, new):
                memory = [0] * 65536
                memory[a:a + 2] = code
                sim = CSimulator(memory, config={'int_active': 0})
                p = Ports()
                sim.set_tracer(p)
                sim.registers[A] = av
                sim.registers[F] = 0x55
                sim.registers[PC] = a
                sim.run(stop=a + 2)
                res.append((sim.registers[T], sim.registers[R], sim.registers[F], sim.registers[PC], p.out))
            c['site cases'] += 1
            if res[0][:4] != res[1][:4]:
                c['T, R, flags or PC differ!'] += 1
            if new == b'\xdb\xff' and res[1][4] != 0:
                c['the replacement writes a port!'] += 1
    return c


def negative_patches(patch):
    one = lambda i, new: [(s[0], s[1], new if j == i else s[2]) for j, s in enumerate(SITES)]
    return {'first write left in': Patch(patch.source, one(0, b'\xd3\xff')),
            'second write left in': Patch(patch.source, one(1, b'\xd3\xff')),
            'first site as two NOPs (R, T)': Patch(patch.source, one(0, b'\x00\x00')),
            'second site as two NOPs (R, T)': Patch(patch.source, one(1, b'\x00\x00')),
            'a stray byte in game RAM': Patch(patch.source, [(0xABEF, b'\xd3\xff', b'\xdb\xff'), (0x8E73, b'\x00', b'\x01')])}


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched snapshot, bar the tail."""
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


def auto(a, z80, name, out, say):
    """nexclash.py auto: the build, its boot check, and with --rzx the differential replay, the unit cases and the broken builds."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'fix_label', None):
        a.fix_label = 'NexClash build'
    say('Game      : Mad Mix 2 (Topo Soft, 1990, 128K)')
    say('Engine    : mad_mix_2; the original look; both port FF writes of the copy become reads; no hooks')
    ok = True
    nex = out / (name + '_sprites.nex')
    p = Patch(z80)
    zt.convert(str(z80), str(nex), patch=p, quiet=True)
    bad = boot_check(nex, z80, Patch(z80))
    ok = not bad
    say('Plain     : %s' % nex.name)
    say('Sprites   : none; the build is the fix')
    say('Boot      : %s' % ('simulated, OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    states = []
    for path in list(getattr(a, 'rzx', None) or []):
        c, ex, got = verify(Patch(z80), path, stop=getattr(a, 'quick', None), collect=1)
        states += got
        fail = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fail
        say('Verify    : %s %d frames, %d R comparisons, %d site passes: %s' % (Path(path).name, c['frames'], c['R comparisons'], c['site passes'], 'IDENTICAL' if not fail else str(fail)))
    u = unit_tests(Patch(z80), states)
    ok = ok and not [k for k in u if k.endswith('!')]
    say('Unit      : %s' % dict(u))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
