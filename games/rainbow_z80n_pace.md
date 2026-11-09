# Rainbow Islands (rainbow_z80n): pace (split from rainbow_z80n.md, size budget)

## Pace (2026-11-08): the redraw after a lost life
Owner's pace rule: within 2% of the original where it runs steadily; never slower. Audit of the published 1.1 (33639cab, JNext, state in lockstep): play exact or faster, but after a lost life the
ROUND READY redraw took 124 frames against the original's 58, about 1.3 s more each time; whole up to +6.20, busy up to +16.53, slowest stretch +57.9.
- Why: only the game frame in the interrupt sets 28 MHz. This redraw runs in the main loop, interrupts off, about 5,500 cell hook calls at 3.5 MHz.
- 28 MHz in the cell hooks alone was not enough: 94 frames against 61 in the sampled stretch (JNext: the JP through the alt ROM, the entry and exit at 3.5 MHz, 24 frames' worth; the work at 28 MHz, 12).
- Fix: outside a game frame (V_LON = 0) cin latches the speed and the hook works at 28 MHz; cout leaves the game's own cell code at 7 MHz (RD_SPD), or the caller's speed if faster, until
  lexit's NEXTREG 7,0 at the end of the next game frame. The cell's own bytes reach the same buffer; only time changes. That alone reads 81 ms quick, so cout waits RD_DLY (20 x 16 T at
  28 MHz) per cell, about 3.2 ms a unit over the redraw. Result 57 to 58 frames, on JNext; the update then starts at the next interrupt, so it moves in 20 ms steps.
- Inside a game frame only the flag is read: 2 x 24 T a cell at 28 MHz. Quiet stays +0.00, the fast stretches are the same.
- A per-cell delay, not one cell in N at 3.5 MHz: N = 10 read +20 to +40 ms, N = 16 read +120 to +140 ms, because the speed left at the last cell also runs the game's long non-cell stretches: it is chaotic.
- Fast stretches, -9.1 at most: all of the gain is on updates where the original runs over its base pace, 81 ms against 60.8; the build stays at the base. Legal under the rule. Same figures as 1.1.
- cin / cout at the alt ROM block's tail: asm lsamp stays at 0x3B00, as rainbow_dma's pinned check wants. CODE3 and the main block were full; ocpre / ocpost moved to CODE3.
- R: not compared at any hook (CMP as before). The game reads R at round set-up (0x6385) and hooks change the instruction count, as in 1.0 and 1.1, so the same keys give another set-up than the original;
  the pace runs fix it at that site in both arms. No shared library change: hlib_speed.asm's macro as it stands. No hlib_pace: the engine has its own limiter.
