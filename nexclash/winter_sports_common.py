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
    at 28 MHz (NextReg 0x07 = 3) and puts 3.5 MHz back. The drawing therefore starts at the top of a frame, inside the vertical blank,
    and updates come at an even cadence. Returns its start address."""
    start = a.pc
    a.e(0x3A, a.w(mode_addr))                     # ld a,(mode)
    a.e(0xB7)
    a.jr(0x20, '_orig')                           # jr nz,orig
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
    a.jp(0xCD, '_call')                           # call the drawing
    a.nr(0x07, 0x00)                              # 3.5 MHz
    a.e(0xC9)
    a.L('_orig')
    a.e(0xC3, a.w(call_target))                   # jp call_target (it returns to our caller)
    a.L('_call')
    a.e(0xC3, a.w(call_target))                   # jp call_target (reached by the call above: returns to it)
    return start
