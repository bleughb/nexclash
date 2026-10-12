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
PAGE_LO = 0x2000                            # alt ROM image 1 page we own (the game never executes ROM
                                            # and reads only page 0x00 - RZX scan)
ROM_ORG, ROM2_ORG = 0x3600, 0x3F00          # hooks: part 1 (< 0x3D00), part 2 (+ register block, < 0x4000)
TRAP_LO, TRAP_HI = 0x3D00, 0x3E00            # no code here (code there crashed 541e34e2; probable DivMMC automap, BRIEFING A1)
FILL_LO, SVR_LO = 0x3080, 0x3550            # body fill code; scenery save / restore
DT, NTYPES = 0x3400, 41                     # depth table (41 x 8, + variant table pointers)
RAM_LO, RAM_HI = 0x5C00, 0x6100             # hook state (never read/written by the game once it runs)
SCRATCH_LO = 0x5E20                          # mask, temps, save buffer, ink / fill rows: written before read
ZP = 0x5D00                                 # zero page (new frame source while converted)
INKB, FILB, MASK = 0x5F20, 0x6020, 0x5E20
V_CLK = 0x5C0E                                # last pattern slot allocated
SLOTK, NSLOT = 0x6080, 32                     # pattern-slot keys (persistent, like the entries)
ENT, NENT = 0x5C10, 12
V_ON, V_FREED, V_CNT = 0x5C04, 0x5C05, 0x5C06
TAIL_ADDR = 0x6D00                          # 0x6CB5-0x70F7: never read or written in the RZX
CONV = (23514, 23313, 23333, 23353, 23373, 23393, 64975)
PLAYER, POW = 23514, 64975
SITES_ORIG = {39120: bytes.fromhex('C32299'), 39366: bytes.fromhex('7A93EBE1'),
              39529: bytes.fromhex('ED7B82FDC9'), 40955: bytes.fromhex('ED7B82FDC9'),
              27468: bytes.fromhex('CB21CB21'), 30597: bytes.fromhex('210040'),
              25630: bytes.fromhex('C3D269'),
              39777: bytes.fromhex('D5E5B7'), 40733: bytes.fromhex('E5ED7382FD'),
              40926: bytes.fromhex('DDCB0BAE'), 40930: bytes.fromhex('DD7E06')}
SITE_SYM = {39120: 'e_ent', 39366: 'e_main', 39529: 'e_x', 40955: 'e_x', 27468: 'e_rect',
            30597: 'e_cls', 25630: 'e_init', 39777: 'e_p1', 40733: 'e_p2', 40926: 'e_p3',
            40930: 'e_p4'}
INIT, INIT_TO = 25630, 27090                 # game entry (JP 27090) -> e_init
# bytes of patched instructions that must never be a PC (interiors behind each 3-byte JP)
INTERIORS = (39369, 39532, 39533, 40958, 40959, 27471, 25631, 25632, 39778, 39779,
             40734, 40735, 40736, 40737, 40927, 40928, 40929, 40931, 40932)
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


def _derive_depth(snap):
    """(depth table with variant pointers, shape blob, model) from a game-state snapshot (the RZX's
    start snapshot): the game's own drawer + box builder per type and variant."""
    ram = snap.ram(-1)
    bks = [ram[k:k + 0x4000] for k in range(0, 0x20000, 0x4000)]
    return derive_shapes(bks, snap.out7ffd, derive_table(bks, snap.out7ffd))


def depth_profile(rzx, check=False):
    """Re-derive depth_table + shapes from the RZX's start state and compare with / write them into
    docs/profiles/commando.json (hooks untouched: those come from tools/asm2profile.py).
    Returns (same_as_profile, message)."""
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot as SS
    s0 = [b.obj for b in parse_rzx(rzx) if isinstance(b.obj, SS)][0]
    dtab, blob, model = _derive_depth(s0)
    path = _profile_path()
    text = open(path).read()
    prof = json.loads(text)
    same = prof.get('depth_table', '').upper() == dtab.hex().upper() and prof.get('shapes', '').upper() == blob.hex().upper()
    msg = 'depth table %d bytes, %d shape variants, shapes %d bytes: %s' % (
        len(dtab), len(model), len(blob), 'same as the profile' if same else 'DIFFERENT from the profile')
    if not same and not check:
        if SHAPES_LO + len(blob) > FILL_LO:
            raise ValueError('shape data %d bytes does not fit 0x%04X-0x%04X' % (len(blob), SHAPES_LO, FILL_LO))
        prof['depth_table'], prof['shapes'] = dtab.hex().upper(), blob.hex().upper()
        open(path, 'w').write(json.dumps(prof, indent=1))
        msg += ' -> written to %s' % path
    return same, msg


def identify_commando(mem):
    sg = load_profile()['signature']
    a, sig = sg['addr'], bytes.fromhex(sg['bytes'])
    return bytes(mem[a:a + len(sig)]) == sig


def is_commando(snap):
    try:
        return snap.machine != '48K' and identify_commando(mem64(snap))
    except FileNotFoundError:
        return False


YELLOW = 0xB4                               # body fill: the play area's paper (Dean)


def palette():
    pal = bytearray(256)
    for k in range(16):
        pal[16 * k + 1] = SPECCY[k]
        pal[16 * k + 2] = YELLOW
    return bytes(pal)


class CommandoPatch:
    name = 'Commando figures (player, soldiers, POWs) -> hardware sprites (altrom + bank-5 state)'

    def __init__(self, prof=None, swap_pairs=False, dtab=None, edit=None):
        """swap_pairs / dtab / edit (ROM address -> bytes): negative controls with their own data."""
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = bytes.fromhex(h['rom'])
        self.rom2_code = bytes.fromhex(h['rom2'])
        self.fill_code = bytes.fromhex(h['fill'])
        self.svr_code = bytes.fromhex(h['svr'])
        self.setup = bytes.fromhex(h['setup'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = self.setup + palette()
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.tail_addr = TAIL_ADDR
        self.max_tail = 80
        self.scratch = bytes(8192)              # (rainbow.NextState wants one; unused here)
        self.regblock = ROM2_ORG + len(self.rom2_code)
        if self.regblock + 20 > 0x4000 or ROM_ORG + len(self.rom_code) > TRAP_LO:
            raise ValueError('ROM hooks too long')
        self.dtab = bytes.fromhex(self.prof['depth_table']) if dtab is None else dtab
        self.shapes = bytes.fromhex(self.prof['shapes'])
        if len(self.dtab) != 8 * NTYPES or SHAPES_LO + len(self.shapes) > FILL_LO:
            raise ValueError('depth table / shape data size')
        if FILL_LO + len(self.fill_code) > SR_T or SVR_LO + len(self.svr_code) > ROM_ORG or DT + 8 * NTYPES > SVR_LO:
            raise ValueError('alt ROM block overlap')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (PAGE_LO, self.regblock + 20)
        from .build import rom48
        page = bytearray(rom48()[0x2000:0x4000])
        sr, sl = smear_tables()
        p0, p1 = pair_tables(swap_pairs)
        for a, data in ((SHAPES_LO, self.shapes), (FILL_LO, self.fill_code), (SR_T, sr), (SL_T, sl),
                        (DT, self.dtab), (SVR_LO, self.svr_code), (PT0, p0), (PT1, p1),
                        (ROM_ORG, self.rom_code), (ROM2_ORG, self.rom2_code)):
            page[a - 0x2000:a - 0x2000 + len(data)] = data
        for a, data in (edit or {}).items():
            page[a - 0x2000:a - 0x2000 + len(data)] = data
        self.page = bytes(page)
        self.shape_model = shapes_from_blob(self.dtab, self.shapes)
        ram = bytearray(RAM_HI - RAM_LO)        # zeros: V_*, entry table, stack, zero page
        ram[V_FREED - RAM_LO] = 0xFF
        ram[SLOTK - RAM_LO:SLOTK - RAM_LO + 4 * NSLOT] = b'\xFF' * (4 * NSLOT)
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


# Alt ROM image 1, page 0x2000-0x3FFF (the game never executes ROM and reads only page 0x00):
SHAPES_LO = 0x2000                               # per-type variant tables + shape bitmaps
SR_T, SL_T = 0x3200, 0x3300                      # smear right / left (body fill)
PT0, PT1 = 0x3D00, 0x3E00                        # (ink nibble, fill nibble) -> 2 bytes of 4-bit pixels
SHAPES_HI = SR_T


def _run_obj(base, o7ffd, t, x, y, entry, scr_fill=0):
    """One scenery object (type t, x byte, y) alone in the list; run the game's routine at entry
    (37302 drawer / 60754 box builder) from base RAM with the screen filled with scr_fill."""
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_memory
    from skoolkit.pagingtracer import Memory as PM
    mem = PM([list(b) for b in base], o7ffd, '128K')
    sim = from_memory(Simulator, mem, {'IY': 64896, 'SP': 0x5EFE, 'PC': entry}, {'iff': 0, 'im': 2},
                      {'int_active': 0})
    R = sim.registers
    R[15] = 0x80                                # masked scenery drawing (the game's play mode)

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
        mem[i] = scr_fill
    mem[0xFF00] = 0x08
    for k, v in enumerate((0x08, 0, t, x, y, 0, 0, 0)):
        mem[0xFF08 + k] = v
    mem[64904] = 0x08
    mem[0x5EFE], mem[0x5EFF] = ENTRY & 255, ENTRY >> 8
    n = 0
    while R[24] != ENTRY and n < 300000:
        sim.opcodes[mem[R[24]]]()
        n += 1
    return mem


def _shape_bits(base, o7ffd, t, x, y):
    """{(column, line): mask byte} of the object's solid shape: per byte the drawer wrote, all 8
    bits if the result does not depend on the background (opaque block), else the bits it drew or
    masked out (ink | ~AND-mask)."""
    a = _run_obj(base, o7ffd, t, x, y, 37302, 0x00)
    b = _run_obj(base, o7ffd, t, x, y, 37302, 0xFF)
    out = {}
    for o in range(6144):
        va, vb = a[0x4000 + o], b[0x4000 + o]
        if va or vb != 0xFF:
            m = 0xFF if va == vb else (va | (~vb & 0xFF))
            if m:
                out[(o & 31, ((o >> 8) & 7) | ((o >> 2) & 0x38) | ((o >> 5) & 0xC0))] = m
    return out


def body_fill(rows, nbits):
    """Reference body fill (the Z80 code computes exactly this for figures): rows = list of ints
    (bit nbits-1 = leftmost pixel). A pixel is fill when it is not ink and the row has ink at or
    left of it and at or right of it, and its column has ink in some row above and some row below.
    Returns the fill rows."""
    full = (1 << nbits) - 1
    above, acc = [], 0
    for r in rows:
        above.append(acc)
        acc |= r
    below, acc = [0] * len(rows), 0
    for i in range(len(rows) - 1, -1, -1):
        below[i] = acc
        acc |= rows[i]
    out = []
    for i, r in enumerate(rows):
        if not r:
            out.append(0)
            continue
        hi, lo = r.bit_length() - 1, (r & -r).bit_length() - 1
        span = ((1 << (hi + 1)) - 1) & ~((1 << lo) - 1) & full
        out.append(span & above[i] & below[i] & ~r & full)
    return out


def _solid(bits, w, h):
    """Shape bitmap {(byte col, line): byte} -> the same with enclosed holes filled (body_fill)."""
    rows = []
    for ll in range(h):
        v = 0
        for cc in range(w):
            v = v << 8 | bits.get((cc, ll), 0)
        rows.append(v)
    fill = body_fill(rows, 8 * w)
    out = {}
    for ll in range(h):
        v = rows[ll] | fill[ll]
        for cc in range(w):
            m = v >> (8 * (w - 1 - cc)) & 255
            if m:
                out[(cc, ll)] = m
    return out


def derive_shapes(banks, o7ffd, dtab):
    """Solid shapes of the depth objects (types with a walk box in dtab) for every x variant (x
    bits 5-7), derived from the game's own drawer: per byte it writes, all 8 bits if the result does
    not depend on the background (opaque block), else ink | ~AND-mask. Variants of a type differ
    only by a line offset, so each distinct shape is stored once.
    Returns (dtab with +6/+7 = variant table pointer, blob for SHAPES_LO, model).
    Variant table: 8 x (shape pointer lo, hi, l0 = first line relative to 2y, signed); pointer 0 =
    no shape. Shape: flags (bit 0 rectangle, bit 1 absolute column), c0 (signed, relative to the
    object column x & 31, or absolute), w (bytes), h (lines), then w*h bytes unless a rectangle.
    model[(t, v)] = (absolute, c0, l0, w, h, {(byte column, line): mask byte})."""
    base = [bytes(b) for b in banks]
    m0 = _BankMemLite(base, o7ffd)
    first_e, a = {}, m0[32778] | m0[32779] << 8
    for _ in range(4000):
        t, e = m0[a] & 0x7F, m0[a + 1]
        a += 2
        if t == 127:
            break
        if 1 <= t <= 40 and t != 34:
            first_e.setdefault(t, e)
    dt = bytearray(dtab)
    types = [t for t in range(1, NTYPES) if dt[8 * t] & 1]
    blob = bytearray(24 * len(types))                # variant tables first
    shapes, model = {}, {}
    for k, t in enumerate(types):
        vt = SHAPES_LO + 24 * k
        dt[8 * t + 6], dt[8 * t + 7] = vt & 255, vt >> 8
        c = min(first_e.get(t, 16) & 31, 20)
        best = None
        for y in range(30, 150, 4):                 # fully visible position: most pixels
            bits = _shape_bits(base, o7ffd, t, c, y)
            n = sum(bin(v).count('1') for v in bits.values())
            if best is None or n > best[0]:
                best = (n, y)
        y = best[1]
        for v in range(8):
            bits = _shape_bits(base, o7ffd, t, (v << 5) | c, y)
            if not bits:
                continue
            bits2 = _shape_bits(base, o7ffd, t, (v << 5) | (c + 2), y)
            absolute = {q for q in bits} == {q for q in bits2}
            cols, lines = [q[0] for q in bits], [q[1] for q in bits]
            c0, c1, l0, l1 = min(cols), max(cols), min(lines), max(lines)
            w, h = c1 - c0 + 1, l1 - l0 + 1
            rel = _solid({(cc - c0, ll - l0): mm for (cc, ll), mm in bits.items()}, w, h)
            bits = {(cc + c0, ll + l0): mm for (cc, ll), mm in rel.items()}      # solid: holes filled
            rect = all(bits.get((cc, ll), 0) == 0xFF for cc in range(c0, c1 + 1) for ll in range(l0, l1 + 1))
            rc0 = c0 if absolute else c0 - c
            body = b'' if rect else bytes(bits.get((cc, ll), 0) for ll in range(l0, l1 + 1)
                                          for cc in range(c0, c1 + 1))
            rec = bytes([(1 if rect else 0) | (2 if absolute else 0), rc0 & 255, w, h]) + body
            if rec not in shapes:
                shapes[rec] = SHAPES_LO + len(blob)
                blob += rec
            ptr, rl0 = shapes[rec], l0 - 2 * y
            if not -128 <= rl0 < 128:
                raise ValueError('shape line offset out of range (type %d)' % t)
            blob[24 * k + 3 * v:24 * k + 3 * v + 3] = bytes([ptr & 255, ptr >> 8, rl0 & 255])
            model[(t, v)] = (absolute, rc0, rl0, w, h,
                             {(cc - c0, ll - l0): mm for (cc, ll), mm in bits.items()})
    if SHAPES_LO + len(blob) > SHAPES_HI:
        raise ValueError('shape data too long (%d bytes)' % len(blob))
    return bytes(dt), bytes(blob), model


def shapes_from_blob(dtab, blob):
    """Model dict from the ROM data (the verifier uses exactly what the hooks read)."""
    model = {}
    rd = lambda a: blob[a - SHAPES_LO]
    for t in range(1, NTYPES):
        if not dtab[8 * t] & 1:
            continue
        vt = dtab[8 * t + 6] | dtab[8 * t + 7] << 8
        for v in range(8):
            ptr = rd(vt + 3 * v) | rd(vt + 3 * v + 1) << 8
            if not ptr:
                continue
            rl0 = _signed(rd(vt + 3 * v + 2))
            fl, c0, w, h = (rd(ptr + k) for k in range(4))
            bits = {}
            for ll in range(h):
                for cc in range(w):
                    mm = 0xFF if fl & 1 else rd(ptr + 4 + ll * w + cc)
                    if mm:
                        bits[(cc, ll)] = mm
            model[(t, v)] = (bool(fl & 2), _signed(c0), rl0, w, h, bits)
    return model


class _BankMemLite:
    def __init__(self, banks, o7ffd):
        self.banks, self.o7 = banks, o7ffd

    def __getitem__(self, a):
        return self.banks[(5, 2, self.o7 & 7)[(a >> 14) - 1]][a & 0x3FFF] if a >= 0x4000 else 0


def smear_tables():
    sr, sl = bytearray(256), bytearray(256)
    for x in range(256):
        r = l = 0
        for k in range(8):
            r |= x >> k
            l |= (x << k) & 0xFF
        sr[x], sl[x] = r, l
    return bytes(sr), bytes(sl)


def pair_tables(swap=False):
    """n = ink nibble << 4 | fill nibble -> two bytes of 4-bit pixels (ink 1, fill 2, else 0).
    swap: negative control (ink and fill exchanged)."""
    p0, p1 = bytearray(256), bytearray(256)
    a, b_ = (2, 1) if swap else (1, 2)
    for n in range(256):
        ink, fil = n >> 4, n & 15
        px = [a if ink & b else b_ if fil & b else 0 for b in (8, 4, 2, 1)]
        p0[n], p1[n] = px[0] << 4 | px[1], px[2] << 4 | px[3]
    return bytes(p0), bytes(p1)


def occluded(get, ix, dtab, shapes):
    """Model of occl for a converted plot (descriptor after the plot): the set of screen pixels
    (x, line) inside the figure's box (3 columns x rows, lines <= 191) covered by the solid shape of
    an object the figure is behind - for every list object with a walk box (dtab +0 bit 0): behind
    when y + box middle + 64 >= y_figure + 6 + 64 (the game's walk-test point), shape = shapes[(type,
    x >> 5)] at column (x & 31) + c0 (or c0 if absolute) and line 2y + l0."""
    out = set()
    last = get(64904)
    if not last:
        return out
    col, fy, pairs = get(ix + 0), get(ix + 1), get(ix + 10)
    f64, fl0 = fy + 70, 2 * fy
    fl1 = min(191, fl0 + 2 * pairs - 1)
    e, n = get(0xFF00), 0
    while n < 64:
        n += 1
        a = 0xFF00 + e
        t = get(a + 2) & 0x7F
        if 1 <= t < NTYPES and dtab[8 * t] & 1:
            x, y = get(a + 3), get(a + 4)
            if y + dtab[8 * t + 5] >= f64 and (t, x >> 5) in shapes:
                ab, c0, l0, w, h, bits = shapes[(t, x >> 5)]
                sc = c0 if ab else _signed(((x & 31) + c0) & 255)
                sl = 2 * y + l0
                for line in range(max(sl, fl0), min(sl + h - 1, fl1) + 1):
                    for cx in range(max(sc, col), min(sc + w - 1, col + 2) + 1):
                        m = bits.get((cx - sc, line - sl), 0)
                        for b in range(8):
                            if m & (128 >> b):
                                out.add((cx * 8 + b, line))
        if e == last:
            break
        e = get(a)
    return out


def frame_rows(get, ix):
    """The figure's new frame as the plotter's own stream gives it (descriptor after the plot):
    rows = 2 * (+10) lines of 24 bits (bit 23 = leftmost); graphics page (+3) + 0xA0, offset at
    0x98E2 + 2 * frame (+1 if flags bit 2), even rows c0 c1 c2, odd rows c2 c1 c0."""
    pg = (get(ix + 3) + 0xA0) & 255
    l0 = get(0x98E2 + 2 * get(ix + 2) + ((get(ix + 11) >> 2) & 1))
    rows = []
    for r in range(2 * get(ix + 10)):
        bs = [get(pg * 256 + ((l0 + 3 * r + k) & 255)) for k in range(3)]
        if r & 1:
            bs = bs[::-1]
        rows.append(bs[0] << 16 | bs[1] << 8 | bs[2])
    return rows


def expected_pixels(get, ix, dtab, shapes):
    """{(x, line): 1 ink / 2 fill} the converted figure's sprite must show (lines <= 191)."""
    rows = frame_rows(get, ix)
    fill = body_fill(rows, 24)
    occ = occluded(get, ix, dtab, shapes)
    col, fy = get(ix + 0), get(ix + 1)
    out = {}
    for r, (ink, fl) in enumerate(zip(rows, fill)):
        line = 2 * fy + r
        if line > 191:
            break
        for k in range(24):
            m = 1 << (23 - k)
            p = (col * 8 + k, line)
            if p in occ:
                continue
            if ink & m:
                out[p] = 1
            elif fl & m:
                out[p] = 2
    return out, rows, occ


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
        self.dtab, self.shapes = patch.dtab, patch.shape_model

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
    if not _run_to(so, stop, sp_ret):
        err.append('did not return')
    if not _run_to(sp_, stop, sp_ret, check=_isafe(sp_, regs, err)):
        err.append('did not return')
    for e in ns.events:
        if e[0] == 'nr' and e[1] not in NR_OK:
            err.append(('hook writes NextReg', e[1]))
            break
        if e[0] == 'port' and e[1] & 0xFF != 0x5B and e[1] != 0x303B:
            err.append(('hook writes port', e[1]))
            break
    if ns.nr.get(0x07, 0) != 0:
        err.append(('speed not restored', ns.nr.get(0x07)))
    if any(e[0] == 'in' for e in ns.events):
        err.append('port read in hook')
    return so, o, sp_, p, err


NEG_CACHE_FRAMES = 400
NR_OK = {0x07, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39}  # speed + sprite attributes: all a hook may write
ISAFE = {'checked': 0}


def _isafe(sim, regs0, err):
    """Interrupt safety, checked after every instruction of hook code (alt ROM page): an IM2
    interrupt may arrive there and the game's handler needs IY (flags at IY+7), IX, I, its interrupt
    state and room on the stack it lands on. SP must be on the hook stack (0x5C70..0x5D00) or at or
    above the game's own SP at the hook site."""
    R = sim.registers
    iy, ix, i, iff = (regs0[10], regs0[11]), (regs0[8], regs0[9]), regs0[14], regs0[26]
    sp0 = regs0[12]
    seen = []

    def chk(pc):
        if 0x2000 <= pc < 0x4000:
            ISAFE['checked'] += 1
            bad = None
            if (R[10], R[11]) != iy:
                bad = 'IY changed'
            elif (R[8], R[9]) != ix:
                bad = 'IX changed'
            elif R[14] != i or R[26] != iff:
                bad = 'I / interrupt state changed'
            elif not (0x5C70 <= R[12] <= 0x5D00 or R[12] >= sp0 - 4):
                bad = 'SP outside the hook stack and the game stack'
            elif TRAP_LO <= pc < TRAP_HI:
                bad = 'instruction fetch in 0x3D00-0x3DFF (crashed on hardware; probable DivMMC automap)'
            if bad and not seen:
                seen.append(bad)
                err.append(('interrupt-unsafe hook: %s' % bad, pc))
    return chk


def _run_to(sim, stop, sp_ret, limit=400000, check=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not (R[24] == stop and (sp_ret is None or R[12] == sp_ret)):
        pc = R[24]
        ops[mem[pc]]()
        if check is not None:
            check(pc)
        n += 1
        if n > limit:
            return False
    return True


def _scr_xy(a):
    o = a - 0x4000
    return (o & 31), ((o >> 8) & 7) | ((o >> 2) & 0x38) | ((o >> 5) & 0xC0)


def check_plot(get, o, p, world, ix, conv, n_before_ent, dtab=None, shapes=None):
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
    had = any(e[1] == ix and e[2] == pc0 and e[3] == py0 for e in (n_before_ent or ()))
    now = world.entries()
    if had and any(e[1] == ix and e[2] == pc0 and e[3] == py0 for e in now) and \
            not (conv and (o[ix + 0], o[ix + 1]) == (pc0, py0)):
        f.append(('old sprite still shown after the plot', pc0, py0))
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
    shown = {}
    for k in range(4):
        px = world.ns.sprite_pixels(4 * i + k)
        if px is None:
            f.append(('sprite hidden', 4 * i + k))
            continue
        for x, yy, v in px:
            if v and 0 <= x < 256 and 0 <= yy < 192:          # clip window
                shown[(x, yy)] = v
    exp, frows, occ = expected_pixels(lambda a: o[a], ix, dtab if dtab is not None else world.dtab,
                                      world.shapes if shapes is None else shapes)
    # the frame model against the original: its ink is on the original screen, and everything
    # the original drew (bits missing from the patched screen) belongs to it
    ink = {(col * 8 + k, 2 * y + r) for r, v in enumerate(frows) if 2 * y + r <= 191
           for k in range(24) if v >> (23 - k) & 1}
    for x, yy in ink:
        a = 0x4000 | ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2) | (x >> 3)
        if not o[a] & (128 >> (x & 7)):
            f.append(('frame model pixel not on the original screen', x, yy))
            break
    want = set()
    for a, bits in d.items():
        cx, ly = _scr_xy(a)
        for b in range(8):
            if bits & (128 >> b):
                want.add((cx * 8 + b, ly))
    if want - ink:
        f.append(('original drew bits outside the frame model', sorted(want - ink)[:3]))
    if shown != exp:
        behind = [q for q in shown if q in occ]
        if behind:
            f.append(('sprite shows pixels of scenery it is behind', len(behind)))
        bad = [q for q in set(shown) | set(exp) if shown.get(q) != exp.get(q) and q not in occ]
        if bad:
            f.append(('sprite pixels differ from the model (ink 1 / fill 2)', len(bad), sorted(bad)[:3]))
    world.occluded = getattr(world, 'occluded', 0) + len([q for q in occ if q in ink])
    world.filled = getattr(world, 'filled', 0) + sum(1 for v in exp.values() if v == 2)
    return f, len(shown)


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
            pw0 = world.ns.pat_writes
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
                if world.ns.pat_writes == pw0:
                    c['converted, image reused from a pattern slot'] += 1
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
    c['fill pixels'] = getattr(world, 'filled', 0)
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
    if len(saved_ram) >= RAM_HI - RAM_LO:       # pattern-slot keys (states captured by this layout)
        w.ram[SLOTK - RAM_LO:SLOTK - RAM_LO + 4 * NSLOT] = saved_ram[SLOTK - RAM_LO:SLOTK - RAM_LO + 4 * NSLOT]
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


LAST_WORLD = [None]


def unit_tests(patch, states, neg=None, dtab=None, neg_depth=None, neg_restore=None, neg_iy=None):
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
        if pt is not patch:                         # a broken patch builds with its own tables:
            w.ram[SLOTK - RAM_LO:SLOTK - RAM_LO + 4 * NSLOT] = pt.ram[SLOTK - RAM_LO:SLOTK - RAM_LO + 4 * NSLOT]
        LAST_WORLD[0] = w                           # no images cached by the good patch
        nb = w.entries()
        so, o, sp_, p, err = _pair(pt, w, get, regs, ret, pt.rom_image(), (sp0 + 2) & 0xFFFF)
        f = list(err)
        diff = [i for i in CMP if so.registers[i] != sp_.registers[i]]
        if diff:
            f.append(('registers differ', diff))
        cf, npx = check_plot(get, o, p, w, ix, p.conv, nb, dtab, patch.shape_model)
        c['occluded'] += getattr(w, 'occluded', 0)
        f += cf
        vb = _visible_ok(w)
        if vb:
            f.append(('visibility', vb[:2]))
        main = _main_visited(get, regs, ret, (sp0 + 2) & 0xFFFF)
        own = any(e[1] == ix and e[2] == get(ix + 0) and e[3] == get(ix + 1) for e in nb)
        full = ram[V_CNT - RAM_LO] >= NENT and not own
        step = (get(ix + 4) - get(ix + 0)) & 0xFF
        dy = abs(get(ix + 5) - get(ix + 1))
        want = ix in CONV and main and not full and get(ix + 7) < 32 and step in (0, 1, 0xFF) \
            and dy < get(ix + 10)
        if p.conv != want:
            f.append(('guard mismatch', label, p.conv, want))
        return f, p.conv, npx

    for si, (R, banks, o7, ram, attrs, pat) in enumerate(states):
        ix = R[8] * 256 + R[9]
        if len(ram) < RAM_HI - RAM_LO:                  # state captured before the slot table
            ram = bytes(ram) + patch.ram[len(ram):]
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
        # 2b. pattern slots: 11 entries in use show slots 0-10, every slot holds another image, the
        #     round robin points at slot 0: the plot must take slot 11 (never a shown slot)
        r2 = bytearray(ram)
        for i in range(NENT):
            r2[ENT - RAM_LO + 8 * i:ENT - RAM_LO + 8 * i + 8] = bytes(8)
        for i in range(NENT - 1):
            r2[ENT - RAM_LO + 8 * i:ENT - RAM_LO + 8 * i + 8] = bytes([1, 0x34, 0x12, 200, 200, i, 20, 0])
        r2[V_CNT - RAM_LO] = NENT - 1
        r2[V_FREED - RAM_LO] = 0xFF
        r2[V_CLK - RAM_LO] = NSLOT - 1
        r2[SLOTK - RAM_LO:SLOTK - RAM_LO + 4 * NSLOT] = bytes(x for k in range(NSLOT) for x in (0xA0, k, 2, 0))
        a2 = [list(a) for a in attrs]
        for s_ in range(4 * NENT):
            a2[s_][3] = (a2[s_][3] | 0x80) if s_ < 4 * (NENT - 1) else (a2[s_][3] & 0x7F)
        bm = _BankMem(banks, o7, rom)
        ed = {ix + 0: bm[ix + 4], ix + 1: bm[ix + 5]}       # no column / row step: converted
        f, conv, _ = one(patch, R, banks, o7, bytes(r2), a2, pat, ed, 'slots')
        c['slot-full cases'] += 1
        c['slot-full cases converted'] += bool(conv)    # (one() checks conv against the guard)
        for k in f:
            fail('slots: %s' % (k[0],), (si,) + tuple(k[1:]))
        if conv:
            used = [e for e in LAST_WORLD[0].entries() if e[1] == ix]
            if not used or used[0][4] != NENT - 1:
                fail('slots full: wrong slot', (si, used[:1]))
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
        # 8. interrupt safety: the broken e_ent (LD IY) must be caught by the per-instruction check
        if neg_iy is not None and si == 0:
            f8, _, _ = one(neg_iy, R, banks, o7, ram, attrs, pat, None, 'negi')
            if any('interrupt-unsafe' in str(k) for k in f8):
                c['interrupt negative control detected'] += 1
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
    # 0x5E00-0x5E1F: the front end's prompt data, never used by the hooks; scratch: written first
    loose = set(range(V_SP_LO, V_SP_LO + 2)) | set(range(STK_LO, RUN_HI)) | set(range(F_ATT, SLOTK))

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
    return CommandoPatch(edit={pt.syms['svrest']: b'\xC9'})


def negative_init_patch():
    """Broken copy: e_init does not empty the pattern-slot keys (stale loader bytes would be taken
    for cached images): caught by init_tests (hook RAM differs from the start state)."""
    pt = CommandoPatch()
    a = pt.syms['e_init'] - 0x2000
    loop = bytes([0x21, SLOTK & 255, SLOTK >> 8, 0x06, 4 * NSLOT, 0x77, 0x2C, 0x10, 0xFC])
    k = pt.page.index(loop, a, a + 64)
    return CommandoPatch(edit={0x2000 + k + 5: b'\x00'})


def negative_cache_patch():
    """Broken copy: the pattern-slot lookup ignores the frame offset (any image of the same page and
    height is reused): caught by the RZX verify (sprite pixels differ from the model)."""
    pt = CommandoPatch()
    a = pt.syms['show.lk'] + 10
    if pt.page[a - 0x2000] != 0xBE:
        raise ValueError('show.lk + 10 is not CP (HL)')
    return CommandoPatch(edit={a: b'\xBF'})


def static_checks(patch):
    """Disassemble every hook block: no instruction may write IX or IY (the game's interrupt
    handler needs them at any instruction). Returns [(address, instruction)] of offenders and the
    number of instructions read."""
    import re
    from types import SimpleNamespace
    from skoolkit.disassembler import Disassembler
    mem = [0] * 65536
    img = patch.rom_image()
    mem[0:0x4000] = list(img)
    cfg = SimpleNamespace(defb_size=8, defm_size=65, defw_size=1, handle_rst=False, wrap=False,
                          opcodes='', asm_hex=False, asm_lower=False,
                          imaker=lambda a, o, b: SimpleNamespace(address=a, operation=o, bytes=b))
    d = Disassembler(mem, cfg)
    bad, n = [], 0
    wr = re.compile(r'^(LD I[XY][HL]?,|POP I[XY]|INC I[XY][HL]?$|DEC I[XY][HL]?$|ADD I[XY],|EX \(SP\),I[XY])')
    for lo, hi in ((ROM_ORG, ROM_ORG + len(patch.rom_code)), (ROM2_ORG, ROM2_ORG + len(patch.rom2_code)),
                   (FILL_LO, FILL_LO + len(patch.fill_code)),
                   (SVR_LO, SVR_LO + len(patch.svr_code))):
        if lo < TRAP_HI and hi > TRAP_LO:
            bad.append((lo, 'hook code in 0x3D00-0x3DFF (crashed on hardware; probable DivMMC automap)'))
        a = lo
        while a < hi:
            i = d.disassemble(a, a + 1, 'n')[0]
            n += 1
            if wr.match(i.operation.upper()):
                bad.append((a, i.operation))
            a += len(i.bytes)
    return bad, n


def negative_iy_patch():
    """Broken copy: e_ent starts with LD IY,0x5C00 instead of LD (V_SP),SP - an interrupt there
    would run the game's handler with the wrong IY. The interrupt-safety check must catch it."""
    pt = CommandoPatch()
    return CommandoPatch(edit={pt.syms['e_ent']: bytes.fromhex('FD21005C')})


def negative_patch():
    """Broken copy: pixel-pair tables with ink and fill exchanged (pixel check must fail)."""
    return CommandoPatch(swap_pairs=True)


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
    say('Plain     : %s  %s  boot %s  (tail 0x%04X: never read or written in the reference RZX; with --rzx checked per access)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = CommandoPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    zt.convert(z80, spr, quiet=True, patch=patch)
    bad2 = boot_check(spr, z80, patch)
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                          'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2 and ok_front
    sbad, sn = static_checks(patch)
    ok = ok and not sbad
    say('Static    : %d hook instructions disassembled; IX/IY writes, code in 0x3D00-0x3DFF (probable DivMMC trap): %s -> %s' % (
        sn, sbad or 'none', 'PASS' if not sbad else 'FAIL'))
    ISAFE['checked'] = 0
    states = []
    dtab = None
    for r in list(a.rzx or [])[:1]:
        from skoolkit.rzxplay import parse_rzx
        from skoolkit.snapshot import Snapshot as SS
        s0 = [b.obj for b in parse_rzx(r) if isinstance(b.obj, SS)][0]
        dtab, blob, model = _derive_depth(s0)
        dok = dtab == patch.dtab and blob == patch.shapes
        ok = ok and dok
        say('Depth     : table + solid shapes re-derived from the game (RZX start state: drawer 37302 + '
            'box builder 60754 per type and variant) %s the profile; %d types with walk boxes, %d '
            'shape variants, %d bytes -> %s' % ('=' if dok else '!=', sum(dtab[8 * k] & 1 for k in range(NTYPES)),
                                              len(model), len(blob), 'PASS' if dok else 'FAIL'))
        if not dok:
            say('            update the profile: python -m nexclash.commando depth %s  (then re-run auto)' % r)
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
        say('            figure pixels hidden behind solid scenery (depth rule): %d; yellow body-fill pixels: %d'
            % (c['occluded pixels'], c['fill pixels']))
        say('            sprite-frames %d, mostly covered/erased on the original %d (scenery/bullets '
            'drawn over a figure)' % (c['sprite-frames'],
                                      c['sprite-frames mostly covered/erased on the original']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
        nc, nex = verify(negative_cache_patch(), r, stop=NEG_CACHE_FRAMES, dtab=dtab)
        cneg = any('sprite pixels differ' in k for k in nc if k.endswith('!'))
        ok = ok and cneg and c['converted, image reused from a pattern slot'] > 0
        say('Cache     : %d of %d converted plots reused an image already in a pattern slot (no upload); '
            'negative control (lookup ignores the frame) over %d frames %s -> %s' % (
                c['converted, image reused from a pattern slot'], c['converted'], NEG_CACHE_FRAMES,
                'detected' if cneg else 'NOT detected', 'PASS' if cneg else 'FAIL'))
    ic, iex = init_tests(patch, z80, negative_init_patch())
    iok = not ic['init failures!'] and ic['init negative control detected'] == ic['init negative control cases']
    ok = ok and iok
    say('Init      : e_init (25630) from the loader RAM, %d cases, negative control %d/%d -> %s' % (
        ic['init cases'], ic['init negative control detected'], ic['init negative control cases'],
        'PASS' if iok else 'FAIL %s' % str(iex)[:300]))
    if states:
        u, uex = unit_tests(patch, states, negative_patch(), dtab, negative_depth_patch(),
                            negative_restore_patch(), negative_iy_patch())
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        neg_ok = u['negative control cases'] and u['negative control detected'] == u['negative control cases']
        ok = ok and not uf and neg_ok
        say('Unit      : %d position cases (%d converted, %d passthrough, %d step guard), %d '
            'table-full, %d slot-full, %d other-descriptor, %d page-guard, negative control %d/%d -> %s' % (
                u['cases'], u['converted'], u['passthrough'], u['step guard cases'],
                u['table-full cases'], u['slot-full cases'],
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
        ineg = u['interrupt negative control detected'] == 1
        ok = ok and ineg
        say('Interrupt : %d hook instructions checked (IY, IX, I, interrupt state, stack, NextRegs, '
            'ports, no paging); negative control (LD IY in e_ent) %s -> %s' % (
                ISAFE['checked'], 'detected' if ineg else 'NOT detected',
                'PASS' if ineg and not any('interrupt-unsafe' in k for k in uf) else 'FAIL'))
        for k, v in uex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    # python -m nexclash.commando depth GAME.rzx [--check]
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == 'depth':
        same, msg = depth_profile(sys.argv[2], '--check' in sys.argv)
        print(msg)
        sys.exit(0 if same or '--check' not in sys.argv else 1)
    sys.exit('usage: python -m nexclash.commando depth GAME.rzx [--check]')
