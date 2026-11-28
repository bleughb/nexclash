# Yie Ar Kung-Fu (Imagine 1985, 128K edition) - engine `yie_ar_kung_fu`

Techniques: `patch.xor-overlay-keep-ula`, `detect.gameplay-screen-readers`, `patch.scenery-edge-masks`, `patch.restore-speed`

## Next session
The owner test copy is ready for the Spectrum Next. Start with the ordinary colours, then select Enhanced in the patch menu. The owner reviews the sheet, checks the pace and watches the caves on hardware. See [Owner test copy](#owner-test-copy).

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
thrown-star hit test 0xF622 (drawing-screen cell vs clean copy) reads the original screen. The random generator also reads the modified code and spare ROM. Its hook restores those sampled values.
Sprites (4-bit, slots 0-63 fighters, 80-111 chain, 120-122 stars, 127 spark) cover every pixel the figure stores drew.
Only the spark's four attribute stores (0xB90B, 0xB914, 0xB91B, 0xB948) go: its coloured cell would clash; nothing
reads them back.
Bodies: the original shows a fighter's body (mask, no ink) in the paper under it; default colours give every body the
ground's paper (attribute of row 22, column 2: lawn cyan, courtyard yellow), written to the sprite palette at the flip
when it changes (asm ground_body). Ink black. No outline.
Feedle's caves: during his level the game ORs two black caves (rows at 41500 / 41741, 5 bytes drawn 6 apart, 38 patterned lines
from line 144 at x 0 and x 216, then 6 solid lines) over everything each tick (0xB547-0xB5B7), so a waiting clone is
hidden in the black. Their ink goes on Layer 2 over the sprites (patch.scenery-edge-masks; NR 0x15 = 0x05 LSU, banks
30-32, transparent 0xE3 elsewhere, shown with port 0x123B so NR 0x69's 7FFD bit 3 alias is left alone): drawn at the
flip after 0xB547 noted them on the hidden screen, cleared on the wipes or when the flag (48575) drops.

## Hooks and memory
The alternate ROM stubs occupy 0x386E through 0x3BE5. The boot register block follows. Page 26 holds the hook code and a private stack at 0xFF00. Pages 28 through 59 cache patterns. Page 27 stages painted bytes. Layer 2 uses banks 30 through 32. Enhanced stores per-fighter paint in banks 33 through 45. The cache distinguishes a fighter as well as a graphics frame. This matters when an opponent overlay reuses an address and when Blues borrows Oolong's resident graphics.

The 12 displaced instructions and their original bytes are listed in `nexclash/yie_ar_kung_fu.py` under `SITES`. The graphics hooks save the caller's CPU speed and use the private stack. The RNG hook stays at the caller's clock and preserves the selected NextReg when it inspects the top bank.

## Dependencies

The thrown-star hit test at 0xF622 reads the drawing screen and its clean copy. All bitmap stores still run. The RNG at 0xB9AE can sample patched opcodes and the spare area of the 48K ROM. The stub at 0xB9B3 supplies their original bytes before the game uses A. It distinguishes bank 7 from other banks at the same address. Differential replay counts differing raw samples and leaves both machines to compute their own results. Each displaced opcode uses its recorded fetch. All recorded port reads must be consumed.

The screen check derives Feedle's two cave masks from the original game's graphics and draw path. It compares the entire 49,152-byte Layer 2 image. A flash landing inside a cave opens its cell on Layer 2 until the game flips to a newly drawn cave. The RAM comparison allows the single live spark attribute offset, installed patch bytes and spent hook stack bytes. Both screen bitmaps are checked.

## Pacing

The game's HALT is at 0xB3E2. The earlier default build measured about 1.5 percent of a 128K frame on average in the simulator. That estimate predates the RNG stub, corrected fetch accounting and Enhanced artwork. In the Enhanced t3 replay, 281 hooks exceeded 280,000 T. The longest took 1,993,258 T, about 71 ms at 28 MHz. Real-time pacing and first-use pauses still need an owner comparison against the original at the same CPU speed.

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
The two enabled-by-choice trainers both start off.

- Infinite energy replaces DEC (HL) at 44123 with NOP. It holds the hit counter at 48587. The round code resets it to eight.
- Infinite lives replaces DEC (HL) at 44170 with OR (HL). A holds eight. The current player's byte at 48589 plus the player index stays intact and the continue branch sees NZ.
- The archive's 29483, 29587, 29974 and 29633 hit reloadable opponent data in this edition. The entries at 61482 and 61461 change the target of a CALL and a conditional JP. The extra-life entry at 44732 disables a real award and also writes into a banked overlay. The test copy omits all seven.

## Owner test copy

Version 1.0 supports the 88,055-byte 128K snapshot with MD5 `954472db58451ab0183075154cd70169`. The toolkit packages the bank 7 loading screen, default ground-colour bodies and an optional arcade painting. The painting covers 105 poses across Oolong and all eleven opponents. The owner can return an edited PNG using the supplied layout. The game-specific colour map is `docs/profiles/yie_ar_kung_fu_enhanced_colours.json`.

All eight combinations of colours, energy and lives produced their expected NEX bytes. All eight reached the Buchu fight from the OverSpec patch menu. Direct play-code checks covered 16 damage cases and 32 life-loss cases. Emulated sprite conversion matched 63,177 opaque and 82,007 transparent pixels on the sheet. All 39,225 original ink pixels remained black. An unchanged sheet re-import reproduced the Enhanced NEX. The Enhanced t3 replay matched 1,144,576 uploaded fighter bytes against the sheet across 70 poses. Its 685 display checks covered 187,392 cave pixels.

Default replay of t1, t2 and t3 matched for 33,008 frames, 75,083 hook returns and 8,253 RAM comparisons. The 2,076 display checks compared 2,533,093 sprite pixels. All twelve hook sites ran. The original star hit test ran 260 times. The RNG hook handled 1,788 differing raw samples out of 42,234 reads.

## Lessons
- [local: a pilot first cut is not proof] Two recordings passed the layer check; the third reached a screen reader the
  design broke. Search every routine that reads the drawing screen (scan --writers readers) before building.
- [card patch.xor-overlay-keep-ula §Use / do not use] Keeping every pixel store preserved the hit test and the two screen bitmaps; the old design needed A/F exceptions in the figure spans and a screen exception in the RAM
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
- 2026-11-28: corrected RNG sampling, recorded fetch accounting and cave clearing. Added Enhanced painting, trainers, the loading screen and an OverSpec owner test copy.
