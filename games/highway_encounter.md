# Highway Encounter (Vortex, 1985)

## Next session

Release candidate verified on the normal DMA path; packaging handoff is in the run folder.
Frozen implementation 1809904 on main dace0cc. Full 22306-frame verification per mode,
all five exact NEX rebuilds, full hidden ROM and six actual-loader modes pass. No hardware test.
CPU-only fallback is functionally checked but fails transition pace: 303.568..308.507ms
versus 261.095..263.915ms original. Keep this limitation in any release notes; do not claim
unqualified original pace on old cores or hardware-IM2 configurations.

The normal-DMA transition penalty is resolved in
measured trials: four Enhanced transitions 256.868..261.808ms versus 261.095..263.915ms
original. All 301 tracked states agree for each of three seeds in both modes. Enhanced
quiet -0.410..+0.144%, busy -0.463..-0.081%, worst 20 +0.589%; default quiet
-0.698..+0.294%, busy -0.683..+0.142%, worst 20 +0.441%. These are measured tolerances,
not a claim of zero overhead at every individual update.

The 95EF..9765 and 976D..981F memory-only scene loops use measured fixed original-cycle
budgets 375864T and 247097T;68 original states across zones 1..31 have identical counts.
Nested colour work is included once in those windows. The 576-byte attribute copy uses
an 8-pixel lookup in unused page 45 space, preserving identical source bytes and colours.
Original sound/logic/delays remain at their incoming speed. Default and Enhanced use
shared hlib_pace and speed restore; no per-frame tune to disguise a scene overrun.

Next: packaging review, preserving the fallback limitation; then owner playtest.
Editable import, standard auto/verify/unit record, trainers, loading screen and exact
NXC loader acceptance are complete. The full frozen verification log and native pace,
sound, lifecycle, package and private-card evidence are retained outside this source repo.

## Status

2026-11-10: normal-DMA release candidate complete for packaging review. CPU-only
fallback timing remains a known limitation. No push, shared-card write or hardware test.

## Inputs

- Archive `Highway Encounter (1985)(Vortex).z80`, MD5 `ecfe7da10ba9aa395ae54c44301be1af`,
  41,836 bytes. Actual 48K, IM1, I=3F; no AY release was found in the specified archive folder.
- Colour source MD5 `f2fb116ed79269c2412f210edc45675f`; associated SNA MD5
  `4f8e72e3445462ac6090b416f3e24ded`. Credit: **Enhanced colours: MatGubbins (Spec256)**.
  The menu label is Enhanced, off by default. Colour source and all game data remain private.
- Original loading screen, MD5 `be406c30814d5149a1b9053be25a8d58`, retained from the archive.
- Painter's `highway.txt` read. Its logo/sea/beach attribute edits are not applied to game code.
  All 8,208 moving-graphic bytes, 2,048 scenery bytes, 1,440 ship bytes, 215 font bytes and
  1,024 HUD bytes match the original release exactly. Map colour planes to those originals.

## Observed engine

- Initial PC1F3E is the ROM's BASIC PAUSE. Enter continues the final USR F260: DI, SP=0,
  copy F160..F25F to 5B00..5BFF, LD R,F9, then JP B0E0. B0E0 runs the original opening sound
  and title sequence. B1E0 is reached later; it is not the loader's first game instruction.
- Gameplay leaves interrupts disabled and uses beeper loops at 9AEF..9B71. The survey's 30
  ROM interrupts occurred before that gameplay phase; do not infer a 50 Hz game interrupt.
- 9822 restores old figure regions from background; 985A sorts and draws current objects;
  9A9B copies dirty eight-row cells to the ULA. Original buffer D900..FCFF is game data.
- Four 24-row mask/OR plotters: 9933 (+2 pixel shift), 99D1 (-4, two output bytes),
  9A26 (-2), 9A70 (unshifted). Source rows contain three mask bytes then three ink bytes,
  bottom first. DE is source, BC destination at entry. No additional outline is drawn.
- 7A00..7AFF has 128 pointer entries, 56 unique figures. B8F0..D8FF contains 57 complete
  144-byte records; the additional opening/title figure is included in the editable sheet.
- Scenery writes: 960B/9610/9641/964D/96BF/9734 plus their copies and border writes.
  The original display uses per-cell colours, including green vegetation and blue water.
- A11B is the controlled Vorton's command handler, also called during the starting procession.
  Pace probe 9C7F is the active Vorton's movement update, just after IX=(8F01), gated on caller
  return 916C. The procession also calls this routine, so the caller gate is necessary. Later
  objects loop through 9CCD; this probe counts the player's own regular update once.
- After B1E0, the 2,000-frame scan touches 5C76/77 (random seed) in 5B00..5E5F. This is scoped
  evidence, not permission to overwrite the archive loader or unvisited data.

## Design and staged evidence

Earlier development measurements below are historical; the Next session block and
Release integration section are the current result.

Keep the original ordered mask/OR composition and all game RAM for logic. A colour mirror of
the original buffers can preserve depth and exact clipping; a foreground-only sprite overlay
would put hidden objects in front. Default must retain the original look without overstating
clash removal in the mostly monochrome road. Enhanced uses only the supplied colour planes.
The owner authorised continued overnight work with comparison sheets retained for review.

The private design model reconstructs all 286 commits in the first 1,400-frame walk and all
1,379 commits in the 7,446-frame demo with zero playfield bitmap differences. The demo spans
all 30 zones but uses its own loop, so it does not prove normal gameplay collisions. A one-pixel
shift mutation gives 140/140 incorrect commits in the first 850 frames. The ending changes
INK to PAPER without erasing the old road bitmap: the colour preview respects this visibility.

The default prototype restores every register including R and all 48K RAM at B0E0, both with
and without NEXLOAD. Both complete hidden ROM images match. A 2,000-frame walk passes 1,056
hook comparisons, 528 balanced drawing windows and 51,904,512 compared RAM bytes. Another
128 entry cases cover all four incoming speeds, both IFF values and eight R boundaries.
Wrong R, wrong MMU and forced-3.5-MHz-exit mutations are all caught. No added DI/EI is used;
the original game is already DI. These are staged checks, not the frozen release verification.

Paired JNext trials start from the same original gameplay checkpoint: three seeds, 300 player
updates each, no state differences. With K=104 and 176 sixteenths of a line of fixed wrapper
debt, overall penalty is -0.50/-1.08/-0.59%, quiet -0.24/-1.08/-0.27%, busy -0.86/-0.93/-1.04%.
The slowest 20-update windows are -0.13/-0.66/-0.20%; none is slower. Positive means slower.
This is the default drawing-window prototype, before adding Enhanced work. Sound code and
the original adaptive delay remain at their original clock and are not rewritten.

Enhanced development now includes 43 colour hooks plus the two default pacing hooks.
All 49,152 logical addresses and 288 copies were checked; 684 frame/shift/position cases
match the independent mask/colour model. Wrong cached pixels and positions are caught.
A grouped/direct-canvas 900-frame replay passed all registers including R, original RAM
and every changed colour group. This is not the full frozen release proof.

Current layout: visible Layer2 pages 12..17, shifted figure cache pages 25..45,
expanded source/buffer pages 50..91. The final cache page holds its pointer table at
C200 after 320 bytes of graphics. Code is owned page 24, 2200..3C78; original
font/tail backup 2000..21FF, state 3E00..3EC2, stack 3F00. Monochrome lookup
is page 45 offset 2048..4095, after the cache/table. Game data ends at bank 45;
banks 46/47 remain full hidden-ROM sources. Every mode still fits 1MB.

The room attribute upload at 97DD is separate from its bitmap. New room pixels are
painted before upload, then INK=PAPER cells are hidden and Layer2 enabled. The title
colour animation stays on the original ULA with Layer2 disabled, as does the ending
message. Ordinary dirty cells honour the original current attributes. No second
colour screen is copied on each write. The previous published-canvas prototype and
its checks remain private history, not the current architecture.

Performance is NOT release-ready. Three paired 300-update trials initially showed
+225..437% overhead. Grouping eight dirty rows and complete 24-row restorations reduced
that to +41..168%; direct drawing reduced it to +26..93%. Octet-level transparent copies
retain an exact mask/OR fallback where the supplied colour and mask overlap, and pass
all 684 image cases, but the pace gate still fails. Current bulk-copy work maps expanded
buffers once per bank boundary, uses unrolled LDI, and runs the displaced original LDIR
at 28MHz with an explicit original-time budget. It restores the incoming clock without
writing below the original stack. The revised 56 bulk cases and eight attribute/title
cases pass; native timing and the full integration proof still need completion.

Three opening comparisons and an editable 57-frame PNG are under the run's `out/` directory.
The 7,446-frame built-in demo reaches later zones and the return to the menu; the manual walk
is a continuous 2,860-frame recording. Broader model, cheats, pace and loader checks remain.

## Feasibility

No frame sync in play; interrupts stay off. Preserve the original player update, beeper
and delays at their incoming clock. Original draw/erase and scenery construction are
separate memory-only acceleration windows. Scene window 965D..9765 ends before the A8D6
ship/ending dispatcher; its helpers stay outside. The complete original loops/writes remain.

The earlier copy-per-row candidate was 28–55% slow. Native profiles found repeated wrappers,
raster bookkeeping, erasure mapping and per-byte scenery copies dominated. One-window-at-a-
time diagnostics separated real copying cost from excessive limiter waiting. Measured nested
wrapper overhead is~91us plus 27us between samples; at K6.5 its debt is 155 sixteenths, not 52.
The corrected 156 rounds that cost up; the original game-window K104 was not retuned.

Current group/copy candidate meets the 2% average pace gate, but seed 5 room transitions take
431ms versus 261–264ms. Whole-copy cost, not average pace, is the remaining budget. No final
release until that is resolved or the owner explicitly changes the requirement. Grouping
entire scene copies is an untested next CPU option; DMA needs ownership/MMU/fallback tests
and whole-hook native measurement. No DMA gain or hardware result is claimed.

## Technique use

- detect.buffer-layout-producer: helped: shared survey and scan located the mirror sources.
- detect.drawing-parameters: helped: original registers/rows supplied exact shift geometry.
- detect.graphics-record-layout: helped: decoded all 57 records and compared the ninth plane.

## Lessons

- [local: Highway NXC bank layout] SET3 may add only banks 8+. Reserve unused 48K banks 6/7
  in the default build so Enhanced can enable its Layer2 pages 12..15 without a format change.
  The base has zero-filled banks; game-visible RAM and runtime code are unchanged.

- [local: Highway fixed scene windows] A nested debt counter saturated during room construction.
  Two original memory-only loops have invariant 375864T/247097T budgets in 68 states across
  zones 1..31. Include the entire colour update once in those windows; leave the intervening
  original sound dispatcher outside. Independent instruction-budget tests guard this assumption.
- [local: Highway attribute conversion] A backward 576-byte attribute expansion was mostly repeated
  map/register work. An 8-pixel lookup in unused cache-page space preserves exact colours and
  eliminates the measured transition penalty without consuming another bank.
- [local: Highway painting identity] Native sheets use original mask+ink geometry and bottom-first
  source rows. Keep unchanged palette indices exactly; map only edited RGB pixels to RGB333.

- [local: Highway transition timing] A+0.16% whole-trial result still hides a69–76ms zone
  penalty. Keep per-transition timestamps alongside quiet/busy and rolling-window tables.
- [local: Highway copy ownership] Whole-row DMA is safe only across stable mapped RAM;
  backward expanded-byte overlap uses grouped LDD to retain read/write order. Core and
  hardware-IM2 fallbacks must run the same independent colour-copy oracle.

- [local: Highway timing/geometry evidence] Passing quiet/busy averages can hide scene-change
  delays: report individual slow updates as well as 20-update windows. Current source remains
  held at that stage despite three averages within 2%; the final window/LUT work resolved it.
- [local: Highway timing/geometry evidence] Raster samples omit wrapper entry/exit and the
  gap between window/debt samples. Profile those native offsets before choosing fixed debt;
  otherwise the limiter can turn a real copy optimization into additional waiting.
- [local: Highway timing/geometry evidence] Group complete original loops, including their
  final ADD/DJNZ and alternate registers. Preserve original writes and R while removing repeated
  hooks. The verifier must permit reached displaced interiors, not arbitrary interior jumps.
- [local: Highway timing/geometry evidence] Map a rectangle once only after checking both
  positive byte-span crossings and negative row steps. Erasure and tile page faults need
  separate negative controls; table flags must be cached before mapping over their RAM.

- [local: Highway-specific buffer and loader evidence] Profile complete hooks before assigning cost to large copies. The 100-update
  seed 5 profile attributes 4.35s to dirty cells, 2.91s to erasure and 1.09s to dirty flags;
  the background LDIR at 97E8 occurs only once (29ms). The old per-cell profiler counted
  repeat returns incorrectly; the replacement resets each entry guard after its first exit.
- [local: Highway-specific buffer and loader evidence] Grouping the complete dirty table at 9A9B reduces wrapper count; mapped eight-row
  cells avoid remapping 64 separate pixels. The original dirty flags and loop remain intact.
  This is insufficient for the required pace: retain measured failure and do not tune a
  limiter to conceal real cost. Consider a broader separately paced erasure window and
  DMA only after proving bank boundaries, preservation and backend support.

- [local: Highway-specific buffer and loader evidence] A loader's final JP is a stronger entry boundary than the first convenient menu PC:
  F260 jumps to B0E0, while B1E0 is reached after title work. Exact prefix/boot proof is required.
- [local: Highway-specific buffer and loader evidence] Read the palette format: the supplied `.pal` is 256 text RGB triplets, not raw RGB bytes.
  The private colour decoder asserts the count and dimensions before producing the reviewed sheets.
- [local: Highway-specific buffer and loader evidence] Model the -4-pixel plotter's two-byte output width separately; the other three draw
  three bytes. Compare to original writes, and retain a wrong-position negative control.
- [local: Highway-specific buffer and loader evidence] This archive POK has overlapping immunity variants at 40905 (0 versus 8).
  They require independent behaviour checks and compatible menu choices, not blind concatenation.
- [local: Highway-specific buffer and loader evidence] Dirty flags at 99A0/99A2/99A4 overlap the last colour-buffer row. Later scene copies
  at A5F0/A603 also need mirroring; missing them produced eight bad bytes from demo frame 1450.
  Audit actual writes, not only the final image, to find the first lost dependency.
- [local: Highway-specific buffer and loader evidence] Original INK=PAPER can hide an intact bitmap. An opaque colour layer must reproduce
  that visibility change; matching bitmap bytes alone does not prove the ending screen.
- [local: Highway-specific buffer and loader evidence] NEXLOAD overwrites the printer buffer before entry. Restore 5B00..5CFF, including
  both the font and temporary startup tail, then compare every byte and register at B0E0.
- [local: Highway-specific buffer and loader evidence] The same player routine runs during the initial procession. Gate 9C7F by caller 916C
  and start paired native trials from one original checkpoint to avoid mixing startup with play.

## 2026-11-10 copy and timing evidence

- Ordinary DMA and CPU fallback match 56 copy cases each on current core, old-core fallback
  and hardware-IM2 fallback. No blitter extensions are issued. DMA jobs are synchronous,
  bounded to 8K real mapped RAM; this 48K game has no DMA owner or Next interrupt sources.
- Default 2000-frame replay: 4754 hook/R comparisons, 233668608 RAM bytes, no differences.
 576 speed/IFF/R cases pass; wrong R/MMU/fixed-speed controls are caught.
- Independent 900-frame colour replay before the grouped reverse copy: 6279 hook/R checks
  and 235446 colour bytes, no differences. The new 2000-frame colour replay also passes: 16928 hook/R checks,
  688746 independently compared colour bytes, zero differences.
- Whole-hook profiling: full-row colour copies fell 87.84 ->68.69 ->42.20ms per scene;
  the drawing window avoids redundant per-copy waits. That intermediate scene transition still failed;
  Release integration below records the resolved result.
- No original logic, sound or delay routine is accelerated; CALL A8D6 stays outside both
  scene windows. CPU-only output is checked, but CPU-only native pace is not accepted.

## Release integration

- All 57 native figure frames import from HIGHWAY_PAINTING_SPRITES.png at 256x256. Unedited
  PNG produces the byte-identical NEX. Original source indices are retained; edits become
  solid RGB333, with no blend. Partial alpha and changed figure borders are rejected.
- Original loading screen included in both modes. Highest game bank 45; hidden ROM46/47.
  Plain conversion and both modes preserve exact B0E0 registers/R/RAM on normal/NEXLOAD boot.
- Native three-seed default/Enhanced trials each compare 300 actual Vorton updates; all 301
  tracked states agree. Six sound comparisons matched 117674, 135424 and 128046 beeper writes
  per seed, including values/order. All writes use 3.5MHz. Pulse delta at most 1.715us.
- Current source has the complete independent colour oracle in the engine, 684 frame/shift/
  position cases, default/colour ABI matrices and deliberate R/MMU/speed/pixel/position
  faults. Current/old-core/hardware-IM2 copy backends each pass 56 independent cases.
- Trainers: Infinite time; Immunity (both collision directions); Objects only destroyed
  by shots. 26 original-function cases passed. Natural collision coverage is still limited.
  Exact-package loader checks test each option alone and all together; timer stays 3500.
- Standard engine registry/auto/record now integrated. Quick integrated 2000-frame verification passed: 16928 Enhanced hook/R boundaries and
  5,509,968 independently checked colour bytes; default 576 ABI and Enhanced 840 ABI
  cases, plus all 684 figure cases and five broken builds. Actual-loader default passed
  with 964 player updates. Those staged counts are superseded by the frozen results below.

### Frozen release evidence

- Full replay: 22306 frames per mode across continuous 2860, demo 7446 and collision-route12000.
  Default 57701 hook/R comparisons and 2836119552 RAM bytes; Enhanced 202783 hook/R comparisons
  and 65086776 independent colour-byte comparisons. No differences. All five outputs rebuild.
- Default 576 and Enhanced 888 ABI cases; 684 figure cases; 56 copy cases for each of three
  backends; 8 attribute cases; 2 original scene budgets; 26 trainer behaviour cases. Deliberate
  R/MMU/speed faults caught in both modes; cached-pixel and wrong-position faults in Enhanced.
- Additional lifecycle proof covers 12 original-clock/NR69 scenarios and 3 broken controls.
- Final 87504-byte NXC SHA256:95947ad7a5087b07506cc96e16967907b6e680cab2b5035d9ff8df83ad3bf265.
  Ten colour/trainer combinations reconstruct exactly with ram_top47. Six actual-loader modes
  pass on disposable 26.11 cards: default, Enhanced, all trainers, and each trainer separately.
  Rebuilt NEXes are byte-exact; all reach 644..964 player updates, no fast-clock beeper writes.
- Packaging preserves the accepted candidate nonce/key, so it rebuilds byte for byte from
  the same owner inputs. The envelope is never printed or included in source contributions.
- CPU-only native fallback diagnostics: quiet/busy averages within 0.51%, worst 20+2.942%,
  transitions up to 45.76ms slower. A separate stack-fill experiment reduced that marginally
  but still failed; it was not adopted. Normal DMA is the measured original-pace target.
- Known issues: title colour animation and ending message remain original ULA; individual
  update timing varies with raster phase. Missing: natural completion, comprehensive
  collision playthrough, hardware and other-emulator testing.

## Friction

- reuse: [local: private Highway development workflow] used shared survey, recorder, boot, pace and hook libraries.
- retries: [local: private Highway development workflow] discarded the segmented recording after desync; continuous recording works.
- environment: [local: private Highway development workflow] native JNext uses private configuration and temporary directories.
- hand-rolled: [local: private Highway development workflow] independent colour/mask oracle is game-specific; no shared tool replacement.
- scratch: [local: private Highway development workflow] private probes retained while stage2 is unfinished; promote useful engine
  verifiers before delivery, with no game data in the repo.

## Stage log

- 2026-11-08: fetched main 364cb7f; staged exact release, read painter's fixes, recorded two
  continuous routes, traced buffers/plotters and exported initial comparison and painting sheets.
- 2026-11-08: refreshed to c086e2b after reading incoming Army Moves/Game Over additions;
  no shared runtime change. Added exact-entry boot, paced default hooks, full demo mirror and
  separately checked cached colour helpers. Runtime integration, trainer proof and packaging remain.

- 2026-11-08: Held at performance gate after several distinct cache/copy approaches.
  Latest 5098-byte hook block fits below 3C00. 9A9B now mirrors the whole dirty table;
  the original dirty loop follows untouched. 983D maps each 24-byte erasure row once.
  The 96-state write matrix passes. Enhanced paired 300-update trials are +28.45/+54.78/
  +41.80%, failing release. The previous latest whole-table/generic-row candidate was
  +44.49/+105.20/+64.09%. No package or shipping claim. Batch moves to Bruce Lee.

-2026-11-08: resumed after Head Over Heels handoff; fetched/read/merged main 5081555.
  Reprofiled the actual current whole-table candidate. New erase window is under quick
  CPU/R/RAM/colour and native timing checks; not a passing release yet.

- 2026-11-08: measured/removed most Enhanced slowdown with shared pacing and grouped copies.
  Three overall trials now -0.461/+0.673/-0.196%, but room-transition gate still fails.
  Default 448-case matrix and 3 faults, 88 colour-write cases, 26 trainer function cases and native
  Enhanced boot/play pass. Full release evidence and NXC remain outstanding. No pushes.

- 2026-11-10: refreshed main; added measured DMA/grouped-copy/post-scene candidates.
  Passing state/colour checks do not close the remaining zone-transition pace gate.

- 2026-11-10: resolved measured transition penalty; promoted independent colour/replay,
  frame/position, trainer and copy-backend checks into the engine. Added native editable
  import, loading screens and release registry/record. No shared runtime change.

- 2026-11-10: full frozen verification stamped, exact NXC and six actual-loader modes passed.
  CPU-only transition limitation measured separately and retained in package/handoff notes.
