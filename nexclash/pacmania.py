"""Pac-Mania (Grandslam / Teque, 1988, the 128K release with AY music) engine 'pacmania'. Additive module: reachable
only through is_pacmania(). Facts and design: games/pac_mania.md.

The release's snapshot waits in BASIC (PAUSE 0 over the loading screen, then ': RANDOMIZE USR 30000'). That BASIC
runs through the 128 editor (ROM 0) and the printer buffer's ROM-switching code, which NEXLOAD overwrites, so the
build starts the game itself: PC = 0x7530, interrupts off (its first instructions are CPL, DI), all memory as in the
file. The loading screen shows while the .nex loads. 0x7530 finds the AY bank (bank 1) and sets 0xB332: the music
plays.

Back buffer + undo: A8FA saves under each figure (A9CA), sorts by y (A93A) and plots (AE73); B090 blits
the buffer's window to the ULA; AB3B restores. One plotter, 86 static 16x16 frames (0xBB38) with masks
(0xC5F8 + 32 * table 0xB418[frame]). The play area has one attribute (0xB336), bar Pac-Man's two
yellow cells painted by 89DF. Build: the plotter's writes and 89DF's attribute writes become NOPs, and a
stateless commit at the end of the blit sets one hardware sprite per record of the game's own tables.
"""
import collections
import copy
import hashlib
import json
import os

RECORD = 'pac_mania'
ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5E00          # BASIC's dead program / work space: never read once the PAUSE ends (poison-tested)
HOOK_RAM = (0x5B70, 0x5B74)  # hlib_r (3 bytes) + the speed latch: 128K system variables N_STR1 / HD_, unused
TAIL_FREE = (0x5D00, 0x5FB0)  # the tail may only go here
PAUSE_PC = 0x1F3D           # the release's snapshot: HALT in the ROM's PAUSE
START_PC = 0x7530           # what its ': RANDOMIZE USR 30000' calls: the game's own start
GFX, MASK, MASKTAB, NFRAME = 0xBB38, 0xC5F8, 0xB418, 86
# frames whose top 8 rows are copied at run time: frame -> (graphics table, mask table, forms, first pattern, gfx, mask)
FORMS = {85: (0xCC18, 0xCD18, 10, 86, 0xC5D8, 0xCB98),    # fruit score, 0x96B8
         81: (0xCBB8, 0xCCB8, 6, 96, 0xC558, 0xCB78)}     # ghost score, 0x9224
NPAT = 102
COUNT, ROOM, ORDER, RECS, SCROLL = 0xB335, 0xB336, 0xA982, 0xB3B4, 0xB3E6
BUF = (0xE000, 0xF800)
CALLS = {0x87AA: ('cd90b0', 'e_b1'), 0x88E9: ('cd90b0', 'e_b2'), 0x891B: ('cd90b0', 'e_b3'),
         0x7B9A: ('cd90b0', 'e_b4'), 0xB094: ('cd1faf', 'e_hide')}
PLOT_NOPS = (0xAEED, 0xAEF4, 0xAEFB)
ATTR_NOPS = (0x8A17, 0x8A1B)
EXITS = {0x87AD: 'play', 0x88EC: 'play', 0x891E: 'play', 0x7B9D: 'theatre'}
INTERIORS = tuple(a + k for a in CALLS for k in (1, 2))
YELLOW_CELLS = frozenset(0x594B - 32 * r + c for r in range(6) for c in (0, 1))
WINDOW = (8, 167, 8, 183)
SLOTS = 12
# 2-14: fixed colours (a painted set only); 15 black; row inks are the attribute's. As the asm's `fixed`.
FIXED = (0xE8, 0xB8, 0xF6, 0xF1, 0x56, 0x6E, 0xB7, 0xFC, 0x54, 0xBE, 0xF8, 0xFF, 0xD8, 0x00)
PALETTE = (0x00, 0xFF) + FIXED                # the sheet's slots: 1 stands for the figure's run-time ink

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_colours.json')
NOTE = ('Pac-Mania colour map (docs/COLOURS.md): key = graphics byte (hex address, check = its value), 8 nibbles, '
        '0 = default (1 run-time ink / 15 black paper / transparent); optional 4th = transparent mask')
RECOLOUR = {'game': RECORD, 'output': 'sprites', 'colours': 'docs/profiles/pac_mania_colours.json', 'clear': True,
            'note': NOTE}
from .hooklib import CMP_R as CMP   # every register, R included; not T / MEMPTR
HOOKS = ('e_b1', 'e_b2', 'e_b3', 'e_b4', 'e_hide', 'c1', 'c2', 'c3', 'c4')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_pacmania(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '128K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours():
    from . import coloursheet as cs
    from .recolour import build_colours_path
    return cs.load(build_colours_path(COLOURS))


# --------------------------------------------------------------------------------------------- patterns

def key_of(frame, row, byte):
    return '%04X' % (GFX + 32 * frame + 2 * row + byte)


def sources(peek, p, r, b):
    """Pattern p, row r, byte b -> (graphics address (the colour key), mask address). Patterns from 86:
    a score frame with that form in its top 8 rows."""
    if p >= NFRAME:
        for fr, (gt, mt, n, first, _, _) in FORMS.items():
            if first <= p < first + n:
                if r < 8:
                    return gt + 16 * (p - first) + 2 * r + b, mt + 16 * (p - first) + 2 * r + b
                p = fr
                break
    return GFX + 32 * p + 2 * r + b, MASK + 32 * peek(MASKTAB + p) + 2 * r + b


def frame_nibbles(peek, f, cmap=None):
    """16 rows of 16 nibbles: 0 clear, 1 ink, 15 paper (the mask without the graphic), or the map's."""
    cmap = cmap or {}
    rows = []
    for r in range(16):
        row = []
        for b in range(2):
            a, ma = sources(peek, f, r, b)
            g, k = peek(a), peek(ma)
            e = cmap.get('%04X' % a)
            if e and e[0] != g:
                e = None                      # another graphic at that address: defaults
            for i in range(8):
                v = (g >> (7 - i)) & 1 or (15 if (k >> (7 - i)) & 1 else 0)
                if e:
                    if len(e) > 3 and e[3] & (0x80 >> i):
                        v = 0
                    elif e[2][i]:
                        v = e[2][i]
                row.append(v)
        rows.append(row)
    return rows


def patterns(peek, cmap=None):
    out = bytearray()
    for f in range(NPAT):
        for row in frame_nibbles(peek, f, cmap):
            for k in range(0, 16, 2):
                out.append(row[k] << 4 | row[k + 1])
    return bytes(out)


def colour_inputs_md5(peek):
    return hashlib.md5(bytes(peek(a) for a in list(range(GFX, MASK + 32 * 46)) + list(range(0xCBB8, 0xCDB8)))).hexdigest()


def colour_identity(peek):
    return {'schema': 1, 'game': RECORD, 'engine': 'pacmania', 'keys': 'pacmania-1: %04X graphics byte, bit = pixel',
            'inputs': colour_inputs_md5(peek), 'geometry': hashlib.md5(bytes(peek(MASKTAB + i) for i in range(86))).hexdigest()}


def start_state(snap):
    """The release's snapshot (z80tonex.Z80Snapshot) -> the game's start, in place: PC 0x7530, interrupts off."""
    if not snap.is128:
        raise ValueError('Pac-Mania patch expects the 128K release (the 48K form has no AY music)')
    if snap.port7ffd & 0x37 != 0x10:
        raise ValueError('7FFD 0x%02X: expected ROM 1 (48 BASIC) and bank 0, unlocked' % snap.port7ffd)
    if snap.pc not in (PAUSE_PC, START_PC):
        raise ValueError('PC 0x%04X: expected the ROM PAUSE at 0x%04X' % (snap.pc, PAUSE_PC))
    snap.pc = START_PC                           # the game's start, as the BASIC line's USR 30000 gives it
    snap.iff1 = snap.iff2 = 0


class PacPatch:
    name = 'Pac-Mania figures -> hardware sprites (altrom, commit at the end of the blit, R and speed restored)'

    def __init__(self, prof=None, colours=None, fixed=None):
        """colours: a colour map (None: the profile's, {}: none); fixed: palette slots 2-15 (None: FIXED)."""
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        setup = bytearray.fromhex(h['setup'])
        off = self.syms['fixed'] - self.syms['setup']
        if bytes(setup[off:off + len(FIXED)]) != bytes(FIXED):
            raise ValueError('profile: the setup palette is not FIXED')
        if fixed is not None:
            if len(fixed) != len(FIXED):
                raise ValueError('palette: %d slots, not %d' % (len(fixed), len(FIXED)))
            setup[off:off + len(FIXED)] = bytes(fixed)
        self.fixed = tuple(fixed) if fixed is not None else FIXED
        self.stub_extra = bytes(setup)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 256
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        self.make_page()
        self.sites = []
        for a, (old, sym) in CALLS.items():
            self.sites.append((a, bytes.fromhex(old), b'\xCD' + self.syms[sym].to_bytes(2, 'little')))
        for a in PLOT_NOPS:
            self.sites.append((a, b'\x02', b'\x00'))
        for a in ATTR_NOPS:
            self.sites.append((a, b'\x77', b'\x00'))
        self.extra_banks = {}
        self.pats = None
        self.colours = colours
        self.num_patterns = NPAT

    def make_page(self):
        from .build import rom48
        page = bytearray(rom48()[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)

    def apply(self, snap):
        """snap: z80tonex.Z80Snapshot of the 128K release (BASIC's PAUSE over the loading screen)."""
        start_state(snap)
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[HOOK_RAM[0] - 0x4000:HOOK_RAM[1] - 0x4000]):
            raise ValueError('hook RAM 0x%04X-0x%04X is not zero in this snapshot' % HOOK_RAM)
        cmap = self.colours if self.colours is not None else load_colours()
        self.pats = patterns(lambda a: ram[a - 0x4000], cmap)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {11: self.pats + bytes(16384 - len(self.pats)), 12: self.page + bytes(8192)}


def recolour(nex, cmap):
    """Built sprite .nex + colour map -> (new .nex, info). Only bank 11 (patterns) changes."""
    from .recolour import nex_offsets
    d = bytearray(nex)
    off = nex_offsets(d)
    if not {5, 2, 0, 11, 12} <= set(off):
        raise ValueError('not a Pac-Mania sprite build: banks missing')
    bank = lambda b: bytes(d[off[b]:off[b] + 16384])
    ram = bank(5) + bank(2) + bank(0)
    peek = lambda a: ram[a - 0x4000]
    p0 = PacPatch(colours={})
    if bytes(peek(a) for a in range(load_profile()['signature']['addr'], load_profile()['signature']['addr'] + 8)) != \
            bytes.fromhex(load_profile()['signature']['bytes'])[:8]:
        raise ValueError('game code differs')
    for a, old, new in p0.sites:
        if bytes(peek(a + k) for k in range(len(new))) != new:
            raise ValueError("patch site 0x%04X does not hold this build's hook" % a)
    if bank(12) != p0.page + bytes(8192):
        raise ValueError('hook code differs from this version (rebuild)')
    pats = patterns(peek, cmap)
    new = pats + bytes(16384 - len(pats))
    changed = [11] if bank(11) != new else []
    d[off[11]:off[11] + 16384] = new
    return bytes(d), {'banks changed': changed}


# --------------------------------------------------------------------------------------------- sprites -> pixels

class NextState:
    """The NextREGs a hook may touch: sprite attributes (0x34-0x39) and the CPU speed (7, read back through
    0x243B / 0x253B as the core composes it). Anything else is counted in .other."""
    def __init__(self, speed=0):
        self.nr = {0x07: speed}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.other = collections.Counter()
        self.sel = None

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg not in (0x34, 0x07):
            self.other[reg] += 1

    def read(self, port):
        """A NextREG read (port 0x253B after a select at 0x243B), or None for another port."""
        if port == 0x253B and self.sel is not None:
            v = self.nr.get(self.sel, 0)
            return (v & 3) << 4 | (v & 3) if self.sel == 0x07 else v
        return None

    def write(self, port):
        return port in (0x243B, 0x253B)


def sprite_view(a):
    """Attributes -> None (hidden) or (screen x, screen y, pattern, palette offset)."""
    if not a[3] & 0x80:
        return None
    pat = (a[3] & 0x3F) * 2 + (1 if a[4] & 0x40 else 0)
    return a[0] + (a[2] & 1) * 256 - 32, a[1] + (a[4] & 1) * 256 - 32, pat, a[2] >> 4


def overlay(attrs, pats):
    """Visible sprites in hardware order, clipped to the window -> {(x, y): nibble}."""
    out = {}
    for i in range(SLOTS):
        v = sprite_view(attrs[i])
        if v is None:
            continue
        x0, y0, p, _ = v
        for j in range(16):
            y = y0 + j
            if not WINDOW[2] <= y <= WINDOW[3]:
                continue
            base = p * 128 + j * 8
            for k in range(16):
                x = x0 + k
                if WINDOW[0] <= x <= WINDOW[1]:
                    b = pats[base + k // 2]
                    n = (b >> 4) if k % 2 == 0 else (b & 15)
                    if n:
                        out[(x, y)] = n
    return out


def scr_addr(x, y):
    return 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)


def composite_diff(orig_scr, pat_scr, ov):
    """orig_scr / pat_scr: 6144 pixel bytes. Patched ULA + sprites against the original's ULA, as ink
    bits (paper nibble 15 = 0 bit). -> number of pixels that differ."""
    if orig_scr == pat_scr and not ov:
        return 0
    p = bytearray(pat_scr)
    for (x, y), n in ov.items():
        a = scr_addr(x, y) - 0x4000
        m = 0x80 >> (x & 7)
        if n == 15:
            p[a] &= ~m & 255
        else:
            p[a] |= m
    if bytes(p) == bytes(orig_scr):
        return 0
    return sum(bin(a ^ b).count('1') for a, b in zip(p, orig_scr))


# --------------------------------------------------------------------------------------------- lockstep replay

def _alt_rom(patch):
    from .build import rom48
    a = bytearray(rom48())
    a[0x2000:0x4000] = patch.page
    return a


class _Run:
    """One replay machine. 128K: a flat 64K view (bank 5, 2 and the paged bank) plus the banks off the top, swapped
    on each 7FFD write; ROM 1 = Sinclair's 48K ROM on both sides (the Next's whole alt ROM image), with the hooks
    over 0x386E- on the patched side. Frames by RZX fetch count; fetches in hook ROM (ROM_ORG-0x3FFF) are not
    counted, so the original and the patched game take each interrupt at the same game instruction. R is NOT held:
    the hooks restore it (lib/hlib_r.asm), and the frame compare includes it."""

    def __init__(self, snap, patch=None, speed=0):
        from skoolkit.simulator import Simulator
        from skoolkit.simutils import from_memory
        from . import z80n
        from .build import rom48
        ram = snap.ram(-1)
        if len(ram) != 0x20000:
            raise ValueError('a 128K recording is expected (the 128K release)')
        self.banks = [bytearray(ram[16384 * i:16384 * (i + 1)]) for i in range(8)]
        self.o7 = snap.out7ffd
        self.page = self.o7 & 7
        mem = bytearray(65536)
        mem[0:0x4000] = _alt_rom(patch) if patch else rom48()
        mem[0x4000:0x8000] = self.banks[5]
        mem[0x8000:0xC000] = self.banks[2]
        mem[0xC000:0x10000] = self.banks[self.page]
        regs = {'A': snap.a, 'F': snap.f, 'BC': snap.bc, 'DE': snap.de, 'HL': snap.hl, 'IX': snap.ix, 'IY': snap.iy,
                'SP': snap.sp, 'I': snap.i, 'R': snap.r, '^A': snap.a2, '^F': snap.f2, '^BC': snap.bc2, '^DE': snap.de2,
                '^HL': snap.hl2, 'PC': snap.pc, 'MEMPTR': snap.memptr}
        self.sim = from_memory(Simulator, mem, regs, {'im': snap.im, 'iff': snap.iff1, 'tstates': snap.tstates},
                               {'int_active': 0})
        self.mem, self.R, self.ops = self.sim.memory, self.sim.registers, self.sim.opcodes
        self.ns = NextState(speed)
        self.patch = patch
        self.events = []
        self.hook = collections.Counter()
        self.sp_low = 65536
        self.hook_regs = None
        self.hook_bad = 0
        self.speed_in = None
        self.speed_bad = 0
        self.rom0 = 0
        self.locked_writes = 0
        if patch:
            for a, old, new in patch.sites:
                for k, v in enumerate(new):
                    self.mem[a + k] = v
        z80n.install(self.sim, self.ns.nextreg, strict=False)
        run = self

        class Tr:
            def read_port(s, regs, port):
                v = run.ns.read(port)
                if v is not None:
                    return v
                run.pi += 1
                return run.data[run.pi - 1]

            def write_port(s, regs, port, value, *x):
                if port == 0x243B:
                    run.ns.sel = value
                elif port & 0x8002 == 0:
                    run.out7ffd(value)
        self.sim.set_tracer(Tr())
        self.data, self.pi = b'', 0

    def out7ffd(self, value):
        if self.o7 & 0x20:
            self.locked_writes += 1
            return
        if not value & 0x10:
            self.rom0 += 1                       # ROM 0 (the 128 editor) is not modelled: the game never pages it
        new = value & 7
        if new != self.page:
            m = self.mem
            self.banks[self.page][:] = m[0xC000:0x10000]
            m[0xC000:0x10000] = self.banks[new]
            self.page = new
        self.o7 = value

    def bank(self, b):
        """Bank b's bytes now (5 and 2 from the view; the paged one from the view)."""
        m = self.mem
        if b == 5:
            return m[0x4000:0x8000]
        if b == 2:
            return m[0x8000:0xC000]
        if b == self.page:
            return m[0xC000:0x10000]
        return bytes(self.banks[b])

    def buf(self):
        return self.mem[BUF[0]:BUF[1]] if self.page == 0 else bytes(self.banks[0][BUF[0] - 0xC000:BUF[1] - 0xC000])

    def frame(self, count, start, end, data, ev):
        R, mem, ops = self.R, self.mem, self.ops
        self.data, self.pi = data, start
        pc = R[24]
        while count > 0:
            pc = R[24]
            if pc in ev:
                self.on_event(pc)
            op = mem[pc]
            if ROM_ORG <= pc < 0x4000:
                self.in_hook(pc)
                ops[op]()
                if not ROM_ORG <= R[24] < 0x4000:
                    self.hook_out()
                continue
            if op == 0xDD or op == 0xFD:
                r0 = R[15]
                ops[op]()
                count -= 2 - ((R[15] ^ r0) % 2)
            else:
                ops[op]()
                count -= 2 if op == 0xCB or op == 0xED else 1
        while ROM_ORG <= R[24] < 0x4000:          # a hook entered by the frame's last instruction runs on
            self.in_hook(R[24])
            ops[mem[R[24]]]()
            if not ROM_ORG <= R[24] < 0x4000:
                self.hook_out()
        self.hook_regs = None
        if self.pi != end:
            raise RuntimeError('port readings out of step: %d of %d' % (self.pi, end))
        return pc

    def in_hook(self, pc):
        R = self.R
        self.hook[pc] += 1
        now = (R[8], R[9], R[10], R[11], R[14], R[26])     # IX, IY, I, IFF: nothing a hook may write
        if self.hook_regs is None:
            self.hook_regs = now
            self.speed_in = self.ns.nr[7]
        elif now != self.hook_regs:
            self.hook_bad += 1
        if R[12] < self.sp_low:
            self.sp_low = R[12]

    def hook_out(self):
        if self.ns.nr[7] != self.speed_in:
            self.speed_bad += 1
        self.hook_regs = None

    def on_event(self, pc):
        self.events.append((pc, self.snap_event(pc)))

    def snap_event(self, pc):
        m = self.mem
        if pc == 0xA8FA:
            return (bytes(self.buf()),)
        return (bytes(m[0x4000:0x5B00]), bytes(self.buf()), [list(a) for a in self.ns.attr[:SLOTS]],
                m[ROOM], [(m[RECS + 4 * i], m[RECS + 4 * i + 1], m[RECS + 4 * i + 2], m[RECS + 4 * i + 3]) for i in range(12)],
                [m[ORDER + 2 * i] | m[ORDER + 2 * i + 1] << 8 for i in range(12)], m[COUNT])

    def accept(self, pc):
        R, mem = self.R, self.mem
        R[25] = 0
        if R[26]:
            if mem[pc] == 0x76:
                R[24] = (R[24] + 1) % 65536
            self.sim.accept_interrupt(R, mem, 0)


def _segments(patch, page=0):
    """[0x5B00, 0x10000) minus the patch sites, the hook RAM and (bank 0 paged) the buffer, as (lo, hi) slices."""
    cuts = sorted([(a, a + len(new)) for a, old, new in patch.sites] + [HOOK_RAM] + ([BUF] if page == 0 else []))
    out, lo = [], 0x5B00
    for a, b in cuts:
        if a >= 0x5B00:
            if a > lo:
                out.append((lo, a))
            lo = max(lo, b)
    out.append((lo, 0x10000))
    return out


def verify(patch, rzx_path, stop=None, collect=0, progress=None, skip_pats=False):
    """Lockstep: the original game and the patched build (its real hook bytes) replay the RZX side by
    side. Every frame: registers and memory outside the buffer and sites. At each plot pass's start:
    the two buffers equal. At each blit's end: patched ULA + sprites = the original's ULA, attributes
    (the yellow cells excepted), each sprite's ink, the buffer unchanged. Idle frames: the same picture,
    so a stale sprite shows. Failure keys end in '!'."""
    from skoolkit.rzxplay import parse_rzx, InputRecording
    from skoolkit.snapshot import Snapshot
    c = collections.Counter()
    ex = collections.defaultdict(list)
    segs = _segments(patch)
    ev = set(EXITS) | {0xA8FA}
    frame_no = 0
    frames_seen = collections.Counter()

    def fail(k, *info):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((frame_no,) + info)

    o = p = None
    state = {'pass': False, 'blit': False}
    last_room = None
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    for block in parse_rzx(rzx_path):
        obj = block.obj
        if isinstance(obj, Snapshot):
            o, p = _Run(obj), _Run(obj, patch)
            continue
        if not isinstance(obj, InputRecording):
            continue
        for fr in obj.frames:
            if fr.fetch_counter <= 0:
                frame_no += 1
                continue
            pc1 = o.frame(fr.fetch_counter, fr.start, fr.end, obj.data, ev)
            pc2 = p.frame(fr.fetch_counter, fr.start, fr.end, obj.data, ev)
            # events, in order
            if [e[0] for e in o.events] != [e[0] for e in p.events]:
                fail('event order differs', [e[0] for e in o.events][:4], [e[0] for e in p.events][:4])
            for (pc, eo), (_, ep) in zip(o.events, p.events):
                if pc == 0xA8FA:
                    c['plot passes'] += 1
                    state['pass'] = ep[0]
                    if eo[0] != ep[0]:
                        fail('buffers differ before a plot pass', sum(a != b for a, b in zip(eo[0], ep[0])))
                else:
                    kind = EXITS[pc]
                    c['blits ' + kind] += 1
                    ov = overlay(ep[2], patch.pats)
                    d = composite_diff(eo[0][:6144], ep[0][:6144], ov)
                    if d:
                        fail('blit: ULA + sprites != the original', d, pc)
                    c['sprite pixels compared'] += len(ov)
                    if state['pass'] and state['pass'] != ep[1]:
                        fail('the plotter wrote the patched buffer')
                    # attributes
                    adiff = [0x5800 + i for i in range(768) if eo[0][6144 + i] != ep[0][6144 + i]]
                    bad = [a for a in adiff if a not in YELLOW_CELLS or ep[0][6144 + a - 0x5800] != ep[3]]
                    if bad and kind == 'play':
                        fail('attributes outside the yellow cells', bad[:4])
                    if kind == 'play':
                        bad2 = [a for a in YELLOW_CELLS if ep[0][a - 0x4000] != ep[3]]
                        if bad2:
                            fail('yellow cells not the room colour', hex(ep[0][bad2[0] - 0x4000]), hex(ep[3]))
                    # colours + census
                    roomink = (ep[3] & 7) | (8 if ep[3] & 0x40 else 0)
                    for n in range(SLOTS):
                        v = sprite_view(ep[2][n])
                        if v is None:
                            continue
                        rec = ep[5][n]
                        want = 14 if kind == 'play' and rec == RECS else roomink
                        if v[3] != want:
                            fail('sprite ink', n, v[3], want)
                        frames_seen[v[2]] += 1
                        if rec == RECS:
                            c['sprites: record 0xB3B4'] += 1
                        else:
                            c['sprites: other'] += 1
                        # census: this figure's ink pixels in the original's cells
                        ownatt = 0x46 if want == 14 else ep[3]
                        base = v[2] * 128
                        for j in range(16):
                            y = v[1] + j
                            if not WINDOW[2] <= y <= WINDOW[3]:
                                continue
                            for k in range(16):
                                x = v[0] + k
                                if not WINDOW[0] <= x <= WINDOW[1]:
                                    continue
                                b = patch.pats[base + j * 8 + k // 2]
                                if ((b >> 4) if k % 2 == 0 else (b & 15)) == 1:
                                    c['census: figure ink pixels'] += 1
                                    if (eo[0][6144 + (y >> 3) * 32 + (x >> 3)] & 0x47) != (ownatt & 0x47):
                                        c['census: figure ink pixels in a foreign colour'] += 1
                    if kind == 'play':
                        for a in YELLOW_CELLS:
                            if eo[0][a - 0x4000] != ep[3]:
                                c['census: yellow cells in play'] += 1
                                y0, x0 = ((a - 0x5800) >> 5) * 8, ((a - 0x5800) & 31) * 8
                                for yy in range(8):
                                    c['census: scenery pixels in yellow cells'] += bin(ep[0][scr_addr(x0, y0 + yy) - 0x4000]).count('1')
                    state['pass'] = False
            o.events, p.events = [], []
            # registers
            if o.R[24] != p.R[24]:
                fail('PC differs', hex(o.R[24]), hex(p.R[24]))
            diff = [i for i in CMP if o.R[i] != p.R[i]]
            if 0xB090 <= o.R[24] <= 0xB0E8 or 0xAE73 <= o.R[24] <= 0xAF0D:
                diff = [i for i in diff if i > 1]   # A / F inside the blit and plot loops follow the buffer's bytes
            if diff:
                fail('registers differ', diff[:6], [hex(o.R[i]) for i in diff[:6]], [hex(p.R[i]) for i in diff[:6]])
            # memory: the view (bank 5, 2, the paged bank) and every bank off the top
            mo, mp = o.mem, p.mem
            if o.page != p.page or o.o7 != p.o7:
                fail('paging differs', hex(o.o7), hex(p.o7))
            for lo, hi in _segments(patch, o.page):
                if mo[lo:hi] != mp[lo:hi]:
                    dd = [a for a in range(lo, hi) if mo[a] != mp[a]]
                    sp = o.R[12]
                    real = []
                    for a in dd:
                        if sp - 64 <= a < sp:
                            continue                 # dead stack: hooks push below SP
                        w = mp[a] | mp[a + 1] << 8 if a & 1 == (sp & 1) else mp[a - 1] | mp[a] << 8
                        if sp <= a < sp + 24 and ROM_ORG <= w < 0x4000:
                            continue                 # the blit's return address is c_n (see e_b1)
                        real.append(a)
                    if real:
                        fail('memory differs', [hex(a) for a in real[:6]], len(real))
            for b in range(8):
                if b in (5, 2) or b == o.page:
                    continue
                bo, bp = o.banks[b], p.banks[b]
                if b == 0:
                    lo, hi = BUF[0] - 0xC000, BUF[1] - 0xC000
                    same = bo[:lo] == bp[:lo] and bo[hi:] == bp[hi:]
                else:
                    same = bo == bp
                if not same:
                    fail('bank differs', b)
            # idle frames: same picture
            pc = o.R[24]
            if not state['pass'] and not 0xB090 <= pc <= 0xB0E8 and not 0xAF1F <= pc <= 0xAF52:
                c['idle frames compared'] += 1
                d = composite_diff(bytes(mo[0x4000:0x5800]), bytes(mp[0x4000:0x5800]), overlay(p.ns.attr, patch.pats))
                if d:
                    fail('idle frame: ULA + sprites != the original', d, hex(pc))
            o.accept(pc1)
            p.accept(pc2)
            frame_no += 1
            if progress and frame_no % 1000 == 0:
                progress(frame_no, c)
            if stop and frame_no >= stop:
                break
        if stop and frame_no >= stop:
            break
    c['frames'] = frame_no
    c['hook instructions'] = sum(p.hook.values())
    for name in HOOKS:
        c['hook ' + name] = p.hook[patch.syms[name]]
    c['hook low SP'] = p.sp_low
    if p.hook_bad:
        c['a hook changed IX, IY, I or IFF!'] = p.hook_bad
    if p.speed_bad:
        c['a hook left another CPU speed!'] = p.speed_bad
    if o.rom0 or p.rom0:
        c['ROM 0 paged (not modelled)!'] = o.rom0 + p.rom0
    c['7FFD writes while locked'] = o.locked_writes
    c['other nextregs in hooks'] = sum(p.ns.other.values())
    if p.ns.other:
        c['hook wrote a NEXTREG other than sprites and speed!'] = sum(p.ns.other.values())
    for a in sorted(site_bytes):
        if o.mem[a] != _orig_site(patch, a):
            c['game wrote a patch site!'] += 1
    c['distinct frames as sprites'] = len(frames_seen)
    res = (c, dict(ex))
    c.frames_seen = frames_seen
    return res + ([],) if collect else res


def _orig_site(patch, a):
    for s, old, new in patch.sites:
        if s <= a < s + len(new):
            return old[a - s]
    return None


# --------------------------------------------------------------------------------------------- unit tests

def _plot_truth(base, f, x, y, h, scroll, bg):
    """The ORIGINAL plotter on a canvas: buffer all bg -> {(screen x, screen y): bit} over the window."""
    from skoolkit.simulator import Simulator
    mem = bytearray(base)
    mem[BUF[0]:BUF[1]] = bytes([bg]) * (BUF[1] - BUF[0])
    mem[RECS:RECS + 4] = bytes((x, y, f, h))
    mem[SCROLL] = scroll
    sim = Simulator(mem, {})
    R = sim.registers
    R[24], R[12] = 0xA92F, 0x5FF0                # CALL AF0E; CALL AE73, IX = record
    R[8], R[9] = RECS >> 8, RECS & 255
    R[26] = 0
    n = 0
    while R[24] != 0xA935:
        sim.opcodes[mem[R[24]]]()
        n += 1
        if n > 20000:
            raise RuntimeError('plot did not end')
    # the blit's view: AF1F with H=8, L=0x10 at this scroll, stride 32, wrap at 0xF800 -> 0xE002
    start = 0xE000 + ((8 + scroll) % 192) * 32 + 2
    out = {}
    a = start
    for sy in range(8, 184):
        for col in range(20):
            v = mem[a + col]
            for b in range(8):
                out[(8 + col * 8 + b, sy)] = (v >> (7 - b)) & 1
        a += 32
        if a >> 8 == 0xF8:
            a = 0xE002
    return out


def _commit(patch, base, recs, count, sym='c1', room=0x45):
    """Run the commit from c_n on the patched memory until its JP back -> NextState."""
    from skoolkit.simulator import Simulator
    from . import z80n
    mem = bytearray(base)
    mem[0:0x4000] = _alt_rom(patch)
    mem[COUNT], mem[ROOM] = count, room
    for i, r in enumerate(recs):
        ad = RECS + 4 * i
        mem[ad:ad + 4] = bytes(r)
        mem[ORDER + 2 * i], mem[ORDER + 2 * i + 1] = ad & 255, ad >> 8
    sim = Simulator(mem, {})
    ns = NextState()
    ns.attr = [[0, 0, 0, 0xFF, 0] for _ in range(128)]
    z80n.install(sim, ns.nextreg)
    R = sim.registers
    R[24], R[12] = patch.syms[sym], 0x5FF0
    n = 0
    while R[24] < 0x4000:
        sim.opcodes[mem[R[24]]]()
        n += 1
        if n > 20000:
            raise RuntimeError('commit did not end')
    return ns, n


EXIT_OF = {'e_b1': 0xB090, 'e_b2': 0xB090, 'e_b3': 0xB090, 'e_b4': 0xB090, 'e_hide': 0xAF1F,
           'c1': 0x87AD, 'c2': 0x88EC, 'c3': 0x891E, 'c4': 0x7B9D}


def hook_case(patch, base, sym, speed, r0, recs=None, ret=None):
    """Run one hook from its entry to the address the original reaches at the same point (EXIT_OF), with NR 7 =
    speed and R = r0 coming in. -> (bad list, NextState). The original reaches that address with R as it was at the
    hook's entry (the CALL is the same; 0xB090 / 0xAF1F directly, 0x87AD.. straight from the blit's RET), so R must
    come out as it went in; every other register too, but HL in e_b*'s return-address swap, and NR 7 = speed."""
    from skoolkit.simulator import Simulator
    from . import z80n
    mem = bytearray(base)
    mem[0:0x4000] = _alt_rom(patch)
    recs = recs if recs is not None else [(40 + 10 * i, 50, i, 0) for i in range(12)]
    mem[COUNT], mem[ROOM] = len(recs), 0x45
    for i, r in enumerate(recs):
        ad = RECS + 4 * i
        mem[ad:ad + 4] = bytes(r)
        mem[ORDER + 2 * i], mem[ORDER + 2 * i + 1] = ad & 255, ad >> 8
    sp = 0x5FE0
    mem[sp:sp + 4] = bytes((0x97, 0xB0, 0x00, 0x70)) if sym == 'e_hide' else bytes((0xAD, 0x87, 0x34, 0x12))
    if ret is not None:
        mem[sp + 2], mem[sp + 3] = ret & 255, ret >> 8
    sim = Simulator(mem, {})
    ns = NextState(speed)
    z80n.install(sim, ns.nextreg)

    class Tr:
        def read_port(s, regs, port):
            v = ns.read(port)
            return 0xFF if v is None else v

        def write_port(s, regs, port, value, *x):
            if port == 0x243B:
                ns.sel = value
    sim.set_tracer(Tr())
    R = sim.registers
    for i, v in enumerate((0x12, 0xD7, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0x11, 0x22, 0x33, 0x44)):
        R[i] = v
    R[12], R[24], R[15], R[26] = sp, patch.syms[sym], r0, 1
    before = list(R)
    n = 0
    while ROM_ORG <= R[24] < 0x4000:
        sim.opcodes[mem[R[24]]]()
        n += 1
        if n > 50000:
            return ['did not end'], ns
    bad = []
    if R[24] != EXIT_OF[sym]:
        bad.append('exit 0x%04X, not 0x%04X' % (R[24], EXIT_OF[sym]))
    if R[15] != r0:
        bad.append('R 0x%02X, not 0x%02X' % (R[15], r0))
    if ns.nr[7] != speed:
        bad.append('speed %d, not %d' % (ns.nr[7], speed))
    skip = {15, 24, 25, 29} | ({6, 7} if sym.startswith('e_b') else set())
    diff = [i for i in CMP if i not in skip and R[i] != before[i]]
    if diff:
        bad.append('registers %s' % diff)
    if sym.startswith('e_b') and (mem[sp] | mem[sp + 1] << 8) != patch.syms['c' + sym[3]]:
        bad.append('return address not c%s' % sym[3])
    if ns.other:
        bad.append('other NEXTREGs %s' % dict(ns.other))
    return bad, ns


def hook_cases(patch, base):
    """Every hook at four incoming speeds and R values across the 7-bit wrap, with and without bit 7."""
    c = collections.Counter()
    ex = []
    for sym in HOOKS:
        for speed in range(4):
            for r0 in (0x00, 0x05, 0x7A, 0x7F, 0x80, 0xFB, 0xFF):
                bad, _ = hook_case(patch, base, sym, speed, r0)
                c['hook cases %s' % ('ok' if not bad else 'FAIL!')] += 1
                if bad and len(ex) < 4:
                    ex.append((sym, speed, hex(r0), bad))
    return c, ex


def unit_tests(patch, base, neg=()):
    """Every frame at the position edges against the original plotter's own pixels (canvas 0x00 and 0xFF);
    slot guards; e_hide both ways; each negative patch on the same cases must fail."""
    c = collections.Counter()
    POS = [(16, 8, 0), (0, 100, 0), (7, 3, 0), (15, 60, 0), (17, 60, 0), (100, 90, 5), (100, 4, 9), (160, 40, 0), (175, 120, 0),
           (176, 100, 0), (255, 50, 0), (40, 167, 8), (40, 168, 8), (90, 183, 0), (90, 184, 0), (90, 191, 0)]

    def one(pt, f, x, y, h, scroll, sym='c1', b0=None):
        b0 = base if b0 is None else b0
        ns, _ = _commit(pt, b0, [(x, y, f, h)], 1, sym, 0x45)
        ov = overlay(ns.attr, pt.pats)
        t0 = _plot_truth(b0, f, x, y, h, scroll, 0x00)
        t1 = _plot_truth(b0, f, x, y, h, scroll, 0xFF)
        bad = 0
        for xy in t0:
            n = ov.get(xy, 0)
            if t0[xy] and t1[xy]:
                want = 1
            elif not t0[xy] and not t1[xy]:
                want = 15
            else:
                want = 0
            if (n != want) if want != 1 else (n in (0, 15)):
                bad += 1
        return bad

    for f in range(NFRAME):
        for i, (x, y, h) in enumerate(POS):
            sc = (0, 37, 170)[i % 3]
            b = one(patch, f, x, y, h, sc)
            c['frame x position cases %s' % ('ok' if not b else 'FAIL!')] += 1
            if b and c['  fail example'] < 4:
                c['  fail example'] += 1
                c['  f %d x %d y %d h %d sc %d: %d pixels' % (f, x, y, h, sc, b)] += 1
    for fr, (gt, mt, n, first, ga, ma) in FORMS.items():   # the score frames' forms, as the game copies them
        for v in range(n):
            b1 = bytearray(base)
            b1[ga:ga + 16] = base[gt + 16 * v:gt + 16 * v + 16]
            b1[ma:ma + 16] = base[mt + 16 * v:mt + 16 * v + 16]
            for x, y, h in ((100, 60, 0), (17, 100, 3), (160, 180, 0)):
                b = one(patch, fr, x, y, h, 37, b0=bytes(b1))
                c['score frame form cases %s' % ('ok' if not b else 'FAIL!')] += 1
    # guards: frames 0x50 / 0xFF / >= 86 hide; count hides the rest; slot order; Pac-Man's ink
    recs = [(40 + 10 * i, 50, i, 0) for i in range(12)]
    for cnt in range(13):
        ns, _ = _commit(patch, base, recs, cnt)
        vis = [i for i in range(12) if sprite_view(ns.attr[i])]
        c['count guard %s' % ('ok' if vis == list(range(cnt)) else 'FAIL!')] += 1
    for bad_f in (0x50, 0xFF, 86, 0xC0):
        r2 = list(recs)
        r2[3] = (70, 50, bad_f, 0)
        ns, _ = _commit(patch, base, r2, 12)
        c['frame guard %s' % ('ok' if not sprite_view(ns.attr[3]) and sprite_view(ns.attr[4]) else 'FAIL!')] += 1
    ns, _ = _commit(patch, base, recs, 12, 'c1', 0x45)
    ok = sprite_view(ns.attr[0])[3] == 14 and sprite_view(ns.attr[1])[3] == 13
    c['ink: play %s' % ('ok' if ok else 'FAIL!')] += 1
    ns, _ = _commit(patch, base, recs, 12, 'c4', 0x03)
    ok = sprite_view(ns.attr[0])[3] == 3 and sprite_view(ns.attr[1])[3] == 3
    c['ink: theatre %s' % ('ok' if ok else 'FAIL!')] += 1
    # e_hide
    from skoolkit.simulator import Simulator
    from . import z80n
    for ret, hid in ((0x7000, True), (patch.syms['c1'], False)):
        mem = bytearray(base)
        mem[0:0x4000] = _alt_rom(patch)
        sim = Simulator(mem, {})
        ns = NextState()
        ns.attr = [[0, 0, 0, 0xFF, 0] for _ in range(128)]
        z80n.install(sim, ns.nextreg)
        R = sim.registers
        R[24], R[12] = patch.syms['e_hide'], 0x5FF0
        mem[0x5FF0], mem[0x5FF1] = 0x97, 0xB0
        mem[0x5FF2], mem[0x5FF3] = ret & 255, ret >> 8
        R[6], R[7] = 8, 0x10
        n = 0
        while R[24] < 0x4000 and n < 2000:
            sim.opcodes[mem[R[24]]]()
            n += 1
        g = sum(1 for i in range(12) if not sprite_view(ns.attr[i]))
        c['e_hide %s' % ('ok' if g == (12 if hid else 0) and (R[6], R[7]) == (8, 0x10) else 'FAIL!')] += 1
    hc, hx = hook_cases(patch, base)
    c.update(hc)
    for e in hx:
        c['  hook case %s' % (e,)] += 1
    return c


# --------------------------------------------------------------------------------------------- negative controls

def negative_patches(patch):
    """{name: broken copy}. Pattern shift; y one line down; Pac-Man's ink wrong; height ignored; no hide; R one
    off after c1 / after e_hide; c1 not restoring the caller's speed; the plotter's writes left in; the yellow cells
    left in."""
    out = {}
    q = copy.copy(patch)
    p = bytearray(patch.pats)
    o2 = bytearray(len(p))
    for r in range(len(p) // 8):
        row = int.from_bytes(p[8 * r:8 * r + 8], 'big')
        o2[8 * r:8 * r + 8] = (row >> 4).to_bytes(8, 'big')
    q.pats = bytes(o2)
    out['patterns one pixel right'] = q

    def rom(old, new, k=None):
        """old -> new in the hook code: the only occurrence, or with k the k-th (from 0)."""
        o = bytes.fromhex(old)
        at = [i for i in range(len(patch.rom_code)) if patch.rom_code.startswith(o, i)]
        if k is None and len(at) != 1 or k is not None and k >= len(at):
            raise ValueError('negative patch pattern %s: %d occurrences' % (old, len(at)))
        i = at[k or 0]
        z = copy.copy(patch)
        z.rom_code = patch.rom_code[:i] + bytes.fromhex(new) + patch.rom_code[i + len(o):]
        z.make_page()
        return z
    out['sprite y one line down'] = rom('c620ed9236', 'c621ed9236')
    out['Pac-Man ink wrong'] = rom('3ee0', '3ec0')
    out['height above ground ignored'] = rom('9630', '0030')
    out['no hide at a figure-free blit'] = rom('fe40380d', 'fe40180d')
    rexit = 'f53e%02xcd%02x%02xf1' % (128 - 5, patch.syms['hlib_r_set'] & 255, patch.syms['hlib_r_set'] >> 8)
    out['R one off after the commit (c1)'] = rom(rexit, rexit[:4] + '%02x' % (128 - 4) + rexit[6:], 4)
    out['R one off after e_hide'] = rom(rexit, rexit[:4] + '%02x' % (128 - 6) + rexit[6:], 8)
    out['speed not restored (c1 leaves 3.5 MHz)'] = rom('3a735bed9207', '3a745bed9207', 0)
    z = copy.copy(patch)
    z.sites = [s for s in patch.sites if s[0] not in PLOT_NOPS]
    out['plotter writes left in'] = z
    z = copy.copy(patch)
    z.sites = [s for s in patch.sites if s[0] not in ATTR_NOPS]
    out['yellow cells left in'] = z
    return out


def negative_patch(patch):
    return negative_patches(patch)['patterns one pixel right']


# --------------------------------------------------------------------------------------------- colour sheets

def part_of(peek, f, cmap=None):
    px, ent = [], {}
    for r in range(16):
        for b in range(2):
            a, ma = sources(peek, f, r, b)
            key = '%04X' % a
            g, k = peek(a), peek(ma)
            ent[key] = [g, 'g']
            for i in range(8):
                gb, kb = (g >> (7 - i)) & 1, (k >> (7 - i)) & 1
                code, dflt = (1, 1) if gb else (2, 15) if kb else (0, 0)
                px.append((b * 8 + i, r, key, i, code, dflt))
    return {'id': 'F%02X' % f, 'size': 1, 'w': 16, 'h': 16, 'x': 0, 'y': 0, 'mir': 0, 'dx': 0, 'dy': 0, 'dmir': 0, 'vmir': 0,
            'pixels': px, 'entries': ent, 'group': 0}


def sheets(peek, out_dir, prefix='pac_mania', colours=None, say=print):
    from . import coloursheet as cs
    comps = []
    for f in range(NPAT):
        if f == 80 or f in FORMS:                  # 80 is "no figure"; 81 and 85 are shown by their forms, 86 up
            continue
        p = part_of(peek, f)
        if any(q[4] for q in p['pixels']):
            comps.append({'count': 1, 'group': 0, 'parts': [p]})
    rgb = cs.palette_rgb(bytes(PALETTE))
    pre = os.path.join(out_dir, prefix)
    ident = colour_identity(peek)
    cmap = colours if colours is not None else load_colours()
    n = cs.write(comps, pre + '_PAINTING_SPRITES.png', pre + '_PAINTING_SPRITES_layout.json', rgb, colours=cmap,
                 paint_clear=True, identity=ident)
    cs.write(comps, pre + '_REFERENCE_ALL_SPRITES.png', pre + '_REFERENCE_ALL_SPRITES_layout.json', rgb, colours=cmap,
             paint_clear=True, identity=ident)
    say('Sheets    : %d frames (one 16x16 figure each: static graphics, so the sheet covers every frame)' % n)
    return n


# --------------------------------------------------------------------------------------------- auto

ENHANCED = os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '_enhanced.json')
# Enhanced palette slots 2-15: FIXED with 3 red, 6 cyan, 7 blue and 14 orange for the ghosts (owner's look, 2026-11-03)
ENHANCED_FIXED = (0xE8, 0xE0, 0xF6, 0xF1, 0x1F, 0x27, 0xB7, 0xFC, 0x54, 0xBE, 0xF8, 0xFF, 0xF0, 0x00)
SOURCE_MD5 = 'e9cb908bc86661ff81732665741393cc'     # Pac-Mania (1988)(Grandslam)(128K).z80


def enhanced_patch():
    """The Enhanced colour set: the painted map (docs/profiles/pac_mania_enhanced.json) and its palette."""
    from . import coloursheet as cs
    return PacPatch(colours=cs.load(ENHANCED), fixed=ENHANCED_FIXED)


def boot_check(nex, z80, patch):
    """The start-up tail, with and without NEXLOAD's printer buffer: every register (R too) and all RAM
    0x4000-0xFFFF as the patched snapshot has them at 0x7530, but the tail's own bytes (TAIL_FREE, never read).
    -> [(nexload, bad count, examples)]."""
    from . import nextboot, hooklib
    from . import z80tonex as zt
    s = zt.Z80Snapshot(str(z80))
    patch = copy.deepcopy(patch)
    patch.apply(s)
    tail = zt.build_tail(s, TAIL_ADDR, patch.slot1, True)[0]
    t0, t1 = TAIL_ADDR, TAIL_ADDR + len(tail)
    exp = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
           8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r,
           16: s.a_, 17: s.f_, 18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8,
           23: s.hl_ & 255, 26: s.iff1, 27: s.im}
    out = []
    for nl in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nl)
        bad = [('reg', i, v, st['R'][i]) for i, v in exp.items() if st['R'][i] != v]
        for ad in range(0x4000, 65536):
            if t0 <= ad < t1 or nl and 0x5B00 <= ad < 0x5C00:
                continue
            bank = 5 if ad < 0x8000 else 2 if ad < 0xC000 else 0
            if st['mem'][ad] != s.banks[bank][ad & 16383]:
                bad.append(('RAM', hex(ad), s.banks[bank][ad & 16383], st['mem'][ad]))
        out.append((nl, len(bad), bad[:5]))
    return out, (t0, t1)


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : pacmania (one plotter AE73, static frames; commit at the end of the blit; 128K release, AY)')
    if md5(z80) != SOURCE_MD5:
        say('Snapshot  : MD5 %s, not the 128K release %s: refused' % (md5(z80), SOURCE_MD5))
        say('Result    : FAILED')
        return False
    plain = os.path.join(out, name + '.nex')

    class Start:                                 # the plain conversion starts the game the same way
        sites, extra_banks, stub_extra, setup_call, hook_page_data = [], {}, b'', None, b''
        uses_printer_buffer, tail_addr, name = True, TAIL_ADDR, 'start at 0x7530'

        def apply(self, snap):
            start_state(snap)
    zt.convert(z80, plain, TAIL_ADDR, True, quiet=True, patch=Start())
    say('Plain     : %s  %s  (starts at 0x%04X, as the sprite build)' % (os.path.basename(plain), md5(plain), START_PC))
    ok = True
    outs = [('Sprites', name + '_sprites.nex', PacPatch()), ('Enhanced', name + '_enhanced.nex', enhanced_patch())]
    for label, fn, pt in outs:
        path = os.path.join(out, fn)
        zt.convert(z80, path, None, True, quiet=True, patch=pt)
        boot, (t0, t1) = boot_check(path, z80, pt)
        bok = all(n == 0 for _, n, _ in boot) and TAIL_FREE[0] <= t0 and t1 <= TAIL_FREE[1]
        ok = ok and bok
        say('%-10s: %s  %s  boot (registers with R, RAM; tail 0x%04X-0x%04X; plain and after NEXLOAD) %s' % (
            label, fn, md5(path), t0, t1 - 1, 'OK' if bok else 'FAIL %s' % str(boot)[:300]))
    patch = PacPatch()
    zt.convert(z80, os.path.join(out, name + '_sprites.nex'), None, True, quiet=True, patch=patch)
    for r in list(a.rzx or []):
        c, ex = verify(patch, r, stop=getattr(a, 'quick', None))
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d passes, blits play %d theatre %d, idle frames %d, %d sprite pixels -> %s' % (
            os.path.basename(r), c['frames'], c['plot passes'], c['blits play'], c['blits theatre'], c['idle frames compared'],
            c['sprite pixels compared'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            hooks: ' + ' '.join('%s %d' % (k[5:], v) for k, v in c.items() if k.startswith('hook ') and k != 'hook low SP'))
        say('            hook low SP 0x%04X; distinct frames %d; census %s' % (c['hook low SP'], c['distinct frames as sprites'],
            {k[8:]: v for k, v in c.items() if k.startswith('census')}))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
    s = zt.Z80Snapshot(z80)
    base = bytes(65536 - 49152) + s.banks[5] + s.banks[2] + s.banks[0]
    u = unit_tests(patch, base)
    uf = {k: v for k, v in u.items() if k.endswith('!')}
    ok = ok and not uf
    say('Unit      : %s -> %s' % ({k: v for k, v in u.items() if not k.startswith('  ')}, 'PASS' if not uf else 'FAIL'))
    for k, v in u.items():
        if k.startswith('  '):
            say('          %s' % k)
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
