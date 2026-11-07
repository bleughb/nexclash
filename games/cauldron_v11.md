# Cauldron v1.1 (opt-in rework of cauldron; moved from games/cauldron.md, its size budget)

## Rework (opt-in) v11 (engine `cauldron_v11`; Jon Attree, 2026-11-05)
Dean's build stays the default. "Bats clash with the trees" = the Q4 rule: a type 0 image took a scenery cell's ink
(cave bats, v 5, red by trunks). v11: type 0 -> v (`ink`), unit cases + Dean's rule as a negative. Speed pass: image
cache built offline (pages 36-43, commonest ink, OUTINB; XLT for other inks; off with a colour map), every hook at 28
MHz restoring the caller's speed (latches), a limiter on the attribute hooks (JNext's original durations). sprites
b25577e4: RZX 89,596 frames IDENTICAL, 90 cases, 22 negatives, clock matrix 68 cases PASS; pace -1.4 to -1.7 % (the
body copy runs from uncontended RAM); 23 one-frame flicker transients in 900 frames (none in the original's): open.

Round 2 (2026-11-05, sprites 08ddd639; pilot runs/dean_cauldron work/r2):
- Cause (JNext headless, one PNG per video frame, every plot entry / show / erase hide logged with FRAME and CVC,
  work/r2/blinkrun.py + cause.py): an erase hid its sprite at its end and the next draw showed the new one at its start;
  in between neither the sprite nor the ULA figure (XOR-erased) was there. All 23 transients of b25577e4 in frames
  600-1499 fall on a frame whose beam crossed a hidden sprite's rows in such a gap (14 all rows, 9 some), 0 at other
  frame offsets. The original has the same gap, at a beam phase that its slower, contended plotter keeps off the figure.
- Fix (asm, page 26: padd / pmark / commit / bwait / phide / pfree / ptouch / pall): an erase moves its slot to a
  pending list (sprite still shown over the erased ULA figure). A draw marks the pending entries whose rectangle meets
  its own, or that have already seen a draw elsewhere, and its commit hides them and shows its own sprite in one burst
  (under 3 lines at 28 MHz) once the beam (NR 0x1E / 0x1F) is off all their rows (6 above, 2 below); then their slots
  go to the free stack in pending order. A screen writer over a pending sprite, a taint of everything, or a draw that
  finds no free slot hides it at once. Game memory and the ULA at every hook exit are as before (IDENTICAL).
- Model: Model.pend / _mark / _commit, table bytes V_NP / PEND, a model beam (4 lines a read) and beam_check: every
  sprite attribute write of a plot hook with the beam off the rows of the image its slot shows or stops showing.
- Pace: hlib_pace (asm/lib) around the plot hook: popen at the entry, target = rows x PT[width, shifted, type 2]
  (JNext on the unpatched game, 10,762 plots: work/r2/pfit2.py) x 0.95; pwait at the exit at the caller's speed.
- Results: RZX 89,596 frames IDENTICAL; 105 unit cases (15 new: pending, commit, beam), 24 negatives (new: the hide at
  the erase's end, a commit without the beam wait; "erase never hides" now the commit leaving them shown); clock matrix
  68 PASS, forced 3.5 MHz exit detected; ROM paths pass. JNext flicker 900 frames: 0 one-frame transients, 0 vanished,
  0 out of step, 1.20 picture changes a game update (was 1.40; original 1.72). Pace (10 trials each, main loop 0x809D):
  quiet -0.45 %, busy +0.47 % (-0.16 to +0.77), sound +0.49 % (-0.15 to +0.93). 15-minute soak clean.
- Open: 3 of 30 trials warn "interrupts held off longer than the original (59.9 ms against 39.9)", as the speed pass
  did (2 of 30). A pending sprite stays up to the next draw (usually under a line; after a death or a HALT pause until
  the next plot or writer); not seen in the flicker or soak captures.

