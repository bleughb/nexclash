"""Atom Ant Enhanced: the play window and panel on a full Layer 2, from the Spec256 set. The default (atom_ant.Patch) has no hooks and is
not touched by this module. See asm/atom_ant_hooks.asm."""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import atom_ant as A, atom_ant_art as ART, hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/atom_ant.json'
CMP = tuple(hooklib.CMP_R)
L2_A, L2_B = 16, 19
V_Q, V_QBUF, V_SPEED = 0x3E3A, 0x3E80, 0x3E30
DIGIT_CELLS = [(3, c) for c in (4, 10, 15, 17, 18, 20, 21, 22, 23, 24, 25, 29)]   # panel rows from 20: what BD76 to BDFD print, and stay ULA text
TILES_SITE, PLOT_SITE, END_SITE, COPY_SITE, CLS_SITE = 0x9E3E, 0xB112, 0x9E44, 0x9E6B, 0xA16C


class Patch:
    name = 'Atom Ant 128K: Enhanced colours on a full Layer 2'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000

    def __init__(self, source, setpath, panelpath, palettepath, keep_art=None):
        self.source = str(source)
        h = json.loads(PROFILE.read_text())['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        pal, self.moved = ART.palette(json.loads(Path(palettepath).read_text()))
        self.stub_extra = bytes.fromhex(h['setup']) + pal
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        s = zt.Z80Snapshot(str(source))
        mem = bytearray(65536)
        mem[0x4000:0x8000] = s.banks[5]
        mem[0x8000:0xC000] = s.banks[2]
        mem[0xC000:] = s.banks[0]
        self.art = keep_art or ART.compile_art(setpath, mem)
        self.pages, self.index, self.images, self.stats = self.art
        self.panel, self.holes, self.play_shots, self.all_shots = ART.panel_pages(Path(panelpath).read_bytes(), DIGIT_CELLS)
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x1A00:0x1C00] = bytes(512)
        self.ram[0x1A00:0x1A00 + len(self.index)] = self.index
        self.ram[0x1E00:0x2000] = bytes(512)
        self.ram[self.syms['V_BACK'] - 0x2000] = L2_A
        self.ram[V_Q - 0x2000:V_Q - 0x2000 + 2] = V_QBUF.to_bytes(2, 'little')
        s_ = self.syms
        self.sites = [(TILES_SITE, b'\xcd\xfa\xa1', b'\xcd' + zt.w16(s_['h_tiles'])),
                      (PLOT_SITE, b'\x4e\x23\x46', b'\xc3' + zt.w16(s_['h_plot'])),
                      (END_SITE, b'\xcd\x76\xab', b'\xc3' + zt.w16(s_['h_render_end'])),
                      (COPY_SITE, b'\xcd\x84\xa1', b'\xcd' + zt.w16(s_['h_copy'])),
                      (CLS_SITE, b'\x21\x00\x40', b'\xc3' + zt.w16(s_['h_cls']))]
        self._banks()

    def _banks(self):
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_tiles', 'h_plot', 'h_render_end', 'h_copy', 'h_cls'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        extra = {12: bytes(self.ram) + bytes(self.page)}
        # Layer 2: the panel in the sixth page (rows 160-191) of each buffer
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
        if not A.is_atom_ant(snap):
            raise ValueError('Not the 128K start state of Atom Ant (tape MD5 %s)' % A.TAPE_MD5)
        b2 = bytearray(snap.banks[2])
        for a, old, new in self.sites:
            at = a - 0x8000
            if bytes(b2[at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            b2[at:at + len(new)] = new
        banks = dict(snap.banks)
        banks[2] = bytes(b2)
        snap.banks = type(snap.banks)(sorted(banks.items()))


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
            return self.patch.pages[m][a & 8191]
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
        self.pages = {p: bytearray(b'\xff' * 8192) for p in list(range(32, 37)) + list(range(38, 43))}
        self.nr = {0x12: L2_A, 0x69: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'atom-ant-hook')
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
    """The expected picture and the game's own buffer, from the map and the plots, read from the game's state."""
    def __init__(self, patch):
        self.patch = patch
        self.images = {(t, f, s): (p, at, w, r) for t, f, s, p, at, w, r in patch.images}
        self.reset(b'', 0)
        self.queue = []

    def reset(self, mem, scroll):
        self.pic = [bytearray(b'\xff' * 256) for _ in range(160)]
        self.mono = [bytearray(24) for _ in range(160)]

    def tiles(self, mem):
        scroll = mem[0xF876]
        ptr = mem[0x8C2A] | mem[0x8C2B] << 8
        self.reset(mem, scroll)
        pages = self.patch.pages
        for band in range(11):
            for col in range(12):
                t = mem[ptr]
                ptr += 1
                page = pages[ART.TILE_PAGE + (t >> 5)]
                base = (t & 31) << 8
                for r in range(16):
                    y = -1 - scroll + band * 16 + r
                    if 0 <= y < 160:
                        self.pic[y][32 + col * 16:48 + col * 16] = page[base + r * 16:base + r * 16 + 16]
                        a = 0x5DC2 + t * 32 + r * 2
                        self.mono[y][col * 2] = mem[a]
                        self.mono[y][col * 2 + 1] = mem[a + 1]

    def plot(self, mem, hl):
        y, x, n, ty = mem[hl], mem[hl + 1], mem[hl + 2], mem[hl + 3]
        t = 0 if ty == 0 else 2 if ty == 2 else 1
        if x & 1 and t != 2:
            return 'odd x'
        sh = 0 if t == 2 else (x & 6) >> 1
        img = self.images.get((t, n, sh))
        if img is None:
            return 'figure out of range'
        page, at, w, rows = img
        data = self.patch.pages[page]
        col = x >> 3
        wide = w // 8
        table, shifts = {0: (0xF877, 0xF8AF), 1: (0xF88D, 0xF8B7), 2: (0xF8A3, None)}[t]
        src = mem[table + 2 * n] | mem[table + 2 * n + 1] << 8
        if shifts:
            o = mem[shifts + 2 * sh] | mem[shifts + 2 * sh + 1] << 8
            src += o
        for r in range(rows):
            row = y + r - 24
            if not 0 <= row < 160:
                continue
            for c in range(wide):
                if col + c < 24:
                    mk, g = mem[src + (r * wide + c) * 2], mem[src + (r * wide + c) * 2 + 1]
                    self.mono[row][col + c] = (self.mono[row][col + c] & mk) | g
                for b in range(8):
                    xx = col * 8 + c * 8 + b
                    if xx >= 192:
                        continue
                    v = data[at + r * w + c * 8 + b]
                    if v != ART.SKIP:
                        self.pic[row][32 + xx] = v
        return None


def _flat(sim):
    m = sim.memory
    return bytes(16384) + bytes(m.memory[1]) + bytes(m.memory[2]) + bytes(m.memory[3])


def _patched(patch, mem):
    out = bytearray(mem)
    for a, old, new in patch.sites:
        out[a:a + len(new)] = new
    return out


def verify(patch, rzx_path, stop=None, collect=0):
    """Replay the original; at every changed site run the hook on a copy of the state and compare with the original's run: every register
    with R, all 48K RAM. At every copy: Layer 2 against a picture built from the map and the plots, and the game's own buffer against the
    same model in mono, so a writer the hooks missed fails. Nothing from the screen rows of the buffer is exempt."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    pic = Picture(patch)

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    pcs = {TILES_SITE, PLOT_SITE, END_SITE, COPY_SITE, CLS_SITE}

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        patched = _patched(patch, mem)
        ref = simpool.machine(Simulator, list(mem), regs, 'aa-ref')
        R = ref.registers
        if regs[26] and pc != CLS_SITE:
            fail('interrupts on at a hook', {'pc': hex(pc)})
        speed = 0
        expect_clock = 0
        cmp_sp = True
        if pc == TILES_SITE:
            kind = 'tiles'
            ref.opcodes[mem[pc]]()
            stop_pc, stop_sp = 0xA1FA, None
            expect_clock = 3
            pic.tiles(mem)
            pic.queue = []
        elif pc == PLOT_SITE:
            kind = 'plot'
            for _ in range(3):
                ref.opcodes[ref.memory[R[24]]]()
            stop_pc, stop_sp = 0xB115, None
            speed = 3
            expect_clock = 3
            why = pic.plot(mem, regs[6] << 8 | regs[7])
            if why:
                c[why] += 1
            c['figures'] += 1
        elif pc == END_SITE:
            kind = 'end'
            ref.opcodes[mem[pc]]()
            stop_pc, stop_sp = 0xAB76, None
            speed = 3
        elif pc == COPY_SITE:
            kind = 'copy'
            sp = regs[12]
            n = 0
            while n == 0 or R[24] != pc + 3 or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stop_pc, stop_sp = pc + 3, sp
        else:
            kind = 'cls'
            ref.opcodes[mem[pc]]()
            stop_pc, stop_sp = 0xA16F, None
        got, v, model = run_hook(patch, st, patched, regs, stop_pc, stop_sp, speed=speed)
        if kind == 'tiles':
            pass
        for i in CMP:
            if (bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': R[i], 'got': got[i], 'kind': kind})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        if kind == 'copy':
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
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        if kind == 'cls' and st.nr[0x69] != 0:
            fail('overlay not hidden', {})
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['R comparisons'] += 1
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
            c['pixels compared'] += 30720
            # The game's own buffer: nothing the hooks do not see wrote to it.
            buf = 0x8DAC
            bad = 0
            for y in range(160):
                row = mem[buf + y * 24:buf + y * 24 + 24]
                if row != bytes(pic.mono[y]):
                    bad += 1
            if bad:
                fail('game buffer differs from the mono model', {'rows': bad, 'pub': c['publications']})
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
                    want_clock = speed
                    run_speed = speed
                    if pc == TILES_SITE:
                        ref.opcodes[mem[pc]]()
                        stop, sp = 0xA1FA, None
                        want_clock = 3
                    elif pc == PLOT_SITE:
                        for _ in range(3):
                            ref.opcodes[ref.memory[R[24]]]()
                        stop, sp = 0xB115, None
                    elif pc == END_SITE:
                        ref.opcodes[mem[pc]]()
                        stop, sp = 0xAB76, None
                        st.page[V_SPEED - 0x2000] = speed
                        run_speed = 3
                    elif pc == COPY_SITE:
                        s0 = rr[12]
                        n = 0
                        while n == 0 or R[24] != pc + 3 or R[12] != s0:
                            ref.opcodes[ref.memory[R[24]]]()
                            n += 1
                        stop, sp = pc + 3, s0
                    else:
                        ref.opcodes[mem[pc]]()
                        stop, sp = 0xA16F, None
                    got, v, model = run_hook(patch, st, _patched(patch, mem), rr, stop, sp, speed=run_speed)
                    if any((bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i] for i in CMP):
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
    mutate('tile rows one apart too many', bytes.fromhex('111000'), bytes.fromhex('111100'))
    mutate('figure x off by one', bytes.fromhex('C6203242'), bytes.fromhex('C6213242'))
    mutate('figure y off by one', bytes.fromhex('D618FEA0'), bytes.fromhex('D617FEA0'))
    mutate('skip pixels drawn', bytes.fromhex('FEFE2801'), bytes.fromhex('FEFD2801'))
    mutate('figures never drawn', bytes.fromhex('ED5B3A3E7BBD28'), bytes.fromhex('ED5B3A3E7BBD18'))
    mutate('MMU slot 2 left mapped', bytes.fromhex('ED91520AC9'), bytes.fromhex('00000000C9'), last=True)
    mutate('MMU slot 0 left mapped', bytes.fromhex('ED9150FF'), bytes.fromhex('00000000'), last=True)
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
