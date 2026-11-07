"""Beyond the Ice Palace 128K (Elite, 1988): original-colour clash fix, the figures as hardware sprites.

Hooks record each visible original plot (figure plotter 0xBEE6, projectile plotter 0xBD9F) and, at the
screen copy 0x6C03, upload the completed back-buffer bitmap of each figure through the original masks
as sprites in the figure's original ink; scenery attributes come from a clean background pass. Original
drawing and collision buffers, sound and gameplay are unchanged. The hook bytes come from the profile
(asm/ice_palace_hooks.asm, tools/asm2profile.py); the masks are built at build time by running the
game's own initialisers and plotters on the player's snapshot: no game graphics are stored here.

Ported from Jon Attree's private review build (2026-11-06, base bd1528c): the build is byte-identical
(sprite build with the tape's loading screen d53ac5f52471b674354caf96cd94221e). Its verifiers are the
pilot's work/verify.py (paired calls), work/visual_check.py (pixel oracle), work/units.py and
work/boot_check.py, moved here unchanged in what they compare. Cheats: a .pok beside the .z80 (nxcout).
"""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import copy
import hashlib
import json
import os
from . import z80tonex as zt
from . import hooklib, simpool

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/ice_palace.json'
SOURCE_MD5 = '1c1af4775bc0114f7b94edb7de2d4070'
LOADING = 'beyond_the_ice_palace.scr'   # the tape's loading screen, beside the snapshot (record input)
SITES = {0x7407: (0xBEE6, 'player'), 0x7457: (0xBEE6, 'player'), 0x7C9A: (0xBEE6, 'enemy'),
         0x8ECE: (0xBD9F, 'projectile'), 0x6B36: (0x6C03, 'copy_play'),
         0x79CF: (0x6C03, 'copy_death'), 0x94D9: (0x6C03, 'copy_other')}
RESET = (0x91E4, bytes.fromhex('06181800'))         # LD B,24 / JR $+2 -> JP reset / NOP
COPIES = (0x6B36, 0x79CF, 0x94D9)
PLOTS = (0x7407, 0x7457, 0x7C9A, 0x8ECE)
# Bytes inside a patched instruction: the original must never jump there. 0x91E6 (the JR) follows the
# site's own LD B,24: those runs are counted against the site's (SEQUELS, ENGINE_CONTRACT verify loop).
INTERIORS = sorted({a + k for a in SITES for k in (1, 2)} | {RESET[0] + k for k in (1, 2, 3)})
SEQUELS = {0x91E6: 0x91E4}
CMP = tuple(sorted(hooklib.CMP_R + [24]))           # every register, R and PC included; not T / MEMPTR
DECISIONS = {'figures': 'player, enemies, projectiles: sprites in their original ink (original masks)',
             'scenery': 'ULA bitmap unchanged; attributes from a clean background pass',
             'pace': 'ORIGINAL (hlib_pace, the first library: HLIB_PACE_V1)', 'outline': 'none', 'enhanced': 'none'}


def load_profile():
    return json.loads(PROFILE.read_text())


def _peek(snap):
    banks = getattr(getattr(snap, 'memory', None), 'banks', None) or getattr(snap, 'banks', None)
    return lambda a: banks[{1: 5, 2: 2, 3: 0}[a >> 14]][a & 0x3FFF]


def is_ice_palace(snap):
    """The Elite 128K release: 128K machine and every patch site holding its original bytes."""
    if getattr(snap, 'machine', '48K') == '48K':
        return False
    try:
        peek = _peek(snap)
        sites = [(a, b'\xcd' + zt.w16(body)) for a, (body, _) in SITES.items()] + [RESET]
        return all(bytes(peek(a + k) for k in range(len(o))) == o for a, o in sites)
    except (TypeError, IndexError, KeyError):
        return False


@lru_cache(maxsize=2)
def make_masks(source):
    """Extract masks by executing the game's own initialisers and plotters.
    All 32-row and 16-row IDs, both directions and both four-pixel phases.
    The black/white comparison includes only the original masked footprint.
    """
    from skoolkit import CSimulator
    from skoolkit.snapshot import Snapshot
    from .simrun import addr_view
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Use the verified Elite 128K source, MD5 ' + SOURCE_MD5)
    base = addr_view(Snapshot.get(str(source)))
    base[0xff00:0xff02] = [0, 0]
    for pc in (0xe0d9, 0xe0e9):
        s = CSimulator(list(base), {'PC': pc, 'SP': 0xff00}, {'iff': 0})
        s.run(stop=0)
        base = list(s.memory)
    base[0x6dae:0x6db2] = [0] * 4
    out = bytearray()
    for family, total in [(0xbee6, 64), (0xbd9f, 32)]:
        for flip in (0, 128):
            for idx in range(total):
                for phase in (0, 4):
                    if idx >= (50 if family == 0xbee6 else 14):
                        out.extend(bytes([255]) * 512)
                        continue
                    images = []
                    for fill in (0, 255):
                        m = list(base)
                        m[0xe400:0xf600] = [fill] * 0x1200
                        s = CSimulator(m, {'PC': family, 'SP': 0xff00, 'A': idx | flip, 'HL': 64 + phase, 'DE': 32}, {'iff': 0})
                        s.run(stop=0)
                        images.append(bytes(s.memory[0xe400 + (32 + y) * 32 + 8 + x] for y in range(32) for x in range(4)))
                    mask = bytes(a | (~b & 255) for a, b in zip(*images))
                    for qy, qx in [(0, 0), (0, 16), (16, 0), (16, 16)]:
                        for y in range(qy, qy + 16):
                            for x in range(qx, qx + 16, 2):
                                n = [0 if mask[y * 4 + (x + k) // 8] & (128 >> ((x + k) & 7)) else 15 for k in (0, 1)]
                                out.append(n[0] * 16 + n[1])
    return bytes(out)


class Patch:
    name = 'Beyond the Ice Palace: original colours, clash fix v1.0'
    uses_printer_buffer = False
    tail_addr = 0x5b00
    max_tail = 128
    stub_extra = b''
    setup_call = None
    hook_page_data = b''

    def __init__(self, source, enabled=True):
        h = load_profile()['hooks']
        self.rom = bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.slot1 = (24, self.syms['regblock'])
        self.altrom = (0x2800, self.syms['rom_end'])
        self.altrom0 = self.altrom
        masks = make_masks(str(source))
        self.extra_banks = {16 + i: masks[i * 16384:(i + 1) * 16384].ljust(16384, b'\xff')
                            for i in range((len(masks) + 16383) // 16384)}
        scratch = bytearray(16384)
        for v in range(256):
            for k in range(4):
                scratch[0x1800 + v * 4 + k] = ((v >> (7 - k * 2)) & 1) * 16 + ((v >> (6 - k * 2)) & 1)
        for index in range(len(masks) // 512):
            scratch[0x1600 + index] = sum((1 << q) for q in range(4)
                                          if masks[index * 512 + q * 128:index * 512 + (q + 1) * 128] != bytes([255]) * 128)
        self.extra_banks[13] = bytes(scratch)
        self.sites = [(a, b'\xcd' + zt.w16(body), b'\xcd' + zt.w16(self.syms[label]))
                      for a, (body, label) in SITES.items()] if enabled else []
        if enabled:
            self.sites.append((RESET[0], RESET[1], b'\xc3' + zt.w16(self.syms['reset']) + b'\x00'))

    def apply(self, snap):
        assert snap.is128 and snap.port7ffd == 0x10
        rom = bytearray(self.rom)
        off = lambda name: self.syms[name] - 0x2800
        rom[off('printer_saved'):off('printer_saved') + 256] = snap.banks[5][0x1b00:0x1c00]
        rom[off('boot_jump') + 1:off('boot_jump') + 3] = zt.w16(snap.pc)
        rom[off('boot_iff')] = 0xfb if snap.iff1 else 0
        # Sprite palette: each bank has opaque black and the figure's original ink.
        ula_palette = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6,
                       0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
        for colour, value in enumerate(ula_palette):
            rom[off('palette') + colour * 16 + 1] = value
        page = bytearray(8192)
        page[0x800:0x800 + len(rom)] = rom
        self.extra_banks[12] = bytes(page) + bytes(8192)
        self.rom = bytes(rom)
        snap.pc = self.syms['boot_resume']
        banks = {b: bytearray(v) for b, v in snap.banks.items()}
        for a, old, new in self.sites:
            b = 5 if a < 0x8000 else 2 if a < 0xc000 else 0
            o = a & 0x3fff
            assert banks[b][o:o + len(old)] == old, hex(a)
            banks[b][o:o + len(new)] = new
        snap.banks = {b: bytes(v) for b, v in banks.items()}


def loading_nex(nex, scr):
    """The NEX's own loading screen (header byte 10 = 2: a ULA screen after the header)."""
    if len(scr) != 6912:
        raise ValueError('Loading screen must be 6912 bytes')
    b = bytearray(nex)
    assert b[10] == 0
    b[10] = 2
    return bytes(b[:512] + scr + b[512:])


def build(source, destination, loading=None):
    """Rebuild using only the clean source snapshot, the profile and optional SCR."""
    zt.convert(str(source), str(destination), patch=Patch(source))
    if loading:
        Path(destination).write_bytes(loading_nex(Path(destination).read_bytes(), Path(loading).read_bytes()))


# ---- verification (pilot work/verify.py, visual_check.py, units.py, boot_check.py) ----------------------------

_SIM = []


def _sim():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


class View:
    def __init__(self, get, p, scratch):
        self.get = get
        self.p = p
        self.scratch = scratch
        self.ov = {}
        self.ns = None
        self.sites = {a + i: v for a, o, n in p.sites for i, v in enumerate(n)} if p else {}

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if self.p:
            if a < 0x2000 and self.ns.nr.get(0x50) == 26:
                return self.scratch[a]
            if 0x2800 <= a < self.p.syms['rom_end']:
                return self.p.rom[a - 0x2800]
            if 0xA000 <= a < 0xC000 and self.ns.nr.get(0x55, 5) != 5:
                page = self.ns.nr[0x55]
                return self.p.extra_banks[page // 2][(page % 2) * 8192 + (a & 8191)]
            if a in self.sites:
                return self.sites[a]
        return self.ov.get(a, self.get(a))

    def __setitem__(self, a, v):
        if a < 0x2000 and self.p and self.ns.nr.get(0x50) == 26:
            self.scratch[a] = v
        elif a >= 0x4000:
            self.ov[a] = v


class Model(hooklib.NextModel):
    def __init__(self, sim, speed):
        super().__init__(sim, speed, t_line=228, lines=311)
        self.nr.update({0x50: 255, 0x55: 5})
        self.io = []

    def write_port(self, regs, port, v, *args):
        if port in (0x243b, 0x253b, 0x303b) or port & 255 in (0x57, 0x5b):
            super().write_port(regs, port, v, *args)
        else:
            self.io.append((port, v))


def runone(get, regs, p, scratch, speed, slot, previous=None):
    """One call, original (p None) or patched, to its return; -> (registers, memory view, Next model)."""
    v = View(get, p, scratch)
    s = simpool.machine(_sim(), v, list(regs), slot)
    n = Model(s, speed)
    v.ns = n
    if previous:
        n.attrs = [list(a) for a in previous.attrs]
        n.pattern[:] = previous.pattern
        n.nr[0x15] = previous.nr.get(0x15, 0)
    stop = regs[24] + (4 if regs[24] == RESET[0] else 3)
    sp = regs[12]
    r = s.registers
    c = 0
    while c == 0 or r[24] != stop or r[12] != sp:
        s.opcodes[v[r[24]]]()
        c += 1
        if c > 2500000:
            raise RuntimeError(('no return', hex(regs[24]), hex(r[24])))
    return list(r), v, n


def pair(mem, regs, p, scratch, speed=0):
    """Original and patched call from one state: registers (R too), NextREGs 7 / 0x50 / 0x55 back, memory
    outside the sites, the dead stack and (copier) the attribute rows, and the original's I/O."""
    get = mem.__getitem__
    ro, vo, no = runone(get, regs, None, bytearray(scratch), speed, 'original')
    rp, vp, np = runone(get, regs, p, scratch, speed, 'patched')
    bad = []
    for k in CMP:
        if ro[k] != rp[k]:
            bad.append(('register', k, ro[k], rp[k]))
    for k, want in [(7, speed), (0x50, 255), (0x55, 5)]:
        if np.nr[k] != want:
            bad.append(('nextreg', k, want, np.nr[k]))
    excluded = {a + i for a, o, n in p.sites for i in range(len(n))}
    excluded.update(range(max(0, regs[12] - 128), regs[12]))
    if regs[24] in COPIES:
        excluded.update(range(0x5900, 0x5b00))
    for a in vo.ov.keys() | vp.ov.keys():
        if a not in excluded and vo[a] != vp[a]:
            bad.append(('memory', hex(a), vo[a], vp[a]))
    if no.io != np.io:
        bad.append(('io', no.io, np.io))
    return bad, {'original_T': ro[25] - regs[25], 'patched_real_T': np.now(), 'sprite_count': scratch[0x1016],
                 'overflow': scratch[0x1017]}, np


def original_mask(mem, regs):
    """Independent pixel oracle: the original plotter on black and white buffers (no hook table used)."""
    views = []
    for fill in [0, 255]:
        def get(a, fill=fill):
            return fill if 0xe400 <= a < 0xf600 else mem[a]
        _, v, _ = runone(get, regs, None, bytearray(8192), 0, 'mask' + str(fill))
        views.append(v)
    v0, v1 = views
    return {a: v0[a] | (~v1[a] & 255) for a in v0.ov.keys() | v1.ov.keys() if 0xe400 <= a < 0xf600 and (v0[a] | (~v1[a] & 255))}


def layer(ns):
    """The sprite layer the model shows: {(x, y): colour}, inside the play window."""
    out = {}
    if not ns.nr.get(0x15, 1) & 1:
        return out
    for a in ns.attrs:
        if not a[3] & 128:
            continue
        assert a[4] & 128
        off = ((a[3] & 63) * 2 + ((a[4] >> 6) & 1)) * 128
        x = a[0] + ((a[2] & 1) << 8) - 32
        y = a[1] - 32
        col = a[2] >> 4
        for i, b in enumerate(ns.pattern[off:off + 128]):
            for j, n in enumerate([b >> 4, b & 15]):
                xx = x + (i * 2 + j) % 16
                yy = y + (i * 2 + j) // 16
                if 16 <= xx < 240 and 64 <= yy < 192 and n != 15:
                    out[xx, yy] = col if n else 0
    return out


def expected_layer(mem, objects):
    out = {}
    cy = mem[0x6db0] & 15
    for mask, col in objects:
        for a, v in mask.items():
            y = (a - 0xe400) // 32 - cy + 64
            x = ((a - 0xe400) % 32) * 8
            for bit in range(8):
                if v & (128 >> bit) and 16 <= x + bit < 240 and 64 <= y < 192:
                    out[x + bit, y] = col if mem[a] & (128 >> bit) else 0
    return out


def colour(mem, r):
    if r[24] == 0x8ece:
        return 6
    if r[24] != 0x7c9a:
        return 15
    ix = r[8] * 256 + r[9]
    a = mem[0x9f1e + (mem[ix] & 127)]
    if mem[ix + 12] & 4:
        a = mem[0x9a06] & 7 | 64
    return (a & 7) | ((a & 64) >> 3)


def _hex(pc):
    return '%04X' % pc


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Two replays of the recording (rzx.trace). Pass 1, paired calls: at every site the original and the patched
    call from the same state (pair): registers with R, NextREGs back, memory, original I/O; jumps into a patched
    instruction, a site's bytes rewritten. Pass 2, pixel oracle: after each screen copy the sprite layer against the
    original plotter's own pixels on black / white buffers for every figure drawn since; wrong-x negative control;
    overflow and unknown figure IDs. -> (Counter, examples, states {pc: (memory, registers, scratch)})."""
    from . import rzx
    p = patch
    c = Counter()
    ex = []
    states = {}
    originals = [(a, old) for a, old, _ in p.sites]

    def fail(key, what):
        c[key] += 1
        if len(ex) < 5:
            ex.append((key, what))

    scratch = bytearray(p.extra_banks[13][:8192])
    seq = Counter()

    def hit(pc, s):
        if pc in SEQUELS.values():
            seq[pc] += 1
        if pc in INTERIORS:
            if pc in SEQUELS and seq[SEQUELS[pc]] > 0:
                seq[SEQUELS[pc]] -= 1
                c['sequel %s' % _hex(pc)] += 1
            else:
                fail('jump into a patched instruction!', hex(pc))
            return
        m = s.memory
        for a, old in originals:
            if any(m[a + k] != v for k, v in enumerate(old)):
                fail('site bytes rewritten by the game!', hex(a))
        regs = list(s.registers)
        if collect and pc not in states:
            states[pc] = ([m[i] for i in range(65536)], regs, bytes(scratch))
        bad, info, _ = pair(m, regs, p, scratch)
        c['hook ' + _hex(pc)] += 1
        if bad:
            fail('call differs!', (hex(pc), bad[:12]))
        if progress and sum(v for k, v in c.items() if k.startswith('hook ')) % 5000 == 0:
            progress('paired calls %d' % sum(v for k, v in c.items() if k.startswith('hook ')))

    frames, err = rzx.trace(str(rzx_path), [a for a, _, _ in p.sites] + INTERIORS, hit, stop=stop)
    c['frames'] = frames
    if err:
        fail('replay desynced!', err)

    # pass 2: the pixel oracle
    scratch = bytearray(p.extra_banks[13][:8192])
    objects = []
    st = {'previous': None, 'negative': False}

    def look(pc, s):
        r = list(s.registers)
        if pc in PLOTS:
            m = original_mask(s.memory, r)
            if m:
                objects.append((m, colour(s.memory, r)))
        _, _, ns = runone(s.memory.__getitem__, r, p, scratch, 0, 'visual', st['previous'])
        st['previous'] = ns
        for k, v in ns.c.items():
            c['model ' + k] += v
        if pc == RESET[0]:
            objects.clear()
        if pc in COPIES:
            want = expected_layer(s.memory, objects)
            got = layer(ns)
            c['layer checks'] += 1
            c['layer pixels'] += len(want)
            diff = [(xy, want.get(xy), got.get(xy)) for xy in want.keys() | got.keys() if want.get(xy) != got.get(xy)]
            if diff:
                fail('sprite layer differs from the original plot!', (hex(pc), len(diff), diff[:4]))
            if want and not st['negative']:
                ns.attrs[0][0] += 1
                st['negative'] = layer(ns) != want
                ns.attrs[0][0] -= 1
            objects.clear()

    frames2, err = rzx.trace(str(rzx_path), [a for a, _, _ in p.sites], look, stop=stop)
    if err:
        fail('replay desynced (pixel pass)!', err)
    if c['layer pixels'] and not st['negative']:
        fail('negative control (sprite x + 1) NOT DETECTED!', '')
    c['negative wrong x detected'] = int(st['negative'])
    c['peak quadrants'] = scratch[0x102a]
    if scratch[0x1017]:
        fail('quadrant overflow!', scratch[0x1017])
    if scratch[0x1031]:
        fail('unknown figure ID!', scratch[0x1031])
    return c, ex, states


def unit_tests(patch, states, neg=None):
    """What the recordings do not reach: every site at the four incoming clocks (0x79CF from a copier state), every
    figure ID x mirror x phase of both plotters and the viewport edges against the oracle; eight broken builds
    (their own hook code and tables): R, speed, MMU, position, missing mask, missing reset, one pattern buffer, no
    limiter. states: verify's, merged over the recordings. -> (Counter, failures)."""
    p = patch
    c = Counter()
    errors = []
    for pc, old, new in p.sites:
        m, r, sc = states.get(pc, states[0x6b36] if pc in COPIES else states[0x7457])
        r = list(r)
        r[24] = pc
        for speed in range(4):
            scratch = bytearray(p.extra_banks[13][:8192])
            scratch[0x200:0x600] = sc[0x200:0x600]
            scratch[0x1000:0x1500] = sc[0x1000:0x1500]
            bad, info, ns = pair(m, r, p, scratch, speed)
            c['clock cases'] += 1
            if bad:
                errors.append((hex(pc), speed, bad[:4]))
    m, r, sc = states[0x7457]
    r = list(r)
    m = list(m)
    m[0x6dae:0x6db2] = [0] * 4
    copyr = list(states[0x6b36][1])
    copyr[24] = 0x6b36
    tests = []
    for pc, ids in [(0x7457, range(50)), (0x8ece, range(14))]:
        for a in ids:
            for flip in [0, 128]:
                for phase in [0, 4]:
                    tests.append((pc, a | flip, 64 + phase, 32))
        for x, y in [(-1, 32), (0, 32), (238, 32), (239, 32), (255, 32), (256, 32)] + \
                [(64, y) for y in [-33, -32, -31, -16, -15, -2, 0, 96, 112, 126, 127, 128, 232, 255, 256]]:
            tests.append((pc, 2, x, y))
    for pc, a, x, y in tests:
        rr = list(r)
        rr[24] = pc
        rr[0] = a
        rr[6] = x >> 8 & 255
        rr[7] = x & 255
        rr[4] = y >> 8 & 255
        rr[5] = y & 255
        scratch = bytearray(p.extra_banks[13][:8192])
        mask = original_mask(m, rr)
        _, v, _ = runone(m.__getitem__, rr, p, scratch, 0, 'unitdraw')
        _, _, ns = runone(v.__getitem__, copyr, p, scratch, 0, 'unitcopy')
        want = expected_layer(v, [(mask, 15 if pc == 0x7457 else 6)])
        c['pixel cases'] += 1
        if want != layer(ns):
            errors.append((hex(pc), a, x, y))
    # Deliberate broken variants, using their own hook code and tables.
    negatives = {}
    m, r, sc = states[0x7457]
    broken = copy.deepcopy(p)
    code = bytearray(broken.rom)
    at = code.index(bytes.fromhex('3ef1cd'))
    code[at + 1] = 0xf2
    broken.rom = bytes(code)
    bad, _, _ = pair(m, r, broken, bytearray(broken.extra_banks[13][:8192]))
    negatives['wrong_R'] = any(v[0] == 'register' and v[1] == 15 for v in bad)
    for name, hexold in [('wrong_speed', 'ed9207'), ('wrong_MMU', 'ed9250')]:
        # the register target mutated in place (same length): the old resource is never restored
        broken = copy.deepcopy(p)
        code = bytearray(broken.rom)
        at = code.index(bytes.fromhex(hexold), p.syms['player'] - 0x2800)
        code[at + 2] = 0x06 if name == 'wrong_speed' else 0x51
        broken.rom = bytes(code)
        bad, _, _ = pair(m, r, broken, bytearray(broken.extra_banks[13][:8192]))
        negatives[name] = bool(bad)
    rr = list(r)

    def draw_copy(q):
        sc = bytearray(q.extra_banks[13][:8192])
        _, v, ns = runone(m.__getitem__, rr, q, sc, 0, 'negdraw')
        _, _, ns = runone(v.__getitem__, copyr, q, sc, 0, 'negcopy', ns)
        return ns, sc, expected_layer(v, [(original_mask(m, rr), 15)])
    for name in ['wrong_position', 'missing_mask']:
        q = copy.deepcopy(p)
        if name == 'wrong_position':
            code = bytearray(q.rom)
            code[q.syms['quadrant.sprite_x_offset'] - 0x2800 + 1] = 33
            q.rom = bytes(code)
        else:
            bank = bytearray(q.extra_banks[13])
            bank[0x1600:0x1780] = bytes(384)
            q.extra_banks[13] = bytes(bank)
        ns, sc, want = draw_copy(q)
        negatives[name] = layer(ns) != want
    ns, sc, want = draw_copy(p)
    q = copy.deepcopy(p)
    code = bytearray(q.rom)
    off = code.index(bytes.fromhex('ed911500'), q.syms['reset'] - 0x2800)
    code[off + 3] = 1
    q.rom = bytes(code)
    reset_r = list(states[RESET[0]][1])
    reset_m = states[RESET[0]][0]
    _, _, good = runone(reset_m.__getitem__, reset_r, p, bytearray(sc), 0, 'goodreset', ns)
    _, _, bad = runone(reset_m.__getitem__, reset_r, q, bytearray(sc), 0, 'badreset', ns)
    negatives['missing_reset'] = not layer(good) and bool(layer(bad))
    q = copy.deepcopy(p)
    code = bytearray(q.rom)
    at = code.index(bytes.fromhex('ee40'), q.syms['prepare'] - 0x2800)
    code[at + 1] = 0
    q.rom = bytes(code)
    ns, sc, _ = draw_copy(q)
    _, v, ns = runone(m.__getitem__, rr, q, sc, 0, 'negdraw2', ns)
    _, _, ns = runone(v.__getitem__, copyr, q, sc, 0, 'negcopy2', ns)
    negatives['one_pattern_buffer'] = ns.c['upload into a shown pattern!'] > 0
    m, r, sc = states[0x6b36]
    q = copy.deepcopy(p)
    code = bytearray(q.rom)
    code[q.syms['hlib_pace_wait'] - 0x2800] = 0xc9
    q.rom = bytes(code)
    _, good, _ = pair(m, r, p, bytearray(sc))
    _, bad, _ = pair(m, r, q, bytearray(sc))
    negatives['missing_limiter'] = bad['patched_real_T'] < good['patched_real_T'] * .8
    for k, v in negatives.items():
        c['negative %s %s' % (k, 'detected' if v else 'NOT DETECTED!')] += 1
    if errors:
        c['unit case differs!'] += len(errors)
    return c, errors[:10]


def boot_check(nex, z80, patch):
    """The start-up tail, with and without NEXLOAD's printer buffer: every register (R too) and all RAM
    0x4000-0xFFFF as the snapshot has them at its PC. -> [(nexload, bad count, examples)]."""
    from . import nextboot
    from skoolkit import CSimulator
    from skoolkit.snapshot import Snapshot
    from skoolkit.simutils import from_snapshot
    s = zt.Z80Snapshot(str(z80))
    pc = s.pc
    patch.apply(s)
    expected = from_snapshot(CSimulator, Snapshot.get(str(z80))).registers
    out = []
    for nl in (False, True):
        st = nextboot.boot(str(nex), pc, nexload=nl)
        bad = [('reg', i, expected[i], st['R'][i]) for i in hooklib.CMP_R if expected[i] != st['R'][i]]
        for a in range(0x4000, 65536):
            bank = 5 if a < 0x8000 else 2 if a < 0xc000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', hex(a), s.banks[bank][a & 16383], st['mem'][a]))
        out.append((nl, len(bad), bad[:5]))
    return out


def auto(a, z80, name, out, say):
    import time
    md5 = lambda f: hashlib.md5(Path(f).read_bytes()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : ice_palace (figures as sprites in their original ink; ULA bitmap and scenery colours kept)')
    if md5(z80) != SOURCE_MD5:
        say('Snapshot  : MD5 %s, not the verified release %s: refused' % (md5(z80), SOURCE_MD5))
        say('Result    : FAILED')
        return False
    # No plain build: SP is in the paged top 16K (no automatic tail place), and a tail at 0x5B00 is wrong without the
    # hooks' boot code - the game reads the printer buffer before writing it (ROM path check, intake frame 1353).
    say('Plain     : none (the converter has no tail place for this snapshot; the sprite build\'s boot code puts '
        '0x5B00-0x5BFF back)')
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=Patch(z80))
    say('Sprites   : %s  %s' % (os.path.basename(spr), md5(spr)))
    scr = Path(z80).resolve().parent / LOADING
    if scr.exists():
        ld = os.path.join(out, name + '_sprites_loading.nex')
        Path(ld).write_bytes(loading_nex(Path(spr).read_bytes(), scr.read_bytes()))
        say('Loading   : %s  %s  (the tape\'s loading screen in the NEX header)' % (os.path.basename(ld), md5(ld)))
    else:
        say('Loading   : no %s beside the snapshot: no loading-screen build' % LOADING)
    ok = True
    boot = boot_check(spr, z80, Patch(z80))
    bok = all(n == 0 for _, n, _ in boot)
    ok = ok and bok
    say('Boot      : registers with R and RAM 0x4000-0xFFFF as the snapshot, plain start and after NEXLOAD -> %s'
        % ('PASS' if bok else 'FAIL %s' % boot))
    rzxs = list(a.rzx or [])
    stop = getattr(a, 'quick', None)
    states = {}
    p = Patch(z80)
    for r in rzxs:
        t = time.time()
        c, ex, st = verify(p, r, stop, collect=1)
        states.update(st)                       # the last recording's state per site wins (as the pilot's units)
        bad = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not bad
        calls = sum(v for k, v in c.items() if k.startswith('hook '))
        say('Verify    : %s  %d frames, %d paired calls (%s), %d layer checks, %d oracle pixels, wrong-x negative %s, '
            'peak %d quadrants, %.0fs -> %s' % (
                os.path.basename(r), c['frames'], calls,
                ' '.join('%s %d' % (k[5:], v) for k, v in sorted(c.items()) if k.startswith('hook ')),
                c['layer checks'], c['layer pixels'], 'detected' if c['negative wrong x detected'] else 'NOT DETECTED',
                c['peak quadrants'], time.time() - t, 'IDENTICAL' if not bad else 'FAILED %s %s' % (bad, str(ex)[:400])))
    if not rzxs:                                # a rebuild (selftest, --decisions): builds and boot only
        say('Verify    : no recording (--rzx): rebuild only, the record holds the verification')
        say('Result    : %s' % ('PASSED (rebuild)' if ok else 'FAILED'))
        return ok
    missing = [hex(x) for x in (0x7457, 0x6B36, RESET[0]) if x not in states]
    if missing:
        say('Unit      : no captured state for %s: not run' % ', '.join(missing))
        ok = False
    else:
        u, uf = unit_tests(p, states)
        ub = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not ub
        say('Unit      : %d clock cases (every site x 4 incoming speeds), %d pixel cases (64 IDs x mirror x phase + '
            'edges), negatives %d of 8 detected -> %s' % (
                u['clock cases'], u['pixel cases'], sum(v for k, v in u.items() if k.endswith(' detected')),
                'PASS' if not ub else 'FAIL %s %s' % (ub, uf)))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('source')
    ap.add_argument('destination')
    ap.add_argument('--loading')
    a = ap.parse_args()
    build(a.source, a.destination, a.loading)
