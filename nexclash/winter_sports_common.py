"""Winter Sports: what every event plugin shares (assembler, Next register writes, the 16 colours, the pace wrapper). GPL-3.0-or-later.
Facts and the plugin contract: games/winter_sports.md "Event plugins".

An event plugin is a module nexclash/winter_sports_<event>.py with
    INDEX                      the event's number (0 Downhill/Slalom/Giant Slalom, 1 Ice Hockey, 2 Ski Jumping, 3 Speed Skating, 4 Bobsled, 5 Biathlon)
    BANKS                      the 16K banks it uses beyond the tape's (winter_sports.BANK_PLAN says which are yours)
    patch_event(block, enhanced=False, original_pace=False) -> (patched block, {bank: bytes})
                               block = the event's 32,824 tape bytes (loaded at 0x7500); every patched site is checked against its original bytes
    disable_code()             NextReg writes (a list of bytes) that put the display back before ANY event loads (the menu's loader hook runs them)
    verify(patch, z80, ...), unit_tests(patch, z80, ...)   differential test against the original and hook tests with negative controls
and a line in winter_sports.PLUGINS. The defaults of a build are: the ORIGINAL 16 colours only (per-pixel is fine), smoother but similar gameplay
(even update cadence at the original's mean rate, the heavy drawing at 28 MHz inside the vertical blank), the poles / figures as the game draws them;
`enhanced` = the colour set a player can switch on (extended colours); `original_pace` = the toggle that gives the original's free-running pace back.
"""

# The 16 Spectrum colours as Next RRRGGGBB bytes (the toolkit's SPECCY: jetpac.SPECCY; normal 0-7, bright 8-15). 0xE3 (bright magenta) is the global
# transparent colour: a Layer 2 / ULA pixel of that value is see-through, so a build that needs bright magenta must move NextReg 0x14.
SPECCY = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE3, 0x1C, 0x1F, 0xFC, 0xFF]
BLACK, BLUE, RED, MAGENTA, GREEN, CYAN, YELLOW, WHITE = range(8)
TRANSPARENT = 0xE3

# The player's CPU speed (F8) across a wrapper's 28 MHz drawing (Codex review C6). A wrapper calls SPD_IN before its
# halt (the wait absorbs it) with an offset byte after the CALL: SPD_IN reads NR 7 and writes it into the operand of
# that wrapper's own exit NEXTREG 7,n (wrappers sit in RAM) and into SPD, keeping every register and flag. After the
# halt a wrapper runs exactly as before (NEXTREG 7,3 / CALL / NEXTREG 7,n): a latch on the timed path shifted Speed
# Skating's frame-edge pacing by 3 %. SPD_OUT (the events' display-off code, at an event load) puts SPD back. Both live
# in the loader hook's own block (winter_sports.HOOK .. 0x6EFF, untouched by the menu and every event), SPD among the
# hook's 8 variable bytes at 0x6D00 (set to 0 when the hook goes in).
SPD = 0x6D04
SPD_IN = 0x6E80
SPD_OUT = SPD_IN + 32


def speed_code():
    """SPD_IN and SPD_OUT, assembled at SPD_IN (ADD HL,A is Z80N)."""
    code = bytes([0xE3, 0xF5, 0xC5, 0xE5,                    # ex (sp),hl: HL -> the offset byte; push af / bc / hl
                  0x7E, 0xED, 0x31,                          # ld a,(hl) / add hl,a: HL -> the exit NEXTREG's operand
                  0x01, 0x3B, 0x24, 0x3E, 0x07, 0xED, 0x79, 0x04, 0xED, 0x78, 0xE6, 0x03,   # A = NR 7 & 3
                  0x77, 0x32, SPD & 255, SPD >> 8,           # ld (hl),a / ld (SPD),a
                  0xE1, 0x23, 0xC1, 0xF1, 0xE3, 0xC9])       # pop hl / inc hl (past the byte) / pop bc / af / ex / ret
    out = bytes([0xF5, 0x3A, SPD & 255, SPD >> 8, 0xED, 0x92, 0x07, 0xF1, 0xC9])     # push af; NR 7 = SPD; pop af
    assert len(code) <= SPD_OUT - SPD_IN
    return code.ljust(SPD_OUT - SPD_IN, b'\0') + out


def _speed_latch(a):
    """CALL SPD_IN and its offset byte; -> the byte's index in a.code (set by _speed_exit)."""
    a.e(0xCD, a.w(SPD_IN), 0x00)
    return len(a.code) - 1


def _speed_exit(a, at):
    """NEXTREG 7,n whose n SPD_IN sets to the player's speed; points the offset byte at `at` to it."""
    a.code[at] = len(a.code) + 3 - at
    a.nr(0x07, 0x00)


class Asm:
    """A tiny assembler for hook code: emit bytes, labels, relative jumps checked, absolute jumps/calls by label. `org` is where the code will sit."""

    def __init__(self, org):
        self.org, self.code, self.lab, self.fix = org, bytearray(), {}, []

    @property
    def pc(self):
        return self.org + len(self.code)

    def L(self, name):
        assert name not in self.lab, name
        self.lab[name] = self.pc

    def e(self, *b):
        for x in b:
            if isinstance(x, (list, tuple, bytes, bytearray)):
                self.code.extend(x)
            else:
                assert 0 <= x < 256, x
                self.code.append(x)

    def w(self, v):
        return [v & 255, (v >> 8) & 255]

    def jr(self, op, name):                       # op: 0x18 jr, 0x20 jr nz, 0x28 jr z, 0x30 jr nc, 0x38 jr c, 0x10 djnz
        self.e(op, 0)
        self.fix.append(('r', len(self.code) - 1, name))

    def jp(self, op, name):                       # op: 0xC3 jp, 0xCD call, 0xCA jp z, 0xC2 jp nz, ...
        self.e(op, 0, 0)
        self.fix.append(('a', len(self.code) - 2, name))

    def nr(self, reg, val):
        self.e(0xED, 0x91, reg, val)              # NEXTREG reg,val

    def nr_a(self, reg):
        self.e(0xED, 0x92, reg)                   # NEXTREG reg,A

    def done(self):
        for kind, pos, name in self.fix:
            t = self.lab[name]
            if kind == 'r':
                d = t - (self.org + pos + 1)
                assert -128 <= d <= 127, (name, d)
                self.code[pos] = d & 255
            else:
                self.code[pos], self.code[pos + 1] = t & 255, t >> 8
        return bytes(self.code)


class Block:
    """A patchable event block (the tape's 32,824 bytes, loaded at 0x7500): reads and writes by runtime address, with the original bytes checked."""
    BASE = 0x7500

    def __init__(self, data):
        self.b = bytearray(data)

    def at(self, a, n):
        return bytes(self.b[a - self.BASE:a - self.BASE + n])

    def expect(self, a, orig, what):
        orig = bytes.fromhex(orig) if isinstance(orig, str) else orig
        if self.at(a, len(orig)) != orig:
            raise ValueError('%s: bytes at 0x%04X are %s, not %s' % (what, a, self.at(a, len(orig)).hex(), orig.hex()))

    def free(self, a, n, what):
        if any(self.at(a, n)):
            raise ValueError('%s: 0x%04X-0x%04X is not free in this event block' % (what, a, a + n - 1))

    def put(self, a, d):
        self.b[a - self.BASE:a - self.BASE + len(d)] = d

    def bytes(self):
        return bytes(self.b)


# ---------------------------------------------------------------- the pace wrapper (smoother, similar gameplay)
CADENCE = (2,)                                # frames per update: 25 updates a second. Downhill's original runs 2.24 frames per update on average over a run (581
#                                               updates), the cadence builds 2.31 (the game's blocking beeps, with interrupts off, still add their own time): 3 % slower, evenly


def pace_wrapper(a, call_target, mode_addr, idx_addr, cadence=CADENCE):
    """Emit, at a.pc, a routine that replaces `CALL call_target` (the event's per-update drawing call): unless the mode byte is non-zero
    (the 'original pace' toggle) it halts for the cadence's next number of frames (interrupts on: the halt ends on the frame interrupt), runs the call
    at 28 MHz (NextReg 0x07 = 3) and puts the player's speed back (SPD_IN / SPD_OUT). The drawing therefore starts at the top of a frame, inside the vertical blank,
    and updates come at an even cadence. Returns its start address."""
    start = a.pc
    a.e(0x3A, a.w(mode_addr))                     # ld a,(mode)
    a.e(0xB7)
    a.jr(0x20, '_orig')                           # jr nz,orig
    k = _speed_latch(a)                           # the player's speed -> this wrapper's exit (before the halt)
    a.e(0xFB)                                     # ei
    a.e(0x3A, a.w(idx_addr), 0x3C)                # ld a,(idx) / inc a
    a.e(0xFE, len(cadence))                       # cp n
    a.jr(0x38, '_ok')
    a.e(0xAF)                                     # xor a
    a.L('_ok')
    a.e(0x32, a.w(idx_addr))                      # ld (idx),a
    # b = frames: the cadence table is a run of `cp k / jr nz` tests, small and checked
    a.e(0x06, cadence[0])                         # ld b,base
    extra = [(i, n) for i, n in enumerate(cadence) if n != cadence[0]]
    for i, n in extra:
        a.e(0xFE, i)                              # cp i
        a.jr(0x20, '_c%d' % i)
        a.e(0x06, n)                              # ld b,n
        a.L('_c%d' % i)
    a.L('_h')
    a.e(0x76)                                     # halt
    a.jr(0x10, '_h')                              # djnz
    a.nr(0x07, 0x03)                              # 28 MHz
    a.e(0xCD, a.w(call_target))                   # call the drawing
    _speed_exit(a, k)                             # NEXTREG 7,<the player's speed> (never a fixed 3.5 MHz)
    a.e(0xC9)
    a.L('_orig')
    a.e(0xC3, a.w(call_target))                   # jp call_target (it returns to our caller)
    return start


def draw_wrapper(a, call_target, mode_addr, di_site=False, halts=1):
    """Emit, at a.pc, the wrapper that replaces a drawing call whose event does NOT pace itself by frames (its own delay loops set its speed; Bobsled):
    unless the mode byte is non-zero (the 'original pace' toggle) it halts to the frame interrupt (the drawing then starts at the top of a frame, inside
    the vertical blank: no tearing), runs the call at 28 MHz (NextReg 0x07 = 3) and puts the player's speed back (SPD_IN / SPD_OUT). The halt costs on average half a frame, the 28 MHz
    drawing saves about as much, so the game's pace stays within a few percent of the original's (no padding).
    di_site: the site is `DI / CALL target / EI` (5 bytes, replaced by `CALL wrapper / NOP / NOP`): the wrapper switches interrupts on for the halt,
    off for the call and on after it, as the original sequence ends. Otherwise the halt is skipped when interrupts are off (LD A,I; P/V = IFF2)."""
    start = a.pc
    a.e(0xF5, 0xC5)                               # push af / push bc  (the call's inputs)
    a.e(0x3A, a.w(mode_addr), 0xB7)               # ld a,(mode) / or a
    a.jr(0x20, '_op')
    k = _speed_latch(a)                           # the player's speed -> this wrapper's exit (before the halt)
    if halts:
        if di_site:
            a.e(0xFB)                             # ei
        else:
            a.e(0xED, 0x57)                       # ld a,i  (P/V = IFF2)
            a.jp(0xE2, '_nohalt')                 # jp po,nohalt
        a.e(0x06, halts)                          # ld b,halts
        a.L('_h')
        a.e(0x76)                                 # halt
        a.jr(0x10, '_h')                          # djnz
    a.L('_nohalt')
    if di_site:
        a.e(0xF3)                                 # di
    a.e(0xC1, 0xF1)                               # pop bc / pop af
    a.nr(0x07, 0x03)                              # 28 MHz
    a.e(0xCD, a.w(call_target))                   # call the drawing
    _speed_exit(a, k)                             # NEXTREG 7,<the player's speed> (never a fixed 3.5 MHz)
    if di_site:
        a.e(0xFB)                                 # ei
    a.e(0xC9)
    a.L('_op')
    a.e(0xC1, 0xF1)                               # pop bc / pop af
    if di_site:
        a.e(0xF3)                                 # di
        a.e(0xCD, a.w(call_target))
        a.e(0xFB, 0xC9)                           # ei / ret
    else:
        a.e(0xC3, a.w(call_target))               # jp target (returns to the caller)
    return start
