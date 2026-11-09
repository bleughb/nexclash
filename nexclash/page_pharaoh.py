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
             'pace': 'the game\'s own frame wait', 'outline': 'none',
             'enhanced': "the Spec256 set's values on Layer 2, off by default (page_pharaoh_enh)"}
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


# ---- nexclash.py auto: the published builds, boot-checked; with recordings the replay proof of both modes ---------------
LOAD_SCREEN, LOAD_MD5 = 'page_pharaoh_loading.scr', '93efbf5304ce3397d0cf0c684c16ea37'   # the tape's screen: game data
# Enhanced, beside the start state, both or neither; never in this repo:
SET_NAME, SET_MD5 = 'page_pharaoh.256', 'b1961046825ce0fd1ed45624d58845b7'                    # the Spec256 set (Ynicky)
PALETTE_NAME, PALETTE_MD5 = 'page_pharaoh_palette.json', 'cc822d044ec89ffcffbfb3a122f4d088'  # the set's 256 colours as RGB
ENH_NEG_STOP = 1200                       # Enhanced broken builds, as in the review run
WHOLE = ('overlay not hidden',)           # needs a ROM CLS after play: the whole of the first recording, to its game over
# The archive's two, each tested alone (games/page_pharaoh.md); bank 8 = no paging.
TRAINERS = """NInfinite Lives
Z 8 30879 0 0
NImmunity
M 8 61300 0 0
Z 8 61443 0 0
Y
"""


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2), as the published .nxc."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


def _beside(z80, file, md5, what):
    """A private input beside the start state -> its path, or None. A different file there is refused."""
    import hashlib
    path = Path(z80).resolve().parent / file
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not %s (MD5 %s)' % (file, what, md5))
    return path


def enhanced_inputs(z80):
    """-> (set, palette) paths beside the start state, or None when either is missing."""
    got = (_beside(z80, SET_NAME, SET_MD5, 'the set this engine was proved with'),
           _beside(z80, PALETTE_NAME, PALETTE_MD5, "the set's palette this engine was proved with"))
    return tuple(str(p) for p in got) if all(got) else None


def _patch(z80, inputs):
    if inputs is None:
        return Patch(z80)
    from . import page_pharaoh_enh as E
    return E.Patch(z80, *inputs)


def _mod(inputs):
    if inputs is None:
        import sys
        return sys.modules[__name__]
    from . import page_pharaoh_enh as E
    return E


def boot_check(nex, z80, patch):
    """Booted with and without NEXLOAD's printer buffer: every register with R and all 48K RAM against the patched start
    state, bar the start-up tail (and the printer buffer NEXLOAD overwrites). -> problems."""
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
            if tail <= a < tail + size or (nexload and 0x5B00 <= a < 0x5C00):
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def _replay(z80, inputs, rzx, stop, collect):
    """One recording against one build's hooks (a process of its own) -> (name, counts, failures, states)."""
    r = _mod(inputs).verify(_patch(z80, inputs), rzx, stop=stop, collect=collect)
    c, ex, states = r[0], r[1], (r[2] if len(r) > 2 else [])
    return Path(rzx).name, dict(c), {k: (v, ex.get(k[:-1], [])[:2]) for k, v in c.items() if k.endswith('!')}, states


def _negative(z80, inputs, name, rzx, stop):
    """One deliberately broken build's replay (a process of its own) -> (name, its failure keys)."""
    M = _mod(inputs)
    try:
        return name, sorted(M.run_negative(M.negative_patches(_patch(z80, inputs))[name], rzx, stop))
    except Exception as e:          # noqa: BLE001 - a hang or crash of a broken build is a catch
        return name, ['hung or crashed: %s' % repr(e)[:80]]


def auto(a, z80, name, out, say):
    """nexclash.py auto: the overlay build and, with the set and its palette beside the start state, Enhanced; each with
    the tape's loading screen when it is beside the start state, as published; every build boot-checked. With --rzx:
    every recording replayed against each build's hooks, the ABI cases on states from the first recording, and the broken
    builds on its start ('overlay not hidden' on the whole of it). Pace, soak, flicker and the real loader are the review
    runs' (games/page_pharaoh.md "Evidence")."""
    import concurrent.futures, hashlib, os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'pok', None):
        trainers = out / (name + '_verified.pok')
        trainers.write_text(TRAINERS)
        a.pok = str(trainers)
    say('Game      : Page and the Curse of the Pharaoh (David Pagett, T.D.F. micro-visions, 2015)')
    say("Engine    : page_pharaoh; the ULA as the original, the figures' XOR plots repeated in white on Layer 2; Enhanced: "
        "the Spec256 set's values on Layer 2")
    ok = True
    screen = _beside(z80, LOAD_SCREEN, LOAD_MD5, "the tape's loading screen")
    inputs = enhanced_inputs(z80)
    if screen is None:
        say('Loading   : no %s beside the start state: builds without the loading screen' % LOAD_SCREEN)
    builds = [('Sprites', '_sprites', None)]
    if inputs is None:
        say('Enhanced  : not both of %s, %s beside the start state: default build only' % (SET_NAME, PALETTE_NAME))
    else:
        builds.append(('Enhanced', '_enhanced', inputs))
    for label, suffix, inp in builds:
        nex = out / (name + suffix + '.nex')
        zt.convert(str(z80), str(nex), patch=_patch(z80, inp), quiet=True)
        nexes = [(label, nex)]
        if screen is not None:
            loading = out / (name + suffix + '_loading.nex')
            loading.write_bytes(loading_nex(nex.read_bytes(), screen.read_bytes()))
            nexes.append((label[:3] + '+scr', loading))
        for lab, path in nexes:
            bad = boot_check(path, z80, _patch(z80, inp))
            ok = ok and not bad
            say('%-10s: %s  %s' % (lab, path.name, hashlib.md5(path.read_bytes()).hexdigest()))
            say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM; converter loader and NEXLOAD)' if not bad
                                    else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    stop = getattr(a, 'quick', None)
    if not rzxs:
        say('Verify    : not requested; boot evidence only')
        say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
        return bool(ok)
    with concurrent.futures.ProcessPoolExecutor(os.cpu_count() or 1) as pool:
        jobs = []
        for label, suffix, inp in builds:
            nstop = NEG_STOP if inp is None else ENH_NEG_STOP
            nstop = nstop if stop is None else min(stop, nstop)
            first = pool.submit(_replay, z80, inp, rzxs[0], nstop, 1)
            reps = [pool.submit(_replay, z80, inp, r, stop, 0) for r in rzxs]
            negs = []
            if stop is None:
                names = list(_mod(inp).negative_patches(_patch(z80, inp)))
                negs = [pool.submit(_negative, z80, inp, k, rzxs[0], None if k in WHOLE else nstop) for k in names]
            jobs.append((label, inp, first, reps, negs, nstop))
        for label, inp, first, reps, negs, nstop in jobs:
            for f in reps:
                rname, c, fail, _ = f.result()
                ok = ok and not fail
                say('Verify    : %s %s %d frames, %d hooks, %d R comparisons, %d overlay pictures: %s' % (
                    label, rname, c.get('frames', 0), c.get('hooks', 0), c.get('R comparisons', 0),
                    c.get('overlay pictures compared', 0), 'IDENTICAL' if not fail else str(fail)[:400]))
            u = _mod(inp).unit_tests(_patch(z80, inp), first.result()[3])
            ok = ok and not [k for k in u if k.endswith('!')] and u.get('ABI cases', 0) > 0
            say('Unit      : %s %s' % (label, dict(u)))
            if negs:
                res = dict(f.result() for f in negs)
                missed = [k for k, v in res.items() if not v]
                ok = ok and not missed
                say('Negatives : %s %d of %d broken builds caught (%s, %d frames each; %s to its end)%s' % (
                    label, len(res) - len(missed), len(res), Path(rzxs[0]).name, nstop, ', '.join(WHOLE),
                    '; MISSED %s' % missed if missed else ''))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
