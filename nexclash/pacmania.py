"""Pac-Mania (Grandslam / Teque, 1988, 48K form) engine 'pacmania'. Additive module: reachable only through
is_pacmania(). Facts and design: games/pac_mania.md.

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
TAIL_ADDR = 0x5B00
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
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_pacmania(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
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


class PacPatch:
    name = 'Pac-Mania figures -> hardware sprites (altrom, stateless commit at the end of the blit)'

    def __init__(self, prof=None, colours=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
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
        if snap.is128:
            raise ValueError('Pac-Mania patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if any(ram[TAIL_ADDR - 0x4000:TAIL_ADDR - 0x4000 + 256]):
            raise ValueError('printer buffer is not empty in this snapshot (tail site)')
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
    def __init__(self):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.other = collections.Counter()

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg != 0x34:
            self.other[reg] += 1


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
    """One replay machine; frames by RZX fetch count. Fetches in hook ROM are not counted, so the
    original and the patched game take each interrupt at the same game instruction."""

    def __init__(self, snap, patch=None):
        from skoolkit.simutils import from_snapshot
        from skoolkit.simulator import Simulator
        from . import z80n
        self.sim = from_snapshot(Simulator, snap, config={'int_active': 0})
        self.mem, self.R, self.ops = self.sim.memory, self.sim.registers, self.sim.opcodes
        self.ns = NextState()
        self.patch = patch
        self.events = []
        self.hook = collections.Counter()
        self.sp_low = 65536
        self.hook_regs = None
        self.hook_bad = 0
        self.r_hold = None
        if patch:
            self.mem[0:0x4000] = _alt_rom(patch)
            for a, old, new in patch.sites:
                for k, v in enumerate(new):
                    self.mem[a + k] = v
        z80n.install(self.sim, self.ns.nextreg, strict=False)
        run = self

        class Tr:
            def read_port(s, regs, port):
                run.pi += 1
                return run.data[run.pi - 1]

            def write_port(s, regs, port, value, *x):
                pass
        self.sim.set_tracer(Tr())
        self.data, self.pi = b'', 0

    def frame(self, count, start, end, data, ev):
        R, mem, ops = self.R, self.mem, self.ops
        self.data, self.pi = data, start
        pc = R[24]
        while count > 0:
            pc = R[24]
            if pc in ev:
                self.on_event(pc)
            op = mem[pc]
            if pc < 0x4000:
                self.in_hook(pc)
                ops[op]()
                if R[24] >= 0x4000:
                    R[15], self.r_hold = self.r_hold, None
                    self.hook_regs = None
                continue
            if op == 0xDD or op == 0xFD:
                r0 = R[15]
                ops[op]()
                count -= 2 - ((R[15] ^ r0) % 2)
            else:
                ops[op]()
                count -= 2 if op == 0xCB or op == 0xED else 1
        while R[24] < 0x4000:                    # a hook entered by the frame's last instruction runs on
            self.in_hook(R[24])
            ops[mem[R[24]]]()
            if R[24] >= 0x4000:
                R[15], self.r_hold = self.r_hold, None
        self.hook_regs = None
        if self.pi != end:
            raise RuntimeError('port readings out of step: %d of %d' % (self.pi, end))
        return pc

    def in_hook(self, pc):
        R = self.R
        self.hook[pc] += 1
        if self.r_hold is None:
            self.r_hold = R[15]                  # the game's RNG reads R: hook fetches do not count here
        now = (R[8], R[9], R[10], R[11], R[14], R[26])     # IX IY-ish, I, IFF: nothing a hook may write
        if self.hook_regs is None:
            self.hook_regs = now
        elif now != self.hook_regs:
            self.hook_bad += 1
        if R[12] < self.sp_low:
            self.sp_low = R[12]

    def on_event(self, pc):
        self.events.append((pc, self.snap_event(pc)))

    def snap_event(self, pc):
        m = self.mem
        if pc == 0xA8FA:
            return (bytes(m[BUF[0]:BUF[1]]),)
        return (bytes(m[0x4000:0x5B00]), bytes(m[BUF[0]:BUF[1]]), [list(a) for a in self.ns.attr[:SLOTS]],
                m[ROOM], [(m[RECS + 4 * i], m[RECS + 4 * i + 1], m[RECS + 4 * i + 2], m[RECS + 4 * i + 3]) for i in range(12)],
                [m[ORDER + 2 * i] | m[ORDER + 2 * i + 1] << 8 for i in range(12)], m[COUNT])

    def accept(self, pc):
        R, mem = self.R, self.mem
        R[25] = 0
        if R[26]:
            if mem[pc] == 0x76:
                R[24] = (R[24] + 1) % 65536
            self.sim.accept_interrupt(R, mem, 0)


def _segments(patch):
    """[0x5B00, 0x10000) minus the buffer and the patch sites, as (lo, hi) slices."""
    cuts = sorted((a, a + len(new)) for a, old, new in patch.sites) + [(BUF[0], BUF[1])]
    cuts.sort()
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
            # memory
            mo, mp = o.mem, p.mem
            for lo, hi in segs:
                if mo[lo:hi] != mp[lo:hi]:
                    dd = [a for a in range(lo, hi) if mo[a] != mp[a]]
                    sp = o.R[12]
                    real = []
                    for a in dd:
                        if sp - 40 <= a < sp:
                            continue                 # dead stack: hooks push below SP
                        w = mp[a] | mp[a + 1] << 8 if a & 1 == (sp & 1) else mp[a - 1] | mp[a] << 8
                        if sp <= a < sp + 24 and w < 0x4000:
                            continue                 # the blit's return address is c_n (see e_b1)
                        real.append(a)
                    if real:
                        fail('memory differs', [hex(a) for a in real[:6]], len(real))
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
    for name in ('e_b1', 'e_b2', 'e_b3', 'e_b4', 'e_hide', 'c1', 'c2', 'c3', 'c4'):
        c['hook ' + name] = p.hook[patch.syms[name]]
    c['hook low SP'] = p.sp_low
    if p.hook_bad:
        c['a hook changed IX, IY, I or IFF!'] = p.hook_bad
    c['other nextregs in hooks'] = sum(p.ns.other.values())
    if p.ns.other:
        c['hook wrote a NEXTREG other than sprite attributes!'] = sum(p.ns.other.values())
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
    return c


# --------------------------------------------------------------------------------------------- negative controls

def negative_patches(patch):
    """{name: broken copy}. Pattern shift; y one line down; Pac-Man's ink wrong; height ignored; no hide;
    the plotter's writes left in; the yellow cells left in."""
    out = {}
    q = copy.copy(patch)
    p = bytearray(patch.pats)
    o2 = bytearray(len(p))
    for r in range(len(p) // 8):
        row = int.from_bytes(p[8 * r:8 * r + 8], 'big')
        o2[8 * r:8 * r + 8] = (row >> 4).to_bytes(8, 'big')
    q.pats = bytes(o2)
    out['patterns one pixel right'] = q

    def rom(old, new):
        i = patch.rom_code.find(bytes.fromhex(old))
        if i < 0 or patch.rom_code.count(bytes.fromhex(old)) != 1:
            raise ValueError('negative patch pattern %s not unique' % old)
        z = copy.copy(patch)
        z.rom_code = patch.rom_code[:i] + bytes.fromhex(new) + patch.rom_code[i + len(old) // 2:]
        z.make_page()
        return z
    out['sprite y one line down'] = rom('c620ed9236', 'c621ed9236')
    out['Pac-Man ink wrong'] = rom('3ee0', '3ec0')
    out['height above ground ignored'] = rom('9630', '0030')
    out['no hide at a figure-free blit'] = rom('fe40380d', 'fe40180d')
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

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    from skoolkit.snapshot import get_snapshot
    say('Game      : %s' % name)
    say('Engine    : pacmania (one plotter AE73, static frames; commit at the end of the blit)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200]))
    patch = PacPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
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
    base = bytes(get_snapshot(z80))
    u = unit_tests(patch, base)
    uf = {k: v for k, v in u.items() if k.endswith('!')}
    ok = ok and not uf
    say('Unit      : %s -> %s' % ({k: v for k, v in u.items() if not k.startswith('  ')}, 'PASS' if not uf else 'FAIL'))
    for k, v in u.items():
        if k.startswith('  '):
            say('          %s' % k)
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
