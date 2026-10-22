# Hardware tests

Small .nex programs that answer one hardware question each, for facts the toolkit's simulator does
not model (BRIEFING A1 blind spots). Recipe (after MikeDX/next-testsuite): one question per .nex,
cases from Ped7g's tests (docs/TECHNIQUES.md "Hardware ground truth") plus ours; each visual phase
held on screen ~2 s; the final screen is one coloured block per test (green pass, red fail, white
visual). Build:

    python tools/hwtests/build.py im2hold -o OUTDIR

Run the .nex on a real Next (NextZXOS browser), photograph the final screen and the border; then
run it in MAME / CSpect to see whether the emulator agrees. Record the result in the C2 item and,
for an emulator, LEARNINGS 2.7 [MAME]. Never commit the built .nex.

Every test writes a results table at $7E00: `NXHT`, version, test count, then two bytes per test -
status (0 not run, 1 pass, 2 fail, 3 info) and a detail byte. A MAME script can read it once the
border is green or red.

## im2hold - BRIEFING C2 #34 (hardware IM2 mode holds interrupts)

Final screen: seven 2x2 blocks on character rows 2-3 (columns 2, 5, 8, ..., 20), numbered by test
(run order T1 T2 T3 T5 T6 T4 T7). Green pass, red fail, white info, black not run. Under each
block (row 5) its detail byte in hex. Border green = nothing failed, red = something did.

| # | Test | Pass means | Detail byte |
|---|---|---|---|
| 1 | vector | in hardware IM2 mode ($C0 bit 0) the ULA interrupt reads its handler from I*256 + $16 | runs of a wrong vector's handler |
| 2 | held | an interrupt arriving during 3 frames with interrupts off is taken at the EI (not lost) | interrupts taken after the EI |
| 3 | pulse (control) | the same in pulse mode ($C0 = 0) is LOST, as expected | interrupts taken (0 = lost) |
| 4 | ret-ack (info, white) | - | handler runs in one frame when it ends EI;RET instead of RETI: 1 = RET acknowledges too, 200 = never acknowledged (re-fires; the test stops it) |
| 5 | trampoline | vector -> push game handler -> RETI (acknowledge) -> game handler ending EI;RET: 4-6 runs in 5 frames, foreground keeps running | handler runs |
| 6 | uniform table | a game-style 257-byte IM2 table (all $A1 -> handler at $A1A1) works unchanged in hardware mode: 4-6 runs in 5 frames | handler runs |
| 7 | recover | after test 4, one dummy RETI with interrupts off lets the interrupts come again: 4-6 runs in 5 frames | handler runs |

Board results:
- v1 (2026-10-20, Dean): T1-T3 green, T4 white, T5 + T6 red. T5 / T6 ran right after T4: suspected
  cause, T4's never-acknowledged interrupt blocks the next ones (v2 runs T4 late and adds T7).
- v2 (2026-10-20, Dean, board photo): ALL PASS, border green. Details T1-T7: 01 01 00 01 06 06 06.
  T4 = 01: a handler ending EI;RET runs once and no interrupt comes after it - RET does NOT
  acknowledge, and the unacknowledged interrupt BLOCKS every later one (so v1's T5 / T6 saw 0).
  T7 = 06: one dummy RETI with interrupts off clears it. (6 in "5 frames": the count starts mid-frame.)

If the screen stays black with a black border after a few seconds, a test hung: note the border
colour and which blocks are drawn (none are drawn until the end) and report it.

Reading the results: tests 2, 5 and 6 passing = C2 #34's design works (hooks may run with
interrupts off; the game's handler is reached through a RETI trampoline or the game's own uniform
table). Test 4 says whether a game handler that ends EI;RET needs the trampoline at all.

## z80ntest - every Z80N instruction against nexclash/z80n.py

    python tools/hwtests/build.py z80ntest -o OUTDIR

build.py first runs `z80ntest_gen.py`, which takes each case's expected result from the shared
module's handlers (SkoolKit + `z80n.install`) - so the board checks exactly what the toolkit's
verifiers assume. Runs ~10 s (blue border), then shows page 1; ANY KEY flips between the pages.
Photograph both pages and the border.

Page 1, FUNC (46 cases): one Z80N instruction from a known A F BC DE HL, SP = $6200 and a 1 KB
window at $6000; A..L, SP and a checksum of the window compared. Flag-changing instructions run
from F = 0 and F = $FF (last character of the name 0 / F), the rest from F = $A5. Columns: name,
F on the board, F expected, code. Green all equal; YELLOW only F differs (the flag question the
module had to guess - write down both values); red R = a register or SP, M = memory differs.
NEXTRGn / NEXTRGA / OUTINB write NextReg $7F and read it back. JPC: JP (C) with IN = 5 must land
on $C140; JPCedge runs from $BFFE, so A = $FF (red) means the base came from the instruction's own
address instead of the next one.

Page 2, TIME: T-states at 3.5 MHz from the raster line counter (2048 runs per instruction,
4 measurements a quarter line apart, scaled by 2048 x LD A,(IX+0) = 19 T). Columns: name,
measured T, expected T; green within 0.5. NEG / LDI / LDIR are Z80 controls (8 / 16 / 21): if
they are red the method failed on that machine, not the Z80N rows. Timing code and data stay in
uncontended RAM; any video timing (48K / 128K, 50 / 60 Hz) works.

Border: green all pass, yellow only flag differences, red a failure. The harness itself uses
NEXTREG (speed, NextReg $7F): if NEXTREG were broken every page would be wrong.

Results table at $7E00 as above (status 4 = flags only; detail = F on page 1, T * 10 on page 2),
then the calibration line count (word); per FUNC case the registers at $7000 + 16 * (n-1):
F A C B E D L H, SP, checksum.

Board results:
- v1 (2026-10-21, core 3.02.00): TIME all green (LDWS 13.9, NEXTREG 20.0 / 17.0, PUSHnn 23.0;
  controls 8.1 / 16.0 / 20.9). FUNC all green except LDWSF yellow (F $94, module said $95: LDWS's
  CF comes from ADD D,1 - module fixed, v2 expects $94) and LDPIRX0 / LDPIRXF red M (memory) with
  F $00 / $C1 instead of $08 / $C9: core changelog 3.02.02 fixes LDPIRX - re-run on 3.02.02+.
- v2 (2026-10-21, same board, core 3.02.00): all green except LDPIRX0 / LDPIRXF (red M, F $00 /
  $C1 again - expected on 3.02.00). LDWS7F $94 and LDWSFF $51: LDWS's flags are ADD D,1's, CF set
  when D was $FF - the module's fix confirmed. TIME all green again (LDWS 13.9, NEG 8.0).
- CSpect 3.3.1.0 (2026-10-21, reports core 4.00.00; emulator, not ground truth): differs from the
  board in ADD rr,A (CF kept: ADDHLAF / ADDDEAF $FF, ADDBCA $A5), LDIX / LDIRX / LDDX / LDDRX from
  F = $FF (bits 5 / 3 kept: $ED / $E9), LDWS (INC D flags: 7F -> $95, FF -> $50), JP (C) (IN-style
  flags, F $05; target right) and PUSH nn timing (19.0 T, board 23). LDPIRX: memory as the 3.02.02+
  model (no M), F $00 / $E9. Everything else, all other T-states, as the board.

Checked before any board (2026-10-21): the .nex run in SkoolKit + z80n with a modelled raster
(224 T x 312 lines, 228 x 311, 224 x 262): 77/77 green, T within 0.1; with ADD HL,A keeping CF,
LDWS at 16 T and a wrong MUL result: ADDHLAF yellow, MUL red R, LDWS red (15.9).

## nextbench - what Next techniques cost, at several sizes, set up / reused / torn down (v2)

    python tools/hwtests/build.py nextbench -o OUTDIR     (runs nextbench_gen.py: the 88 rows)

Microseconds PER CALL at 3.5 MHz and 28 MHz (the hooks' speed) on the raster line counter, as
z80ntest's TIME page: 4 dithered passes, the same with an empty routine subtracted, calibrated
against 2048 x LD A,(IX+0) at 3.5 MHz. The repeat count R is chosen per row and speed by a probe
run (a measurement fills ~140 lines; R = 1 for long calls; ">" = one call does not fit a frame),
so no row can wrap the line counter. ~1 minute with a blue border, then 5 pages (any key).
Border green = every check passed, red = a "!" somewhere.

Rows (name, size):
- copy 1 / 16 / 64 / 256 / 1024 / 2048 B: LDIR, LDI unr (unrolled; one 256-LDI block entered at
  the right point, looped above 256), STACK (2 KB unrolled POP / PUSH, entered at the right chunk),
  DMA (full 16-byte program each call); DMA rtg (only addresses + length rewritten, ports kept)
  16 / 256 / 2048; DMA rrun (LOAD + ENABLE: the same transfer again) 256; DMA brst (burst mode)
  256 / 2048; LDIRX 256. Every copy is checked.
- fill $55 16 / 256 / 2048: FILL LDR, FILL PSH (PUSH block), FILL DMA (fixed source). Checked.
- sprite pattern to port 0x5B 64 / 128 / 256 / 2048: PAT OTIR, PAT OUTI (unrolled), PAT DMA.
- sprite attributes: ATR 57 (port, 1 / 32 sprites), ATR NR (NEXTREG $34-$38, 1 / 32), HIDE NR
  (128 sprites by NEXTREG $78 post-increment), HIDE 57 (128 hide records by port), SPR OFF ($15).
- NR v, NR a, PORTPAIR (OUT $243B + $253B), NR READ; MMU 1 / 4 slots, 7FFD.
- ULA CHAR, TILE ENT, L2 CELL; TM SWAP ($6E), L2 FLIP ($12), SHADOW2 (7FFD bit 3 and back);
  TM SCRL, L2 SCRL.
- PAL8 1 / 16 entries, PAL9 1, PAL SEL ($43).
- copper load (stopped) 8 / 32 / 256 instructions by NEXTREG $60 (COP NR) / OUT $253B (COP IO);
  COPGO+ST (start + stop); LDIR+COP (LDIR 256 while the copper loops MOVEs: does the copper slow
  the CPU?).
- copper function (the value is a number): CP WAIT = raster line at which the CPU sees the MOVE
  after a copper WAIT 120 (copper line numbering vs $1E/$1F; ">" = never); CP APART = wrong palette
  entries (of 256) the CPU reads back while the copper loops MOVE $7F (expected 0, "!" otherwise);
  CP SHARE = the same with the copper looping MOVE $40, the palette index the CPU uses (wrong
  entries expected: TECHNIQUES 1 "never drive one register pair from both"; info, never "!").

Results at $7A00: "NXB2", version, count, calibration lines, per row 10 bytes (value at 3.5 / 28
MHz as dwords in tenths, R at 3.5 / 28 MHz), then a flag byte per row (bit 0 / 1 check failed at
3.5 / 28 MHz, bit 2 / 3 did not fit a frame).

v1 (commit 0b51cc9, 32 rows, one size each, fixed R) is the run the board results below were taken
with; TECHNIQUES 1.0 holds its table.

v2 board run (2026-10-22, core 3.02.00): all 88 rows; every 3.5 MHz CPU row matched its T-state
count; DMA "!" at 3.5 MHz only (border red), right at 28 MHz; CP WAIT 122 / 120, CP APART 0 / 0,
CP SHARE 255 / 255. Table and conclusions: docs/TECHNIQUES.md 1.0b. Photos: specnext
reference/hwtests/nextbench/ (board_v2_p1..p5).

v2 checked before any board (2026-10-22): in SkoolKit + z80n with a modelled raster (no DMA, copper
or CPU speed change) every CPU row at 3.5 MHz matches its T-state count (LDIR 64 390.7 for 391.1 us,
LDI unr 64 300.2 for 304, L2 CELL 359.5 for 360.6, NR v 5.7 for 5.7); the R probe needed three
tiers (1 / 8 / 64 calls) - a single tier either under-sized tiny rows or overran the frame on rows
of 100-640 us. DMA / copper rows show "!" / ">" there (no DMA, no copper).

Board results: v1 (2026-10-22, core 3.02.00): every CPU row at 3.5 MHz as its T-state count; 28 MHz
6.3-7x faster (memory wait states); DMA rows WRONG at 3.5 MHz ("!" on DMA 1B / 256 / 2K and FILL DMA,
border red; the core changelog fixes it in 3.02.02), right at 28 MHz. The table and conclusions:
docs/TECHNIQUES.md 1.0. Photos: specnext reference/hwtests/nextbench/.

Checked before any board (2026-10-22): in SkoolKit + z80n with a modelled raster (no DMA, no CPU
speed change) every CPU-only row at 3.5 MHz matches its T-state count within 0.7 % (e.g. LDI x256
1251.3 for 1249.7 us, NEXTREGv 5.5 for 5.7, ULA CHAR 61.7 for 61.7).
