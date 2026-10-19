# Hardware tests

Small .nex programs that answer one hardware question each, for facts the toolkit's simulator does
not model (BRIEFING A1 blind spots). Recipe: BRIEFING C2 "How to test #31 / #35". Build:

    python tools/hwtests/build.py im2hold -o OUTDIR

Run the .nex on a real Next (NextZXOS browser), photograph the final screen and the border; then
run it in MAME / CSpect to see whether the emulator agrees. Record the result in the C2 item and,
for an emulator, LEARNINGS 2.7 [MAME]. Never commit the built .nex.

Every test writes a results table at $7E00: `NXHT`, version, test count, then two bytes per test -
status (0 not run, 1 pass, 2 fail, 3 info) and a detail byte. A MAME script can read it once the
border is green or red.

## im2hold - BRIEFING C2 #38 (hardware IM2 mode holds interrupts)

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

Reading the results: tests 2, 5 and 6 passing = C2 #38's design works (hooks may run with
interrupts off; the game's handler is reached through a RETI trampoline or the game's own uniform
table). Test 4 says whether a game handler that ends EI;RET needs the trampoline at all.
