# Midnight Resistance: pace (split from midnight_resistance.md, size budget)

## Pace (2026-11-08): the game has a frame sync; limiter on the screen copy and before the sync
Owner's pace rule: within 2% of the original where it runs steadily; never slower. Measured against the plain build, in
lockstep for the first time (below), 1.1: all -4.26..+1.44%, quiet -9.28..+1.13%, busy -1.07..+5.84%, stretches of 20
updates -18..+14%. The numbers of 2026-11-07 ran different games but had the right sign.
- CORRECTED: this file and the notes said no frame sync. There is one: 0x8A03 CALL 0x831E clears R (LD R,A) and plays a tone
  (OUT 0xFE at 0x833A / 0x8344) until R's bit 7 sets. Only the ISR sets it (LD A,255 / LD R,A at 0x7FDE). So every update starts at
  an interrupt and takes a whole number of frames, nearly always 4 to 8. The tone is the game's sound, and it plays only in
  the wait: arrive early and it lasts longer, arrive late and the frame is lost.
- Why, per update, in ms (seed 2): scenery 41.6 -> 39.4; figures 10.1 -> 6.6 (their loops run at 28 MHz); screen copy 26.0 unchanged; logic
  after it 4.3; commit 0.1 -> 6.3, up to 45. The arrival averages out, so whole frames are won in quiet scenes (4 frames, not
  5) and lost in busy ones.
- Limiter (lib/hlib_pace.asm, whole library, HLIB_V_PACE 0xB0E0 in page 26). All sites new but the plots and the commit:
  - e_bw (0x8A60 JP 0x8730): window open, the screen copy at 28 MHz (3 ms). Only called from the game loop: the return address
    must be 0x8944; the shop's call (0xB88A) stays as it was.
  - e_hd (0x8944): the copy is over: hold the window, the caller's speed for the game's routines up to the commit.
  - commit: resume, tick per figure (a commit can pass a frame), then wait for T_BLIT less the debt, at the caller's speed so the
    ISR runs at its own clock. So a commit up to about 23 ms costs nothing.
  - c_go: the plot hook's time goes to the debt (hlib_nest_*), and each converted plot's saving to V_CRED (W x R at the kind's rate).
  - e_tw (0x8A03): pays V_CRED less the debt, so the update reaches the sync when the original's does.
  - e_bg (0x8941) / e_bk (0x89C3): a commit overran and left a debt over 1 ms: the scenery work runs at 28 MHz in a K window (K 133)
    and repays it before the sync. About 36 ms a game frame when needed. Plots inside it take no credit.
- Tuned on the meter: T_BLIT 6005 sixteenths of a line, credit rates 72 / 72 / 93 / 110 per 256 of a line a byte, K 133. Whole
  frames make the meter steep near zero: T_BLIT 5880 gives about -1%, 6095 gives +0.6%.
- Pace, JNext, Kempston, input applied after the game's read (0x82CD), probe 0x8730 (0x8950 can run twice in an update: use the
  screen copy), game state in lockstep at every one of the 600 updates, against the plain build, all / quiet third / busy
  third, then the fastest and slowest stretch of 20 updates:

| seed | 1.1 (947dc8a9) | this (081de91a) |
|---|---|---|
| 1 | -4.26 / -9.16 / -1.07 (-18.3, +9.1) | -0.07 / +0.73 / -0.70 (-2.9, +3.3) |
| 2 | -0.72 / -7.06 / +3.92 (-12.2, +12.8) | -0.10 / +0.43 / +0.01 (-4.4, +5.8) |
| 3 | -2.19 / -9.28 / +0.28 (-15.9, +5.9) | +0.35 / +0.10 / +0.55 (-1.1, +7.1) |
| 4 | -0.19 / -7.48 / +5.84 (-12.7, +13.9) | -0.81 / -1.59 / -0.00 (-5.4, +2.5) |
| 5 | -1.83 / -7.11 / +2.01 (-17.1, +8.0) | +0.13 / -0.40 / +0.95 (-3.2, +4.2) |
| 6 | +1.44 / +1.13 / +4.01 (-7.1, +14.1) | +0.23 / +0.23 / +0.80 (-2.1, +4.0) |

  What is left: arrival at the sync is within about +-3 ms of the original's (q10 / q90). Where the original itself is that close to a
  frame boundary the build can take a frame more or less (20 ms in about 100), so a stretch of 20 updates reads up to +7%.
  AY writes a second equal, longest interrupt gap equal (20.3 ms), port 0xFE writes within about 8% either way in the tone. Hardware
  untested. Interrupts: the ISR runs at 28 MHz during the copy and the scenery in a debt, as it already did in the plot loops.
- R: not compared (CMP as before; a converted plot's loop exits add an M1 per line, so R would need counting per plot). The game's
  reads: 0x782D-0x783B the RNG seed, under DI straight after LD R,A with no hook between; 0x833D-0x836B in the sync's tone, the
  sign only (bit 7, which no hook writes); bank 7 0x0D15 in the ISR, sound only, and that value depends on where each interrupt
  lands in the original too. So no hook can change a value game logic reads. JNext shows it: game state equal at every update.
