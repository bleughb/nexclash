"""Smash TV (Probe / Ocean 1991, 48K) engine 'smashtv'. Additive module: reachable only through
is_smashtv().

Game facts (analysis passes over Smash_TV.z80 and Dean's RZX; details in games/smash_tv.md):
  The .z80 is a BASIC loader (trainer prompt "DO YOU WANT TO BE INVULNERABLE ?", Y = POKE
  33465,201) that enters the game with RANDOMIZE USR 59776. In play the game runs with interrupts
  off and rebuilds a back buffer every game frame: 59506 restores the arena grid (pixels
  0xEC00-0xFFFF, line = B - 48; attrs 0xE980-0xEBFF), the plotters draw the figures, the blit
  53293 copies columns 2-29 to screen rows 3-22 (unrolled LDI, loop end JP PE at 53861).
  Plotters (byte-column aligned, masked by table 0x7E00[g], mirror = bit reverse 0x7D00):
    29858 / 29974  24x24 masked / mirrored, L = frame (word 0x5B00+2L: 72 bytes + 9 attrs)
    29704 / 29777  8x8 masked / mirrored (word 0x5C00+2L: 8 bytes + 1 attr)
  C = buffer column, B = line (row tables 0xC800 / 0xCA00 point at ROM 0x2000 off the buffer).
Hooks (asm/smashtv_hooks.asm, alt ROM 0x2100- + Next page 26 at MMU slot 7 while a hook runs):
the game's own plotter runs into a scratch copy of the buffer (page 26), so registers and
self-modified operands are the original's; the figure becomes 4-bit sprites (ink in the cell's
ink, the mask's outline in the cell's paper, Dean's option A; 24x24 = 2x2,
8x8 = 1) from a 32-group pattern cache; the restore runs twice (real buffer + scratch); the blit
loop end commits the sprites; 53868 hides them all. The front end at 0x5D00 replaces the BASIC
prompt (the .nex starts from the loader's state at its USR, run in the simulator with N).
"""
import collections
import json
import os

PG = 26                     # hook page (slot 7 during hooks)
GPG = 1                     # the game's page at slot 7
ALT_PAGE = 24
ROM_ORG = 0x2100
TAIL_ADDR = 0x5B00          # write-first by the entry code (59823) in the RZX and in a free run
ENTRY = 59776
FRONT, FRONT_END = 0x5D00, 0x5D6D   # write-first game RAM 0x5C6C-0x5D6C after the entry
BUF = (0xE980, 0x10000)     # attr + pixel back buffer (never read by game logic)
PROMPT_ROW = 23
SITES_ORIG = {29704: 'ed734e', 29777: 'ed739f', 29858: 'ed7313', 29974: 'ed7399',
              59506: 'ed73f9', 53861: 'ea3ed0', 53868: 'af32dc'}
SITE_SYM = {29704: 'e_s8', 29777: 'e_s8m', 29858: 'e_b24', 29974: 'e_b24m', 59506: 'e_rs',
            53861: 'e_bl', 53868: 'e_end'}
KIND = {29858: 0, 29974: 1, 29704: 2, 29777: 3}          # bit 1 = 8x8, bit 0 = mirrored
OPER = {29704: 29774, 29777: 29855, 29858: 29971, 29974: 30105, 59506: 59641}
# instruction interiors that must never be a PC (bytes of patched instructions after the first)
INTERIORS = (29705, 29706, 29707, 29778, 29779, 29780, 29859, 29860, 29861, 29975, 29976, 29977,
             59507, 59508, 59509, 53862, 53863, 53870, 53871)
FOLLOW = {53869: 53868}     # an instruction start inside a site: reached only after the site's start
RS_CODE = (59506, 59644)    # the restore routine (slot 7): copied into PG at the same address
RS_OPER = (59641, 59642)    # its self-modified operand
# page PG layout (offsets from 0xE000; asm/smashtv_hooks.asm)
V_N, V_PREV = 0x000, 0x001
CACHE, SPRTAB, ATTR4, PT, PAPER4 = 0x040, 0x240, 0x500, 0x600, 0x700
HSTK_LOW = 0x940            # lowest hook stack byte allowed (above the restore copy 0x872-0x8FB)
STATE_END = 0x980           # 0xE980-0xFFFF of PG = scratch copy of the back buffer
NGRP, MAXSPR = 32, 128
# sprite palette 0: index 0 transparent, 1 black, 2-8 normal blue..white, 9-15 bright blue..white
PALETTE = [0x00, 0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
CLIP = (16, 239, 24, 183)   # play area (buffer columns 2-29, lines 48-207)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'smash_tv.json'),
              os.path.join(_HERE, 'smash_tv.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('smash_tv.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_smashtv(snap):
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    a, sig = int(sg['addr']), bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[a:a + len(sig)]) == sig


def colour(attr):
    """Sprite colour index of a figure cell: its ink (+ bright); attribute 0 (cell not painted by
    the game) -> white (Dean, 2026-10-13)."""
    if attr == 0:
        return 8
    ink = attr & 7
    if attr & 0x40:
        return 8 + ink if ink else 1
    return 1 + ink


def paper(attr):
    """Sprite colour of a figure cell's outline pixels (the 4-px outline the mask clears): the
    cell's paper (+ bright); attribute 0 -> blue, the arena's paper (Dean, 2026-10-13: option A)."""
    if attr == 0:
        return 2
    p = (attr >> 3) & 7
    if attr & 0x40:
        return 8 + p if p else 1
    return 1 + p


def hook_page():
    """Initial contents of page PG (8K at 0xE000)."""
    p = bytearray(8192)
    for g in range(NGRP):
        p[CACHE + 16 * g + 3] = 0xFF                 # no key (size byte 0xFF never matches)
    for a in range(256):
        p[ATTR4 + a] = colour(a) * 4
        p[PAPER4 + a] = paper(a) * 4
    for c in range(16):
        for pair in range(4):
            p[PT + 4 * c + pair] = ((c << 4) if pair & 2 else 0) | (c if pair & 1 else 0)
    return bytes(p)


class SmashPatch:
    name = 'Smash TV figures -> hardware sprites (altrom + page 26 at slot 7, scratch-buffer plots)'

    def __init__(self, prof=None, rom_code=None, page=None):
        from .build import rom48
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code or bytes.fromhex(h['rom'])
        self.front = bytes.fromhex(h['front'])
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup']) + bytes(PALETTE)
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = False
        self.tail_addr = TAIL_ADDR
        self.max_tail = 0xDE                          # 0x5B00-0x5BDD write-first
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3800:
            raise ValueError('ROM hooks too long')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (ROM_ORG, self.regblock + 20)
        rom = rom48()
        pg = bytearray(rom[0x2000:0x4000])
        pg[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(pg)
        self.hpage = bytearray(page if page is not None else hook_page())
        self.sites = [(a, bytes.fromhex(old), b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]
        self.extra_banks = {12: self.page + bytes(8192), 13: bytes(self.hpage) + bytes(8192)}

    def fill_code(self, get):
        """Copy the restore routine (it lives in slot 7) into PG at the same address."""
        for a in range(*RS_CODE):
            self.hpage[a - 0xE000] = get(a)
        self.extra_banks = {12: self.page + bytes(8192), 13: bytes(self.hpage) + bytes(8192)}

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Smash TV patch expects the 48K start snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if bytes(ram[FRONT - 0x4000:FRONT - 0x4000 + len(self.front)]) != self.front:
            raise ValueError('the snapshot is not the Smash TV start snapshot (front end missing)')
        self.fill_code(lambda a: ram[a - 0x4000])
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


def alt_image(patch):
    from .build import rom48
    alt = bytearray(rom48())
    alt[0x2000:0x4000] = patch.page
    return alt


# ---------------------------------------------------------------------------------------------
# Start state: the loader run to its USR 59776 (key N), + front end and prompt row
# ---------------------------------------------------------------------------------------------

def loader_entry(z80, out_z80):
    """Run the BASIC loader (IM 1, ROM keyboard scan) holding N until PC = 59776; save the state.
    Returns (frame, registers list, 64K memory)."""
    from . import simrun
    from skoolkit.simutils import get_state
    from skoolkit.snapshot import write_snapshot
    f, sim = simrun.free_run(z80, 600, None, keys='10-40:N', stop_pc=ENTRY)
    if sim.registers[24] != ENTRY:
        raise ValueError('the loader did not reach USR %d' % ENTRY)
    ram, regs, state, machine = get_state(sim)
    write_snapshot(out_z80, ram, regs, state, machine)
    return f, list(sim.registers), bytes(sim.memory[a] for a in range(65536))


def _row_addrs(row):
    return [0x4000 + ((row & 0x18) << 8) + (l << 8) + ((row & 7) << 5) + c for l in range(8) for c in range(32)]


def make_start(loader_z80, entry_z80, start_z80, front):
    """Start snapshot = entry state + front end at FRONT + the loader's prompt row; PC = FRONT."""
    from skoolkit.snapshot import Snapshot, write_snapshot
    from skoolkit.simutils import from_snapshot, get_state
    from skoolkit.simulator import Simulator
    ld = Snapshot.get(loader_z80).memory
    sim = from_snapshot(Simulator, Snapshot.get(entry_z80))
    mem = sim.memory
    for a in _row_addrs(PROMPT_ROW) + list(range(0x5800 + 32 * PROMPT_ROW, 0x5820 + 32 * PROMPT_ROW)):
        mem[a] = ld[a]
    for i, v in enumerate(front):
        mem[FRONT + i] = v
    sim.registers[24] = FRONT

    class Tr:
        border = outfe = outfffd = 0
        ay = [0] * 16
    sim.set_tracer(Tr())
    ram, regs, state, machine = get_state(sim)
    write_snapshot(start_z80, ram, regs, state, machine)


CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [27]   # all but R, T, IFF, MEMPTR


def front_tests(start_z80, entry_regs, entry_mem):
    """Run the front end with N and with Y: it must reach 59776 with every register (R and IFF
    aside: 59776 is DI) and all RAM as the loader's own entry state, except the front end bytes
    (0x5D00-0x5D6C, write-first game RAM) and, for Y, 33465 = 201."""
    from skoolkit.snapshot import Snapshot
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    out = {}
    for key, row, bit, sym in (('N', 0x7F, 3, False), ('Y', 0xDF, 4, False), ('SYM+Y', 0xDF, 4, True)):
        sim = from_snapshot(Simulator, Snapshot.get(start_z80), config={'int_active': 0})
        R, mem, ops = sim.registers, sim.memory, sim.opcodes
        n = [0]

        class Tr:
            border = outfe = outfffd = 0
            ay = [0] * 16

            def read_port(self, regs, port):
                n[0] += 1
                if port & 1:
                    return 0xFF
                v = 0xFF
                if sym and n[0] > 400:              # SYM+Y ignored; then N alone
                    return 0xFF & ~8 if (port >> 8) == 0x7F else 0xFF
                if sym and (port >> 8) == 0x7F:     # SYMBOL SHIFT held from the start
                    v &= ~2
                if n[0] >= 30 and (port >> 8) == row:
                    v &= ~(1 << bit)
                return v & 0xFF

            def write_port(self, regs, port, value, offset=0):
                pass
        sim.set_tracer(Tr())
        steps = 0
        while R[24] != ENTRY and steps < 400000:
            ops[mem[R[24]]]()
            steps += 1
        bad = []
        if R[24] != ENTRY:
            bad.append('did not reach %d' % ENTRY)
        bad += ['register %d' % i for i in CMP if R[i] != entry_regs[i]]
        want = {33465: 201} if key == 'Y' else {}
        if sym and n[0] <= 400:
            bad.append('SYM+Y accepted')
        for a in range(0x4000, 0x10000):
            if FRONT <= a < FRONT_END:
                continue
            if mem[a] != want.get(a, entry_mem[a]):
                bad.append(('ram', a, mem[a], want.get(a, entry_mem[a])))
                break
        out[key] = bad
    return out


# ---------------------------------------------------------------------------------------------
# Next-side state and the event runner (original vs patched from one state)
# ---------------------------------------------------------------------------------------------

class NextState:
    def __init__(self, patch):
        self.page = bytearray(patch.hpage)
        self.nr = {0x57: GPG, 0x07: 0}
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pat_ptr = 0
        self.events = []
        self.t3 = 0                 # T-states run at 28 MHz (counted by the runner)

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val

    def out(self, port, val):
        if port == 0x303B:
            self.pat_ptr = (val & 0x3F) * 256 + (128 if val & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pat_ptr & 0x3FFF] = val
            self.pat_ptr += 1
        else:
            self.events.append(('out', port, val))

    def sprite_pixels(self, attr):
        """4-bit anchor sprite attributes -> {(x, y): colour} in ULA coordinates (clip applied)."""
        a0, a1, a2, a3, a4 = attr
        out = {}
        if not a3 & 0x80:
            return out
        x = a0 + (a2 & 1) * 256 - 32
        y = a1 + (a4 & 1) * 256 - 32
        base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
        mx = a2 & 8
        for j in range(16):
            for k in range(16):
                b = self.pat[base + j * 8 + k // 2]
                c = (b >> 4) if k % 2 == 0 else (b & 15)
                if c:
                    xx = x + (15 - k if mx else k)
                    yy = y + j
                    if CLIP[0] <= xx <= CLIP[1] and CLIP[2] <= yy <= CLIP[3]:
                        out[(xx, yy)] = c
        return out


def _machine(Sim, mem, regs, ns):
    from skoolkit.simulator import R2
    sim = Sim(mem, {})
    sim.registers[:] = regs
    R, ed = sim.registers, sim.after_ED

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536; R[25] += 20

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536; R[25] += 17
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs_, port):
            ns.events.append(('in', port))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.out(port, value)
    sim.set_tracer(Tr())
    return sim


def _run(sim, stops, ns=None, limit=600000):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    t3 = 0
    while R[24] not in stops:
        t = R[25]
        ops[mem[R[24]]]()
        if ns is not None and ns.nr.get(0x07, 0) == 3 and mem is not None:
            t3 += R[25] - t
        n += 1
        if n > limit:
            return False, t3
    return True, t3


def _overlays(get, alt, psite, ns, err):
    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return get(a) if v is None else v

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __init__(s, R):
            O.__init__(s)
            s.R = R
            s.page_w = set()

        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if a >= 0xE000 and ns.nr.get(0x57) == PG:
                return ns.page[a - 0xE000]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a >= 0xE000 and ns.nr.get(0x57) == PG:
                if a < 0xE000 + STATE_END and s.R[0][24] >= 0x4000 and a not in RS_OPER:
                    err.append(('game code wrote the hook state', a, s.R[0][24]))
                if RS_CODE[0] <= a < 0xE000 + HSTK_LOW and s.R[0][24] < 0x4000 and a not in RS_OPER:
                    err.append(('hook wrote below its stack area (restore copy)', a))
                ns.page[a - 0xE000] = v
                s.page_w.add(a)
            elif a >= 0x4000:
                if a in psite:
                    err.append(('wrote a patch site', a))
                s.ov[a] = v
    return O, P


def _pair(patch, get, regs, ns, stops, alt):
    """Run original and patched code from one state until PC in stops. Returns
    (orig_sim, orig_mem, patched_sim, patched_mem, errors, original T, patched T, T at 28 MHz)."""
    from skoolkit.simulator import Simulator
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    err = []
    O, P = _overlays(get, alt, psite, ns, err)
    o = O()
    rp = [None]
    p = P(rp)

    class NS0:                      # the original never touches Next state
        nr = {}

        def nextreg(s, r, v):
            err.append(('original wrote a NextReg', r))

        def out(s, port, v):
            pass
        events = []
    so = _machine(Simulator, o, list(regs), NS0())
    ns.events = []
    sp_ = _machine(Simulator, p, list(regs), ns)
    rp[0] = sp_.registers
    t0 = so.registers[25]
    ok1, _ = _run(so, stops)
    t1 = sp_.registers[25]
    ok2, t3 = _run(sp_, stops, ns)
    if not (ok1 and ok2):
        err.append('did not return')
    if ns.nr.get(0x57) != GPG or ns.nr.get(0x07, 0) != 0:
        err.append(('MMU 7 / speed not restored', ns.nr.get(0x57), ns.nr.get(0x07)))
    if any(e[0] == 'in' for e in ns.events):
        err.append('port read in a hook')
    return so, o, sp_, p, err, so.registers[25] - t0, sp_.registers[25] - t1, t3


def figure_model(get, kind, L, C, B, outline=False):
    """Expected sprite pixels of one plot: {(x, y): colour} in ULA coordinates, clipped to the play
    area. Ink = the graphic's set bits (mirrored: columns and bits reversed) in the cell's ink;
    outline = bits the mask table 0x7E00 clears without ink, in the cell's paper. outline=True
    returns (ink set, outline set) instead."""
    w = lambda a: get(a) | get(a + 1) << 8
    small = kind & 2
    p = w((0x5C00 if small else 0x5B00) + 2 * L)
    nb, nr = (1, 8) if small else (3, 24)
    out, ink, ol = {}, set(), set()
    for r in range(nr):
        for k in range(nb):
            g = get((p + r * nb + k) & 0xFFFF)
            m = get(0x7E00 + g)
            at = get((p + nb * nr + (r // 8) * nb + k) & 0xFFFF)
            for b in range(8):
                bit = 0x80 >> b
                if g & bit:
                    c, s_ = colour(at), ink
                elif not m & bit:
                    c, s_ = paper(at), ol
                else:
                    continue
                fx = 8 * k + b
                if kind & 1:
                    fx = 8 * nb - 1 - fx
                x, y = 8 * C + fx, B - 24 + r
                if CLIP[0] <= x <= CLIP[1] and CLIP[2] <= y <= CLIP[3]:
                    out[(x, y)] = c
                    s_.add((x, y))
    return (ink, ol) if outline else out


def attr_bytes(kind, C, B):
    """Addresses the plotter's attribute painter may write: rows from the attr row of line B (not
    clipped per row: for B in 192-207 they run on into pixel lines 0-15 of the buffer)."""
    if not 48 <= B < 208:
        return set()
    base = 0xE980 + ((B - 48) >> 3) * 32
    nb, nr = (1, 1) if kind & 2 else (3, 3)
    return {(base + 32 * r + C + j) & 0xFFFF for r in range(nr) for j in range(nb)}


def _buf_bit(m, x, y):
    a = 0xEC00 + (y - 24) * 32 + (x >> 3)
    return (m[a] >> (7 - (x & 7))) & 1


def model_decide(page, get, kind, L, C, B):
    """The hook's decision from the page state before the plot: 'conv' (sprites), 'inv' (nothing
    visible: converted, no sprites) or 'ula' (column >= 30, sprite table or pattern cache full)."""
    if C >= 30:
        return 'ula'
    small = kind & 2
    if not ((41 if small else 25) <= B < 208):
        return 'inv'
    if page[V_N] + (1 if small else 4) > MAXSPR:
        return 'ula'
    w = lambda a: get(a) | get(a + 1) << 8
    ptr = w((0x5C00 if small else 0x5B00) + 2 * L)
    key = bytes([ptr & 255, ptr >> 8, 1 if small else 0])
    if small:
        key += bytes([get(ptr + 8)]) + bytes(8)
    else:
        key += bytes(get(ptr + 72 + i) for i in range(9))
    for g in range(NGRP):
        if bytes(page[CACHE + 16 * g + 1:CACHE + 16 * g + 13]) == key:
            return 'conv'
    if all(page[CACHE + 16 * g] for g in range(NGRP)):
        return 'ula'
    return 'conv'


def check_plot(pc, R, get, o, p, ns, page0, so, sp_):
    """A plot event. Returns (failures, decision, sprite pixels)."""
    f = []
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    n0, n1 = page0[V_N], ns.page[V_N]
    kind = KIND[pc]
    L, C, B = R[7], R[3], R[2]
    md = [a for a in set(o.ov) | set(p.ov) if not BUF[0] <= a < BUF[1] and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), sorted(md)[:4]))
    wrote_real = any(BUF[0] <= a < BUF[1] for a in p.ov)
    dec = model_decide(page0, get, kind, L, C, B)
    flag = ns.page[0x010]
    if flag != (0 if dec == 'ula' else 1):
        f.append(('decision differs from the model', dec, flag))
    if dec == 'ula':
        if n1 != n0:
            f.append(('ULA plot recorded sprites',))
        bufo = {a: v for a, v in o.ov.items() if BUF[0] <= a < BUF[1]}
        bufp = {a: v for a, v in p.ov.items() if BUF[0] <= a < BUF[1]}
        if set(bufp) != set(bufo):
            f.append(('ULA plot wrote other buffer bytes than the original',))
        return f, dec, 0
    if wrote_real:
        f.append(('converted plot wrote the real buffer',))
    want = figure_model(get, kind, L, C, B)
    if dec == 'inv':
        if n1 != n0 or want:
            f.append(('invisible figure: sprites or visible pixels', n1 - n0, len(want)))
        return f, dec, 0
    if n1 - n0 != (1 if kind & 2 else 4):
        f.append(('sprite count', n0, n1))
    got = {}
    for i in range(n0, n1):
        got.update(ns.sprite_pixels(list(ns.page[SPRTAB + 5 * i:SPRTAB + 5 * i + 5])))
    if got != want:
        f.append(('sprite pixels differ from the model', len(set(got.items()) ^ set(want.items()))))
    ink, ol = figure_model(get, kind, L, C, B, outline=True)   # the model against the original's plot
    for (x, y) in ink:
        if not _buf_bit(o, x, y):
            f.append(('model ink not drawn by the original', x, y))
            break
    for (x, y) in ol:
        if _buf_bit(o, x, y):
            f.append(('model outline not cleared by the original', x, y))
            break
    attr_w = attr_bytes(kind, C, B)
    for a, v in o.ov.items():
        if 0xEC00 <= a < 0x10000 and a not in attr_w:
            y = (a - 0xEC00) // 32 + 24
            new = v & ~get(a)
            for k in range(8):
                x = ((a - 0xEC00) % 32) * 8 + k
                if CLIP[0] <= x <= CLIP[1] and (new >> (7 - k)) & 1 and (x, y) not in ink:
                    f.append(('original drew ink the model misses', x, y))
                    break
    return f, dec, len(got)


def _commit_layer(ns):
    out = {}
    for i in range(128):
        out.update(ns.sprite_pixels(ns.attr[i]))
    return out


# ---------------------------------------------------------------------------------------------
# Differential verification against an RZX (the replay runs the ORIGINAL game)
# ---------------------------------------------------------------------------------------------

def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = alt_image(patch)
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    st = {'frame': 0, 'on': False, 'game': False}
    ns = None
    cnt = collections.Counter()
    WATCH = set(SITES_ORIG) | set(INTERIORS) | {ENTRY}
    states = []
    pending = []                    # expected images since the last commit (plot order)
    tm = collections.Counter()

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __setitem__(s, a, v):
            if st['game'] and type(a) is int and G(s, a) != v:   # (51175 copies RAM onto itself)
                if a in site_bytes:
                    fail('game wrote a patch site', (a,))
                elif RS_CODE[0] <= a < RS_CODE[1] and a not in RS_OPER:
                    fail('game wrote the restore routine (copied into PG)', (a,))
            S(s, a, v)

    def event(pc, R, mem):
        get = lambda a: G(mem, a)
        ns = st['ns']
        if R[26]:
            fail('interrupts enabled at a hook site', (pc,))
        if pc in KIND:
            if collect and c['collected %d' % pc] < collect:
                c['collected %d' % pc] += 1
                states.append(('plot', pc, list(R), bytes(G(mem, a) for a in range(65536)), bytes(ns.page),
                               bytes(ns.pat)))
            page0 = bytes(ns.page)
            stops = (get(R[12]) | get(R[12] + 1) << 8,)
            so, o, sp_, p, err, to, tp, t3 = _pair(patch, get, R, ns, stops, alt)
            for e in err:
                fail('plot %d: %s' % (pc, e[0] if isinstance(e, tuple) else e), e[1:] if isinstance(e, tuple) else ())
            fl, dec, npx = check_plot(pc, R, get, o, p, ns, page0, so, sp_)
            for k in fl:
                fail('plot %d: %s' % (pc, k[0]), k[1:])
            c['plot %d %s' % (pc, dec)] += 1
            c['sprite pixels compared'] += npx
            if dec == 'conv':
                pending.append(figure_model(get, KIND[pc], R[7], R[3], R[2]))
            tm['plot orig'] += to
            tm['plot patched'] += tp - t3 + t3 // 8
        elif pc == 59506:
            if collect and c['collected restore'] < 1:
                c['collected restore'] += 1
                states.append(('restore', pc, list(R), bytes(G(mem, a) for a in range(65536)), bytes(ns.page),
                               bytes(ns.pat)))
            stops = (get(R[12]) | get(R[12] + 1) << 8,)
            so, o, sp_, p, err, to, tp, t3 = _pair(patch, get, R, ns, stops, alt)
            for e in err:
                fail('restore: %s' % (e[0] if isinstance(e, tuple) else e,))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            md = [a for a in set(o.ov) | set(p.ov) if o[a] != p[a]]
            if diff or md:
                fail('restore: registers/memory differ', (diff, sorted(md)[:4]))
            sc = [a for a in o.ov if a >= 0xE980 and ns.page[a - 0xE000] != o.ov[a]]
            if sc:
                fail('restore: scratch copy differs from the restored buffer', (len(sc),))
            c['restores (real + scratch)'] += 1
            tm['restore orig'] += to
            tm['restore patched'] += tp - t3 + t3 // 8
        elif pc == 53861:
            pv = R[1] & 4
            so, o, sp_, p, err, to, tp, t3 = _pair(patch, get, R, ns, (53310, 53864), alt)
            for e in err:
                fail('blit end: %s' % (e[0] if isinstance(e, tuple) else e,))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            md = [a for a in set(o.ov) | set(p.ov) if o[a] != p[a]]
            if diff or md:
                fail('blit end: registers/memory differ', (diff, sorted(md)[:4]))
            if pv:
                return
            c['commits'] += 1
            want = {}
            for img in pending:
                want.update(img)
            got = _commit_layer(ns)
            if got != want:
                fail('commit: sprite layer differs from the figures since the last commit',
                     (len(set(got.items()) ^ set(want.items())),))
            nshown = sum(1 for a in ns.attr if a[3] & 0x80)
            c['max sprites shown'] = max(c['max sprites shown'], nshown)
            c['max figures in a commit'] = max(c['max figures in a commit'], len(pending))
            if ns.page[V_N] != 0:
                fail('commit: N not reset')
            pending.clear()
            tm['commit patched'] += tp - t3 + t3 // 8 - to
            tm['game frames'] += 1
        elif pc == 53868:
            so, o, sp_, p, err, to, tp, t3 = _pair(patch, get, R, ns, (53872,), alt)
            for e in err:
                fail('end: %s' % (e[0] if isinstance(e, tuple) else e,))
            ro, rp = so.registers, sp_.registers
            diff = [i for i in CMP if ro[i] != rp[i]]
            md = [a for a in set(o.ov) | set(p.ov) if o[a] != p[a]]
            if diff or md:
                fail('end: registers/memory differ', (diff, sorted(md)[:4]))
            if any(a[3] & 0x80 for a in ns.attr):
                fail('end: a sprite is still visible')
            pending.clear()
            c['hide all (53868)'] += 1

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            st['on'] = True
            R, mem, ops = self.registers, self.memory, self.opcodes

            def mk(fn):
                def g():
                    pc = R[24]
                    if pc in WATCH:
                        cnt[pc] += 1
                        if pc in FOLLOW and st.get('prev') != FOLLOW[pc]:
                            fail('%d reached other than from %d' % (pc, FOLLOW[pc]), (st.get('prev'),))
                        if pc == ENTRY and not st['game']:
                            st['game'] = True
                            patch.fill_code(lambda a: G(mem, a))
                            st['ns'] = NextState(patch)
                        elif st['game'] and pc in SITES_ORIG:
                            event(pc, R, mem)
                    fn()
                    st['prev'] = pc
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    def next_frame(self):
        st['frame'] += 1
        if progress and st['frame'] % 500 == 0:
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
            c['jump into a patched instruction (%d)!' % a] += 1
    c['frames'] = st['frame']
    c['_time'] = dict(tm)
    return (c, dict(ex), states) if collect else (c, dict(ex))


# ---------------------------------------------------------------------------------------------
# Unit tests: guard edges (column, line, sprite table), cache hit / full, the ULA path (real +
# scratch runs), negative controls
# ---------------------------------------------------------------------------------------------

def _mem_get(mem64):
    return lambda a: mem64[a & 0xFFFF]


RUNTIME = (0x000, 0x4C0)     # vars, cache keys/flags, sprite table: the run-time part of PG (tables,
                             # V_PC 0x800 and the restore copy come from the patch)


def _plot_case(patch, pc, R, mem64, page, pat, C=None, B=None, L=None, n=None, full=False, fresh=False,
               alt=None):
    R = list(R)
    if C is not None:
        R[3] = C
    if B is not None:
        R[2] = B
    if L is not None:
        R[7] = L
    get = _mem_get(mem64)
    ns = NextState(patch)
    ns.page[RUNTIME[0]:RUNTIME[1]] = page[RUNTIME[0]:RUNTIME[1]]   # run-time state; tables from the patch
    ns.pat[:] = pat
    if fresh:                                       # empty cache: the image is built
        for g in range(NGRP):
            ns.page[CACHE + 16 * g] = 0
            ns.page[CACHE + 16 * g + 3] = 0xFF
    for a in range(0xE980, 0x10000):                # scratch = the buffer as the original sees it
        ns.page[a - 0xE000] = mem64[a]
    if n is not None:
        ns.page[V_N] = n
    if full:
        for g in range(NGRP):
            ns.page[CACHE + 16 * g] = 2              # every group on show
            ns.page[CACHE + 16 * g + 3] = 0xFE       # and no key matches (size byte)
    page0 = bytes(ns.page)
    stops = (get(R[12]) | get(R[12] + 1) << 8,)
    so, o, sp_, p, err, to, tp, t3 = _pair(patch, get, R, ns, stops, alt or alt_image(patch))
    f, dec, npx = check_plot(pc, R, get, o, p, ns, page0, so, sp_)
    return err + f, dec


def unit_tests(patch, states, negs=()):
    """states from verify(collect=n): ('plot', pc, registers, 64K memory, page). Returns Counter."""
    c = collections.Counter()
    alt = alt_image(patch)
    plots = [s for s in states if s[0] == 'plot']
    for _, pc, R, mem64, page, pat in plots:
        small = KIND[pc] & 2
        lo = 41 if small else 25
        for C in (0, 1, 2, 28, 29, 30, 31):
            for B in (lo - 1, lo, 47, 48, 100, 191, 192, 207, 208, 230):
                f, dec = _plot_case(patch, pc, R, mem64, page, pat, C=C, B=B, fresh=(C + B) % 2 == 0, alt=alt)
                c['cases'] += 1
                c['decision ' + dec] += 1
                for k in f:
                    c['%d C%d B%d: %s!' % (pc, C, B, k[0] if isinstance(k, tuple) else k)] += 1
        need = 1 if small else 4
        for n in (MAXSPR - need - 1, MAXSPR - need, MAXSPR - need + 1, MAXSPR):
            f, dec = _plot_case(patch, pc, R, mem64, page, pat, B=100, C=10, n=n, alt=alt)
            c['table cases'] += 1
            c['table ' + dec] += 1
            for k in f:
                c['%d N%d: %s!' % (pc, n, k[0] if isinstance(k, tuple) else k)] += 1
        f, dec = _plot_case(patch, pc, R, mem64, page, pat, B=100, C=10, full=True, alt=alt)
        c['cache-full cases'] += 1
        if dec != 'ula':
            c['%d cache full not on the ULA!' % pc] += 1
        for k in f:
            c['%d cache full: %s!' % (pc, k[0] if isinstance(k, tuple) else k)] += 1
        for name, neg in negs:
            f, dec = _plot_case(neg, pc, R, mem64, page, pat, B=100, C=10 if name != 'guard' else 30,
                                fresh=True, alt=alt_image(neg))
            c['negative control cases'] += 1
            c['negative control detected' if f else 'negative control %s NOT detected!' % name] += 1
    return c


def negative_patches(patch):
    """Broken copies that the checks must catch: ink colours shifted (ATTR4), guard column 31 instead of
    30 (decide's CP 30), the restore copy missing (scratch run executes zeros)."""
    import copy
    a = copy.copy(patch)
    a.hpage = bytearray(patch.hpage)
    for i in range(256):
        a.hpage[ATTR4 + i] = (patch.hpage[ATTR4 + i] + 4) & 0x3C
    o = copy.copy(patch)                            # outline drawn transparent (look B)
    o.hpage = bytearray(patch.hpage)
    for i in range(256):
        o.hpage[PAPER4 + i] = 0
    b = copy.copy(patch)
    rom = bytearray(patch.rom_code)
    d = patch.syms['decide'] - ROM_ORG
    k = rom.index(bytes([0xFE, 30]), d)             # decide: LD A,C / CP 30
    rom[k + 1] = 31
    b.rom_code = bytes(rom)
    pg = bytearray(patch.page)
    pg[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(rom)] = rom
    b.page = bytes(pg)
    return [('colour', a), ('outline', o), ('guard', b)]


def static_checks(patch):
    """Hook code (alt ROM) disassembled from every entry symbol: no DI/EI/IM/LD I/RETI/RETN, no
    IX/IY prefixes, nothing in 0x3D00-0x3DFF; alt image keeps ROM 0x0000-0x20FF, 0x386E and the
    font 0x3D00-0x3FFF."""
    from .build import rom48
    rom = rom48()
    alt = alt_image(patch)
    bad = []
    if alt[0:0x2100] != rom[0:0x2100]:
        bad.append('alt ROM 0x0000-0x20FF differs from the ROM')
    if alt[0x386E] != 0xFF or alt[0x3800:0x4000] != rom[0x3800:0x4000]:
        bad.append('alt ROM 0x3800-0x3FFF (0x386E check byte, font) differs from the ROM')
    if patch.regblock + 20 > 0x386E:
        bad.append('register block reaches 0x386E')
    code = patch.rom_code
    n = 0
    i = 0
    while i < len(code):                            # linear sweep (the block is code only)
        op = code[i]
        a = ROM_ORG + i
        if 0x3D00 <= a < 0x3E00:
            bad.append(('code in 0x3D00-0x3DFF', a))
        if op in (0xDD, 0xFD):
            bad.append(('IX/IY instruction', hex(a)))
        if op in (0xF3, 0xFB):
            bad.append(('DI/EI', hex(a)))
        if op == 0xED and i + 1 < len(code) and code[i + 1] in (0x46, 0x56, 0x5E, 0x47, 0x4D, 0x45):
            bad.append(('IM / LD I,A / RETI / RETN', hex(a)))
        i += _oplen(code, i)
        n += 1
    return bad, n


def _oplen(code, i):
    op = code[i]
    if op == 0xED:
        o2 = code[i + 1]
        if o2 == 0x91:
            return 4
        if o2 == 0x92:
            return 3
        if o2 & 0xC7 == 0x43:                       # LD (nn),rr / LD rr,(nn)
            return 4
        return 2
    if op == 0xCB:
        return 2
    if op in (0xDD, 0xFD):
        return 4
    one = {0x00, 0x02, 0x03, 0x04, 0x05, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0F, 0x12, 0x13, 0x14,
           0x15, 0x17, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1F, 0x23, 0x24, 0x25, 0x27, 0x29, 0x2B, 0x2C, 0x2D,
           0x2F, 0x33, 0x34, 0x35, 0x37, 0x39, 0x3B, 0x3C, 0x3D, 0x3F, 0xC0, 0xC1, 0xC5, 0xC8, 0xC9, 0xD0,
           0xD1, 0xD5, 0xD8, 0xD9, 0xE1, 0xE3, 0xE5, 0xE9, 0xEB, 0xF1, 0xF3, 0xF5, 0xF9, 0xFB}
    if 0x40 <= op <= 0xBF or op in one or op & 0xC7 == 0xC7:
        return 1
    two = {0x06, 0x0E, 0x10, 0x16, 0x18, 0x1E, 0x20, 0x26, 0x28, 0x2E, 0x30, 0x36, 0x38, 0x3E, 0xC6, 0xCE,
           0xD3, 0xD6, 0xDB, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE}
    if op in two:
        return 2
    return 3


# ---------------------------------------------------------------------------------------------
# nexclash auto entry point
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    import hashlib
    from . import z80tonex as zt, rzx as RZ
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : smashtv (Smash TV: back-buffer composer, 24x24 / 8x8 masked plotters -> sprites)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(z80, plain, TAIL_ADDR, True, quiet=True)
    bad = check(plain, z80, None, (conv[1], conv[1] + len(conv[2])))
    say('Plain     : %s  %s  boot %s  (the BASIC loader as it is; tail 0x%04X: write-first by the '
        'game entry 59823)' % (os.path.basename(plain), md5(plain),
                               'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    ent = os.path.join(out, name + '_entry.z80')
    start = os.path.join(out, name + '_start.z80')
    fr, eregs, emem = loader_entry(z80, ent)
    patch = SmashPatch()
    make_start(z80, ent, start, patch.front)
    ft = front_tests(start, eregs, emem)
    fok = not any(ft.values())
    say('Loader    : BASIC loader run in the simulator with N to USR %d (frame %d) -> %s; start = '
        'that state + front end 0x%04X + the prompt row' % (ENTRY, fr, os.path.basename(start), FRONT))
    say('Front end : "DO YOU WANT TO BE INVULNERABLE ?" -> N / Y / SYM+Y: state = the loader\'s at '
        'its USR (Y: 33465 = 201) -> %s' % ('PASS' if fok else 'FAIL %s' % ft))
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(start, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, start, patch, (conv[1], conv[1] + len(conv[2])))
    say('Sprites   : %s  %s  boot %s  (tail 0x%04X, %d bytes)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:200],
        conv[1], len(conv[2])))
    sbad, sn = static_checks(patch)
    say('Static    : %d hook instructions; DI/EI/IM/LD I, IX/IY, code at 0x3D00-0x3DFF, ROM bytes the '
        'game reads (0x0000-0x20FF, 0x386E, font): %s -> %s' % (sn, sbad or 'none', 'PASS' if not sbad else 'FAIL'))
    ok = not bad and not bad2 and fok and not sbad
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
        c, ex, st = verify(SmashPatch(), r, stop=getattr(a, 'quick', None), collect=3)
        states += st
        fails = {k: v for k, v in c.items() if isinstance(k, str) and k.endswith('!')}
        ok = ok and not fails
        conv_n = sum(v for k, v in c.items() if isinstance(k, str) and k.startswith('plot') and k.endswith(' conv'))
        inv_n = sum(v for k, v in c.items() if isinstance(k, str) and k.endswith(' inv'))
        ula_n = sum(v for k, v in c.items() if isinstance(k, str) and k.endswith(' ula'))
        say('Verify    : %s  %d frames, %d plots converted (24x24 %d + mirrored %d, 8x8 %d + mirrored %d), '
            '%d invisible, %d on the ULA, %d restores, %d commits (max %d figures / %d sprites), %d hide-all, '
            '%d sprite pixels -> %s' % (
                os.path.basename(r), c['frames'], conv_n, c['plot 29858 conv'], c['plot 29974 conv'],
                c['plot 29704 conv'], c['plot 29777 conv'], inv_n, ula_n, c['restores (real + scratch)'],
                c['commits'], c['max figures in a commit'], c['max sprites shown'], c['hide all (53868)'],
                c['sprite pixels compared'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        tm = c['_time']
        gf = max(1, tm.get('game frames', 1))
        say('Speed     : per game frame (T at 3.5 MHz, 28 MHz parts / 8): plots %d -> %d, restore %d -> %d, '
            'commit +%d: hooks add %d T (the game has no frame sync: ~%.1f%% slower at ~250K T per game frame)' % (
                tm['plot orig'] // gf, tm['plot patched'] // gf, tm['restore orig'] // gf,
                tm['restore patched'] // gf, tm['commit patched'] // gf,
                (tm['plot patched'] - tm['plot orig'] + tm['restore patched'] - tm['restore orig']
                 + tm['commit patched']) // gf,
                100.0 * (tm['plot patched'] - tm['plot orig'] + tm['restore patched'] - tm['restore orig']
                         + tm['commit patched']) / gf / 250000))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(_applied(start), states, negative_patches(_applied(start)))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        neg_ok = u['negative control cases'] and u['negative control detected'] == u['negative control cases']
        ok = ok and not uf and neg_ok
        say('Unit      : %d position cases (conv %d, invisible %d, ULA %d), %d sprite-table cases (ULA %d), '
            '%d cache-full cases, negative controls %d/%d -> %s' % (
                u['cases'], u['decision conv'], u['decision inv'], u['decision ula'], u['table cases'],
                u['table ula'], u['cache-full cases'], u['negative control detected'],
                u['negative control cases'], 'PASS' if not uf and neg_ok else 'FAIL %s' % uf))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def _applied(start):
    """A SmashPatch with the restore copy filled from the start snapshot."""
    from . import z80tonex as zt
    p = SmashPatch()
    p.apply(zt.Z80Snapshot(start))
    return p
