"""Ruff and Reddy in the Space Adventure (Hi-Tec, 1990, 128K): clash removal by a Layer 2 figure overlay.

The ULA stays the original's byte for byte; each figure's ink goes on a double-buffered Layer 2 in white, in the
game's plot order. See asm/ruff_and_reddy_hooks.asm.
"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib, json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/ruff_and_reddy.json'
SOURCE_MD5 = '4b6c490438881cb23d0993d4b32788a2'
CMP = tuple(hooklib.CMP_R)
BIG, SMALL = 0xA66C, 0xA867
# site: (original CALL target, hook symbol, kind)
CALLS = {0xA468: (BIG, 'h_big', 'big'), 0xA484: (BIG, 'h_big', 'big'), 0xA4A0: (BIG, 'h_big', 'big'),
         0xA4BC: (SMALL, 'h_small', 'small'), 0xA4D8: (SMALL, 'h_small', 'small'), 0xA4F4: (SMALL, 'h_small', 'small'),
         0x818B: (0xAADD, 'h_room', 'hide'), 0x80F7: (0xD332, 'h_title', 'hide'),
         0x8B45: (0xAC70, 'h_over', 'hide'), 0x8B79: (0xAC70, 'h_over', 'hide'),
         0xFD75: (0xAC70, 'h_over', 'hide')}   # FD75, in bank 0: giving up in the pause, or the end of the game
COPY_IN, COPY_OUT, COPY_RET = 0xA506, 0xA5E6, 0xA5E9
MSG_SITE = 0xD42B      # in bank 0: the window is cleared for a message, such as LEVEL COMPLETE
RENDER, WAIT, HALT = 0x81B2, 0xA4F7, 0xA4F8
V_SPEED, V_Q = 0x3E30, 0x3E42
SIGNATURE = {0xA506: '31A49E', 0xA5E6: '31BF5D', 0xA468: 'CD6CA6', 0xA4BC: 'CD67A8', 0x818B: 'CDDDAA'}
ROW_FIRST, X_LEFT = 32, 24
WHITE = 15
DECISIONS = {'figures': 'original bitmap on the ULA; figure ink in white on Layer 2, in plot order',
             'scenery': 'keeps its own attributes', 'pace': 'original; hlib_pace K windows',
             'outline': 'none: figures have their own black masks', 'enhanced': 'waiting for the mock-up'}
PUBLISHER = 'Hi-Tec, 1990'


def load_profile():
    return json.loads(PROFILE.read_text())


def is_ruff_and_reddy(snap):
    """The 128K release: zt.Z80Snapshot (banks) or skoolkit's Snapshot (memory)."""
    banks = getattr(snap, 'banks', None)
    if banks is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    if not getattr(snap, 'is128', False):
        return False
    try:
        return all(bytes(banks[2][a - 0x8000:a - 0x8000 + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (KeyError, TypeError, IndexError):
        return False


class Patch:
    name = 'Ruff and Reddy 128K: clash removed by a Layer 2 figure overlay'
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
        self.ram[V_Q - 0x2000:V_Q - 0x2000 + 2] = (0x3E80).to_bytes(2, 'little')
        self.sites = []
        self.site_info = {}
        if enabled:
            for a, (target, sym, kind) in CALLS.items():
                self.sites.append((a, b'\xcd' + zt.w16(target), b'\xcd' + zt.w16(self.syms[sym])))
                self.site_info[a] = (target, sym, kind)
            self.sites.append((RENDER, b'\xc3\x1e\xa3', b'\xc3' + zt.w16(self.syms['h_render'])))
            self.sites.append((WAIT, b'\xfb\x76\xf3', b'\xc3' + zt.w16(self.syms['h_render_end'])))
            self.sites.append((COPY_IN, b'\x31\xa4\x9e', b'\xc3' + zt.w16(self.syms['h_copy'])))
            self.sites.append((COPY_OUT, b'\x31\xbf\x5d', b'\xc3' + zt.w16(self.syms['h_copy_end'])))
            self.sites.append((MSG_SITE, b'\xed\x73\xa0', b'\xc3' + zt.w16(self.syms['h_msg'])))
            self.site_info[MSG_SITE] = (0xD42F, 'h_msg', 'hide')
        self._banks()

    def _banks(self):
        # Hidden ROM (page 25): tiny entry and return veneers only. Code and writable state: page 24.
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_big', 'h_small', 'h_copy', 'h_room', 'h_title', 'h_over', 'h_msg', 'h_render', 'h_render_end'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}

    def apply(self, snap):
        if not is_ruff_and_reddy(snap):
            raise ValueError('Not the supported Ruff and Reddy 128K release (MD5 %s)' % SOURCE_MD5)
        if not self.enabled:
            return
        banks = {i: bytearray(b) for i, b in snap.banks.items()}
        for a, old, new in self.sites:
            bank, at = (0, a - 0xC000) if a >= 0xC000 else (2, a - 0x8000)
            if bytes(banks[bank][at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[bank][at:at + len(new)] = new
        snap.banks = type(snap.banks)(sorted((i, bytes(b)) for i, b in banks.items()))


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
        self.pages = {p: bytearray(b'\xff' * 8192) for p in list(range(32, 37)) + list(range(38, 43))}
        self.nr = {0x12: 16, 0x69: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'ruff-reddy-hook')
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
    """The expected picture, by an independent reading of the game's own plot state."""
    def __init__(self):
        self.back = {}          # (x, y) -> colour; absent = transparent
        self.fresh = False

    def plot(self, mem, kind):
        if self.fresh:
            self.back = {}
            self.fresh = False
        if kind == 'big':
            x, y, s, table, h, n = mem[0xA671], mem[0xA69B], mem[0xA68F], 0xA034, 32, 3
        else:
            x, y, s, table, h, n = mem[0xA86C], mem[0xA896], mem[0xA88A], 0xA05E, 16, 2
        src = mem[table + 2 * s] | mem[table + 2 * s + 1] << 8
        for r in range(h):
            row = y + r - ROW_FIRST
            if not 0 <= row < 160:
                continue
            at = src + r * 2 * n
            for i in range(n):
                m, g = mem[at + i], mem[at + n + i]
                for b in range(8):
                    xy = (x + X_LEFT + i * 8 + b, row)
                    if not X_LEFT <= xy[0] <= 231:
                        continue
                    if g & (128 >> b):
                        self.back[xy] = WHITE
                    elif not m & (128 >> b):
                        self.back.pop(xy, None)


def _flat(sim):
    m = sim.memory
    return bytes(16384) + bytes(m.memory[1]) + bytes(m.memory[2]) + bytes(m.memory[3])


def _patched(patch, mem):
    out = bytearray(mem)
    for a, old, new in patch.sites:
        out[a:a + len(new)] = new
    return out


def _pixels(st):
    front = st.nr[0x12]
    picture = {}
    for row in range(160):
        page = st.pages[front * 2 + (row >> 5)]
        at = (row & 31) << 8
        seg = page[at + X_LEFT:at + 232]
        if seg.count(255) == 208:
            continue
        for xb, val in enumerate(seg):
            if val != 255:
                picture[(xb + X_LEFT, row)] = val
    return picture


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original; at every changed site run the hook on a copy of the state and compare with the original's
    run to its return: every register with R, all 48K RAM. The Layer 2 picture is compared with an independent model
    at every publication, and every lit pixel with the bitmap the copy wrote."""
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
    pcs = set(CALLS) | {COPY_IN, RENDER, WAIT, MSG_SITE}

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        if pc == COPY_IN:
            kind, sym, target = 'copy', 'h_copy', None
            if mem[pc:pc + 3] != b'\x31\xa4\x9e':
                fail('site bytes changed', {'pc': hex(pc)})
                return
            ret, sp = COPY_RET, 0x5DBF
        elif pc == RENDER:
            kind, sym, target = 'render', 'h_render', 0xA31E
            ret, sp = target, regs[12]
        elif pc == WAIT:
            kind, sym, target = 'wait', 'h_render_end', HALT
            ret, sp = HALT, regs[12]
        else:
            target, sym, kind = patch.site_info[pc]
            if mem[pc:pc + 3] != (b'\xed\x73\xa0' if pc == MSG_SITE else bytes((0xCD, target & 255, target >> 8))):
                if pc >= 0xC000:                # another bank at C000: not this site
                    return
                fail('site bytes changed', {'pc': hex(pc)})
                return
            ret, sp = target, regs[12] - 2
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        ref = simpool.machine(Simulator, list(mem), regs, 'rr-ref')
        patched = _patched(patch, mem)
        if regs[26] and kind in ('big', 'small', 'render', 'wait', 'copy'):
            fail('interrupts on at a hook', {'pc': hex(pc)})
        if kind in ('big', 'small'):
            ov.plot(mem, kind)
            c['figures %s' % kind] += 1
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched, regs, target)
        elif kind == 'hide':
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched, regs, target)
            if st.nr.get(0x69) != 0:
                fail('overlay not hidden', {'pc': hex(pc)})
        elif kind == 'render':
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched, regs, target)
        elif kind == 'wait':
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched, regs, patch.syms['h_halt'], speed=3)
        else:
            n = 0
            R = ref.registers
            while n == 0 or R[24] != ret or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            got, v, model = run_hook(patch, st, patched, regs, ret, sp)
        for i in CMP:
            if kind == 'wait' and i == 24:
                continue
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        # The stack below SP: the original's call chain wrote it, the hook's ran on its own stack.
        if kind != 'copy':
            sp0 = regs[12]
            for a in range(sp0 - 32, sp0):
                expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255:
            fail('MMU not restored', {'pc': hex(pc)})
        if model.nr[7] != (3 if kind == 'render' else 0):
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7]})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if kind == 'copy':
            c['publications'] += 1
            if st.nr[0x69] != 0x80:
                fail('overlay not on after publish', {})
            picture = _pixels(st)
            want = {} if ov.fresh else dict(ov.back)
            if picture != want:
                diff = [k for k in set(picture) | set(want) if picture.get(k) != want.get(k)]
                fail('overlay differs from the model', {'pc': hex(pc), 'count': len(diff), 'ex': sorted(diff)[:6]})
            c['overlay pixels compared'] += len(picture)
            # Every lit pixel is a set bit of the bitmap the copy wrote.
            m2 = ref.memory
            for (x, y), val in picture.items():
                a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
                if not m2[a] & (128 >> (x & 7)):
                    fail('overlay pixel over a clear bitmap bit', {'x': x, 'y': y})
                    break
            ov.fresh = True
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), pcs, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


def unit_tests(patch, states):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R, the caller's clock,
    the MMU restored."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        if pc == COPY_IN:
            target, kind, ret, sp0 = None, 'copy', COPY_RET, 0x5DBF
        elif pc == RENDER:
            target, kind, ret, sp0 = 0xA31E, 'render', 0xA31E, regs[12]
        elif pc == WAIT:
            target, kind, ret, sp0 = patch.syms['h_halt'], 'wait', HALT, regs[12]
        else:
            target, _, kind = patch.site_info[pc]
            ret, sp0 = target, regs[12]
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    if kind in ('hide', 'render', 'wait', 'big', 'small'):
                        ref.opcodes[mem[pc]]()
                        stop, sp = target, None
                    else:
                        n = 0
                        while n == 0 or ref.registers[24] != ret or ref.registers[12] != sp0:
                            ref.opcodes[ref.memory[ref.registers[24]]]()
                            n += 1
                        stop, sp = ret, sp0
                    st = State(patch)
                    if kind == 'wait':
                        st.page[V_SPEED - 0x2000] = speed
                    got, v, model = run_hook(patch, st, _patched(patch, mem), rr, stop, sp, speed=3 if kind == 'wait' else speed)
                    if kind == 'wait':
                        pass
                    if any((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i] for i in CMP if not (kind == 'wait' and i == 24)):
                        c['ABI registers differ!'] += 1
                    if kind == 'render':
                        if model.nr[7] != 3 or st.page[V_SPEED - 0x2000] != speed:
                            c['render window clock wrong!'] += 1
                    elif model.nr[7] != speed:
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
    mutate('R off by one', bytes((0x3E, 0x100 - 12, 0xCD)), bytes((0x3E, 0x100 - 11)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('x off by one', bytes.fromhex('C6186F'), bytes.fromhex('C6196F'))
    mutate('wrong ink', bytes.fromhex('360FCB11'), bytes.fromhex('360ECB11'))
    mutate('mask ignored', bytes.fromhex('36FF2C'), bytes.fromhex('00002C'))
    mutate('MMU slot 0 left mapped', bytes.fromhex('ED9150FFC9'), bytes.fromhex('00000000C9'))
    mutate('stale figures never cleared', bytes.fromhex('3A373EB7C8AF'), bytes.fromhex('3A373EB7C9AF'))
    mutate('overlay never published', bytes.fromhex('ED916980'), bytes.fromhex('ED916900'))
    mutate('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('ED916980'))
    return out


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2)."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


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
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad
