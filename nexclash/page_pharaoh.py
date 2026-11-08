"""Page and the Curse of the Pharaoh (T.D.F. micro-visions, 2015): clash removal by a Layer 2 figure overlay.

The ULA stays the original's byte for byte; each of the game's XOR figure plots is repeated on a Layer 2 in the figures'
own white. See asm/page_pharaoh_hooks.asm.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/page_pharaoh.json'
SOURCE_MD5 = '5237d25deb5ff67f461c7de61e5d2df3'
CMP = tuple(hooklib.CMP_R)
SITES = {0x8BB7: (0x8C63, 'h_both', 'both'), 0x8BAA: (0x8C4E, 'h_old', 'old'), 0x7F8A: (0x8C4E, 'h_old', 'old'), 0x868A: (0x8C4E, 'h_old', 'old'),
         0x8BC4: (0x8C5D, 'h_new', 'new'), 0x8364: (0x881D, 'h_room', 'room'), 0x7F70: (0x881D, 'h_room', 'room'),
         0x7743: (0x0DAF, 'h_cls', 'cls'), 0x7815: (0x0DAF, 'h_cls', 'cls'), 0x78D4: (0x0DAF, 'h_cls', 'cls'), 0x7955: (0x0DAF, 'h_cls', 'cls')}
SIGNATURE = {0x8BB7: 'CD638C', 0x8BAA: 'CD4E8C', 0x8364: 'CD1D88', 0x7815: 'CDAF0D'}
L2_PAGES = list(range(32, 38))
DECISIONS = {'figures': 'XOR plots unchanged on the ULA; their pixels repeated in white on Layer 2', 'scenery': 'keeps its own attributes',
             'pace': 'the game\'s own frame wait', 'outline': 'none', 'enhanced': 'waiting for the mock-up'}
PUBLISHER = 'T.D.F. micro-visions, 2015'
NEG_STOP = 1500


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_page(snap):
    banks = getattr(snap, 'banks', None)
    mem = bytes(16384) + banks[5] + banks[2] + banks[0] if banks is not None else bytes(snap.memory)
    try:
        return all(mem[a:a + len(v) // 2] == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (TypeError, IndexError):
        return False


def _bank(a):
    return (5, a - 0x4000) if a < 0x8000 else (2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000)


class Patch:
    name = 'Page and the Curse of the Pharaoh: clash removed by a Layer 2 figure overlay'
    uses_printer_buffer = True
    keep_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000
    tail_addr = 0x5B00

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
        self.ram[0x1E00:0x2000] = bytes(512)
        self.sites = [(a, b'\xcd' + zt.w16(t), b'\xcd' + zt.w16(self.syms[s])) for a, (t, s, k) in SITES.items()]
        self._banks()

    def _banks(self):
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_both', 'h_old', 'h_new', 'h_room', 'h_cls'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}

    def apply(self, snap):
        if not is_page(snap):
            raise ValueError('Not the supported Page release (MD5 %s)' % SOURCE_MD5)
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
    """64K view of the game RAM + the pages the hook maps, per the model's MMU."""
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
        if a >= 0xE000 and m != 1:
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
        if a >= 0xE000 and m != 1:
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
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.pages = {p: bytearray(b'\xff' * 8192) for p in L2_PAGES}
        self.nr = {0x12: 16, 0x69: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'page-hook')
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


class Overlay:
    """The expected overlay, by an independent reading of the game's figure table: the XOR of every plot."""
    def __init__(self):
        self.lit = set()

    def clear(self):
        self.lit = set()

    def toggle(self, mem, ix, new):
        if new:
            y, x, sp, fr = mem[ix + 8], mem[ix + 9], mem[ix + 6], mem[ix + 7]
        else:
            y, x, sp, fr = mem[ix + 3], mem[ix + 4], mem[ix + 1], mem[ix + 2]
        table = mem[0x7D39] | mem[0x7D3A] << 8
        a = (mem[(table + 2 * sp) & 0xFFFF] + fr) & 255
        base = (mem[0x7D3B] | mem[0x7D3C] << 8) + ((a >> 1) << 8) + ((a & 1) << 7) + ((x & 6) << 4)
        lm, rm = mem[0x8C46 + (x & 6)], mem[0x8C47 + (x & 6)]
        col = x & 0xF8
        for r in range(16):
            v, mid = mem[(base + 2 * r) & 0xFFFF], mem[(base + 2 * r + 1) & 0xFFFF]
            for i, bits in enumerate((v & lm, mid, v & rm)):
                for b in range(8):
                    if bits & (128 >> b):
                        self.lit ^= {(((col + 8 * i) & 255) + b, y + r)}


def _flat(sim):
    return bytes(sim.memory)


def _picture(st):
    out = set()
    for p in L2_PAGES:
        d = st.pages[p]
        if d.count(255) == 8192:
            continue
        y0 = (p - 32) * 32
        for r in range(32):
            seg = d[r * 256:r * 256 + 256]
            if seg.count(255) == 256:
                continue
            for x, v in enumerate(seg):
                if v == 7:
                    out.add((x, y0 + r))
                elif v != 255:
                    out.add((x, y0 + r, v))
    return out


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original; at every changed CALL run the hook on a copy of the state and compare with the original's run to
    its return (or the target's entry): every register with R, all 48K RAM except 32 bytes of dead stack the original's call
    chain wrote. The overlay against an independent XOR model of the figure table, after every plot."""
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

    def patched_mem(mem):
        p = bytearray(mem)
        for a, old, new in patch.sites:
            p[a:a + len(new)] = new
        return p

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        target, sym, kind = SITES[pc]
        if mem[pc:pc + 3] != bytes((0xCD, target & 255, target >> 8)):
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        ref = simpool.machine(Simulator, list(mem), regs, 'pp-ref')
        ret = (pc + 3) & 0xFFFF
        ix = regs[8] << 8 | regs[9]
        if kind == 'cls':
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched_mem(mem), regs, target)
            if st.nr.get(0x69) != 0:
                fail('overlay not hidden', {})
        else:
            sp = regs[12]
            n = 0
            R = ref.registers
            while n == 0 or R[24] != ret or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            if kind == 'both':
                ov.toggle(mem, ix, False)
                ov.toggle(mem, ix, True)
            elif kind == 'old':
                ov.toggle(mem, ix, False)
            elif kind == 'new':
                ov.toggle(mem, ix, True)
            else:
                ov.clear()
            got, v, model = run_hook(patch, st, patched_mem(mem), regs, ret, sp)
            if kind == 'room' and st.nr[0x69] != 0x80:
                fail('overlay not on after a room', {})
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        if kind != 'cls':
            sp = regs[12]
            for a in range(sp - 32, sp):
                expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x57] != 1:
            fail('MMU not restored', {'pc': hex(pc)})
        if model.nr[7] != 0:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7]})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if kind in ('both', 'old', 'new', 'room'):
            pic = _picture(st)
            if pic != ov.lit:
                diff = sorted(pic ^ ov.lit, key=str)
                fail('overlay differs from the model', {'pc': hex(pc), 'count': len(diff), 'ex': diff[:12]})
            c['overlay pictures compared'] += 1
            c['overlay pixels compared'] += len(pic)
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), set(SITES), on_pc, stop)
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
        target, sym, kind = SITES[pc]
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
                    if kind == 'cls':
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
                    got, v, model = run_hook(patch, st, patched, rr, stop, sp, speed=speed)
                    if any((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    if model.nr[7] != speed:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x57] != 1:
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
    mutate('x off by one column', bytes.fromhex('E6F8323E3E'), bytes.fromhex('E6F0323E3E'))
    mutate('wrong toggle colour', bytes.fromhex('EEF8'), bytes.fromhex('EEF0'))
    mutate('slot 7 left mapped', bytes.fromhex('ED915701C9'), bytes.fromhex('00000000C9'))
    mutate('right part of the wrap dropped', bytes.fromhex('3A403E4F'), bytes.fromhex('AF004F00'))
    l2 = patch.syms['l2_toggle']
    mutate('old place never taken off', bytes.fromhex('CDE08BCD') + zt.w16(l2), bytes.fromhex('CDE08B000000'))
    mutate('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('00000000'))
    mutate('overlay never cleared', bytes.fromhex('36FFD5'), bytes.fromhex('3600D5'))
    return out


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}
