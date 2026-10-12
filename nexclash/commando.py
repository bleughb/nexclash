"""Commando (Elite; 128K) engine 'commando'. Additive module: reachable only through is_commando().

Game facts (analysis passes over the snapshot and Dean's RZX; details in games/commando.md):
  every figure is drawn by one plotter, 39120 (JP 39202), IX = object descriptor:
    +0/+4 old/new column, +1/+5 old/new y (2-line units), +2/+6 old/new frame, +3/+7 old/new
    graphics page (gfx at (page+0xA0)*256 + (0x98E2 + 2*frame)), +8/+9 window (4..95),
    +10 row pairs (image = 2*(+10) lines x 24 pixels, zig-zag stream), +11 flags.
  One pass clears the old frame's bits and ORs in the new frame: no mask, so a figure's pixels
  are exactly its OR'ed bits and no game logic reads them (lockstep proof, games/commando.md).
  Main path (both columns < 30, inside the window): new frame read only through the active set's
  H/L (INC L only) -> H := zero page makes the call erase-only. Edge/top-clip paths stay on the ULA.
  The main-path loops draw the new frame at old column -1/0/+1 only: other column steps (never
  made by the game) stay on the ULA, and so do row steps |dy| >= the row pairs (the loops wrap
  and draw past the frame; never made by the game). Sprite rows below line 191 are cut by the clip window; a
  frame starting below line 191 keeps no entry (soldiers leaving at the bottom are reused without
  another plot: such entries were never freed and filled the table).
  Interrupts are enabled at every hook site and the ISR writes 7FFD: no paging in the hooks.
Converted descriptors: player 23514, enemy soldiers 23313+20n (n<5), POW group 64975 (shared).
Hooks: asm/commando_hooks.asm (stubs + code in alt ROM image 1 at 0x386E, state in bank-5 RAM
0x5C00-0x5E1F which the game never touches once it runs).
The snapshot is the BASIC loader (line 30: PAUSE 0, "INFY LIVES", USR 25088 -> JP 25630): 0x5C00-
0x5E1F holds the system variables and the program until then, so the build leaves it alone and
e_init (at 25630, run once on both loader paths) sets the hook state up when the game takes over.
"""
import collections
import json
import os

from .rainbow import NextState, _machine, _run, boot_check as _rb_boot_check, mem64

ALT_PAGE = 24
ROM_ORG = 0x386E
RAM_LO, RAM_HI = 0x5C00, 0x5E20             # hook state (never read/written by the game once it runs)
ZP = 0x5D00                                 # zero page (new frame source while converted)
NIBT = 0x5E00
ENT, NENT = 0x5C10, 12
V_ON, V_FREED, V_CNT = 0x5C04, 0x5C05, 0x5C06
TAIL_ADDR = 0x6D00                          # 0x6CB5-0x70F7: never read or written in the RZX
CONV = (23514, 23313, 23333, 23353, 23373, 23393, 64975)
PLAYER, POW = 23514, 64975
SITES_ORIG = {39120: bytes.fromhex('C32299'), 39366: bytes.fromhex('7A93EBE1'),
              39529: bytes.fromhex('ED7B82FDC9'), 40955: bytes.fromhex('ED7B82FDC9'),
              27468: bytes.fromhex('CB21CB21'), 30597: bytes.fromhex('210040'),
              25630: bytes.fromhex('C3D269')}
SITE_SYM = {39120: 'e_ent', 39366: 'e_main', 39529: 'e_x', 40955: 'e_x', 27468: 'e_rect',
            30597: 'e_cls', 25630: 'e_init'}
INIT, INIT_TO = 25630, 27090                 # game entry (JP 27090) -> e_init
# bytes of patched instructions that must never be a PC (interiors behind each 3-byte JP)
INTERIORS = (39369, 39532, 39533, 40958, 40959, 27471, 25631, 25632)
# Next default ULA colours (RRRGGGBB): ink 0-7 normal, then bright
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'commando.json'),
              os.path.join(_HERE, 'commando.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('commando.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def identify_commando(mem):
    sg = load_profile()['signature']
    a, sig = sg['addr'], bytes.fromhex(sg['bytes'])
    return bytes(mem[a:a + len(sig)]) == sig


def is_commando(snap):
    try:
        return snap.machine != '48K' and identify_commando(mem64(snap))
    except FileNotFoundError:
        return False


def nibt(swap=False):
    """nibble -> 2 bytes of 4-bit pixels (ink index 1, 0 = transparent). swap: negative control."""
    t = bytearray(32)
    on, off = (0, 1) if swap else (1, 0)
    for n in range(16):
        px = [on if n & b else off for b in (8, 4, 2, 1)]
        t[2 * n] = px[0] << 4 | px[1]
        t[2 * n + 1] = px[2] << 4 | px[3]
    return bytes(t)


def palette():
    pal = bytearray(256)
    for k in range(16):
        pal[16 * k + 1] = SPECCY[k]
    return bytes(pal)


class CommandoPatch:
    name = 'Commando figures (player, soldiers, POWs) -> hardware sprites (altrom + bank-5 state)'

    def __init__(self, prof=None, swap_nibt=False):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        nb = int(h['syms']['nibrom'], 16) - ROM_ORG
        if self.rom_code[nb:nb + 32] != nibt():
            raise ValueError('profile nibble table differs from nibt()')
        if swap_nibt:                           # negative control: its own (broken) table
            self.rom_code = self.rom_code[:nb] + nibt(True) + self.rom_code[nb + 32:]
        self.setup = bytes.fromhex(h['setup'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = self.setup + palette()
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 80
        self.scratch = bytes(8192)              # (rainbow.NextState wants one; unused here)
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
        ram = bytearray(RAM_HI - RAM_LO)        # zeros: V_*, entry table, stack, zero page
        ram[V_FREED - RAM_LO] = 0xFF
        ram[NIBT - RAM_LO:NIBT - RAM_LO + 32] = nibt(swap_nibt)
        self.ram = bytes(ram)                   # = the state e_init leaves (unit-tested)
        self.extra_banks = {12: self.page + bytes(8192)}
        self.sites = [(a, old, (b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little')).ljust(len(old), b'\x00'))
                      for a, old in SITES_ORIG.items()]

    @staticmethod
    def _bank_of(a):
        return (5, 2, 0)[(a >> 14) - 1]

    def check_sites(self, banks):
        for a, old, new in self.sites:
            b = banks[self._bank_of(a)]
            cur = bytes(b[(a & 0x3FFF):(a & 0x3FFF) + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('Commando patch expects the 128K snapshot')
        if snap.port7ffd & 0x17 != 0x10:
            raise ValueError('snapshot must select ROM 1 (48K BASIC) and bank 0 at C000')
        self.check_sites(snap.banks)
        for a, old, new in self.sites:
            k = self._bank_of(a)
            b = bytearray(snap.banks[k])
            b[(a & 0x3FFF):(a & 0x3FFF) + len(new)] = new
            snap.banks[k] = bytes(b)
        # 0x5C00-0x5E1F untouched: BASIC still needs it; e_init sets it up at the game entry

    def rom_image(self):
        from .build import rom48
        img = bytearray(rom48())
        img[0x2000:0x4000] = self.page
        return img


def boot_check(nex, z80, patch=None):
    return _rb_boot_check(nex, z80, patch, tail=(TAIL_ADDR, TAIL_ADDR + 80))


# ---------------------------------------------------------------------------------------------
# Differential verification: replay the RZX (original game); at every hook site run the original
# and the patched code from the same state and compare.
# ---------------------------------------------------------------------------------------------

CMP = list(range(0, 13)) + [14, 16, 17] + list(range(18, 25)) + [26, 27, 28]   # all but R, T, MEMPTR


class World:
    """The patched machine's own state that persists between events: hook RAM + Next sprites."""

    def __init__(self, patch):
        self.ram = bytearray(patch.ram)
        self.ns = NextState(patch)

    def entries(self):
        out = []
        for i in range(NENT):
            e = self.ram[ENT - RAM_LO + 8 * i:ENT - RAM_LO + 8 * i + 8]
            if e[0]:
                out.append((i, e[1] | e[2] << 8, e[3], e[4], e[5], e[6]))
        return out


def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def _pair(patch, world, get, regs, stop, rom_img, sp_ret=None):
    """Run original and patched code from one state (memory read through get(a)) until PC == stop
    (and SP == sp_ret if given). world (the patched side's RAM + Next state) is mutated.
    Returns (so, o, sp, p, err)."""
    Sim = _sim_class()
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    err = []

    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            if v is not None:
                return v
            return rom_orig[a] if a < 0x4000 else get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return rom_img[a]
            if RAM_LO <= a < RAM_HI:
                return world.ram[a - RAM_LO]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                err.append(('rom write', a))
            elif RAM_LO <= a < RAM_HI:
                world.ram[a - RAM_LO] = v
                if a == V_ON and v == 1:
                    s.conv = True
            else:
                s.ov[a] = v
    from .build import rom48
    rom_orig = rom48()
    o, p = O(), P()
    p.conv = False
    ns = world.ns
    ns.events = []
    so = _machine(Sim, o, list(regs), NextState(patch))
    sp_ = _machine(Sim, p, list(regs), ns)
    for sim in (so, sp_):
        if not _run_to(sim, stop, sp_ret):
            err.append('did not return')
    if ns.nr.get(0x07, 0) != 0:
        err.append(('speed not restored', ns.nr.get(0x07)))
    if any(e[0] == 'in' for e in ns.events):
        err.append('port read in hook')
    return so, o, sp_, p, err


def _run_to(sim, stop, sp_ret, limit=400000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not (R[24] == stop and (sp_ret is None or R[12] == sp_ret)):
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            return False
    return True


def _scr_xy(a):
    o = a - 0x4000
    return (o & 31), ((o >> 8) & 7) | ((o >> 2) & 0x38) | ((o >> 5) & 0xC0)


def check_plot(get, o, p, world, ix, conv, n_before_ent):
    """Screen and sprite checks for one plot call. Returns ([failures], pixels compared)."""
    f = []
    keys = set(o.ov) | set(p.ov)
    scr = [a for a in keys if 0x4000 <= a < 0x5800]
    other = [a for a in keys if not 0x4000 <= a < 0x5800 and o[a] != p[a]]
    if other:
        f.append(('memory differs', sorted(other)[:4]))
    extra = [a for a in scr if p[a] & ~o[a]]
    if extra:
        f.append(('patched screen has bits the original lacks', sorted(extra)[:4]))
    d = {a: o[a] & ~p[a] for a in scr if o[a] & ~p[a]}
    if not conv:
        if d:
            f.append(('passthrough plot differs on screen', sorted(d)[:4]))
        return f, 0
    # converted: the missing bits are inside the new frame, and the sprite shows them
    col, y, rows = o[ix + 0], o[ix + 1], 2 * o[ix + 10]
    ents = [e for e in world.entries() if e[1] == ix and e[2] == col and e[3] == y]
    if y >= 96:                                 # frame starts below line 191: no entry, no pixels
        if d:
            f.append(('original drew bits for a frame below the screen', sorted(d)[:4]))
        if ents:
            f.append(('entry kept for a frame below the screen', col, y))
        return f, 0
    if len(ents) != 1:
        f.append(('no sprite entry for the converted plot', col, y))
        return f, 0
    i = ents[0][0]
    lit = set()
    for k in range(4):
        px = world.ns.sprite_pixels(4 * i + k)
        if px is None:
            f.append(('sprite hidden', 4 * i + k))
            continue
        lit |= {(x, yy) for x, yy, v in px if v and 0 <= x < 256 and 0 <= yy < 192}   # clip window
    box = lambda x, yy: col * 8 <= x < col * 8 + 24 and 2 * y <= yy < 2 * y + rows
    want = set()
    for a, bits in d.items():
        cx, ly = _scr_xy(a)
        for b in range(8):
            if bits & (128 >> b):
                want.add((cx * 8 + b, ly))
    if any(not box(x, yy) for x, yy in want):
        f.append(('missing bits outside the new frame', sorted(want)[:3]))
    if want - lit:
        f.append(('pixels drawn by the original but not by the sprite', len(want - lit)))
    for x, yy in lit:
        if not box(x, yy):
            f.append(('sprite pixel outside the frame', x, yy))
            break
        a = 0x4000 | ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2) | (x >> 3)
        if not o[a] & (128 >> (x & 7)):
            f.append(('sprite pixel not in the original plot', x, yy))
            break
    return f, len(lit)


def _visible_ok(world):
    """In-use entries have 4 visible sprites, free entries none; count == V_CNT."""
    used = {e[0] for e in world.entries()}
    bad = []
    for i in range(NENT):
        for k in range(4):
            vis = bool(world.ns.attr[4 * i + k][3] & 0x80)
            if vis != (i in used):
                bad.append((i, k, vis))
    if world.ram[V_CNT - RAM_LO] != len(used):
        bad.append(('V_CNT', world.ram[V_CNT - RAM_LO], len(used)))
    return bad


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from skoolkit.pagingtracer import Memory
    MG, MS = Memory.__getitem__, Memory.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    rom_img = patch.rom_image()
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'sim': None, 'frame': 0}
    world = World(patch)
    cnt = collections.Counter()
    WATCH = set(SITES_ORIG) | set(INTERIORS)
    states = []
    ghost = collections.Counter()

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class HookMem(Memory):
        def __setitem__(s, a, v):
            a &= 0xFFFF
            if st['sim'] is not None:
                if a in site_bytes:
                    fail('game wrote a patch site', (a,))
                if RAM_LO <= a < RAM_HI or TAIL_ADDR <= a < TAIL_ADDR + 80:
                    fail('game wrote hook RAM / tail', (a,))
            MS(s, a, v)

        def __getitem__(s, a):
            a &= 0xFFFF
            if st['sim'] is not None:
                if RAM_LO <= a < RAM_HI or TAIL_ADDR <= a < TAIL_ADDR + 80:
                    fail('game read hook RAM / tail', (a,))
                elif ROM_ORG <= a < patch.altrom[1]:
                    fail('game read the alt-ROM hook range', (a, st['sim'].registers[24]))
            return MG(s, a)

    def event(pc, real, R):
        get = lambda a: MG(real, a)
        if pc == 39120:
            ix = R[8] * 256 + R[9]
            sp0 = R[12]
            ret = get(sp0) | get((sp0 + 1) & 0xFFFF) << 8
            if collect and ix in CONV and c['collected'] < collect:
                c['collected'] += 1
                states.append((list(R), [bytes(b) for b in real.banks], real.o7ffd, bytes(world.ram),
                               [list(a) for a in world.ns.attr], bytes(world.ns.pat)))
            nb = world.entries()
            full0 = world.ram[V_CNT - RAM_LO] >= NENT
            so, o, sp_, p, err = _pair(patch, world, get, R, ret, rom_img, (sp0 + 2) & 0xFFFF)
            for e in err:
                fail('plot: %s' % (e,))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            if diff:
                fail('plot: registers differ', (diff, [ro[i] for i in diff], [rp[i] for i in diff]))
            conv = p.conv                   # the patched side set V_ON (main path, converted)
            if conv and ix not in CONV:
                fail('plot: converted a descriptor outside the list', (ix,))
            f, npx = check_plot(get, o, p, world, ix, conv, nb)
            for k in f:
                fail('plot: %s' % k[0], k[1:])
            vb = _visible_ok(world)
            if vb:
                fail('sprite visibility / table', vb[:3])
            if conv:
                c['converted'] += 1
                c['sprite pixels compared'] += npx
            elif ix in CONV:
                c['figure plot on the ULA (edge/clip path or table full)'] += 1
                if full0 and world.ram[V_FREED - RAM_LO] >= NENT:
                    c['figure plot on the ULA: table full'] += 1
            else:
                c['other plot (unchanged)'] += 1
            c['max entries'] = max(c['max entries'], len(world.entries()))
        elif pc in (27468, 30597):
            stopa = 27472 if pc == 27468 else 30600
            so, o, sp_, p, err = _pair(patch, world, get, R, stopa, rom_img)
            for e in err:
                fail('clear %d: %s' % (pc, e))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            if diff or o.ov != p.ov:
                fail('clear %d: registers/memory differ' % pc, (diff,))
            vb = _visible_ok(world)
            if vb:
                fail('sprite visibility / table', vb[:3])
            c['clear %d' % pc] += 1

    def frame_end(real):
        # ghost metric: lit sprite pixels the original screen does not show at frame end
        b5 = real.banks[5]
        for e in world.entries():
            lit = miss = 0
            for k in range(4):
                px = world.ns.sprite_pixels(4 * e[0] + k) or []
                for x, yy, v in px:
                    if v and 0 <= x < 256 and 0 <= yy < 192:
                        lit += 1
                        a = ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2) | (x >> 3)
                        if not b5[a] & (128 >> (x & 7)):
                            miss += 1
            ghost['sprite-frames'] += 1
            if lit and miss * 2 > lit:
                ghost['sprite-frames mostly covered/erased on the original'] += 1

    class S(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            memory.__class__ = HookMem
            super().__init__(memory, registers, state_, config)
            st['sim'] = self
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(f):
                def g():
                    pc = R[24]
                    if pc in WATCH:
                        cnt[pc] += 1
                        if pc == INIT:
                            fail('game entry 25630 executed during the recording (re-init)')
                        if pc in (39120, 27468, 30597):
                            event(pc, mem, R)
                    f()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame
    _wp = rzxplay.RZXTracer.write_port

    def write_port(self, registers, port, value, offset=0):
        if port & 0x8002 == 0:
            c['7FFD writes'] += 1
            if not value & 0x10:
                fail('7FFD write selects ROM 0 (alt ROM image 1 hooks unreachable)', (value,))
        return _wp(self, registers, port, value, offset)

    def next_frame(self):
        st['frame'] += 1
        if st['sim'] is not None:
            frame_end(st['sim'].memory)
        if progress and st['frame'] % 500 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator, _wp)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.RZXTracer.write_port = write_port
    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator, rzxplay.RZXTracer.write_port = old
    # patched instructions: their interiors must only be reached by falling through the original
    for a, b in ((39366, 39369), (39529, 39532), (40955, 40958), (27468, 27470)):
        if cnt[b] and cnt[a] != cnt[b] and a != 27468:
            c['%d reached other than from %d!' % (b, a)] += 1
    c['frames'] = st['frame']
    c.update(ghost)
    return (c, dict(ex), states) if collect else (c, dict(ex))



# ---------------------------------------------------------------------------------------------
# Unit tests: guard edges (converted vs passthrough must match the guard), table full, a
# descriptor outside the list, a non-figure page, and a negative control (broken patch tables)
# ---------------------------------------------------------------------------------------------

RUN_HI = 0x5D00                             # run-time state (V_*, entries, hook stack) ends here
V_SP_LO, STK_LO = 0x5C00, ENT + 8 * NENT        # V_SP and the hook stack hold stale values


def _restore(patch, saved_ram, attrs, pat):
    """Patched world for a captured state: run-time state from the capture, tables (zero page,
    nibble table) from the patch itself (so a broken patch is tested with its own tables)."""
    w = World(patch)
    w.ram[:RUN_HI - RAM_LO] = saved_ram[:RUN_HI - RAM_LO]
    w.ns.attr = [list(a) for a in attrs]
    w.ns.pat = bytearray(pat)
    return w


def _main_visited(get, regs, ret, sp_ret):
    """Run the ORIGINAL call alone and report whether it took the main path (PC 39370)."""
    from .build import rom48
    rom = rom48()
    Sim = _sim_class()

    class M:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return v if v is not None else (rom[a] if a < 0x4000 else get(a))

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536
    sim = _machine(Sim, M(), list(regs), NextState(type('P', (), {'scratch': bytes(8192)})()))
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    seen = False
    n = 0
    while not (R[24] == ret and R[12] == sp_ret):
        if R[24] == 39370:
            seen = True
        ops[mem[R[24]]]()
        n += 1
        if n > 400000:
            break
    return seen


def unit_tests(patch, states, neg=None):
    from .rainbow import _BankMem
    from .build import rom48
    rom = rom48()
    rom_img = patch.rom_image()
    c = collections.Counter()
    ex = collections.defaultdict(list)

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 4:
            ex[k].append(info)

    def one(pt, regs, banks, o7, ram, attrs, pat, edit=None, label=''):
        bm = _BankMem(banks, o7, rom)
        ov = {}
        if edit:
            ov.update(edit)
        get = lambda a: ov[a] if a in ov else bm[a]
        ix = regs[8] * 256 + regs[9]
        sp0 = regs[12]
        ret = get(sp0) | get((sp0 + 1) & 0xFFFF) << 8
        w = _restore(pt, ram, attrs, pat)
        nb = w.entries()
        so, o, sp_, p, err = _pair(pt, w, get, regs, ret, pt.rom_image(), (sp0 + 2) & 0xFFFF)
        f = list(err)
        diff = [i for i in CMP if so.registers[i] != sp_.registers[i]]
        if diff:
            f.append(('registers differ', diff))
        cf, npx = check_plot(get, o, p, w, ix, p.conv, nb)
        f += cf
        vb = _visible_ok(w)
        if vb:
            f.append(('visibility', vb[:2]))
        main = _main_visited(get, regs, ret, (sp0 + 2) & 0xFFFF)
        full = ram[V_CNT - RAM_LO] >= NENT
        step = (get(ix + 4) - get(ix + 0)) & 0xFF
        dy = abs(get(ix + 5) - get(ix + 1))
        want = ix in CONV and main and not full and get(ix + 7) < 32 and step in (0, 1, 0xFF) \
            and dy < get(ix + 10)
        if p.conv != want:
            f.append(('guard mismatch', label, p.conv, want))
        return f, p.conv, npx

    for si, (R, banks, o7, ram, attrs, pat) in enumerate(states):
        ix = R[8] * 256 + R[9]
        # 1. sweep the new position / height (edges, window, off-screen), the column step (old
        #    column = new - step: -1/0/+1 are the game's, 2 must stay on the ULA) and the row step
        #    (old y = new - dy: |dy| < row pairs is the game's, dy = row pairs must stay on the ULA)
        for col in (0, 1, 14, 28, 29, 30, 31, 255):
            for step in (-1, 0, 1, 2):
                for y in (4, 5, 47, 85, 90, 95, 96):
                    for n10 in (2, 10):
                        for dy in (-1, 1, n10):
                            ed = {ix + 0: (col - step) & 0xFF, ix + 4: col,
                                  ix + 1: (y - dy) & 0xFF, ix + 5: y, ix + 10: n10}
                            f, conv, npx = one(patch, R, banks, o7, ram, attrs, pat, ed,
                                               ('pos', col, step, y, n10, dy))
                            c['cases'] += 1
                            c['converted' if conv else 'passthrough'] += 1
                            c['pixels'] += npx
                            if abs(step) == 2 or dy == n10:
                                c['step guard cases'] += 1
                            for k in f:
                                fail('pos: %s' % (k[0],), (si, col, step, y, n10, dy) + tuple(k[1:]))
        # 2. table full: 12 entries in use with keys that match nothing -> passthrough
        r2 = bytearray(ram)
        for i in range(NENT):
            r2[ENT - RAM_LO + 8 * i:ENT - RAM_LO + 8 * i + 8] = bytes([1, 0x34, 0x12, 200, 200, 0, 20, 0])
        r2[V_CNT - RAM_LO] = NENT
        a2 = [list(a) for a in attrs]
        for s_ in range(4 * NENT):
            a2[s_][3] |= 0x80
        f, conv, _ = one(patch, R, banks, o7, bytes(r2), a2, pat, None, 'full')
        c['table-full cases'] += 1
        if conv:
            fail('table full: converted', (si,))
        for k in f:
            fail('full: %s' % (k[0],), (si,) + tuple(k[1:]))
        # 3. a descriptor outside the list (explosion slot 63574 with this descriptor's bytes)
        bm = _BankMem(banks, o7, rom)
        ed = {63574 + k: bm[ix + k] for k in range(20)}
        R3 = list(R)
        R3[8], R3[9] = 63574 >> 8, 63574 & 255
        f, conv, _ = one(patch, R3, banks, o7, ram, attrs, pat, ed, 'other ix')
        c['other-descriptor cases'] += 1
        if conv:
            fail('other descriptor: converted', (si,))
        for k in f:
            fail('other ix: %s' % (k[0],), (si,) + tuple(k[1:]))
        # 4. a page outside the figure pages (0xC0xx): passthrough
        f, conv, _ = one(patch, R, banks, o7, ram, attrs, pat, {ix + 7: 32}, 'page 32')
        c['page-guard cases'] += 1
        if conv:
            fail('page 32: converted', (si,))
        for k in f:
            fail('page: %s' % (k[0],), (si,) + tuple(k[1:]))
        # 5. negative control: the broken patch (its own tables) must be caught by the pixel check
        if neg is not None:
            f, conv, _ = one(neg, R, banks, o7, ram, attrs, pat, None, 'neg')
            if conv:
                c['negative control cases'] += 1
                if any('pixels' in str(k[0]) or 'sprite pixel' in str(k[0]) for k in f):
                    c['negative control detected'] += 1
    return c, dict(ex)


def init_tests(patch, z80, neg=None, n=16, seed=1):
    """e_init (25630) from the loader snapshot's own RAM (BASIC sysvars + program in the hook
    area), random registers/flags, all sprites visible: registers as the original JP, no memory
    outside the hook RAM written, hook RAM = the model's start state (except V_SP and the hook
    stack), sprites 0..4*NENT-1 hidden. neg: a broken patch whose result must be caught."""
    import random
    from .rainbow import _BankMem
    from .build import rom48
    from . import z80tonex as zt
    zs = zt.Z80Snapshot(z80)
    bm = _BankMem([bytes(zs.banks[i]) for i in range(8)], zs.port7ffd, rom48())
    get = lambda a: bm[a]
    rnd = random.Random(seed)
    c = collections.Counter()
    ex = []
    loose = set(range(V_SP_LO, V_SP_LO + 2)) | set(range(STK_LO, RUN_HI))

    def run(pt, regs):
        w = World(pt)
        w.ram[:] = bytes(get(a) for a in range(RAM_LO, RAM_HI))
        for i in range(128):
            w.ns.attr[i][3] |= 0x80
        so, o, sp_, p, err = _pair(pt, w, get, regs, INIT_TO, pt.rom_image())
        f = list(err)
        diff = [i for i in CMP if so.registers[i] != sp_.registers[i]]
        if diff:
            f.append(('registers differ', diff))
        if o.ov or p.ov:
            f.append(('memory written outside the hook RAM', sorted(set(o.ov) | set(p.ov))[:4]))
        bad = [RAM_LO + i for i in range(RAM_HI - RAM_LO)
               if RAM_LO + i not in loose and w.ram[i] != patch.ram[i]]
        if bad:
            f.append(('hook RAM differs from the start state', len(bad), bad[:4]))
        vis = [i for i in range(4 * NENT) if w.ns.attr[i][3] & 0x80]
        if vis:
            f.append(('sprites left visible', vis[:4]))
        return f

    for k in range(n):
        regs = [0] * 29
        for i in CMP + [15]:
            regs[i] = rnd.randrange(65536 if i in (12, 24) else 256)
        regs[24], regs[12] = INIT, 25064             # the entry's SP (boot simulation)
        f = run(patch, regs)
        c['init cases'] += 1
        if f:
            c['init failures!'] += 1
            if len(ex) < 4:
                ex.append(f)
        if neg is not None:
            c['init negative control cases'] += 1
            if run(neg, regs):
                c['init negative control detected'] += 1
    return c, ex


def negative_patch():
    """Broken copy: nibble table with ink and transparent swapped (pixel check must fail)."""
    return CommandoPatch(swap_nibt=True)


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    say('Game      : %s' % name)
    say('Engine    : commando (Commando: differential OR plotter, player/soldiers/POWs -> sprites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    zt.convert(z80, plain, TAIL_ADDR, quiet=True)
    bad = boot_check(plain, z80)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X, never read or written in the RZX)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = CommandoPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch)
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    states = []
    for r in list(a.rzx or []):
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        nsnap = sum(1 for b in parse_rzx(r) if isinstance(b.obj, SS))
        if nsnap > 1:
            s2 = os.path.join(out, os.path.splitext(os.path.basename(r))[0] + '_stripped.rzx')
            RZ.strip(r, s2)
            say('RZX       : %s had %d autosave snapshots -> %s' % (os.path.basename(r), nsnap - 1,
                                                                   os.path.basename(s2)))
            r = s2
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=12)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, %d plots converted, %d on the ULA (edge/clip; %d of them table '
            'full), %d other plots, %d clears, max %d figures, %d sprite pixels -> %s' % (
                os.path.basename(r), c['frames'], c['converted'],
                c['figure plot on the ULA (edge/clip path or table full)'],
                c['figure plot on the ULA: table full'], c['other plot (unchanged)'],
                c['clear 27468'] + c['clear 30597'], c['max entries'], c['sprite pixels compared'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('            sprite-frames %d, mostly covered/erased on the original %d (scenery/bullets '
            'drawn over a figure)' % (c['sprite-frames'],
                                      c['sprite-frames mostly covered/erased on the original']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    ic, iex = init_tests(patch, z80, negative_patch())
    iok = not ic['init failures!'] and ic['init negative control detected'] == ic['init negative control cases']
    ok = ok and iok
    say('Init      : e_init (25630) from the loader RAM, %d cases, negative control %d/%d -> %s' % (
        ic['init cases'], ic['init negative control detected'], ic['init negative control cases'],
        'PASS' if iok else 'FAIL %s' % str(iex)[:300]))
    if states:
        u, uex = unit_tests(patch, states, negative_patch())
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        neg_ok = u['negative control cases'] and u['negative control detected'] == u['negative control cases']
        ok = ok and not uf and neg_ok
        say('Unit      : %d position cases (%d converted, %d passthrough, %d step guard), %d '
            'table-full, %d other-descriptor, %d page-guard, negative control %d/%d -> %s' % (
                u['cases'], u['converted'], u['passthrough'], u['step guard cases'],
                u['table-full cases'],
                u['other-descriptor cases'], u['page-guard cases'], u['negative control detected'],
                u['negative control cases'], 'PASS' if not uf and neg_ok else 'FAIL %s' % uf))
        for k, v in uex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
