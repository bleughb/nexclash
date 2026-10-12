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
RAM_LO, RAM_HI = 0x5C00, 0x5F60             # hook state (never read/written by the game once it runs)
DEPTH_LO, DT, NTYPES = 0x3000, 0x3400, 41      # alt ROM: depth code, depth table (game never reads ROM there)
DEPTH_HI = DT + 8 * NTYPES
SCRATCH_LO = 0x5E20                          # occlusion mask + depth temps: written before read
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

    def __init__(self, prof=None, swap_nibt=False, dtab=None):
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
        self.depth = bytes.fromhex(h['depth'])
        self.dtab = bytes.fromhex(self.prof['depth_table']) if dtab is None else dtab
        if DEPTH_LO + len(self.depth) > DT or len(self.dtab) != 8 * NTYPES:
            raise ValueError('depth code / table size')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (DEPTH_LO, self.regblock + 20)
        from .build import rom48
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        page[DEPTH_LO - 0x2000:DEPTH_LO - 0x2000 + len(self.depth)] = self.depth
        page[DT - 0x2000:DT - 0x2000 + len(self.dtab)] = self.dtab
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


# ---------------------------------------------------------------------------------------------
# The reference .z80 is the 128K BASIC loader (line 30). 128K BASIC pages ROM 0 (the 128K editor)
# on every statement; a Next has no such ROM 0 (and alt ROM image 0 is not filled), so a .nex
# made from the loader crashes once a key is pressed. The game itself only selects ROM 1. So the
# loader is run here, with the real 128K ROMs and the keys of Dean's recording (SPACE for PAUSE 0,
# N for "INFY LIVES"), up to the game entry 25088 after its DI, and the .nex is built from there.
# ---------------------------------------------------------------------------------------------

ENTRY = 25088                                   # USR target: DI / page bank 1 / JP 25630
LOADER_PC = 7997                                # ROM PAUSE in the loader snapshot


def is_loader(snap):
    return snap.pc < 0x4000 and snap.memory[ENTRY] == 0xF3


def advance_loader(z80, out_path, lives='N', max_frames=400):
    """Run the loader snapshot to PC ENTRY+1 (after the DI) and write that state as a .z80.
    Keys: SPACE frames 5-14 (PAUSE 0), then `lives` (N/Y) from frame 30 until the game entry.
    Returns (frame, registers dict). Deterministic (fixed key schedule, Python simulator)."""
    from skoolkit.snapshot import Snapshot, write_snapshot
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot, get_state, PC, T, IFF
    ft = 70908                                  # 128K frame
    rows = {0x7F: ' \x00MNB', 0xDF: 'POIUY', 0xBF: '\nLKJH', 0xFE: '\x01ZXCV'}
    s = Snapshot.get(z80)
    if not is_loader(s) or s.pc != LOADER_PC:
        raise ValueError('not the Commando BASIC-loader snapshot (PC %d)' % s.pc)
    sim = from_snapshot(Simulator, s, config={'int_active': 0})
    mem, R, ops = sim.memory, sim.registers, sim.opcodes
    st = {'held': ''}

    class Tr:
        border, outfe, outfffd, ay = s.border, s.border, 0, [0] * 16
        out7ffd = mem.o7ffd

        def read_port(self, regs, port):
            v = 0xFF
            if port & 1 == 0:
                for row, ks in rows.items():
                    if (port >> 8) & (row ^ 0xFF) == 0:
                        for i, ch in enumerate(ks):
                            if ch in st['held']:
                                v &= ~(1 << i)
            return v

        def write_port(self, regs, port, value, offset=0):
            if port & 1 == 0:
                self.border, self.outfe = value & 7, value
            if port & 0x8002 == 0 and self.out7ffd & 32 == 0:
                mem.out7ffd(value)
                self.out7ffd = value
    sim.set_tracer(Tr())
    for f in range(max_frames):
        st['held'] = ' ' if 5 <= f < 15 else (lives.upper() if f >= 30 else '')
        while R[T] < ft:
            if R[PC] == ENTRY + 1:
                entry = ([bytes(b) for b in mem.banks], list(R))
                make_front(s, mem, R)
                ram, regs, state, machine = get_state(sim)
                write_snapshot(out_path, ram, regs, state, machine)
                return f, {'pc': ENTRY + 1, 'sp': R[12], 'iff': R[IFF], 'im': R[27], '7ffd': mem.o7ffd,
                           'entry': entry}
            ops[mem[R[PC]]]()
        R[T] -= ft
        if R[IFF]:
            if mem[R[PC]] == 0x76:
                R[PC] = (R[PC] + 1) & 0xFFFF
            sim.accept_interrupt(R, mem, 0)
    raise ValueError('the loader did not reach the game entry %d in %d frames' % (ENTRY, max_frames))


FRONT, F_PIX, F_ATT, F_END = 0x5D00, 0x5D80, 0x5E00, 0x5E20


def make_front(orig, mem, R):
    """Entry state -> start state: the prompt cells (row 0, columns 0-15) back to the loading
    screen, their printed pixels/attributes stored for the front end, front end at 0x5D00, PC there."""
    code = bytes.fromhex(load_profile()['hooks']['front'])
    cells = {0x4000 + 256 * k + c for k in range(8) for c in range(16)} | {0x5800 + c for c in range(16)}
    diff = [a for a in range(0x4000, 0x5B00) if mem[a] != orig.memory[a]]
    if any(a not in cells for a in diff):
        raise ValueError('the loader changed the screen outside the prompt: %s' % diff[:4])
    pix = bytes(mem[0x4000 + 256 * k + c] for k in range(8) for c in range(16))
    att = bytes(mem[0x5800 + c] for c in range(16))
    for a in cells:
        mem[a] = orig.memory[a]
    for i, v in enumerate(code + bytes(F_PIX - FRONT - len(code)) + pix + att):
        mem[FRONT + i] = v
    R[24] = FRONT


def front_tests(start_z80, entry):
    """Run the front end from the start snapshot with N and with Y (after a key for PAUSE 0):
    it must reach 25089 with every register (R aside) and all RAM as the loader's entry state,
    except 0x5D00-0x5E1F (front end, never used by the game) and, for Y, 27653 = 182."""
    from skoolkit.snapshot import Snapshot
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot, PC
    banks0, regs0 = entry
    out = {}
    for key, row, bit in (('N', 0x7F, 3), ('Y', 0xDF, 4)):
        sim = from_snapshot(Simulator, Snapshot.get(start_z80), config={'int_active': 0})
        R, mem, ops = sim.registers, sim.memory, sim.opcodes
        n = [0]

        class Tr:
            border = outfe = outfffd = 0
            ay = [0] * 16

            def read_port(self, regs, port):
                n[0] += 1
                if n[0] < 20 or port & 1:
                    return 0xFF                     # nothing held at first
                if n[0] < 40:
                    return 0xFF & ~(1 if (port >> 8) & 0x7F == 0 else 0)   # SPACE (all-rows read)
                if (port >> 8) == row:
                    return 0xFF & ~(1 << bit)
                return 0xFF

            def write_port(self, regs, port, value, offset=0):
                pass
        sim.set_tracer(Tr())
        steps = 0
        while R[PC] != ENTRY + 1 and steps < 200000:
            ops[mem[R[PC]]]()
            steps += 1
        bad = []
        if R[PC] != ENTRY + 1:
            bad.append('did not reach 25089')
        bad += ['register %d' % i for i in CMP if i != 24 and R[i] != regs0[i]]
        want = {27653: 182} if key == 'Y' else {}
        for b in range(8):
            base = {5: 0x4000, 2: 0x8000}.get(b)
            for i in range(16384):
                a = (base + i) if base else None
                v = mem.banks[b][i]
                exp = want.get(a, banks0[b][i]) if a is not None else banks0[b][i]
                if v != exp and not (a is not None and FRONT <= a < F_END):
                    bad.append(('ram', b, i))
                    break
        out[key] = bad
    return out


# ---------------------------------------------------------------------------------------------
# Depth (Dean's rule): the game's walk-blocking boxes decide whether a figure is in front of or
# behind a scenery object. The table is derived from the game by running its own object drawer
# (37302) and box builder (60754) on one object of each type, from an in-game state.
# ---------------------------------------------------------------------------------------------

def _signed(v):
    return v - 256 if v > 127 else v


def derive_table(banks, o7ffd, y=80):
    """41 x 8 bytes: per type +0 bit 0 has a walk box, +1/+2 first/last column, +3/+4 first/last
    line (signed, relative to column x&31 and line 2y), +5 box middle (2-line units, rel. y) + 64.
    Walk boxes = collision entries the game tests when walking (57143/57139: bit 7 clear = box,
    0x82 = box with a counter, 0x84 = sloped box (57278); 0x81 only in a non-walking mode)."""
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_memory
    from skoolkit.pagingtracer import Memory as PM
    base = [bytes(b) for b in banks]
    m0 = PM([list(b) for b in base], o7ffd, '128K')
    p = m0[32778] | m0[32779] << 8
    first_e, a = {}, p
    for _ in range(4000):
        t, e = m0[a] & 0x7F, m0[a + 1]
        a += 2
        if t == 127:
            break
        if 1 <= t <= 40 and t != 34:
            first_e.setdefault(t, e)
    stop = ENTRY

    def run(t, x, entry):
        mem = PM([list(b) for b in base], o7ffd, '128K')
        sim = from_memory(Simulator, mem, {'IY': 64896, 'SP': 0x5EFE, 'PC': entry},
                          {'iff': 0, 'im': 2}, {'int_active': 0})
        R = sim.registers

        class Tr:
            border = outfe = outfffd = 0
            ay = [0] * 16

            def read_port(self, r, port):
                return 0xFF

            def write_port(self, r, port, v, o=0):
                if port & 0x8002 == 0:
                    mem.out7ffd(v)
        sim.set_tracer(Tr())
        for i in range(0x4000, 0x5800):
            mem[i] = 0
        mem[0xFF00] = 0x08
        for k, v in enumerate((0x08, 0, t, x, y, 0, 0, 0)):
            mem[0xFF08 + k] = v
        mem[64904] = 0x08
        mem[0x5EFE], mem[0x5EFF] = stop & 255, stop >> 8
        n = 0
        while R[24] != stop and n < 300000:
            sim.opcodes[mem[R[24]]]()
            n += 1
        return mem
    tab = bytearray(8 * NTYPES)
    for t in range(1, NTYPES):
        x = first_e.get(t, 16)
        mem = run(t, x, 37302)
        pts = [(o & 31, ((o >> 8) & 7) | ((o >> 2) & 0x38) | ((o >> 5) & 0xC0))
               for o in range(6144) if mem[0x4000 + o]]
        mem2 = run(t, x, 60754)
        boxes, a = [], 0xF900
        while mem2[a] != 0x80 and a < 0xF9F0:
            c, w, by, h = (mem2[a + k] for k in range(4))
            a += 4
            if c & 0x80 and not c & 6:              # 0x81 entries: tested only in a non-walking mode
                continue
            boxes.append((by - y - h, by - y))
        if not pts or not boxes:
            continue
        top, bot = min(b[0] for b in boxes), max(b[1] for b in boxes)
        ent = (1, min(q[0] for q in pts) - (x & 31), max(q[0] for q in pts) - (x & 31),
               min(q[1] for q in pts) - 2 * y, max(q[1] for q in pts) - 2 * y, (top + bot) // 2 + 64)
        tab[8 * t:8 * t + 6] = bytes(v & 255 for v in ent)
    return bytes(tab)


def occluded(get, scr, ix, dtab):
    """Model of the rule for a converted plot (descriptor after the plot): the set of screen pixels
    (x, line) inside the figure's 24 x rows box that belong to objects it is behind. scr(a) = the
    screen as the hook sees it (after the plot)."""
    out = set()
    last = get(64904)
    if not last:
        return out
    col, fy, pairs = get(ix + 0), get(ix + 1), get(ix + 10)
    feet, fl0 = fy + 6, 2 * fy                  # the game's walk-test point (y + 6), not the feet
    fl1 = min(191, fl0 + 2 * pairs - 1)
    e, n = get(0xFF00), 0
    while n < 64:
        n += 1
        a = 0xFF00 + e
        t = get(a + 2) & 0x7F
        if 1 <= t < NTYPES and dtab[8 * t] & 1:
            ox, oy = get(a + 3) & 31, get(a + 4)
            c0, c1, l0, l1 = (_signed(dtab[8 * t + k]) for k in (1, 2, 3, 4))
            mid = dtab[8 * t + 5] - 64
            if feet <= oy + mid:                    # reached from above: figure behind
                for line in range(max(fl0, 2 * oy + l0), min(fl1, 2 * oy + l1) + 1):
                    for cx in range(max(col, ox + c0), min(col + 2, ox + c1) + 1):
                        ad = 0x4000 | ((line & 0xC0) << 5) | ((line & 7) << 8) | ((line & 0x38) << 2) | cx
                        v = scr(ad)
                        for b in range(8):
                            if v & (128 >> b):
                                out.add((cx * 8 + b, line))
        if e == last:
            break
        e = get(a)
    return out


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


def check_plot(get, o, p, world, ix, conv, n_before_ent, dtab=None):
    """Screen and sprite checks for one plot call. Returns ([failures], pixels compared)."""
    f = []
    keys = set(o.ov) | set(p.ov)
    scr = [a for a in keys if 0x4000 <= a < 0x5800]
    other = [a for a in keys if not 0x4000 <= a < 0x5800 and o[a] != p[a]]
    if other:
        f.append(('memory differs', sorted(other)[:4]))
    # converted plot whose old image was a sprite: svsave/svrest leave the ULA exactly as before the
    # plot; the original's erase holes (old-frame bits) may then exceed it inside the old frame only
    pc0, py0, pp = get(ix + 0), get(ix + 1), 2 * get(ix + 10)
    found = conv and pc0 < 30 and any(e[1] == ix and e[2] == pc0 and e[3] == py0
                                      for e in (n_before_ent or ()))
    if found:
        changed = [a for a in scr if p[a] != get(a)]
        if changed:
            f.append(('converted plot changed the ULA (scenery not restored)', sorted(changed)[:4]))

    def in_old(a):
        cx, ly = _scr_xy(a)
        return pc0 <= cx < pc0 + 3 and 2 * py0 <= ly < 2 * py0 + pp
    extra = [a for a in scr if p[a] & ~o[a] and not (found and in_old(a))]
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
    occ = occluded(lambda a: o[a], lambda a: p[a], ix, dtab) if dtab is not None else set()
    if (want - occ) - lit:
        f.append(('pixels drawn by the original but not by the sprite', len((want - occ) - lit)))
    if lit & occ:
        f.append(('sprite shows pixels of scenery it is behind', len(lit & occ)))
    world.occluded = getattr(world, 'occluded', 0) + len(occ)    # scenery pixels in front of it
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


def verify(patch, rzx_path, stop=None, collect=0, progress=None, dtab=None):
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
                elif patch.altrom[0] <= a < patch.altrom[1]:
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
            f, npx = check_plot(get, o, p, world, ix, conv, nb, dtab)
            if conv and get(ix + 0) < 30 and any(e[1] == ix and e[2] == get(ix + 0) and e[3] == get(ix + 1)
                                               for e in nb):
                c['converted, scenery restored (old image a sprite)'] += 1
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
    c['occluded pixels'] = getattr(world, 'occluded', 0)
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


def _with_entry(ram, attrs, ix, col, y, pairs):
    """Run-time state with a sprite entry for (ix, col, y) - the old image already a sprite - if
    there is none (captured states are often a figure's first plot)."""
    r = bytearray(ram)
    a2 = [list(a) for a in attrs]
    for i in range(NENT):
        e = r[ENT - RAM_LO + 8 * i:ENT - RAM_LO + 8 * i + 8]
        if e[0] and e[1] | e[2] << 8 == ix and e[3] == col and e[4] == y:
            return bytes(r), a2
    for i in range(NENT):
        if not r[ENT - RAM_LO + 8 * i]:
            r[ENT - RAM_LO + 8 * i:ENT - RAM_LO + 8 * i + 8] = bytes([1, ix & 255, ix >> 8, col, y, 0,
                                                                     2 * pairs, 0])
            r[V_CNT - RAM_LO] += 1
            for k in range(4):
                a2[4 * i + k][3] |= 0x80
            return bytes(r), a2
    return bytes(r), a2


def unit_tests(patch, states, neg=None, dtab=None, neg_depth=None, neg_restore=None):
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
        cf, npx = check_plot(get, o, p, w, ix, p.conv, nb, dtab)
        c['occluded'] += getattr(w, 'occluded', 0)
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
        # 6. depth: one object of a solid type over the figure's new box, its box middle swept around
        #    the figure's walk-test point (y + 6); ink in the overlap so 'behind' has pixels to hide.
        #    Negative control: the same case with no walk boxes must show scenery-covered pixels.
        bm = _BankMem(banks, o7, rom)
        col, fy, pairs = bm[ix + 4], bm[ix + 5], bm[ix + 10]
        if col < 30 and 4 <= fy < 96 and ix in CONV and dtab is not None:
            ram6, attrs6 = _with_entry(ram, attrs, ix, bm[ix + 0], bm[ix + 1], pairs)
            ink = {}
            for line in range(2 * fy, min(192, 2 * fy + 2 * pairs)):
                for cx in range(col, col + 3):
                    ink[0x4000 | ((line & 0xC0) << 5) | ((line & 7) << 8) | ((line & 0x38) << 2) | cx] = 0x5A
            for t in (1, 2, 3, 7, 9, 11, 20, 24, 35):
                mid = dtab[8 * t + 5] - 64
                for rel in (-6, -1, 0, 1, 6):
                    oy = (fy + 6 - mid + rel) & 0xFF
                    ed = dict(ink)
                    ed.update({0xFF00: 0x08, 0xFF08: 0x08, 0xFF0A: t, 0xFF0B: (col + 1) & 31, 0xFF0C: oy,
                               64904: 0x08})
                    w0 = c['occluded']
                    f, conv, npx = one(patch, R, banks, o7, ram6, attrs6, pat, ed, ('depth', t, rel))
                    c['depth cases'] += 1
                    if conv:
                        c['depth cases converted'] += 1
                        if c['occluded'] > w0:
                            c['depth cases behind (pixels hidden)'] += 1
                    for k in f:
                        fail('depth: %s' % (k[0],), (si, t, rel) + tuple(k[1:]))
                    if neg_depth is not None and conv and c['occluded'] > w0:
                        f2, _, _ = one(neg_depth, R, banks, o7, ram6, attrs6, pat, ed, 'negd')
                        c['depth negative control cases'] += 1
                        if any('behind' in str(k[0]) for k in f2):
                            c['depth negative control detected'] += 1
        # 7. scenery restore: on the captured state itself, svrest disabled must be caught wherever
        #    the plot is converted and its old image was a sprite
        if neg_restore is not None and ix in CONV:
            bm7 = _BankMem(banks, o7, rom)
            ram7, attrs7 = _with_entry(ram, attrs, ix, bm7[ix], bm7[ix + 1], bm7[ix + 10])
            ink7 = {}                               # scenery under the old image for the erase to cut
            for line in range(2 * bm7[ix + 1], min(192, 2 * bm7[ix + 1] + 2 * bm7[ix + 10])):
                for cx in range(bm7[ix], min(32, bm7[ix] + 3)):
                    ink7[0x4000 | ((line & 0xC0) << 5) | ((line & 7) << 8) | ((line & 0x38) << 2) | cx] = 0xA5
            f0, conv0, _ = one(patch, R, banks, o7, ram7, attrs7, pat, ink7, 'restore')
            for k in f0:
                fail('restore: %s' % (k[0],), (si,) + tuple(k[1:]))
            if conv0 and bm7[ix] < 30:
                c['restore negative control cases'] += 1
                f7, _, _ = one(neg_restore, R, banks, o7, ram7, attrs7, pat, ink7, 'negr')
                if any('not restored' in str(k[0]) for k in f7):
                    c['restore negative control detected'] += 1
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
    loose = set(range(V_SP_LO, V_SP_LO + 2)) | set(range(STK_LO, RUN_HI)) | set(range(SCRATCH_LO, RAM_HI))

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


def negative_depth_patch():
    """Broken copy: depth table with no walk boxes (figures never behind): must be caught."""
    t = bytearray(bytes.fromhex(load_profile()['depth_table']))
    for k in range(NTYPES):
        t[8 * k] = 0
    return CommandoPatch(dtab=bytes(t))


def negative_restore_patch():
    """Broken copy: svrest returns at once (scenery cut by the erase is not restored): caught."""
    pt = CommandoPatch()
    off = int(load_profile()['hooks']['syms']['svrest'], 16) - 0x2000
    page = bytearray(pt.page)
    page[off] = 0xC9
    pt.page = bytes(page)
    return pt


def negative_patch():
    """Broken copy: nibble table with ink and transparent swapped (pixel check must fail)."""
    return CommandoPatch(swap_nibt=True)


def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    say('Game      : %s' % name)
    say('Engine    : commando (Commando: differential OR plotter, player/soldiers/POWs -> sprites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    from skoolkit.snapshot import Snapshot as _S
    if is_loader(_S.get(z80)):
        ent = os.path.join(out, name + '_entry.z80')
        fr, info = advance_loader(z80, ent)
        say('Loader    : 128K BASIC loader run to the game entry (SPACE, N): frame %d, PC %d, SP %d, '
            'IM %d, IFF %d, 7FFD 0x%02X -> %s starts in the front end (no 128K BASIC on the Next)' % (fr, info['pc'], info['sp'], info['im'], info['iff'], info['7ffd'],
                           os.path.basename(ent)))
        ft = front_tests(ent, info['entry'])
        fok = not ft['N'] and not ft['Y']
        ok_front = fok
        say('Front end : loading screen -> any key -> "INFY LIVES(Y/N)?" -> Y/N -> game entry 25089 '
            '(N: state = the loader\'s; Y: also 27653 = 182) -> %s' % ('PASS' if fok else 'FAIL %s' % ft))
        z80 = ent
    else:
        ok_front = True
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
    ok = not bad and not bad2 and ok_front
    states = []
    dtab = None
    for r in list(a.rzx or [])[:1]:
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        s0 = [b.obj for b in parse_rzx(r) if isinstance(b.obj, SS)][0]
        ram = s0.ram(-1)
        dtab = derive_table([ram[k:k + 0x4000] for k in range(0, 0x20000, 0x4000)], s0.out7ffd)
        dok = dtab == patch.dtab
        ok = ok and dok
        say('Depth     : table re-derived from the game (RZX start state: drawer 37302 + box builder '
            '60754 per type) %s the profile; %d types with walk boxes -> %s' % (
                '=' if dok else '!=', sum(dtab[8 * k] & 1 for k in range(NTYPES)), 'PASS' if dok else 'FAIL'))
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
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=12, dtab=dtab)
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
        say('            %d converted plots put back the scenery their erase cut (ULA unchanged by the plot)'
            % c['converted, scenery restored (old image a sprite)'])
        say('            scenery pixels drawn in front of figures (depth rule): %d' % c['occluded pixels'])
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
        u, uex = unit_tests(patch, states, negative_patch(), dtab, negative_depth_patch(),
                            negative_restore_patch())
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        neg_ok = u['negative control cases'] and u['negative control detected'] == u['negative control cases']
        ok = ok and not uf and neg_ok
        say('Unit      : %d position cases (%d converted, %d passthrough, %d step guard), %d '
            'table-full, %d other-descriptor, %d page-guard, negative control %d/%d -> %s' % (
                u['cases'], u['converted'], u['passthrough'], u['step guard cases'],
                u['table-full cases'],
                u['other-descriptor cases'], u['page-guard cases'], u['negative control detected'],
                u['negative control cases'], 'PASS' if not uf and neg_ok else 'FAIL %s' % uf))
        dneg = u['depth negative control cases'] and \
            u['depth negative control detected'] == u['depth negative control cases']
        ok = ok and dneg and u['depth cases behind (pixels hidden)'] > 0
        say('Depth unit: %d cases (%d converted, %d behind with pixels hidden), negative control (no '
            'walk boxes) %d/%d -> %s' % (u['depth cases'], u['depth cases converted'],
                                         u['depth cases behind (pixels hidden)'],
                                         u['depth negative control detected'],
                                         u['depth negative control cases'],
                                         'PASS' if dneg and not any(k.startswith('depth') for k in uf) else 'FAIL'))
        rneg = u['restore negative control cases'] and \
            u['restore negative control detected'] == u['restore negative control cases']
        ok = ok and rneg
        say('Restore   : converted plots leave the ULA as before the plot (scenery the erase cuts is put '
            'back); negative control (restore disabled) %d/%d -> %s' % (
                u['restore negative control detected'], u['restore negative control cases'],
                'PASS' if rneg else 'FAIL'))
        for k, v in uex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
