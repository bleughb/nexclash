# Heartbroken (Atlantis Software, 1989, 48K)

## Next session

Stage 1, engine feasibility. Branch `add-heartbroken` at `e759250f9b9cefa084dae213ea4c6e4fd4c9a1ea`. The owner has settled the display and trainer choices. Two display experiments failed the original depth rule. Review the counterexamples below before implementing hooks.
Inputs are in `reference-local/heartbroken/`. Pair `heartbroken.rzx` with `heartbroken.z80` and `contact.rzx` with `contact-start.z80`. The private evidence directory is `2026-11-02-nexclash/pilot/runs/heartbroken/to-test/`.
Start by replaying `draw_probe.py` and `backing_probe.py` there on the archive recording, using the toolkit checkout on PYTHONPATH. The two probes take the recording path. Compare frames 3014, 23584 and 23777. The first feasible build needs a model of exactly which pixels belong to each figure in both the displayed and saved screens.

## Inputs and start

- Original target `Heartbroken (1989)(Atlantis Software).tap`, 54,856 bytes, MD5 `7d3b5f6c8fefaa84eba29cfb6b1cc2b5`. All 10 TAP block checksums pass. `heartpic` supplies 6,912 bytes at file offset 383, MD5 `99169ef4e624a5fc13a890bce794e88a`. Use that offset for `build_screen`.
- The archive RZX has one start, 24,894 frames and zero desyncs. MD5 `f211b806481ce52d8acc31d99ea8fb2c`. Its embedded Z80 is 49,216 bytes, MD5 `eabd89a2fd007bccfd3dddb7aecf558b`. PC $0038, SP $61CC, IM 1, return $FE4E.
- The loader writes `heartmain` to $61E8, then overlays its first 6,912 bytes with `heartplus`. Of the 40,472 resulting bytes, 40,459 match the recording's start. Independently loading the TAP to $FE4E brings this to 40,467. The five differences are at $A478, $A47A, $EB15, $EB17 and $EB19. Both archive trainer sites and the extra firebolt site match the tape.
- The toolkit's standard TAP1 table uses 52 copies and 795 residual bytes across 41 sites. One site contains the 12-byte copier that BASIC assembled at $5B00. The private tape probe takes those 12 bytes individually from the actual BASIC DATA literals. The revised table has 64 copies, 40 sites, 783 residual bytes and a length of 1,686 bytes. TAP1 decoding and all 49,152 RAM bytes match the archive start. This is a tested table recipe. Integration into a release patch is pending.
- The supplied Stage 0 survey reports 15,001 frames, 14,244 accepted interrupts and a passing caller gate. The stack reached $61A4. The plain build also boots with its 79-byte tail at $5F00 through $5F4E and the printer buffer restored. With the supplied Next ROM, both normal and NEXLOAD boot checks returned zero differences. Whole-game tail safety remains open.

## Decisions

The default build must use hardware sprites for the player, enemies, projectiles, effects and pickups drawn as figures. Preserve the game's colours, black drawing lines, original overlap order, timing and screen reads. The scope excludes a white outline and Enhanced colours. Start with DivMMC automap off, clear all 128 sprite records, and leave the trainers off by default. Keep scenery, HUD and text on the ULA. No compromise to depth or update rate has been approved.

## Feasibility

$F8DD dispatches through HL. The masked figure renderer is $E700. It assembles the image and mask at $5B00, shifts them horizontally, reads a saved background byte, then writes the result to the live ULA. The two forms are 24 rows of four destination bytes and eight rows of two bytes. Their masks start 96 and 16 bytes after the corresponding image. A scan of a 400-frame gameplay slice found all 192 scratch bytes written before their first read. $E706 clears the scratch area, $E717 populates it and $E740 shifts it.

| Original archive check | Measured result |
|---|---:|
| Masked draws entered and returned | 9,333 each |
| Large / small form | 8,367 / 966 |
| Immediate callers $CCCB / $C71A / $C5D6 / $C86E | 8,277 / 966 / 60 / 30 |
| Destination bytes predicted from the mask, image and saved background | 818,688 of 818,688 |
| Distinct masked source addresses, including the blank at $FF58 | 24 |
| ROM firebolt prints traced through $CC33 | 773 prints, 6,184 rows |
| Full playfield saves / restores | 128 / 5 |

1. **One whole sprite per draw.** A later rectangle writes saved scenery even through transparent pixels. The full-replay probe found 388 partial overwrites of earlier masks, even discarding its history on other bitmap writers. At frame 3014 the firebolt eraser covers 40 of the 472 previously visible mask pixels of the figure from $8AB0. Keeping the whole figure shows the extra 40. Hiding it drops the other 432. See `draw-proof.json` and `partial-erase.png`.
2. **Clip earlier figures at each later rectangle and treat saved pixels as scenery.** The save at frame 23584 takes 408 masked figure pixels with it, following the one draw from the $E2E0 caller. Three later blits restore 387 figure bits in total through their transparent areas. The first is at frame 23777, destination $4827. That count includes repeated restores. The ROM firebolt uses the normal character printer, separately from $E700. See `backing-proof.json`.

The supplementary death recording independently reproduces both failures. Its 950 frames contain 605 completed comparable plots (58,080 destination bytes, zero mismatches) and 17 partial overwrites. All three saves captured figure bits. A total of 173 later plots restored 1,802 bits. The first save was at frame 382, and the first such plot followed at frame 384. A 606th plot entry is at the recording boundary, without a complete plot comparison.

**Missing implementation.** A renderer needs to retain figure identity and colour for both the live pixels and their saved copies at $9500. It must implement partial erases, restore surviving pixels in order and include figures drawn by the ROM printer. Classify the remaining printed pickups separately from scenery and HUD. The next host experiment must reproduce the two counterexamples and check ownership after each draw, save and restore across both recordings. Then measure a whole assembled update, including worst-case uploads, interrupts, freshness and sound.

**Timing.** In frames 3000 through 3399, 101 intervals between player draws at $C682 took 147,459 to 2,156,800 uncontended T-states, median 191,666. The idle probe found zero HALT or self-jump idle T-states. It also saw 4,050 even-port writes at $E806, 180 at $FF01 and 120 at ROM $03E1. That sample supplies no safe wait budget. A separate early probe at $AA36 measured only three long intervals and is unsuitable for measuring player draw cadence. DMA could upload prepared patterns. Neither ordinary DMA nor DDMA performs the mask and saved-owner calculation. CPU and core-gated DDMA costs remain unmeasured.

## Cheats

The game's archive POK file has two entries. The separate `heartbroken-checked.pok` records expected original bytes for all three candidates. Its MD5 is `a8ab6b29593c5079bd0cfd6620ad8a13`.

| Trainer | Code check | Result in play |
|---|---|---|
| Infinite lives | $D46D changes a store to a load of the lives word at $E64E. | Contact normally took 3 lives to 2. With infinite lives it stayed at 3 and play resumed. |
| Immunity | $CC9C returns from a successful contact test before the death handler. | Contact returned to the caller, lives stayed at 3 and player drawing resumed. Coverage is this damage path. |
| One-hit firebolt | At $C430 the four-byte subtraction becomes a load of signed stamina −1 followed by a NOP. The original store, threshold and defeat animation still run. | The same shot normally took stamina from 1 to 0 and the enemy survived. With the trainer it reached −1, played the defeat effect and returned to player drawing. |

All eight on/off combinations were tested from **before** contact and **before** the shot, 16 encounters in total, in the unconverted game with normal interrupts. Both scenarios used released keys after archive frames 4800 and 6050 respectively. The original recording reaches neither archive trainer site. The 950-frame supplementary recording replays without desync and reaches contact once, the death animation loop three times and the lives store once. Its MD5 is `3770ffc116a7d2a5a63e04277e2036cc`. Its own start's MD5 is `5f07db198d052f30a94915e96872125d`. No trainer was dropped. The firebolt trainer was derived here. Publication history is unknown. Loader application and patched-play tests are pending.

## Hardware checklist

For a future release build, check that selecting the original TAP displays its loading picture, the game starts with clean sprite slots, and the all-off run keeps its original pace and sound. Check the firebolt crossing an enemy, the death effect, pickups, room changes and the rescue scene. Look for missing black lines, stale pieces and visible sprite updates. Try the three trainers separately and together. No sprite build, loader-menu capture, hardware run or verification stamp exists for this stage.

## Lessons

- [local: compiled USR dispatch] The $F8DD call count combines unrelated operations. Reconstructing the $E700 output predicted all 818,688 destination bytes.
- [local: rescue-scene save order] An empty $FF58 firebolt-erasure mask restores a whole rectangle. A saved screen can also contain the rescue figure.
- [local: Atlantis tape loader] The cassette stores the printer-buffer copier in BASIC DATA. Twelve tape-copy entries reproduce the machine instructions.
- [local: archive walkthrough route] The successful archive walkthrough misses both trainer sites. Releasing the keys after frame 4800 reaches a natural death.

## Technique use

- detect.buffer-layout-producer: used
- detect.tracked-unit: used
- detect.pacing-structure: used
- detect.routine-removal: helped
- patch.scratch-redirect: no help: the destination is the live ULA and the saved buffer can itself contain figures
- tools/probes/rzx_census.py: used
- tools/probes/pacing_census.py: used

## Friction

- reuse: [local: self-modified plot dimensions] The two geometry modes and BASIC literal positions are specific to this release.
- retries: [local: title precedes the plotter] Replaying a slice that begins during play exposed all 192 scratch bytes. The first 2,001 frames touched only two.
- environment: [none: the supplied interpreter, ROM and inputs worked]
- hand-rolled: [local: renderer-specific save and erase order] Per-pixel ownership probes identify the exact erase and restore cases for a design review.
- scratch: [local: the counterexamples use this game’s code] Retain the game-specific probes and their JSON results with the private pilot evidence.

## Stage log

2026-11-28. Intake confirmed and Stage 1 feasibility investigated, one session, about 10 minutes of machine wall time, roughly 60 tool calls, no user rounds. The maintainer owns Git writes. The review point is the pair of failed depth experiments above.
