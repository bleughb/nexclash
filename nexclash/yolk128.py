"""Prince of the Yolkfolk 128K - opt-in rework 'v128' of Dean Woodyatt's 'tid_mirror' build of Dizzy 6 (Jon Attree,
2026-11-06).

Dean's TID build with the mirrored second Dizzy (nexclash/dizzy6.py: build.TidPatch + an unpatched, relocated copy of
the plotter and eraser for the actor that draws the mirrored player; his profile docs/profiles/
dizzy6_prince_of_the_yolkfolk.json; untouched, still his record's slot1 build of the 48K file) applied to the game's
128K release. The 128K file is the same program: banks 5, 2 and 0 (0xC000-0xFFFF in play) hold the 48K game's code at
every patch site, and identify() finds Dean's profile there. The game ISR (0xF026) plays the AY music: after the hide
call at 0xF043 it CALLs 0x78DA, which pages bank 3 (OUT 0x7FFD = 0x13), CALLs 0xC0E4 and pages bank 0 back (0x10):
an unlocked 7FFD write every frame, which resets MMU slots 0/1 to ROM. So Dean's slot-1 RAM page cannot stay mapped
(BRIEFING "Legacy paging"); this rework moves everything into the whole alt ROM image:
  - image 1 = Sinclair's 48K ROM + Dean's hooks, table and register block at 0x386E, and his mirror copy at 0x2000
    (the game never reads or runs the ROM: the verifier counts every ROM access). The copy's plotter half never
    writes to itself, so the actor's plot CALL (0x83CD) goes to it in the alt ROM, interrupts as the original;
  - the copy's eraser half modifies its own operand (LD (nn),A into LD BC,nn), so the actor's erase CALL (0x8390,
    always after the actor's own DI) goes to a trampoline: NEXTREG 0x51,24 maps RAM page 24 (the stub's copy source
    for the alt ROM: the same bytes as image 1's 0x2000-0x3FFF) at slot 1 and JPs into the eraser copy, whose last six
    bytes (LD SP,(spsave) / EI / RET) become JP to their own copy behind NEXTREG 0x51,0xFF (the alt ROM again): the
    eraser runs on the original's stack, so its saved SP is the original's. An interrupt taken after the EI / RET
    lands on the same bytes in either view (the ISR's 7FFD write maps the alt ROM back itself);
  - image 0 = the 128K ROM 0 (the game never selects it);
  - the start-up tail in the player's undo buffer 0x5C00 (Dean's 48K decision, 88 bytes; the ROM path check proves it
    is written before it is read); the printer buffer (the game's bit-reverse table for mirrored objects at 0x5B00,
    as Magicland's) put back after NEXLOAD;
  - the hook-speed pass (CODEX-HOOK-SPEED, pace ORIGINAL): Dean's plot hook runs at 28 MHz between a head that
    latches the incoming NR 7 speed (on the stack, EX (SP),HL) and a tail that writes it back before JP to the game's
    plotter (card patch.restore-speed); his erase, wipe, box and ISR hooks and the mirror trampoline are one to three
    NEXTREGs and never touch NR 7;
  - a 128K copy of the TID verifier (nexclash/verify.py is 48K only) with the mirror events: the actor's plot and
    erase run as the original on the patched-screen model against the copy, and the patched-screen model follows the
    mirrored Dizzy, who stays on the ULA screen; guards for ROM reads, patch sites, R, the hook stack and the tail.
The game never reads or writes R (no LD A,R / LD R,A runs: the verifier counts them), so R needs no preserving.

    python nexclash.py auto YOLK128.z80 --rzx R1 --rzx R2 --no-record
"""
import collections
import copy
import hashlib
import json
import os

from . import build as B
from . import dizzy6 as D6
from .verify import REGS as CMP        # registers compared (verify.py's: all but R, T, MEMPTR)

PROFILE_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'profiles', 'dizzy6_prince_of_the_yolkfolk.json')
TAIL, TAIL_MAX = 0x5C00, 88    # Dean's 48K decision: the player's undo buffer (written by every plot before a read)
AY_CALL = (0xF046, bytes.fromhex('cdda78'))          # the ISR's CALL 0x78DA: bank 3 paged, the AY player, bank 0 back
STACK = (0x9B00, 0x9D00)        # the stack area (SP 0x9C8F-0x9C97 in play; the plotter's SP points at data elsewhere)
CODE_END = 0x9C33               # the game's code ends at 0x9C32; 0x9C33-0x9C68 is the never-written stack filler
P24 = B.T['slot1']['page']      # RAM page 24: the alt ROM image's copy source, mapped at slot 1 by the trampoline
DECISIONS = {'engine': 'yolk128', 'base': "Dean's tid_mirror build (dizzy6.py: build.TidPatch + the mirror copy)",
             'input': 'the 128K release (AY music from bank 3 in the game ISR)',
             'strategy': 'altrom: hooks + table + register block at 0x386E and the mirror copy at 0x2000 in alt image 1 = '
                         "Sinclair's 48K ROM (whole image); image 0 = the 128K ROM 0; the mirror erase through a slot-1 "
                         'map of RAM page 24; tail in the undo buffer 0x5C00; printer buffer put back; plot hook at 28 MHz',
             'tail': TAIL}
HEAD_LEN, TAILW_LEN = 27, 11


def load_profile():
    """Dean's profile (docs/profiles/dizzy6_prince_of_the_yolkfolk.json) as his _auto_dizzy6 uses it."""
    p = json.load(open(PROFILE_FILE))
    return dict(p, engine='tid')


def _flat(banks):
    return bytes(banks[5]) + bytes(banks[2]) + bytes(banks[0])


def is_yolk128(snap):
    if snap.machine != '128K':
        return False
    b = snap.memory.banks
    if any(x is None for x in (b[0], b[2], b[5])):
        return False
    ram = _flat(b)
    prof = load_profile()
    if ram[AY_CALL[0] - 0x4000:AY_CALL[0] - 0x4000 + 3] != AY_CALL[1]:
        return False
    if not all(ram[a - 0x4000:a - 0x4000 + len(old)] == old for a, old, new in B.tid_sites(prof, B.T['slot1']['syms'])):
        return False
    m = [0] * 0x4000 + list(ram)
    try:
        D6.layout(prof, m)
    except AssertionError:
        return False
    return True


def head(t_plot):
    """Latch NR 7's programmed speed (port 0x243B / 0x253B, bits 1:0), 28 MHz, the latch left on the stack in H
    (EX (SP),HL), every register as it came; JP Dean's plot hook. 27 bytes (Magicland's)."""
    return bytes([0xF3, 0xE5, 0xF5, 0xC5, 0x01, 0x3B, 0x24, 0x3E, 0x07, 0xED, 0x79, 0x04, 0xED, 0x78, 0xE6, 0x03,
                  0xED, 0x91, 0x07, 0x03, 0xC1, 0x67, 0xF1, 0xE3, 0xC3, t_plot & 0xFF, t_plot >> 8])


def tailw(plotter):
    """The latched speed back (EX (SP),HL / LD A,H / NEXTREG 7,A), HL and AF as they were; JP the game's plotter.
    11 bytes."""
    return bytes([0xE3, 0xF5, 0x7C, 0xED, 0x92, 0x07, 0xF1, 0xE1, 0xC3, plotter & 0xFF, plotter >> 8])


def tramp(copy_erase, spsave):
    """NEXTREG 0x51,24 / JP the eraser copy (7 bytes); then the copy's exit: LD SP,(spsave) / NEXTREG 0x51,0xFF / EI /
    RET (10 bytes, at +7)."""
    return bytes([0xED, 0x91, 0x51, P24, 0xC3, copy_erase & 0xFF, copy_erase >> 8,
                  0xED, 0x7B, spsave & 0xFF, spsave >> 8, 0xED, 0x91, 0x51, 0xFF, 0xFB, 0xC9])


def printer_back(snap, org, call=None):
    """Stub code at org: [CALL call (Dean's set-up)], the snapshot's 0x5B00-0x5BFF copied back over what NEXLOAD left
    there, RET; the 256 bytes after it. The game keeps its bit-reverse table for mirrored objects there (as Magicland)."""
    c = bytearray(b'\xCD' + bytes([call & 0xFF, call >> 8]) if call is not None else b'')
    src = org + len(c) + 12
    c += bytes([0x21, src & 0xFF, src >> 8, 0x11, 0x00, 0x5B, 0x01, 0x00, 0x01, 0xED, 0xB0, 0xC9])
    return bytes(c) + bytes(snap.banks[5][0x1B00:0x1C00])


class PlainPrinter128(B._PlainCompact):
    """Dean's plain() layout (compact tail, register block in RAM page 24 at slot 1) with the tail in the undo buffer
    and the printer buffer put back after NEXLOAD."""
    def __init__(self):
        super().__init__(TAIL, TAIL_MAX)
        self.page = bytes(8192)
        self.setup_call = B.SETUP_ORG

    def apply(self, snap):
        self.stub_extra = printer_back(snap, B.SETUP_ORG)


class YolkPatch128(B.TidPatch):
    """Dean's TidPatch, strategy altrom, + his mirror copy (dizzy6.layout / relocated_copy) in the alt ROM image."""

    def __init__(self, mem):
        prof = load_profile()
        super().__init__(prof, 'altrom', TAIL)
        self.name = ("Prince of the Yolkfolk 128K: Dizzy hardware sprite + the mirrored Dizzy on the ULA (Dean's "
                     "tid_mirror build; whole alt ROM image; plot hook 28 MHz)")
        self.lay = D6.layout(prof, mem)
        self.copy = D6.relocated_copy(mem, self.lay)
        self.copy0 = self.copy                                     # Dean's relocated copy (apply() starts from it)
        self.copy_plot = D6.COPY_ORG
        self.copy_erase = D6.COPY_ORG + prof['eraser'] - prof['plotter']
        self.smod = mem[prof['eraser'] + 12] | mem[prof['eraser'] + 13] << 8     # the eraser's self-modified operand
        self.orig_sites = list(self.sites)
        self.dean_code = self.code

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('this rework is for the 128K release')
        if snap.port7ffd & 7 != 0 or not snap.port7ffd & 0x10:
            raise ValueError('expected bank 0 and ROM 1 paged in the snapshot (7FFD 0x%02X)' % snap.port7ffd)
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        P = self.lay['start']
        if bytes(ram[P - 0x4000:self.lay['end'] - 0x4000]) != D6.relocated_copy_src(ram, self.lay):
            raise ValueError('plotter bytes changed')
        prof = self.prof
        P_, E = prof['plotter'], prof['eraser']
        mirror = [(self.lay['plot_call'], b'\xCD' + B._w(P_)), (self.lay['erase_call'], b'\xCD' + B._w(E))]
        for a, old, new in self.orig_sites:
            if bytes(ram[a - 0x4000:a - 0x4000 + len(old)]) != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, ram[a - 0x4000:a - 0x4000 + len(old)].hex(), old.hex()))
        for a, old in mirror:
            if bytes(ram[a - 0x4000:a - 0x4000 + 3]) != old:
                raise ValueError('unexpected mirror call at 0x%04X' % a)
        self.max_tail = TAIL_MAX
        from .sprites import patterns_for
        pats, table, n = patterns_for(lambda a: ram[a - 0x4000], prof['frame_table'], prof['frame_base'])
        self.num_patterns = n
        syms = B.T['slot1']['syms']
        org = B.T['slot1']['org']
        code = bytearray(self.dean_code)
        jp = 0x53                                                  # T_PLOT's JP plotter (fix PLOTTER at 84)
        if code[jp] != 0xC3 or code[jp + 1:jp + 3] != B._w(P_):
            raise ValueError("Dean's plot hook does not end JP plotter at +0x53")
        w_head = org + len(code) + len(table)
        w_tail = w_head + HEAD_LEN
        w_tramp = w_tail + TAILW_LEN
        code[jp + 1:jp + 3] = B._w(w_tail)
        self.code = bytes(code)
        self.table = table
        self.w_head, self.w_tail, self.w_tramp = w_head, w_tail, w_tramp
        sps = prof['eraser_spsave']
        body = self.code + table + head(syms['T_PLOT']) + tailw(P_) + tramp(self.copy_erase, sps)
        end = bytes([0xED, 0x7B, sps & 0xFF, sps >> 8, 0xFB, 0xC9])
        cp = bytearray(self.copy0)
        if bytes(cp[-6:]) != end:
            raise ValueError('the eraser copy does not end LD SP,(spsave) / EI / RET')
        cp[-6:] = b'\xC3' + B._w(w_tramp + 7) + b'\x00\x00\x00'
        self.copy = bytes(cp)
        ps = prof['plot_site']
        self.sites = [(a, old, (b'\xC3' + B._w(w_head)) if a == ps else new) for a, old, new in self.orig_sites]
        self.sites += [(self.lay['plot_call'], mirror[0][1], b'\xCD' + B._w(self.copy_plot)),
                       (self.lay['erase_call'], mirror[1][1], b'\xCD' + B._w(w_tramp))]
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        page, regblock, hooks = B.altrom_image(B.rom48(), org, body)
        page = bytearray(page)
        if D6.COPY_ORG + len(self.copy) > org:
            raise ValueError('mirror copy overlaps the hooks')
        page[0:len(self.copy)] = self.copy
        self.page = bytes(page)
        self.hooks = hooks
        self.altrom = (D6.COPY_ORG, hooks[1])                      # image 1: the copy + Dean's hooks over Sinclair's ROM
        self.slot1 = (P24, regblock)
        self.altrom0 = (0x2000, 0x2000)                            # image 0: the 128K ROM 0, no build bytes
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        pats = pats + bytes(-len(pats) % 256)
        if len(pats) < 8192:
            pats = pats + bytes(8192 - len(pats))
        setup = bytearray(B.SETUP)
        setup[B.SETUP_NBLOCKS2_OFF] = (len(pats) - 8192) // 256
        self.setup_call = B.SETUP_ORG + len(setup)
        self.stub_extra = bytes(setup) + printer_back(snap, self.setup_call, B.SETUP_ORG)
        self.extra_banks = {11: pats, 12: self.page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# The verifier: nexclash/verify.py for a 128K recording + box, pixel tests, the mirror events, guards
# ---------------------------------------------------------------------------------------------

def _ret(kind, mm, R, pc):
    if kind in ('isr', 'mplot', 'merase'):
        return pc + 3, R[12]                                   # the CALL's next instruction
    return mm[R[12]] | mm[R[12] + 1] << 8, R[12] + 2          # JP plot site, eraser, wipe, box: the routine's RET


def _patched(B_, patch, sites, applied, P0, nr15, attrs, p24=None):
    for a, new in sites:
        list.__setitem__(B_.mem, slice(a, a + len(new)), list(new))
    list.__setitem__(B_.mem, slice(0x2000, 0x4000), list(patch.page))
    B_.nr[0x7F] = applied
    list.__setitem__(B_.mem, slice(0x4000, 0x5800), P0)
    B_.nr[0x15] = nr15
    B_.attrs = collections.defaultdict(lambda: [0] * 5, {k: list(v) for k, v in attrs.items()})
    if hasattr(B_, 'p24'):
        B_.p24 = list(p24 if p24 is not None else patch.page)
        B_.img = list(patch.page)
        B_.mmu1 = 0xFF
        B_.minsp = 0x10000
    return B_


def _rw_machine(hooks=(0x386E, 0x3D00)):
    """verify._M on the simulator whose writes below 0x4000 land (dizzy6._rw_simulator), with MMU slot 1 modelled:
    NEXTREG 0x51,24 shows RAM page 24 (B_.p24, kept between events), 0xFF the alt ROM image (B_.img; a write there is
    a fault, counted in B_.romw). Also the lowest SP the hook code reaches (B_.minsp)."""
    from . import verify as V
    old = V.Simulator
    V.Simulator = D6._rw_simulator()
    try:
        m = V._M(False, [0] * 8192)
    finally:
        V.Simulator = old
    ed = m.sim.after_ED
    nn0, na0 = ed[0x91], ed[0x92]
    R, mem = m.R, m.mem
    m.p24, m.img, m.mmu1, m.romw, m.minsp = None, None, 0xFF, 0, 0x10000
    HK = hooks

    def mmu1(val):
        if val == P24 and m.mmu1 != P24:
            m.img = list(mem[0x2000:0x4000]) if m.img is None else m.img
            list.__setitem__(mem, slice(0x2000, 0x4000), m.p24)
        elif val == 0xFF and m.mmu1 == P24:
            m.p24 = list(mem[0x2000:0x4000])
            list.__setitem__(mem, slice(0x2000, 0x4000), m.img)
        m.mmu1 = val

    def nn():
        pc = R[24]
        reg, val = mem[(pc + 2) & 0xFFFF], mem[(pc + 3) & 0xFFFF]
        nn0()
        if reg == 0x51:
            mmu1(val)

    def na():
        pc = R[24]
        reg, val = mem[(pc + 2) & 0xFFFF], R[0]
        na0()
        if reg == 0x51:
            mmu1(val)
    ed[0x91], ed[0x92] = nn, na

    def run(ret_pc, ret_sp, limit=3000000):
        ops, n = m.sim.opcodes, 0
        rom = list(mem[0:0x2000])
        while not (R[24] == ret_pc and R[12] == ret_sp):
            ops[mem[R[24]]]()
            if HK[0] <= R[24] < HK[1] and STACK[0] <= R[12] < m.minsp:     # SP as a data pointer elsewhere
                m.minsp = R[12]
            n += 1
            if n > limit:
                raise RuntimeError('routine did not return (%d)' % ret_pc)
        if list(mem[0:0x2000]) != rom or (m.mmu1 == 0xFF and m.img is not None and list(mem[0x2000:0x4000]) != m.img):
            m.romw += 1
    m.run = run
    return m


def verify(patch, rzx_path, stop=None, collect=0):
    """Differential test at every patched routine (plot site, eraser, wipe, box, ISR hide call, and the mirror actor's
    plot and erase calls): the original and the patched code from the same real state; registers, memory, the
    patched-screen model and the sprite pixels against the undo buffer; every pixel test against the screen without
    Dizzy; guards (patch sites, ROM reads, R, the hook stack). collect: states kept per site (clock matrix). -> dict."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from .verify import _M, _ypix, REGS
    from .analyse import classify, apply_write
    prof = patch.prof
    U = prof['undo_buffer']
    lo, hi = prof['plotter'], prof['eraser'] + 53
    sites = [(a, new) for a, old, new in patch.sites]
    excl = set()
    for a, new in sites:
        excl.update(range(a, a + len(new)))
    hook = [0] * 8192
    pats = patch.extra_banks[11]
    A, B_ = _M(True, hook), _rw_machine(patch.hooks)
    A2 = _M(False, hook)
    A.mem.lo, A.mem.hi = lo, hi
    st = {'P': None, 'applied': 0, 'nr15': 0, 'attrs': {}, 'synced': False, 'sp0': None, 'drawn': False,
          'p24': list(patch.page), 'minsp': 0x10000}
    stats = collections.Counter()
    log = []
    states = []
    pt = prof['pixel_test']
    PT = {pt + 8: 0xF0, pt + 13: 0x0F}
    ALT = patch.altrom
    CP = (D6.COPY_ORG, D6.COPY_ORG + len(patch.copy))
    MRET = patch.lay['erase_call'] + 3

    def sprite_px(m):
        out = {}
        if not (m.nr.get(0x15, 0) & 1):
            return out
        for sp in range(4):
            a = m.attrs[sp]
            if not a[3] & 0x80:
                continue
            x = a[0] | ((a[2] & 1) << 8)
            y = a[1]
            p = ((a[3] & 0x3F) << 1) | ((a[4] >> 6) & 1)
            pat = pats[p * 128:(p + 1) * 128]
            for yy in range(16):
                for xx in range(16):
                    b = pat[yy * 8 + xx // 2]
                    c = (b >> 4) if xx % 2 == 0 else (b & 15)
                    if c:
                        out[(x + xx - 32, y + yy - 32)] = c
        return out

    def undo_px(mem):
        col, h, ptr = mem[U], mem[U + 1], mem[U + 2] | mem[U + 3] << 8
        d = {}
        for r in range(h):
            row = mem[ptr + 2 * r] | mem[ptr + 2 * r + 1] << 8
            for k in range(4):
                v = mem[U + 4 + 4 * r + k]
                if v:
                    d[row + col + k] = d.get(row + col + k, 0) ^ v
        return d

    def check(kind, snap, R, pc):
        ret_pc, ret_sp = _ret(kind, snap, R, pc)
        regs, P0 = list(R), list(st['P'])
        if collect and stats['collected ' + kind] < collect:
            stats['collected ' + kind] += 1
            states.append((kind, pc, list(snap), regs, P0, st['applied'], st['nr15'],
                           {k: list(v) for k, v in st['attrs'].items()}, list(st['p24'])))
        mirror = kind in ('mplot', 'merase')
        if mirror:                       # the original's routine on the patched-screen model (the mirrored Dizzy stays
            A2.load(snap, regs)          # on the ULA in both): the copy must give the same memory and registers
            list.__setitem__(A2.mem, slice(0x4000, 0x5800), P0)
            O = A2
        else:
            A.load(snap, regs)
            A.mem.P = list(P0)
            O = A
        B_.load(snap, regs)
        _patched(B_, patch, sites, st['applied'], P0, st['nr15'], st['attrs'], st['p24'])
        O.run(ret_pc, ret_sp)
        B_.run(ret_pc, ret_sp)
        st['minsp'] = min(st['minsp'], B_.minsp)
        if B_.romw:
            stats['WRITE INTO THE ALT ROM (' + kind + ')'] += 1
            B_.romw = 0
        if B_.mmu1 != 0xFF:
            stats['SLOT 1 LEFT ON RAM PAGE 24 (' + kind + ')'] += 1
        bad = [i for i in REGS if O.R[i] != B_.R[i]]
        dead = range(ret_sp - 40, ret_sp)
        skip = excl | {patch.smod, patch.smod + 1} if mirror else excl
        md = [a for a in range(0x5800, 65536) if O.mem[a] != B_.mem[a] and a not in skip and a not in dead]
        if mirror:
            sd = [a for a in range(0x4000, 0x5800) if B_.mem[a] != O.mem[a]]
        else:
            sd = [a for a in range(0x4000, 0x5800) if B_.mem[a] != A.mem.P[a - 0x4000]]
        if bad or md or sd:
            if not bad and not sd and all(U <= a < U + 4 + 4 * 32 for a in md) and kind == 'plot' \
                    and any(snap[a] != P0[a - 0x4000] for a in range(0x4000, 0x5800)):
                stats['plot: undo buffer differs (original ghost pixels, harmless)'] += 1
            elif bad == [2] and not sd and all(U <= a < U + 4 + 4 * 32 for a in md) and kind == 'plot' \
                    and any(snap[a] != P0[a - 0x4000] for a in range(0x4000, 0x5800)) and _b_dead(O, B_.R[2], ret_pc, ret_sp):
                stats['plot: B differs (the original plots over the mirrored Dizzy\'s pixels under him; B dead: the '
                      'game runs on identically with either value)'] += 1
            else:
                stats[kind + ' MISMATCH'] += 1
                if len(log) < 6:
                    log.append((kind, pc, 'regs', bad, 'mem', [hex(x) for x in md[:6]], 'screen', [hex(x) for x in sd[:6]]))
        else:
            stats[kind + ' ok'] += 1
        if B_.nr.get(7, 0) & 3 != 0:
            stats[kind + ' EXIT SPEED MISMATCH'] += 1
        st['applied'] = B_.nr.get(0x7F, 0)
        st['nr15'] = B_.nr.get(0x15, 0)
        st['attrs'] = {k: list(v) for k, v in B_.attrs.items()}
        st['p24'] = list(B_.p24)
        if mirror:
            st['P'] = list(B_.mem[0x4000:0x5800])          # the model follows the mirrored Dizzy on the ULA
        vis = bool(st['nr15'] & 1)
        if kind == 'plot':
            sp = sprite_px(B_)
            miss = wrong = 0
            for a, v in undo_px(A.mem).items():
                y = _ypix(a)
                x0 = (a & 31) * 8
                for bit in range(8):
                    if (v >> (7 - bit)) & 1 and (x0 + bit, y) not in sp:
                        miss += 1
            for (x, y), c in sp.items():
                a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
                if not (0 <= x < 256 and 0 <= y < 192) or ((A.mem[a] >> (7 - (x & 7))) & 1) != (1 if c == 2 else 0):
                    wrong += 1
            stats['sprite pixel-perfect' if not (miss or wrong) else 'SPRITE PIXEL MISMATCH'] += 1
        elif kind in ('box', 'wipe'):
            stats[kind + (' hides sprite' if not vis else ' LEAVES SPRITE VISIBLE')] += 1
        elif kind == 'isr' and not st['applied'] and vis:
            stats['ISR: SPRITE VISIBLE WHILE ERASED'] += 1

    ev = {prof['plot_site']: 'plot', prof['eraser']: 'erase', prof['wipe']: 'wipe', prof['isr_hide_call']: 'isr',
          prof['box']: 'box', patch.lay['plot_call']: 'mplot', patch.lay['erase_call']: 'merase'}
    REG = [None]
    MEM = [None]
    WR = bytearray(1024)
    TA = {}
    ROMR = {}
    LASTW = {}
    last = [None]

    def flat():
        m = MEM[0].memory
        return list(m[0]) + list(m[1]) + list(m[2]) + list(m[3])

    def install(memory):
        base = type(memory)
        MG, MS = base.__getitem__, base.__setitem__
        MEM[0] = memory

        class W(base):
            def __getitem__(s, a):
                R = REG[0]
                if type(a) is int and R is not None:
                    pc = R[24]
                    if TAIL <= a < TAIL + TAIL_MAX and a not in TA:
                        TA[a] = 'r'
                    if a == pc:
                        if a in ev and last[0] != (a, R[25]):
                            last[0] = (a, R[25])
                            k = ev[a]
                            if k == 'erase' and (MG(s, R[12]) | MG(s, R[12] + 1) << 8) == MRET:
                                k = None                   # the mirror erase's own entry: checked at its CALL
                            if k == 'wipe' and not st['synced']:
                                st['synced'] = True
                                st['P'] = [MG(s, x) for x in range(0x4000, 0x5800)]
                                st['applied'] = 0
                            if st['synced'] and k:
                                check(k, flat(), R, a)
                                if k in ('plot', 'erase'):
                                    st['drawn'] = k == 'plot'
                        elif MG(s, a) == 0xED and MG(s, (a + 1) & 0xFFFF) in (0x5F, 0x4F):
                            stats['R READ OR WRITTEN BY THE GAME (LD A,R / LD R,A)'] += 1
                    elif st['synced']:
                        if a < 0x4000:
                            stats['ROM data reads'] += 1
                            ROMR[pc] = (min(a, ROMR.get(pc, (a, a))[0]), max(a, ROMR.get(pc, (a, a))[1]))
                            if ALT[0] <= a < ALT[1]:
                                stats['ALT ROM BUILD BYTES READ BY THE GAME'] += 1
                        elif a < 0x5800 and not (lo <= pc < hi):
                            if pc in PT:
                                m = PT[pc]
                                stats['pixel tests'] += 1
                                if bool(MG(s, a) & m) != bool(st['P'][a - 0x4000] & m):
                                    stats['PIXEL TESTS THAT DEPEND ON THE PLAYER'] += 1
                                    if len(log) < 6:
                                        log.append(('pixel test', hex(a), 'pc', hex(pc), 'screen %02X model %02X' % (
                                            MG(s, a), st['P'][a - 0x4000]), 'last writers %s' % (LASTW.get(a),)))
                            elif MG(s, a) != st['P'][a - 0x4000]:
                                stats['screen reads where Dizzy is drawn (pc %04X)' % pc] += 1
                    if a < 0x4000 and a == pc and st['synced']:
                        stats['ROM CODE RUN BY THE GAME'] += 1
                return MG(s, a)

            def __setitem__(s, a, v):
                R = REG[0]
                if R is not None and type(a) is int:
                    if TAIL <= a < TAIL + TAIL_MAX and a not in TA:
                        TA[a] = 'w'
                    if 0x4000 <= a < 0x5800:
                        LASTW[a] = (LASTW.get(a, ()) + ('%04X:%02X>%02X' % (R[24], MG(s, a), v),))[-4:]
                    if st['synced'] and 0x4000 <= a < 0x5800 and not (lo <= R[24] < hi):
                        apply_write(st['P'], a, MG(s, a), v, classify(_code_list(s, MG, R[24]), R[24]))
                    if st['sp0'] - 1024 <= a < st['sp0']:
                        WR[a - st['sp0'] + 1024] = 1
                    if a in excl and st['synced']:
                        stats['PATCH SITE WRITTEN BY THE GAME'] += 1
                        if len(log) < 6:
                            log.append(('site write', hex(a), 'pc', hex(R[24])))
                MS(s, a, v)
        memory.__class__ = W
        return memory

    class S(Simulator):
        def __init__(self, memory, registers=None, state=None, config=None):
            super().__init__(install(memory), registers, state, config)
            REG[0] = self.registers
            st['synced'] = False
            if st['sp0'] is None:
                st['sp0'] = self.registers[12]

    old = (rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    args = ['--python', '--quiet', '--no-screen', '--fps', '0'] + (['--stop', str(stop)] if stop else [])
    try:
        rzxplay.main(args + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.Simulator, rzxplay.CSimulator = old
    REG[0] = None
    low, a, gap = st['sp0'], st['sp0'] - 1, 0          # stack low-water mark (analyse's: contiguous writes below SP)
    while a > st['sp0'] - 1024 and gap < 8:
        if WR[a - st['sp0'] + 1024]:
            low, gap = a, 0
        else:
            gap += 1
        a -= 1
    stats['stack low water 0x%04X' % low] += 1
    stats['hook stack low water 0x%04X' % st['minsp']] += 1
    if st['minsp'] < CODE_END:
        stats['HOOK STACK BELOW THE STACK AREA (code at 0x%04X)' % (CODE_END - 1)] += 1
    if ROMR:
        log.append(('ROM data reads by pc', sorted(('%04X' % p, '%04X-%04X' % r) for p, r in ROMR.items())[:8]))
    rd = sorted(a for a, x in TA.items() if x == 'r')
    stats['undo buffer (tail) first access: %d written, %d read' % (sum(1 for x in TA.values() if x == 'w'), len(rd))] += 1
    if rd:
        stats['TAIL BYTES READ BEFORE WRITTEN'] += 1
        log.append(('tail read first', [hex(x) for x in rd[:6]]))
    failed = any(_bad(k) for k in stats)
    return {'passed': not failed and stats['plot ok'] > 0, 'stats': dict(stats), 'examples': log, 'states': states}


def _b_dead(O, b, ret_pc, ret_sp, n=20000):
    """The original from the plot's return, once with its own B and once with the build's: n instructions later every
    other register and all RAM must be the same (B is overwritten before any use)."""
    from .verify import _M
    out = []
    for v in (O.R[2], b):
        m = _M(False, [0] * 8192)
        m.load(list(O.mem[0:65536]), list(O.R))
        m.R[2] = v
        ops = m.sim.opcodes
        for _ in range(n):
            ops[m.mem[m.R[24]]]()
        out.append((list(m.R[0:2]) + list(m.R[3:13]) + [m.R[24]], list(m.mem[0x4000:0x10000])))
    return out[0] == out[1]


def _bad(k):
    return any(w in k for w in ('MISMATCH', 'VISIBLE', 'BY THE GAME', 'DEPEND', 'BELOW', 'ALT ROM', 'LEFT ON', 'BEFORE WRITTEN'))


_CODE = [0] * 65536


def _code_list(mem, get, pc):
    """analyse.classify reads the writer's code (pc - 24 .. pc) from a plain list: those bytes of the paged view."""
    for x in range(pc - 24, pc + 1):
        _CODE[x & 0xFFFF] = get(mem, x & 0xFFFF)
    return _CODE


# ---------------------------------------------------------------------------------------------
# The every-site clock matrix, on states the replays captured
# ---------------------------------------------------------------------------------------------

def clock_matrix(patch, states):
    """Each hook (plot, erase, wipe, box, ISR hide, the mirror plot and erase) from a captured state, entered at NR 7 =
    0-3: the exit speed must be the incoming one and the result the same (registers, memory outside the dead stack
    the head's latch sits in, the sprite layer, page 24)."""
    from .hooklib import every_site
    from .verify import REGS
    sites = [(a, new) for a, old, new in patch.sites]
    by = {}
    for s in states:
        by.setdefault(s[1], s)

    def run(site, clock):
        kind, pc, snap, regs, P0, applied, nr15, attrs, p24 = by[site]
        ret_pc, ret_sp = _ret(kind, snap, regs, pc)
        B_ = _rw_machine(patch.hooks)
        B_.load(snap, regs)
        _patched(B_, patch, sites, applied, P0, nr15, attrs, p24)
        B_.nr[7] = clock
        B_.run(ret_pc, ret_sp)
        m = bytearray(B_.mem[0x4000:0x10000])
        for a in range(ret_sp - 40, ret_sp):
            m[a - 0x4000] = 0
        mem = hashlib.md5(bytes(m) + bytes(B_.p24)).hexdigest()
        nr = tuple(sorted((k, v) for k, v in B_.nr.items() if k != 7))
        return B_.nr.get(7, 0) & 3, (tuple(B_.R[i] for i in REGS), mem, nr, B_.mmu1, B_.romw,
                                     tuple(sorted((k, tuple(v)) for k, v in B_.attrs.items())))
    return every_site(sorted(by), run)


def forced35(patch):
    """The tail's restore (LD A,H / NEXTREG 7,A) replaced by NEXTREG 7,0: a broken build."""
    n = copy.copy(patch)
    page = bytearray(patch.page)
    i = patch.w_tail - 0x2000 + 2
    if page[i:i + 4] != b'\x7C\xED\x92\x07':
        raise ValueError('speed tail layout')
    page[i:i + 4] = b'\xED\x91\x07\x00'
    n.page = bytes(page)
    return n


def unit_tests(patch, states):
    cm, rows = clock_matrix(patch, states)
    c = collections.Counter({'clock cases': cm['cases']})
    for k, v in cm.items():
        if k.endswith('!'):
            c[k] += v
    cn, _ = clock_matrix(forced35(patch), states)
    caught = sum(v for k, v in cn.items() if k.endswith('!'))
    c['negative control forced 3.5 MHz exit caught' if caught else 'negative control forced 3.5 MHz exit not caught!'] += caught or 1
    return c


def _page_edit(patch, find, repl, what, start=None):
    n = copy.copy(patch)
    page = bytearray(patch.page)
    i = bytes(page).find(find, (B.T['slot1']['org'] if start is None else start) - 0x2000)
    if i < 0:
        raise ValueError(what)
    page[i:i + len(repl)] = repl
    n.page = bytes(page)
    return n


def negatives(patch):
    """Broken builds the verifier must catch: Dean's controls (the patterns' nibbles swapped, the hook frame table
    rotated), the ISR hook that never hides an erased Dizzy, the wipe and box hooks that leave him visible; and the
    mirror's: the trampoline that never maps RAM page 24 (the eraser copy's own operand stays the alt ROM's), and the
    actor's plot sent to the patched plotter (the mirrored Dizzy never drawn: the 48K slot1 build's hazard)."""
    out = {}
    n = copy.copy(patch)
    b = bytearray(patch.extra_banks[11])
    for i in range(len(b)):
        b[i] = ((b[i] & 15) << 4) | (b[i] >> 4)
    n.extra_banks = dict(patch.extra_banks)
    n.extra_banks[11] = bytes(b)
    out['pattern nibbles swapped'] = n
    n = copy.copy(patch)
    page = bytearray(patch.page)
    t0 = B.T['slot1']['syms']['table'] - 0x2000
    tab = page[t0:t0 + len(patch.table)]
    page[t0:t0 + len(patch.table)] = tab[8:] + tab[:8]
    n.page = bytes(page)
    out['hook frame table rotated'] = n
    out['ISR hook never hides Dizzy'] = _page_edit(patch, bytes.fromhex('ED911500C1F1C3'), b'\x00\x00\x00\x00', 'T_ISR')
    out['wipe hook leaves Dizzy visible'] = _page_edit(patch, bytes.fromhex('ED911500DD21'), b'\x00\x00\x00\x00', 'T_WIPE')
    out['box hook leaves Dizzy visible'] = _page_edit(patch, bytes.fromhex('ED911500' + '3A'), b'\x00\x00\x00\x00', 'T_BOX')
    n = _page_edit(patch, bytes.fromhex('ED911500C1F1C3'), b'\x00\x00\x00\x00', 'T_ISR')
    out['ISR and wipe hooks never hide Dizzy'] = _page_edit(n, bytes.fromhex('ED911500DD21'), b'\x00\x00\x00\x00', 'T_WIPE')
    out['mirror trampoline never maps page 24'] = _page_edit(patch, bytes([0xED, 0x91, 0x51, P24]), b'\x00\x00\x00\x00',
                                                             'tramp', patch.w_tramp)
    n = copy.copy(patch)
    pc_ = patch.lay['plot_call']
    n.sites = [(a, old, (b'\xCD' + B._w(patch.prof['plotter'])) if a == pc_ else new) for a, old, new in patch.sites]
    out['mirror plot sent to the patched plotter'] = n
    return out


# ---------------------------------------------------------------------------------------------
# auto
# ---------------------------------------------------------------------------------------------

def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say("Engine    : yolk128 (Prince of the Yolkfolk 128K: Dean's tid_mirror build on the 128K release; whole alt ROM "
        'image with the mirror copy; plot hook at 28 MHz)')
    s = zt.Z80Snapshot(z80)
    mem = [0] * 0x4000 + list(s.banks[5] + s.banks[2] + s.banks[0])
    plain = os.path.join(out, name + '.nex')
    pc_ = PlainPrinter128()
    conv = zt.convert(z80, plain, None, True, quiet=True, patch=pc_)
    bad = check(plain, z80, pc_, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X, %d bytes)' % (os.path.basename(plain), md5(plain), 'OK' if not bad else
                                                                  'MISMATCH %s' % str(bad[:3])[:300], conv[1], len(conv[2])))
    patch = YolkPatch128(mem)
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(z80, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, z80, patch, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Sprites   : %s  %s  boot %s  (%d patterns; tail 0x%04X, %d bytes; mirror copy 0x%04X-0x%04X; hooks 0x%04X-0x%04X)' % (
        os.path.basename(spr), md5(spr), 'OK' if not bad2 else 'MISMATCH %s' % str(bad2[:3])[:300], patch.num_patterns,
        conv[1], len(conv[2]), D6.COPY_ORG, D6.COPY_ORG + len(patch.copy) - 1, patch.hooks[0], patch.hooks[1] - 1))
    ok = not bad and not bad2
    say('Boot      : simulated stub + alt ROM fill + tail, printer buffer as NEXLOAD leaves it: %s' % (
        'OK (registers, RAM, ROM view, paging, $8C; plain and sprites)' if ok else 'MISMATCH %s' % str((bad + bad2)[:3])[:300]))
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'))
    if getattr(a, 'decisions', None):
        say('Result    : %s (rebuild from stored decisions, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
    states = []
    total = collections.Counter()
    for r in a.rzx or []:
        v = verify(patch, r, stop=getattr(a, 'quick', None), collect=2)
        states += v['states']
        s_ = {k: x for k, x in v['stats'].items() if not k.startswith('collected')}
        total.update(s_)
        ok = ok and v['passed']
        say('Verify    : %s  %s -> %s %s' % (os.path.basename(r), ', '.join('%s %d' % kv for kv in sorted(s_.items())),
                                            'IDENTICAL' if v['passed'] else 'FAILED', str(v['examples'])[:300]))
    if a.rzx:
        miss = [k for k in ('plot ok', 'erase ok', 'wipe ok', 'isr ok', 'box ok', 'mplot ok', 'merase ok', 'pixel tests')
                if not total[k]]
        say('Coverage  : every hook ran: %s' % ('yes' if not miss else 'NO, never: %s' % ', '.join(miss)))
        ok = ok and not miss
        neg = negatives(patch)
        caught = 0
        for what, n in neg.items():
            for r in a.rzx:                              # each recording in turn until one catches it
                v = verify(n, r, stop=getattr(a, 'quick', None))
                det = not v['passed']
                if det:
                    break
            caught += det
            say('Negative  : %s -> %s %s' % (what, ('DETECTED by %s' % os.path.basename(r)) if det else 'NOT DETECTED!',
                                            {k.replace('MISMATCH', 'difference'): x for k, x in v['stats'].items() if _bad(k)}))
            # 'difference' (as tid128.py): a report holding MISMATCH fails the run, and these counters are the broken
            # build's, wanted
        ok = ok and caught == len(neg)
        if states:
            u = unit_tests(patch, states)
            cm, rows = clock_matrix(patch, states)
            cn, _ = clock_matrix(forced35(patch), states)
            badc = {k: x for k, x in cm.items() if k.endswith('!')}
            c2 = sum(x for k, x in cn.items() if k.endswith('!'))
            st = sorted({r['site'] for r in rows})
            ok = ok and not badc and c2 > 0 and not any(k.endswith('!') for k in u)
            say('Clocks    : every-site matrix, %d hook sites (%s) x 4 incoming clocks = %d cases: exit speed = the '
                'incoming one, result the same at every clock -> %s; negative "forced 3.5 MHz exit" (the plot hook\'s '
                'restore) caught at %d cases -> %s' % (len(st), ', '.join('0x%04X' % x for x in st), cm['cases'],
                                                       'PASS' if not badc else 'FAIL %s' % badc, c2,
                                                       'DETECTED' if c2 else 'NOT DETECTED!'))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
