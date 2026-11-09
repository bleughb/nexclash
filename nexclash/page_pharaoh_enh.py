"""Page and the Curse of the Pharaoh, Enhanced: the Spec256 set's colours, faithfully, on a Layer 2.

The Layer 2 holds the 8-bit value Spec256's planes would hold: tiles overwrite, figures and items XOR. Value FF, "the
attribute's colour", is transparent, so the ULA shows it. The set is read from a local .256 (never in this repo); see
asm/page_pharaoh_enh_hooks.asm. The default mode is nexclash/page_pharaoh.py, unchanged.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json, os
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/page_pharaoh_enh.json'
CMP = tuple(hooklib.CMP_R)
SITES = {0x8BB7: (0xCD, 0x8C63, 'h_both', 'both'), 0x8BAA: (0xCD, 0x8C4E, 'h_old', 'old'), 0x7F8A: (0xCD, 0x8C4E, 'h_old', 'old'),
         0x868A: (0xCD, 0x8C4E, 'h_old', 'old'), 0x8BC4: (0xCD, 0x8C5D, 'h_new', 'new'),
         0x86B8: (0xCD, 0x8743, 'h_tile', 'tile'), 0x878F: (0xCD, 0x8743, 'h_tile', 'tile'), 0x8AAF: (0xCD, 0x8743, 'h_tile', 'tile'),
         0x859B: (0xC3, 0x87AB, 'h_item', 'item'), 0x85BD: (0xC3, 0x87AB, 'h_item', 'item'), 0x8304: (0xCD, 0x7F9B, 'h_ula', 'ula'),
         0x8364: (0xCD, 0x881D, 'h_room', 'room'), 0x7F70: (0xCD, 0x881D, 'h_room', 'room'),
         0x8367: (0xCD, 0x8092, 'h_after1', 'after'), 0x7F73: (0xCD, 0x8572, 'h_after2', 'after'),
         0x7743: (0xCD, 0x0DAF, 'h_cls_menu', 'cls'), 0x7815: (0xCD, 0x0DAF, 'h_cls', 'cls'), 0x78D4: (0xCD, 0x0DAF, 'h_cls', 'cls'), 0x7955: (0xCD, 0x0DAF, 'h_cls', 'cls')}
SIGNATURE = {0x8BB7: 'CD638C', 0x8BAA: 'CD4E8C', 0x8364: 'CD1D88', 0x7815: 'CDAF0D', 0x859B: 'C3AB87', 0x8304: 'CD9B7F'}
L2_PAGES = list(range(32, 38))
TABLES = ((38, 0x9050, 0xA628), (44, 0x7A00, 0x7B00), (45, 0xDB79, 0xE37E))
FIG_LO = 0x9050
FIG_HI = 0xA350              # figures; the tiles run on from here to A627
SET_ENV = 'NEXCLASH_PAGE_SET'


def load_profile():
    return json.loads(PROFILE.read_text())


def _bank(a):
    return (5, a - 0x4000) if a < 0x8000 else (2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000)


class Set256:
    """The set's planes and master, by 64K address. Value of a pixel: bit k of plane i is bit i of its value."""
    def __init__(self, path=None):
        d = open(path or os.environ[SET_ENV], 'rb').read()
        self.d = d
        self.cache = {}

    def word(self, a):
        b, off = _bank(a)
        return (b * 16384 + off) * 9

    def values(self, a):
        v = self.cache.get(a)
        if v is None:
            s = self.word(a)
            pl = self.d[s:s + 8]
            v = bytes(sum(((pl[i] >> (7 - k)) & 1) << i for i in range(8)) for k in range(8))
            self.cache[a] = v
        return v

    def master(self, a):
        return self.d[self.word(a) + 8]


def palette(rgb):
    """The set's palette as NR 0x44 pairs. Value 255 is the transparent colour; no other value may land on it."""
    out = bytearray()
    for i, c in enumerate(rgb):
        r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
        r3, g3, b3 = round(r * 7 / 255), round(g * 7 / 255), round(b * 7 / 255)
        top = r3 << 5 | g3 << 2 | b3 >> 1
        low = b3 & 1
        if i == 255:
            top, low = 0xE3, 1
        elif top == 0xE3:
            top = 0xE7
        out += bytes((top, low))
    return bytes(out)


def tables(s):
    """{page: 8192 bytes}: 8 values a byte for each coloured range."""
    pages = {}
    for page, lo, hi in TABLES:
        out = bytearray()
        for a in range(lo, hi):
            out += s.values(a)
        if lo == FIG_LO:        # figure rows in screen order: s..7, 8..15, 0..s-1, s from the pre-shift
            for a in range(lo, FIG_HI, 2):
                sh = ((a - lo) >> 5 & 3) * 2
                v0, v1 = s.values(a), s.values(a + 1)
                out[(a - lo) * 8:(a - lo) * 8 + 16] = v0[sh:] + v1 + v0[:sh]
        data = bytes(out)
        for i in range(0, len(data), 8192):
            pages[page + i // 8192] = data[i:i + 8192].ljust(8192, b'\0')
    return pages


class Patch:
    name = 'Page and the Curse of the Pharaoh: the Spec256 colours on Layer 2'
    uses_printer_buffer = True
    keep_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000
    tail_addr = 0x5B00

    def __init__(self, source=None, set_path=None, palette_path=None):
        self.source = str(source) if source else None
        self.set = Set256(set_path)
        rgb = json.load(open(palette_path or os.environ[SET_ENV + '_PALETTE']))
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup']) + palette(rgb)
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x1E00:0x2000] = bytes(512)
        self.sites = [(a, bytes((op,)) + zt.w16(t), bytes((op,)) + zt.w16(self.syms[s])) for a, (op, t, s, k) in SITES.items()]
        self.tables = tables(self.set)
        self._banks()

    def _banks(self):
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_both', 'h_old', 'h_new', 'h_tile', 'h_item', 'h_ula', 'h_room', 'h_after1', 'h_after2', 'h_cls', 'h_cls_menu'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 6] = self.ram[at:at + 6]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}
        for bank in sorted({p // 2 for p in self.tables}):
            self.extra_banks[bank] = self.tables.get(bank * 2, bytes(8192)) + self.tables.get(bank * 2 + 1, bytes(8192))

    def apply(self, snap):
        banks = {i: bytearray(snap.banks[i]) for i in snap.banks}
        for a, v in SIGNATURE.items():
            b, at = _bank(a)
            if bytes(banks[b][at:at + len(v) // 2]) != bytes.fromhex(v):
                raise ValueError('Not the supported Page release')
        for a, old, new in self.sites:
            b, at = _bank(a)
            if bytes(banks[b][at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[b][at:at + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in banks)


def build(source, destination, set_path=None, palette_path=None):
    p = Patch(source, set_path, palette_path)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


class View:
    """64K view of the game RAM + the pages the hook maps, per the model's MMU."""
    DEFAULT = (255, 255, 10, 11, 4, 5, 0, 1)

    def __init__(self, mem, patch, page, pages):
        self.mem = bytearray(mem)
        self.patch, self.page, self.pages = patch, page, pages
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        s = a >> 13
        m = self.model.nr.get(0x50 + s, self.DEFAULT[s])
        if a < 0x4000:
            if m == 255:
                return self.patch.page[a - 0x2000] if a >= 0x2000 else self.mem[a]
            if m == 24:
                return self.page[a - 0x2000]
            return self.pages[m][a & 8191]
        if m != self.DEFAULT[s]:
            return self.pages[m][a & 8191]
        return self.mem[a]

    def __setitem__(self, a, v):
        s = a >> 13
        m = self.model.nr.get(0x50 + s, self.DEFAULT[s])
        if a < 0x4000:
            if m == 24:
                self.page[a - 0x2000] = v
            elif m != 255:
                self.pages[m][a & 8191] = v
            return
        if m != self.DEFAULT[s]:
            self.pages[m][a & 8191] = v
            return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line)
        self.nr.update({0x50 + i: p for i, p in enumerate(View.DEFAULT)})
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
        self.pages = {p: bytearray(8192) for p in L2_PAGES}
        for p, d in patch.tables.items():
            self.pages[p] = bytearray(d)
        self.nr = {0x12: 16, 0x69: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'page-enh-hook')
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
    """The expected Layer 2: what the set's planes would hold, by an independent reading of the game's state."""
    def __init__(self, s):
        self.set = s
        self.px = bytearray(48 * 1024)

    def clear(self):
        self.px = bytearray(48 * 1024)

    def figure(self, mem, ix, new):
        if new:
            y, x, sp, fr = mem[ix + 8], mem[ix + 9], mem[ix + 6], mem[ix + 7]
        else:
            y, x, sp, fr = mem[ix + 3], mem[ix + 4], mem[ix + 1], mem[ix + 2]
        table = mem[0x7D39] | mem[0x7D3A] << 8
        a = (mem[(table + 2 * sp) & 0xFFFF] + fr) & 255
        base = (mem[0x7D3B] | mem[0x7D3C] << 8) + ((a >> 1) << 8) + ((a & 1) << 7) + ((x & 6) << 4)
        s6 = x & 6
        x0 = x & 0xF8
        for r in range(16):
            v0, v1 = self.set.values((base + 2 * r) & 0xFFFF), self.set.values((base + 2 * r + 1) & 0xFFFF)
            row = v0[s6:] + v1 + v0[:s6]
            at = (y + r) * 256
            for i, c in enumerate(row):
                self.px[at + ((x0 + s6 + i) & 255)] ^= c

    def tile(self, mem, code):
        src = (mem[0x869B] | mem[0x869C] << 8) + code * 8
        y, x = mem[0x7D2F] * 8, (mem[0x7D30] & 31) * 8
        for r in range(8):
            self.px[(y + r) * 256 + x:(y + r) * 256 + x + 8] = self.set.values((src + r) & 0xFFFF)

    def item(self, mem, src):
        y, x = mem[0x7D2F], mem[0x7D30]
        for r in range(16):
            row = self.set.values((src + 2 * r) & 0xFFFF) + self.set.values((src + 2 * r + 1) & 0xFFFF)
            at = (y + r) * 256
            for i, c in enumerate(row):
                self.px[at + ((x + i) & 255)] ^= c


def _flat(sim):
    return bytes(sim.memory)


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original; at every changed site run the hook on a copy of the state and compare with the original's run to
    its return (or the target's entry): every register with R, all 48K RAM except 32 bytes of dead stack the original's call
    chain wrote. The whole Layer 2 against an independent model from the set's planes, after every hook that draws."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    ov = Overlay(patch.set)

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
        op, target, sym, kind = SITES[pc]
        if mem[pc:pc + 3] != bytes((op, target & 255, target >> 8)):
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        ref = simpool.machine(Simulator, list(mem), regs, 'ppe-ref')
        ix = regs[8] << 8 | regs[9]
        if kind in ('room', 'cls', 'after'):
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched_mem(mem), regs, target)
            if kind == 'after':
                pass
            elif kind == 'room':
                if st.nr[0x69] != 0x80:
                    fail('overlay not on after a room', {})
            else:
                ov.clear()
                if st.nr.get(0x69) != (0x80 if pc == 0x7743 else 0):
                    fail('overlay not hidden' if pc != 0x7743 else 'menu overlay not shown', {})
        else:
            sp = regs[12]
            if op == 0xC3:
                ret, want_sp = mem[sp] | mem[sp + 1] << 8, sp + 2
            else:
                ret, want_sp = (pc + 3) & 0xFFFF, sp
            n = 0
            R = ref.registers
            while n == 0 or R[24] != ret or R[12] != want_sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            if kind == 'both':
                ov.figure(mem, ix, False)
                ov.figure(mem, ix, True)
            elif kind == 'old':
                ov.figure(mem, ix, False)
            elif kind == 'new':
                ov.figure(mem, ix, True)
            elif kind == 'tile':
                ov.tile(mem, regs[0])
            elif kind == 'item':
                ov.item(mem, regs[6] << 8 | regs[7])
            got, v, model = run_hook(patch, st, patched_mem(mem), regs, ret, want_sp)
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        if kind not in ('room', 'cls', 'after'):
            sp = regs[12]
            for a in range(sp - 32, sp):
                expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x56] != 0 or model.nr[0x57] != 1:
            fail('MMU not restored', {'pc': hex(pc)})
        if kind != 'room' and model.nr[7] != 0:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7]})
        if kind == 'room' and model.nr[7] != 3:
            fail('room not at 28 MHz', {'pc': hex(pc), 'value': model.nr[7]})
        io = [x for x in model.io if x[0] not in (0xBF3B, 0xFF3B)] if kind == 'ula' else model.io
        if io:
            fail('extra game I/O', {'pc': hex(pc), 'io': io[:4]})
        if kind == 'ula' and model.io[-2:] != [(0xBF3B, 0x40), (0xFF3B, 0)]:
            fail('ULA+ not turned off', {'io': model.io[-4:]})
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        pic = b''.join(bytes(st.pages[p]) for p in L2_PAGES)
        if pic != bytes(ov.px):
            d = [i for i, (x, y) in enumerate(zip(pic, ov.px)) if x != y]
            fail('overlay differs from the model', {'pc': hex(pc), 'sym': sym, 'count': len(d), 'ex': [(i & 255, i >> 8, pic[i], ov.px[i]) for i in d[:6]]})
        c['overlay pictures compared'] += 1
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
        op, target, sym, kind = SITES[pc]
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
                    if kind in ('room', 'cls', 'after'):
                        ref.opcodes[mem[pc]]()
                        stop, sp = target, None
                    else:
                        s0 = rr[12]
                        ret, sp = (mem[s0] | mem[s0 + 1] << 8, s0 + 2) if op == 0xC3 else ((pc + 3) & 0xFFFF, s0)
                        n = 0
                        while n == 0 or ref.registers[24] != ret or ref.registers[12] != sp:
                            ref.opcodes[ref.memory[ref.registers[24]]]()
                            n += 1
                        stop = ret
                    st = State(patch)
                    got, v, model = run_hook(patch, st, patched, rr, stop, sp, speed=speed)
                    if any((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    if kind not in ('ula', 'room', 'after') and model.nr[7] != speed:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr[0x56] != 0 or model.nr[0x57] != 1:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def clone():
        b = copy.copy(patch)
        b.ram = bytearray(patch.ram)
        return b

    def mutate(name, old, new, last=False):
        b = clone()
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.rfind(old) if last else code.find(old)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new)] = new
        b._banks()
        out[name] = b
    mutate('R off by one', bytes((0x3E, 0x100 - 21, 0xCD)), bytes((0x3E, 0x100 - 20)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('x off by one column', bytes.fromhex('E6FE4F'), bytes.fromhex('E6F64F'))
    mutate('XOR made a plain write', bytes.fromhex('1AAE771C2C'), bytes.fromhex('1A00771C2C'), last=True)   # the figures' loop
    mutate('slot 7 left mapped', bytes.fromhex('ED915701C9'), bytes.fromhex('00000000C9'))
    mutate('old place never taken off', bytes.fromhex('CDE08BCD') + zt.w16(patch.syms['l2_fig']), bytes.fromhex('CDE08B000000'))
    mutate('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('00000000'))
    mutate('overlay not cleared', bytes.fromhex('3600D5'), bytes.fromhex('36FFD5'))
    mutate('menu overlay not shown', bytes.fromhex('ED916980F5'), bytes(4) + b'\xF5')
    mutate('ULA+ left on', bytes.fromhex('013BBF3E40ED79'), bytes.fromhex('013BBF3E400000'))
    # wrong colours: one table page shifted by one value
    b = clone()
    b.tables = dict(patch.tables)
    b.tables[38] = patch.tables[38][1:] + patch.tables[38][:1]
    b._banks()
    out['wrong colours'] = b
    return out


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}
