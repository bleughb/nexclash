# Ikari Warriors: pace and results (split from ikari_warriors.md, size budget)

## Pace (2026-11-08): the blit's window, a pattern store, K windows when in debt
Owner's pace rule: within 2% of the original where it runs steadily; never slower. Measured against the plain build, like
for like for the first time (below), 1.1 broke it both ways: quiet -0.9..-17.8%, busy +4.9..+25.9%, stretches of 20 updates
-36..+83% (6 seeds). The earlier "12-15% faster" numbers ran different games.
- Why, per update, in ms (JNext, seed 2): logic 16.5 = 16.3; figures 12.6 -> 36.6 (the hooks' 23.8); blit 25.9 -> 5.4; erases 4.2 -> 4.8. The
  game has no frame sync and DI in play, so the build's pace is its hook time less the blit's saving. A K1 image not in the
  cache cost 38 ms at 28 MHz: 287 of them in 600 updates, 12% of K1 plots, hook time 11 ms an update with none, 49 with one,
  90 with two; each other kind's 9 ms. The cache's 32 images (128 patterns: all of sprite RAM) give images up again and again.
- Pattern store (`find` -> `l2get`, `uend`): an image's 512 bytes are written to CAPT (page H) and copied to Next pages 32-47,
  16 a page, RAM only, directory L2DIR in page H, key = the cache's key, up to 255 images. A cache miss in the store: OTIR
  back into sprite RAM, about 0.4 ms instead of 38. Only the first sight of an image is computed. Pictures come from the
  same pattern bytes, checked by the same picture checks (new negative: the store gives back image 0).
- The no-outline builds (default and Enhanced) jump over the outline pass: it could only store 0 in a 0 (8 ms of a miss).
  uploadn.o0 in edge_patch / enhanced_patch; IkariPatch(colours={}), the classing build, keeps it.
- Limiter (lib/hlib_pace.asm, whole library, HLIB_V_PACE 0x8040): e_bl opens a window, the blit at 28 MHz, e_post commits and
  waits for T_BLIT (6130 sixteenths of a line: tuned on the meter; 25.9 ms less the hooks' own unmeasured parts) less the
  debt. Every plot hook and e_pre go to the debt (dbo / dbc, hlib_nest_*; dtk ticks in a long K1 image).
- When the debt is over 2 ms a burst is being repaid: e_lg (0xEB3B, new site) runs that update's logic at 28 MHz in a K window
  (K 128: 8 x 16) up to e_pre, and e_pre runs the figure phase the same way up to e_bl if still in debt. Budget per update:
  about 18 ms from the blit, 14 from logic, 11 from the figures; repaid inside the following updates. The AY calls in those
  two phases come at 28 MHz only in such updates; the game has no beeper in play and AY writes per second are unchanged.
- Pace, JNext, input keyed to updates, game state in lockstep at every one of the 600 updates, against the plain build,
  all / quiet third / busy third, then the fastest and slowest stretch of 20 updates:

| seed | 1.1 (2b9f431b) | this (8777f2c4) | Enhanced (4f3565ba) |
|---|---|---|---|
| 1 | -0.29 / -6.47 / +4.89 (-27.0, +41.3) | -0.26 / -0.37 / +1.04 (-10.5, +14.9) | -0.26 / -0.49 / +0.97 (-10.5, +15.1) |
| 2 | +6.82 / -17.76 / +25.88 (-36.0, +83.3) | -0.29 / -1.27 / +0.59 (-3.5, +4.3) | -0.20 / -1.26 / +0.77 (-3.5, +4.3) |
| 3 | -1.70 / -17.16 / +9.70 (-33.8, +33.1) | -0.62 / -0.79 / -0.46 (-4.7, +5.8) | -0.58 / -0.81 / -0.27 (-6.1, +6.8) |
| 4 | +12.17 / -0.93 / +23.59 (-18.5, +57.6) | -0.08 / -1.84 / +0.35 (-13.5, +15.7) | not run |
| 5 | +13.11 / -2.35 / +19.21 (-15.5, +64.4) | +0.64 / -0.51 / +1.81 (-3.5, +15.6) | not run |
| 6 | +3.72 / +0.21 / +9.17 (-27.3, +50.5) | -0.47 / -0.95 / -0.21 (-4.2, +4.2) | not run |

  What is left: the first sight of a new image still costs about 27 ms. A stretch with many of them runs up to +16% and
  the following stretch catches up (-13%). It happens once for each image in a session. Hardware untested.
- R: not compared (CMP as before). The whole snapshot holds no LD A,R or LD R,A (scan of all three banks), so no hook can
  change a value the game reads. Game memory and all other registers are compared as before.

## Speed restored (2026-11-07, refactor goal 2)
ENTER latches NR 7 (HLIB_SPEED_IN, V_SPD 0x8036) on the hook stack; LEAVE restores it (A via V_A). e_bl blits at
max(14 MHz, V_SPD); e_post, entered at the blit's speed, keeps e_bl's latch (ENTERB). The verifier answers NR reads;
O3_OUTLINE is the profile symbol uploadn.o3. Sprites c90fab6f -> 2b9f431b, Enhanced 118a55f6 -> 1bf270bf. 8 RZX x 2 sets IDENTICAL, negatives
all DETECTED, stamped. JNext pace vs the plain build: main -0.89%, this +0.09%.

## Results in today's tree (`selftest.py --game ikari_warriors --verify --stamp`, 2026-11-04, after the import)
Rebuild = recorded: plain 2d56c304, sprites e740ae71, Enhanced 22be808b (= the .nxc v1.0's default and Enhanced);
recolour guard OK. Verify, per recording, default and Enhanced each IDENTICAL through the colour-set checker:
ik_play1 4,829 frames / 1,446 commits, ik_cheat1 8,815 / 2,853, ik_bot2_1 16,879 / 6,286, ik_2p 6,877 / 2,004,
ik_2pw 7,841 / 2,517, ik_att 5,025 / 925, ik_gameover 12,612 / 1,134, ik_tank 11,986 / 3,817 (20,982 commits);
96,698 images checked; enemy faces checked in Enhanced 3,302. Negatives: colour sets 12/12 on ik_2pw, engine 7/7.
Stamped verified 2026-11-04.
