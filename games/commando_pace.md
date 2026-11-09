# Commando: pace (split from commando.md, size budget)

## Pace (2026-11-08, review 1.2): the logic at 28 MHz down to the frame sync
Owner's pace rule: within 2% of the original where it runs steadily; never slower. 1.1 broke it: whole +0.72 to +3.07%, slowest stretch of 20 updates +35.7% (audit, runs/pace-audit-20261108; the
published +0.38% had the player standing still, with keys the game does not read). Why: the update is 2 frames, set by bit 0 of IY+7 from the handler (0xDEAC), and takes 26 to 34 ms against 40: a plot
hook's time (1 to 2.5 ms, 17 ms in a burst of new images) comes after the first 14 ms of the update, so a burst runs it past the sync and it takes 3 frames.
- e_fa 0xDEB2 (past the sync): the update's logic runs at 28 MHz. e_fb 0xDF13 (the loop's end, before the sync): back. e_isr 0x7357 (the handler's first instruction): back first, so the handler plays the
  game's beeper sound at the game's clock; inside a hook (SP on the hook stack) the hook's own 28 MHz stands, as in 1.1. In practice the logic before the first interrupt, about 18 ms of it, is run 6.6 times as fast:
  credit of up to 15 ms, before the debt comes.
- No wait and no K. The game's own sync does the pacing, so nothing is tuned to JNext. hlib_pace is not used: the sync already gives back all the time, a limiter would only add its own.
- Sites in bank 5: 0x6100-0x61BF, code; never read or written by the game (the access scan above; area 1 only, like the hook RAM). The alt ROM is full: e_init moved to the fill block, spdi / spdo to the
  svr block, hlib_r_set / _add past the shapes (fill block from 0x3066).
- Game facts: the game writes the JP at 0xFCFC itself, at the entry (so a site there would not hold: found by the verifier); its logic clears R at 0x91AB every update and reads it at 12 sites.
- Pace, JNext, keys replayed into 0xFD85 at the player's plot, R fixed in both arms, 74 state addresses equal at every update, all 6 seeds of 714 to 800 updates, against the plain build (c51d7288):
  all / quiet third / busy third (fastest, slowest stretch of 20):

| seed | 1.1 (5362a84e) | this (cded9ba3) |
|---|---|---|
| 1 | +0.81 / +0.39 / -0.08 (-1.4, +19.6) | +0.01 / +0.07 / -0.00 (-0.3, +0.4) |
| 2 | +0.97 / +1.17 / +1.14 (-0.2, +8.0) | +0.01 / +0.10 / -0.05 (-0.2, +0.4) |
| 3 | +1.62 / +2.36 / +1.80 (-4.2, +29.6) | -0.00 / +0.22 / -0.15 (-1.0, +1.0) |
| 4 | +0.72 / +0.49 / +1.20 (-3.4, +8.0) | -0.00 / +0.06 / -0.02 (-0.2, +0.2) |
| 5 | +3.07 / +2.60 / +3.50 (-2.6, +35.7) | +0.00 / +0.07 / -0.03 (-0.2, +0.2) |
| 6 | +2.37 / +2.00 / +1.28 (-0.1, +25.2) | +0.00 / +0.09 / -0.04 (-0.2, +0.3) |

  Long events (a lost life, a tune) within a frame of the original's. Sound (beeper, played from the handler): seed 3, 500 updates, 2011 port 0xFE writes in both, none at 28 MHz, and the gaps between them
  match 1846 of 1864 by 50 T bins. Interrupts 50.00, longest gap as the original's.
- R: compared at every hook now (CMP includes 15, lib/hlib_r.asm unchanged, D_ constants counted; negative: R off by one). Not at the front end (the start stub: a key wait no recording runs).
  In play R is still not equal between arms: interrupts land at other instructions in logic at 28 MHz, as they did at other times in 1.1, so lockstep runs keep the audit's R fixture.
- Coverage: area 1 by random keys, in JNext; later areas are not measured. Hardware untested.


## Checks (2026-11-08)
- `selftest.py --game commando --verify --stamp`: Dean's snapshot, sprites ff488056 (no loading screen; was 6a547a86): commando.rzx IDENTICAL, 3,279 frames, 4,332 plots, R compared; unit 16,128 cases, negative 6/6; depth, restore, interrupt safety, cache, init, speed controls 2/2 (this recording's updates all meet an interrupt first, so the sync control has nothing to show here). Stamped.
- The published target, the clean release, by `auto` with the loading screen: cded9ba3 (plain c51d7288). walk1 + walk2 IDENTICAL, 24,002 frames, 22,176 plots converted, R compared; 32,256 position cases, negative 14/14; speed controls 3/3 on each; 172.9M hook instructions interrupt-safe.
- The start front end does not keep R; no recording runs it.
