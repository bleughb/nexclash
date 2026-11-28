# North Star (Gremlin Graphics Software, 1988, 48K)

## Next session

Stage 1 feasibility, held at the display check. The owner has settled the design. Branch `add-north-star`, base `e759250f9b9cefa084dae213ea4c6e4fd4c9a1ea`. The native game and both test recordings are usable. No release build or stamp.

Start with the publication counterexample below. In the pilot's `runs/north_star/to-test` directory, with the checkout on PYTHONPATH and the pilot Python, run `python check_publication.py tmp/play.rzx --picture publication.png`. The cut starts at archive frame 1,820 and contains the next 250 recorded frames. The zero-error control is the same game at copy completion.

## Inputs and decisions

| Private reference file | Bytes | MD5 |
|---|---:|---|
| North Star (1988)(Gremlin Graphics Software).z80 | 37,863 | d3b9ee33a44caecfdbd50334b7d3bfda |
| North Star (1988)(Gremlin Graphics Software).tap | 49,231 | 6d20142e267e7858acc4fa48f7495806 |
| North Star (1988)(Gremlin Graphics Software).pok | 94 | 2ede98ffcb2a3b6ca12b4b3312c9cd88 |
| northstar.rzx | 107,049 | d5bed9b4f4539833ef2d5c110601d94d |
| northstar-start.z80, embedded archive start | 37,864 | d6076ac727b0dc05ece507b887d8d50c |
| north_star.scr, tape screen | 6,912 | c65a36e6de854e30e0f454e1723cacda |
| northstar-idle.rzx, native death supplement | 47,225 | c700f851d66d880adeb6874f3c3c5dd1 |
| northstar-idle-start.z80, embedded idle start | 43,703 | ef68ab378bdbbb7ff454ac006355f60e |

Use the original TOSEC Z80 as the player target. Its PC is $FEFE. The archive start PC is $FAF0. Of 49,152 RAM bytes, 591 differ: 523 bitmap bytes, two system bytes, 60 title/work bytes in $B7A6-$B9A5 and six stack bytes. No traced instruction started at a difference or in the preceding three bytes over the full recording. Each RZX replays with its own start. All eight TAP block checksums pass. The screen starts at byte 118. A snapshot-target patch needs the extracted screen and `build_screen=nex`.

First release: all moving figures, including both lance directions, enemies, pickups and effects drawn as actors. Keep the native ink, opaque black detail, holes and draw order. Leave scenery and HUD on the ULA. No added white outline. Keep logic, screen reads, pace and sound. Use automap off, the 128-sprite setup and optional trainers off at startup. Enhanced colours are deferred.

## Feasibility

- Stage 0 covered 15,001 frames and 3,684 interrupts. Coverage gate OK. The 66,048-byte plain NEX boot check passed at tail $5B00, MD5 `6c48ea79a92b3a47d52a519abb7b92eb`.
- The full native archive replay ran 48,857 frames without desync. $AD2D ran 9,353 times. The actor compositor $AD5D was called 9,352 times from gameplay, once from $C5E5, 397 times from $C5ED and seven times from $C735. The last three are the name-entry screen. The archive never reached the lives decrement.
- The bitmap buffer starts at $8000. The ISR copies 26 columns by 120 lines to the ULA, then 390 attributes. It published 10,817 times. The main loop sets $FAED, enables interrupts and polls the flag. The ISR also runs beeper loops and clears the flag. The scroll routine borrows SP to shift the bitmap. An interrupt count alone understates the time between updates.
- In the 250-frame gameplay cut, 78 instructions wrote the bitmap and eight wrote the attribute buffer. Across 45 complete updates there was one accepted interrupt per update, 340,839 / 341,966 / 412,861 simulated T-states (min / median / max). Wait-entry to interrupt was 1,782 / 42,063 / 60,030 T. Added work of 1 / 5 / 10 ms before that wait would exceed 1 / 2 / 14 of the 45 measured gaps. The beeper toggled 478 times at $FC84 and 80 at $FC73. These are host counts.
- Removing the $AD3D call to $AD5D gave 0/11 matching next updates, even excluding the bitmap buffer. The first difference was $AD10. Besides drawing, this code saves the background and sets damage or pickup flags. Preserve its effects.
- A second experiment ran the game's erasers on a private buffer and put that clean view behind sprites. At the natural death wipe, the separate view differed on 518 of 24,960 ULA reads. At one wipe step 48 of 51 figure-ink bits remained. The missing three bits matter to a sprite that stays on top.
- Keeping the game's ULA intact solves those reads. A host overlay decoded all 9,175 player draws, 15,754 other actor draws and 7,908 lance pieces, using 12 / 29 / 5 distinct graphic addresses. A first pass disagreed on 2,581 bits in 28 copies. Giving the level caption priority on its 940 draws reduced this to **0 of 9,642,678 compared opaque bits**, over all 10,817 copy entries. This tests the assembled *bitmap in RAM* before copying. It does not test assembled hook code, sprite colours, transparent-pixel completeness or the physical display.
- **Publication blocker.** In the gameplay cut, all 46 completed copies matched. At 45 frame boundaries inside the copier, both an early and a late sprite switch failed. Even choosing the better time independently per sample left 9,218 wrong opaque bits in total. Both choices also left pixels from the other pose outside the selected sprites in all 45 samples, at least 1,503 stray pixels summed across them. In 31 samples even one of the player's 16 by 16 tiles contained both phases. At boundary 11, PC $FBB1, early left 19 stray pixels and late left 67. These are sampled ULA values, not a hardware raster measurement. The picture marks mismatched opaque bits in pink.
- End effects also bypass the ordinary copy. In the cut starting at archive frame 46,590, $C340 wrote 234,000 bytes directly into the surveyed ULA range. The finale and name-entry pictures are in the pilot run. Recheck all visibility transitions in an integrated design.
- DMA can upload prepared patterns. Gated 3.03.00 DDMA can copy rectangles. Neither operation assigns partially copied pixels to the right pose. Replacing or accelerating the game's copy requires a measured wait, preserved beeper output and a CPU fallback. No hook or DMA timings have been measured.

## Trainers

The archive POKEs and the two new candidates were checked on native Spectrum code. The new pair is absent from the supplied POK and the Hackers Anonymous North Star listing. Earlier publication elsewhere is unknown.

| Decision | Site and change | Observed effect |
|---|---|---|
| Keep Infinite lives | $BCF3, $35 to $B6 | The idle supplement loses a life at frame 462. Lives went 4 to 3 with the trainer off and stayed 4 with it on. |
| Keep Unlimited oxygen | $AD59, $29 to $95 | Redirects only the play-loop oxygen call to a RET at $BC95. At frame 120 the gauge and divider retained their initial four bytes. The bonus call at $B9C7 still targets $BC29. |
| Keep Safe enemy contact | $AF3D, $06 to $B1 | Skips the damage store for enemy contact. With lives off, the 600-frame idle test kept all four lives. From a captured type-4 pickup contact the collect flag became 1 both ways. |
| Drop Infinite Ammo | $AAA0, $35 to $00 | Freezes horizontal lance retraction. From length 3 it stayed active for 120/120 frames, versus 0/120 unpatched. The active bit prevents starting the next normal strike. |
| Drop No Enemies | $AD91, $3D to $00 | The NOP preserves NZ from the occupied-slot test and skips every selected actor, including pickups. The archive drew 963 type-4 pickups and took the pickup-contact branch 87 times. |

`northstar-candidates.pok` contains the three retained native trainers with original-byte guards. The pilot's `check_trainers.py` exercised all eight selections for 600 frames each. Separate tests covered all 16 selections of the archive trio plus a preliminary oxygen POKE against captured states. That prototype also intercepted the level-bonus drain and was superseded by the play-loop-only change. No NXC menu or trainer combinations in a patched build have been tested. [Published archive list](https://worldofspectrum.org/hackersanon/ha3/n01.htm)

## Open and hardware checklist

Review a separately displayed playfield that can switch scenery and sprites together while the CPU keeps its original ULA reads. The first target is zero stray figure pixels on the 45 mixed-copy samples. Then measure update cadence, interrupts and beeper timing on both CPU and accelerated routes. A release also needs original colours and black-mask validation, menu and wipe checks, guarded patch sites, verified loading and a stamped rebuild. Compare scrolling, level captions, death, both lance directions, pickups, the finale and name entry in OverSpec and on the Next. Hardware status is untested.

## Lessons

- [local: North Star IM 2 copier] A correct finished bitmap can still leave stray actor pixels on every sampled partial copy. Check actual ULA bytes between $FB2A and $FC4D.
- [local: North Star masked actor branch] A NOP at $AD91 inherits NZ from the earlier occupied-slot test. There were 963 type-4 draws subject to that same branch.

## Friction

- reuse: [local: North Star bitmap format] The publication comparison uses the game's three plot formats and caption coordinates.
- retries: [local: caption priority] Clipping at the actual caption draw removed all 28 steady-image errors.
- environment: [none: the pinned environment and supplied reference files worked]
- hand-rolled: [local: partial copies] A frame-boundary probe compares the two sprite poses with the live ULA.
- scratch: [local: pilot evidence] The game-specific probes, picture and logs are kept with the pilot run. No shared runtime code changed.

## Technique use

- detect.buffer-layout-producer: helped. Back-buffer scans identified the masked writers, restores and interrupt copy.
- detect.pacing-structure: helped. Measured the flag wait and beeper ports on a play segment.
- detect.routine-removal: helped. The positive differences exposed the compositor's game-state writes.

## Stage log

- 2026-11-28, stage 1 feasibility, one owner brief, no design-question round. Reassessed after two publication times failed the visible-pixel check. Maintainer review can start from the saved reproducer. Git remained read-only as requested.
