# Impossamole (Gremlin, 1990, 128K)

## Next session

Stage 1, renderer feasibility. Intake and the original-game trainer check are complete. The owner has settled the visual choices. The test copy awaits a sprite build.

Use branch `add-impossamole` at `3f3f1446`. Inputs are under `NEXCLASH_REFERENCE/impossamole/`. The local run folder is `pilot/runs/impossamole/to-test` under the 2026-11-02-nexclash evidence tree. Start with its `check_cells.py`, `cell-feasibility.log` and `level2-producers.log`. Replay each section with its own snapshot. First trace the prior tile IDs through a scroll, then compare both screen publishers against a model which tracks the owner of each pixel.

## Inputs and multiload

- Both supplied RZX files have MD5 `1566372a75d79cc54024a2cb57578adc`. All 6 sections replayed independently to their ends. Their lengths are 837, 48,564, 41,568, 33,821, 33,213 and 42,691 frames. Removing the 5 later snapshots exhausts the port inputs at frame 837.
- The recording starts in IM 2 at PC $FF00, SP $FFF6, ROM 0 selected. The next five starts contain the exact 20,959 tape bytes at $6C00, in level-ID order 0, 3, 1, 2, 4. The first five sections end inside the tape pulse reader. A snapshot boundary supplies the result of the load.
- The player target is `Impossamole (1990)(Gremlin Graphics Software).tzx`, MD5 `66208dd233f9b994ef743f50f97428d7`, 153,113 bytes. Its 16 data blocks include the 6,912-byte loading screen at file offset 461 and five numbered levels. The program requests a one-byte ID with flag $80 and then $51DF bytes with flag $FF via $C9FB. The requested ID is at $FE1E.
- Use the original tape entry `impossamole-tape-entry.z80`, MD5 `87f938a8549d43f723bb63bfd3e9af55`. SkoolKit's simulated 128K LOAD stopped at BASIC's USR $CC25. All 40,704 CODE bytes match the tape. The recording start would store 2,406 literal bytes in its tape table, including two bytes fetched as opcodes during the first 837 frames.
- Host packing test at the clean entry placed level ID n in banks 16+2n and 17+2n. All 8 start banks and 10 level banks rebuilt byte for byte. The 1,502-byte table has 40 copies and 38 residual runs totalling 849 bytes, all outside the loaded CODE range. The tape supplies 47,905 start-state bytes and all 104,795 level bytes. A runtime hook must still deliver the selected level to $6C00 and return with the loader's expected state.

## Plain conversion

The automatic survey stopped on the recording's high SP. An explicit tail at $6080 recovered a private plain diagnostic. All 8 file banks matched. Simulated NEXLOAD restored the printer buffer, SP $FFF6, PC $FF00 and all visible RAM outside the 79-byte tail. Automap bit 4 was clear. The generic boot comparison reported two differences because it expects ROM 3 and 1FFD bit 2. This start selects ROM 0. A separate comparison matched all 16,384 bytes of the selected NextZXOS ROM 0. Six original replay prefixes of 837 frames each used zero ROM bytes and had zero reads of the tail before a write. The recording start has unequal IFF1 and IFF2, which the converter normalizes.

The preferred clean tape-entry plain NEX is 147,968 bytes, MD5 `c3c9e7568811a759fabd39b855274217`. Simulated NEXLOAD boot had zero errors. In 500 original free-run frames, none of its 80 tail bytes at $5D88 were accessed. This diagnostic has the original tape reader.

## Feasibility

The survey counted 2,839 frame callbacks and 2,268 accepted interrupts. The static coverage heuristic reported zero nearby missed CALLs to its top routines. Instruction-level tracing located the figure producers upstream of those routines.

Eight 50-byte actor records start at $BEB4. Two walkers at $C044 and $C060 feed the compositor. It allocates glyph IDs, copies either a scenery tile or an existing dynamic glyph, then applies a mask and ink. Four inner loops handle size and alignment. They borrow SP for graphics and modify instruction operands. The dirty map begins at $6080, glyphs at $6600, glyph attributes at $6B00, scenery pixels at $6C00 and scenery attributes at $7400. The priority lookup at $7500 can suppress an actor cell. The routine at $C561 publishes ordinary cells. Scrolling uses $C4C0 with different map offsets.

The host probe followed 2,000 recorded frames from each level start. Counts below are repeated drawing events, not distinct graphics or screen positions.

| Check across 10,000 frames | Result |
|---|---:|
| Active actor draws | 8,215 |
| Masked byte stores predicted from the live mask, ink and old byte | 490,052 of 490,052 |
| Stores that disagreed when the AND mask was removed | 61,096 |
| Ordinary dynamic cells published | 58,357 |
| Cells where a figure's attribute recoloured exposed scenery ink | 7,705 |
| Exposed scenery ink pixels in those cells | 110,225 |
| Checked exposed terrain bits differing from the composed glyph | 0 |
| Cell compositions taking an earlier dynamic glyph as input | 3,174 |
| Earlier glyph references with no source tracked in that draw pass | 713 |
| Actor cells skipped by foreground priority | 11,900 |
| Opaque figure pixel writes in skipped slots | 243,143 |

An overlay on the existing ULA leaves the 110,225 exposed scenery pixels recoloured. Putting whole figures in front also draws opaque pixels the original hides. Redirecting only the four inner loops leaves the allocated IDs, colours and earlier glyph references in the game's maps. The scroll publisher read the attribute table 286 times in the 2,000-frame level-ID-2 sample. A normal-publisher-only hook misses those reads. The remaining design problem is to restore the scenery under each figure at both publishers and apply the same per-cell depth to the sprites, while giving the game its original memory view.

The original limiter at $FF21 was reached from $CCCE in normal play. The 1,501-callback sample contained 362 update intervals. 352 took three interrupts. Of 360 measured waits the median slack was 40,467 T-states and the minimum was 395. The ISR reads interrupted IX, pages memory and uses up to 24 stack bytes. CPU or zxnDMA pattern uploads and core-gated 3.03.00 DDMA copies are candidates once the images exist. DMA cannot recover the masks or resolve tile priority. Whole-hook timing and the CPU fallback are unmeasured.

## Decisions and cheats

Use hardware sprites for Monty, enemies, effects and pickups drawn as figures. Keep the original colours, black lines, depth, screen reads and pace. The first release has no white outlines or Enhanced palette. Use the 128-sprite setup and disable DivMMC automap. Keep the loading screen visible during patching using the player's tape.

The archive supplies one trainer, Infinite Energy (`POKE 53432,0`). Keep it for the release, off by default. Drop none. In bank 0 it changes the immediate operand at $D0B8 from 1 to 0. $D0B4 reads energy from $FE0B, $D0B7 subtracts the operand and $D0C1 stores the result. The underflow path sets $FE1F. Across two 6,000-frame replays, all six damage events lost one point with the trainer off. All six kept energy at 18 with it on. Both runs consumed the recorded inputs. These are checks on original play. The loader menu and trainer export await a patch.

## Hardware checklist

When a sprite candidate exists, launch the main TZX through the NXC menu. Check the loading screen, keyboard selection, all five level loads, scroll boundaries, foreground occlusion, overlapping actors, pickups, attacks, pause, HUD, and loss of energy with the trainer off and on. Compare pace and music in busy rooms. Check for stale sprites after a transition on OverSpec and on a physical Next.

## Lessons

- [local: Impossamole tape boundaries] Five new machine states supply five exact level payloads. Removing them loses the first load.
- [local: Impossamole tile priority] Mask and ink recover individual row writes. Scenery colour and occlusion also require the game's cell map and the previous glyph in each overlap.
- [local: Impossamole startup choice] The tape entry reconstructs the complete initial CODE block from the target and avoids embedding the running ISR's modified instructions.

## Friction

- reuse: [tool nxc.make_tape_table] The existing tape-table builder reconstructed all five level payloads.
- retries: [local: the recorded SP is in paged RAM] An explicit $6080 tail and a second start at the tape entry gave separate boot measurements.
- environment: [none: all required original inputs were available locally]
- hand-rolled: [local: four self-modifying kernels] A private register-level check compared each AND/OR store and its mask-free control.
- scratch: [local: game addresses and masks] The private run folder holds the probe and evidence. Its decoding tables apply only to this game.

## Technique use

- detect.buffer-layout-producer: helped trace both screen writers to the dirty map, glyph allocator and masked writes.
- detect.tracked-unit: helped separate actor records from published 8x8 cells.
- patch.scratch-redirect: no help here. There is no shared address helper. The game uses dirty IDs and colour tables alongside the glyph bytes.

## Open

Trace the 713 earlier references through scroll preparation, including marker values. Compare both publisher outputs pixel by pixel with scenery, actor ownership and foreground priority separated. Inventory pickups and effects outside the eight actor records. Then prove a complete hardware-sprite update fits the measured waits, including IRQ state, level loading and menu transitions. The graphics engine, release record, full verify and stamp, packaged trainer, OverSpec menu capture and physical hardware check remain open.

## Stage log

- 2026-11-28, stages 0 and 1, about ten minutes, one owner brief. Used checkout 3f3f1446. Stopped at renderer feasibility after measuring the failures of the two simple overlays.
