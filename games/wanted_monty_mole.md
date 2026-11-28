# Wanted! Monty Mole (Gremlin, 1984, 48K)

## Next session

Stage 2 development build on branch `add-wanted-monty-mole`, resumed from WIP 22fb626c. The owner copy opens from the NXC menu. Full verification found 0 figure mismatches in 249,911 comparisons and 137 updates over budget. Room 19 still fails the scenery check. Release verification and physical testing remain open.

At frame 26,433 of wantedold.rzx in room 19, the enemy ends at X 133. The adjacent scenery pixel (134,51) has a set bit in both the visible byte at 0x43D0 and the saved byte at 0xD630. Each byte is 0x1E. The painter at 0xFC13 changes attribute 0x58D0 from 0x47 to 0x43. The scenery changes from bright white to bright magenta. The hardware sprite nibble here is zero. The older recording contains 486 cell/update observations where off-figure scenery keeps a changed colour through the next game update. Correcting those pixels requires a display change outside the figure while preserving the underlying ULA bytes.

A separate timing test reached the same game state for 35 comparable updates. At update 38 the crusher's Y coordinate was 167 in the original and 169 in the patch. Compare accepted interrupts and the position at each update when testing a revision. To reproduce the full check, stage the record inputs and run `python selftest.py --game wanted_monty_mole --verify --stamp`.

## Sprite design

All 30 plotter CALLs target 0xEBE0. Both shift paths converge at 0xEBF5 and pass 0xEC15 before the first pixel write. This hook uses the game's shifted 48-byte image, row table and column. Each occupied 16×16 tile uses one hardware slot. Three-byte row writes replace the corresponding tile pixels, including erased bits. An ownership mask and a 16 KiB expansion table update the 4-bit patterns. Empty tiles release their slots. Playfield and title clears hide all occupied slots.

The hooks preserve both ULA stores and the intervening background read. The main row publishes each source byte as it is written. Interrupt-side scenery writers synchronize the completed portion of the plot. The six-byte eraser and eight-row coal writer publish their destinations in the same way. Interrupt handlers restore the game's incoming speed during a 28 MHz row burst. A private IM 2 vector defers a gameplay interrupt received during mapped work and delivers it to the game after the mapping is restored. Code and small mutable state occupy a writable copy of the upper half of the original ROM in MMU slot 1.

The occupied tiles use the two Spectrum brightness levels, the outside silhouettes and the enemy record ink. Palette entry 8 provides visible black. Transparent zero leaves the ULA visible. No outline is drawn. Startup hides all 128 hardware sprites and disables DivMMC automap. Enhanced colours are deferred.

## Inputs and coverage

The main snapshot starts on the title picture, inside the ROM beeper at 0x03E1, IM 1, DI, SP 0x5FE4. Its MD5 is 2435c5b4870ee326f7ebab0de5efa4c2.
The newer RZX starts 41 RAM bytes away. All 40,960 bytes from 0x6000 up match the main dump. The older RZX starts at the IM 1 vector with a return to the options screen at 0x806A. Both recordings reach the ending. The verified-archive copy of wanted.rzx is byte-identical.
The candidate player file is the 49,411-byte main TAP, MD5 b0e0ce98a04c2372e679698f25fd56e1. Its bytes 258 through 7169 match all 6,912 bytes of the archive SCR and snapshot screen. The patch uses build_screen offset 258. The tape plus the start-state recipe reproduces the default NEX byte for byte.

| Recording | Frames | Calls to 0xEBE0 | Observed outcome |
|---|---:|---:|---|
| wanted.rzx | 32,965 | 57,503 | Completion with three lives |
| wantedold.rzx | 32,088 | 56,644 | Fatal enemy contact, then completion |
| scripted.rzx | 2,870 | 2,929 | Keyboard play and one life deducted |
| options.rzx | 10,969 | 2,552 | Keyboard and Sinclair menu choices, three lives deducted, game over |
| fall.rzx | 352 | 510 | Held Kempston right from the newer recording's frame 2600. Landed with fall count 142 |
| Total | 79,244 | 120,138 | Five complete replays |

### Coverage

The detailed survey used `--stop 2000 --top 20`. It reports 2,001 frame callbacks and 16 nearby CALL sites missed across the ranked routines. Whole-recording instruction counts cover 20 of 30 static CALL sites to the main figure plotter at 0xEBE0. No new site appeared in the three scripted recordings after the older completion was included. Ten sites have synthetic call coverage and no natural RZX visits. Their original contexts are listed below.

- 0x86D8, 0x86F3, 0x874A. The first two handle an animated sequence. The third draws after an options/input routine at 0x872F. The actor records and input path here differ from the observed main loop.
- 0xC673, 0xC6B2, 0xC6C7, 0xC828, 0xC83F. These use fixed coordinates and animation counters. Their screen or mode is unknown.
- 0xFB9A, 0xFC95. These use an IX-based actor layout different from the active six-slot loop. Code at 0xFC6A selects a graphic in 32-byte increments.

All 30 CALL instructions execute the common hook in the synthetic test. The test varies X across six positions including both edges and checks blank graphics and overlaps. It proves the entry path and geometry. Natural reachability and actor-specific colours in the ten unobserved contexts remain open. The secondary row writer at 0x8452 has two unseen callers at 0x843D and 0x8445. The interrupt row shifter at 0x90A8 and menu painter at 0x80FF have coverage at all 10 and all 6 static callers respectively.

## Feasibility

Techniques: `detect.gameplay-screen-readers`, `detect.pacing-structure`, `detect.routine-removal`.

- The 17 surveyed RAM routines were compared with 5 Monty on the Run, 2 Monty is Innocent and 3 Auf Wiedersehen Monty draw/paint entries from their reference snapshots. The toolkit found zero matching masked six-instruction windows in 170 comparisons. The generic and dedicated game detectors also found no engine.
- At 0xEBE0 the game shifts a 16-row figure into three bytes per row. 0xEC2E writes each figure byte. 0xEC59 reads the saved bitmap at screen address + 0x9260 and ORs it into the visible byte. In 177,984 measured writes, XOR would give a different result 2,611 times. Calls include drawing, blank images, items and death animation. A room snapshot at 0xD254 copies all 6,144 visible bytes back into the saved bitmap.
- A new draw may erase another figure's pixels. In 2,400 frames from wanted frame 950, 70 cross-actor byte writes cleared 82 previously set figure bits. In 500 frames from wantedold frame 25,100, 35 writes cleared 50 bits. Both directions occurred. A sprite that simply stays visible until its actor moves can show pixels the game has cleared.
- The point test at 0x9228 compares a masked screen bit with the saved bitmap. In wantedold, replacing the visible bit with scenery changes 11 of 84,604 reads at 0x9254. One of the resulting contacts costs a life. The crusher uses a separate three-byte screen comparison at 0x9168 and writes both bitmaps at 0x8E6B/0x8E6C. The 2,000-frame survey also counted 4,922 and 4,497 attribute reads at 0x8D15/0x8D34 and 2,570 bitmap reads at 0x8C02. Suppressing the painter needs a separate check on the values these readers consume.
- The main update calls the six-actor routine at 0x943D. Skipping that call gave **0/459 equal gameplay RAM comparisons**, zero runaways or input mismatches. Keep movement and collision state intact.
- The main loop waits at HALT 0x943C. Of 459 intervals, 404 used two interrupts, 52 used three and 3 used eight. The minimum / median / maximum slack was 456 / 19,716 / 63,796 uncontended T-states. The beeper changed output in 65 intervals. The survey saw 1,771 interrupts accepted and up to 24 bytes of ISR stack. These are measurements of the original.
- A CPU path is needed to shift bits, combine graphics and translate them into sprite pixels. Standard DMA could upload completed patterns. Core 3.03.00 DDMA can copy or fill byte rectangles but cannot implement the OR or the bit ownership rules. The verifier subtracts the full OUTI upload time in a second timing estimate. The full check counts 60 deficits at zero transfer cost. No DMA speed-up was assumed.

## Design decisions

The first release should use the game's colours and black lines, with no white outlines. Convert Monty, enemies, effects and pickups drawn as figures. Keep scenery and text on the ULA and preserve the game's overlap, screen reads, sound and pace. Use the standard 128-sprite setup and disable DivMMC automap at startup. All trainers start off. Enhanced colours follow later. These are requirements for the sprite build.

## Cheats

The clean Gremlin TAP has five valid block checksums and matches all 40,960 bytes of the build snapshot above 0x5FFF. Both life initializers at 0xCE87 and 0xF7EA set three lives. The sole decrement at 0x9474 is intact. In 10,969 original frames the counter went 3, 2, 1, 0 and the game reached game over. The player tape is the untagged Gremlin release, CRC32 A50A88CC. [Tape catalogue](https://www.planetemu.net/en/rom/sinclair-zx-spectrum-games-tap/wanted-monty-mole-1984-gremlin-graphics)

| Menu option | Decimal POKE | Observed effect |
|---|---|---|
| Infinite lives | 38004,0 | Cancels the original decrement. The death animation still plays. |
| Safe to fall | 35874,255 | Raises the lethal fall threshold from 32 to 255. The captured fall count of 142 survives. |
| Stop crushers | 36301,201 | Returns before the crusher updater. The captured crusher stayed at Y 169. |
| Enemy contact immunity | 37607,17 | The recorded fatal encounter takes the enemy-removal path. |
| Freeze moving floors | 36657,201 | Returns at 0x8F31. Over 150 frames the original cycled through 66 floor states and 65 visible strips. The trained game retained one of each. |

The first four are the distinct effects from the two archive POKE files. Three duplicate entries and the alternate three-NOP immunity encoding were omitted. Both encodings converged in four comparisons across two contact states. The moving-floor trainer was found in this game's code. All five default off.

All 64 original archive-event checks passed. Five 1,000-frame follow-ups covered the original fatal encounter, lives and immunity. All 160 captured-event checks using the packaged opcodes passed. Each of the 32 combinations also ran for 150 frames on the moving floor and 350 frames on the cliff. All 16 with each relevant trainer gave its expected effect and all 16 without it followed the original behaviour.

## Diagnostic and hardware checklist

Both NEXLOAD starts restore the printer buffer. The sprite build matched every ROM byte used by each recording (244, 233, 227, 282 and 66 distinct bytes respectively). Neither boot tail was read before the game wrote it. The plain NEX uses the Next's ROM3, where six executed or read bytes differed in the first four recordings and four differed in the fall recording. Plain is 66,048 bytes, MD5 0d8d704da79d5220664fa54ff19cc1b4, tail 0x5F85+79. Sprites is 180,736 bytes, MD5 f4b20f24da434409ae3c9a36b72a3d27, tail 0x5F9B+57. The pinned sjasmplus 1.24.0 matches all three blocks and 37 exported symbols.

The owner NXC is 22,411 bytes, MD5 a80b9bdd15e51ff5d822cc60a9b2083a. Seven copies from five tape blocks supply 49,073 start bytes. Four sites below 0x6000 supply 72 more, 24 in system variables and 48 on the startup stack. The reconstruction table is 225 bytes. The loader reproduced all 32 distinct full builds and all 32 fix-off snapshots. The 6,912-byte loading screen comes from TAP offset 258. In all 32 fix-on builds only the 72 bytes under the patching label differed. All 32 trainer combinations started from the installed NXC in OverSpec. Each displayed the selected settings and reached the mine. The owner folder holds the tape, patch, README and four captures from that run.

Physical Next and NextTang checks are open. Try loading from the menu, keyboard and joystick, the outdoor silhouettes, room 19, overlapping enemies, coal, floor movement, crushers, the cliff fall, game over and completion. Compare movement, beeper pace and flicker against the original. Check all trainers with the fix on and off.

## Verification results

The 2,000-frame quick run matched all 29,504 hook-exit ULA checks, all 6,285 figure checks and all 459 timing budgets. It covered 3,708 plots, 59,328 rows, 220,443 original bitmap stores, 4,740 collision tests and 8,595 pattern uploads, with a peak of 24 sprites. The measured three-byte row saved 386.875 base T-states. The original minimum, median and maximum HALT slack in this sample was 456, 19,716 and 63,796 T.

| Recording | Frames | Plots | ULA checks | Sprite checks | Sprite mismatches | Timed intervals | Over budget | Over budget with free transfers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wanted.rzx | 32,965 | 57,503 | 520,018 | 119,700 | 0 | 14,011 | 60 | 24 |
| wantedold.rzx | 32,088 | 56,644 | 522,097 | 118,982 | 0 | 13,792 | 77 | 36 |
| scripted.rzx | 2,870 | 2,929 | 21,901 | 5,617 | 0 | 552 | 0 | 0 |
| options.rzx | 10,969 | 2,552 | 22,693 | 4,516 | 0 | 778 | 0 | 0 |
| fall.rzx | 352 | 510 | 6,344 | 1,096 | 0 | 128 | 0 | 0 |
| **Total** | 79,244 | 120,138 | 1,093,053 | 249,911 | 0 | 29,261 | 137 | 60 |

Actual hooks executed from recorded inputs. 7,298,688 monitored original bitmap stores, 304,055 uploads, 10,549,321 marked ink bits and 182,102 point tests, including 22 figure-dependent reads. Peak occupancy was 31 of 128 sprite slots. Worst modelled deficit was 47,507 base T-states. The room 19 scenery check failed 1/1. The five runs exercised all 30 static caller contexts and all eight speed/IFF cases each. Broken uploads detected in 5/5 controls.

Zero additional register, live-RAM, ULA, interior-entry, paging, or recording errors were reported.

The independent JNext run from the same indoor HALT state took 1.456849 s in the original and 1.435597 s in the build over 35 comparable updates, a 1.46% shorter interval. The longest interrupt gap grew from 19.97 ms to 39.94 ms and accepted interrupts fell from 50.0/s to 49.2/s. The two games had identical screen memory at 37 of 38 consecutive updates. The first difference was at update 38, when 21 of 6,912 bytes differed. All 222 collision-read observations through update 37 agreed. The second start provided only one aligned update. Full-game pace and audio remain unproven.

The differential verifier executes assembled hooks on the original recording's inputs, retains the hardware state between events and checks hardware patterns against original writers. It compares the complete 6,912-byte ULA and live RAM at measured hook exits. Register R, guarded instruction bytes and bounded dead stack bytes are excluded from their corresponding comparisons. Repeated row and shift paths reuse measured costs. It separately injects interrupts at 376 row and 30 secondary-writer boundaries, including clock and mapping transitions, and tests three deferred-interrupt cases. The actual NEX runs independently in JNext and OverSpec.

In the older recording the crusher interrupted 500 active plots. Of 6,972 crusher collision-byte tests, 756 occurred during a plot and none touched that plot rectangle. The 49 room bitmap copies preserved 3,214 observations of figure bits into saved scenery. Restored pickup colour ownership and the natural appearance of the ten synthetic-only callers are still open.

## Lessons

- [local: Monty's point collision] The collision routine reads the visible bitmap and the room copy. In the older completion, eleven tested bits depend on that difference.
- [local: Monty's overlap order] A later three-byte row can erase pixels from a different actor. The two short overlap samples provide a regression case.

- [local: room 19 scenery] Check pixels outside the bounding box as well as the figure mask when the game paints whole attribute cells.
- [local: asynchronous drawing] Original crusher interrupts can land inside an unfinished 16-row plot. Compare visible tiles at ISR exits as well as at the game update.

## Friction

- reuse: [local: compared three later Monty renderers by masked instructions before selecting a hook]
- retries: [local: the completion uses Kempston. Replaying its room state with right on Kempston produced the fatal fall.]
- environment: [none: the supplied Python, ROM and desktop emulator were usable]
- hand-rolled: [local: measured the two bitmaps at the point reader and the source bit ownership at the main plotter]
- scratch: [local: game-specific probes and scripts are retained beside the run logs for the next session]

## Technique use

- detect.gameplay-screen-readers: helped: eleven bit differences in the recorded collision test.
- detect.pacing-structure: helped: the shortest play-loop wait was 456 T.
- detect.routine-removal: helped: enemy movement and drawing share the same routine.

- patch.xor-overlay-keep-ula: helped: preserved collision inputs and covered all 30 call paths. The OR plot requires per-byte replacement and the attribute painter also colours scenery.
- patch.iff-safe-read: helped: the hook restores both incoming interrupt states in all eight clock and IFF cases.
- patch.restore-speed: helped: all four incoming clocks were restored under both interrupt states.

## Stage log

- 2026-11-28. Stage 0 established the original OR plot, screen-reader dependency, shared entry and HALT budget from two completions and three scripted recordings.
- 2026-11-28. Stage 1 selected the retained ULA and a figure overlay. Stage 2 produced the engine, verifier and owner menu package. The resumed build passed the 2,000-frame quick comparison. Full release verification failed on scenery and timing. No release stamp.
