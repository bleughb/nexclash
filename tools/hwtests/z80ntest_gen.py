"""Cases for z80ntest.asm: every Z80N instruction, expected results from nexclash/z80n.py.

    python tools/hwtests/z80ntest_gen.py OUTDIR      -> OUTDIR/z80ntest_cases.inc

build.py runs it before assembling z80ntest. The expected values come from the shared module's
handlers (SkoolKit Simulator + z80n.install), so a red or yellow entry on the board is a place
where nexclash/z80n.py and the hardware disagree. Timing expectations are z80n.OPCODES' T-states.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from nexclash import z80n  # noqa: E402

WIN, WINLEN, CSTACK, RB = 0x6000, 0x400, 0x6200, 0x63F0     # RB: NextReg $7F read back here
JPC_AT, JPC_EDGE, JPC_VAL = 0xC020, 0xBFFE, 5
A, F, B, C, D, E, H, L, SP, PC = 0, 1, 2, 3, 4, 5, 6, 7, 12, 24
READBACK = ['ld bc,$243B', 'ld a,$7F', 'out (c),a', 'inc b', 'in a,(c)', 'ld ($%04X),a' % RB]
SEL7F = ['ld bc,$243B', 'ld a,$7F', 'out (c),a']

# functional cases: (name, bytes, regs, memory, F values, pre, post); 46 = one screen page
SRC = {0x6000: 0x11, 0x6001: 0xE3, 0x6002: 0x22}
PAT = {0x6000 + i: 0x10 + i for i in range(8)}
FUNC = [
    ('SWAPNIB', [0xED, 0x23], {A: 0x5A}, {}, [0xA5], [], []),
    ('MIRROR', [0xED, 0x24], {A: 0x1E}, {}, [0xA5], [], []),
    ('TESTz', [0xED, 0x27, 0x0F], {A: 0xF0}, {}, [0x00, 0xFF], [], []),
    ('TESTnz', [0xED, 0x27, 0xB1], {A: 0xF3}, {}, [0x00], [], []),
    ('BSLA', [0xED, 0x28], {D: 0x00, E: 0x81, B: 0x22}, {}, [0xA5], [], []),
    ('BSRA', [0xED, 0x29], {D: 0x80, E: 0x00, B: 4}, {}, [0xA5], [], []),
    ('BSRL', [0xED, 0x2A], {D: 0x80, E: 0x00, B: 4}, {}, [0xA5], [], []),
    ('BSRF', [0xED, 0x2B], {D: 0x00, E: 0x10, B: 4}, {}, [0xA5], [], []),
    ('BSRF 20', [0xED, 0x2B], {D: 0x12, E: 0x34, B: 20}, {}, [0xA5], [], []),
    ('BRLC', [0xED, 0x2C], {D: 0x80, E: 0x01, B: 0x11}, {}, [0xA5], [], []),
    ('MUL', [0xED, 0x30], {D: 0xFF, E: 0xFF}, {}, [0xA5], [], []),
    ('ADDHLA', [0xED, 0x31], {H: 0xFF, L: 0xF0, A: 0x20}, {}, [0x00, 0xFF], [], []),
    ('ADDDEA', [0xED, 0x32], {D: 0x12, E: 0xF0, A: 0x20}, {}, [0x00, 0xFF], [], []),
    ('ADDBCA', [0xED, 0x33], {B: 0x01, C: 0x02, A: 0x03}, {}, [0xA5], [], []),
    ('ADDHLnn', [0xED, 0x34, 0x34, 0x12], {H: 0xF0, L: 0x01}, {}, [0xA5], [], []),
    ('ADDDEnn', [0xED, 0x35, 0xFF, 0x00], {D: 0x01, E: 0x01}, {}, [0xA5], [], []),
    ('ADDBCnn', [0xED, 0x36, 0x00, 0x80], {B: 0x80, C: 0x01}, {}, [0xA5], [], []),
    ('PUSHnn', [0xED, 0x8A, 0x12, 0x34], {}, {}, [0xA5], [], []),
    ('NEXTRGn', [0xED, 0x91, 0x7F, 0x5A], {}, {}, [0xA5], ['nextreg $7F,0'], READBACK),
    ('NEXTRGA', [0xED, 0x92, 0x7F], {A: 0xC3}, {}, [0xA5], ['nextreg $7F,0'], READBACK),
    ('PXDN 1', [0xED, 0x93], {H: 0x40, L: 0x00}, {}, [0xA5], [], []),
    ('PXDN 2', [0xED, 0x93], {H: 0x47, L: 0x00}, {}, [0xA5], [], []),
    ('PXDN 3', [0xED, 0x93], {H: 0x47, L: 0xE0}, {}, [0xA5], [], []),
    ('PXDN 4', [0xED, 0x93], {H: 0x57, L: 0xFF}, {}, [0xA5], [], []),
    ('PXAD 1', [0xED, 0x94], {D: 191, E: 255}, {}, [0xA5], [], []),
    ('PXAD 2', [0xED, 0x94], {D: 9, E: 17}, {}, [0xA5], [], []),
    ('SETAE', [0xED, 0x95], {E: 0x0B}, {}, [0xA5], [], []),
    ('LDIX', [0xED, 0xA4], {H: 0x60, L: 0x00, D: 0x61, E: 0x00, B: 0, C: 2, A: 0xE3}, SRC, [0x00, 0xFF], [], []),
    ('LDIRX', [0xED, 0xB4], {H: 0x60, L: 0x00, D: 0x61, E: 0x00, B: 0, C: 3, A: 0xE3}, SRC, [0x00, 0xFF], [], []),
    ('LDDX', [0xED, 0xAC], {H: 0x60, L: 0x02, D: 0x61, E: 0x00, B: 0, C: 2, A: 0xE3}, SRC, [0x00, 0xFF], [], []),
    ('LDDRX', [0xED, 0xBC], {H: 0x60, L: 0x02, D: 0x61, E: 0x00, B: 0, C: 3, A: 0xE3}, SRC, [0x00, 0xFF], [], []),
    ('LDPIRX', [0xED, 0xB7], {H: 0x60, L: 0x05, D: 0x61, E: 0x06, B: 0, C: 4, A: 0x17}, PAT, [0x00, 0xFF], [], []),
    ('LDWS', [0xED, 0xA5], {H: 0x60, L: 0xFF, D: 0x7F, E: 0x10}, {0x60FF: 0x5A}, [0x00, 0xFF], [], []),
    ('OUTINB', [0xED, 0x90], {B: 0x25, C: 0x3B, H: 0x60, L: 0x00}, {0x6000: 0x77}, [0x00, 0xFF],
     ['nextreg $7F,0'] + SEL7F, READBACK),
    ('JPC', None, {B: 0x25, C: 0x3B}, {}, [0xA5], None, []),
    ('JPCedge', None, {B: 0x25, C: 0x3B}, {}, [0xA5], None, []),
]

# timing cases: (name, mode, body, base body, adjust T, expected T, regs); mode 0 = 8 x 256 copies,
# mode 1 = one repeating instruction with BC = 2048. T = 19 * (lines(body) - lines(base)) /
# (lines(LD A,(IX+0)) - lines(nothing)) + adjust
R0 = {H: 0xD0, L: 0x00, D: 0xE0, E: 0x00, B: 0xFF, C: 0xFF, A: 0x55}    # reads $D0xx, writes $E0xx
RREP = {**R0, B: 0x08, C: 0x00}                       # BC = 2048 repeats
OUT = {**R0, B: 0xFF, C: 0xFD}                        # port $FFFD (AY register select) <- 0


def t_(op):
    return z80n.OPCODES[op][2]


TIME = [
    ('NEG z80', 0, [0xED, 0x44], [], 0, 8, R0),
    ('LDI z80', 0, [0xED, 0xA0], [], 0, 16, R0),
    ('LDIRz80', 1, [0xED, 0xB0], [], 0, 21, RREP),
    ('SWAPNIB', 0, [0xED, 0x23], [], 0, t_(0x23), R0),
    ('MIRROR', 0, [0xED, 0x24], [], 0, t_(0x24), R0),
    ('TEST n', 0, [0xED, 0x27, 0x0F], [], 0, t_(0x27), R0),
    ('BSLA', 0, [0xED, 0x28], [], 0, t_(0x28), {**R0, B: 3}),
    ('BSRA', 0, [0xED, 0x29], [], 0, t_(0x29), {**R0, B: 3}),
    ('BSRL', 0, [0xED, 0x2A], [], 0, t_(0x2A), {**R0, B: 3}),
    ('BSRF', 0, [0xED, 0x2B], [], 0, t_(0x2B), {**R0, B: 3}),
    ('BRLC', 0, [0xED, 0x2C], [], 0, t_(0x2C), {**R0, B: 3}),
    ('MUL', 0, [0xED, 0x30], [], 0, t_(0x30), R0),
    ('ADDHLA', 0, [0xED, 0x31], [], 0, t_(0x31), R0),
    ('ADDDEA', 0, [0xED, 0x32], [], 0, t_(0x32), R0),
    ('ADDBCA', 0, [0xED, 0x33], [], 0, t_(0x33), R0),
    ('ADDHLnn', 0, [0xED, 0x34, 0x01, 0x00], [], 0, t_(0x34), R0),
    ('ADDDEnn', 0, [0xED, 0x35, 0x01, 0x00], [], 0, t_(0x35), R0),
    ('ADDBCnn', 0, [0xED, 0x36, 0x01, 0x00], [], 0, t_(0x36), R0),
    ('PUSHnn', 0, [0xED, 0x8A, 0x12, 0x34], [], 0, t_(0x8A), R0),    # the block has its own SP
    ('OUTINB', 0, [0xED, 0x90], [], 0, t_(0x90), OUT),
    ('NEXTRGn', 0, [0xED, 0x91, 0x7F, 0x00], [], 0, t_(0x91), R0),
    ('NEXTRGA', 0, [0xED, 0x92, 0x7F], [], 0, t_(0x92), R0),
    ('PIXELDN', 0, [0xED, 0x93], [], 0, t_(0x93), {**R0, H: 0x40}),
    ('PIXELAD', 0, [0xED, 0x94], [], 0, t_(0x94), R0),
    ('SETAE', 0, [0xED, 0x95], [], 0, t_(0x95), R0),
    ('LDIX', 0, [0xED, 0xA4], [], 0, t_(0xA4), R0),
    ('LDWS', 0, [0x16, 0xE0, 0xED, 0xA5], [0x16, 0xE0], 0, t_(0xA5), R0),     # LD D,$E0 each time
    ('LDDX', 0, [0xED, 0xAC], [], 0, t_(0xAC), {**R0, H: 0xD7, L: 0xFF}),
    ('LDIRX', 1, [0xED, 0xB4], [], 0, t_(0xB4), RREP),
    ('LDPIRX', 1, [0xED, 0xB7], [], 0, t_(0xB7), RREP),
    ('LDDRX', 1, [0xED, 0xBC], [], 0, t_(0xBC), {**RREP, H: 0xD7, L: 0xFF}),
]


def fletcher(mem):
    s1 = s2 = 0
    for a in range(WIN, WIN + WINLEN):
        s1 = (s1 + mem[a]) & 255
        s2 = (s2 + s1) & 255
    return s2, s1                       # bytes as `ld (gchk),de` stores D = s1, E = s2


def expect(code, regs, memset, f, edge=False):
    """Run one case in SkoolKit + z80n -> (F A C B E D L H, SP, checksum bytes)."""
    from skoolkit.simulator import Simulator
    mem = [0] * 65536
    for a, v in memset.items():
        mem[a] = v
    nr = {}

    class Tr:
        def read_port(s, r, port):
            assert port == 0x253B
            return JPC_VAL

        def write_port(s, r, port, value, *x):
            assert port == 0x253B
            nr[0x7F] = value

    org = (JPC_EDGE if edge else JPC_AT) if code is None else 0x8000
    if code is None:
        code = [0xED, 0x98]
    mem[org:org + len(code)] = code
    sim = Simulator(mem, {})
    r = sim.registers
    for k in (A, B, C, D, E, H, L):
        r[k] = regs.get(k, 0)
    r[F], r[SP], r[PC] = f, CSTACK, org
    sim.set_tracer(Tr())
    z80n.install(sim, lambda reg, v: nr.__setitem__(reg, v))
    for _ in range(100000):
        sim.opcodes[mem[r[PC]]]()
        if not (org <= r[PC] < org + len(code)):
            break
    if code == [0xED, 0x98]:
        assert r[PC] == 0xC000 + (JPC_VAL << 6), hex(r[PC])
        r[A] = JPC_VAL                  # the slot's stub: LD A,slot ; JP (IX)
    elif r[PC] != org + len(code):
        raise SystemExit('case did not finish: %r' % code)
    if 0x7F in nr:
        mem[RB] = nr[0x7F]
    regs8 = [r[F], r[A], r[C], r[B], r[E], r[D], r[L], r[H]]
    return regs8, r[SP], fletcher(mem)


def db(bs):
    return '        db ' + ','.join('$%02X' % b for b in bs)


def main(out):
    lines, run, jpc, names = [], [], [], []
    n = 0
    for name, code, regs, memset, fs, pre, post in FUNC:
        for f in fs:
            n += 1
            label = 'case_%d' % n
            nm = name if len(fs) == 1 else name + ('0' if f == 0 else 'F')     # last char: initial F
            names.append(nm)
            edge = name == 'JPCedge'
            regs8, sp, chk = expect(code, regs, memset, f, edge)
            init = [f, regs.get(A, 0), regs.get(C, 0), regs.get(B, 0), regs.get(E, 0), regs.get(D, 0),
                    regs.get(L, 0), regs.get(H, 0)]
            lines.append('; %d %s' % (n, nm))
            lines.append('%s:' % label)
            lines.append('        ld hl,set_%d : call setup' % n)
            if code is None:
                lines += ['        nextreg $7F,%d' % JPC_VAL] + ['        ' + x for x in SEL7F]
                lines.append('        ld ix,cont_%d' % n)
            else:
                lines += ['        ' + x for x in pre]
            lines.append('        ld (msp),sp')
            lines.append('        ld sp,ini_%d : pop af : pop bc : pop de : pop hl' % n)
            lines.append('        ld sp,CSTACK')
            if code is None:
                lines.append('        jp %s' % ('JPC_EDGE' if edge else 'JPC_AT'))
            else:
                lines.append(db(code))
            lines.append('cont_%d: ld (gsp),sp' % n)
            lines.append('        ld sp,GOT+8 : push hl : push de : push bc : push af')
            lines.append('        ld sp,(msp)')
            lines += ['        ' + x for x in post]
            lines.append('        ld hl,exp_%d : ld a,%d : jp check' % (n, n))
            lines.append('ini_%d:' % n + db(init)[7:])
            lines.append('exp_%d:' % n + db(regs8 + [sp & 255, sp >> 8] + list(chk))[7:])
            lines.append('set_%d:' % n)
            for a, v in sorted(memset.items()):
                lines.append('        dw $%04X : db $%02X' % (a, v))
            lines.append('        dw 0')
            (jpc if code is None else run).append(label)
    nfunc = n
    tlines = ['ttab:']
    for name, mode, body, base, adj, exp, regs in TIME:
        n += 1
        assert len(name) <= 7, name
        names.append(name)
        init = [0, regs.get(A, 0), regs.get(C, 0), regs.get(B, 0), regs.get(E, 0), regs.get(D, 0),
                regs.get(L, 0), regs.get(H, 0)]
        tlines.append('        db %d,%d,%d : dw tini_%d : db %d : dw tx_%d : db %d : dw tb_%d   ; %s'
                      % (mode, exp, adj, n, len(body), n, len(base), n, name))
        lines.append('tini_%d:' % n + db(init)[7:])
        lines.append('tx_%d:' % n + (db(body)[7:] if body else ''))
        lines.append('tb_%d:' % n + (db(base)[7:] if base else ''))
    tlines.append('        db $FF')
    head = ['; generated by tools/hwtests/z80ntest_gen.py from nexclash/z80n.py - do not edit',
            'NFUNC   equ %d' % nfunc, 'NTIME   equ %d' % (n - nfunc), 'NTESTS  equ %d' % n,
            'run_cases:'] + ['        call %s' % x for x in run] + ['        ret', 'run_jpc:'] + \
        ['        call %s' % x for x in jpc] + ['        ret', 'names:']
    assert nfunc <= 46 and n - nfunc <= 46, (nfunc, n - nfunc)
    for nm in names:
        assert len(nm) <= 7, nm
        head.append('        db "%-8s"' % nm)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, 'z80ntest_cases.inc')
    with open(path, 'w') as fh:
        fh.write('\n'.join(head + tlines + lines) + '\n')
    return path


if __name__ == '__main__':
    print(main(sys.argv[1] if len(sys.argv) > 1 else '.'))
