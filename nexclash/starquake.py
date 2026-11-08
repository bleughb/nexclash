"""Starquake (Bubble Bus Software, 1985, 48K) engine 'starquake'. Additive module: reachable only
through is_starquake().

Game facts (games/starquake.md): 0xD9C8 runs once per game frame: CALL 0xDF70 XOR-plots six objects
(record 0xDD18 + 32i: +0/1 line table pointer, +2/3 shifted image, +4 x byte drawn; +5 x, +6 y,
+7/8 image base, +9 colour), each erased and redrawn; CALL 0xD8B1 then paints each object's ink
into the cells under it (cells with paper bit 5 clear), and 0xD964 puts back the room's own
coloured cells (list at 0x5B20). Images: 4 pre-shifted copies of 48 bytes (24 x 16), base + (x&6)*24.
BLOB 0xE074 + 192n (13), the rest 0xA548 + 192n (36 slots; 0xAFC8.. 0xBF88 seen).
Collision reads attributes (bright = open, 0xD338..) but only the bright bit, never the ink.
Hooks (asm/starquake_hooks.asm, alt ROM image 1, stateless): the plotter keeps every ULA write; each
figure becomes a solid sprite (ink, black fill, outline) over its silhouette; the nine attribute
stores of the painter become NOPs. Original and patched run the same game instructions in the same
order, so the verifier runs both in lockstep over the recording, hook fetches not counted.
"""
import collections
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5D20          # BASIC area, never touched in play (scan); printer buffer holds the game's list
REC = 0xDD18
EN0, EN_N = 0xA548, 144      # 48-byte shifted images (each its own animation frame)
PL0, PL_N = 0xE074, 52
LTAB = 0xDDDE
NIMG = EN_N + PL_N
BLANK = 0xDF40
STP = 26                    # first pattern store page (bank 13)
STORE_BANKS = (13, 14, 15, 16, 17, 18, 19)
SITES_CALL = {0xD9CE: ('cdb1d8', 'e_pl', 0xCD), 0x6194: ('cdd05f', 'e_cls', 0xCD),
              0x6618: ('cdd05f', 'e_cls', 0xCD), 0x672A: ('cdd05f', 'e_cls', 0xCD),
              0xA45F: ('cd47a6', 'e_rc', 0xCD), 0xA412: ('c347a6', 'e_rc', 0xC3),
              0xD964: ('21205b', 'e_un', 0xC3), 0xE06D: ('c272df', 'e_ob', 0xC3)}
# the plot's 24 screen stores (erase and draw, after XOR (HL)): the ULA keeps no figure pixels.
# No game code reads the bitmap but the plot itself (scan --writers); A is reloaded after each loop.
NOPS = (0xDF97, 0xDF9C, 0xDFA1, 0xDFA9, 0xDFAE, 0xDFB3, 0xDFBB, 0xDFC0, 0xDFC5, 0xDFCD, 0xDFD2, 0xDFD7,
        0xE01F, 0xE024, 0xE029, 0xE031, 0xE036, 0xE03B, 0xE043, 0xE048, 0xE04D, 0xE055, 0xE05A, 0xE05F)
SAVEPG = 38
INTERIORS = tuple(a + k for a in SITES_CALL for k in (1, 2))
CMP = [i for i in range(24) if i not in (15,)]   # all but R (T, MEMPTR are not in the register list)
CANVAS, ORGX, ORGY = 32, 4, 8

_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'starquake_colours.json')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', 'starquake.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_starquake(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def load_colours(path=None):
    p = path or COLOURS
    if os.path.exists(p):
        return json.load(open(p))
    return {}


# ---------------------------------------------------------------------------------------------
# Images -> 32 x 32 canvases: 1 ink, 2 black fill (holes, mouths), 3 outline; colour map on top
# ---------------------------------------------------------------------------------------------

def image_index(base):
    if EN0 <= base < EN0 + 48 * EN_N and (base - EN0) % 48 == 0:
        return (base - EN0) // 48
    if PL0 <= base < PL0 + 48 * PL_N and (base - PL0) % 48 == 0:
        return EN_N + (base - PL0) // 48
    return None


def image_base(n):
    return EN0 + 48 * n if n < EN_N else PL0 + 48 * (n - EN_N)


def canvas(get, n, cmap=None):
    """-> 32x32 list of codes for image n (graphic at (8,8))."""
    b = image_base(n)
    W = CANVAS
    ink = [[0] * W for _ in range(W)]
    for r in range(16):
        v = get(b + 3 * r) << 16 | get(b + 3 * r + 1) << 8 | get(b + 3 * r + 2)
        for c in range(24):
            if v >> (23 - c) & 1:
                ink[ORGY + r][ORGX + c] = 1
    def dil(m):
        o = [[0] * W for _ in range(W)]
        for y in range(W):
            for x in range(W):
                if m[y][x]:
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if 0 <= y + dy < W and 0 <= x + dx < W:
                                o[y + dy][x + dx] = 1
        return o
    def ero(m):
        o = [[0] * W for _ in range(W)]
        for y in range(1, W - 1):
            for x in range(1, W - 1):
                o[y][x] = int(all(m[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)))
        return o
    clo = ero(dil(ink))
    sil = [[ink[y][x] | clo[y][x] for x in range(W)] for y in range(W)]
    # holes: not reachable from the border through non-silhouette pixels (4-connected)
    out = [[0] * W for _ in range(W)]
    st = [(0, 0)]
    out[0][0] = 1
    while st:
        y, x = st.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < W and 0 <= xx < W and not out[yy][xx] and not sil[yy][xx]:
                out[yy][xx] = 1
                st.append((yy, xx))
    solid = [[1 - out[y][x] for x in range(W)] for y in range(W)]
    ring = dil(solid)
    cv = [[0] * W for _ in range(W)]
    if not any(any(r) for r in ink):
        return cv
    for y in range(W):
        for x in range(W):
            if ink[y][x]:
                cv[y][x] = 1
            elif solid[y][x]:
                cv[y][x] = 2
            elif ring[y][x] and not (cmap and cmap.get('drop_outline')):
                cv[y][x] = 3
    # transparent pixels the outline ring encloses (a narrow gap between two parts): outline too, so
    # no background shows inside a figure
    seen = [[0] * W for _ in range(W)]
    st = [(0, 0)]
    seen[0][0] = 1
    while st:
        y, x = st.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < W and 0 <= xx < W and not seen[yy][xx] and cv[yy][xx] == 0:
                seen[yy][xx] = 1
                st.append((yy, xx))
    for y in range(W):
        for x in range(W):
            if cv[y][x] == 0 and not seen[y][x]:
                cv[y][x] = 2 if (cmap and cmap.get('drop_outline')) else 3
    if cmap:
        for k, v in cmap.get('pixels', {}).items():
            nn, xy = k.split(':')
            if int(nn) == n:
                x, y = map(int, xy.split(','))
                if cv[y + ORGY][x + ORGX] in (1, 2):
                    cv[y + ORGY][x + ORGX] = int(v)
    return cv


def tiles(cv):
    """canvas -> 512 bytes: tiles TL, TR, BL, BR, 128 bytes each (4-bit, high nibble first)."""
    out = bytearray()
    for ty in (0, 16):
        for tx in (0, 16):
            for y in range(16):
                for x in range(0, 16, 2):
                    out.append(cv[ty + y][tx + x] << 4 | cv[ty + y][tx + x + 1])
    return bytes(out)


def store(get, cmap=None):
    """the pattern store, 16 images per 8K page, from page STP."""
    s = bytearray(16384 * len(STORE_BANKS))
    for n in range(NIMG):
        s[n * 512:(n + 1) * 512] = tiles(canvas(get, n, cmap))
    return bytes(s)


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

class StarquakePatch:
    name = 'Starquake: six figures -> hardware sprites (altrom, stateless hooks; attribute paint removed)'

    def __init__(self, prof=None, rom_code=None, colours=None, nops=NOPS, sites=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 160
        self.colours = load_colours() if colours is None else colours
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        # The WHOLE alt ROM image comes from the build: Sinclair's 48K ROM + hooks. The Next fills the
        # image from NextZXOS's ROM3 first, which has code of its own at 0x386E-0x3BF4: its IM 1
        # handler CALLs 0x386E (0x004A, KEY-INT moved there) and its UDG print JPs to 0x387E (0x0B52).
        # With only 0x386E.. written, every interrupt ran e_pl and the define-keys screen's first
        # arrow UDG jumped into the middle of e_pl: sprites over the menu, then a crash (owner's play
        # in JNext, 2026-11-04). The verifier ran Sinclair's ROM, so it never saw ROM3's code; _machine now
        # builds the patched image the way the stub does, from ROM3 (negative _rom3_left).
        self.altrom = (0x2000, 0x4000)
        self.hook_range = (ROM_ORG, self.syms['rom_end'])
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.altrom_low = (ALT_PAGE + 1, bytes(rom[0:0x2000]))
        self.sites = []
        for a, (old, sym, op) in (sites or SITES_CALL).items():
            self.sites.append((a, bytes.fromhex(old), bytes([op]) + self.syms[sym].to_bytes(2, 'little')))
        for a in nops:
            self.sites.append((a, b'\x77', b'\x00'))
        self.extra_banks = {}
        self.store = None

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Starquake patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        self.store = store(lambda a: ram[a - 0x4000], self.colours)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {12: self.page + self.altrom_low[1]}
        for i, b in enumerate(STORE_BANKS):
            self.extra_banks[b] = self.store[i * 16384:(i + 1) * 16384]


# ---------------------------------------------------------------------------------------------
# Next-side model
# ---------------------------------------------------------------------------------------------

class NS:
    def __init__(self, store_bytes):
        self.nr = {0x07: 0, 0x57: 1}
        self.sel = 0
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pp = 0
        self.store = bytearray(store_bytes)
        self.mem = None
        self.game7 = None

    def _page(self, val):
        # slot 7 of the flat 48K memory: page 1 = the game's, STP.. = the pattern store
        m = self.mem
        cur = self.nr.get(0x57)
        if cur == 1:
            self.game7 = bytes(m[0xE000:0x10000])
        else:
            k = cur - STP
            self.store[k * 8192:(k + 1) * 8192] = bytes(m[0xE000:0x10000])
        if val == 1:
            m[0xE000:0x10000] = self.game7
        else:
            k = val - STP
            if not 0 <= k < 2 * len(STORE_BANKS):
                raise ValueError('MMU7 page %d' % val)
            m[0xE000:0x10000] = self.store[k * 8192:(k + 1) * 8192]

    def nextreg(self, reg, val):
        if reg == 0x57 and val != self.nr.get(0x57) and self.mem is not None:
            self._page(val)
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def out(self, port, val):
        if port == 0x243B:
            self.sel = val
        elif port == 0x253B:
            self.nextreg(self.sel, val)
        elif port == 0x303B:
            self.pp = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pp & 0x3FFF] = val
            self.pp += 1
        else:
            return False
        return True

    def inp(self, port):
        if port == 0x253B:
            return self.nr.get(self.sel, 0)
        return None

    def layer(self):
        out = {}
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            x0 = a0 + (a2 & 1) * 256 - 32
            y0 = a1 + (a4 & 1) * 256 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            pal = a2 & 0xF0
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + k // 2]
                    c = (b >> 4) if k % 2 == 0 else (b & 15)
                    if c and 0 <= x0 + k < 256 and 0 <= y0 + j < 192:
                        out[(x0 + k, y0 + j)] = pal | c
        return out


def obj(get, i):
    r = REC + 32 * i
    return dict(x=get(r + 5), y=get(r + 6), base=get(r + 7) | get(r + 8) << 8, col=get(r + 9),
                lt=get(r) | get(r + 1) << 8, gfx=get(r + 2) | get(r + 3) << 8, xb=get(r + 4))


def plotted(get, o):
    """the pixels the XOR plot drew for this object (from what it stored at +0..+4)."""
    out = set()
    for r in range(16):
        a = get(o['lt'] + 2 * r) | get(o['lt'] + 2 * r + 1) << 8
        if not 0x4000 <= a < 0x5800:
            continue
        a -= 0x4000
        y = (a >> 5 & 0xC0) | (a >> 8 & 7) | (a >> 2 & 0x38)
        xb = (a & 31) + o['xb']
        v = get(o['gfx'] + 3 * r) << 16 | get(o['gfx'] + 3 * r + 1) << 8 | get(o['gfx'] + 3 * r + 2)
        for b in range(24):
            if v >> (23 - b) & 1 and xb * 8 + b < 256 + 16:
                out.add((xb * 8 + b, y))
    return out


def expected(get, cmap, cache):
    """-> (layer dict, [(i, model ink set, plotted set)])"""
    lay, inks = {}, []
    for i in range(5, -1, -1):
        o = obj(get, i)
        n = image_index(o['gfx'])
        p = plotted(get, o) if o['gfx'] != BLANK else set()
        if n is None:
            inks.append((i, None, p))
            continue
        if n not in cache:
            cache[n] = canvas(get, n, cmap)
        if p:
            SEEN.add(n)
        cv = cache[n]
        X0, Y0 = o['xb'] * 8 - ORGX, 16 + (o['lt'] - LTAB) // 2 - ORGY
        pal = (o['col'] & 7) << 4
        ink = set()
        for y in range(CANVAS):
            for x in range(CANVAS):
                c = cv[y][x]
                if c:
                    X, Y = (X0 + x) % 512, (Y0 + y) % 512
                    X = X - 512 if X >= 480 else X
                    Y = Y - 512 if Y >= 480 else Y
                    if 0 <= X < 256 and 0 <= Y < 192:
                        lay[(X, Y)] = pal | c
                    if c == 1:
                        ink.add((X0 + x, Y0 + y))
        inks.append((i, ink, p))
    return lay, inks


# ---------------------------------------------------------------------------------------------
# Lockstep verification over the recording
# ---------------------------------------------------------------------------------------------

def _frames(rzx_path):
    from skoolkit.rzxplay import parse_rzx, InputRecording
    from skoolkit.snapshot import Snapshot
    out, snap = [], None
    for block in parse_rzx(rzx_path):
        o = block.obj
        if isinstance(o, InputRecording):
            out.append((o.snapshot if getattr(o, 'snapshot', None) else snap,
                        [(f.fetch_counter, list(o.data[f.start:f.end])) for f in o.frames]))
        else:
            snap = o
    return out


class _Ports:
    def __init__(self, ns=None):
        self.ns, self.ins, self.i, self.bad = ns, [], 0, 0

    def read_port(self, registers, port):
        if self.ns is not None:
            v = self.ns.inp(port)
            if v is not None:
                return v
        if self.i < len(self.ins):
            self.i += 1
            return self.ins[self.i - 1]
        self.bad += 1
        return 255

    def write_port(self, registers, port, value, offset=0):
        if self.ns is not None:
            self.ns.out(port, value)




def _machine(snap, patch=None, ns=None):
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    from .build import rom48
    sim = from_snapshot(Simulator, snap, config={'int_active': 0})
    mem = sim.memory
    r = rom48()
    for a in range(0x4000):
        mem[a] = r[a]
    if patch is not None:
        from . import z80n
        # the alt ROM image as the Next's stub fills it (z80tonex.altrom_fill): the SYSTEM ROM3 copied first
        # (NextZXOS's, not Sinclair's: code at 0x386E-0x3BF4 that its IM 1 handler and UDG print call), then
        # lo..hi of the patch page, then altrom_low over 0x0000-0x1FFF. Missing NextZXOS ROM: Sinclair's.
        from .nextboot import system_rom3            # $NEXCLASH_NEXT_ROM / --next-rom; else Sinclair's ROM
        r3 = system_rom3()[0]
        for a in range(0x4000):
            mem[a] = r3[a]
        lo, hi = patch.altrom
        for a in range(lo, hi):
            mem[a] = patch.page[a - 0x2000]
        low = getattr(patch, 'altrom_low', None)
        if low:
            for a in range(0x2000):
                mem[a] = low[1][a]
        for a, old, new in patch.sites:
            for k, v in enumerate(new):
                mem[a + k] = v
        z80n.install(sim, ns.nextreg, strict=False)
    return sim


HOOKT = [0]
SEEN = set()


def _run(sim, fc, skip=None, watch=None, cb=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    lo, hi = skip or (0, 0)
    pc = R[24]
    while fc > 0:
        pc = R[24]
        if watch and pc in watch:
            cb(pc)
        op = mem[pc]
        if lo <= pc < hi:
            t0 = R[25]
            ops[op]()
            HOOKT[0] += R[25] - t0
            continue
        if op in (0xDD, 0xFD):
            r0 = R[15]
            ops[op]()
            fc -= 2 - ((R[15] ^ r0) % 2)
        else:
            ops[op]()
            fc -= 2 if op in (0xCB, 0xED) else 1
    # a hook entered on the last counted fetch runs to its exit before the interrupt
    return pc


def _accept(sim):
    R, mem = sim.registers, sim.memory
    pc = R[24]
    R[25] = 0
    if R[26]:
        if mem[pc] == 0x76:
            R[24] = (R[24] + 1) % 65536
        sim.accept_interrupt(R, mem, 0)


def xor_out(mem, on=(1,) * 6):
    """the bitmap with every object's image, as the plot XORed it at +0..+4, taken out again"""
    b = bytearray(mem[0x4000:0x5800])
    for i in range(6):
        if not on[i]:
            continue
        r = REC + 32 * i
        lt, g, xb = mem[r] | mem[r + 1] << 8, mem[r + 2] | mem[r + 3] << 8, mem[r + 4]
        for k in range(16):
            a = mem[lt + 2 * k] | mem[lt + 2 * k + 1] << 8
            if not 0x4000 <= a < 0x5800:
                continue
            h, l = a & 0xFF00, (a + xb) & 0xFF
            for j in range(3):
                b[h + ((l + j) & 0xFF) - 0x4000] ^= mem[g + 3 * k + j]
    return bytes(b)


def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=1, model_colours=None, speed=0):
    """-> (Counter, examples). Failure keys end in '!'."""
    from skoolkit.snapshot import Snapshot
    import copy
    C = collections.Counter()
    ex = collections.defaultdict(list)

    def fail(k, *info):
        C[k] += 1
        if len(ex[k]) < 5:
            ex[k].append(info)
    segs = _frames(rzx_path)
    snap0 = segs[0][0]
    p2 = copy.deepcopy(patch)
    s2 = copy.deepcopy(snap0)
    # the snapshot as patched (banks), for the store
    ram = bytes(snap0.memory[0x4000:0x10000])
    p2.store = store(lambda a: ram[a - 0x4000], p2.colours)
    ns = NS(p2.store)
    ns.nr[0x07] = speed                    # the caller's speed: every hook gives it back
    A = _machine(snap0)
    B = _machine(s2, p2, ns)
    ns.mem = B.memory
    # Z: the original game with each frame's figure paint undone by the verifier (attributes saved at
    # 0xD8B1, put back at 0xD964): the reference for the patched attributes, compared in full
    Z = _machine(copy.deepcopy(snap0))
    pz = _Ports()
    Z.set_tracer(pz)
    zst = {}

    zst['on'] = [0] * 6

    def zcb(pc):
        if pc == 0xE070:                    # the plot's RET: all six drawn where +0..+4 say
            zst['on'] = [1] * 6
        elif pc in (0xA647, 0x5FD0):           # a clear runs over several frames
            zst['clearing'] = 1
        elif pc in (0xA65D, 0x5FE0):           # its bitmap part done: no figure left on the screen
            zst['on'] = [0] * 6
            zst['clearing'] = 0
        elif pc == 0xD8B1:
            zst['a'] = bytes(Z.memory[0x5800:0x5B00])
        elif pc == 0xD964 and 'a' in zst:
            Z.memory[0x5800:0x5B00] = zst.pop('a')
    pa, pb = _Ports(), _Ports(ns)
    A.set_tracer(pa)
    B.set_tracer(pb)
    lo, hi = p2.hook_range
    cache = {}
    HOOKT[0] = 0
    cmap = load_colours() if model_colours is None else model_colours
    e_pl, e_cls, e_rc = p2.syms['e_pl'], p2.syms['e_cls'], p2.syms['e_rc']
    state = {'in': None}

    def cb(pc):
        R, mem = B.registers, B.memory
        if pc == p2.syms['e_un']:
            C['hook e_un'] += 1
            state['un'] = list(R)
            return
        if pc == 0xD967 and 'pre' in state:
            u = state.pop('un', None)
            if u is not None:
                for k in (0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27):
                    if R[k] != u[k]:
                        fail('e_un changed a register!', k, R[k], u[k])
                if R[6] * 256 + R[7] != 0x5B20:
                    fail('e_un HL!', R[6], R[7])
            if bytes(mem[0x5800:0x5B00]) != state.pop('pre'):
                fail('attributes not put back after the paint!', C['hook e_pl'])
            else:
                C['attribute restores checked'] += 1
            return
        if pc in (e_pl, e_cls, e_rc):
            state['in'] = pc
            if pc == e_pl:
                state['pre'] = bytes(mem[0x5800:0x5B00])
                if ns.nr.get(0x07, 0) & 3 != 3:       # the plot's stretch: at 28 MHz from e_ob down to here
                    fail('the plot stretch not at 28 MHz!', C['hook e_pl'])
            C['hook ' + {e_pl: 'e_pl', e_cls: 'e_cls', e_rc: 'e_rc'}[pc]] += 1
            state['sp'] = R[12]
            state['regs'] = list(R)
            return
        if state['in'] is None:
            return
        if pc in (0xD8B1, 0x5FD0, 0xA647):
            h = state['in']
            state['in'] = None
            for k in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27):
                if R[k] != state['regs'][k]:
                    fail('hook changed a register!', hex(pc), k, R[k], state['regs'][k])
            if ns.nr.get(0x57) != 1:
                fail('MMU7 not restored!', ns.nr.get(0x57))
            if ns.nr.get(0x07, 0) & 3 != speed:
                fail('speed not restored!', ns.nr.get(0x07))
            get = mem.__getitem__
            if h == e_pl:
                if C['hook e_pl'] % every:
                    return
                lay, inks = expected(get, cmap, cache)
                for i, ink, p in inks:
                    if ink is None:
                        if p:
                            fail('figure image not in the store!', i, hex(obj(get, i)['gfx']))
                        continue
                    C['figures checked'] += 1 if p else 0
                    if p and {q for q in ink if 0 <= q[0] < 256 and q[1] < 192} != {q for q in p if q[0] < 256}:
                        a_, b_ = {q for q in ink if 0 <= q[0] < 256 and q[1] < 192}, {q for q in p if q[0] < 256}
                        fail('model ink differs from the plot!', i, len(ink), len(p), sorted(a_ - b_)[:4], sorted(b_ - a_)[:4], obj(get, i))
                got = ns.layer()
                C['sprite pixels compared'] += len(lay)
                if got != lay:
                    d = [k for k in set(got) | set(lay) if got.get(k) != lay.get(k)]
                    fail('sprite layer differs from the model!', len(d), d[:4])
            else:
                vis = [s for s in range(24) if ns.attr[s][3] & 0x80]
                C['hides checked'] += 1
                if vis:
                    fail('sprites left visible after a screen clear!', vis)

    watch = {e_pl, e_cls, e_rc, 0xD8B1, 0x5FD0, 0xA647, p2.syms['e_un'], 0xD967}
    sitebytes = {a + k for a, old, new in p2.sites for k in range(len(new))}
    nf = 0
    attr_diff = 0
    for snap, frames in segs:
        for fc, ins in frames:
            if stop and nf >= stop:
                break
            pa.ins, pa.i = ins, 0
            pb.ins, pb.i = ins, 0
            pz.ins, pz.i = ins, 0
            _run(A, fc)
            _run(Z, fc, None, {0xD8B1, 0xD964, 0xE070, 0xA647, 0x5FD0, 0xA65D, 0x5FE0}, zcb)
            _run(B, fc, (lo, hi), watch, cb)
            # finish a hook the last fetch entered (never happens at these sites, counted)
            if lo <= B.registers[24] < hi:
                fail('frame ended inside a hook!', nf)
            sp = A.registers[12]
            zpc = Z.registers[24]
            _accept(A)
            _accept(Z)
            _accept(B)
            nf += 1
            if 0xDF70 <= zpc <= 0xE070 or zst.get('clearing'):   # inside the plot or a clear: next frame
                C['frames ending inside the plot or a clear (bitmap not compared)'] += 1
                za = bytes(Z.memory[0x5800:0x10000])
                zb = bytes(B.memory[0x5800:0x10000])
                off = 0x5800
            else:
                za = xor_out(Z.memory, zst['on']) + bytes(Z.memory[0x5800:0x10000])
                zb = bytes(B.memory[0x4000:0x10000])
                off = 0x4000
            if za != zb:
                d = [i + off for i in range(len(za)) if za[i] != zb[i]]
                d = [a for a in d if not (sp - 64 <= a < sp) and a not in sitebytes]
                if d:
                    fail('differs from the original with its paint undone!', nf, ['%04X' % a for a in d[:6]], len(d))
                    if os.environ.get('SQ_DEBUG'):
                        import pickle
                        pickle.dump((za, zb, bytes(Z.memory), bytes(B.memory), zst['on']), open(os.environ['SQ_DEBUG'], 'wb'))
                    return C, dict(ex)
            if C['hook e_pl'] == state.get('npl'):
                state['idle'] = state.get('idle', 0) + 1
                if state['idle'] > 3 and any(ns.attr[s][3] & 0x80 for s in range(24)):
                    C['frames with figure sprites up and no play loop (info)'] += 1
                    if len(ex['stale']) < 5:
                        ex['stale'].append(nf)
            else:
                state['idle'] = 0
            state['npl'] = C['hook e_pl']
            ma, mb = A.memory, B.memory
            if any(A.registers[k] != B.registers[k] for k in CMP if k != 25):
                fail('registers differ!', nf, [(k, A.registers[k], B.registers[k]) for k in CMP
                                               if A.registers[k] != B.registers[k]][:4])
                return C, dict(ex)
            a1 = bytes(ma[0x5B00:0x10000])
            b1 = bytes(mb[0x5B00:0x10000])
            if a1 != b1:
                d = [i for i in range(len(a1)) if a1[i] != b1[i]]
                adr = [i + 0x5B00 for i in d]
                adr = [a for a in adr if not (sp - 64 <= a < sp) and a not in sitebytes]
                if adr:
                    fail('memory differs!', nf, ['%04X' % a for a in adr[:6]], len(adr))
                    return C, dict(ex)
            if bytes(ma[0x5800:0x5B00]) != bytes(mb[0x5800:0x5B00]):
                attr_diff += 1
            # the patched attributes never carry a figure's paint: compare with the hidden-paint truth
            if pa.bad or pb.bad:
                fail('port reads past the recording!', nf, pa.bad, pb.bad)
                return C, dict(ex)
            if progress and nf % 500 == 0:
                progress(nf)
        if stop and nf >= stop:
            break
    C['frames'] = nf
    C['hook T at 3.5 MHz'] = HOOKT[0]
    C['frames with attributes differing (paint removed)'] = attr_diff
    return C, dict(ex)


# ---------------------------------------------------------------------------------------------
# Negative controls: broken builds the lockstep must catch
# ---------------------------------------------------------------------------------------------

def negative_patches(z80=None):
    out = []
    prof = load_profile()
    syms = {k: int(v, 16) for k, v in prof['hooks']['syms'].items()}
    rom = bytes.fromhex(prof['hooks']['rom'])

    def rep(name, old, new, nth=0):
        r = bytearray(rom)
        i = -1
        for _ in range(nth + 1):
            i = r.find(old, i + 1)
        if i < 0:
            raise ValueError(name)
        r[i:i + len(old)] = new
        out.append((name, StarquakePatch(prof, rom_code=bytes(r))))
    rep('x one pixel right (add a,28 -> 29)', bytes.fromhex('c61c'), bytes.fromhex('c61d'))
    rep('wrong image page (add a,STP -> STP+1)', bytes.fromhex('c61a'), bytes.fromhex('c61b'))
    rep('hook clobbers BC (pop bc -> pop de at exit)', bytes.fromhex('e1d1c1f1c3b1d8'), bytes.fromhex('e1d1d1f1c3b1d8'))
    rep('MMU7 left on the store (nextreg 0x57,a -> nop nop nop)', bytes.fromhex('ed92577ced9207'), bytes.fromhex('0000007ced9207'))
    rep('the plot stretch never opened (e_ob, nextreg 7,3 -> nops)', bytes.fromhex('ed910703c1f1'), bytes.fromhex('00000000c1f1'))
    rep("the plot stretch never closed (e_pl, nextreg 7,a -> nops)", bytes.fromhex('ed92577ced9207'), bytes.fromhex('ed92577c000000'))
    rep("the plot stretch at the wrong object (never reached)", bytes.fromhex('f5fe03'), bytes.fromhex('f5fe07'))
    rep('BLOB never hidden on a clear (hideall 24 -> 20)', bytes.fromhex('0618ed9234'), bytes.fromhex('0614ed9234'))
    sites = dict(SITES_CALL)
    del sites[0xD964]
    out.append(('attributes not put back (no e_un site)', StarquakePatch(prof, sites=sites)))
    out.append(('a game store removed (0xDB51 tile XOR LD (HL),A -> NOP)', _extra_nop(prof, 0xDB51, 0x77)))
    out.append(('a paint store removed (0xD943 -> NOP: the 0x5B00 overflow lost)', _extra_nop(prof, 0xD943, 0x77)))
    out.append(('a plot store kept (0xDF97 not NOP: figure pixels on the ULA)', StarquakePatch(prof, nops=NOPS[1:])))
    out.append(('alt ROM filled at 0x386E- only (NextZXOS ROM3 code left round the hooks: the 30763c45 build)', _rom3_left(prof)))
    out.append(('white outline drawn (old design: drop_outline off)', _outline_back(prof)))
    out.append(("BLOB's black fill see-through (fill 2 -> 0, images 144-195)", _fill_clear(prof, range(EN_N, NIMG), z80)))
    return out


def _extra_nop(prof, addr, old):
    p = StarquakePatch(prof)
    p.sites.append((addr, bytes([old]), b'\x00'))
    return p


def _rom3_left(prof):
    # the build before 2026-11-04: only the hook bytes written over NextZXOS's ROM3 in the alt ROM image
    p = StarquakePatch(prof)
    p.altrom = (ROM_ORG, p.regblock + 20)
    p.altrom_low = None
    return p


def _outline_back(prof):
    # the design before 2026-11-04: a one-pixel ring round every figure (white; black on a white one)
    p = StarquakePatch(prof)
    p.colours = {}
    return p


def _fill_clear(prof, imgs, z80):
    # every black-fill pixel of these images made transparent: background shows through the holes
    from skoolkit.snapshot import Snapshot
    from .simrun import addr_view
    p = StarquakePatch(prof)
    cm = dict(load_colours())
    m = addr_view(Snapshot.get(z80))
    px = {}
    for n in imgs:
        cv = canvas(lambda a: m[a], n, cm)
        px.update({'%d:%d,%d' % (n, x - ORGX, y - ORGY): 0 for y in range(CANVAS) for x in range(CANVAS) if cv[y][x] == 2})
    if not px:
        raise ValueError('no fill in these images')
    cm['pixels'] = dict(cm.get('pixels', {}), **px)
    p.colours = cm
    return p


# ---------------------------------------------------------------------------------------------
# RECOLOUR: rewrite the pattern store banks from a colour map (no rebuild of game banks)
# ---------------------------------------------------------------------------------------------

# No RECOLOUR registration (import, 2026-11-04): this map's format is the engine's own ({"drop_outline", "pixels":
# "image:x,y" -> code}), not coloursheet's, so the shared recolour tool and its selftest guard cannot read it.
# recolour_own_map() below rewrites the store banks from such a map; it has not been run on a painting.


def recolour_own_map(nex_bytes, cmap):
    from . import recolour as rc
    banks = rc.banks(nex_bytes)
    ram = banks[5] + banks[2] + banks[0]
    s = store(lambda a: ram[a - 0x4000], cmap)
    out, _ = rc.splice(nex_bytes, {b: s[i * 16384:(i + 1) * 16384] for i, b in enumerate(STORE_BANKS)})
    return out, {'images': NIMG, 'pixels': len(cmap.get('pixels', {}))}


def colour_identity(peek):
    import hashlib
    h = hashlib.md5(bytes(peek(a) for a in list(range(EN0, EN0 + 48 * EN_N)) + list(range(PL0, PL0 + 48 * PL_N))))
    return {'schema': 1, 'game': 'starquake', 'engine': 'starquake', 'keys': 'image:x,y v1',
            'inputs': h.hexdigest(), 'geometry': None}


def canvas_rules(get, n, cv=None):
    """The canvas rules for image n (cv: its canvas, default canvas(get, n)) -> [broken rules]: every ink bit of the
    graphic is ink (1) and nothing else is; nothing on the canvas edge (never clipped); no transparent pixel enclosed
    (holes filled); every pixel touching the figure (8 ways) is opaque (the outline ring complete); the tiles hold
    the canvas exactly."""
    cv = cv if cv is not None else canvas(get, n)
    W, b, bad = CANVAS, image_base(n), []
    ink = {(ORGY + r, ORGX + c) for r in range(16) for c in range(24)
           if (get(b + 3 * r) << 16 | get(b + 3 * r + 1) << 8 | get(b + 3 * r + 2)) >> (23 - c) & 1}
    if not ink:
        return [] if not any(any(r) for r in cv) else ['blank image drawn']
    if {(y, x) for y in range(W) for x in range(W) if cv[y][x] == 1} != ink:
        bad.append('ink pixels differ from the graphic')
    if any(cv[0][x] or cv[W - 1][x] or cv[x][0] or cv[x][W - 1] for x in range(W)):
        bad.append('clipped: drawn on the canvas edge')
    out, st = {(0, 0)}, [(0, 0)]
    while st:
        y, x = st.pop()
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < W and 0 <= xx < W and (yy, xx) not in out and not cv[yy][xx]:
                out.add((yy, xx))
                st.append((yy, xx))
    if any(not cv[y][x] and (y, x) not in out for y in range(W) for x in range(W)):
        bad.append('a hole left transparent')
    if any(cv[y][x] in (1, 2) and any(0 <= y + dy < W and 0 <= x + dx < W and not cv[y + dy][x + dx]
                                      for dy in (-1, 0, 1) for dx in (-1, 0, 1)) for y in range(W) for x in range(W)):
        bad.append('outline ring open')
    t = tiles(cv)
    back = [[(t[(y // 16 * 2 + x // 16) * 128 + (y % 16) * 8 + (x % 16) // 2] >> (4 * (1 - x % 2))) & 15
             for x in range(W)] for y in range(W)]
    if back != cv:
        bad.append('tiles do not hold the canvas')
    return bad


def unit_tests(patch, states=(), neg=None, z80=None):
    """Cases no recording needs to reach: the canvas rules (canvas_rules) on every one of the 196 images, drawn or
    not in the recordings, from the game's own graphics; and a negative control: canvases broken on purpose (an ink
    pixel cleared, the outline dropped, a hole cut, the image moved onto the edge) must each break a rule.
    -> (Counter, failures). Without z80 (the snapshot) nothing is checked: 'not exercised'."""
    C, fails = collections.Counter(), []
    if z80 is None:
        C['unit tests not exercised (no snapshot)!'] += 1
        return C, ['no snapshot']
    from . import z80tonex as zt
    s = zt.Z80Snapshot(z80)
    ram = bytes(s.banks[5] + s.banks[2] + s.banks[0])
    get = lambda a: ram[a - 0x4000]
    for n in range(NIMG):
        bad = canvas_rules(get, n)
        C['images'] += 1
        for k in bad:
            C[k + '!'] += 1
            fails.append((n, k))
    n = next(i for i in range(NIMG) if any(get(image_base(i) + k) for k in range(48)))
    cv = canvas(get, n)
    y0, x0 = next((y, x) for y in range(CANVAS) for x in range(CANVAS) if cv[y][x] == 1)
    broken = {'ink pixel cleared': lambda c: c[y0].__setitem__(x0, 2),
              'outline dropped': lambda c: [r.__setitem__(x, 0) for r in c for x in range(CANVAS) if r[x] == 3],
              'hole cut': lambda c: c[y0].__setitem__(x0, 0),
              'moved onto the edge': lambda c: [c.__setitem__(y, c[y][4:] + [0] * 4) for y in range(CANVAS)]}
    for k, f in broken.items():
        c = [list(r) for r in cv]
        f(c)
        C['negative control cases'] += 1
        if canvas_rules(get, n, c):
            C['negative control detected'] += 1
        else:
            C['negative control (%s) NOT DETECTED!' % k] += 1
            fails.append(('negative', k))
    return C, fails


# ---------------------------------------------------------------------------------------------
# Build, loading screen, auto (imported 2026-11-04: the pilot built these with work/build.py and
# loading/work/mkload.py; the same bytes)
# ---------------------------------------------------------------------------------------------

LOADING = 'starquake_loading.scr'    # the tape's 6,912-byte loading screen, beside the snapshot (record input)
LOAD_BANK = 22


def loading_nex(nex, scr):
    """The sprite build with the tape's loading screen (the approved .nxc's build): bank 5's screen area holds
    the picture, bank 22 (asm loading: the hold, then bank 5's own screen put back) is the entry bank."""
    h = load_profile()['hooks']
    o = bytes(nex)
    if len(scr) != 6912:
        raise ValueError('loading screen: %d bytes, want 6912' % len(scr))
    hd = bytearray(o[:512])
    if hd[18 + LOAD_BANK] or hd[139] != 10 or any(o[18 + k] for k in range(LOAD_BANK + 1, 112)):
        raise ValueError('not a starquake sprite build: bank 22 in use, entry bank %d, or a bank above 22' % hd[139])
    code, end = bytes.fromhex(h['loading']), bytes.fromhex(h['loadend'])
    bank = code + o[512:512 + 6912]
    bank += bytes(0x4000 - len(end) - len(bank)) + end
    hd[9] += 1
    hd[18 + LOAD_BANK] = 1
    hd[139] = LOAD_BANK
    return bytes(hd) + scr + o[512 + 6912:] + bank


def build(z80, out, name, say=print):
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    c = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (c[1], c[1] + len(c[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300], TAIL_ADDR))
    patch = StarquakePatch()
    spr = os.path.join(out, name + '_sprites.nex')
    c = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (c[1], c[1] + len(c[2])))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300]))
    scr = os.path.join(os.path.dirname(os.path.abspath(z80)), LOADING)
    if os.path.exists(scr):
        ld = os.path.join(out, name + '_sprites_loading.nex')
        open(ld, 'wb').write(loading_nex(open(spr, 'rb').read(), open(scr, 'rb').read()))
        say('Loading   : %s  %s  (the tape\'s screen held by bank 22 until a key or 5 s)' % (os.path.basename(ld), md5(ld)))
    else:
        say('Loading   : no %s beside the snapshot: no loading-screen build' % LOADING)
    return not bad and not bad2, patch


def fixtures(rzxs):
    """The recordings given, by the record's name for their MD5 ({'m1': path, ...}): a negative's fixture is the
    record's recording, whatever the file is called; another file called m1.rzx is not it."""
    import hashlib
    from . import records
    names = {r['md5']: os.path.splitext(r['name'])[0] for r in records.load('starquake')['inputs']['recordings']}
    out = {}
    for p in rzxs:
        k = names.get(hashlib.md5(open(p, 'rb').read()).hexdigest())
        if k:
            out[k] = p
    return out


# negatives: the recording (name, frames; 0 = whole) that reaches each case
NEG_PLAN = {'a paint store removed (0xD943 -> NOP: the 0x5B00 overflow lost)': ('b1', 5500)}
NEG_DEFAULT = ('m1', 0)


def auto(a, z80, name, out, say):
    import time
    say('Game      : %s' % name)
    say('Engine    : starquake (XOR plotter keeps running without its screen stores; six figures -> sprites; '
        'attribute paint saved and put back)')
    ok, patch = build(z80, out, name, say)
    from .nextboot import rom_model
    rzxs = list(a.rzx or [])
    stop = getattr(a, 'quick', None)
    if rzxs:
        say('ROM model : %s' % rom_model())
    if rzxs:
        u, uf = unit_tests(patch, z80=z80)
        ok = ok and not uf
        say('Unit      : %s %s' % ('PASS' if not uf else 'FAILED', ' '.join('%s=%s' % kv for kv in sorted(u.items()))))
    for r in rzxs:
        t = time.time()
        c, ex = verify(patch, r, stop=stop)
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %s, %.0fs -> %s' % (os.path.basename(r), ', '.join('%s %s' % (k, v) for k, v in sorted(c.items())
                                                                              if not k.endswith('!'))[:700],
                                               time.time() - t, 'IDENTICAL' if not fails else 'FAILED %s' % fails))
    if rzxs:                                    # the caller's speed comes back whatever it is (card patch.restore-speed)
        for sp in (1, 2, 3):
            c, ex = verify(patch, rzxs[0], stop=min(stop or 1500, 1500), speed=sp)
            fails = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fails
            say('Speed     : caller at NR 7 = %d, %s, %d frames -> %s' % (sp, os.path.basename(rzxs[0]), c['frames'],
                                                                         'IDENTICAL' if not fails else 'FAILED %s' % fails))
    from . import runchecks
    if rzxs and stop:
        runchecks.add(runchecks.RUN, 'negatives', 'incomplete', '--quick %d: the negatives need whole recordings' % stop)
    if rzxs and not stop:
        by = fixtures(rzxs)
        det = tot = 0
        unrun = []
        for nm, p in negative_patches(z80):
            k, n = NEG_PLAN.get(nm, NEG_DEFAULT)
            tot += 1
            if k not in by:
                say('Negative  : %-62s NOT EXERCISED (no recording with the record\'s %s.rzx MD5)' % (nm, k))
                unrun.append(nm)
                continue
            c, _ = verify(p, by[k], stop=n or None)
            f = {x: v for x, v in c.items() if x.endswith('!')}
            det += bool(f)
            say('Negative  : %-62s %s' % (nm, 'DETECTED on %s %s' % (k, str(f)[:120]) if f else 'NOT DETECTED (%s)' % k))
        ok = ok and det == tot - len(unrun)
        say('Negatives : %d of %d DETECTED%s' % (det, tot, ', %d NOT EXERCISED' % len(unrun) if unrun else ''))
        runchecks.add(runchecks.RUN, 'negatives', 'incomplete' if unrun else 'pass' if det == tot else 'fail',
                      ('not exercised: %s' % '; '.join(unrun)) if unrun else '%d of %d detected' % (det, tot))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
