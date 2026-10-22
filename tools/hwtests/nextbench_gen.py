"""Cases for nextbench.asm (v3): every technique at several sizes, set up / reused / torn down.

    python tools/hwtests/nextbench_gen.py OUTDIR      -> OUTDIR/nextbench_cases.inc

build.py runs it before assembling nextbench. Each row = one routine (CALLed R times in a row,
R chosen on the board so a run fills ~120 raster lines), with an optional set-up routine run once
before the measurement and a tear-down after it, and a result check. kind 1 rows are copper
function tests: run once per speed, their value is a count / a line, not a time.

v3 repeats the whole table NRUNS times. A row's run-to-run spread is flagged when it is larger than
the measurement's own rounding can explain (SIGTHR, below).
"""
import math
import os
import sys

SRC, DST = 0xC000, 0xD000
COPY = (1, 16, 64, 256, 1024, 2048)
NRUNS = 5               # odd: N - 1 degrees of freedom stay even (closed-form chi-square below)
P = 0.001               # false-flag probability per value at most (176 values: < 0.2 per board run)


def chi2_upper(df, p):
    """x with P(chi2(df) > x) = p, for even df (survival = exp(-x/2) * sum (x/2)^k / k!, k < df/2)."""
    assert df % 2 == 0

    def sf(x):
        return math.exp(-x / 2) * sum((x / 2) ** k / math.factorial(k) for k in range(df // 2))
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if sf(mid) > p else (lo, mid)
    return hi


def sigthr(n=NRUNS, p=P):
    """Threshold on N * sum((d - mean)^2) for the per-run line counts d of one row and speed.

    d = 4 line reads after the routine minus 4 after the empty routine. A read whose instant wobbles
    by less than one line (frame_sync's exit, ~28 T of 224 at 3.5 MHz) can only round to one of two
    adjacent lines: variance at most 1/4. So rounding alone gives d a variance of at most 8/4 = 2
    line^2, and sum((d - mean)^2) / 2 is at most chi-square with N - 1 degrees of freedom. (1/12, the
    variance of a uniform rounding error, is the wrong bound: the simulator with a random phase per
    read flagged 16 of 176 values with it, none but the deliberately slowed row with 1/4.)"""
    return math.ceil(n * chi2_upper(n - 1, p) * 2)


class Gen:
    def __init__(s):
        s.rows, s.code, s.n = [], [], 0

    def add(s, name, size, body, check=0, n=0, setup='0', teardown='0', kind=0):
        s.n += 1
        lab = 'r%d' % s.n
        assert len(name) <= 8, name
        s.rows.append('        dw %s, %s, %s : db %d, %d : dw %d, %d : db "%-8s"' % (
            lab, setup, teardown, kind, check, n, size, name))
        s.code.append('%s:' % lab)
        s.code += [x if x.startswith('.') else '        ' + x for x in body]   # labels in column 0
        return lab


def dma(src, n, dst, r1, r2, r4=0xAD):
    """A full zxnDMA program: disable, WR0 A->B + address + length, WR1 / WR2 with 2 T timing,
    WR4 (continuous $AD / burst $CD) + port B address, WR5, LOAD, ENABLE."""
    b = [0x83, 0x7D, src & 255, src >> 8, n & 255, n >> 8, r1, 2, r2, 2, r4, dst & 255, dst >> 8, 0x82, 0xCF, 0x87]
    return b


def otir_prog(label, prog):
    return ['ld hl,%s : ld bc,%d : otir : ret' % (label, (len(prog) << 8) | 0x6B)]


def main(out):
    g = Gen()
    data = []

    def prog(name, b):
        data.append('%s: db %s' % (name, ','.join('$%02X' % x for x in b)))
        return name

    MEM_INC_A, MEM_FIX_A, MEM_INC_B, IO_FIX_B = 0x54, 0x64, 0x50, 0x68
    # ---- copy memory -> memory
    for n in COPY:
        if n == 1:
            g.add('LDIR', n, ['ld hl,SRC : ld de,DST : ld bc,1 : ldir : ret'], 1, n)
        else:
            g.add('LDIR', n, ['ld hl,SRC : ld de,DST : ld bc,%d : ldir : ret' % n], 1, n)
    for n in COPY:
        if n < 256:
            g.add('LDI unr', n, ['ld hl,SRC : ld de,DST : jp ldiblk_end-%d' % (2 * n)], 1, n)
        elif n == 256:
            g.add('LDI unr', n, ['ld hl,SRC : ld de,DST : jp ldiblk'], 1, n)
        else:
            g.add('LDI unr', n, ['ld hl,SRC : ld de,DST : ld a,%d' % (n // 256),
                                 '.l: call ldiblk : dec a : jr nz,.l : ret'], 1, n)
    for n in COPY[1:]:
        g.add('STACK', n, ['ld (spsave),sp : jp stkblk+%d' % ((256 - n // 8) * 14)], 1, n)
    for n in COPY:
        p = prog('dc%d' % n, dma(SRC, n, DST, MEM_INC_A, MEM_INC_B))
        g.add('DMA', n, otir_prog(p, dma(SRC, n, DST, MEM_INC_A, MEM_INC_B)), 1, n)
    # DMA reuse: retarget (new addresses / length, ports kept) and re-run (LOAD + ENABLE only)
    for n in (16, 256, 2048):
        b = [0x83, 0x7D, SRC & 255, SRC >> 8, n & 255, n >> 8, 0xAD, DST & 255, DST >> 8, 0xCF, 0x87]
        p = prog('dr%d' % n, b)
        g.add('DMA rtg', n, otir_prog(p, b), 1, n, setup='dmaset')
    b = [0x83, 0xCF, 0x87]
    g.add('DMA rrun', 256, otir_prog(prog('drr', b), b), 1, 256, setup='dmaset')
    for n in (256, 2048):
        b = dma(SRC, n, DST, MEM_INC_A, MEM_INC_B, 0xCD)
        g.add('DMA brst', n, otir_prog(prog('db%d' % n, b), b), 1, n)
    g.add('LDIRX', 256, ['ld hl,SRC : ld de,DST : ld bc,256 : ld a,$E3 : ldirx : ret'], 1, 256)
    # ---- fill $55
    for n in (16, 256, 2048):
        g.add('FILL LDR', n, ['ld hl,DST : ld (hl),$55 : ld de,DST+1 : ld bc,%d : ldir : ret' % (n - 1)], 2, n)
    for n in (16, 256, 2048):
        body = ['ld (spsave),sp : ld sp,DST+%d : ld hl,$5555' % n]
        if n <= 256:
            body += ['ld ix,.r : jp pushblk_end-%d' % (n // 2)]
        else:                               # pushblk = 128 x PUSH HL = 256 bytes, ends JP (IX)
            body += ['ld a,%d' % (n // 256), '.l: ld ix,.c : jp pushblk', '.c: dec a : jr nz,.l']
        body += ['.r: ld sp,(spsave) : ret']
        g.add('FILL PSH', n, body, 2, n)
    for n in (16, 256, 2048):
        bb = dma(0, n, DST, MEM_FIX_A, MEM_INC_B)
        p = 'df%d' % n
        data.append('%s: db $83,$7D : dw fillb, %d : db %s' % (p, n, ','.join('$%02X' % x for x in bb[6:])))
        g.add('FILL DMA', n, otir_prog(p, bb), 2, n)
    # ---- sprite patterns to port 0x5B (pattern slot 0)
    SEL = 'ld bc,$303B : xor a : out (c),a'
    for n in (64, 128, 256, 2048):
        if n <= 256:
            g.add('PAT OTIR', n, [SEL, 'ld hl,SRC : ld bc,%d : otir : ret' % (((n & 255) << 8) | 0x5B)])
        else:
            g.add('PAT OTIR', n, [SEL, 'ld hl,SRC : ld c,$5B : ld a,%d' % (n // 256),
                                  '.l: ld b,0 : otir : dec a : jr nz,.l : ret'])
    for n in (64, 128, 256, 2048):
        if n < 256:
            g.add('PAT OUTI', n, [SEL, 'ld hl,SRC : ld c,$5B : jp outiblk_end-%d' % (2 * n)])
        elif n == 256:
            g.add('PAT OUTI', n, [SEL, 'ld hl,SRC : ld c,$5B : jp outiblk'])
        else:
            g.add('PAT OUTI', n, [SEL, 'ld hl,SRC : ld c,$5B : ld a,%d' % (n // 256),
                                  '.l: call outiblk : dec a : jr nz,.l : ret'])
    for n in (64, 128, 256, 2048):
        b = dma(SRC, n, 0x5B, MEM_INC_A, IO_FIX_B)
        p = prog('dp%d' % n, b)
        g.add('PAT DMA', n, [SEL] + otir_prog(p, b))
    # ---- sprite attributes (invisible: byte 3 = 0)
    g.add('ATR 57', 1, [SEL, 'ld hl,attr32 : ld c,$57 : outi : outi : outi : outi : ret'])
    g.add('ATR 57', 32, [SEL, 'ld hl,attr32 : ld bc,$8057 : otir : ret'])
    nr4 = ['ld a,(hl) : nextreg $35,a : inc hl', 'ld a,(hl) : nextreg $36,a : inc hl',
           'ld a,(hl) : nextreg $37,a : inc hl', 'ld a,(hl) : nextreg $38,a : inc hl']
    g.add('ATR NR', 1, ['nextreg $34,0 : ld hl,attr32'] + nr4 + ['ret'])
    g.add('ATR NR', 32, ['ld hl,attr32 : ld e,0', '.l: ld a,e : nextreg $34,a'] + nr4 +
          ['inc e : ld a,e : cp 32 : jr nz,.l : ret'])
    g.add('HIDE NR', 128, ['nextreg $34,0 : ld b,128', '.l: nextreg $78,0 : djnz .l : ret'])
    g.add('HIDE 57', 128, [SEL, 'ld hl,COPZ : ld bc,$0057 : otir : otir : ret'])
    g.add('SPR OFF', 0, ['nextreg $15,0 : ret'])
    # ---- registers, paging
    g.add('NR v', 0, ['nextreg $7F,$55 : ret'])
    g.add('NR a', 0, ['ld a,$55 : nextreg $7F,a : ret'])
    g.add('PORTPAIR', 0, ['ld bc,$243B : ld a,$7F : out (c),a : inc b : ld a,$55 : out (c),a : ret'])
    g.add('NR READ', 0, ['ld bc,$243B : ld a,$7F : out (c),a : inc b : in a,(c) : ret'])
    g.add('MMU', 1, ['nextreg $56,0 : ret'])
    g.add('MMU', 4, ['nextreg $54,4 : nextreg $55,5 : nextreg $56,0 : nextreg $57,1 : ret'])
    g.add('7FFD', 0, ['ld bc,$7FFD : ld a,$10 : out (c),a : ret'])
    # ---- 8x8 cells, buffer flips, scroll
    g.add('ULA CHAR', 0, ['ld hl,$4000 : ld de,SRC'] + ['ld a,(de) : ld (hl),a : inc e : inc h'] * 8 +
          ['ld a,$38 : ld ($5800),a : ret'])
    g.add('TILE ENT', 0, ['ld hl,$1234 : ld ($6000),hl : ret'])
    g.add('L2 CELL', 0, ['ld hl,SRC : ld de,DST : ld a,8', '.r:'] + ['ldi'] * 8 +
          ['ld e,0 : inc d : dec a : jr nz,.r : ret'])
    g.add('TM SWAP', 0, ['nextreg $6E,$6C : ret'])
    g.add('L2 FLIP', 0, ['nextreg $12,8 : ret'])
    g.add('SHADOW2', 0, ['ld bc,$7FFD : ld a,$18 : out (c),a : ld a,$10 : out (c),a : ret'])
    g.add('TM SCRL', 0, ['nextreg $2F,0 : nextreg $30,1 : ret'])
    g.add('L2 SCRL', 0, ['nextreg $16,1 : nextreg $17,0 : ret'])
    # ---- palette (sprite palette 1)
    g.add('PAL8', 1, ['nextreg $43,$20 : nextreg $40,0 : nextreg $41,$E3 : ret'])
    g.add('PAL8', 16, ['nextreg $43,$20 : nextreg $40,0 : ld hl,SRC : ld b,16',
                       '.l: ld a,(hl) : nextreg $41,a : inc hl : djnz .l : ret'])
    g.add('PAL9', 1, ['nextreg $43,$20 : nextreg $40,0 : nextreg $44,$E3 : nextreg $44,1 : ret'])
    g.add('PAL SEL', 0, ['nextreg $43,0 : ret'])
    # ---- copper: load (stopped), start / stop
    for n in (8, 32, 256):
        g.add('COP NR', n, ['nextreg $62,0 : nextreg $61,0 : ld hl,COPZ : ld de,%d' % (2 * n),
                            '.l: ld a,(hl) : nextreg $60,a : inc hl : dec de : ld a,d : or e : jr nz,.l : ret'])
    for n in (8, 32, 256):
        g.add('COP IO', n, ['nextreg $62,0 : nextreg $61,0 : ld bc,$243B : ld a,$60 : out (c),a : inc b',
                            'ld hl,COPZ : ld de,%d' % (2 * n),
                            '.l: ld a,(hl) : out (c),a : inc hl : dec de : ld a,d : or e : jr nz,.l : ret'])
    g.add('COPGO+ST', 0, ['nextreg $62,%01000000 : nextreg $62,0 : ret'], setup='copnops')
    # ---- copper at work
    g.add('LDIR+COP', 256, ['ld hl,SRC : ld de,DST : ld bc,256 : ldir : ret'], 1, 256,
          setup='copmove7f', teardown='copstop')
    g.add('CP WAIT', 120, ['jp cp_wait'], kind=1)
    g.add('CP APART', 256, ['ld a,$7F : ld e,$55 : ld d,0 : jp cp_pal'], kind=1)
    g.add('CP SHARE', 256, ['ld a,$40 : ld e,$00 : ld d,1 : jp cp_pal'], kind=1)

    lines = ['; generated by tools/hwtests/nextbench_gen.py - do not edit', 'tests:'] + g.rows + \
        ['        dw 0', 'NTESTS  equ %d' % g.n, 'NRUNS   equ %d' % NRUNS, 'SIGTHR  equ %d' % sigthr()] + \
        g.code + data
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, 'nextbench_cases.inc')
    open(p, 'w').write('\n'.join(lines) + '\n')
    return p


if __name__ == '__main__':
    print(main(sys.argv[1] if len(sys.argv) > 1 else '.'))
