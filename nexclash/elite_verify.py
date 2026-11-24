"""Elite verifier (games/elite.md "## Build plan" Verify, ENGINE_CONTRACT): the differential test per main-loop pass.

From a state the recording reaches at the main loop's top (0x7471, outside the ISR), the patched build runs PASSES
passes as on the Next (28 MHz, interrupts by the clock: h_isr, its owed game ISR bodies, the tick wait, the 50 fps
renders); the original runs the same passes with its interrupts placed where the patched run ran the game's ISR body
(0xFF25), counted in main-line instructions - the ISR pattern is the engine's design (detail: 16 bodies per 25
frames), the logic between must be the original's. After each pass: registers (CMP), banks 0-7 and the port writes
(ULA, AY, 7FFD; not the Next's) must match, except what the design changes on purpose (EXCLUDED below).
Render (alpha = 1): the first render of each pass is run at full weight (A = TICK: cur as recorded, no interpolation,
no own turning, scenery at weight 0) and its Layer 2 back buffer must equal the pass's mono buffer bit for bit
(lines 1-118, x 9-246: inside the view frame, which stays the ULA's). The render saves and restores all game RAM it writes, so forcing
its weight leaves the logic as it was - the logic compare checks that too.

Main-line count: instructions at 0x4000+ outside the ISR, outside a hook context, not a patch-site byte, not a HALT
repeat. A hook context opens when the main line enters the alt ROM (an RST / CALL / JP site, or a ROM routine the
game calls) and closes when the PC is back in RAM with SP at the depth it entered with (+2: a RET), or on the
PFILL stubs' own exit (SP 0x8FB6 at the blit). Game code a hook runs on its own stacks (render: RSTK, the wrapper's
0x4020; h_ship: HSTK) is the engine's, not the main line.
R: the game reads R at 0x7992 / 0x799B only (the star routine: bits 0-1 are each star's +-1 jitter per pass, kept
in the star table 0x7A39). Both runs get the same supplied sequence there (main line; inside a hook the render's
own stars get a constant), and R is not compared (CMP): the hooks do not preserve R. Another sequence changes the
star table (unit test: caught). Natural play: the stars jitter otherwise than the original's (visual only).
I: 0x39 in the build (the IM 2 table in the alt ROM, nexclash/elite.py IM2_I), 0xFD in the original: not compared.
"""
import collections
import hashlib
from pathlib import Path

from . import hooklib
from . import elite as E

CLEAR_SITE = 0x8080             # the buffer clear (JP h_clear): the pass's drawing starts
PASS_PC = 0x7471                # the main loop's top (JR 0x7471 at 0x74A8; probe pass_calls.py)
ISR_ENTRY = 0xFEFE              # the original's IM 2 target (JR 0xFF25)
ISR_BODY = 0xFF25               # the game's ISR body: h_isr jumps here when one is owed
R_SITES = (0x7992, 0x799B)      # the only LD A,R (ED 5F) in game RAM
FRAME = 228 * 311               # 128K frame, T at 3.5 MHz
FAST = 7.0                      # 28 MHz against 3.5 (wait states: about 7, LEARNINGS 2.1f)
TICK = 10                       # asm TICK
STATE_PG = 26                   # asm STATE_PG
S_BACK = 0x0005                 # asm S_BACK (state page offset)
TRANS = 0xE3
BASE_BK = 14                    # asm BASE_BK: the logic pass's mirrored draws (base of every render)
RSTK, RSTKLEN = 0x7470, 0x60    # asm RSTK / RSTKLEN (render stack, saved and restored)
PF_SITES = (0x8BCD, 0x8CCD, 0x8DC3)
PF_EXITS = frozenset((s + 3, 0x8FB6) for s in PF_SITES)     # PFILL .orig: JP site+3 with SP 0x8FB6
CMP = E.CMP                     # not I (IM 2 table) nor R (supplied at R_SITES)
PASSES = 3                      # passes per case (the engine's lists and tick warm up after the first)
EVERY = 25                      # every 25th pass of a recording is a case
NEXT_PORTS = (0x243B, 0x253B, 0x303B)
# What the design changes on purpose (banks 0-7): the mono buffer (cleared after each flight pass, games/elite.md M2),
# the ULA viewport rows 8-127 (left blank, ulaclr, rowfix), the hack's save of row 56 (rowfix), MIRF (0x581E, the
# hooks' mirror flag in an attribute byte), the condition light's right cells (h_light: white), dead stack (the
# main one below SP; AI_STACK: the hack's 0xDA25 runs 0xA2C0 on SP 0x4220 and leaves it - an interrupt without a
# game ISR body pushes PC + AF there, the original takes none at that point; Witch pass 200).
BUFFER = (0x0000, 0x0FE0)       # bank 0: 0xC000-0xCFDF
ROW56_SAVE = (0x3FD0, 0x3FE0)   # bank 0: 0xFFD0-0xFFDF, the hack's save of 0x40F0-0x40FF (row 56, rowfix)
STACK_SAVE = 0x3FE0             # bank 0: 0xFFE0-0xFFFF, its save of 0x4100-0x411F (the game's stack row, 0xF8EC):
HACK_SP = 0xF90A                # dead below the SP it saved at 0xF8E7 (LD (0xF90A),SP)
AI_STACK = (0x4200, 0x4220)
MIRF = 0x581E
LIGHT_WHITE = (0x5A29, 0x5A49)
_CACHE = {}


def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


def scr_y(o):
    """ULA pixel offset (0-0x17FF) -> y."""
    return ((o >> 5) & 0xC0) | ((o >> 8) & 7) | ((o >> 2) & 0x38)


def scr_off(y, col):
    return ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | col


# ------------------------------------------------------------------------------------------------ machine

class Mem(object):
    """The Next's 64K as this build maps it: 8K MMU slots (NR $50-$57; 0xFF in slots 0-1 = the ROM image), Layer 2
    write-over (port 0x123B bit 0: writes below 0x4000 - 0xC000 with segment 3 - go to the Layer 2 bank of NR $12,
    or NR $13 with bit 3). pages: {8K page: bytearray}."""

    def __init__(self, pages, rom, nr):
        self.pages = pages
        self.rom = [bytearray(rom[0:0x2000]), bytearray(rom[0x2000:0x4000])]
        self.nr = nr
        self.l2 = 0
        self.mmu = [0xFF, 0xFF, 10, 11, 4, 5, 0, 1]
        self.map = [None] * 8
        for s in range(8):
            self._map(s)

    def page(self, p):
        b = self.pages.get(p)
        if b is None:
            b = self.pages[p] = bytearray(8192)
        return b

    def _map(self, s):
        p = self.mmu[s]
        self.map[s] = self.rom[s] if s < 2 and p == 0xFF else self.page(p)

    def set_mmu(self, s, v):
        self.mmu[s] = v
        self._map(s)

    def __getitem__(self, a):
        return self.map[a >> 13][a & 0x1FFF]

    def __setitem__(self, a, v):
        if self.l2 & 1 and a < (0xC000 if self.l2 & 0xC0 == 0xC0 else 0x4000):
            bank = self.nr.get(0x13, 11) if self.l2 & 8 else self.nr.get(0x12, 8)
            seg = self.l2 >> 6
            p = bank * 2 + (a >> 13) if seg == 3 else (bank + seg) * 2 + (a >> 13)
            self.page(p)[a & 0x1FFF] = v
            return
        s = a >> 13
        if s < 2 and self.mmu[s] == 0xFF:
            return
        self.map[s][a & 0x1FFF] = v

    def __len__(self):
        return 65536

    def bank(self, b):
        return bytes(self.page(2 * b)) + bytes(self.page(2 * b + 1))

    def l2_pixel(self, bank, x, y):
        o = (y & 63) << 8 | x
        return self.page((bank + (y >> 6)) * 2 + (o >> 13))[o & 0x1FFF]


class Model(hooklib.NextModel):
    """NextModel + this build's machine: MMU slots, Layer 2 port; the game's ports logged (ULA, AY, 7FFD), no keys."""

    def __init__(self, sim, mem, line=0, speed=0):
        self.mem = mem
        self.log = []
        super().__init__(sim, speed=speed, t_line=228, lines=311, fast=FAST, line=line)
        mem.nr = self.nr

    def nextreg(self, reg, v):
        if 0x50 <= reg <= 0x57:
            self.mem.set_mmu(reg - 0x50, v)
        super().nextreg(reg, v)

    def read_port(self, regs, port):
        if port == 0x123B:
            return self.mem.l2
        if port == 0x253B:
            if 0x50 <= self.sel <= 0x57:           # the MMU slots read back (h_isr keeps slot 0's page)
                return self.mem.mmu[self.sel - 0x50]
            return super().read_port(regs, port)
        if port & 0xFF == 0x1F:
            return 0
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if port == 0x123B:
            self.mem.l2 = value
        elif port in NEXT_PORTS or port & 0xFF in (0x57, 0x5B, 0x6B):
            super().write_port(regs, port, value, *x)
        elif port & 1 == 0:
            self.log.append(('fe', value & 0x1F))
        elif port & 0x8002 == 0:
            self.log.append(('7ffd', value))
        elif port & 0xC002 == 0xC000:
            self.log.append(('ay sel', value))
        elif port & 0xC002 == 0x8000:
            self.log.append(('ay', value))
        else:
            self.log.append(('port', port, value))


def _site_bytes(patch):
    """Addresses the main-line count leaves out in both runs: the patch sites, and the fills' stack blits after
    them (POP AF / LD SP,HL / JR / 16 x PUSH AF, to site + 0x17) - a mirroring PFILL stub (the explosion flash, drawn
    by the main line) writes those bytes itself and rejoins after the chain, a buffer-only one runs the original's."""
    s = set(a + i for a, old, new in patch.sites for i in range(len(old)))
    for a in PF_SITES:
        s.update(range(a, a + 0x17))
    return frozenset(s)


def _setup(patch):
    """The build's Next state after the stub's CALL setup (asm setup, run here from the stub bank as on the Next):
    -> {rom: alt ROM image 0x0000-0x3FFF, pages: engine pages, nr, attrs, pattern, l2}. Cached per build."""
    from . import nextboot
    key = ('setup', hashlib.md5(patch.page + patch.altrom_low[1] + patch.stub_extra).hexdigest())
    if key in _CACHE:
        return _CACHE[key]
    rom = bytes(nextboot.alt_image(patch))
    p20 = bytearray(8192)
    p20[0x1000:0x1000 + len(patch.stub_extra)] = patch.stub_extra
    pages = {20: p20, 21: bytearray(8192)}
    for b, data in patch.extra_banks.items():
        pages[2 * b], pages[2 * b + 1] = bytearray(data[:0x2000]), bytearray(data[0x2000:])
    mem = Mem(pages, rom, {})
    mem.set_mmu(6, 20)
    mem.set_mmu(7, 21)
    sim = _sim_class()(mem, {}, config={'int_active': 0})
    model = Model(sim, mem, 0, speed=0)
    sim.registers[12] = 0xDF00
    hooklib.call(sim, patch.setup_call)
    st = dict(rom=rom, pages={p: bytes(v) for p, v in mem.pages.items() if p >= 16 and p not in (20, 21)},
              nr={k: v for k, v in model.nr.items() if not 0x50 <= k <= 0x57}, attrs=[list(a) for a in model.attrs],
              pattern=bytes(model.pattern), l2=mem.l2)
    _CACHE[key] = st
    return st


class Machine(object):
    """One run from a captured state {'regs', 'o7ffd', 'banks'} at PASS_PC. patch None: the original, its interrupts
    from `events` per pass. rseq: the values LD A,R returns at R_SITES on the main line. neg_rom {addr: byte}: alt ROM
    bytes changed (a negative control)."""

    def __init__(self, st, patch=None, line=0, rseq=None, render_check=False, neg_rom=None):
        if st['o7ffd'] & 0x17 != 0x10:
            raise ValueError('state: 7FFD 0x%02X (expected ROM 1, bank 0)' % st['o7ffd'])
        banks = [bytearray(b) for b in st['banks']]
        self.patched = patch is not None
        if self.patched:
            for a, old, new in patch.sites:
                o = a & 0x3FFF
                banks[E._bank_of(a)][o:o + len(new)] = new
            setup = _setup(patch)
            rom = bytearray(setup['rom'])
            for a, v in (neg_rom or {}).items():
                rom[a] = v
        else:
            from .build import rom48
            rom = rom48()
        pages = {}
        for n in range(8):
            pages[2 * n], pages[2 * n + 1] = bytearray(banks[n][:0x2000]), bytearray(banks[n][0x2000:])
        if self.patched:
            for p, data in setup['pages'].items():
                pages[p] = bytearray(data)
        self.mem = Mem(pages, rom, {})
        self.sim = _sim_class()(self.mem, {}, config={'int_active': 0})
        R = self.R = self.sim.registers
        R[:] = list(st['regs'])
        self.model = Model(self.sim, self.mem, line, speed=3 if self.patched else 0)
        if self.patched:
            R[14] = E.IM2_I
            self.model.nr.update(setup['nr'])
            self.model.attrs = [list(a) for a in setup['attrs']]
            self.model.pattern = bytearray(setup['pattern'])
            self.mem.l2 = setup['l2']
            self.syms = patch.syms
            self.skip = _site_bytes(patch)
            self.site_pcs = frozenset(a for a, _, _ in patch.sites)
            lo = patch.low_code                 # from 0x0010; rst18 = JP h_plot
            hp = lo[9] | lo[10] << 8
            if lo[8] != 0xC3 or rom[hp + 9] != 0x77 or rom[hp + 16] != 0x71:
                raise ValueError('h_plot layout changed (asm): its two buffer writes not found')
            self.wr_u, self.wr_m = hp + 9, hp + 16      # h_plot's LD (HL),A (buffer only) / LD (HL),C (mirrored)
        else:
            self.skip = _site_bytes(_CACHE.setdefault('sites_of', E.ElitePatch()))
            self.site_pcs = frozenset()
        self.rseq, self.rk = list(rseq or [(37 * k + 11) & 0xFF for k in range(97)]), 0
        self.next_int = (int(self.model.now()) // FRAME + 1) * FRAME
        self.game = 0               # main-line instructions
        self.isr = []               # [return PC, SP, body run] of the handlers running
        self.ctx = None             # SP at the hook context's entry (patched)
        self.c = collections.Counter()
        self.hits = collections.Counter()
        self.render_check = render_check and self.patched
        self.renders = []           # (differing pixels, lit pixels, buffer, back bank) per checked render
        # Per buffer bit, how the logic pass last took it 1 -> 0 (cleared by any 0 -> 1): xoff by a mirrored write
        # (text XORed onto a set pixel: h_plot makes the base pixel transparent), uoff by a buffer-only write.
        self.xoff, self.uoff, self.xrec = bytearray(0x1000), bytearray(0x1000), False
        self.watch, self.watched = (), []   # buffer offsets to log writes of (probes): (offset, PC, mirrored, old, new)
        self.trace, self.traced = (), []    # PCs to log (probes): (PC, SP, main-line count, hook context, in ISR, stack)

    def _buf_write(self, mirrored):
        R = self.R
        o = (R[6] << 8 | R[7]) - 0xC000
        if not 0 <= o < 0x1000:
            return
        old, new = (R[0], R[3]) if mirrored else (self.mem[o + 0xC000], R[0])
        if o in self.watch:
            sp = R[12] + (4 if mirrored else 0)
            self.watched.append((o, self.mem[sp] | self.mem[sp + 1] << 8, mirrored, old, new, self.xrec))
        if not self.xrec:
            return
        keep, off = ~(new & ~old) & 0xFF, old & ~new
        a, b = (self.xoff, self.uoff) if mirrored else (self.uoff, self.xoff)
        a[o] = a[o] & keep | off
        b[o] &= keep & ~off

    def _accept(self, prev):
        R = self.R
        pc, sp = R[24], R[12]
        halt = self.mem[pc] == 0x76
        if halt:
            R[24] = (pc + 1) & 0xFFFF       # on a HALT: the handler returns after it (SkoolKit pushes the HALT's own
        if self.sim.accept_interrupt(R, self.mem, prev):        # address unless int_active, which is 0 here)
            self.isr.append([(pc + halt) & 0xFFFF, sp, False])
            return True
        R[24] = pc
        return False

    def run(self, events=None, limit=30_000_000):
        """One pass: to PASS_PC at the starting SP. Patched: -> the ISR events [(kind, count)] ('body': the game's
        ISR body ran, 'empty': an interrupt without it). Original: takes `events`; -> the ones it could not place."""
        R, m, ops, model = self.R, self.mem, self.sim.opcodes, self.model
        patched, skip = self.patched, self.skip
        stop_sp = R[12]
        out, ev = [], list(events or [])
        pend, prev, n = None, R[24], 0
        rchk, rpend = self.render_check, None
        render = self.syms['render'] if patched else -1
        while True:
            pc, sp = R[24], R[12]
            if self.isr and pc == self.isr[-1][0] and sp == self.isr[-1][1]:
                f = self.isr.pop()
                if patched and not f[2] and not self.isr:
                    out.append(('empty', self.game))
            in_isr = bool(self.isr)
            if patched:
                now = model.now()
                if now >= self.next_int:
                    pend = self.next_int
                    self.next_int += FRAME
                    while self.next_int <= now:
                        self.next_int += FRAME
                        self.c['interrupt lost (clock)'] += 1
                if pend is not None:
                    if R[26] and self._accept(prev):
                        pend = None
                        continue
                    if model.now() - pend > 32:
                        self.c['interrupt lost (DI)'] += 1
                        pend = None
            elif ev and not in_isr and self.game >= ev[0][1]:
                if ev[0][0] == 'body':
                    if R[26] and self._accept(prev):
                        ev.pop(0)
                        continue
                    self.c['ISR body waits for EI'] += 1
                else:
                    if m[pc] == 0x76:
                        R[24] = (pc + 1) & 0xFFFF          # an interrupt that returns at once (h_isr, none owed)
                    ev.pop(0)
                    continue
            if patched and not in_isr:
                if self.ctx is None:
                    if pc < 0x4000:
                        self.ctx = sp
                elif pc >= 0x4000 and (self.ctx <= sp <= self.ctx + 2 or (pc, sp) in PF_EXITS):
                    self.ctx = None
            if pc == PASS_PC and n and not in_isr and self.ctx is None and sp == stop_sp:
                return out if patched else ev
            if patched:
                if pc == ISR_BODY:
                    if in_isr and not self.isr[-1][2]:          # h_isr's JP 0xFF25
                        self.isr[-1][2] = True
                        out.append(('body', self.game))
                    elif not in_isr and self.ctx is not None:   # waitpt's CALL 0xFF25 (an owed body in the wait)
                        out.append(('body', self.game))
                if pc in self.site_pcs and self.ctx is None:
                    self.hits[pc] += 1
                if pc == self.wr_m or pc == self.wr_u:
                    self._buf_write(pc == self.wr_m)
                elif pc == CLEAR_SITE:
                    self.xoff, self.uoff, self.xrec = bytearray(0x1000), bytearray(0x1000), True
                elif pc == render:
                    self.xrec = False                           # the render's own draws are not the pass's
                if pc == render and rchk and not in_isr:
                    rchk = False                                # the pass's first render: full weight
                    rpend = (m[sp] | m[sp + 1] << 8, sp + 2, m.bank(0)[:0x1000], m.page(STATE_PG)[S_BACK],
                             bytes(self.xoff), bytes(self.uoff))
                    R[0] = TICK
                elif rpend is not None and pc == rpend[0] and sp == rpend[1]:
                    img = self.l2_image(rpend[3])
                    bad, xor = render_diff(rpend[2], img, self.l2_image(BASE_BK), m.bank(0)[:0x1000], rpend[4],
                                           rpend[5])
                    self.renders.append((bad, bits_differ(bytes(len(img)), img), rpend[2], img, xor))
                    rpend = None
            main = not in_isr and self.ctx is None
            if self.trace and pc in self.trace:
                self.traced.append((pc, sp, self.game, self.ctx is not None, in_isr,
                                    [m[sp + i] | m[(sp + i + 1) & 0xFFFF] << 8 for i in (0, 2, 4, 6)]))
            if main and pc >= 0x4000 and pc not in skip and m[pc] != 0x76:
                self.game += 1
            prev = pc
            ops[m[pc]]()
            if pc in R_SITES and m[pc] == 0xED and m[(pc + 1) & 0xFFFF] == 0x5F:
                if main:
                    a = self.rseq[self.rk % len(self.rseq)]
                    self.rk += 1
                else:
                    a = 0x55
                R[0] = a
                R[1] = (R[1] & 1) | (a & 0xA8) | (0x40 if a == 0 else 0) | (4 if R[26] else 0)
            n += 1
            if n > limit:
                raise RuntimeError('pass does not end (PC %04X SP %04X, %s)' % (R[24], R[12], 'patched' if patched
                                                                               else 'original'))

    def l2_image(self, back):
        """Layer 2 bank `back` as a mono buffer image (0x1000 bytes, the buffer's layout: line k = Layer 2 y k + 8,
        bit set = not transparent), lines 0-119 and columns 1-30 only (what h_plot mirrors); 0 elsewhere."""
        img = bytearray(0x1000)
        for k in range(120):
            for col in range(1, 31):
                v = 0
                for i in range(8):
                    v = v << 1 | (self.mem.l2_pixel(back, col * 8 + i, k + 8) != TRANS)
                img[scr_off(k, col)] = v
        return bytes(img)


def render_diff(buf, img, base, mine, xoff, uoff):
    """-> (unexplained differing pixels, XOR overlaps). An XOR overlap: two figures that cancel in the one mono
    buffer but lie on different layers of Layer 2 - the buffer has the pixel clear, Layer 2 lit, the full-weight
    render's own mono buffer (mine: scenery and ships, no text) set, and the pass is seen taking that bit 1 -> 0:
    xoff - by a mirrored write (the text XORed onto a star / planet pixel: h_plot then makes the base pixel
    transparent and the render's star shows; Front View over a star, Docking), or uoff with the base lit - by a
    buffer-only write (a scenery / ship XOR onto a text pixel, which stays lit in the base). The layered design's
    limit, counted apart; any other difference is unexplained. Inside the frame only."""
    bad = xor = 0
    for k in range(1, 119):
        for col in range(1, 31):
            o = scr_off(k, col)
            v = buf[o] ^ img[o]
            if col == 1:
                v &= 0x7F
            elif col == 30:
                v &= 0xFE
            if v:
                ok = v & img[o] & ~buf[o] & mine[o] & (xoff[o] | uoff[o] & base[o])
                xor += bin(ok).count('1')
                bad += bin(v & ~ok).count('1')
    return bad, xor


def bits_differ(buf, img):
    """Set bits that differ between a mono buffer and an l2_image inside the view frame: lines 1-118, x 9-246 (the
    frame - lines 0 / 119, x 8 / 247 - is the ULA's: ulaclr keeps it, Layer 2 is transparent there)."""
    n = 0
    for k in range(1, 119):
        for col in range(1, 31):
            o = scr_off(k, col)
            v = buf[o] ^ img[o]
            if col == 1:
                v &= 0x7F
            elif col == 30:
                v &= 0xFE
            n += bin(v).count('1')
    return n


def _excluded(n, i, sp, hack_sp):
    if n == 0:
        return BUFFER[0] <= i < BUFFER[1] or ROW56_SAVE[0] <= i < ROW56_SAVE[1] or             (i >= STACK_SAVE and 0x4100 + i - STACK_SAVE < hack_sp)
    if n == 5:
        a = 0x4000 + i
        if i < 0x1800:
            y = scr_y(i)
            return 8 <= y <= 127 or a < 0x4020 or 0x4100 <= a < sp or AI_STACK[0] <= a < AI_STACK[1]
        return a == MIRF or a in LIGHT_WHITE
    return False


def compare(o, p, skip, limit=8):
    """-> [problem] between the original o and the patched p after a pass."""
    bad = [('register', i, o.R[i], p.R[i]) for i in CMP if o.R[i] != p.R[i]]
    sp = min(o.R[12], p.R[12])
    hack_sp = min(o.mem[HACK_SP] | o.mem[HACK_SP + 1] << 8, p.mem[HACK_SP] | p.mem[HACK_SP + 1] << 8)
    for n in range(8):
        x, y = o.mem.bank(n), p.mem.bank(n)
        if x == y:
            continue
        base = (0x4000, 0x8000, 0xC000)[{5: 0, 2: 1}.get(n, 2)] if n in (0, 2, 5) else None
        for i in range(16384):
            if x[i] != y[i] and not _excluded(n, i, sp, hack_sp) and not (base is not None and base + i in skip):
                bad.append(('RAM', n, '%04X' % ((base or 0) + i), x[i], y[i]))
                if len(bad) >= limit:
                    return bad
    if o.model.log != p.model.log:
        k = next((j for j, (a, b) in enumerate(zip(o.model.log, p.model.log)) if a != b),
                 min(len(o.model.log), len(p.model.log)))
        bad.append(('ports', len(o.model.log), len(p.model.log), 'first difference at %d' % k))
    if o.rk != p.rk:
        bad.append(('R reads', o.rk, p.rk))
    return bad


# ------------------------------------------------------------------------------------------------ cases

def run_case(patch, st, passes=PASSES, line=0, rseq=None, orseq=None, drop_body=False, neg_rom=None, check=True):
    """PASSES passes patched and original from st. -> (problems per pass, patched machine, original machine).
    Negative-control knobs: orseq (another R sequence for the original), drop_body (the original misses the pass's
    first ISR body), neg_rom (alt ROM bytes changed)."""
    p = Machine(st, patch, line, rseq, render_check=check, neg_rom=neg_rom)
    o = Machine(st, None, 0, orseq or rseq)
    skip = p.skip
    res = []
    for k in range(passes):
        o.model.log, p.model.log = [], []
        try:
            ev = p.run()
        except RuntimeError as e:               # the build never gets back to the main loop: a failure
            res.append(dict(bad=[('patched pass does not end', str(e))], events=[], bodies=0, lost=dict(p.c)))
            break
        if drop_body and k == 0:
            bodies = [i for i, e in enumerate(ev) if e[0] == 'body']
            if bodies:
                ev = ev[:bodies[0]] + ev[bodies[0] + 1:]
        try:
            left = o.run(ev, limit=max(3_000_000, 20 * p.game))
        except RuntimeError as e:               # the original went another way (a HALT waiting for an interrupt
            res.append(dict(bad=[('original pass does not end', str(e))], events=ev,    # the build never took)
                            bodies=sum(x[0] == 'body' for x in ev), lost=dict(p.c)))
            break
        bad = compare(o, p, skip)
        if left:
            bad.append(('ISR events not placed', len(left)))
        res.append(dict(bad=bad, events=ev, bodies=sum(e[0] == 'body' for e in ev), lost=dict(p.c)))
    return res, p, o


def capture(rzx_path, every=EVERY, stop=None):
    """States at PASS_PC outside the ISR, every `every`th pass of a recording."""
    from .simrun import play_rzx
    out = []

    class H(object):
        def __init__(s):
            s.ist, s.n = [], 0

        def on_sim(s, sim):
            s.sim = sim

        def on_desync(s, f, msg):
            raise RuntimeError('%s: replay desynchronised at frame %d (%s)' % (rzx_path, f, msg))

        def on_interrupt(s, sim, prev):
            s.ist.append((sim.registers[24], sim.registers[12]))

        def before(s, pc):
            R = s.sim.registers
            if s.ist and pc == s.ist[-1][0] and R[12] == s.ist[-1][1]:
                s.ist.pop()
            if pc == PASS_PC and not s.ist:
                s.n += 1
                if s.n % every == 0:
                    m = s.sim.memory
                    out.append({'regs': list(R), 'o7ffd': m.o7ffd, 'banks': [bytes(b) for b in m.banks], 'pass': s.n})
    play_rzx(rzx_path, H(), stop=stop)
    return out


def check_state(patch, st, k, c, examples, keep=5):
    res, p, o = run_case(patch, st, line=(k * 97) % 311)
    c['cases'] += 1
    for j, r in enumerate(res):
        c['passes'] += 1
        c['ISR bodies'] += r['bodies']
        if r['bad']:
            c['pass mismatch!'] += 1
            if len(examples.setdefault('pass', [])) < keep:
                examples['pass'].append((st.get('pass'), j, r['bad'][:6]))
        else:
            c['pass exact'] += 1
    for diff, lit, buf, back, xor in p.renders:
        c['render pixels'] += 118 * 238
        c['render XOR overlaps (layered)'] += xor
        if diff:
            c['render differs from buffer!'] += 1
            c['render pixels differing'] += diff
            if len(examples.setdefault('render', [])) < keep:
                examples['render'].append((st.get('pass'), diff, lit))
        else:
            c['render = buffer exact'] += 1
    for k2, v in p.c.items():
        c['patched ' + k2] += v
    c['R reads'] += o.rk
    return p


def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=EVERY):
    """run_case on every `every`th pass of the recording. -> (Counter, examples, states): `collect` states for the
    unit tests, spread over the flight cases (every pass rendered: the docked pages draw and clear nothing)."""
    states = capture(rzx_path, every, stop)
    c, examples = collections.Counter(), {}
    hits = collections.Counter()
    flight = []
    for k, st in enumerate(states):
        p = check_state(patch, st, k, c, examples)
        hits.update(p.hits)
        if len(p.renders) == PASSES:
            flight.append(st)
        if progress:
            progress('%s %d/%d %s' % (Path(rzx_path).name, k + 1, len(states),
                                      {x: c[x] for x in ('pass exact', 'pass mismatch!', 'render = buffer exact',
                                                         'render differs from buffer!') if c[x]}))
    if not states:
        c['no states (recording too short)!'] += 1
    c['hook sites reached'] = len(hits)
    patch.site_hits = getattr(patch, 'site_hits', collections.Counter()) + hits
    return c, examples, flight[::max(1, len(flight) // collect)][:collect] if collect else []


# ------------------------------------------------------------------------------------------------ unit tests

def negative_rom(patch):
    """The broken build the negative control runs: h_clear's LD BC,30 (the original's count, restored before JP
    0x8084) made 31 - one byte more cleared."""
    code = patch.rom_code
    i = code.find(bytes.fromhex('011e00c38480'))
    if i < 0:
        raise ValueError('h_clear tail not found (asm changed)')
    return {E.ROM_ORG + i + 1: 0x1F}


def unit_tests(patch, states, neg=True):
    """Recolour (empty map = the build; one key changes only its byte), hook coverage, and the negative controls:
    a broken h_clear, another R sequence for the original, a missed ISR body - each must fail the pass compare -
    and a render compared with the wrong pass's buffer must differ."""
    from . import elite_colours as EC
    c = collections.Counter()
    syms, code = patch.syms, bytes.fromhex(patch.prof['hooks']['rom'])
    img, _ = E._coloured_rom(code, syms, {})
    c['recolour empty map = build ' + ('exact' if img == code else 'differs!')] += 1
    key = EC.ship_key(EC.BLUEPRINTS[0])
    img2, _ = E._coloured_rom(code, syms, {key: (0, 0, (2,))})
    changed = [i for i in range(len(code)) if img2[i] != code[i]]
    want = [a - E.ROM_ORG for a in EC.sites(syms)[key]]
    c['recolour one key ' + ('exact' if changed == want and img2[want[0]] == EC.PAL8[1] else 'differs!')] += 1
    hit = getattr(patch, 'site_hits', {})
    hooks = [a for a, _, _, _ in E.HOOK_SITES]
    c['hook sites never reached'] = sum(1 for a in hooks if not hit.get(a))
    patch.unreached = ['%04X' % a for a in hooks if not hit.get(a)]
    if not (neg and states):
        return c
    caught = None
    for cand in states[len(states) // 2:] + states[:len(states) // 2]:
        res, p, o = run_case(patch, cand, passes=1, neg_rom=negative_rom(patch) if neg is True else neg, check=False)
        if p.hits[CLEAR_SITE]:                  # a pass that clears the buffer
            caught = bool(res[0]['bad'])
            break
    c['negative h_clear ' + ('no state clears!' if caught is None else 'caught' if caught else 'missed!')] += 1
    # R (0x7992 / 0x799B): bits 0-1 are a +-1 jitter the star routine adds to its table (0x7A39) each pass. The
    # original given the other value of both bits must leave the compare (a flight pass: one that reads R).
    alt = [((37 * k + 11) ^ 3) & 0xFF for k in range(97)]
    caught = None
    for cand in states:
        res, p, o = run_case(patch, cand, passes=1, orseq=alt, check=False)
        if o.rk:
            caught = bool(res[0]['bad'])
            break
    c['negative R sequence ' + ('no state reads R!' if caught is None else 'caught' if caught else 'missed!')] += 1
    # ISR pattern: the bodies decay the controls (0xFF08 / 0xFF0A) only in some states (no keys in the replay):
    # dropping half of a pass's bodies must be caught in at least one state.
    caught = False
    for cand in states:
        res, p, o = run_case(patch, cand, passes=1, check=False)
        ev = res[0]['events']
        bodies = [i for i, e in enumerate(ev) if e[0] == 'body']
        if res[0]['bad'] or len(bodies) < 2:
            continue
        o2 = Machine(cand, None)
        try:
            o2.run([e for i, e in enumerate(ev) if i not in bodies[:len(bodies) // 2]], limit=max(3_000_000, 20 * p.game))
            caught = bool(compare(o2, p, p.skip, limit=1))
        except RuntimeError:
            caught = True
        if caught:
            break
    c['negative ISR pattern ' + ('caught' if caught else 'missed!')] += 1
    for cand in states:
        res, p, o = run_case(patch, cand, passes=2, check=True)
        if len(p.renders) == 2 and not any(r['bad'] for r in res):
            (_, _, buf0, _, _), (_, _, buf1, img1, _) = p.renders
            if buf0 != buf1:
                c['negative render (wrong pass) ' + ('caught' if bits_differ(buf0, img1) else 'missed!')] += 1
                break
    else:
        c['negative render: no state with two different passes!'] += 1
    return c
