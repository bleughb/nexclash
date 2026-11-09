"""Booty (John F. Cain, Firebird, 1984, 48K): the original game by default; Enhanced colours from the Spec256 set on a Layer 2.

Every figure and all the scenery are whole 8x8 cells printed with their own attribute, so the play area has no colour clash and
the default look runs no hook. Enhanced repeats each print on a Layer 2 over the unchanged ULA, from a table of the set's pixels
kept by the graphic's own address; the set's value FF (use the attribute) is transparent. See asm/booty_hooks.asm, games/booty.md.
"""
from collections import Counter, defaultdict
from pathlib import Path
import json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/booty.json'
PAL_NAME = 'spec256-palette.pal'     # Spec256-Games' palette, beside the .256 (licence not established: never in this repo)
PAL_MD5 = 'b095dc99a047bab844b87b06657b0a7a'
SOURCE_MD5 = '0b2cb0c5a033e853d62c3a5e492f8bc0'
CMP = tuple(hooklib.CMP_R)
SIGNATURE = {0xE9D9: '01D0070B78B120FBC9', 0xE6F9: '1B0608', 0xA834: '1B0608'}
# (original, symbol, kind, where original and hook meet again)
SITES = {0xA834: ('1B0608', 'h_a', 'cell', 0xA837), 0xE6F9: ('1B0608', 'h_e', 'cell', 0xE6FC), 0xCE41: ('CDBED4', 'h_hid', 'hidden', 0xD4BE),
         0xE522: ('2A845C', 'h_f1', 'fill', 0xE525), 0xE564: ('2A845C', 'h_f2', 'fill', 0xE567),
         0xCD9D: ('110040', 'h_title', 'title', 0xCDA0), 0xE9D9: ('01D007', 'h_dly1', 'delay', 0xE9E1), 0xD3A6: ('018813', 'h_dly2', 'delay', 0xD3AE),
         0xE0A9: ('CD04A8', 'h_room', 'room', 0xA804), 0xE0AC: ('21003C', 'h_re', 'roomend', 0xE0AF),
         0xEED7: ('11ECA0', 'h_comp', 'compose', 0xEEDA),}
ROM_SITES = {0x0B9B: ('3A915C', 'h_rom', 'rom', 0x0B9E), 0x0E44: ('C5CD9B', 'h_cll', 'cll', None)}
ALL_SITES = {**SITES, **ROM_SITES}
ALT_PAGE, LOW_PAGE = 24, 26
PLAY_PAGE, TITLE_PAGE, FONT_PAGE, TABLE_PAGE = 32, 38, 44, 46
V_IN = 0x3BF0
V_ILEAVE = 0x3E3D
VECTOR = 0x3BFF                     # I = 3B in a hook or a room
I_GAME = 0xF4
DECISIONS = {'figures': 'unchanged: whole cells with their own attribute', 'scenery': 'unchanged', 'pace': 'original: no hook in the default look',
             'outline': 'none', 'enhanced': 'the Spec256 set on Layer 2'}
PUBLISHER = 'Firebird, 1984'
PLANES = 131072 * 9


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_booty(snap):
    try:
        mem = snap.memory if hasattr(snap, 'memory') else (bytes(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0])
        return all(bytes(mem[a:a + len(bytes.fromhex(v))]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (AttributeError, KeyError, TypeError, IndexError):
        return False


class ColourSet:
    """The player's own .256: the planes of a graphic byte, and the pictures. Nothing of it is in this repository."""
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        gr = self.d.find(b'GRX1', PLANES)
        self.rom = self.d[gr + 4:gr + 4 + (0x4000 - 0x3D00) * 8]

    def planes(self, a):
        if a < 0x4000:
            o = (a - 0x3D00) * 8
            return self.rom[o:o + 8] if a >= 0x3D00 else bytes(8)
        w = ((5, 2, 0)[(a >> 14) - 1] * 16384 + (a & 16383)) * 9
        return self.d[w:w + 8]

    def master(self, a):
        return self.d[((5, 2, 0)[(a >> 14) - 1] * 16384 + (a & 16383)) * 9 + 8]

    def pixels(self, a):
        """The eight colour values of the byte at a. A06C-A0EB: the game clears them at its start (CD56) before any print."""
        if 0xA06C <= a < 0xA0EC:
            return bytes(8)
        pl = self.planes(a)
        return bytes(sum(((pl[p] >> (7 - k)) & 1) << p for p in range(8)) for k in range(8))

    def title(self):
        """The title on Layer 2, row by row (the copy at 6978 the game shows again). A byte the sparkle may change (the copy's
        byte 5: D0B3) stays on the ULA, as the set's value FF does."""
        out = bytearray(6144 * 8)
        for y in range(192):
            row = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
            for c in range(32):
                a = 0x6978 + (row | c)
                out[y * 256 + c * 8:y * 256 + c * 8 + 8] = b'\xff' * 8 if self.master(a) == 5 else self.pixels(a)
        return bytes(out)


def spec256_palette(path):
    """The Spec256 palette (PAL_NAME beside the .256 at path; a declared, MD5-pinned input, never in the repo) -> 256 RGB."""
    import hashlib
    p = Path(path).resolve().parent / PAL_NAME
    if not p.is_file():
        raise ValueError('no %s beside %s: the Enhanced colours need it' % (PAL_NAME, Path(path).name))
    raw = p.read_bytes()
    if hashlib.md5(raw).hexdigest() != PAL_MD5:
        raise ValueError('%s MD5 %s, the published build used %s' % (PAL_NAME, hashlib.md5(raw).hexdigest(), PAL_MD5))
    v = [int(x) for x in raw.decode('ascii').split()]
    if len(v) != 768:
        raise ValueError('%s: %d values, expected 768' % (PAL_NAME, len(v)))
    return [tuple(v[i:i + 3]) for i in range(0, 768, 3)]


def art(path):
    """-> dict(font page, table pages, title banks, palette). Palette: the Spec256 palette (beside the .256) at 9 bits;
    255 is the transparent colour."""
    s = ColourSet(path)
    font = bytearray(8192)
    for a in range(0x3D00, 0x4000):
        font[(a & 0x3FF) * 8:(a & 0x3FF) * 8 + 8] = s.pixels(a)
    table = bytearray(32768 * 8)
    for a in range(0x8000, 0x10000):
        table[(a - 0x8000) * 8:(a - 0x8000) * 8 + 8] = s.pixels(a)
    entries = []
    for r, g, b in spec256_palette(path):
        hi = ((r >> 5) << 5) | ((g >> 5) << 2) | (b >> 6)
        lo = (b >> 5) & 1
        if hi == 0xE3:
            hi = 0xE2
        entries.append((hi, lo))
    entries[255] = (0xE3, 1)
    title = s.title()
    used = set(table) | set(font) | set(title)
    return dict(font=bytes(font), table=bytes(table), title=title, l2pal=bytes(x for e in entries for x in e), used=len(used - {255}), set=s)


class Patch:
    uses_printer_buffer = False
    keep_printer_buffer = True
    hook_page_data = b''
    tail_addr = 0x5D00

    def __init__(self, source=None, enhanced=False, art=None):
        self.source = str(source) if source else None
        self.enhanced = enhanced
        self.art = art
        self.name = 'Booty: ' + ('Enhanced colours from the Spec256 set on Layer 2' if enhanced else 'the original game, Sinclair ROM as the whole alt ROM')
        rom = zt.rom48()
        if not enhanced:
            self.page = bytearray(rom[0x2000:0x4000])
            self.slot1 = (25, 0x3C00)
            self.altrom = (0x3C00, 0x3C14)
            self.extra_banks = {12: bytes(8192) + bytes(self.page)}
            self.sites = ()
            self.stub_extra = b''
            self.setup_call = None
            return
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        st = bytearray(bytes.fromhex(h['setup']))
        at = self.syms['e_palette'] - self.syms['setup']
        st[at:at + 512] = art['l2pal']
        self.stub_extra = bytes(st)
        self.setup_call = self.syms['setup']
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = (0x2800, 0x3D00)
        self.ram = bytearray(rom[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[V_IN - 0x2000] = 0
        self.ram[0x1E00:0x2000] = bytes(512)
        self.ram[V_ILEAVE - 0x2000] = I_GAME
        self.ram[VECTOR - 0x2000:VECTOR - 0x2000 + 2] = self.syms['isr_w'].to_bytes(2, 'little')
        low = bytearray(rom[0:0x2000])
        self.rom_sites = []
        for a, (old, sym, k, stop) in ROM_SITES.items():
            old = bytes.fromhex(old)
            if bytes(low[a:a + 3]) != old:
                raise ValueError('48K ROM differs at %04X' % a)
            new = b'\xc3' + zt.w16(self.syms[sym])
            low[a:a + 3] = new
            self.rom_sites.append((a, old, new))
        self.altrom_low = (LOW_PAGE, bytes(low))
        self.sites = [(a, bytes.fromhex(old), (b'\xcd' if k in ('hidden', 'room') else b'\xc3') + zt.w16(self.syms[sym])) for a, (old, sym, k, stop) in SITES.items()]
        self._banks()

    def _banks(self):
        rom = zt.rom48()
        self.page = bytearray(rom[0x2000:0x4000])
        for sym in ('h_rom', 'h_a', 'h_e', 'h_hid', 'h_f1', 'h_f2', 'h_cll', 'h_title', 'h_dly1', 'h_dly2', 'h_comp', 'h_room', 'h_re'):
            at = self.syms[sym] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        a, b = self.syms['isr_w'] - 0x2000, self.syms['isr_end'] - 0x2000
        self.page[a:b] = self.ram[a:b]
        self.page[V_IN - 0x2000] = 0
        self.page[VECTOR - 0x2000:VECTOR - 0x2000 + 2] = self.ram[VECTOR - 0x2000:VECTOR - 0x2000 + 2]
        code = bytes(self.ram[0x800:0x800 + len(self.code)])
        for i in range(len(code) - 4):
            if code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 7] = self.ram[at:at + 7]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page), LOW_PAGE // 2: self.altrom_low[1] + bytes(8192)}
        t = self.art['title']
        for i in range(3):
            self.extra_banks[PLAY_PAGE // 2 + i] = bytes(16384)
            self.extra_banks[TITLE_PAGE // 2 + i] = t[i * 16384:(i + 1) * 16384]
        self.extra_banks[FONT_PAGE // 2] = self.art['font'] + bytes(8192)
        for i in range(16):
            self.extra_banks[TABLE_PAGE // 2 + i] = self.art['table'][i * 16384:(i + 1) * 16384]

    def apply(self, snap):
        if not is_booty(snap):
            raise ValueError('Not the supported Booty release (MD5 %s)' % SOURCE_MD5)
        if not self.sites:
            return
        banks = {i: bytearray(snap.banks[i]) for i in snap.banks}
        for a, old, new in self.sites:
            b, at = (5, a - 0x4000) if a < 0x8000 else (2, a - 0x8000) if a < 0xC000 else (0, a - 0xC000)
            if bytes(banks[b][at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[b][at:at + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in banks)


def build(source, destination, enhanced=False, colour_set=None):
    p = Patch(source, enhanced, art(colour_set) if enhanced else None)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


class View:
    """64K view of the game RAM + the pages the hook maps, per the model's MMU."""
    def __init__(self, mem, patch, st):
        self.mem = bytearray(mem)
        self.patch, self.st = patch, st
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        s = a >> 13
        if s == 0:
            return self.mem[a]
        if s == 1:
            m = self.model.nr.get(0x51, 255)
            return self.patch.page[a - 0x2000] if m == 255 else self.st.page[a - 0x2000]
        if 4 <= s <= 6:
            m = self.model.nr.get(0x50 + s, (4, 5, 0)[s - 4])
            if m != (4, 5, 0)[s - 4]:
                return self.st.read(m, a & 8191)
        return self.mem[a]

    def __setitem__(self, a, v):
        s = a >> 13
        if s == 0:
            return
        if s == 1:
            if self.model.nr.get(0x51, 255) == 24:
                self.st.page[a - 0x2000] = v
            return
        if 4 <= s <= 6:
            m = self.model.nr.get(0x50 + s, (4, 5, 0)[s - 4])
            if m != (4, 5, 0)[s - 4]:
                self.st.write(m, a & 8191, v)
                return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line)
        self.nr.update({0x51: 255, 0x54: 4, 0x55: 5, 0x56: 0})
        self.io = []

    def write_port(self, regs, port, v, *args):
        if port in (0x243B, 0x253B) or port & 255 == 0x6B:
            return super().write_port(regs, port, v, *args)
        self.io.append((port, v))


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class State:
    """What a hook keeps between calls: its page, Layer 2's pages, the Next registers that last."""
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.patch = patch
        self.l2 = {p: bytearray(8192) for p in range(PLAY_PAGE, PLAY_PAGE + 6)}
        self.table = bytearray(patch.art['table'])
        self.nr = {0x12: 19, 0x69: 0x80, 0x40: 17, 0x41: 0, 0x7F: 0}
        self.clock = 0
        self.line = 0

    def read(self, m, o):
        if m in self.l2:
            return self.l2[m][o]
        if FONT_PAGE <= m < FONT_PAGE + 2:
            return self.patch.extra_banks[22][(m - FONT_PAGE) * 8192 + o]
        if TABLE_PAGE <= m < TABLE_PAGE + 33:
            n = m - TABLE_PAGE
            return self.table[n * 8192 + o] if n < 32 else 0
        raise AssertionError('hook read page %d' % m)

    def write(self, m, o, v):
        if m == TABLE_PAGE + 8:
            self.table[8 * 8192 + o] = v
        elif m not in self.l2:
            raise AssertionError('hook wrote page %d' % m)
        else:
            self.l2[m][o] = v


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=20000000, speed=0, iff_in=None):
    Sim = _rw()
    v = View(mem, patch, st)
    s = simpool.machine(Sim, v, list(regs), 'booty-hook')
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
    for k in (0x12, 0x69, 0x40, 0x41, 0x7F):
        if k in m.nr:
            st.nr[k] = m.nr[k]
    st.clock = m.nr[7]
    return list(R), v, m


class Picture:
    """The expected Layer 2, from the set's own planes and the print's own registers (independent of the table)."""
    def __init__(self, cs):
        self.cs = cs
        self.px = bytearray(256 * 192)
        self.cells = {}
        self.buf = {}

    def pixels(self, a):
        return self.buf[a] if a in self.buf else self.cs.pixels(a)

    def compose(self, mem, ix):
        """EED7 as the game runs it, on each plane's bits: the clear from A06C, then SLA A / RL C n times and OR (IX)."""
        for a in range(0xA0EC, 0xA16C):
            self.buf[a] = bytes(8)
        phase, w, h, first = mem[ix + 2], mem[ix + 7], mem[ix + 8], mem[ix + 6]
        chars = mem[0x5C36] | mem[0x5C37] << 8
        src = (chars + 8 * first) & 0xFFFF
        n = 2 * (phase + 1)
        iy_at, ix_at = 0xA0F4 + 8 * (h + 1), 0xA0F4
        for c in range(w):
            for row in range(h):
                for r in range(8):
                    a = (src + c * 8 + row * w * 8 + r) & 0xFFFF
                    p = self.pixels(a)
                    lo = bytes(p[n:]) + bytes(n)            # A after the shifts: bits n.. at the top
                    hi = bytes(8 - n) + bytes(p[:n])        # C: the top n bits at the bottom
                    self.buf[iy_at] = lo
                    old = self.pixels(ix_at)
                    self.buf[ix_at] = bytes(x | y for x, y in zip(hi, old))
                    ix_at += 1
                    iy_at += 1
            ix_at += 8
            iy_at += 8

    def cell(self, mem, scr, src, flag):
        y = ((scr >> 8) & 0x18) * 8 | (scr & 0xE0) >> 2
        x = (scr & 31) * 8
        inv = 255 if flag & 4 else 0
        over = bool(flag & 1)
        for r in range(8):
            p = self.pixels((src + r) & 0xFFFF)
            for k in range(8):
                v = p[k] ^ inv
                if over:
                    v ^= self.px[(y + r) * 256 + x + k]
                self.px[(y + r) * 256 + x + k] = v
        self.cells[scr] = (src, inv, over, bytes(mem[(src + r) & 0xFFFF] ^ inv for r in range(8)))

    def src_at(self, i):
        y, x = i // 256, i % 256
        scr = 0x4000 | (y & 0xC0) << 5 | (y & 0x38) << 2 | x >> 3
        return hex(self.cells[scr][0]) if scr in self.cells else None

    def fill(self, scr, w):
        y = ((scr >> 8) & 0x18) << 3 | (scr & 0xE0) >> 2 | ((scr >> 8) & 7)
        x = (scr & 31) * 8
        self.px[y * 256 + x:y * 256 + x + w * 8] = b'\xff' * (w * 8)
        for c in range(w):
            self.cells.pop((scr & 0xFFE0 | ((scr + c) & 31)) & 0xF8FF, None)

    def clear(self, lines):
        top = (24 - lines) * 8
        self.px[top * 256:] = bytes((192 - top) * 256)
        for scr in list(self.cells):
            y = ((scr >> 8) & 0x18) * 8 | (scr & 0xE0) >> 2
            if y >= top:
                del self.cells[scr]

    def against_ula(self, mem):
        """Every cell the model holds still shows that graphic on the ULA: a screen write that no hook saw fails here."""
        bad = []
        for scr, (src, inv, over, want) in self.cells.items():
            if over:
                continue
            for r in range(8):
                if mem[scr + (r << 8)] != want[r]:
                    bad.append(hex(scr))
                    break
        return bad


def _l2(st):
    return b''.join(bytes(st.l2[p]) for p in range(PLAY_PAGE, PLAY_PAGE + 6))


def _flat(sim):
    return bytes(sim.memory)


def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=64, first_failure=False):
    """Replay the original; at every site run the hook on a copy of the state and compare with the original's run to where they
    meet again: every register with R and all 48K RAM. Layer 2 against an independent picture from the set's planes after every
    print, and the model's cells against the ULA every 64 hooks (a screen write no hook saw)."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    if not patch.sites:
        return (c, {}, []) if collect else (c, {})
    st = State(patch)
    pic = Picture(patch.art['set'])
    hidden = [False]

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
        if first_failure:
            raise _Stop()

    def patched_mem(mem):
        p = bytearray(mem)
        for a, old, new in patch.sites:
            p[a:a + len(new)] = new
        for a, old, new in patch.rom_sites:
            p[a:a + len(new)] = new
        return p

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        old, sym, kind, stop_pc = ALL_SITES[pc]
        if mem[pc:pc + 3] != bytes.fromhex(old):
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        ref = simpool.machine(Simulator, list(mem), regs, 'booty-ref')
        R = ref.registers
        sp = regs[12]
        hsp = None
        if kind == 'cll':
            ret = mem[sp] | mem[sp + 1] << 8
            while not (R[24] == ret and R[12] == sp + 2):
                ref.opcodes[ref.memory[R[24]]]()
            stop_pc, hsp = ret, sp + 2
        elif kind == 'isrx':
            for _ in range(3):
                ref.opcodes[ref.memory[R[24]]]()
            stop_pc, hsp = R[24], R[12]
        else:
            n = 0
            while n == 0 or R[24] != stop_pc:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
        p = patched_mem(mem)
        clock0 = st.clock
        got, v, model = run_hook(patch, st, p, regs, stop_pc, hsp, speed=clock0)
        for i in CMP:
            if (bool(R[i]) != bool(got[i])) if i == 26 else (R[i] != got[i] and i != 14):
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': R[i], 'got': got[i], 'sym': sym})
        want_i = 0x3B if kind == 'room' or (st.page[V_ILEAVE - 0x2000] == 0x3B and kind != 'roomend') else R[14]
        if got[14] != want_i:
            fail('I differs', {'pc': hex(pc), 'got': got[14], 'want': want_i, 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, _, new in patch.sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        for a in range(max(0x4000, min(sp, got[12]) - 32), min(sp, got[12])):
            expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if (model.nr[0x51] != 255 or model.nr[0x54] != 4 or model.nr[0x55] != 5 or model.nr[0x56] != 0):
            fail('MMU not restored', {'pc': hex(pc)})
        want_clock = {'room': 3, 'roomend': 0}.get(kind, clock0)
        if model.nr[7] != want_clock:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7], 'want': want_clock, 'sym': sym})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        if st.page[V_IN - 0x2000]:
            fail('hook flag left on', {'pc': hex(pc)})
        if kind == 'hidden':
            hidden[0] = True
            if st.nr[0x69] != 0:
                fail('Layer 2 left on in the hidden game', {})
        elif kind == 'title':
            hidden[0] = False
            if st.nr[0x69] != 0x80:
                fail('Layer 2 left off', {})
        if kind == 'cell':
            pic.cell(mem, (regs[4] << 8 | regs[5]) - 1, regs[6] << 8 | regs[7], mem[0x5C91] & 0)
        elif kind == 'rom':
            if 0x40 <= regs[6] < 0x58:
                pic.cell(mem, regs[6] << 8 | regs[7], regs[4] << 8 | regs[5], mem[0x5C91])
        elif kind == 'fill':
            pic.fill(mem[0x5C84] | mem[0x5C85] << 8, mem[(regs[8] << 8 | regs[9]) + 7])
        elif kind == 'cll':
            pic.clear(regs[2])
            if st.nr[0x12] != 16:
                fail('title left on', {})
        elif kind == 'compose':
            pic.compose(mem, regs[8] << 8 | regs[9])
        elif kind == 'title':
            if st.nr[0x12] != 19:
                fail('title not shown', {})
        if kind == 'room' and st.clock != 3:
            fail('room not at 28 MHz', {})
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if kind in ('cell', 'rom', 'fill', 'cll') and hidden[0]:
            pic.cells.clear()
        elif kind in ('cell', 'rom', 'fill', 'cll'):
            if c['hooks'] % every == 0 or kind == 'cll':
                got_l2 = _l2(st)
                if got_l2 != bytes(pic.px):
                    diff = [i for i, (a, b) in enumerate(zip(got_l2, pic.px)) if a != b]
                    fail('Layer 2 differs from the set', {'pc': hex(pc), 'sym': sym, 'count': len(diff), 'ex': [(i % 256, i // 256, got_l2[i], pic.px[i], pic.src_at(i)) for i in diff[:6]]})
                c['Layer 2 pictures compared'] += 1
                c['Layer 2 pixels compared'] += 49152
                bad = pic.against_ula(mem if kind != 'cll' else ref.memory)
                # the cell being printed is still the old one on the ULA at the hook, so only count others
                if kind in ('cell', 'rom'):
                    this = (regs[4] << 8 | regs[5]) - 1 if kind == 'cell' else regs[6] << 8 | regs[7]
                    bad = [b for b in bad if int(b, 16) != this]
                if bad:
                    fail('a screen write no hook saw', {'pc': hex(pc), 'count': len(bad), 'ex': [(b, ['%04X %s %d' % (pic.cells[int(b, 16)][0], bytes(mem[int(b, 16) + (r << 8)] for r in range(8)).hex(), pic.cells[int(b, 16)][1])]) for b in bad[:3]]})
                c['ULA cells checked'] += len(pic.cells)
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    try:
        frames, err = trace(str(rzx_path), set(ALL_SITES), on_pc, stop)
    except _Stop:
        return c, dict(examples)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


def unit_tests(patch, states, neg=True):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R and the clock the caller had;
    the MMU restored. The ISR's two sites as well with a hook interrupted: the handler runs at the game's clock, the hook's comes back."""
    from skoolkit.simulator import Simulator
    c = Counter()
    if not patch.sites:
        return c

    def patched(mem):
        p = bytearray(mem)
        for a, old, new in list(patch.sites) + patch.rom_sites:
            p[a:a + len(new)] = new
        return p

    def meet(mem, rr, kind, stop_pc):
        ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
        R = ref.registers
        sp = rr[12]
        hsp = None
        if kind == 'cll':
            ret = mem[sp] | mem[sp + 1] << 8
            while not (R[24] == ret and R[12] == sp + 2):
                ref.opcodes[ref.memory[R[24]]]()
            stop_pc, hsp = ret, sp + 2
        elif kind == 'isrx':
            for _ in range(3):
                ref.opcodes[ref.memory[R[24]]]()
            stop_pc, hsp = R[24], R[12]
        else:
            n = 0
            while n == 0 or R[24] != stop_pc:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
        return ref, stop_pc, hsp
    for pc, regs, mem in states:
        old, sym, kind, stop_pc = ALL_SITES[pc]
        p = patched(mem)
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref, stop, hsp = meet(mem, rr, kind, stop_pc)
                    st = State(patch)
                    got, v, model = run_hook(patch, st, p, rr, stop, hsp, speed=speed)
                    if any(((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]) for i in CMP if i != 14):
                        c['ABI registers differ!'] += 1
                    want = {'room': 3}.get(kind, speed)
                    if kind == 'roomend':
                        want = st.page[0x3E35 - 0x2000]
                    if model.nr[7] != want:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x54] != 4 or model.nr[0x55] != 5 or model.nr[0x56] != 0:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    # an interrupt inside a hook, and inside a room: the handler at the game's clock, the interrupted clock back after it
    if states:
        pc, regs, mem = states[0]
        p = patched(mem)
        isr_w, isr_r = patch.syms['isr_w'], patch.syms['isr_r']
        for in_hook in (1, 0):
            for game in range(3 if in_hook else 1):
                st = State(patch)
                if in_hook:
                    st.nr[0x51] = 24
                    st.page[V_IN - 0x2000] = 1
                    st.page[0x3E30 - 0x2000] = game
                rr = list(regs)
                rr[24] = isr_w
                got, v, model = run_hook(patch, st, p, rr, 0xFE69, None, speed=3)
                if model.nr[7] != game or model.nr.get(0x7F) != 3:
                    c['ISR clock wrong in a hook!'] += 1
                if any(got[i] != rr[i] for i in (0, 1, 2, 3)):
                    c['ISR registers wrong!'] += 1
                sp = got[12]
                if v.mem[sp] | v.mem[sp + 1] << 8 != isr_r:
                    c['ISR return wrong!'] += 1
                rr = list(got)
                rr[12] = sp + 2
                rr[24] = isr_r
                mm = bytearray(v.mem)
                mm[sp + 2] = 0x34
                mm[sp + 3] = 0x12
                got2, v2, model2 = run_hook(patch, st, mm, rr, 0x1234, sp + 4, speed=game)
                if model2.nr[7] != 3:
                    c['ISR clock not put back!'] += 1
                c['ISR-in-hook cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def mutate(name, sym, old, new):
        b = copy.deepcopy(patch)
        at = patch.syms[sym] - 0x2800
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.find(bytes.fromhex(old), at)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(bytes.fromhex(new))] = bytes.fromhex(new)
        b._banks()
        out[name] = b
    # -13 at each entry's R set (FD = ld a,-3...; 3E F3 = ld a,-13)
    mutate('R off by one', 'h_rom', '3EF3', '3EF4')
    mutate('clock left at 28 MHz', 'h_e', '3A303EED9207', '3E0300ED9207')
    mutate('hook flag left on', 'h_a', 'AF32F03B', '0032F03B')
    mutate('x off by one column', 'l2_cell', '878787', '878700')
    mutate('wrong row', 'l2_cell', 'E660', 'E640')
    mutate('wrong colour table', 'l2_cell', 'C60E', 'C60F')
    mutate('font table for a RAM graphic', 'l2_cell', 'FE20', 'FE00')
    mutate('Layer 2 page left mapped', 'l2_cell', 'ED915404', '00000000')
    mutate('table page left mapped', 'l2_cell', 'ED915505', '00000000')
    mutate('inverse ignored', 'l2_cell', 'E605', 'E600')
    mutate('frame never built', 'h_comp', 'CD', '00')
    mutate('frame shifted wrongly', 'h_comp', 'DD7E023C87', 'DD7E020087')
    mutate('frame buffer not cleared', 'h_comp', '3600', '3601')
    mutate('title not shown again', 'h_title', 'ED911213', '00000000')
    mutate('Layer 2 left on the title', 'h_cll', 'ED911210', '00000000')
    mutate('clear left out', 'h_cll', 'CD', '00')
    mutate('fill left out (E522)', 'h_f1', 'DD7E0747', '3E0047')
    mutate('fill left out (E564)', 'h_f2', 'DD7E0747', '3E0047')
    mutate('delay R wrong', 'h_dly1', '3EF4', '3EF5')
    mutate('I left at the hook vector', 'h_e', '3A3D3EED47', '3E3B00ED47')
    mutate('room left at 28 MHz', 'h_re', '3A353E32303E', '3E0332303E00')
    return out


class _Stop(Exception):
    pass


def run_negative(b, rzx, stop):
    """Stops at the first failure: a negative only has to fail."""
    c, ex = verify(b, rzx, stop=stop, first_failure=True)
    return {k: v for k, v in c.items() if k.endswith('!')}


# ---- nexclash.py auto: the published builds, boot-checked; with recordings the Enhanced replay proof -------------------
import hashlib

LOAD_SCREEN = 'booty_loading.scr'         # the tape's screen, beside the snapshot: game data, never in this repo
LOAD_MD5 = 'd09b4390902bd3d61a35554eb4f06e6e'
SET_NAME = 'booty.256'                    # the Spec256 set as a .256 (ColourSet), beside the snapshot with PAL_NAME: never in this repo
SET_MD5 = '62ccf9b7af0e5d58e3186388107fd70b'
STOPS = {'a1.rzx': 6000, 'over.rzx': 9000}           # frames replayed, as in the review run's verify
NEG_RECORDINGS, NEG_STOP = ('rooms.rzx', 'die.rzx', 'hid.rzx'), 11000   # a broken build must fail one of these, in order
UNIT_RECORDINGS = ('rooms.rzx', 'die.rzx')           # the ABI cases: these recordings' states, one per site
# Each tested alone in the simulator (games/booty.md "Cheats"); the published patch's eight.
TRAINERS = '''NInfinite Lives
Z 8 58294 0 0
NImmune To Pirates
Z 8 61635 24 0
NImmune To Birds & Rats
Z 8 58104 201 0
NBombs Don't Explode
Z 8 58317 201 0
NWalk Through All Doors
M 8 60576 0 0
Z 8 60577 0 0
NNo Pirates
M 8 61441 201 0
Z 8 58294 4 0
NDon't Throw Back To Start
Z 8 58304 206 0
NAccess Hidden Game
Z 8 52798 58 0
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
    snapshot, except the start-up tail's own bytes (and the printer buffer NEXLOAD overwrites); then nextboot.check
    (slots, paging, the alt ROM). -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    tail, size = patch.tail_addr, len(zt.build_tail(s, 0x8000, patch.slot1, True)[0])
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
    return bad + [('check', x) for x in nextboot.check(str(nex), str(z80), patch=patch, tail=(tail, tail + size))]


def _replay(z80, colour_set, rzx, stop, collect):
    """One recording's Enhanced replay (a process of its own) -> (counts, examples, states)."""
    got = verify(Patch(z80, True, art(colour_set)), rzx, stop=stop, collect=collect)
    return got if collect else (got[0], got[1], [])


def _negative(z80, colour_set, name, rzxs, stop):
    """One deliberately broken build against the recordings in turn until one fails it (a process of its own):
    -> (name, recording, its failure keys)."""
    b = negative_patches(Patch(z80, True, art(colour_set)))[name]
    for rzx in rzxs:
        try:
            got = sorted(run_negative(b, rzx, stop))
        except Exception as e:              # noqa: BLE001 - a broken hook that runs off into data is caught too
            got = ['exception ' + type(e).__name__]
        if got:
            return name, Path(rzx).name, got
    return name, None, []


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build (no game byte changed, no hook; Sinclair's ROM as the whole alt ROM) and, with
    the set and its palette beside the snapshot, the Enhanced build; each with the loading screen when it is beside the
    snapshot, as published; every build boot-checked. With --rzx the Enhanced replay proof of each recording, the ABI
    cases and the broken builds. The pace, soak, flicker and real loader proofs are the review run's (games/booty.md
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
    say('Game      : Booty (John F. Cain, Firebird, 1984, 48K)')
    say("Engine    : booty; default: the original game, no hook (no clash to remove); Enhanced: the Spec256 set's "
        'pixels on a Layer 2 over the unchanged ULA; original pace')
    ok = True
    screen = _beside(z80, LOAD_SCREEN, LOAD_MD5, 'the original loading screen')
    cset = _beside(z80, SET_NAME, SET_MD5, 'the set this engine was proved with')
    if cset is not None and not (cset.parent / PAL_NAME).is_file():
        say('Enhanced  : %s without %s beside it: default build only' % (SET_NAME, PAL_NAME))
        cset = None
    if screen is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    if cset is None:
        say('Enhanced  : no %s (and %s) beside the snapshot: default build only' % (SET_NAME, PAL_NAME))
    builds = [('Default', name, lambda: Patch(z80))]
    if cset is not None:
        colours = art(cset)                 # MD5 of the palette checked here (spec256_palette)
        builds.append(('Enhanced', name + '_enhanced', lambda: Patch(z80, True, colours)))
    for label, stem, make in builds:
        nex = out / (stem + '.nex')
        zt.convert(str(z80), str(nex), patch=make(), quiet=True)
        nexes = [(label, nex)]
        if screen is not None:
            loading = out / (stem + '_loading.nex')
            loading.write_bytes(loading_nex(nex.read_bytes(), screen.read_bytes()))
            nexes.append((label[:3] + '+scr', loading))
        for lab, path in nexes:
            bad = boot_check(path, z80, make())
            ok = ok and not bad
            say('%-10s: %s  %s' % (lab, path.name, hashlib.md5(path.read_bytes()).hexdigest()))
            say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM, slots and paging; converter loader and NEXLOAD)'
                                    if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    if rzxs and cset is None:
        say('Verify    : FAILED: recordings given but no %s and %s beside the snapshot (the default runs no hook; the '
            'replay proves Enhanced)' % (SET_NAME, PAL_NAME))
        ok = False
    elif rzxs:
        quick = getattr(a, 'quick', None)
        stops = [min(x for x in (quick, STOPS.get(Path(r).name)) if x) if (quick or STOPS.get(Path(r).name)) else None
                 for r in rzxs]
        collect = [1 if Path(r).name in UNIT_RECORDINGS else 0 for r in rzxs]
        with concurrent.futures.ProcessPoolExecutor(min(len(rzxs), os.cpu_count() or 1)) as pool:
            done = list(pool.map(_replay, [z80] * len(rzxs), [cset] * len(rzxs), rzxs, stops, collect))
        states, sites = [], set()
        for path, stop, (c, ex, got) in zip(rzxs, stops, done):
            states += [x for x in got if x[0] not in sites]
            sites |= {x[0] for x in got}
            fail = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fail
            say('Verify    : %s %d frames%s, %d hooks, %d R comparisons, %d Layer 2 pictures, %d pixels, %d ULA cells: %s' % (
                Path(path).name, c['frames'], ' (stop %d)' % stop if stop else '', c['hooks'], c['R comparisons'],
                c['Layer 2 pictures compared'], c['Layer 2 pixels compared'], c['ULA cells checked'],
                'IDENTICAL' if not fail else str(fail)))
            for k, v in ex.items():
                say('            %s: %s' % (k, v))
        counts = unit_tests(Patch(z80, True, colours), states)
        fail = {k: v for k, v in counts.items() if k.endswith('!')}
        ok = ok and not fail
        say('Unit      : %s (%d sites)' % (dict(counts), len(states)))
        negs = [r for n in NEG_RECORDINGS for r in rzxs if Path(r).name == n] or rzxs[:1]
        names = list(negative_patches(Patch(z80, True, colours)))
        with concurrent.futures.ProcessPoolExecutor(min(len(names), os.cpu_count() or 1)) as pool:
            neg = list(pool.map(_negative, [z80] * len(names), [cset] * len(names), names, [negs] * len(names),
                                [min(quick or NEG_STOP, NEG_STOP)] * len(names)))
        missed = [n for n, r, keys in neg if not keys]
        ok = ok and not missed
        say('Negatives : %d of %d broken builds caught (%s, up to %d frames each)%s' % (
            len(neg) - len(missed), len(neg), ', '.join(Path(r).name for r in negs), NEG_STOP,
            '; MISSED %s' % missed if missed else ''))
    else:
        say('Verify    : not requested; boot evidence only')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
