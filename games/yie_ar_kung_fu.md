# Yie Ar Kung-Fu (Imagine 1985, 128K edition) - engine `yie_ar_kung_fu`

Techniques: `patch.xor-overlay-keep-ula`, `detect.gameplay-screen-readers`, `patch.scenery-edge-masks`, `patch.restore-speed`

## Next session
Stage: 3 (prove + deliver)    Branch: add-yie-ar-kung-fu (worktree wt-yie_ar_kung_fu, main merged 2026-11-26)
State: overlay rework done 2026-11-26 (the pilot's first cut kept the screens clean and broke the thrown-star hit
  test). Whole run PASSED: t1 6,002 + t2 12,002 + t3 15,004 frames IDENTICAL, every site reached, the same at the four
  CPU speeds, hide cases, negative controls. Record yie_ar_kung_fu, reference folder yie_ar_kung_fu/.
Owner decisions (Jon 2026-11-26): no white outline (none on any patch); Feedle's waiting clones hidden in the caves as
  the original; an Enhanced colour set from the arcade original's fighter colours (sheets for his approval first).
Next: Codex review, PR; then the arcade colour sheets (docs/COLOURS.md) and the Enhanced set; JNext pace check.

## Source
Pilot run NextTang-evidence/2026-11-02-nexclash/pilot/runs/yie_ar_kung_fu: `yie_ar_kung_fu.z80` (128K, 7FFD 0x17),
machine-played recordings rzx/t1-t3 (t3 reaches Feedle and the courtyard level). Cheats: the archive's
`Yie Ar Kung-Fu (1985)(Imagine Software).pok`, entries checked against this release's code (below).

## Design
Drawing in the original: two screens (bank 5, bank 7), one shown; 7FFD bit 3 flips at 0xB3FC once a tick. Fighters:
0xB423 restores old rectangles from the clean copy (0x5B00-, lines 64-191), then 0xB4EC / 0xB528 CALL 0xB5D8 plot each
object on the hidden screen (masked). Stars: OR plot on the shown screen (0xF56C). Chain: XOR plot on the shown screen
(0xEF36 / 0xEF73). Spark: 8 x 8 on the shown screen with one attribute cell (0xB8FC).
Overlay (patch.xor-overlay-keep-ula): every pixel store stays, so both screens hold exactly the original's bytes; the
thrown-star hit test 0xF622 (drawing-screen cell vs clean copy) and the random generator read what the original reads.
Sprites (4-bit, slots 0-63 fighters, 80-111 chain, 120-122 stars, 127 spark) cover every pixel the figure stores drew.
Only the spark's four attribute stores (0xB90B, 0xB914, 0xB91B, 0xB948) go: its coloured cell would clash; nothing
reads them back.
Bodies: the original shows a fighter's body (mask, no ink) in the paper under it; default colours give every body the
ground's paper (attribute of row 22, column 2: lawn cyan, courtyard yellow), written to the sprite palette at the flip
when it changes (asm ground_body). Ink black. No outline.
Feedle's caves: during his level the game ORs two black caves (rows at 41500 / 41741, 5 bytes drawn 6 apart, 40 lines
from line 144 at x 0 and x 216, then 6 solid lines) over everything each tick (0xB547-0xB5B7), so a waiting clone is
hidden in the black. Their ink goes on Layer 2 over the sprites (patch.scenery-edge-masks; NR 0x15 = 0x05 LSU, banks
30-32, transparent 0xE3 elsewhere, shown with port 0x123B so NR 0x69's 7FFD bit 3 alias is left alone): drawn at the
flip after 0xB547 noted them on the hidden screen, cleared on the wipes or when the flag (48575) drops.

## Hooks and memory
Stubs in alt ROM image 1 (0x386E-0x3B09); the rest in page H (26) at slot 7 while a hook runs; hook stack 0xFF00.
Store pages 28-59 (slot 6) hold converted frames; Layer 2 banks 30-32. Speed: hlib_speed (V_SPD latch), entered with
interrupts off, the caller's speed given back. Sites: 0xB4EC, 0xB528 (plot), 0xB3F9 (flip / commit), 0xF563 (star),
0xEF25 / 0xEFAB (chain, chain wipe), 0xB908 / 0xB91C (spark on, off), 0xAAAF / 0xAAE9 (the two wipes), 0xB547 (caves).

## Dependencies
Readers of figure pixels: the thrown-star hit test 0xF622-0xF646 (cell sums of the drawing screen and the clean copy)
and the random generator 0xB9AE (walks all memory). With every pixel store kept, both read the original's bytes; the
verifier compares the whole of RAM (both screens included) every 4 frames and registers at every hook exit. The
spark's attribute bytes differ while it is shown (counted exception); patch sites and stubs differ where the
generator reads them (the original's value stands, counted).

## Pacing
No frame sync beyond the game's HALT per tick (0xB3E2). Hook time over t3: 130.5M T at 28 MHz over 15,004 frames, about
1,090 T a frame at 3.5 MHz (1.5 % of a 128K frame). Spikes: the first conversion of a new frame of figure graphics
(cache miss) runs up to 856k T at 28 MHz (about 1.5 frames); 31 hooks over 280k T in t3. Not yet measured in JNext or on
hardware (verify.update-locked-pace is the next step).

## Verification (2026-11-26)
Lockstep replay of original and patched machines (hook instructions run free). Checked: registers at every hook
exit, the PC, SP, paging, the whole of RAM every 4 frames; the speed given back; at every 4th HALT and at the spark,
the shown screen equal to the original's and the sprite layer against it: a sprite ink pixel set in the original, a
body pixel clear, no figure pixel (one a figure store drew, track_figure_pixels) left uncovered; Layer 2 cave pixels
only where the original shows ink; every shown sprite's body in the ground's paper.
Counted exceptions, by design: figure pixels in a spark's cell the original has wiped (sprites keep the figure whole
until the game redraws that screen); game-drawn pixels off the clean copy that no figure store drew (the Feedle
arches' edges); outline exceptions (only with the optional ring, off by default).
Results: t1 6,002 frames, 7,146 hook returns, 460 layer checks; t2 12,002 / 5,016 / 322; t3 15,004 / 13,486 / 782,
688,576 cave pixels over the sprites. Speed matrix: entered at speeds 1, 2, 3, the first 1,500 frames IDENTICAL.
Hide cases (hooklib.hide_cases, four speeds, every sprite shown first): both wipes (and the caves cleared), spark
off, chain wipe: 64 cases. Negative controls, each caught by its own failure: speed not given back, HL/DE swapped, the
fighter plot sites left out, ink lost in the pattern tables, a wipe that leaves the sprites, spark off that leaves the
spark, the cave hook left out (t3 Feedle level), bodies kept cyan on every level.

## Cheats
Checked against this release (the archive's other entries are for other releases: 29587, 61482, 29974 hit unrelated
bytes here):
- Infinite energy: 44123 (0xAC5B) DEC (HL) -> NOP; (48587) counts the hits left in a life (reset to 8 at 0xAC7E).
- Infinite lives: 44170 (0xAC8A) DEC (HL) -> OR (HL); the lives counter at 48589+player, OR keeps the NZ branch.

## Lessons
- [local: a pilot first cut is not proof] Two recordings passed the layer check; the third reached a screen reader the
  design broke. Search every routine that reads the drawing screen (scan --writers readers) before building.
- [card patch.xor-overlay-keep-ula §Use / do not use] Keeping every pixel store made the hit test, the random generator and the RAM
  compare exact at once; the old design needed A/F exceptions in the figure spans and a screen exception in the RAM
  compare.
- [tool nexclash/yie_ar_kung_fu.py] "Off the clean copy" is not "a figure": the Feedle level draws scenery outside the
  clean copy. Tell figure pixels by the store that drew them (track_figure_pixels), not by difference.
- [local: spark hook] The pilot's spark hook switched the outline on after every spark whatever the build said: restore
  a flag a hook borrows, never set it to a constant.
- [local: palette selection] Hooks that write NR 0x41 rely on NR 0x43 as set-up leaves it: a set-up that selects
  another palette (Layer 2) must select the sprite palette again before it returns.
- [card patch.scenery-edge-masks §Use / do not use] Scenery the game ORs over figures each tick (Feedle's caves) goes on Layer 2 above the
  sprites, ink only, shown at the flip that shows the screen it was drawn on.
- [tool nexclash/yie_ar_kung_fu.py] Hide cases must restore only page H's run-time ranges from a captured state: copying
  the whole page put the good code back over a negative control's broken code.

## Technique use
- patch.xor-overlay-keep-ula: used: every pixel store kept, sprites over the figures.
- detect.gameplay-screen-readers: helped: found the star hit test and the generator reading the screens.
- patch.scenery-edge-masks: used: Feedle's caves on Layer 2 over the sprites.
- patch.restore-speed: used: hlib_speed in every stub.
- optimise.pattern-cache: used (pilot): converted frames cached per graphics address.

## Friction
- reuse: [none: the shared machine model refuses 128K] the survey could not run on this 128K game; toolkit gap, own PR.
- retries: [local: palette] three reruns for the cave rows' stride, the flip timing and the palette selection.
- environment: [local: none met] nothing in the environment slowed this round.
- hand-rolled: [local: verifier] the lockstep verifier stays per engine (Dean's decision).
- scratch: [local: one-off diagnostics] scratchpad run/diag/preview scripts dropped; the preview picture went to Jon for the cave question.

## Hardware checklist
No hardware or JNext run yet. On a Next: start, both levels' bodies in the ground's colour, Feedle's clones hidden in
the caves until they step out, thrown stars hitting, the chain, the spark, a wipe between rounds, speed F8 kept, cheats.

## Stage log
- 2026-11-21: ported from the pilot (first cut); blocker: the star hit test reads the screen.
- 2026-11-26: overlay rework, no outline, ground-colour bodies, Feedle caves on Layer 2, hlib_speed, units and
  negatives to the engine template; whole run PASSED on three recordings.
