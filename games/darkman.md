# Darkman (Ocean, 1991, 128K)

## Next session

Stage 1 remains open on branch `add-darkman` at `e759250f`. The owner's design decisions are complete. The local test copy contains a trainer diagnostic with the original graphics. The evidence record rebuilds the plain TOSEC conversion only.

Start with the level 2 screen changes and level 5 foreground test below. Use the original TOSEC snapshot for the first load and the TOSEC tape for the second. Capture the actual load boundary and the original later-level code. Exercise or rule out the level 5 type-10 figure. Run the page and foreground models on those inputs before installing hooks. The pilot evidence folder is `pilot/runs/darkman/to-test`. The reference folder is `darkman/`.

## Source and recordings

The target is `Darkman (1991)(Ocean)[128K].z80`, 82,352 bytes, MD5 `1d778f5a9691fcf4dbec960078a76d91`. It starts at PC $D4D7, SP $7FF8, IM 2, interrupts enabled, 7FFD $14. The first archive recording starts at PC $D4D9 with 7FFD $11. Its bank 4 is identical to target bank 1 across all 16,384 bytes. Its bank 1 matches 16,293 bytes of target bank 4. The recording's menu is at a different point in the game's bank exchanges.

| Input | Check | Result |
|---|---|---|
| DARKMAN1.RZX | Native replay | 30,274 of 30,274 frames. Its embedded start MD5 is 506154677af3a61237ce3cfc10bdefe5. |
| DARKMAN2.RZX | Native replay | 46,404 of 46,404 frames. Its embedded start MD5 is abf8eae5139664a3efd1a2217a904131. It begins at a loaded prompt for the second half. |
| TOSEC tape | Loading screen | Block 33 names TITLE. Block 34 contains 6,912 screen bytes at file offset $1F52. Block XOR is zero. Screen MD5 is 41362d2840e91c42a1440549fea3ce4e. |
| TOSEC tape | Multiload | MAINCODE is block 36. MAINLD2 is block 52 after stop block 49. Of 450 nonzero aligned 32-byte chunks of block 56, 439 have no exact match anywhere in the decompressed original snapshot. |
| Release-code substitution | Keep each recording's start state except the resident $8600 to $B9FD image from its TOSEC main-code block | This changes 3,184 bytes for RZX1 and 4,568 for RZX2, including mutable bytes. Port readings ran out at zero-based frames 12,756 and 45 respectively. This experiment alone cannot identify the first causal instruction. |

The code comparison independently finds different absolute operands. For level 2 energy the release decrements $A179 at PC $A189. RZX1 decrements $A16B at $A17B. For levels 4 and 6 the tape decrements $AD23 at $AD33. RZX2 decrements $AD31 at $AD41. The level 4 bomb decrement is at $AB4E on the tape and $AB5C in RZX2. A hook or POKE address copied between these states can land inside another instruction. Both embedded starts and the tape screen are staged outside the checkout. The original snapshot remains the only diagnostic patch target.

## Feasibility

Level 1 paints moving figures with masks. $9268 selects a graphic through IX, fetches mask and picture bytes using SP, and pages the destination screen back in. $92B1 reads the background, ANDs E, ORs B and stores the result. $9543 handles the smaller records. Both opaque bit values matter. An XOR toggle cannot represent the opaque paper inside a figure. Scenery, status panels, messages and their reads belong to the original ULA.

The host experiment follows physical banks 5 and 7, including aliases at $C000. It interprets each mask and OR operand, checks the resulting byte against the real store, and keeps a scenery copy with the selected figure writes omitted. At each display-bank change it recomposes all 6,144 bitmap bytes. It compares visible bits using the displayed cell's actual ink and paper. Each trace starts from the recorded screen, so it measures writes after the bookmark. These tests model the picture, without executing a hardware sprite hook.

| Recorded scene | Input frames | Display-bank changes | Figure byte writes | Visible result |
|---|---:|---:|---:|---|
| Level 1, RZX1 after 916 | 350 | 84 | 31,228 | The current masked figures match the visible bitmap at all 84 changes. Old bits persist in black-on-black cells. |
| Level 1, RZX1 after 5,200 | 350 | 112 | 25,064 | The same test matches at all 112 changes. Both level 1 traces record zero figure writes to the displayed bank and zero outside reads of tracked figure bytes before overwrite. |
| Level 2, RZX1 after 15,630 | 250 | 87 | 24,368 | Current figures alone lose 515, 463, 1,043 and 985 visible pixels on four switches. Reusing the previous figure mask for each physical bank when it is reselected without a new draw gives zero visible mismatches across all 87 switches. |
| Level 4, RZX2 after 6,500 | 250 | 84 | 34,444 | Current masked figures match at all 84 changes. This window covers the recording's code. |
| Level 5, RZX2 after 20,500 | 7,100 | 1,821 completed inline masked plots | 50,207 figure stores that changed a bit | Keeping the earlier $D2F3 figures on top conflicts with the later $C38C to $C412 painter on 68 plots, 408 visible pixels in total, at most 26 per plot. |

Applying the later painter’s AND/OR mask to the earlier sprite reduced those 408 conflicting pixels to zero in the host model. The level 5 count tracks only bits the $D2F3 family demonstrably changed and excludes bytes touched by other unclassified producers. It is a lower bound. A 250-frame trace after 22,480 observed 8,232 actor stores into physical bank 5. Level 1's hidden-screen publication rule does not cover this direct renderer. The local images show the street overlay, the level 2 figures lost on a reselected page, and the level 5 overlap. The street preview uses the figure's neutral street ink on the source mask, preserves its black marks and clips invisible cells. It is an illustrated colour choice for that scene.

The figure CALL census found 21/21 in level 1, 23/23 in level 2 and 32/32 in each sampled level 4 and 6 code family. Level 3 reached 8/9 calls to three identified routines in the archive. A 254-frame no-key continuation reached the ninth, $866D, and took five damage decrements. Level 5 bank 3 called $D2F3 from $C33B, $C345, $CFF7, $D051 and $D08F respectively 29, 1,792, 0, 283 and 331 times in the 7,100-frame window. $CFF7 is the type-10 dispatch entry. Its player-accessible use is open. These counts cover identified families only. The bonus, inline effects, later-level ownership and the transition between the recordings still require original-release coverage.

The supplied survey saw 4,954 interrupts in 8,001 frames. In the 350-frame street sample after 5,200, 111 complete updates took two accepted interrupts each. Update time was 203,437 to 280,103 T, median 206,245 T. HALTs at $86E2 and $9026 pace the foreground loop. The observed wait from $9025 to interrupt was 70,844 to 70,848 T in this replay. This is uncontended original timing. It does not establish a hook budget on a Next. Core 3.03.00 DDMA can copy a prepared pattern, but mask decoding, clipping and ordering require other work. Evaluate cached uploads, CPU and DMA with the same whole-update timing and interrupt counts after the publication points are known.

## Trainers

Seven independent choices are off by default in the local diagnostic. Each location below is guarded in the original input bank. A trainer applied before a bank exchange has to patch the stored level image. The test compares actual update stores on both sides of recorded or directed play.

| Menu choice | Original location in snapshot (bank + offset) | Play result |
|---|---|---|
| Energy level 1 | 2 + $31EA | At $B1EA original energy fell from 31 to 30. OR A held 31. |
| Photo time after level 1 | 4 + $0528 | Four timer stores in 42 frames. The original units digit borrowed then counted 8, 7, 6. NOP held 0 at all four stores and prevented the borrow. |
| Mask time level 2 | 5 + $2316 | Four stores in 100 frames. The original mask counter fell from 9 to 5. NOP held 9. This routine matches the release byte window. |
| Energy level 2 | 6 + $1B89 | On the TOSEC game, right and jump produced a real hit in a 121-frame recording. The release $A189 stored 30 off and 31 on. The lab used the level 1 skip to reach level 2. |
| Energy level 3 | 3 + $260D | Five hits in the 254-frame level 3 continuation. The original energy fell from 31 to 26. The trainer held 31. The site matches the TOSEC image. |
| Time level 3 | 3 + $24B2 | Seven timer stores in 65 frames at $AAB2. The first store changed from 255 (borrow) to 0 and the units digit held 0. |
| Skip level 1 | 2 + $078E | New local choice outside the supplied archive. Change the offset of the paused debug-key branch from 9 to 0. Hold 1 and press Enter. In paired 600-frame runs from original play, only the enabled run reached $B2A7 at frame 7 and the next stage selector at frame 63. The global invulnerability flag stayed zero in both runs. External publication history is unknown. |

Six of eleven archive labels are in the diagnostic. Five later labels are withheld. The bonus timer after levels 3/5 repeats $C528. RZX2 reached that decrement and the altered first store held the digit, then its recorded inputs diverged. The later energy and mask checks held 31 and 9 in sampled RZX2 play. The level 4 bomb address points at an instruction operand in RZX2 and a decrement on the tape. At the corresponding recording site, four real updates dropped the digit code from 38 to 34 off and held 38 on. During level 6 three mask stores held 9 and a damage store held 31. The modified photo clocks diverged from recorded input at local frames 15 and 7 after levels 3 and 5, respectively. Level 5 lives fell from 2 to 1 off and held 2 on in the recorded rope section. The original-release second-load installation and combined effects of these five options are unverified. Never write their live addresses into the initial level's bank 2.

## Test copy and proof limits

The local trainer NXC rebuilds the original-graphics diagnostic from the named TOSEC snapshot, with zero changed game-bank sites in the default file. The boot stub restores the 256-byte printer buffer and the patch carries the verified TITLE screen. The menu uses `build_screen=nex`. In the Next boot model, 16 CPU fields, including R, matched the snapshot. 7FFD was $14 and NextReg $0A changed from $11 to $01. All eight physical RAM banks matched outside the 80-byte startup tail at $BA00. Within the tail, 77 bytes differed. The supplied 8,001-frame survey found $BA00 to $BFFF untouched. Tail safety over the entire original release is open.

All 128 selections produced the expected NEX banks and loading screen. Each also ran 70 host frames from a level 1 gameplay checkpoint, 8,960 frames total, and took the skip branch exactly when enabled. Those runs exercise the two live level 1 options' installation and the skip path. Later options have separate event tests above. OverSpec ran the diagnostic from the NXC menu with all options off and all on. With all seven on, the level skip reached the photo round. The test folder holds the original file, local NXC, instructions and captures. The reproducible record stamp covers the plain conversion only.

## Release design and hardware checklist

Use all 128 sprite slots as needed. Start with DivMMC automap off. Convert moving actors, drawn effects and pickups. Keep the game palette, black lines, depth, pace, logic and screen reads. Add no white outline. Enhanced colours are deferred. For an integrated build, compare both display banks through a scroll and a damage flip, and exercise the rope foreground, road, photo round, messages, second load, restart and stage exits. Check actor display age, audio and accepted interrupts beside update timing. An actual board run, sprite profile, full sprite differential and release NXC are pending.

## Lessons

- [local: Darkman] A screen-page change without a draw can redisplay an entire earlier pose. Attribute equality distinguishes hidden residue from visible loss.
- [local: Darkman] The archive POKEs can be correct on the tape even when the recordings execute different operands. Follow each stored level image through its bank exchange.

## Technique use

- patch.xor-overlay-keep-ula: helped: identified when an ink-only overlay is ineligible. The observed figures use masks. Keeping the native ULA is useful when the overlay also respects publication and later foreground masks.
- detect.pacing-structure: helped locate two HALT waits and count accepted interrupts per update.
- detect.routine-removal: helped frame the comparison between omitting figure writes, retaining page history and preserving later visible writers.

## Friction

- reuse: [local: used the toolkit replay cuts, masked-render traces, boot model and NXC packer]
- retries: [local: testing the actual selected screen bank exposed visible loss hidden by bank-5-only previews]
- environment: [local: OverSpec used an isolated data directory and the software SDL driver]
- hand-rolled: [local: page ownership and later masked overwrites required per-game probes]
- scratch: [local: stage-specific scripts, logs and images retained in the pilot evidence folder]

## Stage log

2026-11-28. One session, about 25 minutes, zero owner rounds. Reviewed intake, compared release code, tested rendering feasibility and delivered the original-graphics trainer diagnostic. Stage 1 remains open.
