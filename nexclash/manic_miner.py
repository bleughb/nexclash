"""Manic Miner (Bug-Byte, 1983, 48K) engine 'manic_miner'. Additive module: reachable only through
is_manic_miner(). Facts, design and results: games/manic_miner.md; hooks: asm/manic_miner_hooks.asm.

Back-buffer composer with interrupts off for the whole game. Every frame the game copies the clean
buffers (0x7000 pixels -> 0x6000, 0x5E00 attributes -> 0x5C00), plots the figures into 0x6000 and
paints 0x5C00, then LDIRs 0x6000 -> ULA pixels and 0x5C00 -> ULA attributes. Collisions read only
the buffers, never the ULA. So the buffers stay as they are, and only the two LDIRs' sources change;
each plot call sets one hardware sprite.

Verify: at every hook site run original and patched code from the same state and compare registers
and memory; at every pixel blit rebuild the picture from the patched ULA (0x7000) plus the sprites
and compare it with the bytes the original shows (0x6000), bit for bit.
"""
import collections
import copy
import hashlib
import json
import os

ROM_ORG = 0x386E
ALT_PAGE = 24
TAIL_ADDR = 0x5B00
CNT = 0x5BFF
NSPR = 16
BEAM_CAVERN = 18
PAT_ITEM, PAT_PORT, PAT_FLASH = 18, 19, 20
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]
# site: (original bytes, entry symbol, kind)
SITES = {
    0x86AD: ('cd758a', 'e_cav', 'cav'),
    0x8DEB: ('cdf48f', 'e_hg', 'hg'),
    0x8E39: ('cdf48f', 'e_eug', 'eug'),
    0x8EC9: ('cdf48f', 'e_sky', 'sky'),
    0x8F3B: ('cdf48f', 'e_sky', 'vg'),
    0x91D7: ('cdf48f', 'e_kfl', 'kfl'),
    0x9206: ('cdf48f', 'e_kst', 'kst'),
    0x8FAB: ('cdd592', 'e_item', 'item'),
    0x8FEF: ('2ab280', 'e_port', 'port'),
    0x927F: ('3a6880', 'e_wil', 'wil'),
    0x87A2: ('210060', 'e_blit', 'blit'),
    0x87C8: ('21005c', 'e_attr', 'attr'),
    0x85E6: ('210040', 'e_hl40', 'title'),
    0x8963: ('210040', 'e_hl40', 'over'),
    0x9040: ('116082', 'e_de82', 'sword'),
}
SITE_KIND = {a: v[2] for a, v in SITES.items()}
INTERIORS = {a + k for a in SITES for k in (1, 2)}
# where the pair run of a site ends (default: site + 3)
STOP = {0x87A2: 0x87B1,     # past the pixel LDIR and OR A (its bits 3, 5 of F are dead there)
        0x87C8: 0x92D1}     # past the attribute LDIR, LD H,7 / LD L,A and ADD HL,HL in the HUD print
STOP_SP = {0x87C8: 4}       # inside CALL 0x92BA / CALL 0x92CB
HL_DEAD = {0x87A2}          # HL = 0x8000 vs 0x7000; both paths from 0x87B1 reload it (0x87BC, 0x87C8)
FIGS = ('wil', 'hg', 'eug', 'sky', 'vg', 'kfl', 'kst', 'item', 'port')

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'manic_miner.json'),
              os.path.join(_HERE, 'manic_miner.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('manic_miner.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_manic_miner(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


# ---------------------------------------------------------------------------------------------
# The patch
# ---------------------------------------------------------------------------------------------

class ManicMinerPatch:
    name = 'Manic Miner figures -> hardware sprites (altrom, blit sources redirected)'

    def __init__(self, prof=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 200
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)
        self.sites = []
        for a, (old, sym, _k) in SITES.items():
            self.sites.append((a, bytes.fromhex(old), b'\xCD' + self.syms[sym].to_bytes(2, 'little')))
        self.extra_banks = {}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Manic Miner patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if ram[CNT - 0x4000]:
            raise ValueError('hook counter byte 0x%04X is not zero in this snapshot' % CNT)
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        self.extra_banks = {12: self.page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# Next-side model and event runner
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self):
        self.nr = {}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_at = 0
        self.pal = {}
        self.pal_i = 0
        self.events = []
        self.cnt = 0              # the hook counter byte (0x5BFF) as the patched code leaves it

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x40:
            self.pal_i = val
        elif reg == 0x41:
            self.pal[self.pal_i] = val
            self.pal_i = (self.pal_i + 1) & 255
        self.events.append(('nr', reg, val))

    def port_out(self, port, val):
        if port == 0x303B:
            self.pat_at = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pat_at % 16384] = val
            self.pat_at += 1
        else:
            self.events.append(('out', port, val))

    def clone(self):
        q = copy.copy(self)
        q.nr, q.pal = dict(self.nr), dict(self.pal)
        q.attr = [list(a) for a in self.attr]
        q.pat = bytearray(self.pat)
        q.events = []
        return q


def sprite_nibbles(attr, pat):
    """Visible 4-bit anchor sprite -> (x, y, pattern number, 16 x 16 nibbles) or None."""
    a0, a1, a2, a3, a4 = attr
    if not a3 & 0x80:
        return None
    x = a0 + (a2 & 1) * 256 - 32
    y = a1 - 32
    n = (a3 & 0x3F) * 2 + (1 if a4 & 0x40 else 0)
    base = n * 128
    nib = [[(pat[base + j * 8 + k // 2] >> (0 if k % 2 else 4)) & 15 for k in range(16)] for j in range(16)]
    return x, y, n, nib


def _ink(n, v):
    """Pattern n, nibble v (not 0) -> pixel bit the ULA would show: FLASH phase swaps the two."""
    return v == 3 if n == PAT_FLASH else v == 1


def composite(clean, attrs, pat):
    """The picture of the patched build: clean 4K pixels, sprites in slot order (higher on top)."""
    buf = bytearray(clean)
    for at in attrs:
        s = sprite_nibbles(at, pat)
        if s is None:
            continue
        x, y, n, nib = s
        for j in range(16):
            yy = y + j
            if yy >= 128:
                continue
            base = ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2)
            for k in range(16):
                v = nib[j][k]
                if v:
                    xx = x + k
                    if xx >= 256:
                        continue
                    a = base + (xx >> 3)
                    m = 0x80 >> (xx & 7)
                    if _ink(n, v):
                        buf[a] |= m
                    else:
                        buf[a] &= ~m & 255
    return buf


def _overlays(get, alt, psite, ns=None, cnt=0):
    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return v if v is not None else get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __init__(s):
            s.ov = {CNT: cnt}
            s.romw = 0

        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            v = psite.get(a)
            if v is not None:
                return v
            v = s.ov.get(a)
            return v if v is not None else get(a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw += 1
            else:
                s.ov[a] = v
    return O, P


def _machine(Sim, mem, regs, ns, slot='o'):
    from .simpool import machine
    from . import z80n
    sim = machine(Sim, mem, regs, slot)

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.port_out(port, value)
    sim.set_tracer(Tr())
    z80n.install(sim, ns.nextreg)
    return sim


def _run(sim, stop, limit=400000):
    from .z80n import Z80NError
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    try:
        while not stop(R):
            ops[mem[R[24]]]()
            n += 1
            if n > limit:
                return False
    except Z80NError:           # ran off into data: only a broken hook gets here
        return False
    return True


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR
HL = (6, 7)


def event(patch, pc, get, R, ns, alt, Sim, clean0=None):
    """One hook site from one state. Returns (failures, info). ns is updated in place. clean0: the
    4K the game copied to 0x6000 this frame (0x874A); it may change 0x7000 after that copy: conveyor
    (0x9105), crumbling floor (0x8BBA), Kong's wall and floor (0x916C, 0x9194). The original shows
    such a change a frame later than the patched ULA, which copies 0x7000 at the blit."""
    f = []
    kind = SITE_KIND[pc]
    sp0 = R[12]
    end = STOP.get(pc, pc + 3)
    sp_end = sp0 - STOP_SP.get(pc, 0)

    def stop(r):
        return r[24] == end and r[12] == sp_end
    psite = patch._psite
    O, P = _overlays(get, alt, psite, cnt=ns.cnt)
    o, p = O(), P()
    so = _machine(Sim, o, list(R), NextState())
    so_ok = _run(so, stop)
    Ro = list(so.registers)
    ns.events = []
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    sp_ok = _run(sp_, stop)
    Rp = list(sp_.registers)
    ns.cnt = p.ov.get(CNT, ns.cnt)
    info = {'t_o': Ro[25] - R[25], 't_p': Rp[25] - R[25]}
    if not (so_ok and sp_ok):
        return [('did not return', so_ok, sp_ok)], info
    regs = [i for i in CMP if not (pc in HL_DEAD and i in HL)]
    diff = [i for i in regs if Ro[i] != Rp[i]]
    if diff:
        f.append(('registers differ', diff, [Ro[i] for i in diff], [Rp[i] for i in diff]))
    if p.romw:
        f.append(('patched code wrote ROM',))
    bad = [e for e in ns.events if e[0] in ('in', 'out') or e[1] not in (0x07, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x40, 0x41)]
    if bad:
        f.append(('port or NEXTREG outside the sprite registers', bad[:3]))
    if ns.nr.get(0x07, 0) != 0:
        f.append(('hook left the CPU at 28 MHz',))
    dead = range(Ro[12] - 64, Ro[12])
    cavern = get(0x8407)
    ula = (0x4000, 0x5A00) if pc in (0x87A2, 0x87C8) else (0, 0)
    keys = (set(o.ov) | set(p.ov)) - {CNT}
    md = []
    for a in keys:
        if a in dead or ula[0] <= a < ula[1]:
            continue
        if pc == 0x87C8 and cavern == BEAM_CAVERN and 0x5C00 <= a < 0x5E00:
            continue            # dead after this copy: rewritten at 0x8748 before any read
        if o[a] != p[a]:
            md.append(a)
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    if pc == 0x87A2:
        if any(p.ov.get(0x4000 + i, -1) != get(0x7000 + i) for i in range(4096)):
            f.append(('ULA pixels are not the clean buffer',))
        if clean0 is not None:
            now = bytes(get(0x7000 + i) for i in range(4096))
            info['ahead'] = sum(1 for i in range(4096) if now[i] != clean0[i])
            pic = composite(clean0, ns.attr[:NSPR], ns.pat)
            truth = bytes(get(0x6000 + i) for i in range(4096))
            info['blit'] = 1
            if bytes(pic) != truth:
                bytes_diff = [i for i in range(4096) if pic[i] != truth[i]]
                missing = [i for i in bytes_diff if truth[i] & ~pic[i]]
                if get(0x806B) == 0xFF and not missing:
                    # the frame a collision cut short: the original's figure stopped in mid-plot,
                    # the sprite is whole (the picture holds every pixel the original shows)
                    info['cut'] = 1
                else:
                    f.append(('picture differs (ULA + sprites vs the original)', len(bytes_diff),
                              ['0x%04X' % (0x6000 + i) for i in bytes_diff[:4]]))
            info['visible'] = sum(1 for a in ns.attr[:NSPR] if a[3] & 0x80)
            same = differ = 0
            for a in ns.attr[:NSPR]:
                if a[3] & 0x80:
                    x, y = a[0] + (a[2] & 1) * 256 - 32, a[1] - 32
                    cell = get(0x5C00 + (y >> 3) * 32 + (x >> 3))
                    if (a[2] >> 4) == ((cell & 7) | (8 if cell & 0x40 else 0)):
                        same += 1
                    else:
                        differ += 1
            info['ink same'], info['ink differs'] = same, differ
    elif pc == 0x87C8:
        wrong = 0
        for i in range(512):
            v = p.ov.get(0x5800 + i, -1)
            if R[6] == 0x5D:
                exp = o.ov.get(0x5800 + i, -1)          # the effect's colour, as the original
            elif cavern == BEAM_CAVERN and get(0x5C00 + i) == 0x77:
                exp = 0x77
            else:
                exp = get(0x5E00 + i)
            if v != exp:
                wrong += 1
        if wrong:
            f.append(('ULA attributes are not the clean buffer', wrong))
        info['attr'] = 1
    return f, info


def _alt(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _prepare(patch):
    patch._psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay the RZX (original game); at every hook site run original and patched code from the same
    state and compare. Returns (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    _prepare(patch)
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = _alt(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'frame': 0, 'on': False}
    ns = NextState()
    cnt = collections.Counter()
    WATCH = set(SITE_KIND) | INTERIORS
    NOTE = 0x8755
    states = []
    Rw = _rw()

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __setitem__(s, a, v):
            if st['on'] and type(a) is int and a in site_bytes:
                fail('game wrote a patch site', (a,))
            S(s, a, v)

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a)

            def mk(fn):
                def g():
                    pc = R[24]
                    if pc == 0x8755:            # the game has just copied 0x7000 -> 0x6000
                        st['clean0'] = bytes(G(mem, a) for a in range(0x7000, 0x8000))
                    if pc in WATCH:
                        cnt[pc] += 1
                        kind = SITE_KIND.get(pc)
                        if kind:
                            if collect and c['collected ' + kind] < collect:
                                c['collected ' + kind] += 1
                                states.append((pc, list(R), bytes(G(mem, a) for a in range(65536)), ns.clone()))
                            fl, info = event(patch, pc, get, R, ns, alt, Rw, st.get('clean0'))
                            c[kind] += 1
                            c['T orig'] += info['t_o']
                            c['T hook'] += info['t_p']
                            c['cavern %d' % get(0x8407)] += kind == 'blit'
                            if kind == 'wil':
                                c['willy cavern %d' % get(0x8407)] += 1
                            for key in ('blit', 'cut', 'attr'):
                                c['picture ' + key] += info.get(key, 0)
                            if 'visible' in info:
                                c['sprites shown'] += info['visible']
                            c['ULA bytes a frame ahead'] += info.get('ahead', 0)
                            c['ink same'] += info.get('ink same', 0)
                            c['ink differs'] += info.get('ink differs', 0)
                            for k in fl:
                                fail('%s: %s' % (kind, k[0]), k[1:])
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if progress and st['frame'] % 1000 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = Sm
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    for a in INTERIORS:
        if cnt[a]:
            c['jump into a patched instruction (0x%04X)!' % a] += 1
    c['frames'] = st['frame']
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Lockstep: the whole patched game against the original, same inputs (no RZX timing needed: the
# game never enables interrupts, so its logic depends only on the sequence of IN values)
# ---------------------------------------------------------------------------------------------

def inputs_of(rzx_path, stop=None):
    """The IN values of the recording, in order."""
    from skoolkit.rzxplay import parse_rzx
    vals = []
    n = 0
    for b in parse_rzx(rzx_path):
        o = b.obj
        fr = getattr(o, 'frames', None)
        if fr is None:
            continue
        for f in fr:
            vals.extend(o.data[f.start:f.end])
            n += 1
            if stop and n >= stop:
                return vals
    return vals


def lockstep(patch, z80, rzx_path, stop=None, progress=None, on_frame=None):
    """Run the original and the patched game side by side on the same IN values; at each pass
    through the pixel blit compare registers and all RAM outside the ULA, the hook byte, the sites.
    on_frame(n, original memory, patched memory, NextState): called when both have copied the screen.
    -> Counter (failure keys end in !), examples."""
    _prepare(patch)
    c, ex = collections.Counter(), {}
    vals = inputs_of(rzx_path, stop)
    Rw = _rw()
    from .machine import Machine
    mo = Machine(z80)
    regs0 = list(mo.sim.registers)
    ram0 = bytes(mo.sim.memory)

    class Feed:
        def __init__(s):
            s.i = 0
            s.over = False

        def read_port(s, r, port):
            if s.i >= len(vals):
                s.over = True
                return 0xFF
            v = vals[s.i]
            s.i += 1
            return v

        def write_port(s, r, port, value, *x):
            pass

    alt = _alt(patch)
    mo_ = bytearray(ram0)
    mp_ = bytearray(alt[:0x4000]) + bytearray(ram0[0x4000:])
    for a, old, new in patch.sites:
        mp_[a:a + len(new)] = new
    so = Rw(mo_, {})
    sp = Rw(mp_, {})
    so.registers[:] = regs0
    sp.registers[:] = regs0
    fo, fp = Feed(), Feed()
    so.set_tracer(fo)
    ns = NextState()
    sp.set_tracer(type('T', (), {'read_port': lambda s, r, port: fp.read_port(r, port),
                                 'write_port': lambda s, r, port, v, *x: ns.port_out(port, v)})())
    from . import z80n
    z80n.install(sp, ns.nextreg)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    BLIT = 0x87A2
    Ro, Rp = so.registers, sp.registers
    opso, opsp = so.opcodes, sp.opcodes
    n = 0
    clean0 = None
    limit = 4_000_000_000
    while fo.i < len(vals) and n < limit:
        while Ro[24] != BLIT and not fo.over:
            opso[mo_[Ro[24]]]()
        while Rp[24] != BLIT and not fp.over:
            if Rp[24] == 0x8755:
                clean0 = bytes(mp_[0x7000:0x8000])
            opsp[mp_[Rp[24]]]()
        if fo.over or fp.over:
            break
        n += 1
        c['blits compared'] += 1
        c['cavern %d' % mo_[0x8407]] += 1
        rd = [i for i in CMP if Ro[i] != Rp[i]]
        # (HL has no value here: 0x87A2 loads it. Dead stack below SP may differ.)
        if rd and rd != [6, 7]:
            c['registers differ!'] += 1
            ex.setdefault('registers', (n, rd))
        sp_ = Ro[12]
        if fo.i != fp.i:
            c['input position differs!'] += 1
            ex.setdefault('input', (n, fo.i, fp.i))
        a = bytes(mo_[0x5A00:sp_ - 64]) + bytes(mo_[sp_:65536])
        b = bytes(mp_[0x5A00:sp_ - 64]) + bytes(mp_[sp_:65536])
        if a != b:
            d = [i for i in range(0x5A00, 65536) if not sp_ - 64 <= i < sp_ and mo_[i] != mp_[i]
                 and i != CNT and i not in site_bytes and not 0x5B00 <= i < 0x5C00]
            if d:
                c['memory differs!'] += 1
                ex.setdefault('memory', (n, len(d), ['0x%04X' % x for x in d[:6]]))
        if progress and n % 500 == 0:
            progress(n, c)
        opso[mo_[Ro[24]]]()
        opsp[mp_[Rp[24]]]()
        while Rp[24] != BLIT + 3:       # e_blit: hides the slots this frame did not use
            opsp[mp_[Rp[24]]]()
        if clean0 is not None:
            pic = composite(clean0, ns.attr[:NSPR], ns.pat)
            truth = bytes(mo_[0x6000:0x7000])
            if bytes(pic) == truth:
                c['pictures identical'] += 1
            elif mo_[0x806B] == 0xFF and not any(truth[i] & ~pic[i] for i in range(4096)):
                c['pictures cut short by a collision'] += 1
            else:
                c['picture differs!'] += 1
                ex.setdefault('picture', (n, mo_[0x8407], sum(1 for i in range(4096) if pic[i] != truth[i])))
        if on_frame is not None:
            while Ro[24] != 0x87D3:
                opso[mo_[Ro[24]]]()
            while Rp[24] != 0x87D3:
                opsp[mp_[Rp[24]]]()
            on_frame(n, mo_, mp_, ns)
    c['inputs used'] = fo.i
    c['inputs total'] = len(vals)
    return c, ex


# ---------------------------------------------------------------------------------------------
# Unit tests: what the recording may not reach
# ---------------------------------------------------------------------------------------------

def _canvas_case(patch, pc, R, mem, alt, Sim, ns0):
    """Original plot on an empty buffer -> its bits; patched -> the sprite. They must agree."""
    m2 = bytearray(mem)
    m2[0x6000:0x7000] = bytes(4096)
    ns = ns0.clone()
    ns.cnt = 0
    before = [list(a) for a in ns.attr]
    get = m2.__getitem__
    fl, info = event(patch, pc, get, R, ns, alt, Sim)
    # run the original alone for the truth
    O, _ = _overlays(get, alt, patch._psite)
    o = O()
    so = _machine(Sim, o, list(R), NextState())
    end = STOP.get(pc, pc + 3)
    sp0 = R[12]
    _run(so, lambda r: r[24] == end and r[12] == sp0)
    truth = bytearray(4096)
    for a, v in o.ov.items():
        if 0x6000 <= a < 0x7000:
            truth[a - 0x6000] = v
    if pc == 0x8FEF:                     # portal: the LD HL only; plotted by the code after it
        pass
    pic = composite(bytes(4096), [ns.attr[0]], ns.pat)
    if pc != 0x8FEF and bytes(pic) != bytes(truth):
        fl = list(fl) + [('sprite differs from the plot', sum(1 for i in range(4096) if pic[i] != truth[i]))]
    return fl, ns


def unit_tests(patch, states, neg=None):
    """states from verify(collect=n): (site, registers, 64K memory, NextState)."""
    c = collections.Counter()
    alt = _alt(patch)
    Sim = _rw()
    _prepare(patch)
    by = collections.defaultdict(list)
    for pc, R, mem, ns in states:
        by[pc].append((R, mem, ns))
    ns_full = None
    # setup routine: palette index o << 4 + 1 = Spectrum colour o; all sprites hidden; sprites on
    ns = NextState()
    m0 = bytearray(65536)
    m0[0xD000:0xD000 + len(patch.stub_extra)] = patch.stub_extra
    m0[0xFFFC], m0[0xFFFD] = 0x00, 0xE0
    r0 = list(Sim(bytearray(65536), {}).registers)
    r0[12], r0[24] = 0xFFFC, 0xD000
    sim = _machine(Sim, m0, r0, ns)
    done = _run(sim, lambda q: q[24] == 0xE000)
    ok = done and all(ns.pal.get(o << 4 | 1) == SPECCY[o] for o in range(16)) and ns.nr.get(0x15) == 1 and \
        ns.nr.get(0x4B) == 0 and ns.nr.get(0x43) == 0x20 and not any(a[3] & 0x80 for a in ns.attr)
    c['setup %s' % ('ok' if ok else 'FAIL!')] += 1
    # (a) every cavern's data through the cavern hook: patterns from each cavern's own graphics
    if 0x86AD in by:
        R, mem, ns0 = by[0x86AD][0]
        for cav in range(20):
            m2 = bytearray(mem)
            src = 0xB000 + cav * 0x400
            m2[0x8000:0x8200] = mem[src + 0x200:src + 0x400]
            ns = ns0.clone()
            fl, _ = event(patch, 0x86AD, m2.__getitem__, R, ns, alt, Sim)
            c['cavern load cases %s' % ('ok' if not fl else 'FAIL!')] += 1
            if fl:
                c['  cav %d %s' % (cav, str(fl[0])[:60])] += 1
            # every pattern == its graphics
            bad = 0
            def rows(a):
                return [m2[a + r] << 8 | m2[a + r + 1] for r in range(0, 32, 2)]
            want = [(0x8200 + 32 * i, 1, 0) for i in range(8)] + [(0x8100 + 32 * i, 1, 0) for i in range(8)] + \
                [(0x8140, 1, 4), (0x8160, 1, 4)]
            want += [None, (0x8090, 1, 3), (0x8090, 3, 1), (0x80E0, 1, 0)]
            for n, w in enumerate(want):
                base = n * 128
                nib = [[(ns.pat[base + j * 8 + k // 2] >> (0 if k % 2 else 4)) & 15 for k in range(16)] for j in range(16)]
                if w is None:
                    exp = [[((1 if m2[0x80B4 + j] >> (7 - k) & 1 else 2) if j < 8 and k < 8 else 0)
                            for k in range(16)] for j in range(16)]
                else:
                    r = rows(w[0])
                    exp = [[(w[1] if r[j] >> (15 - k) & 1 else w[2]) for k in range(16)] for j in range(16)]
                if nib != exp:
                    bad += 1
            c['cavern patterns %s' % ('ok' if not bad else 'FAIL!')] += 1
            # palette: the three paper colours
            for nibble, attr in ((2, m2[0x8075]), (3, m2[0x808F]), (4, m2[0x8020])):
                exp = SPECCY[(attr >> 3 & 7) | (8 if attr & 0x40 else 0)]
                ok = all(ns.pal.get(o << 4 | nibble) == exp for o in range(16))
                c['cavern palette %s' % ('ok' if ok else 'FAIL!')] += 1
            ns_full = ns
    # (b) each plot kind on an empty buffer at edge positions, every frame the game can select
    if ns_full is not None:
        for pc in (0x8DEB, 0x8EC9, 0x8F3B, 0x9206):
            for R, mem, ns0 in by.get(pc, [])[:2]:
                base = by[0x86AD][0]
                # patterns from this state's own cavern
                ns1 = NextState()
                Rc = list(base[0])
                event(patch, 0x86AD, mem.__getitem__, Rc, ns1, alt, Sim)
                for fr in range(8):
                    for row in (0, 8, 16, 24, 32, 40, 48, 56):        # cell rows of the two thirds
                        for col in (0, 1, 15, 30):
                            for pix in (0, 3, 7):
                                y = row * 2 + pix
                                if y > 112:
                                    continue
                                h = 0x60 | (y & 7) | ((y & 0xC0) >> 3)
                                l = col | ((y & 0x38) << 2)
                                r = list(R)
                                r[4], r[5] = 0x81, fr * 32
                                r[6], r[7] = h, l
                                r[3] = 1
                                fl, _ = _canvas_case(patch, pc, r, mem, alt, Sim, ns1)
                                c['plot cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                                if fl and c['  plot fail example'] < 3:
                                    c['  plot fail example'] += 1
                                    c['  site 0x%04X fr %d row %d col %d %s' % (pc, fr, y, col, str(fl[0])[:70])] += 1
    # (c) Willy: every frame, column edges, every other row
    for R, mem, ns0 in by.get(0x927F, [])[:1]:
        ns1 = NextState()
        event(patch, 0x86AD, mem.__getitem__, list(by[0x86AD][0][0]), ns1, alt, Sim)
        for facing in (0, 1):
            for fr in range(4):
                for col in (0, 15, 30):
                    for y in (0, 1, 7, 8, 63, 64, 100, 112):
                        m2 = bytearray(mem)
                        m2[0x6000:0x7000] = bytes(4096)
                        m2[0x806A] = facing
                        m2[0x8069] = fr
                        m2[0x806C] = (m2[0x806C] & 0xE0) | col
                        m2[0x8068] = y * 2
                        ns = ns1.clone()
                        ns.cnt = 0
                        r = list(R)
                        fl, _ = event(patch, 0x927F, m2.__getitem__, r, ns, alt, Sim)
                        # truth: the original's own loop from this state to its RET
                        O, _ = _overlays(m2.__getitem__, alt, patch._psite)
                        o = O()
                        so = _machine(Sim, o, list(r), NextState())
                        sp0 = r[12]
                        ret = m2[sp0] | m2[sp0 + 1] << 8
                        _run(so, lambda q: q[24] == ret and q[12] == sp0 + 2)
                        truth = bytearray(4096)
                        for a, v in o.ov.items():
                            if 0x6000 <= a < 0x7000:
                                truth[a - 0x6000] = v
                        pic = composite(bytes(4096), [ns.attr[0]], ns.pat)
                        if bytes(pic) != bytes(truth):
                            fl = list(fl) + [('sprite differs from Willy', 1)]
                        c['Willy cases %s' % ('ok' if not fl else 'FAIL!')] += 1
                        if fl and c['  Willy fail example'] < 3:
                            c['  Willy fail example'] += 1
                            c['  facing %d fr %d col %d y %d %s' % (facing, fr, col, y, str(fl[0])[:70])] += 1
    # (d) guard: slots full leaves the sprites alone
    for R, mem, ns0 in by.get(0x8DEB, [])[:1]:
        ns = ns0.clone()
        ns.cnt = NSPR
        before = [list(a) for a in ns.attr]
        fl, _ = event(patch, 0x8DEB, mem.__getitem__, list(R), ns, alt, Sim)
        ok = not fl and ns.attr == before and ns.cnt == NSPR
        c['slot guard %s' % ('ok' if ok else 'FAIL!')] += 1
    # (e) screens without figures: title, game over, swordfish hide every slot (+ the counter)
    for pc in (0x85E6, 0x8963, 0x9040):
        base = next(iter(by.get(pc, []) or by.get(0x85E6, []) or []), None)
        if base is None:
            continue
        R, mem, ns0 = base
        ns = ns0.clone()
        for i in range(NSPR):
            ns.attr[i][3] |= 0x80
        ns.cnt = 5
        r = list(R)
        r[24] = pc
        fl, _ = event(patch, pc, mem.__getitem__, r, ns, alt, Sim)
        ok = not fl and not any(a[3] & 0x80 for a in ns.attr[:NSPR]) and ns.cnt == 0
        c['hide cases %s' % ('ok' if ok else 'FAIL!')] += 1
    # (f) the attribute blit: the extra-life fill keeps the effect; the beam cavern keeps the beam
    for R, mem, ns0 in by.get(0x87C8, [])[:1]:
        m2 = bytearray(mem)
        r = list(R)
        r[6], r[7] = 0x5D, 0xFF                      # HL after the fill at 0x87C6
        m2[0x5C00:0x5E00] = bytes([0x28]) * 512
        fl, _ = event(patch, 0x87C8, m2.__getitem__, r, ns0.clone(), alt, Sim)
        c['extra-life fill %s' % ('ok' if not fl else 'FAIL!')] += 1
        m2 = bytearray(mem)
        m2[0x8407] = BEAM_CAVERN
        m2[0x5C00:0x5E00] = bytes(m2[0x5E00:0x6000])
        m2[0x5C17] = m2[0x5C37] = 0x77               # beam
        m2[0x5C50] = m2[0x5C51] = 0x46               # a figure's paint
        r = list(R)
        fl, _ = event(patch, 0x87C8, m2.__getitem__, r, ns0.clone(), alt, Sim)
        c['beam cavern %s' % ('ok' if not fl else 'FAIL!')] += 1
    return c


def negative_patches(patch):
    """Broken builds, each of which the verify must fail: (name, patch, what must catch it)."""
    out = []

    def edit(name, sym, old, new):
        q = copy.copy(patch)
        off = patch.syms[sym] - 0x2000
        page = bytearray(patch.page)
        i = bytes(page).index(bytes.fromhex(old), off)
        if i - off > 80:
            raise ValueError('negative control %s: bytes not found near %s' % (name, sym))
        page[i:i + len(bytes.fromhex(new))] = bytes.fromhex(new)
        q.page = bytes(page)
        out.append((name, q))
    edit('pixel blit keeps the figures', 'e_blit', '210070', '210060')   # LD HL,0x7000 -> 0x6000
    edit('attr blit keeps the figure paint', 'e_attr', '21005e', '21005c')
    # sprite Y off by one: ADD A,32 -> ADD A,33 in putxy (shared by every figure)
    off = patch.page.index(bytes.fromhex('c620ed9236'))
    page = bytearray(patch.page)
    page[off + 1] = 33
    q = copy.copy(patch)
    q.page = bytes(page)
    out.append(('sprites one row low', q))
    edit('patterns inverted', 'e_cav', '110001', '110100')   # LD DE,0x0100 -> 0x0001 (ink <-> paper)
    # a hook that loses a register: put's caller keeps BC only if plot1 pops it; POP BC -> NOP
    off = patch.page.index(bytes.fromhex('e1d1c1f1ed910700c3f48f'))
    page = bytearray(patch.page)
    page[off + 2] = 0x00
    q = copy.copy(patch)
    q.page = bytes(page)
    out.append(('plot hook loses a register', q))
    # a site that never runs: the plain CALL stays in the game (no sprite for the guardians)
    q = copy.copy(patch)
    q.sites = [(a, old, old if a == 0x8DEB else new) for a, old, new in patch.sites]
    out.append(('guardian hook never runs', q))
    return out


def negative_run(patch, rzx, frames=2000):
    """Each broken build on the start of the real recording. -> {name: failures found}."""
    res = {}
    for name, q in negative_patches(patch):
        c, ex = verify(q, rzx, stop=frames)
        res[name] = {k: v for k, v in c.items() if k.endswith('!')}
    return res


# ---------------------------------------------------------------------------------------------
# The whole run
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : manic_miner (back buffer: blit sources redirected, every plot -> a sprite)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (tail 0x%04X = printer buffer)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = ManicMinerPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  (tail %d bytes at 0x%04X)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200], len(conv[2]), conv[1]))
    ok = not bad and not bad2
    states = []
    first = None
    for r in list(a.rzx or []):
        first = first or r
        quick = getattr(a, 'quick', None)
        c, ex, st = verify(patch, r, stop=quick, collect=3)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails and c['picture blit'] > 0     # a replay that shows no frame proves nothing
        say('Verify    : %s  %d frames, %s -> %s' % (
            os.path.basename(r), c['frames'],
            ', '.join('%s %d' % (k, c[k]) for k in ('blit', 'attr', 'cav', 'title', 'over', 'sword') + FIGS),
            ('IDENTICAL' if c['picture blit'] else 'NO GAME FRAME REACHED') if not fails else 'FAILED %s' % fails))
        say('            pictures compared %d (cut short by a collision %d), attribute copies %d, '
            'sprites shown %d, ULA bytes a pass ahead %d; sprite ink = the original cell ink at its top left: %d, not: %d' % (
                c['picture blit'], c['picture cut'], c['picture attr'], c['sprites shown'], c['ULA bytes a frame ahead'],
                c['ink same'], c['ink differs']))
        extra = c['T hook'] - c['T orig']
        say('Speed     : hooks add %d T as simulated, at 28 MHz about %d 3.5 MHz T (/6, LEARNINGS 2.1f) = %.2f%% of %d frames' % (
            extra, extra // 6, 100.0 * extra / 6 / max(1, c['frames'] * 69888), c['frames']))
        say('            caverns reached: %s' % ' '.join('%d:%d' % (i, c['cavern %d' % i]) for i in range(20)
                                                        if c['cavern %d' % i]))
        say('            Willy plotted in caverns: %s' % ' '.join(str(i) for i in range(20) if c['willy cavern %d' % i]))
        unrun = [k for k in FIGS + ('blit', 'attr', 'cav', 'title', 'over', 'sword') if not c[k]]
        say('            hooks that never ran in this recording: %s' % (' '.join(unrun) or 'none'))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:220]))
        lc, lx = lockstep(patch, z80, r, stop=quick)
        lf = {k: v for k, v in lc.items() if k.endswith('!')}
        ok = ok and not lf
        say('Lockstep  : %s  whole patched game vs original, %d blits compared (pictures identical %d, cut short %d), '
            '%d/%d inputs -> %s' % (
            os.path.basename(r), lc['blits compared'], lc['pictures identical'], lc['pictures cut short by a collision'],
            lc['inputs used'], lc['inputs total'],
            'IDENTICAL' if not lf else 'FAILED %s %s' % (lf, str(lx)[:300])))
    if states:
        u = unit_tests(patch, states)
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items()) if k.endswith(' ok')),
                                      'PASS' if not uf else 'FAIL %s' % uf))
        for k, v in u.items():
            if k.startswith('  '):
                say('            %s' % k)
        neg = negative_run(patch, first)
        for k, v in neg.items():
            say('Negative  : %s -> %s' % (k, 'DETECTED %s' % str(sorted(v.items()))[:200] if v else 'NOT DETECTED!'))
            ok = ok and bool(v)
        for k, q in negative_patches(patch):
            un = unit_tests(q, states)
            hit = sum(v for x, v in un.items() if x.endswith('!'))
            say('Neg. unit : %s -> %s' % (k, 'DETECTED (%d failing cases)' % hit if hit else 'not seen by the unit cases'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
