"""Yie Ar Kung-Fu (Imagine 1985, 128K edition): fighters, thrown stars, chain and hit spark -> 4-bit hardware sprites.
Game facts: games/yie_ar_kung_fu.md; hook source: asm/yie_hooks.asm. Original and patched machines replay the recording
in lockstep; hook instructions are not counted, so game code stays in step."""
import collections
import copy
import hashlib
import json
import os

RECORD = 'yie'
SIG = (0xB3F9, bytes.fromhex('01fd7f'))
ROM_ORG = 0x386E
HB = 0xE000
CODE0 = 0x0600
BITS = 0x00F0
STORE = 28
NSTORE = 32
ALT_PAGE, HPG = 24, 26
V_RING = 0x0004
TAB = 0x1800
_HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = os.path.join(_HERE, '..', 'docs', 'profiles', 'yie_colours.json')
# Group colours: index 0 transparent, 1 ink, 2 body, 3 outline. 0 hero, 1 opponent, 2 objects and chain, 3 spark.
# The game's own colours in play: black ink on the lawn's cyan paper (attribute 0x28); the outline is the owner's white.
BLACK, CYAN, WHITE = 0x00, 0x16, 0xFF
GROUPS_DEFAULT = [[0, BLACK, CYAN, WHITE]] * 3 + [[0, BLACK, CYAN, WHITE]]
NOP_SITES = [(0xB632, 0x12), (0xB6AC, 0x12), (0xB6C4, 0x12), (0xB73A, 0x12), (0xB7BA, 0x12), (0xB7D7, 0x12),
             (0xF571, 0x12), (0xEF39, 0x77), (0xEF76, 0x77), (0xB90B, 0x77), (0xB914, 0x77), (0xB91B, 0x77), (0xB948, 0x12),
             (0xB92D, 0x12)]
SITES = [(0xB4EC, 'cdd8b5', 'CD', 'e_plot'), (0xB528, 'cdd8b5', 'CD', 'e_plot'), (0xB3F9, '01fd7f', 'CD', 'e_flip'),
         (0xF563, 'cd6cf5', 'CD', 'e_star'), (0xEF25, '22e3bd', 'CD', 'e_chain'), (0xEFAB, '2ae3bd', 'C3', 'e_cwipe'),
         (0xB908, '3ac8b9', 'CD', 'e_spark'), (0xB91C, 'cd90f4', 'CD', 'e_spoff'),
         (0xAAAF, '21ff5a', 'C3', 'e_wa'), (0xAAE9, '3acfbd', 'C3', 'e_wb')]
CMP = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27]
# A and F may differ on plots over a figure's pixels: the stores are gone, so what a plot reads differs until A is next loaded
FIG_SPANS = [(0xB5D8, 0xB7EF), (0xB4EF, 0xB50F), (0xB52B, 0xB546), (0xF56C, 0xF579), (0xF566, 0xF56B), (0xEF36, 0xEF56), (0xEF73, 0xEF93),
             (0xF410, 0xF41B), (0xB417, 0xB422), (0xB3D6, 0xB3D9), (0xB547, 0xB54B)]
RNG_READ = 0xB9AE
CLEAN = 0x5B00                  # clean copy of the screen's lower two thirds, from 0x4800
ZONE = (64, 192)
HALT = 0xB3E2
OBJI, FPTR = 48570, 47088


def is_yie(snap):
    a, b = SIG
    try:
        m = snap.ram(-1)
    except Exception:
        return False
    if len(m) != 0x20000:
        return False
    bank2 = snap.memory.banks[2]
    return bytes(bank2[a - 0x8000:a - 0x8000 + len(b)]) == b and bytes(bank2[0xB4EC - 0x8000:0xB4EF - 0x8000]) == bytes.fromhex('cdd8b5')


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def load_colours(path=COLOURS):
    return json.load(open(path)) if os.path.exists(path) else None


def tab_bytes():
    t = bytearray(1024)
    for k in range(4):
        for v in range(256):
            hi = (v >> (7 - 2 * k)) & 1
            lo = (v >> (6 - 2 * k)) & 1
            t[k * 256 + v] = hi << 4 | lo
    return bytes(t)


class YiePatch:
    name = 'Yie Ar Kung-Fu figures -> hardware sprites (alt ROM stubs, page 26 at slot 7, screen stores gone)'

    def __init__(self, prof=None, colours=None, rom_code=None, page_code=None, outline=True, sites=None, nops=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.page_code = page_code if page_code is not None else bytes.fromhex(h['page'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.groups = [list(g) for g in (colours or {}).get('groups', GROUPS_DEFAULT)]
        self.stub_extra = bytes.fromhex(h['setup']) + self.palette()
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.outline = outline
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock != self.syms['rom_end']:
            raise ValueError('hook code length differs from the profile symbols')
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hooks reach 0x3D00')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        self.page = bytearray(8192)
        self.page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.hpage = bytearray(16384)
        self.hpage[V_RING] = 1 if outline else 0
        self.hpage[CODE0:CODE0 + len(self.page_code)] = self.page_code
        self.hpage[TAB:TAB + 1024] = tab_bytes()
        self.hpage[BITS:BITS + 4] = bytes([1, 2, 4, 8])
        self.sites = []
        for a, old, op, sym in (sites if sites is not None else SITES):
            self.sites.append((a, bytes.fromhex(old), bytes.fromhex(op) + self.syms[sym].to_bytes(2, 'little')))
        self.nops = list(nops if nops is not None else NOP_SITES)
        self._banks()

    def palette(self):
        out = bytearray(64)
        for g, cols in enumerate(self.groups[:4]):
            out[g * 16:g * 16 + 4] = bytes(cols)
        return bytes(out)

    def _banks(self):
        self.extra_banks = {12: bytes(self.page) + bytes(8192), 13: bytes(self.hpage)}

    def apply(self, snap):
        from . import z80tonex as zt
        if not snap.is128 or snap.port7ffd & 7 != 7:
            raise ValueError('Yie Ar Kung-Fu patch expects the 128K snapshot (7FFD bank 7)')
        ram = {5: bytearray(snap.banks[5]), 2: bytearray(snap.banks[2]), 7: bytearray(snap.banks[7])}

        def where(a):
            return (5, a - 0x4000) if a < 0x8000 else ((2, a - 0x8000) if a < 0xC000 else (7, a - 0xC000))
        for a, old, new in self.sites:
            for k in range(len(old)):
                b, o = where(a + k)
                if ram[b][o] != old[k]:
                    raise ValueError('unexpected code at 0x%04X' % (a + k))
            for k, v in enumerate(new):
                b, o = where(a + k)
                ram[b][o] = v
        for a, old in self.nops:
            b, o = where(a)
            if ram[b][o] != old:
                raise ValueError('unexpected byte at 0x%04X' % a)
            ram[b][o] = 0
        regs = zt.build_tail(snap, 0x8000, self.slot1, True)[3]
        self.page[self.regblock - 0x2000:self.regblock - 0x2000 + len(regs)] = regs
        self._banks()
        snap.banks[5], snap.banks[2], snap.banks[7] = bytes(ram[5]), bytes(ram[2]), bytes(ram[7])


# ---------------------------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------------------------

class _NS:
    """Next-side state of the patched machine."""

    def __init__(self, patch):
        self.nr = {0x07: 0, 0x56: 14, 0x57: 15, 0x15: 1}
        self.store = bytearray(NSTORE * 8192)
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.H = bytearray(patch.hpage[:8192])
        self.palhold = dict()

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def out(self, port, val):
        if port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
            return True
        if port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
            return True
        return False

    def sprite_layer(self):
        """-> {(x, y): (colour index, slot)}, screen coordinates, slot order as the hardware's: higher on top.
        .under_ink: the pixels where a lower slot has an ink pixel (under a higher sprite's pixel)."""
        out = _Layer()
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            x0 = a0 + (a2 & 1) * 256 - 32
            y0 = a1 + (a4 & 1) * 256 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            mir = a2 & 8
            for j in range(16):
                for k in range(16):
                    b = self.pat[base + j * 8 + k // 2]
                    c = (b >> 4) if k % 2 == 0 else (b & 15)
                    if c:
                        xy = (x0 + (15 - k if mir else k), y0 + j)
                        if xy in out and out[xy][0] == 1:
                            out.under_ink.add(xy)
                        out[xy] = (c, i)
        return out


def rom48_image():
    from .build import rom48
    return bytes(rom48())


def game_machine(snap):
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    sim = from_snapshot(Simulator, snap, config={'int_active': 0})
    sim.memory.roms[1][:] = list(rom48_image())
    return sim


class _Ports:
    def __init__(self, sim, snap, ns=None):
        self.sim, self.ns = sim, ns
        self.o7ffd = snap.out7ffd
        self.ins = []
        self.i = 0
        self.bad = 0

    def read_port(self, registers, port):
        if self.i < len(self.ins):
            self.i += 1
            return self.ins[self.i - 1]
        self.bad += 1
        return 255

    def write_port(self, registers, port, value, offset=0):
        if self.ns is not None and self.ns.out(port, value):
            return
        if port & 0x8002 == 0 and self.o7ffd & 32 == 0:
            self.sim.memory.out7ffd(value)
            self.o7ffd = value


def _patched_memory(mem, patch, ns, err):
    from skoolkit.pagingtracer import Memory
    MG, MS = Memory.__getitem__, Memory.__setitem__
    lo, hi = patch.altrom
    page = patch.page
    H = ns.H
    nr = ns.nr
    store = ns.store

    class PM(Memory):
        def __getitem__(self, a):
            if a >= HB and nr[0x57] == HPG:
                return H[a - HB]
            if 0xC000 <= a < 0xE000 and nr[0x56] != 14:
                pg = nr[0x56] - STORE
                if 0 <= pg < NSTORE:
                    return store[pg * 8192 + a - 0xC000]
                err.append(('slot 6 page', nr[0x56]))
                return 0
            if a < 0x4000:
                if lo <= a < hi:
                    if not self.o7ffd & 16:
                        err.append(('alt ROM stub with ROM 0 selected', a))
                    return page[a - 0x2000]
                if not self.o7ffd & 16:
                    err.append(('read of ROM 0', a))
            return MG(self, a)

        def __setitem__(self, a, v):
            if a >= HB and nr[0x57] == HPG:
                H[a - HB] = v
                return
            if 0xC000 <= a < 0xE000 and nr[0x56] != 14:
                pg = nr[0x56] - STORE
                if 0 <= pg < NSTORE:
                    store[pg * 8192 + a - 0xC000] = v
                else:
                    err.append(('slot 6 write', nr[0x56]))
                return
            MS(self, a, v)
    mem.__class__ = PM


def patched_machine(snap, patch, err):
    from . import z80n
    sim = game_machine(snap)
    ns = _NS(patch)
    mem = sim.memory
    for a, old, new in patch.sites:
        for k, v in enumerate(new):
            mem[a + k] = v
    for a, old in patch.nops:
        mem[a] = 0
    _patched_memory(mem, patch, ns, err)
    z80n.install(sim, ns.nextreg, strict=False)
    return sim, ns


def _frames(rzx_path):
    from skoolkit.rzxplay import parse_rzx, InputRecording
    from skoolkit.snapshot import Snapshot
    import shutil
    import tempfile
    out, snap = [], None
    fd, tmp = tempfile.mkstemp(suffix='.rzx', dir=os.environ.get('TMPDIR'))
    os.close(fd)
    try:
        shutil.copy(rzx_path, tmp)
        for block in parse_rzx(tmp):
            o = block.obj
            if isinstance(o, InputRecording):
                out.append((o.snapshot if getattr(o, 'snapshot', None) else snap,
                            [(f.fetch_counter, list(o.data[f.start:f.end])) for f in o.frames]))
            else:
                snap = o
    finally:
        os.remove(tmp)
    return out


def _accept(sim, pc):
    R, mem = sim.registers, sim.memory
    R[25] = 0
    if R[26]:
        if mem[pc] == 0x76:
            R[24] = (R[24] + 1) % 65536
        sim.accept_interrupt(R, mem, 0)


def _addr(line, col, base=0x4000):
    return base + (((line & 0xC0) << 5) | ((line & 7) << 8) | ((line & 0x38) << 2)) + col


def in_spans(pc):
    return any(a <= pc <= b for a, b in FIG_SPANS)


def shown_bank(o7ffd):
    return 7 if o7ffd & 8 else 5


def clean_pixels(mem, line, col):
    return mem.banks[5][CLEAN - 0x4000 + (_addr(line, col) - 0x4800)]


class _Layer(dict):
    def __init__(self):
        super().__init__()
        self.under_ink = set()


SPARK_FLIPS = 4                 # screen flips after a spark until both screens have been drawn again


def cell_of(addr):
    """screen address -> (x, y) of its 8 x 8 cell's top left"""
    a = addr & 0x1FFF
    return (a & 31) * 8, ((a >> 8) & 7) | ((a >> 2) & 0x38) | ((a >> 5) & 0xC0)


def expected_vs_original(so_mem, sp_mem, o7ffd, lay, skip_chain=None, allowed=None, hole=None):
    """The shown screen of the original against sprites over the patched screen, for the figure zone.
    A sprite ink pixel must be set in the original; a body pixel clear; outline and empty pixels as the clean copy shows.
    Exceptions, by design, both about the outline (the owner's white ring, which the game does not draw): it may lie on
    another figure's ink, where the original shows that ink, or on a scenery pixel the game's mask clears next to the
    figure (both hide the scenery there). And the spark: the game copies it over its whole cell, so a figure there
    loses those pixels until the game draws that screen again; sprites keep the figure whole. `hole` = the last
    spark's cell (x, y) while that lasts: in it, a figure pixel where the original shows the clean copy is allowed.
    Such pixels go to `allowed` as (x, y, kind). -> list of (x, y, sprite code,
    original bit, clean bit)."""
    bad = []
    under = getattr(lay, 'under_ink', ())
    b = shown_bank(o7ffd)
    orig = so_mem.banks[b]
    for y in range(*ZONE):
        for col in range(32):
            a = _addr(y, col) - 0x4000
            o = orig[a]
            c = clean_pixels(so_mem, y, col)
            for i in range(8):
                x = col * 8 + i
                v = lay.get((x, y))
                if hole and v and v[0] in (1, 2) and hole[0] <= x < hole[0] + 8 and hole[1] <= y < hole[1] + 8:
                    if bool(o & (0x80 >> i)) == bool(c & (0x80 >> i)):
                        if allowed is not None:
                            allowed.append((x, y, 'spark hole'))
                        continue
                bit = 0x80 >> i
                ob, cb = bool(o & bit), bool(c & bit)
                if v is None or v[0] == 3:
                    if ob != cb:
                        if skip_chain and skip_chain(x, y):
                            continue
                        if v and ob and (x, y) in under:
                            if allowed is not None:
                                allowed.append((x, y, 'on ink'))
                            continue
                        if v and not ob and cb:
                            if allowed is not None:
                                allowed.append((x, y, 'masked'))
                            continue
                        bad.append((x, y, v[0] if v else 0, ob, cb))
                elif v[0] == 1:
                    if not ob:
                        if skip_chain and skip_chain(x, y):
                            continue
                        bad.append((x, y, 1, ob, cb))
                elif v[0] == 2:
                    if ob:
                        if skip_chain and skip_chain(x, y):
                            continue
                        bad.append((x, y, 2, ob, cb))
    return bad


# ---------------------------------------------------------------------------------------------
# Differential verification: lockstep over the recording
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=4):
    """-> (Counter, examples, states). Failure keys end in '!'."""
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    st = {'frame': 0}

    def fail(k, *info):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + info)

    lo, hi = patch.altrom
    for snap, frames in _frames(rzx_path):
        so = game_machine(snap)
        po = _Ports(so, snap)
        so.set_tracer(po)
        err = []
        sp, ns = patched_machine(snap, patch, err)
        pp = _Ports(sp, snap, ns)
        sp.set_tracer(pp)
        Ro, Rp, mo, mp, op = so.registers, sp.registers, so.memory, sp.memory, sp.opcodes
        nr = ns.nr
        H = ns.H
        hook_t = [0]
        worst = [0]
        chain = [False]
        tick = [0]
        ENTRIES = {a: None for a, _, _ in patch.sites}
        code_bytes = {a + k: None for a, old, new in patch.sites for k in range(len(old))}
        code_bytes.update({a: None for a, _ in patch.nops})

        def in_hook(pc):
            return lo <= pc < hi or (pc >= HB and nr[0x57] == HPG)

        def check_shown(where, _dump=[0]):
            """figure zone of the shown screen: patched screen clean, sprites = what the original shows"""
            c['layer checks'] += 1
            bk = shown_bank(mp.o7ffd)
            if pp.o7ffd != po.o7ffd:
                fail('paging differs', hex(pp.o7ffd), hex(po.o7ffd))
                return
            scr = mp.banks[bk]
            cl = mp.banks[5]
            for y in range(*ZONE):
                a0 = _addr(y, 0) - 0x4000
                k0 = CLEAN - 0x4000 + (a0 + 0x4000 - 0x4800)
                if bytes(scr[a0:a0 + 32]) != bytes(cl[k0:k0 + 32]):
                    for col in range(32):
                        if scr[a0 + col] != cl[k0 + col]:
                            fail('patched screen not clean at a layer check', where, y, col, scr[a0 + col], cl[k0 + col])
                            break
                    break
            lay = ns.sprite_layer()
            chn = None
            if H[0x12]:
                # the chain is an XOR on the shown screen: on a figure it inverts; those pixels are not modelled, the rest are
                ys = set()
                for s in range(80, 112):
                    if ns.attr[s][3] & 0x80:
                        ys.add(ns.attr[s][1] - 32)
                if ys:
                    y0 = min(ys)
                    chn = lambda x, y: y0 <= y <= y0 + 6
                c['chain up at a layer check'] += 1
            ok_out = []
            hole = st['hole'][:2] if st.get('hole') else None
            bad = expected_vs_original(mo, mp, po.o7ffd, lay, chn, ok_out, hole)
            c['figure pixels in a spark\'s cell the original has wiped (by design)'] += sum(1 for q in ok_out if q[2] == 'spark hole')
            c['outline pixels on another figure\'s ink (by design)'] += sum(1 for q in ok_out if q[2] == 'on ink')
            c['outline pixels where the game masks the scenery (by design)'] += sum(1 for q in ok_out if q[2] == 'masked')
            if bad:
                fail('sprite layer differs from the original screen', where, len(bad), bad[:6])
            c['layer pixels compared'] += len(lay)
            mx = 0
            per = collections.Counter()
            for s in range(128):
                a = ns.attr[s]
                if a[3] & 0x80:
                    yy = a[1] + (a[4] & 1) * 256 - 32
                    for l in range(yy, yy + 16):
                        per[l] += 1
            if per:
                worst[0] = max(worst[0], max(per.values()))

        def compare_state(pc):
            for i in CMP:
                if Ro[i] != Rp[i]:
                    if i in (0, 1) and in_spans(pc):
                        c['A or F differ in a figure span'] += 1
                        continue
                    if i in (0, 1) and 0xC000 <= pc:
                        continue
                    fail('register differs', hex(pc), i, Ro[i], Rp[i])
            if Ro[24] != Rp[24]:
                fail('PC differs', hex(Ro[24]), hex(Rp[24]))
            if pp.o7ffd != po.o7ffd:
                fail('paging differs', hex(pp.o7ffd), hex(po.o7ffd))

        def compare_ram():
            c['RAM compares'] += 1
            for b in range(8):
                bo, bp = mo.banks[b], mp.banks[b]
                # the two screens' pixels, attributes in a spark; a stack that an interrupt may push A on; patch sites
                if bytes(bo) == bytes(bp):
                    continue
                for a in range(16384):
                    if bo[a] != bp[a]:
                        addr = a + (0x4000 if b == 5 else 0x8000 if b == 2 else 0xC000)
                        if b in (5, 7) and a < 0x1800:
                            continue
                        if b in (5, 7) and a < 0x1B00 and st.get('spark'):
                            continue
                        if b == 2 and 0xBF80 <= addr <= 0xBFFF:
                            continue
                        if b in (5, 2) and addr in code_bytes:
                            continue
                        if b == 7 and addr in code_bytes:
                            continue
                        fail('RAM differs', b, hex(addr), bo[a], bp[a])
                        return

        for n, (fc, ins) in enumerate(frames):
            if stop and n >= stop:
                break
            st['frame'] = n
            po.ins, po.i = ins, 0
            pp.ins, pp.i = ins, 0
            f1, f2 = fc, fc
            # lockstep: one game instruction in each, hook instructions run free
            pco = pcp = Ro[24]
            f = fc
            while f > 0:
                # patched: run hook code free
                pcp = Rp[24]
                if in_hook(pcp):
                    r0 = list(Rp)
                    t0 = Rp[25]
                    while in_hook(Rp[24]):
                        r15 = Rp[15]
                        o = mp[Rp[24]]
                        op[o]()
                        Rp[15] = r15
                    hook_t[0] = Rp[25] - t0
                    if hook_t[0] > st.get('hook_max', 0):
                        st['hook_max'] = hook_t[0]
                    c['hook T total'] += hook_t[0]
                    if hook_t[0] > 280000:
                        c['hooks over 280000 T at 28 MHz'] += 1
                    Rp[25] = t0
                    c['hook returns'] += 1
                    if not Rp[26] and Ro[26]:
                        fail('hook left interrupts off', hex(Rp[24]))
                    if nr[0x57] != 15 or nr[0x56] != 14:
                        fail('hook page left mapped', hex(Rp[24]))
                    if nr[0x07] != 0:
                        fail('speed not restored', hex(Rp[24]), nr[0x07])
                    pcp = Rp[24]
                    # a hook ended in place of the original's own instruction
                    t = st.get('site')
                    if t is not None:
                        # run the original over the displaced instruction
                        st['site'] = None
                        _run_one(so, Ro, mo)
                        for i in CMP:
                            if i in (0, 1) and in_spans(Rp[24]):
                                continue
                            if Rp[i] != Ro[i]:
                                fail('hook changed a register', hex(t), i, Rp[i], Ro[i])
                        c['hook exits checked'] += 1
                        if Rp[24] != Ro[24]:
                            fail('PC after a hook', hex(t), hex(Rp[24]), hex(Ro[24]))
                    continue
                pco = Ro[24]
                if pco != pcp:
                    fail('PC differs', hex(pco), hex(pcp))
                    f = 0
                    break
                if pcp == HALT and not st.get('halted'):
                    st['halted'] = True
                    tick[0] += 1
                    if tick[0] % every == 0 and n > 2:
                        check_shown('HALT')
                if pcp in ENTRIES:
                    c['site %04X' % pcp] += 1
                    if pcp == 0xB3F9:
                        st['spark'] = False
                        st['halted'] = False
                        if st.get('hole'):
                            st['hole'] = st['hole'][:2] + (st['hole'][2] - 1,) if st['hole'][2] > 1 else None
                    if pcp == 0xB908:
                        st['spark'] = True
                        st['hole'] = cell_of(mo[47566] + 256 * mo[47567]) + (SPARK_FLIPS,)
                    if pcp == 0xEFAB:
                        c['chain wipes'] += 1
                    if pcp == 0xB91C:
                        pass
                    if not Rp[26] and pcp != 0xEFAB:
                        fail('interrupts off at a site', hex(pcp))
                    if pp.o7ffd & 7 != 7:
                        fail('a site with another bank at slot 7', hex(pcp), hex(pp.o7ffd))
                    st['site'] = pcp
                    r15 = Rp[15]
                    o = mp[pcp]
                    op[o]()
                    Rp[15] = r15
                    continue
                if pcp == 0xB90C:
                    check_shown('spark')
                    c['spark layer checks'] += 1
                if pcp == RNG_READ:
                    # the generator walks all of memory: where a byte differs (figures, patch sites, stubs) the original's value stands
                    hl = Rp[6] * 256 + Rp[7]
                    vo, vp = mo[hl], mp[hl]
                    o = mo[pco]
                    so.opcodes[o]()
                    op[mp[pcp]]()
                    if vo != vp:
                        Rp[0] = Ro[0]
                        c['generator reads where bytes differ'] += 1
                    c['generator reads'] += 1
                    f -= 1
                    continue
                o = mo[pco]
                oo = mp[pcp]
                if o != oo and pcp not in code_bytes:
                    fail('code differs at', hex(pcp), o, oo)
                if o in (0xDD, 0xFD):
                    r0_ = Ro[15]
                    so.opcodes[o]()
                    op[oo]()
                    f -= 2 - ((Ro[15] ^ r0_) % 2)
                else:
                    so.opcodes[o]()
                    op[oo]()
                    f -= 2 if o in (0xCB, 0xED) else 1
                if Rp[12] != Ro[12]:
                    fail('SP differs', hex(pcp), hex(Ro[12]), hex(Rp[12]))
                    f = 0
            # end of frame
            while in_hook(Rp[24]):
                r15 = Rp[15]
                o = mp[Rp[24]]
                op[o]()
                Rp[15] = r15
            if n % every == 0:
                compare_state(Ro[24])
                compare_ram()
            c['frames'] += 1
            if err:
                fail('patched machine error', err[:3])
                err.clear()
            _accept(so, pco)
            _accept(sp, pcp)
            if Ro[24] != Rp[24]:
                fail('PC after interrupt', hex(Ro[24]), hex(Rp[24]))
            if progress and n % 500 == 0:
                progress(n)
            if any(k.endswith('!') for k in c) and sum(v for k, v in c.items() if k.endswith('!')) > 30:
                break
    c['most sprites on a line'] = worst[0]
    c['longest hook T at 28 MHz'] = st.get('hook_max', 0)
    return c, ex, states


def _run_one(sim, R, mem):
    op = mem[R[24]]
    sim.opcodes[op]()


def boot_check(nex, z80, patch=None):
    """Boot the NEX in the Next model to the snapshot PC: registers, NEX banks = the (patched) snapshot's, paging, alt ROM."""
    from . import nextboot, z80tonex as zt
    from .build import rom48
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)
        patch.apply(s)
    st = nextboot.boot(nex, s.pc)
    R, mem = st['R'], st['mem']
    bad = list(st['bad'])
    w = lambda h, l: R[h] * 256 + R[l]
    got = [w(2, 3), w(4, 5), w(6, 7), w(0, 1), w(8, 9), w(10, 11), w(18, 19), w(20, 21), w(22, 23),
           w(16, 17), R[12], R[14], R[27], R[26]]
    exp = [s.bc, s.de, s.hl, s.a * 256 + s.f, s.ix, s.iy, s.bc_, s.de_, s.hl_, s.a_ * 256 + s.f_,
           s.sp, s.i, s.im, s.iff1]
    bad += [('register', i, g, e) for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    banks, _, _ = nextboot.load_nex(nex)
    for b in range(8):
        if bytes(banks[b]) != bytes(s.banks[b]):
            bad.append(('NEX bank differs from the (patched) snapshot', b))
    if st['p7ffd'] != s.port7ffd:
        bad.append(('paging', hex(st['p7ffd'])))
    if patch is not None:
        lo, hi = patch.altrom
        img1 = bytearray(rom48())
        img1[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
        if bytes(st['alt'][1]) != bytes(img1):
            bad.append(('alt image 1 differs from ROM 3 + hooks',))
        if st['nr'].get(0x8C) != 0x80:
            bad.append(('$8C', st['nr'].get(0x8C)))
        if (0x15, 0x01) not in st['nrlog']:
            bad.append(('sprites not enabled',))
    return bad


def build(z80, out, name, say=print, outline=True):
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, quiet=True)
    bad = boot_check(plain, z80)
    say('Plain     : %s  %s  boot %s' % (os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    patch = YiePatch(outline=outline, colours=load_colours())
    spr = os.path.join(out, name + ('_sprites.nex' if outline else '_noring_sprites.nex'))
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, YiePatch(outline=outline, colours=load_colours()))
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300]))
    return (not bad and not bad2), (plain, spr), patch
