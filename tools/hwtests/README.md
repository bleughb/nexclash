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

Checked before any board (2026-10-21): the .nex run in SkoolKit + z80n with a modelled raster
(224 T x 312 lines, 228 x 311, 224 x 262): 77/77 green, T within 0.1; with ADD HL,A keeping CF,
LDWS at 16 T and a wrong MUL result: ADDHLAF yellow, MUL red R, LDWS red (15.9).
