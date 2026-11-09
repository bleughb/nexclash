"""Game Over (Dinamic / Imagine, 1987, 128K, both worlds): clash removal by a Layer 2 figure overlay.

The ULA bitmap stays the original's byte for byte; the attributes shown come from the clean buffer;
figures' ink goes on a double-buffered Layer 2 in plot order. See asm/game_over_hooks.asm.
"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib, json
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/game_over.json'
SOURCE_MD5 = 'e1c2ff3cfbd4f6f5a84034d57b666acf'
CMP = tuple(hooklib.CMP_R)
IMAGE_OFFSET = 0x5C6            # stored code image: bank offset = address - 0x8000 + this
W1, W2 = 1, 2
# site: (address, original CALL/JP target, hook symbol, kind). W1 lives in bank 2 and image bank 4, W2 in image bank 6.
CALLS = {W1: {0xB381: (0xB4EF, 'h_plot1', 'plot'), 0x962B: (0xAF4B, 'h_rest1', 'rest'), 0x966C: (0xAF4B, 'h_copy1', 'copy'),
              0x9FD3: (0xAF06, 'h_cell', 'cell'), 0xA49B: (0xAF06, 'h_cell', 'cell')},
         W2: {0xB3A9: (0xB517, 'h_plot2', 'plot'), 0x9306: (0xAF73, 'h_rest2', 'rest'), 0x9334: (0xAF73, 'h_copy2', 'copy')}}
ATTR_OPERAND = {W1: 0x964E, W2: 0x9329}
CLS = 0xBA63
A_FIRST = 62
RESERVE_TOP_PAGE = 75           # Enhanced's top page with the English sets: the default reserves the same banks without them
# Enhanced only: (site, original bytes, hook, where the original and the hook meet)
ENH_COMMON = [(0xBDC8, bytes.fromhex('6F2600'), 'h_print', 0xBDCB), (0xBA84, bytes.fromhex('E5D113'), 'h_fill', 0xBA87)]
ENH_WORLD = {1: [(0xA33F, bytes.fromhex('21C05D'), 'h_cap1', 0xA342), (0x9973, bytes.fromhex('3E0012'), 'h_z1', 0x9976)],
             2: [(0xA4AA, bytes.fromhex('21C05D'), 'h_cap2', 0xA4AD), (0x97AE, bytes.fromhex('3E0012'), 'h_z2', 0x97B1)]}
IMAGE_BANK = {W1: 4, W2: 6}
SIGNATURE = {0xB381: 'CDEFB4', 0x966C: 'CD4BAF', 0x964D: '21C079', 0xBA63: '3A8F5C'}
DECISIONS = {'figures': 'original bitmap on the ULA; figure ink in its own colour on Layer 2, in plot order',
             'scenery': 'keeps its own attributes', 'pace': 'original; hlib_pace K windows', 'outline': 'none',
             'enhanced': 'a colour set from the player\'s own Spec256 sets on a full-screen double-buffered Layer 2, backdrop on with it; menu option, off by default'}


LOAD_SCREEN = 'game_over_loading.scr'     # the same re-release's 48K-128K tape's 6,912-byte screen, beside the snapshot: game data, never in this repo
LOAD_MD5 = '3cdb0cbbd8b15c7eae4c3d52b7f6b4b5'
PUBLISHER = 'Imagine / Dinamic, 1987'
# Enhanced (rework "enhanced", NEXCLASH_GAME_OVER_ENHANCED=1): the player's own Spec256 sets beside the snapshot,
# under these names; game_over_art turns them into the colour tables at build time. Game data, never in this repo.
ENH_ENV = 'NEXCLASH_GAME_OVER_ENHANCED'
SET_MD5 = {1: 'a09c38625d29b755c1234700943bf703', 2: 'e15865a5b8ea0fab3c56ddc43effc1af'}
# Broken builds the first recording cannot catch: replayed on the recording that reaches the event, if given (a screen
# clear with the panel up comes in world 2: w2full by frame 2,000; w1full and w1b miss it at 4,000).
NEG_ON = {'screen clear not followed': ('w2full.rzx', 2000)}
NEG_STOP = 900                            # frames of the first recording each deliberately broken build replays


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_game_over(snap):
    """The 128K re-release at its first world's code: zt.Z80Snapshot (banks) or skoolkit's Snapshot (memory, nexclash.py auto)."""
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
    name = 'Game Over 128K: clash removed by a Layer 2 figure overlay'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = 0xD000

    def __init__(self, source=None, enabled=True, enhanced=False, backdrop=False, art=None, reserve=False, nobd=False):
        self.source = str(source) if source else None
        self.enabled = enabled
        self.enhanced = enhanced
        self.backdrop = backdrop
        self.art = art
        self.reserve = reserve or enhanced or backdrop or nobd
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.slot1 = (25, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        from .build import rom48
        self.ram = bytearray(rom48()[0x2000:0x4000])
        self.ram[0x800:0x800 + len(self.code)] = self.code
        self.ram[0x700:0x800] = bytes(256)
        self.ram[0x1C00:0x1D00] = bytes(256)
        self.ram[0x1E00:0x2000] = bytes(512)
        self.ram[self.syms['V_BACK'] - 0x2000] = 16
        self.ram[self.syms['V_RECT'] - 0x2000:self.syms['V_RECT'] - 0x2000 + 2] = (0x2700).to_bytes(2, 'little')
        self.ram[self.syms['V_K2'] - 0x2000] = 122 if enhanced else 123
        self.ram[self.syms['V_K1'] - 0x2000] = 123 if enhanced else 125
        # The picture is on with Enhanced unless the "Backdrop off" line takes this byte to 0; only Enhanced's code reads it.
        if (backdrop or not enhanced) and not nobd:
            self.ram[self.syms['V_BDT'] - 0x2000] = 1
        if enhanced:
            self.ram[self.syms['V_ENH'] - 0x2000] = 1
            self.ram[0:len(art['tables'][1])] = art['tables'][1]
            self.ram[0x300:0x300 + len(art['tables'][2])] = art['tables'][2]
            self.ram[0x600:0x610] = art['zxtab'][:16]
            self.ram[self.syms['V_BDP1'] - 0x2000] = 52
            self.ram[self.syms['V_BDP2'] - 0x2000] = 56
            st = bytearray(self.stub_extra)
            st[self.syms['setup_enh'] - self.setup_call + 1] = 1
            at = self.syms['e_palette'] - self.setup_call
            st[at:at + 512] = art['l2pal']
            self.stub_extra = bytes(st)
        self.sites = []
        self.world_sites = {W1: [], W2: []}
        self.site_info = {}
        if enabled:
            for world in (W1, W2):
                for a, (target, sym, kind) in CALLS[world].items():
                    self.world_sites[world].append((a, b'\xcd' + zt.w16(target), b'\xcd' + zt.w16(self.syms[sym])))
                    self.site_info[(world, a)] = (target, sym, kind)
                a = ATTR_OPERAND[world]
                self.world_sites[world].append((a, b'\xc0\x79', b'\xe0\x6a'))
            self.cls_site = (CLS, b'\x3a\x8f\x5c', b'\xc3' + zt.w16(self.syms['h_cls']))
            self.enh_sites = []
            self.enh_info = {}
            for a, old, sym, stop in ENH_COMMON:
                if enhanced or sym == 'h_fill':
                    new = b'\xc3' + zt.w16(self.syms[sym])
                    self.enh_sites.append((a, old, new))
                    self.enh_info[(W1, a)] = self.enh_info[(W2, a)] = (stop, sym)
            for w, L in ENH_WORLD.items():
                for a, old, sym, stop in L:
                    if enhanced or sym.startswith('h_cap'):
                        new = b'\xc3' + zt.w16(self.syms[sym])
                        self.world_sites[w].append((a, old, new))
                        self.enh_info[(w, a)] = (stop, sym)
            self.sites = self.world_sites[W1] + [self.cls_site] + self.enh_sites
        self._banks()

    def _banks(self):
        # Hidden ROM (page 25): tiny entry and return veneers only. Code and writable state: page 24.
        from .build import rom48
        self.page = bytearray(rom48()[0x2000:0x4000])
        for name in ('h_plot1', 'h_plot2', 'h_rest1', 'h_rest2', 'h_copy1', 'h_copy2', 'h_cell', 'h_cls', 'h_print', 'h_fill', 'h_cap1', 'h_cap2', 'h_z1', 'h_z2'):
            at = self.syms[name] - 0x2000
            self.page[at:at + 4] = self.ram[at:at + 4]
        for i in range(len(self.code) - 4):
            if self.code[i:i + 4] == bytes.fromhex('ed9151ff'):
                at = 0x800 + i + 4
                self.page[at:at + 7] = self.ram[at:at + 7]
        self.extra_banks = {12: bytes(self.ram) + bytes(self.page)}
        if self.reserve:
            art = self.art
            top = (art['top_page'] if art else RESERVE_TOP_PAGE) // 2
            if art and min(art['pages']) < 52:
                raise ValueError('asset pages below the listed banks')
            pages = (art['pages'] if (art and self.enhanced) else {})
            for bank in range(26, top + 1):
                self.extra_banks[bank] = pages.get(2 * bank, bytes(8192)) + pages.get(2 * bank + 1, bytes(8192))

    def apply(self, snap):
        if not is_game_over(snap):
            raise ValueError('Not the supported Game Over 128K release (MD5 %s)' % SOURCE_MD5)
        banks = {i: bytearray(snap.banks[i]) for i in range(8)}
        for a, old, new in self.world_sites[W1] + [self.cls_site] + self.enh_sites if self.enabled else []:
            at = a - 0x8000
            if bytes(banks[2][at:at + len(old)]) != old:
                raise ValueError('Original bytes differ at %04X' % a)
            banks[2][at:at + len(new)] = new
        if self.enabled:
            for world in (W1, W2):
                b = banks[IMAGE_BANK[world]]
                for a, old, new in self.world_sites[world]:
                    at = a - 0x8000 + IMAGE_OFFSET
                    if bytes(b[at:at + len(old)]) != old:
                        raise ValueError('Original bytes differ in world %d image at %04X' % (world, a))
                    b[at:at + len(new)] = new
        snap.banks = type(snap.banks)((i, bytes(banks[i])) for i in range(8))


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
        self.world_patched = {}

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
        if m in self.pages:
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
        if m in self.pages:
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
        self.pages = {p: bytearray(b'\xff' * 8192) for p in range(32, 48)}
        if patch.enhanced:
            self.pages.update({p: bytearray(b) for p, b in patch.art['pages'].items()})
        self.nr = {0x12: 16, 0x69: 0x80 if patch.enhanced else 0, 0x17: 0}
        self.line = 0


def run_hook(patch, st, mem, regs, stop_pc, stop_sp=None, limit=8000000, speed=0):
    Sim = _rw()
    v = View(mem, patch, st.page, st.pages)
    s = simpool.machine(Sim, v, list(regs), 'game-over-hook')
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
    for k in (0x12, 0x69, 0x17):
        if k in m.nr:
            st.nr[k] = m.nr[k]
    return list(R), v, m


class Overlay:
    """The expected picture, by an independent reading of the game's own plot state."""
    def __init__(self):
        self.back = {}          # (x, y) -> colour index, sets 0..15 or 'paper marker' 254; absent = transparent
        self.front = {}
        self.fresh = False
        self.paper = set()

    def _clear_if_new(self):
        if self.fresh:
            self.back = {}
            self.paper = set()
            self.fresh = False

    def plot(self, mem, flag_addr):
        self._clear_if_new()
        blk = 0xB342 if flag_addr == 0xB4A6 else 0xB31A
        row0, rows, col, cols, k = mem[blk], mem[blk + 1], mem[blk + 2], mem[blk + 3], mem[blk + 4]
        if not rows:
            return
        w = mem[blk - 5]
        n = w // 2
        src = mem[0xB736] | mem[0xB737] << 8
        shift = mem[0xB735] & 1
        paint = mem[flag_addr] != 0xC9
        attr = mem[0x5C8F]
        ink = (attr & 7) | (8 if attr & 0x40 else 0)
        for r in range(rows):
            g = list(mem[src + r * w + i] for i in range(n))
            m = list(mem[src + r * w + n + i] for i in range(n))
            if shift:
                gg = [0] * (n + 1)
                mm = [0] * (n + 1)
                prev = 0
                for i in range(n):
                    gg[i] = (prev << 4 | g[i] >> 4) & 255
                    prev = g[i] & 15
                gg[n] = (prev << 4) & 255
                prev = 15
                for i in range(n):
                    mm[i] = (prev << 4 | m[i] >> 4) & 255
                    prev = m[i] & 15
                mm[n] = (prev << 4 | 15) & 255
                g, m = gg, mm
            y = row0 + r + 8
            for c in range(cols):
                gb, mb = g[k + c], m[k + c]
                x0 = (col + 1 + c) * 8
                for b in range(8):
                    xy = (x0 + b, y)
                    if gb & (128 >> b):
                        if paint:
                            self.back[xy] = ink
                        else:
                            self.back.pop(xy, None)
                    elif not mb & (128 >> b):
                        if paint:
                            self.back[xy] = 254
                        else:
                            self.back.pop(xy, None)

    def cells(self, mem):
        self._clear_if_new()
        p = mem[0xB736] | mem[0xB737] << 8
        h, w = mem[p], mem[p + 1]
        row, col = mem[0xB734], mem[0xB735]
        for r in range(h):
            for c in range(w):
                a = mem[p + 2 + r * w + c]
                bright = 8 if a & 0x40 else 0
                ink, paper = (a & 7) | bright, ((a >> 3) & 7) | bright
                for yy in range(8):
                    for xx in range(8):
                        xy = ((col + c) * 8 + xx, (row + r) * 8 + 8 + yy)
                        v = self.back.get(xy)
                        if v is None:
                            continue
                        if v == 254:
                            self.paper.add(xy)
                            self.back[xy] = paper
                        else:
                            self.back[xy] = ink


def _flat(sim):
    m = sim.memory
    return bytes(16384) + bytes(m.memory[1]) + bytes(m.memory[2]) + bytes(m.memory[3])


def world_of(mem):
    for w in (W1, W2):
        if mem[0xB381 if w == W1 else 0xB3A9:(0xB381 if w == W1 else 0xB3A9) + 3] == (b'\xcd\xef\xb4' if w == W1 else b'\xcd\x17\xb5'):
            return w
    return None


def verify(patch, rzx_path, stop=None, collect=0, progress=None, compare_every=1):
    """Replay the original; at every changed CALL run the hook on a copy of the state and compare
    with the original's run to its return (or the body entry): every register with R, all 48K RAM
    except the attributes the copy shows, B740 and the dead stack the original's call chain wrote.
    The Layer 2 picture is compared with an independent model at every publication."""
    from .rzx import trace
    from skoolkit.simulator import Simulator
    c = Counter()
    examples = defaultdict(list)
    states = []
    st = State(patch)
    ov = Overlay()
    fronts = {}

    def fail(key, detail):
        c[key + '!'] += 1
        if len(examples[key]) < 5:
            examples[key].append(detail)
    pcs = {a for w in (W1, W2) for a in CALLS[w]} | {CLS}
    enh = EnhModel(patch) if patch.enhanced else None
    pcs |= {a for w, a in patch.enh_info}

    def on_pc(pc, sim):
        mem = _flat(sim)
        regs = list(sim.registers)
        w = world_of(mem)
        info = patch.site_info.get((w, pc)) if w else None
        if (w or W1, pc) in patch.enh_info:
            stop, sym = patch.enh_info[(w or W1, pc)]
            if collect and sum(1 for x in states if x[0] == pc and x[3] == w) < collect:
                states.append((pc, list(regs), bytes(mem), w))
            patched = bytearray(mem)
            for a, o, new in patch.world_sites[w or W1] + [patch.cls_site] + patch.enh_sites:
                patched[a:a + len(new)] = new
            ref = simpool.machine(Simulator, list(mem), regs, 'go-ref')
            sp = regs[12]
            n = 0
            while n == 0 or ref.registers[24] != stop or ref.registers[12] != sp:
                ref.opcodes[ref.memory[ref.registers[24]]]()
                n += 1
            got, v, model = run_hook(patch, st, patched, regs, stop, sp)
            for i in CMP:
                if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                    fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
            expected = bytearray(ref.memory[0x4000:0x10000])
            actual = bytearray(v.mem[0x4000:0x10000])
            for a, o, new in patch.world_sites[w or W1] + [patch.cls_site] + patch.enh_sites:
                expected[a - 0x4000:a - 0x4000 + len(new)] = new
            for a in range(sp - 32, sp):
                expected[a - 0x4000] = actual[a - 0x4000]
            if actual != expected:
                bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
                fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
            if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr.get(0x53, 11) != 11:
                fail('MMU not restored', {'pc': hex(pc), 'sym': sym})
            if model.nr[7] != 0:
                fail('clock differs', {'pc': hex(pc), 'sym': sym})
            if enh:
                enh.event(sym, mem, regs, w or W1)
            c['hooks'] += 1
            c['hooks ' + sym] += 1
            c['R comparisons'] += 1
            return
        if pc == CLS:
            if mem[CLS:CLS + 3] != b'\x3a\x8f\x5c':
                fail('original changed CLS site', {})
            patched = bytearray(mem)
            for a, old, new in patch.world_sites[w or W1] + [patch.cls_site] + patch.enh_sites:
                patched[a:a + len(new)] = new
            ref = simpool.machine(Simulator, list(mem), regs, 'go-ref')
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched, regs, 0xBA66)
            for i in CMP:
                if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                    fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i]})
            if st.nr.get(0x69) != (0x80 if patch.enhanced else 0):
                fail('overlay state wrong at CLS', {})
            c['cls hooks'] += 1
            c['R comparisons'] += 1
            return
        if not info:
            return
        target, sym, kind = info
        call = bytes((0xCD, target & 255, target >> 8))
        if mem[pc:pc + 3] != call:
            fail('site bytes changed', {'pc': hex(pc)})
            return
        if collect and sum(1 for x in states if x[0] == pc and x[3] == w) < collect:
            states.append((pc, regs, mem, w))
        patched = bytearray(mem)
        for a, old, new in patch.world_sites[w] + [patch.cls_site] + patch.enh_sites:
            patched[a:a + len(new)] = new
        if kind == 'copy' and not getattr(patch, 'attr_broken', False):
            patched[0xB740:0xB742] = b'\xe0\x6a'
        ref = simpool.machine(Simulator, list(mem), regs, 'go-ref')
        ret = (pc + 3) & 0xFFFF
        if kind == 'cell':
            ref.opcodes[mem[pc]]()
            got, v, model = run_hook(patch, st, patched, regs, target)
            ov.cells(mem)
        else:
            sp = regs[12]
            n = 0
            R = ref.registers
            while n == 0 or R[24] != ret or R[12] != sp:
                ref.opcodes[ref.memory[R[24]]]()
                n += 1
            if kind == 'plot':
                ov.plot(mem, 0xB47E if w == W1 else 0xB4A6)
            got, v, model = run_hook(patch, st, patched, regs, ret, sp)
        for i in CMP:
            if (bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i]:
                fail('registers differ', {'pc': hex(pc), 'reg': i, 'orig': ref.registers[i], 'got': got[i], 'sym': sym})
        expected = bytearray(ref.memory[0x4000:0x10000])
        actual = bytearray(v.mem[0x4000:0x10000])
        for a, old, new in patch.world_sites[w] + [patch.cls_site] + patch.enh_sites:
            expected[a - 0x4000:a - 0x4000 + len(new)] = new
        # The stack below SP: the original's call chain wrote it, the hook's ran on its own stack.
        sp = regs[12]
        for a in range(sp - 32, sp):
            expected[a - 0x4000] = actual[a - 0x4000]
        if kind == 'copy':
            expected[0xB740 - 0x4000:0xB742 - 0x4000] = b'\xe0\x6a'
            # Attributes shown: the clean buffer's, every byte.
            want = mem[0x6AE0:0x6AE0 + 448]
            shown = bytes(actual[0x5820 - 0x4000:0x5820 - 0x4000 + 448])
            if want != shown:
                fail('copy attributes are not the clean buffer', {'pc': hex(pc)})
            expected[0x5820 - 0x4000:0x5820 - 0x4000 + 448] = shown
        if actual != expected:
            bad = [a + 0x4000 for a, (x, y) in enumerate(zip(expected, actual)) if x != y]
            fail('48K RAM differs', {'pc': hex(pc), 'sym': sym, 'count': len(bad), 'addresses': [hex(x) for x in bad[:8]]})
        if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr.get(0x53, 11) != 11:
            fail('MMU not restored', {'pc': hex(pc)})
        if model.nr[7] != 0:
            fail('clock differs', {'pc': hex(pc), 'value': model.nr[7]})
        if model.io:
            fail('extra game I/O', {'pc': hex(pc), 'io': model.io[:4]})
        if enh:
            enh.hook(kind, mem, w, v, st, c, fail)
            if kind in ('plot', 'copy', 'rest', 'cell'):
                c['hooks'] += 1
                c['hooks ' + kind] += 1
                c['48K bytes compared'] += 49152
                c['R comparisons'] += 1
            return
        if kind == 'rest':
            ov.fresh = True  # a restore wipes the work buffer
        c['hooks'] += 1
        c['hooks ' + kind] += 1
        c['48K bytes compared'] += 49152
        c['R comparisons'] += 1
        if kind == 'copy':
            c['publications'] += 1
            # Front buffer against the independent model, and against the bitmap the copy wrote.
            front = st.nr[0x12]
            work = v.mem
            if st.nr[0x69] != 0x80:
                fail('overlay not on after publish', {})
            lit = 0
            picture = {}
            for y in range(8, 120):
                page = st.pages[front * 2 + (y >> 5)]
                row = (y & 31) << 8
                seg = page[row + 8:row + 248]
                if seg.count(255) == 240:
                    continue
                for xb, val in enumerate(seg):
                    if val != 255 and val != 254:
                        picture[(xb + 8, y)] = val
            want = {} if ov.fresh else {xy: val for xy, val in ov.back.items() if val != 254}
            if picture != want:
                diff = [k for k in set(picture) | set(want) if picture.get(k) != want.get(k)]
                fail('overlay differs from the model', {'pc': hex(pc), 'count': len(diff), 'ex': sorted(diff)[:6]})
            c['overlay pixels compared'] += len(picture)
            # Every pixel lit on Layer 2 is a set bit of the bitmap the copy wrote (screen row, work row).
            shake = mem[0xBF20] if w == W1 else 0
            ref_mem = ref.memory
            for (x, y), val in picture.items():
                if not ov.fresh and (x, y) not in ov.paper and not ref_mem[0x6CA0 + (y - 8) * 30 + (x - 8) // 8] & (128 >> (x & 7)):
                    fail('overlay pixel over a clear bitmap bit', {'x': x, 'y': y, 'frame': pc})
                    break
            ov.front = want
            ov.fresh = True
        if progress and c['hooks'] % 500 == 0:
            progress(c)
    frames, err = trace(str(rzx_path), pcs, on_pc, stop)
    c['frames'] = frames
    if err:
        fail('recording desynced', err)
    return (c, dict(examples), states) if collect else (c, dict(examples))


OPERANDS = (b'\xc0\x79',)


def SCREEN_SITES(patch):
    return [patch.cls_site]


def _patched_mem(patch, mem, w):
    out = bytearray(mem)
    for a, old, new in patch.world_sites[w] + SCREEN_SITES(patch) + patch.enh_sites:
        out[a:a + len(new)] = new
    return out


def unit_tests(patch, states, neg=True):
    """Every hook at the four incoming clocks, both IFF values and eight R phases: registers with R and the clock the
    caller had; the MMU restored. The negative R control is in negative_patches, run by replay."""
    from skoolkit.simulator import Simulator
    c = Counter()
    for pc, regs, mem, w in states:
        if (w or W1, pc) in patch.enh_info:
            target, sym = patch.enh_info[(w or W1, pc)]
            for speed in range(4):
                for iff in (0, 1):
                    for refresh in (0, 127, 128, 255):
                        rr = list(regs)
                        rr[15] = refresh
                        rr[26] = iff
                        ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                        sp = rr[12]
                        n = 0
                        while n == 0 or ref.registers[24] != target or ref.registers[12] != sp:
                            ref.opcodes[ref.memory[ref.registers[24]]]()
                            n += 1
                        st = State(patch)
                        got, v, model = run_hook(patch, st, _patched_mem(patch, mem, w or W1), rr, target, sp, speed=speed)
                        if any((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i] for i in CMP):
                            c['ABI registers differ!'] += 1
                        if model.nr[7] != speed:
                            c['incoming clock not restored!'] += 1
                        if model.nr[0x51] != 255 or model.nr[0x50] != 255 or model.nr.get(0x53, 11) != 11:
                            c['MMU not restored!'] += 1
                        c['ABI cases'] += 1
            continue
        target, sym, kind = patch.site_info[(w, pc)]
        ret = (pc + 3) & 0xFFFF
        for speed in range(4):
            for iff in (0, 1):
                for refresh in (0, 1, 126, 127, 128, 129, 254, 255):
                    rr = list(regs)
                    rr[15] = refresh
                    rr[26] = iff
                    ref = simpool.machine(Simulator, list(mem), rr, 'unit-ref')
                    if kind in ('cell', 'show'):
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
                    got, v, model = run_hook(patch, st, _patched_mem(patch, mem, w), rr, stop, sp, speed=speed)
                    if any((bool(ref.registers[i]) != bool(got[i])) if i == 26 else ref.registers[i] != got[i] for i in CMP):
                        c['ABI registers differ!'] += 1
                    if model.nr[7] != speed:
                        c['incoming clock not restored!'] += 1
                    if model.nr[0x51] != 255 or model.nr[0x50] != 255:
                        c['MMU not restored!'] += 1
                    c['ABI cases'] += 1
    return c


def negative_patches(patch):
    """Deliberately broken builds: every one must fail the replay."""
    import copy
    out = {}

    def mutate(name, old, new, count=0):
        b = copy.deepcopy(patch)
        code = bytes(b.ram[0x800:0x800 + len(b.code)])
        i = code.find(old) if not count else list(_finds(code, old))[count]
        if i < 0:
            raise ValueError('negative %s: pattern not found' % name)
        b.ram[0x800 + i:0x800 + i + len(new)] = new
        b._banks()
        out[name] = b
    mutate('R off by one', bytes((0x3E, 0x100 - 21, 0xCD)), bytes((0x3E, 0x100 - 20)))
    mutate('clock left at 28 MHz', bytes.fromhex('3A303EED9207'), bytes.fromhex('3E0300ED9207'))
    mutate('x off by one column', bytes.fromhex('FD7E023C'), bytes.fromhex('FD7E0200'))
    mutate('wrong ink', bytes.fromhex('E607CB70'), bytes.fromhex('E603CB70'))
    mutate('MMU slot 0 left mapped', bytes.fromhex('ED9150FFDDE1C9'), bytes.fromhex('00000000DDE1C9'))
    mutate('stale figures never cleared', bytes.fromhex('3A373EB7C8AF'), bytes.fromhex('3A373EB7C9AF'))
    mutate('overlay never published', bytes.fromhex('ED926900') if False else bytes.fromhex('ED916980'), bytes.fromhex('ED916900'))
    mutate('overlay not hidden', bytes.fromhex('ED916900'), bytes.fromhex('ED916980'))
    if patch.enhanced:
        for name in ('x off by one column', 'wrong ink', 'stale figures never cleared', 'overlay not hidden', 'MMU slot 0 left mapped'):
            out.pop(name, None)
        mutate('MMU slot 0 left mapped', bytes.fromhex('ED91530BED9150FF'), bytes.fromhex('ED91530B00000000'))

        def ret_at(name, sym):
            b = copy.deepcopy(patch)
            b.ram[b.syms[sym] - 0x2000] = 0xC9
            b._banks()
            out[name] = b
        ret_at('colour figures never drawn', 'e_plot')
        ret_at('picture never restored', 'e_ready')
        ret_at('scene start not followed', 'e_scene')
        ret_at('screen clear not followed', 'e_clear')
        ret_at('prints not followed', 'e_char')
        b = copy.deepcopy(patch)
        b.ram[b.syms['V_BDT'] - 0x2000] ^= 1
        b._banks()
        out['Backdrop line ignored'] = b
        b = copy.deepcopy(patch)
        b.art = dict(b.art)
        b.art['pages'] = dict(b.art['pages'])
        for k in b.art['pages']:
            if k >= A_FIRST:
                page = bytearray(b.art['pages'][k])
                for i in range(len(page)):
                    if page[i] not in (0, 254, 255):
                        page[i] = page[i] ^ 1 or 1
                b.art['pages'][k] = bytes(page)
        b.art_model = patch.art
        out['colour table wrong'] = b
        for sym in ('h_print', 'h_fill'):
            b = copy.deepcopy(patch)
            b.enh_sites = [t if not any(x[0] == t[0] and x[2] == sym for x in ENH_COMMON) else (t[0], t[1], t[1]) for t in b.enh_sites]
            out['%s site left out' % sym] = b
        b = copy.deepcopy(patch)
        for w in (W1, W2):
            b.world_sites[w] = [t if not any(x[0] == t[0] and 'h_cap' in x[2] for x in ENH_WORLD[w]) else (t[0], t[1], t[1]) for t in b.world_sites[w]]
        out['scene capture site left out'] = b
    b = copy.deepcopy(patch)
    for w in (W1, W2):
        b.world_sites[w] = [t if not (t[1][:2] in OPERANDS) else (t[0], t[1], t[1]) for t in b.world_sites[w]]
    b.attr_broken = True
    out['clash left: work attributes shown'] = b
    return out


def _finds(code, old):
    i = code.find(old)
    while i >= 0:
        yield i
        i = code.find(old, i + 1)


def run_negative(b, rzx, stop):
    c, ex = verify(b, rzx, stop=stop)
    return {k: v for k, v in c.items() if k.endswith('!')}


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2), as the published .nxc."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]


def find_screen(z80):
    """The original loading screen beside the snapshot, or None. A different file there is refused."""
    path = Path(z80).resolve().parent / LOAD_SCREEN
    if not path.is_file():
        return None
    data = path.read_bytes()
    if hashlib.md5(data).hexdigest() != LOAD_MD5:
        raise ValueError('%s is not the original loading screen (MD5 %s)' % (LOAD_SCREEN, LOAD_MD5))
    return data


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


def find_art(z80):
    """The colour tables from the two Spec256 sets beside the snapshot (game_over_art), or None without them. A set
    that is not the expected file is refused."""
    from . import game_over_art as A
    d = Path(z80).resolve().parent
    paths = {pt: d / A.SETS[pt] for pt in A.SETS}
    if not all(p.is_file() for p in paths.values()):
        return None
    for pt, p in paths.items():
        if hashlib.md5(p.read_bytes()).hexdigest() != SET_MD5[pt]:
            raise ValueError('%s is not the expected Spec256 set (MD5 %s)' % (p.name, SET_MD5[pt]))
    return A.compile_assets(str(z80), str(d), str(ROOT / 'docs/profiles/game_over_records.json'))


def _patch(z80, mode):
    """mode 'default' (the published default: banks reserved to Enhanced's top), 'enhanced' (with the backdrop) or
    'enhanced_nobd' (the "Backdrop off" line)."""
    if mode == 'default':
        return Patch(z80, reserve=True)
    return Patch(z80, art=find_art(z80), enhanced=True, backdrop=mode == 'enhanced')


def _negative(z80, name, rzx, stop, mode='default'):
    """One deliberately broken build's replay (a process of its own): -> (name, its failure keys)."""
    return name, sorted(run_negative(negative_patches(_patch(z80, mode))[name], rzx, stop))


def auto(a, z80, name, out, say):
    """nexclash.py auto: the sprite build (the overlay), with the loading screen when it is beside the snapshot, each
    boot-checked; with --rzx the replay proof, the ABI cases and the broken builds. With NEXCLASH_GAME_OVER_ENHANCED=1
    and the Spec256 sets beside the snapshot it also writes Enhanced (backdrop on) and Enhanced with "Backdrop off",
    and the replay, ABI cases and broken builds run on Enhanced. The pace, soak, flicker and real loader proofs are the
    review run's (games/game_over.md "Evidence")."""
    import concurrent.futures, os, tempfile
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    from . import rzx as RZ
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    say('Game      : Game Over (Imagine / Dinamic, 1987, 128K, both worlds)')
    say('Engine    : game_over; original bitmap and scenery attributes on the ULA, figures\' ink on a double-buffered Layer 2; original pace')
    ok = True
    modes = [('default', ('Sprites', 'Loading'), '_sprites')]
    vmode = 'default'
    if os.environ.get(ENH_ENV):
        if find_art(z80) is None:
            from . import game_over_art as A
            say('Enhanced  : %s=1 but the Spec256 sets (%s) are not beside the snapshot' % (ENH_ENV, ', '.join(A.SETS.values())))
            say('Result    : FAILED')
            return False
        modes += [('enhanced', ('Enhanced', 'Enh load'), '_enhanced'), ('enhanced_nobd', ('No bd', 'No bd load'), '_enhanced_nobd')]
        vmode = 'enhanced'
    screen = find_screen(z80)
    if screen is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    nexes = []
    for mode, (label, llabel), suffix in modes:
        nex = out / (name + suffix + '.nex')
        zt.convert(str(z80), str(nex), patch=_patch(z80, mode), quiet=True)
        nexes.append((label, nex, mode))
        if screen is not None:
            loading = out / (name + suffix + '_loading.nex')
            loading.write_bytes(loading_nex(nex.read_bytes(), screen))
            nexes.append((llabel, loading, mode))
    for label, nex, mode in nexes:
        bad = boot_check(nex, z80, _patch(z80, mode))
        ok = ok and not bad
        say('%-10s: %s  %s' % (label, nex.name, hashlib.md5(nex.read_bytes()).hexdigest()))
        say('Boot      : %s' % ('simulated, OK (registers with R, all 48K RAM; converter loader and NEXLOAD)' if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    states, replayed = [], []
    with tempfile.TemporaryDirectory(prefix='game_over_') as temp:
        for path in list(getattr(a, 'rzx', None) or []):
            if sum(isinstance(b.obj, Snapshot) for b in parse_rzx(path)) > 1:
                stripped = str(Path(temp) / Path(path).name)
                RZ.strip(path, stripped)
                path = stripped
            replayed.append(path)
            c, ex, got = verify(_patch(z80, vmode), path, stop=getattr(a, 'quick', None), collect=1)
            states += got
            fail = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not fail
            say('Verify    : %s%s %d frames, %d hooks, %d R comparisons, %d Layer 2 pictures, %d pixels: %s' % (
                Path(path).name, ' (Enhanced)' if vmode != 'default' else '', c['frames'], c['hooks'], c['R comparisons'],
                c['publications'], c.get('overlay pixels compared', 0) + c.get('Enhanced pixels compared', 0),
                'IDENTICAL' if not fail else str(fail)))
            for k, v in ex.items():
                say('            %s: %s' % (k, v))
        if states:
            counts = unit_tests(_patch(z80, vmode), states)
            fail = {k: v for k, v in counts.items() if k.endswith('!')}
            ok = ok and not fail
            say('Unit      : %s' % dict(counts))
            names = list(negative_patches(_patch(z80, vmode)))
            with concurrent.futures.ProcessPoolExecutor(min(len(names), os.cpu_count() or 1)) as pool:
                byname = {Path(p).name: p for p in replayed}
                rzxs = [byname.get(NEG_ON.get(n, ('',))[0], replayed[0]) for n in names]
                stops = [NEG_ON[n][1] if n in NEG_ON and NEG_ON[n][0] in byname else NEG_STOP for n in names]
                done = list(pool.map(_negative, [z80] * len(names), names, rzxs, stops, [vmode] * len(names)))
            missed = [n for n, keys in done if not keys]
            ok = ok and not missed
            say('Negatives : %d of %d broken builds caught%s' % (len(done) - len(missed), len(done), '; MISSED %s' % missed if missed else ''))
        else:
            say('Verify    : not requested; boot evidence only')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)


class EnhModel:
    """The expected Enhanced picture, independent of the hooks' rectangles: the clean picture when a pass begins plus that
    pass's plots in order; the panel from the prints; all from the game's own state and the colour tables."""
    def __init__(self, patch):
        self.patch = patch
        self.art = getattr(patch, 'art_model', patch.art)
        self.c = bytearray(b'\xff' * (128 * 256))
        self.pic = None
        self.panel = bytearray(b'\xff' * (192 * 256))
        self.scene = False
        self.play = False
        self.fresh = True
        self.bd = patch.backdrop
        self.zx = self.art['zxtab']
        self.room = 0

    def bdpixel(self, w, y, x):
        if not self.bd or (w == W2 and self.room >= 5):
            return 0
        return self.art['pages'][(52 if w == W1 else 56) + (y >> 5)][(y & 31) * 256 + x]

    def event(self, sym, mem, regs, w):
        self.room = mem[0xBE70]
        if sym == 'h_print':
            self.char(regs[0], mem, w)
        elif sym == 'h_fill':
            hl = regs[7] | regs[6] << 8
            bc = regs[3] | regs[2] << 8
            if hl == 0x4000:
                self.panel = bytearray(b'\xff' * (192 * 256))
                self.scene = self.play = False
                self.fresh = True
                self.wiped = True
            elif hl == 0x5DC0 and bc == 0x1DC0:
                self.scene, self.play = True, False
                for y in range(8, 120):
                    for x in range(8, 248):
                        self.c[y * 256 + x] = self.bdpixel(w, y, x)
        elif sym.startswith('h_cap'):
            self.scene, self.play = False, True
            self.fresh = True
        elif sym.startswith('h_z'):
            de = regs[5] | regs[4] << 8
            if de < 0x5800:
                y = ((de >> 8) & 7) | ((de >> 5) & 0x38 & 0xFF if False else 0)
                y = (((de >> 8) & 0x18) << 3) | ((de & 0xE0) >> 2) | ((de >> 8) & 7)
                x = (de & 31) * 8
                self.panel[y * 256 + x:y * 256 + x + 8] = b'\xff' * 8
                self.touched = True

    def char(self, a, mem, w):
        if a >= 128:
            return
        font = mem[0xB907] | mem[0xB908] << 8
        fw = {0xAAEF: 1, 0xA977: 2}.get(font)
        row, col = mem[0xB79D], mem[0xB79E]
        if not fw or row >= 24 or col >= 32:
            return
        if self.play and 0 < row < 15 and 0 < col < 31:
            return
        glyph = bytes(mem[font + a * 8 + i] for i in range(8))
        cell = bytes(mem[0x4000 | ((row & 0x18) << 8) | (i << 8) | ((row & 7) << 5) | col] for i in range(8))
        if glyph == cell:
            return
        f = self.art['fonts'][fw]
        for r in range(8):
            for b in range(8):
                v = f[a * 64 + r * 8 + b]
                self.panel[(row * 8 + r) * 256 + col * 8 + b] = 255 if v >= 254 else v

    def begin(self):
        if self.fresh:
            self.pic = bytearray(self.c)
            self.fresh = False

    def plot(self, mem, w):
        iy = 0xB31A if w == W1 else 0xB342
        flag = 0xB47E if w == W1 else 0xB4A6
        row0, rows, col, cols, k = mem[iy], mem[iy + 1], mem[iy + 2], mem[iy + 3], mem[iy + 4]
        if not rows:
            return
        self.room = mem[0xBE70]
        if not self.scene:
            self.begin()
        wd = mem[iy - 5]
        src = mem[0xB736] | mem[0xB737] << 8
        skip = (row0 - mem[0xB734]) & 255
        p = (src - 2 - skip * wd) & 0xFFFF
        shift = mem[0xB735] & 1
        attr = mem[0x5C8F] if mem[flag] != 0xC9 else 7
        ink = self.zx[(attr & 7) | (8 if attr & 0x40 else 0)]
        r = self.art['built'][w].get(p)
        if r is None:
            return
        target = self.c if self.scene else self.pic
        stride = r['nb'] * 8
        st = r['stream']
        sx = k * 8 - (4 if shift else 0)
        pad = 0
        if sx < 0:
            pad, sx = 4, 0
        count = min(cols * 8 - pad, stride - sx)
        dx = (col + 1) * 8 + pad
        for row in range(rows):
            y = row0 + row + 8
            base = (skip + row) * stride + sx
            for i in range(count):
                v = st[base + i]
                if v == 0:
                    continue
                if v == 254:
                    target[y * 256 + dx + i] = self.bdpixel(w, y, dx + i) if self.scene else 0
                else:
                    target[y * 256 + dx + i] = ink if v == 255 else v

    def hook(self, kind, mem, w, v, st, c, fail):
        if kind == 'plot':
            self.plot(mem, w)
        elif kind == 'rest':
            self.fresh = True
        elif kind == 'copy':
            self.begin()
            self.scene = False
            bank = st.nr[0x12]
            bad, first = 0, None
            for y in range(8, 120):
                page = st.pages[bank * 2 + (y >> 5)]
                got = page[(y & 31) * 256 + 8:(y & 31) * 256 + 248]
                want = self.pic[y * 256 + 8:y * 256 + 248]
                if got != want:
                    for x, (a, b) in enumerate(zip(got, want)):
                        if a != b:
                            bad += 1
                            if first is None:
                                first = (x + 8, y, a, b)
            if bad:
                fail('Enhanced picture differs from the model', {'count': bad, 'first': first, 'pub': c['publications'], 'world': w, 'bank': bank})
            pb = 0
            ex = None
            for bk in (16, 19):
                for y in range(192):
                    page = st.pages[bk * 2 + (y >> 5)]
                    row = page[(y & 31) * 256:(y & 31) * 256 + 256]
                    want = self.panel[y * 256:y * 256 + 256]
                    if 8 <= y < 120:
                        row, want = row[:8] + row[248:], want[:8] + want[248:]
                    if row != want:
                        pb += 1
                        ex = ex or (bk, y, [i for i, (a, b) in enumerate(zip(row, want)) if a != b][:4])
            if pb:
                fail('Enhanced panel differs from the model', {'rows': pb, 'pub': c['publications'], 'ex': ex})
            if st.nr.get(0x69) != 0x80:
                fail('overlay not on', {})
            c['publications'] += 1
            c['Enhanced pictures compared'] += 1
            c['Enhanced pixels compared'] += 240 * 112
            self.fresh = True
