"""Z80N (ZX Spectrum Next) instructions for SkoolKit's Python Simulator - the shared handlers.

SkoolKit runs every Z80N opcode as a silent 2-byte NOP (BRIEFING 2.3). `install(sim, nextreg)`
puts a handler for each of them into sim.after_ED, so an engine no longer copies its own
(cyclone._machine, smashtv, verify, ...). Call it after `simpool.machine()` (simpool restores the
tables on every reuse) and after `sim.set_tracer()` is fine too: port I/O goes through the tracer
the simulator has when the instruction runs.

Sources (cite them when a handler changes; authority order as BRIEFING "Sources": hardware test >
core VHDL > dev guide > wiki / MAME):
  [VHDL]  ZX Spectrum Next FPGA core, gitlab.com/SpectrumNext/ZX_Spectrum_Next_FPGA, branch 30205
          (core 3.02.05), commit 15e206dd (2026-09-25), cores/zxnext/src/cpu/t80n/:
          t80n_mcode.vhd = decode, M-cycles, T-states, memory/IO steps;
          t80n.vhd = the Z80N_command execution (MUL_DE, ADD_HL_A, PIXELAD, ...) and the flags.
          The default build instantiates t80n/; t80n-complete/ (memptr + XY flag fixes, optional
          build, "not currently activated" - changelog 3.02.04) has the same Z80N code.
  [GUIDE] ZX Spectrum Next dev guide r3, 4.15 "ZX Spectrum Next Extended" (opcode, flags, T) and
          chapter 5 (one page per instruction); text copy in specnext docs/reference.
  [MAME]  mamedev/mame src/devices/cpu/z80/z80.lst, section "Z80N" (commit df241e3a,
          2026-10-22) - cross-check only.
  Encodings checked with the pinned sjasmplus 1.24.0 --zxnext (2026-10-21).
  Hardware check: tools/hwtests/z80ntest (every handler's result + T-states on a board).

Where the sources disagree the handler follows the VHDL (3.02.05):
  - LDIX / LDIRX / LDDX / LDDRX / LDPIRX flags: VHDL sets them like LDI (I_BT: H = N = 0,
    PV = BC != 0, bits 5/3 from A + byte; S Z C kept); guide and MAME: unchanged; wiki: like LDI
    on core 3.02 (GUIDE_R3_REVIEW). Repeats: t80n sets the LDI flags every step (no PC-based
    X/Y, unlike SkoolKit's LDIR). LDPIRX: t80n_mcode leaves the ALU's A input unassigned in M2,
    so bits 5/3 are a guess (A + byte, as LDI).
  - LDWS T-states: 14 (VHDL: ED 4 + M1 4 + M2 3 + M3 3; MAME the same; board); guide table: 16.
  - LDWS flags: the VHDL's "INC D" step is ALU op 0000 = ADD D,1, so CF = (D was $FF), not kept
    (board 2026-10-21: D = $7F, F = $FF -> $94; D = $FF, F = 0 -> $51); guide "like INC D",
    MAME inc(D).
  - ADD rr,A carry: guide "undefined"; t80n.vhd writes CF from bit 16 of a 16-bit sum, i.e. 0
    (reg_temp_t is cleared at T3 and never sets bit 16); MAME: unchanged. Handler: CF = 0.
  - OUTINB flags: guide "destroyed"; VHDL skips the B decrement, the only flag write on the OUTI
    path, so unchanged; MAME unchanged. Handler: unchanged.
  - JP (C) flags: guide "destroyed"; VHDL / MAME: unchanged. Handler: unchanged.
  - NEXTREG n,A T-states: 17 (VHDL 4 M-cycles after ED, guide); MAME's list gives 14.
  Hooks must not read a flag the guide calls undefined, whatever the handler leaves there.

Board results (tools/hwtests/z80ntest v1, a Next on core 3.02.00, 2026-10-21): every handler and
every T-state above confirmed - LDIX family flags like LDI, ADD rr,A CF = 0, OUTINB flags kept,
JP (C) from the next address, LDWS 14 T, NEXTREG 20 / 17 T - except LDWS's CF (fixed above) and
LDPIRX: memory written and flag bit 3 differ on 3.02.00. Core changelog 3.02.02: "LDPIRX
instruction works properly at all cpu speeds" - the handler models the fixed core. LDPIRX in a
hook needs core 3.02.02+ (set the .nex header's core version) until a newer board run says more.

Not modelled, as for every SkoolKit instruction: contention, 28 MHz wait states (BRIEFING A1).
Memory writes skip 0x0000-0x3FFF, the same ROM guard as every SkoolKit write.
ED B6 is in the core's decoder as "LDIRSCALE" with its scaling part commented out (unfinished,
undocumented): it always raises Z80NError.
"""
from skoolkit.simulator import R2
from skoolkit.simtables import ADD, AND

A, F, B, C, D, E, H, L, SP, PC, T = 0, 1, 2, 3, 4, 5, 6, 7, 12, 24, 25

# ED xx -> (mnemonic, bytes, T-states); T for repeats: 21 per repeated step, 16 for the last
OPCODES = {
    0x23: ('SWAPNIB', 2, 8),
    0x24: ('MIRROR A', 2, 8),
    0x27: ('TEST n', 3, 11),
    0x28: ('BSLA DE,B', 2, 8),
    0x29: ('BSRA DE,B', 2, 8),
    0x2A: ('BSRL DE,B', 2, 8),
    0x2B: ('BSRF DE,B', 2, 8),
    0x2C: ('BRLC DE,B', 2, 8),
    0x30: ('MUL D,E', 2, 8),
    0x31: ('ADD HL,A', 2, 8),
    0x32: ('ADD DE,A', 2, 8),
    0x33: ('ADD BC,A', 2, 8),
    0x34: ('ADD HL,nn', 4, 16),
    0x35: ('ADD DE,nn', 4, 16),
    0x36: ('ADD BC,nn', 4, 16),
    0x8A: ('PUSH nn', 4, 23),
    0x90: ('OUTINB', 2, 16),
    0x91: ('NEXTREG n,n', 4, 20),
    0x92: ('NEXTREG n,A', 3, 17),
    0x93: ('PIXELDN', 2, 8),
    0x94: ('PIXELAD', 2, 8),
    0x95: ('SETAE', 2, 8),
    0x98: ('JP (C)', 2, 13),
    0xA4: ('LDIX', 2, 16),
    0xA5: ('LDWS', 2, 14),
    0xAC: ('LDDX', 2, 16),
    0xB4: ('LDIRX', 2, 21),
    0xB7: ('LDPIRX', 2, 21),
    0xBC: ('LDDRX', 2, 21),
}

# ED opcodes that are a 2-byte NOP on a Z80 and on the Next (all but the Z80 set and OPCODES)
_Z80_ED = set(range(0x40, 0x80)) - {0x77, 0x7F} | {0xA0, 0xA1, 0xA2, 0xA3, 0xA8, 0xA9, 0xAA, 0xAB,
                                                  0xB0, 0xB1, 0xB2, 0xB3, 0xB8, 0xB9, 0xBA, 0xBB}
NOPS = sorted(set(range(256)) - _Z80_ED - set(OPCODES))

MIRROR = tuple(int('{:08b}'.format(v)[::-1], 2) for v in range(256))


class Z80NError(Exception):
    pass


def install(sim, nextreg=None, strict=True):
    """Every Z80N instruction into sim.after_ED.
    nextreg(reg, value): the engine's NextReg model, called by NEXTREG n,n / n,A; None -> NEXTREG
    raises Z80NError (a simulator that should never see one).
    strict: the other ED NOPs raise Z80NError too (a mistyped or unknown opcode in a hook fails
    instead of running as a 2-byte NOP); pass False for a simulator whose game code may run one."""
    R, mem, ed = sim.registers, sim.memory, sim.after_ED

    def done(size, t):
        R[15] = R2[R[15]]; R[25] += t; R[PC] = (R[PC] + size) % 65536

    def arg(n):
        return mem[(R[PC] + n) % 65536]

    def swapnib():
        R[A] = (R[A] << 4 | R[A] >> 4) & 255
        done(2, 8)

    def mirror():
        R[A] = MIRROR[R[A]]
        done(2, 8)

    def test():
        R[F] = AND[R[A]][arg(2)][1]                 # AND n's flags, A kept (VHDL ALU op = IR 5..3)
        done(3, 11)

    def shift(op):
        def f():
            de, s = R[D] << 8 | R[E], R[B] & 31     # VHDL: B(4 downto 0)
            if op == 0x28:
                de <<= s
            elif op == 0x29:
                de = (de - (de & 0x8000) * 2) >> s  # sign fill
            elif op == 0x2A:
                de >>= s
            elif op == 0x2B:
                de = (de - 0x10000) >> s            # 1 fill
            else:
                s &= 15                             # a 16-bit rotate repeats every 16
                de = de << s | de >> (16 - s)
            R[D], R[E] = de >> 8 & 255, de & 255
            done(2, 8)
        return f

    def mul():
        v = R[D] * R[E]
        R[D], R[E] = v >> 8, v & 255
        done(2, 8)

    def add_a(rh):
        def f():
            v = (R[rh] << 8 | R[rh + 1]) + R[A]
            R[rh], R[rh + 1] = v >> 8 & 255, v & 255
            R[F] &= 0xFE                            # CF = 0 (VHDL; guide: undefined)
            done(2, 8)
        return f

    def add_nn(rh):
        def f():
            v = (R[rh] << 8 | R[rh + 1]) + (arg(3) << 8 | arg(2))
            R[rh], R[rh + 1] = v >> 8 & 255, v & 255
            done(4, 16)
        return f

    def push_nn():
        hi, lo = arg(2), arg(3)                     # big-endian operand (guide note 1, MAME)
        sp = (R[SP] - 1) % 65536
        if sp > 0x3FFF:
            mem[sp] = hi
        sp = (sp - 1) % 65536
        if sp > 0x3FFF:
            mem[sp] = lo
        R[SP] = sp
        done(4, 23)

    def outinb():
        hl = R[H] << 8 | R[L]
        if sim.out_tracer:
            sim.out_tracer(R, R[B] << 8 | R[C], mem[hl], 17)   # as SkoolKit's OUTI
        hl = (hl + 1) % 65536
        R[H], R[L] = hl >> 8, hl & 255
        done(2, 16)

    def nextreg_nn():
        if nextreg is None:
            raise Z80NError('NEXTREG at %04X: no nextreg model installed' % R[PC])
        nextreg(arg(2), arg(3))
        done(4, 20)

    def nextreg_na():
        if nextreg is None:
            raise Z80NError('NEXTREG at %04X: no nextreg model installed' % R[PC])
        nextreg(arg(2), R[A])
        done(3, 17)

    def pixeldn():
        hl = R[H] << 8 | R[L]
        if hl & 0x0700 != 0x0700:
            hl += 0x100
        elif hl & 0xE0 != 0xE0:
            hl = (hl & 0xF8FF) + 0x20
        else:
            hl = (hl & 0xF81F) + 0x800
        R[H], R[L] = hl >> 8 & 255, hl & 255
        done(2, 8)

    def pixelad():
        d = R[D]
        R[H] = 0x40 | (d & 0xC0) >> 3 | d & 0x07
        R[L] = (d & 0x38) << 2 | R[E] >> 3
        done(2, 8)

    def setae():
        R[A] = 0x80 >> (R[E] & 7)
        done(2, 8)

    def jp_c():
        v = sim.in_r_c_tracer(R, R[B] << 8 | R[C]) if sim.in_r_c_tracer else 255
        R[15] = R2[R[15]]; R[25] += 13
        R[PC] = ((R[PC] + 2) & 0xC000) | v << 6     # top bits of the address after JP (C)

    def block(hl_step, repeat, pattern=False):
        def f():
            hl, de, bc, a = R[H] << 8 | R[L], R[D] << 8 | R[E], (R[B] << 8 | R[C]) - 1, R[A]
            v = mem[hl & 0xFFF8 | R[E] & 7] if pattern else mem[hl]
            if v != a and de > 0x3FFF:
                mem[de] = v
            hl = (hl + hl_step) % 65536
            de = (de + 1) % 65536                   # DE counts up for LDDX / LDDRX too
            bc %= 65536
            R[H], R[L], R[D], R[E], R[B], R[C] = hl >> 8, hl & 255, de >> 8, de & 255, bc >> 8, bc & 255
            n = a + v
            R[F] = (R[F] & 0xC1) | (n & 0x02) << 4 | n & 0x08 | (0x04 if bc else 0)
            R[15] = R2[R[15]]
            if repeat and bc:
                R[25] += 21                         # PC stays: the next run does the next byte
            else:
                R[25] += 16; R[PC] = (R[PC] + 2) % 65536
        return f

    def ldws():
        hl, de = R[H] << 8 | R[L], R[D] << 8 | R[E]
        if de > 0x3FFF:
            mem[de] = mem[hl]
        R[L] = (R[L] + 1) & 255
        R[D], R[F] = ADD[R[D]][1]                   # flags of ADD D,1: CF = (D was $FF)
        done(2, 14)

    def bad(op, why):
        def f():
            raise Z80NError('ED %02X at %04X: %s' % (op, R[PC], why))
        return f

    for op, fn in ((0x23, swapnib), (0x24, mirror), (0x27, test), (0x30, mul),
                   (0x31, add_a(H)), (0x32, add_a(D)), (0x33, add_a(B)),
                   (0x34, add_nn(H)), (0x35, add_nn(D)), (0x36, add_nn(B)),
                   (0x8A, push_nn), (0x90, outinb), (0x91, nextreg_nn), (0x92, nextreg_na),
                   (0x93, pixeldn), (0x94, pixelad), (0x95, setae), (0x98, jp_c),
                   (0xA4, block(1, False)), (0xA5, ldws), (0xAC, block(-1, False)),
                   (0xB4, block(1, True)), (0xB7, block(0, True, True)), (0xBC, block(-1, True))):
        ed[op] = fn
    for op in range(0x28, 0x2D):
        ed[op] = shift(op)
    if strict:
        for op in NOPS:
            ed[op] = bad(op, 'not a Z80N instruction (a NOP on the Next; install(strict=False) allows it)')
    ed[0xB6] = bad(0xB6, 'LDIRSCALE: unfinished in core 3.02.05 (t80n_mcode.vhd), never use')
    return sim


def selfcheck():
    """Each instruction against hand-worked results from the guide r3 pages -> list of failures."""
    from skoolkit.simulator import Simulator

    class Tr:
        def __init__(s):
            s.out = []

        def read_port(s, regs, port):
            return 0x05

        def write_port(s, regs, port, value, *x):
            s.out.append((port, value))

    def run(code, regs, mem=None, org=0x8000, nr=None, strict=True, steps=1):
        m = [0] * 65536
        m[org:org + len(code)] = code
        for a, v in (mem or {}).items():
            m[a] = v
        sim = Simulator(m, {})
        r = sim.registers
        r[PC], r[SP] = org, 0xFF00
        for k, v in regs.items():
            r[k] = v
        tr = Tr()
        sim.set_tracer(tr)
        install(sim, nr, strict)
        for _ in range(steps):
            sim.opcodes[m[r[PC]]]()
        return r, m, tr

    out, nrs = [], []

    def chk(name, got, want):
        if got != want:
            out.append('%s: %r != %r' % (name, got, want))

    r, m, _ = run([0xED, 0x23], {A: 0x5A})
    chk('SWAPNIB', (r[A], r[PC], r[T]), (0xA5, 0x8002, 8))
    r, m, _ = run([0xED, 0x24], {A: 0x01})
    chk('MIRROR A', r[A], 0x80)
    r, m, _ = run([0xED, 0x27, 0x0F], {A: 0xF0, F: 0x01})
    chk('TEST n', (r[A], r[F] & 0xD7, r[PC], r[T]), (0xF0, 0x54, 0x8003, 11))   # Z, H, P; C reset
    r, m, _ = run([0xED, 0x28], {D: 0x00, E: 0x81, B: 0x22})                   # B & 31 = 2
    chk('BSLA', (r[D], r[E]), (0x02, 0x04))
    r, m, _ = run([0xED, 0x29], {D: 0x80, E: 0x00, B: 4})
    chk('BSRA', (r[D], r[E]), (0xF8, 0x00))
    r, m, _ = run([0xED, 0x2A], {D: 0x80, E: 0x00, B: 4})
    chk('BSRL', (r[D], r[E]), (0x08, 0x00))
    r, m, _ = run([0xED, 0x2B], {D: 0x00, E: 0x10, B: 4})
    chk('BSRF', (r[D], r[E]), (0xF0, 0x01))
    r, m, _ = run([0xED, 0x2B], {D: 0x12, E: 0x34, B: 20})                      # past 16: all 1s
    chk('BSRF 20', (r[D], r[E]), (0xFF, 0xFF))
    r, m, _ = run([0xED, 0x2C], {D: 0x80, E: 0x01, B: 0x11})                   # B & 15 = 1
    chk('BRLC', (r[D], r[E]), (0x00, 0x03))
    r, m, _ = run([0xED, 0x30], {D: 0xFF, E: 0xFF})
    chk('MUL', (r[D], r[E], r[T]), (0xFE, 0x01, 8))
    r, m, _ = run([0xED, 0x31], {H: 0x12, L: 0xF0, A: 0x20, F: 0xFF})
    chk('ADD HL,A', (r[H], r[L], r[F]), (0x13, 0x10, 0xFE))
    r, m, _ = run([0xED, 0x32], {D: 0xFF, E: 0xFF, A: 0x01})
    chk('ADD DE,A', (r[D], r[E]), (0x00, 0x00))
    r, m, _ = run([0xED, 0x33], {B: 0x01, C: 0x02, A: 0x03})
    chk('ADD BC,A', (r[B], r[C]), (0x01, 0x05))
    r, m, _ = run([0xED, 0x34, 0x34, 0x12], {H: 0x01, L: 0x01, F: 0x55})
    chk('ADD HL,nn', (r[H], r[L], r[F], r[PC], r[T]), (0x13, 0x35, 0x55, 0x8004, 16))
    r, m, _ = run([0xED, 0x8A, 0x12, 0x34], {})
    chk('PUSH nn', (r[SP], m[0xFEFE], m[0xFEFF], r[PC], r[T]), (0xFEFE, 0x34, 0x12, 0x8004, 23))
    r, m, tr = run([0xED, 0x90], {B: 0x12, C: 0x3B, H: 0x90, L: 0x00, F: 0x42}, {0x9000: 0x77})
    chk('OUTINB', (tr.out, r[B], r[H], r[L], r[F], r[T]), ([(0x123B, 0x77)], 0x12, 0x90, 0x01, 0x42, 16))
    r, m, _ = run([0xED, 0x91, 0x07, 0x03], {}, nr=lambda reg, v: nrs.append((reg, v)))
    chk('NEXTREG n,n', (nrs[-1:], r[PC], r[T]), ([(0x07, 0x03)], 0x8004, 20))
    r, m, _ = run([0xED, 0x92, 0x56], {A: 0x0A}, nr=lambda reg, v: nrs.append((reg, v)))
    chk('NEXTREG n,A', (nrs[-1:], r[PC], r[T]), ([(0x56, 0x0A)], 0x8003, 17))
    for hl, want in ((0x4000, 0x4100), (0x4700, 0x4020), (0x47E0, 0x4800), (0x57FF, 0x581F)):
        r, m, _ = run([0xED, 0x93], {H: hl >> 8, L: hl & 255})
        chk('PIXELDN %04X' % hl, r[H] << 8 | r[L], want)
    r, m, _ = run([0xED, 0x94], {D: 191, E: 255})                              # (x 255, y 191)
    chk('PIXELAD', r[H] << 8 | r[L], 0x57FF)
    r, m, _ = run([0xED, 0x94], {D: 9, E: 17})
    chk('PIXELAD 17,9', r[H] << 8 | r[L], 0x4122)
    r, m, _ = run([0xED, 0x95], {E: 0x0B})
    chk('SETAE', r[A], 0x10)
    r, m, _ = run([0xED, 0x98], {B: 0x12, C: 0x34}, org=0x8100)
    chk('JP (C)', (r[PC], r[T]), (0x8140, 13))                               # IN = 5: 0x8000 + 5 << 6
    r, m, _ = run([0xED, 0x98], {}, org=0xBFFE)                               # next instruction 0xC000
    chk('JP (C) bank', r[PC], 0xC140)
    src = {0x9000: 0x11, 0x9001: 0xE3, 0x9002: 0x22}
    r, m, _ = run([0xED, 0xB4], {H: 0x90, L: 0, D: 0xA0, E: 0, B: 0, C: 3, A: 0xE3}, src, steps=3)
    chk('LDIRX', ([m[0xA000 + i] for i in range(3)], r[B] << 8 | r[C], r[PC], r[T], r[F] & 0x04),
        ([0x11, 0, 0x22], 0, 0x8002, 21 + 21 + 16, 0))
    r, m, _ = run([0xED, 0xA4], {H: 0x90, L: 0, D: 0xA0, E: 0, B: 0, C: 2, A: 0, F: 0xFF}, src)
    chk('LDIX', (m[0xA000], r[H] << 8 | r[L], r[D] << 8 | r[E], r[F] & 0xD5, r[PC], r[T]),
        (0x11, 0x9001, 0xA001, 0xC5, 0x8002, 16))
    r, m, _ = run([0xED, 0xBC], {H: 0x90, L: 2, D: 0xA0, E: 0, B: 0, C: 3, A: 0xE3}, src, steps=3)
    chk('LDDRX', ([m[0xA000 + i] for i in range(3)], r[H] << 8 | r[L], r[D] << 8 | r[E]),
        ([0x22, 0, 0x11], 0x8FFF, 0xA003))
    pat = {0x9000 + i: 0x10 + i for i in range(8)}
    r, m, _ = run([0xED, 0xB7], {H: 0x90, L: 0x05, D: 0xA0, E: 6, B: 0, C: 4, A: 0x17}, pat, steps=4)
    chk('LDPIRX', ([m[0xA006 + i] for i in range(4)], r[H] << 8 | r[L], r[PC]),
        ([0x16, 0, 0x10, 0x11], 0x9005, 0x8002))
    r, m, _ = run([0xED, 0xA5], {H: 0x90, L: 0xFF, D: 0x7F, E: 0x10, F: 0x01}, {0x90FF: 0x5A})
    chk('LDWS', (m[0x7F10], r[H], r[L], r[D], r[F] & 0xD7, r[T]), (0x5A, 0x90, 0x00, 0x80, 0x94, 14))
    r, m, _ = run([0xED, 0xA5], {D: 0xFF})
    chk('LDWS D=FF', (r[D], r[F] & 0xD7), (0x00, 0x51))           # Z H C: ADD, not INC
    for code, name in (([0xED, 0x00], 'ED 00 strict'), ([0xED, 0xB6], 'LDIRSCALE'),
                       ([0xED, 0x91, 1, 2], 'NEXTREG without a model')):
        try:
            run(code, {})
            out.append('%s: no Z80NError' % name)
        except Z80NError:
            pass
    r, m, _ = run([0xED, 0x00], {}, strict=False)
    chk('ED 00 non-strict', (r[PC], r[T]), (0x8002, 8))
    r, m, _ = run([0xED, 0xB0], {H: 0x90, L: 0, D: 0xA0, E: 0, B: 0, C: 1}, src)
    chk('LDIR untouched', (m[0xA000], r[T]), (0x11, 16))
    return out


if __name__ == '__main__':
    bad = selfcheck()
    print('\n'.join(bad) or 'z80n: OK (%d instructions)' % len(OPCODES))
