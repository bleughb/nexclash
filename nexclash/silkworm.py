"""Silkworm (Random Access / Virgin Games, 1989, 128K): the original game on the Next; Enhanced colours as a set.

The play area is monochrome and has no clash: every figure goes through the back buffer 8002-8DBF
and the blit A25E onto white-on-black rows 4-17; the ground (rows 18-19) is written over any figure below the sky before each blit.
So the default is the game itself. The only things a plain conversion gets wrong here are start-up:
SP is in the top 16K (no automatic tail) and the game keeps code at 5B00, where NEXLOAD writes.
"""
from pathlib import Path
import json, pickle
from . import z80tonex as zt
ROOT = Path(__file__).resolve().parents[1]

SOURCE_MD5 = '8fad50cd8c218ade32bf3c2332c8ee03'
SIGNATURE = {0x946B: 'CD5EA2', 0x9483: 'C32194', 0xA25E: 'F3ED738D9C313EA0', 0x5B00: 'F331FFFFCD039E'}
TAIL_ADDR = 0x90B0                 # zero bytes the game never reads or writes (all eleven waves, the ending)
TAIL_MAX = 0x50                    # 0x9000-0x901F takes writes past the back buffer; 0x9100 up is read
PRINTER = 0x5B00                   # game code; NEXLOAD leaves its own routines here
DECISIONS = {'figures': 'the original monochrome play area', 'scenery': 'the original attributes',
             'outline': 'none', 'enhanced': "the Spec256 set's colours as they are, on Layer 2, off by default"}


def is_silkworm(snap):
    """The 128K release at its title: zt.Z80Snapshot (banks) or skoolkit's Snapshot (memory)."""
    if getattr(snap, 'banks', None) is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    if not getattr(snap, 'is128', False):
        return False
    return all(bytes(snap.read(a + i) for i in range(len(v) // 2)) == bytes.fromhex(v) for a, v in SIGNATURE.items())


class Patch:
    name = 'Silkworm 128K: the original game, no hooks'
    uses_printer_buffer = True
    hook_page_data = b''
    extra_banks = {}
    sites = []
    slot1 = None
    setup_call = zt.STUB_ORG + 0x1000
    tail_addr = TAIL_ADDR
    max_tail = TAIL_MAX

    def __init__(self, source=None):
        self.source = str(source) if source else None
        self.stub_extra = b''

    def apply(self, snap):
        if not is_silkworm(snap):
            raise ValueError('not the Silkworm 128K release this engine was built for')
        if any(snap.read(a) for a in range(TAIL_ADDR, TAIL_ADDR + TAIL_MAX)):
            raise ValueError('the tail area is not empty')
        # Setup in the stub bank: put the game's code at 5B00 back, after NEXLOAD (the stub's own
        # printer option refuses 128K snapshots; this game's 128K ROM 1 and locked paging do not mind).
        printer = bytes(snap.read(PRINTER + i) for i in range(256))
        src = self.setup_call + 12
        code = (b'\x21' + zt.w16(src) + b'\x11' + zt.w16(PRINTER) + b'\x01' + zt.w16(256) + b'\xED\xB0' + b'\xC9')
        assert len(code) == 12
        self.stub_extra = code + printer


COLOURS = 'silkworm_colours.bin'    # built from the Spec256 set: game data, beside the snapshot, never in this repo


def load_profile():
    return json.loads((ROOT / 'docs/profiles/silkworm.json').read_text())


def set_bytes(snap_banks, addr, data):
    bank = 5 if addr < 0x8000 else 2 if addr < 0xC000 else 0
    at = addr & 16383
    snap_banks[bank][at:at + len(data)] = data


class Enhanced(Patch):
    name = 'Silkworm 128K: Enhanced colours on a Layer 2 picture'
    setup_call = 0xD000

    def __init__(self, source=None, colours=None):
        super().__init__(source)
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.setup = bytes.fromhex(h['setup'])
        self.colours_path = colours or (Path(source).parent / COLOURS)
        self.blob = pickle.loads(Path(self.colours_path).read_bytes())
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        S = self.syms
        self.sites = [(0xA2AC, 'jp', S['h_p']), (0xAA0A, 'jp', S['h_w']), (0xB16D, 'jp', S['h_s']), (0xA98A, 'jp', S['h_di1']), (0xA9DD, 'jp', S['h_di2']),
                      (0x9421, 'call', S['h_loop']), (0x7DA3, 'call', S['h_title']), (0x5BEF, 'jp', S['h_buf']), (0xA9BA, 'jp', S['h_ei1']), (0xAA04, 'jp', S['h_ei2']),
                      (0x9474, 'call', S['h_clear']), (0x9477, 'call', S['h_stars']), (0x9465, 'call', S['h_ground']), (0x946B, 'call', S['h_blit']),
                      (0x7B76, 'call', S['h_wave']), (0xFC55, 'jp', S['h_fc']), (0x9E03, 'jp', S['h_fill']),
                      (0x5B11, 'ld', S['h_isr']), (0x7B83, 'ld', S['h_isr'])]
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x1800:0x1C00] = bytes(0x400)
        self.ram[0x1E00:0x2000] = bytes(512)
        self.ram[S['V_BACK'] - 0x2000] = 16
        self.ram[S['V_RECT'] - 0x2000:S['V_RECT'] - 0x2000 + 2] = (0x3800).to_bytes(2, 'little')
        self.ram[S['V_DOTS'] - 0x2000:S['V_DOTS'] - 0x2000 + 2] = (0x3A00).to_bytes(2, 'little')
        self._banks()

    def _banks(self):
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        S = self.syms
        for n in ('h_p', 'h_w', 'h_s', 'h_di1', 'h_di2', 'h_ei1', 'h_ei2', 'h_loop', 'h_title', 'h_buf', 'h_clear', 'h_stars', 'h_ground', 'h_blit', 'h_wave'):
            at = S[n] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for x, y in (('h_isr', 'h_isr_end'), ('h_fc', 'h_fc_end'), ('h_fill', 'h_fill_end')):
            a, b = S[x] - 0x2000, S[y] - 0x2000
            self.page[a:b] = self.ram[a:b]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 12] = self.ram[at:at + 12]
        blob = self.blob
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}
        for bank in (16, 17, 18, 19, 20, 21):
            self.extra_banks[bank] = bytes(16384)
        self.extra_banks[22] = blob['table'].ljust(8192, b'\0') + blob['ground']
        self.extra_banks[27] = blob['title'][:16384]
        self.extra_banks[28] = blob['title'][16384:].ljust(16384, b'\0')
        pages = blob['pages']
        for i in range(0, len(pages), 2):
            hi = pages[i + 1] if i + 1 < len(pages) else bytes(8192)
            self.extra_banks[24 + i // 2] = pages[i] + hi

    def apply(self, snap):
        if not is_silkworm(snap):
            raise ValueError('not the Silkworm 128K release this engine was built for')
        S = self.syms
        banks = {i: bytearray(snap.banks[i]) for i in range(8)}
        for a, kind, target in self.sites:
            if kind == 'ld':
                set_bytes(banks, a + 1, bytes((target & 255, target >> 8)))
            else:
                set_bytes(banks, a, bytes((0xC3 if kind == 'jp' else 0xCD, target & 255, target >> 8)))
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in range(8))
        setup = bytearray(self.setup)
        at = S['l2_pal'] - 0xD000
        setup[at:at + 256] = self.blob['pal']
        at = S['spr_pat'] - 0xD000
        setup[at:at + 256] = self.blob['icon']
        printer = bytes(snap.read(0x5B00 + i) for i in range(256))
        assert S['printer'] - 0xD000 == len(setup)
        self.stub_extra = bytes(setup) + printer


def build(source, destination, enhanced=False, colours=None):
    p = Enhanced(source, colours) if enhanced else Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


# ---- verification: the Enhanced build against the original, hook by hook -------------------------------------------
from collections import Counter, defaultdict
from . import hooklib, simpool
CMP = tuple(hooklib.CMP_R)
SITES = {0xA2AC: (0xA2AF, 'h_p'), 0xAA0A: (0xAA0D, 'h_w'), 0xB16D: (0xB170, 'h_s'), 0xA98A: (0xA98F, 'h_di1'), 0xA9DD: (0xA9E2, 'h_di2'),
         0x9421: (0x9608, 'h_loop'), 0x7DA3: (0x7DA6, 'h_title'), 0x5BEF: (0x5BF3, 'h_buf'), 0xA9BA: ('ei', 'h_ei1'), 0xAA04: ('ei', 'h_ei2'),
         0x9474: (0x9784, 'h_clear'), 0x9477: (0x947A, 'h_stars'), 0x9465: (0x96DB, 'h_ground'), 0x946B: (0x946E, 'h_blit'),
         0x7B76: (0x7BEA, 'h_wave'), 0xFC55: (0xFC58, 'h_fc'), 0x9E03: (0x9E08, 'h_fill'), 0xFDFD: ('isr', 'h_isr')}
FAST = {'h_loop'}              # leaves the clock at 28 MHz
BODY_SLOW = {'h_ground', 'h_title'}        # back to the game's clock


def _rw():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class View:
    def __init__(self, mem, patch, st):
        self.mem, self.patch, self.st = bytearray(mem), patch, st
        self.model = None

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        nr = self.model.nr
        if a < 0x2000:
            return self.mem[a]
        if a < 0x4000:
            return self.st.page[a - 0x2000] if nr[0x51] == 24 else self.patch.page[a - 0x2000]
        if 0xA000 <= a < 0xE000:
            s = 0x55 if a < 0xC000 else 0x56
            p = nr[s]
            if p not in (0, 5):
                return self.st.pages[p][a & 8191]
        return self.mem[a]

    def __setitem__(self, a, v):
        nr = self.model.nr
        if a < 0x2000:
            return
        if a < 0x4000:
            if nr[0x51] == 24:
                self.st.page[a - 0x2000] = v
            return
        if 0xA000 <= a < 0xE000:
            s = 0x55 if a < 0xC000 else 0x56
            p = nr[s]
            if p not in (0, 5):
                self.st.pages[p][a & 8191] = v
                return
        self.mem[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed=0, line=0):
        super().__init__(sim, speed, line=line, lines=311, t_line=228)
        self.nr.update({0x51: 255, 0x55: 5, 0x56: 0})
        self.nr[1] = 0x32
        self.io = []
        self.ins = []
        self.spr = []

    def read_port(self, regs, port):
        if port == 0x253B:
            return super().read_port(regs, port)
        self.ins.append(port)
        return 0xFF

    def write_port(self, regs, port, v, *args):
        if port in (0x243B, 0x253B):
            return super().write_port(regs, port, v, *args)
        if port & 255 == 0x57 or port == 0x303B:
            self.spr.append(v)
            return
        self.io.append((port, v))


class RefPorts:
    def __init__(self):
        self.io, self.ins = [], []

    def read_port(self, regs, port):
        self.ins.append(port)
        return 0xFF

    def write_port(self, regs, port, v, *args):
        self.io.append((port, v))


class State:
    def __init__(self, patch):
        self.page = bytearray(patch.ram)
        self.pages = {}
        for bank, data in patch.extra_banks.items():
            if bank != 12:
                self.pages[bank * 2] = bytearray(data[:8192])
                self.pages[bank * 2 + 1] = bytearray(data[8192:])
        self.nr = {0x12: 16, 0x69: 0}
        self.line = 0
        self.speed = 0
        self.icons = []


def run_hook(patch, st, mem, regs, stop, limit=8000000, speed=None):
    Sim = _rw()
    v = View(mem, patch, st)
    s = simpool.machine(Sim, v, list(regs), 'silk-hook')
    m = Model(s, st.speed if speed is None else speed, st.line)
    m.nr.update(st.nr)
    v.model = m
    n = 0
    R = s.registers
    # The simulator clears P/V for an LD A,I inside its interrupt window, and no handler then runs inside the hook, so
    # the macro's second read would see it too. On the machine the handler runs and the second read is good (iff_audit).
    s.int_active = 0
    while n == 0 or not stop(R, v):
        s.opcodes[v[R[24]]]()
        n += 1
        if n > limit:
            raise AssertionError('hook did not terminate at %04X' % R[24])
    st.line = m.line()
    st.nr.update({k: m.nr[k] for k in (0x12, 0x69)})
    st.speed = m.nr[7] & 3
    return list(R), v, m


def _flat(sim):
    m = sim.memory
    return bytes(16384) + bytes(m.memory[1]) + bytes(m.memory[2]) + bytes(m.memory[3])


SET_NAME = 'silkworm.256'                  # the Spec256 set itself, beside the colour blob: verification only, never in this repo
SET_MD5 = 'a5ab9ff083075971add0d4d16aa80dfa'
PAL_NAME = 'spec256-palette.pal'           # Spec256-Games' palette (licence not established: never in this repo)
PAL_MD5 = 'b095dc99a047bab844b87b06657b0a7a'


def _pinned(folder, name, md5):
    import hashlib
    p = Path(folder) / name
    if not p.is_file():
        raise ValueError('no %s beside the colour blob: the replay model reads the set afresh and needs it' % name)
    data = p.read_bytes()
    if hashlib.md5(data).hexdigest() != md5:
        raise ValueError('%s MD5 %s, the proved one is %s' % (name, hashlib.md5(data).hexdigest(), md5))
    return data


class SetReader:
    """The Spec256 set's plane values and its own colour rule (the review run's colourset.py), read from SET_NAME and
    PAL_NAME in folder."""
    def __init__(self, folder):
        self.d = _pinned(folder, SET_NAME, SET_MD5)
        v = [int(x) for x in _pinned(folder, PAL_NAME, PAL_MD5).decode('ascii').split()]
        self.pal = [tuple(v[i:i + 3]) for i in range(0, 768, 3)]
        mem = 131072 * 9
        self.up, self.down, self.flags = self.d[mem + 29], self.d[mem + 30], self.d[mem + 31]
        if not self.flags & 0x80:
            self.up, self.down, self.flags = 64, 0, 0
        self.p7 = self.d[mem + 28]

    def phys(self, a):
        bank = 5 if a < 0x8000 else 2 if a < 0xC000 else (self.p7 & 7)
        return bank * 16384 + (a & 16383)

    def v8(self, a):
        """The 8 plane values of the byte at a, left pixel first, and the master byte."""
        o = self.phys(a) * 9
        p, m = self.d[o:o + 8], self.d[o + 8]
        return [sum(((p[i] >> (7 - k)) & 1) << i for i in range(8)) for k in range(8)], m

    def rgb(self, v, master, attr):
        if v == 0xFF:
            colour = (attr & 7) if master else (attr >> 3) & 7
            level = 255 if attr & 0x40 else 215
            return (level if colour & 2 else 0, level if colour & 4 else 0, level if colour & 1 else 0)
        r, g, b = self.pal[v]
        if v >= 256 - self.up or v < self.down:
            upper = v >= 256 - self.up
            paper = bool(self.flags & (2 if upper else 4))
            ac = (attr >> 3) & 7 if paper else attr & 7
            level = 255 if self.flags & 1 and attr & 0x40 else 191
            r = (r + (level if ac & 2 else 0)) >> 1
            g = (g + (level if ac & 4 else 0)) >> 1
            b = (b + (level if ac & 1 else 0)) >> 1
        return (r, g, b)


def to9(c):
    return (round(c[0] * 7 / 255), round(c[1] * 7 / 255), round(c[2] * 7 / 255))


class Picture:
    """What the Spec256 machine's planes would hold in the back buffer, by the game's own operations, read from the set
    afresh (SetReader, beside the colour blob): independent of the build's colour images."""
    def __init__(self, patch):
        self.s, self.to9 = SetReader(Path(patch.colours_path).parent), to9
        self.pal = {tuple(c): i for i, c in reversed(list(enumerate(patch.blob['pal9'])))}
        self.buf = bytearray(256 * 128)         # plane value per pixel; buffer row, screen x
        self.master = bytearray(256 * 128)      # the master bit, for FF
        self.attr = bytearray([0x47]) * 128
        self.cache = {}
        self.near_star = set()
        self.star_under = 0
        self.stale = 0
        self.or_overlap = 0

    def frame(self, a, rows, wide):
        k = (a, rows, wide)
        if k not in self.cache:
            gap = 72 if wide == 3 else 8
            out = []
            for r in range(rows):
                row = []
                for c in range(wide):
                    mv, mm = self.s.v8(a + r * wide + c)
                    gv, gm = self.s.v8(a + gap + r * wide + c)
                    for b in range(8):
                        row.append((mv[b], gv[b], mm >> (7 - b) & 1, gm >> (7 - b) & 1))
                out.append(row)
            self.cache[k] = out
        return self.cache[k]

    def plot(self, a, rows, wide, x, y, white=False):
        im = self.frame(a, rows, wide)
        for r in range(rows):
            bufrow = y + r - 24
            if not 0 <= bufrow < 112:
                continue
            base = bufrow * 256
            for i, (mv, gv, mm, gm) in enumerate(im[r]):
                xx = x - 8 + i
                if not 8 <= xx < 232:
                    continue
                p = base + xx
                if white:
                    self.buf[p] = (self.buf[p] & mv) | (mv ^ 255)
                    self.master[p] = (self.master[p] & mm) | (mm ^ 1)
                else:
                    self.buf[p] = (self.buf[p] & mv) | gv
                    self.master[p] = (self.master[p] & mm) | gm

    def clear(self, mem):
        """As the game fills it (9784), from the buffer bytes it wrote: mono, all planes alike."""
        self.near_star = set()
        for bufrow in range(112):
            base = bufrow * 256
            src = 0x8002 + bufrow * 32
            for col in range(28):
                b = mem[src + col]
                for k in range(8):
                    bit = b >> (7 - k) & 1
                    self.buf[base + 8 + col * 8 + k] = 255 if bit else 0
                    self.master[base + 8 + col * 8 + k] = bit

    def text(self, ch, bc):
        """A character into the back buffer (5BEF): the bytes replace what was there, by the font's planes."""
        off = bc - 0x8002
        if not 0 <= off < 112 * 32:
            return
        for r in range(8):
            vs, mb = self.s.v8(0x5B0D + ch * 8 + r)
            bufrow, col = off // 32 + r, off % 32
            if bufrow >= 112:
                continue
            for k in range(8):
                p = bufrow * 256 + 8 + col * 8 + k
                if p % 256 < 232:
                    self.buf[p], self.master[p] = vs[k], mb >> (7 - k) & 1

    def bits_differ(self, mem):
        """The game's own buffer against the picture, bit for bit: a writer the model and the hooks both miss shows here."""
        n = 0
        for bufrow in range(112):
            base = bufrow * 256
            src = 0x8002 + bufrow * 32
            for col in range(28):
                b = mem[src + col]
                for k in range(8):
                    bit, was = b >> (7 - k) & 1, self.master[base + 8 + col * 8 + k]
                    if bit != was and (bufrow, 8 + col * 8 + k) not in self.near_star:
                        if bit:
                            n += 1
                        else:
                            self.stale += 1     # in the picture, gone from the buffer: a restart's own clear, no hook there
        return n

    def star(self, x, y):
        bufrow = y - 24
        for d in range(-3, 4):
            self.near_star.add((bufrow, x - 8 + d))
        if 0 <= bufrow < 112 and 8 <= x - 8 < 232:
            p = bufrow * 256 + x - 8
            self.buf[p] = 255
            self.master[p] = 1

    def ground(self, wave, phase, shifted, attr):
        for r in range(16):
            row = []
            for bi in (0, 1):
                vs, mb = self.s.v8(0x78AC + wave * 32 + r * 2 + bi)
                for k in range(8):
                    row.append((vs[k], mb >> (7 - k) & 1))
            y = 112 + r + (1 if shifted else 0)
            if y < 128:
                for i in range(224):
                    v, mb = row[(i + phase) % 16]
                    p = y * 256 + 8 + i
                    self.buf[p], self.master[p] = v, mb
                    self.attr[y] = attr
        if shifted:
            for i in range(224):
                self.buf[112 * 256 + 8 + i] = 0
                self.master[112 * 256 + 8 + i] = 0

    def compare(self, st, back):
        bad = 0
        first = None
        for bufrow in range(128):
            y = 32 + bufrow
            page = st.pages[back * 2 + (y >> 5)]
            off = (y & 31) << 8
            attr = self.attr[bufrow] if bufrow >= 112 else 0x47
            for x in range(8, 232):
                v = self.buf[bufrow * 256 + x]
                m = self.master[bufrow * 256 + x]
                want = self.pal.get(self.to9(self.s.rgb(v, m, attr)))
                if page[off + x] & 0x7F != want:
                    if v == 255 and page[off + x] & 0x80:
                        self.star_under += 1    # a star under a figure's pixel that is only OR'd: the figure's colour wins
                        continue
                    if page[off + x] & 0x80:
                        self.or_overlap += 1    # two figures overlap at a pixel the upper one only ORs: the set mixes them
                        continue
                    bad += 1
                    if first is None:
                        first = (x, y, v, page[off + x], want)
        return bad, first


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the original; at every site run the hook on a copy of the state and compare with the original's run: every register
    with R, all 48K RAM bar the sites and the dead stack, the clock, the MMU, the game's ports in order. The picture at each blit
    against what the set's planes hold by the game's own operations (class Picture)."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    pic = Picture(patch)
    S = patch.syms
    known = {a for a in patch.blob['frames']}
    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)

    def site_bytes(k, target):
        return bytes((0xC3 if k == 'jp' else 0xCD, target & 255, target >> 8))

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        kind, sym = SITES[pc]
        if pc == 0xFDFD:
            if mem[0xFDFE] != 0x63 or mem[0xFDFF] != 0x9D:
                return
        if pc == 0x9E03 and (regs[12] < 0x4000):
            return
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, mem))
        patched = bytearray(mem)
        for a, k, target in patch.sites:
            if k == 'ld':
                patched[a + 1:a + 3] = bytes((target & 255, target >> 8))
            else:
                patched[a:a + 3] = site_bytes(k, target)
        if pc == 0xFDFD:
            patched[0xFDFE] = S['h_isr'] & 255
            patched[0xFDFF] = S['h_isr'] >> 8
        ref = simpool.machine(Simulator, list(mem), regs, 'silk-ref')
        ports = RefPorts()
        ref.set_tracer(ports)
        R = ref.registers
        sp = regs[12]
        if kind == 'ret':
            ret = mem[sp] | mem[sp + 1] << 8
            n = 0
            while n == 0 or R[24] != ret or R[12] != sp + 2:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stopf = lambda r, v: r[24] == ret and r[12] == sp + 2
        elif kind == 'ei':
            ref.opcodes[ref.memory[R[24]]]()
            ref.opcodes[ref.memory[R[24]]]()
            ref.opcodes[ref.memory[R[24]]]()
            tgt = R[24]
            tsp = R[12]
            stopf = lambda r, v: r[24] == tgt and r[12] == tsp
        elif kind == 'isr':
            ret = mem[sp] | mem[sp + 1] << 8
            n = 0
            while n == 0 or R[24] != ret or R[12] != sp + 2:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            stopf = lambda r, v: r[24] == ret and r[12] == sp + 2
        else:
            n = 0
            while R[24] != kind or n == 0:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            tgt = kind
            stopf = lambda r, v: r[24] == tgt
        # the picture: before the hook, what the game is about to do
        back0 = st.page[S['V_BACK'] - 0x2000]
        speed0 = st.speed
        v9c = lambda a: mem[a] | mem[a + 1] << 8
        got, v, model = run_hook(patch, st, patched, regs, stopf)
        for i in CMP:
            if (bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': R[i], 'got': got[i], 'sym': sym})
                if i == 15:
                    c['R off %s %d' % (sym, (R[i] - got[i]) & 127)] += 1
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, k, target in patch.sites:
            n = 3
            at = a + 1 if k == 'ld' else a
            ln = 2 if k == 'ld' else 3
            expected[at - 0x4000:at - 0x4000 + ln] = actual[at - 0x4000:at - 0x4000 + ln] = patched[at:at + ln]
        expected[0xFDFE - 0x4000:0xFE00 - 0x4000] = actual[0xFDFE - 0x4000:0xFE00 - 0x4000]
        low = regs[12] - (72 if sym == 'h_isr' else 34)
        for a in range(max(0x4000, low), sp + (2 if sym == 'h_fill' else 0)):
            expected[a - 0x4000] = actual[a - 0x4000]
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 and sym != 'h_isr':
            fail('MMU not restored', {'pc': hex(pc), 'slot1': model.nr[0x51]})
        if model.nr[0x56] != 0 or model.nr[0x55] != 5:
            fail('MMU not restored', {'pc': hex(pc), 'sym': sym})
        want_clock = 3 if sym in FAST else (st.page[S['V_SPEED'] - 0x2000] if sym in BODY_SLOW else speed0)
        if model.nr[7] & 3 != want_clock:
            fail('clock differs', {'pc': hex(pc), 'sym': sym, 'got': model.nr[7], 'want': want_clock})
        if model.io != ports.io:
            fail('game ports differ', {'pc': hex(pc), 'sym': sym, 'orig': ports.io[:4], 'got': model.io[:4]})
        if model.ins != ports.ins:
            fail('game reads differ', {'pc': hex(pc), 'sym': sym})
        if sym == 'h_isr' and model.sel != 7:
            fail('interrupt leaves another register selected', {'pc': hex(pc), 'sel': model.sel})
        c['hooks'] += 1
        c['hooks ' + sym] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        # ---- the picture
        if sym in ('h_p', 'h_w') and not mem[0x9C94]:
            a = v9c(0x9C97)
            if a not in known:
                c['frames not in the set images'] += 1
            pic.plot(a, 24, 3, mem[0x9C93], mem[0x9C95], white=sym == 'h_w')
        elif sym == 'h_s' and not mem[0x9C9A]:
            a = v9c(0x9C9D)
            if a not in known:
                c['frames not in the set images'] += 1
            pic.plot(a, 8, 1, mem[0x9C99], mem[0x9C9B])
        elif sym == 'h_clear':
            ref2 = simpool.machine(Simulator, list(mem), regs, 'silk-ref2')
            ref2.set_tracer(RefPorts())
            ret = pc + 3
            n = 0
            while n == 0 or ref2.registers[24] != ret or ref2.registers[12] != sp:
                ref2.opcodes[ref2.memory[ref2.registers[24]]]()
                n += 1
            pic.clear(ref2.memory)
        elif sym == 'h_stars':
            m2 = ref.memory
            for i in range(20):
                x, y = m2[0x7816 + i * 2], m2[0x7817 + i * 2]
                pic.star(x, y)
                x2 = x + 160
                pic.star(x2 & 255, y + (1 if x2 > 255 else 0))
            if mem[0x9CC8]:
                pic.phase = (getattr(pic, 'phase', 0) + 1) & 15
        elif sym == 'h_wave':
            pic.phase = 0
        elif sym == 'h_ground':
            wave = mem[0x9CC0]
            pic.ground(wave, getattr(pic, 'phase', 0), bool(mem[0x9CCA]), mem[0xDDE0 + wave])
        elif sym == 'h_buf':
            pic.text(regs[7], regs[2] << 8 | regs[3])
            c['characters drawn'] += 1
        elif sym == 'h_title':
            if model.nr[0x12] != 27 or model.nr[0x69] != 0x80:
                fail('title image not shown', {'pc': hex(pc), 'bank': model.nr[0x12], 'on': model.nr[0x69]})
            c['title checks'] += 1
        elif sym == 'h_blit':
            if st.page[S['V_SPEED'] - 0x2000] != 0:
                fail('the game clock latched wrong', {'pc': hex(pc), 'speed': st.page[S['V_SPEED'] - 0x2000]})
            nb = pic.bits_differ(mem)
            if nb:
                c['buffer bits not in the picture'] += nb
                c['pictures with such bits'] += 1
                if nb > 16:
                    fail('a writer of the buffer missed', {'pc': hex(pc), 'bits': nb})
            if st.page[S['V_FLIP'] - 0x2000] != 1:
                fail('picture never flipped', {'pc': hex(pc)})
            if model.spr:
                st.icons = model.spr
            want = [0]
            for n in range(5):
                want += [32 + 16 * n, 200, 0, 0x80 if v[0x53A0 + 2 * n] == 0x7F else 0]
            if st.icons != want and (st.icons or any(want[4::4])):
                fail('lives icons differ', {'pc': hex(pc), 'got': st.icons, 'want': want})
            c['lives icons compared'] += 1
            bad, first = pic.compare(st, st.page[S['V_BACK'] - 0x2000])
            if bad:
                fail('picture differs from the set', {'pixels': bad, 'first': first})
            c['pictures compared'] += 1
            c['stale picture bits (a restart)'] = pic.stale
            c['stars under OR pixels'] = pic.star_under
            c['overlaps at OR pixels'] = pic.or_overlap
            c['pixels compared'] += 128 * 224
        if progress and c['hooks'] % 2000 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), set(SITES), on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


def unit_tests(patch, states):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R, the clock, the MMU."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem in states:
        kind, sym = SITES[pc]
        if sym == 'h_isr':
            continue
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15], rr[26] = refresh, iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    ref.set_tracer(RefPorts())
                    R = ref.registers
                    if kind == 'ei':
                        ref.opcodes[ref.memory[R[24]]]()
                        ref.opcodes[ref.memory[R[24]]]()
                        ref.opcodes[ref.memory[R[24]]]()
                        tgt, tsp = R[24], R[12]
                        stopf = lambda r, v: r[24] == tgt and r[12] == tsp
                    else:
                        n = 0
                        while R[24] != kind or n == 0:
                            ref.opcodes[ref.memory[R[24]]]()
                            n += 1
                        tgt = kind
                        stopf = lambda r, v: r[24] == tgt
                    st = State(patch)
                    st.page[patch.syms['V_SPEED'] - 0x2000] = speed
                    patched = bytearray(mem)
                    for a, k, target in patch.sites:
                        if k == 'ld':
                            patched[a + 1:a + 3] = bytes((target & 255, target >> 8))
                        else:
                            patched[a:a + 3] = bytes((0xC3 if k == 'jp' else 0xCD, target & 255, target >> 8))
                    got, v, model = run_hook(patch, st, patched, rr, stopf, speed=speed)
                    if any((bool(R[i]) != bool(got[i])) if i == 26 else R[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    want = 3 if sym == 'h_loop' else speed
                    if model.nr[7] & 3 != want:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x56] != 0 or model.nr[0x55] != 5:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def mutate(name, old, new, after=0x2800):
        b = copy.copy(patch)
        b.ram = bytearray(patch.ram)
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.find(bytes.fromhex(old), after - 0x2800)
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new) // 2] = bytes.fromhex(new)
        b._banks()
        out[name] = b
    S = patch.syms
    v = lambda n: '%02X%02X' % (S[n] & 255, S[n] >> 8)
    mutate('R off by one', '3EF4CD', '3EF5CD')
    mutate('clock not restored at the ground', 'F53A' + v('V_SPEED') + 'ED9207F1', 'F53E0300ED9207F1')
    mutate('figure one row off', 'C608', 'C609', S['fig_p'])
    mutate('figure one column off', 'D608', 'D609', S['fig_p'])
    mutate('MMU slot 6 left mapped', 'ED915600ED915505', '00000000ED915505')
    mutate('old boxes never wiped', 'E5E5E5E5', '00000000')
    mutate('silhouette not white', '3E01', '3E00', S['h_w'])
    mutate('interrupt leaves another register selected', '013B243E07ED79', '00000000000000', S['h_isr'] + 30)
    mutate('characters not on Layer 2', 'CD' + v('buf_char'), '000000')
    mutate('picture never flipped', '3E01', '3E00', S['h_blit'])
    mutate('lives icons do not follow the screen', 'FE7F', 'FE00')
    mutate('title image never set', 'ED9112' + '1B', 'ED9112' + '10')
    return out


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}


# ---- nexclash.py auto: the published builds, boot-checked; with recordings the Enhanced replay proof -------------------
import hashlib

LOAD_SCREEN = 'silkworm_loading.scr'      # the Mastertronic Plus 128K tape's screen, beside the snapshot: game data, never in this repo
LOAD_MD5 = 'ff8f4e3e7648eca89d4bff22ed3ac9f6'
COLOURS_MD5 = '8eaea241f660d8b9616aa35a6b19bf5c'   # COLOURS, built from the Spec256 set: beside the snapshot, never in this repo
PUBLISHER = 'Virgin Games, 1989'
NEG_STOP = 1000                           # frames of the first recording each deliberately broken build replays
NEG_LONG = 9004                           # 'characters not on Layer 2' needs the first GAME OVER, late in that recording
# Each tested alone in the simulator (games/silkworm.md "Cheats"); the published patch's three.
TRAINERS = '''NInfinite lives
Z 8 38052 182 0
NImmune jeep
Z 8 38505 0 0
NImmune helicopter
Z 8 38561 0 0
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
    snapshot, except the start-up tail's own bytes. The game's code at 5B00 must be back after NEXLOAD. -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    patch.apply(s)
    size = len(zt.build_tail(s, TAIL_ADDR, patch.slot1, True)[0])
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 65536):
            if TAIL_ADDR <= a < TAIL_ADDR + size:
                continue
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else s.port7ffd & 7
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
    return bad


def _replay(z80, colours, rzx, stop, collect):
    """One recording's Enhanced replay (a process of its own) -> (counts, examples, states)."""
    got = verify(Enhanced(z80, colours), rzx, stop=stop, collect=collect)
    return got if collect else (got[0], got[1], [])


def _negative(z80, colours, name, rzx, stop):
    """One deliberately broken build's replay (a process of its own): -> (name, its failure keys)."""
    try:
        return name, sorted(run_negative(negative_patches(Enhanced(z80, colours))[name], rzx, stop))
    except Exception as e:                  # noqa: BLE001 - a broken hook that runs off into data is caught too
        return name, ['exception ' + type(e).__name__]


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build (no hooks, start-up only) and, with the colour blob beside the snapshot, the
    Enhanced build; each with the loading screen when it is beside the snapshot, as published; every build boot-checked.
    With --rzx the Enhanced replay proof of each recording, the ABI cases and the broken builds. The pace, soak,
    flicker and real loader proofs are the review run's (games/silkworm.md "Evidence")."""
    import concurrent.futures, os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'pok', None):
        trainers = out / (name + '_verified.pok')
        trainers.write_text(TRAINERS)
        a.pok = str(trainers)
    say('Game      : Silkworm (Random Access / Virgin Games, 1989, 128K)')
    say('Engine    : silkworm; default: the original game, start-up fixes only (no clash to remove); '
        "Enhanced: the Spec256 set's colours on a double-buffered Layer 2; original pace")
    ok = True
    screen = _beside(z80, LOAD_SCREEN, LOAD_MD5, 'the original loading screen')
    colours = _beside(z80, COLOURS, COLOURS_MD5, 'the colour blob this engine was proved with')
    if screen is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    if colours is None:
        say('Enhanced  : no %s beside the snapshot: default build only' % COLOURS)
    builds = [('Default', name, lambda: Patch(z80))]
    if colours is not None:
        builds.append(('Enhanced', name + '_enhanced', lambda: Enhanced(z80, colours)))
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
            say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM, 5B00 back; converter loader and NEXLOAD)'
                                    if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    rzxs = list(getattr(a, 'rzx', None) or [])
    if rzxs and colours is not None and not all((colours.parent / n).is_file() for n in (SET_NAME, PAL_NAME)):
        say('Verify    : FAILED: recordings given but no %s and %s beside the snapshot (the replay model reads the set '
            'afresh)' % (SET_NAME, PAL_NAME))
        ok = False
    elif rzxs and colours is None:
        say('Verify    : FAILED: recordings given but no %s beside the snapshot (the default runs no hook; the replay '
            'proves Enhanced)' % COLOURS)
        ok = False
    elif rzxs:
        stop = getattr(a, 'quick', None)
        workers = min(len(rzxs), os.cpu_count() or 1)
        with concurrent.futures.ProcessPoolExecutor(workers) as pool:
            done = list(pool.map(_replay, [z80] * len(rzxs), [colours] * len(rzxs), rzxs, [stop] * len(rzxs),
                                 [1] + [0] * (len(rzxs) - 1)))
        states = []
        for path, (c, ex, got) in zip(rzxs, done):
            states += got
            fail = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fail
            say('Verify    : %s %d frames, %d hooks, %d R comparisons, %d pictures, %d pixels: %s' % (
                Path(path).name, c['frames'], c['hooks'], c['R comparisons'], c['pictures compared'], c['pixels compared'],
                'IDENTICAL' if not fail else str(fail)))
            for k in ('stale picture bits (a restart)', 'stars under OR pixels', 'overlaps at OR pixels', 'buffer bits not in the picture'):
                if c.get(k):
                    say('            %s: %d (known, games/silkworm.md "Known issues")' % (k, c[k]))
            for k, v in ex.items():
                say('            %s: %s' % (k, v))
        counts = unit_tests(Enhanced(z80, colours), states)
        fail = {k: v for k, v in counts.items() if k.endswith('!')}
        ok = ok and not fail
        say('Unit      : %s' % dict(counts))
        names = list(negative_patches(Enhanced(z80, colours)))
        stops = [NEG_LONG if n.startswith('characters') else NEG_STOP for n in names]
        with concurrent.futures.ProcessPoolExecutor(min(len(names), os.cpu_count() or 1)) as pool:
            neg = list(pool.map(_negative, [z80] * len(names), [colours] * len(names), names, [rzxs[0]] * len(names), stops))
        missed = [n for n, keys in neg if not keys]
        ok = ok and not missed
        say('Negatives : %d of %d broken builds caught%s' % (len(neg) - len(missed), len(neg), '; MISSED %s' % missed if missed else ''))
    else:
        say('Verify    : not requested; boot evidence only')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
