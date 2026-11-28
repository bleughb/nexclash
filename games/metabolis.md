# Metabolis (1985, Gremlin Graphics Software)

## Next session

Intake rechecked. Stage 1 feasibility is incomplete. Branch `add-metabolis`, base `e759250f9b9cefa084dae213ea4c6e4fd4c9a1ea`. The owner's design choices are settled.

Start with the two counterexamples below. Review the four apparent leftover calls in the original release against self-modified dispatch and returns. The pilot run contains the original PC maps, measurements and probes. Use each of the six recordings with its own embedded start. The wizard and moving pickup now have normal play recordings.

## Inputs and plain boot

The patch target is `Metabolis (1985)(Gremlin Graphics Software).z80`, MD5 `3ed7616a0f06647a0a97e0027291d897`. Its IM 1 stack returns to the title wipe at E8A9. The archive RZX, MD5 `cf63bd37e8b6e3e3eeac42ed31528849`, starts in the BASIC loader. Its embedded snapshot is `metabolis-rzx-start.z80`, MD5 `2e60d9c35a83857a4d6c0781522954e5`. It played all 32,428 frames with zero desyncs.

The tape's 40,886-byte game block begins at 604A. The target and RZX starts differ in 47 bytes of this range. Of these, 15 are below FF78, in shift operands, a patched CALL, counters and a scroll pointer. The remaining 32 are in the game's variables. The trainer instructions agree. The original tape has six blocks, all with valid XOR checksums. The 6,912-byte screen starts at file offset 180. Its extracted `metabolis.scr` has MD5 `2aa792ea0cd7ab9e16cd47402caf48db`. For a snapshot-target patch use this picture as SCR1 and select `build_screen nex`.

The target's first 700 frames touched all 32,768 bytes from 4000 to BFFF. Its longest reported write-first span was 16 bytes. The plain tail needs 79. The private diagnostic resumes that target after its current wipe at E75C. Its 40,886 game bytes match the target exactly (MD5 `38d32cc930f59793f5f6656db63eef66`). This is `metabolis-title-start.z80`, MD5 `84dc18c09112b2b5ea0b0c41d9b91800`. The 1,400-frame scan there found 4,224 write-first bytes from 4000. The 80-byte tail at 4000 to 404F produced zero simulated boot mismatches. Injecting the actual boot tail into the title state gave identical RAM and registers by frame 1 and at frame 1,400. This tests the game-side tail effect. Display during the first frame is unmeasured. Private plain NEX MD5 `648c05ad51429e62645919f13570e354`.

## Recording coverage

The staged 15,001-frame analysis reported zero coverage gaps because its proximity check ignored the upper 16K. Rechecking the instruction map at 15,000 and 32,428 recorded frames found four nearby calls missing in both. The full replay executed 3,526 distinct PCs.

| Routine | Direct CALL sites hit | Full replay observations |
|---|---:|---|
| CFBB, paired XOR plot | 19 of 29 | 47,325 entries including jumps. The first survey hit 16 direct sites. |
| E290, vertically overlapping plot | 2 of 2 | 22,493 entries. E307 processed 272,128 rows. |
| D79A, attribute paint | 11 of 14 | 57,290 entries including jumps. |
| D10E, tile writer | 2 of 2 | 148,482 entries. |
| E086, screen transition | 2 of 3 | The proximity flag at E143 concerns a transition. |

Three of the original four flags were figure calls. At D9DB the wizard is erased as he leaves the player's room. Nine initial continuations missed it. A closer start in room 55 and ordinary Q+O reached it in 76 frames. The pointed-hat figure can also be seen in room 40 at archive frame 3,167 (wizard-room-original.png).

Five new recordings in the Metabolis reference folder supplement the archive. No game state was poked to reach these paths. Each was independently replayed and its embedded start checked byte for byte. The attract recording starts from the original TOSEC file. The others start from the specified archive state.

| Recording | Start | Frames | New evidence |
|---|---|---:|---|
| metabolis-attract.rzx | Original title, no input | 2,089 | CBAA and CBBB each drew once. CBCE and CBDE each painted once. |
| metabolis-wizard-exit.rzx | Archive frame 4,063, Q+O | 76 | D9DB erased the visible wizard once. |
| metabolis-contact.rzx | Archive frame 16,870, no input | 125 | C7DA drew once after contact. |
| metabolis-rising.rzx | Archive frame 20,714, no input | 605 | F19F drew once with a modified row count. |
| metabolis-pickup.rzx | Archive frame 17,944, O for 184 frames then release | 429 | C9D9 drew 50 times and C9EF painted 50 times in room 60. CA0D, the refill on contact, had zero calls. |

Across 35,752 frames including shared prefixes and continuations, 25 of 29 literal CALLs to CFBB and all 14 literal CALLs to D79A ran. D2C4, D68B, E37D and E3BB had zero hits. D2C4 and E37D still trip the survey's proximity rule. D2C8 begins a different routine. E36B ends the attribute painter with RET. The four look like remnants of the active D265, F19F, DC55 and DC90 paths respectively. Following direct control flow from every observed upper-game instruction and all eight room-handler table entries visited 3,186 instructions and found no route to the four calls. This check uses the unmodified snapshot bytes. Self-modified branches and computed returns still need an exclusion proof before labelling these dead. Another untargeted playthrough would not settle that question.

## Design and verification boundary

Every moving figure, effect and pickup drawn as a figure goes on hardware sprites. Keep the game's colours, black lines, scenery, HUD and depth. Add no white outline. Keep the original update pace, interrupts and game reads. Start with DivMMC automap off and 128 sprite slots. Enhanced colours are deferred.

## Feasibility

CFBB alternates old and new drawing registers with EXX. E290 interleaves old and new scanlines or jumps to CFBB. E35F preserves bright cells and replaces ink elsewhere in a three-by-three attribute area. Two experiments tested whether a hardware overlay could use a single game-visible and player-visible attribute file.

1. Keep the original attribute paint. In 3,200 recorded frames the player painter made 20,173 stores and changed 1,295 attributes. Of those, 419 changed the ink of set pixels outside the player's 16-by-16 box. There were 5,459 such pixel changes counting repeated stores. A sprite confined to the player cannot hide those changes.
2. Suppress the figure paint. A shadow of cells tracked the value before E35F and discarded it on any other write. At D4F5, the original and clean values gave opposite answers to the exact test for 7 on 15 reads. The first was cell 5957 at frame 266, original 5, clean 7. At D0BA, 3,204 differing bytes left the bright-bit result intact. Over the full archive, 3,451 of 4,648 original D4F5 reads equalled 7 and 1,197 did not.

The missing component is a renderer that keeps the painted values for game logic while presenting clean scenery and hardware figures. A second attribute map or a separate display bank must account for tile writes, room wipes, attribute read-modify-write loops, partial XOR figures and their erasure. The probes above are counterexamples to the two simpler versions. Neither measures a finished split-display implementation. A diagnostic must return the original value for every gameplay read and show zero paint spill, then compare timing and sprite freshness at the player HALT at D3D1. The initial survey counted 15,000 interrupts. The room-60 pickup recording gave 104 complete DB04 updates. Of these, 103 took four interrupts and one took ten. From the first D3D1 wait in an update to the next interrupt, measured slack was 23,836 to 54,712 T-states (median 29,088). This budget applies to that wait in those updates. DDMA cannot expand one-bit figures or perform XOR. Any upload acceleration still needs an end-to-end timing comparison and a fallback.

Sprite integration and the release record are pending. On hardware, cold boot from the NXC menu, observe the loading picture, compare busy-room speed and sound, and watch the wizard cross a room boundary for a stale sprite. Check black detail on figures against bright and dark scenery.

## Trainers

There is one archive POKE. Its original-byte field is 0. The original TOSEC and RZX code at 55202 (D7A2) is C0, RET NZ. Replacing it with C9, RET, bypasses periodic life-force updates. The archive calls it Immunity. In mid-game it held life force at 30. Enabled before starting from the original TOSEC title, it also suppressed the initial fill. At 600 frames after the first D7A2 hit, the gauge was 0, against 14 in the control. Drop this POKE.

Keep No life-force loss. D7D9 changes from 2A (load the HUD graphic pointer) to C9 (return before removing a gauge segment). The fill and refill paths still run. All four option combinations reached the game at frame 477 from the TOSEC target. At +600 frames, each run with this replacement had filled to 31. Both runs with it off read 14.

The additional candidate, Steady heartbeat, changes D5C0 from 3D, DEC A, to B7, OR A. The game keeps ticking, but the shortening branch keeps a positive interval. Its recovery branch stays intact. This candidate was found in the code. Prior publication is unknown.

Free play from archive frame 1,000 started with life force 30 and heartbeat interval 15. Each row uses the same input and machine state. Both trainer bytes were checked against the original before play.

| Options | Life force at +300 frames | Heart interval at +300 frames |
|---|---:|---:|
| Both off | 27 | 14 |
| No life-force loss | 30 | 14 |
| Steady heartbeat | 27 | 15 |
| Both on | 30 | 15 |

All four reached death flag 3 at +354 frames by another route. Eight directed last-tick checks from cloned gameplay state covered two lethal events across the four combinations. In all eight the corresponding option alone determined whether death flag 3 was set. These are controlled states. In six natural follow-up runs from heartbeat intervals 3, 4 and 5, no heart-death instruction ran. Retain the two narrower options, default off. Their prior publication and behaviour on an integrated sprite build are unverified.

## Technique use

- tools/probes/rzx_census.py: used: counted the real figure callers and both outcomes of the attribute test across the full recording.
- detect.gameplay-screen-readers: helped: identified the exact-value placement test and the bright-bit reader.
- tools/probes/pacing_census.py: used: measured 104 complete game updates in room 60.
- detect.pacing-structure: helped: separated the observed HALT before the player plot from the unmeasured hook budget.
- patch.attribute-shadow: helped: identified the need for separate original and visible attribute values. Transitions and full hook costs need proof.
- detect.routine-removal: helped: the attribute painter has gameplay consumers to investigate before removing writes.

## Lessons

- [tool nexclash.survey] A fixed-memory limit hid every proximity flag above BFFF in a 48K game. The full instruction map exposed three flagged figure calls.
- [local: title wipe] The wipe reads all potential low RAM tail locations. Advancing to its return preserved the whole game block and supplied 80 write-first bytes.
- [local: two independent health meters] The archive byte left life force at zero from the title. Blocking just the decrement path let it fill to 31. A separate death still ended all four mid-game runs.

## Friction

- reuse: [tool nexclash.survey] The coverage fix and cache revision apply to other 48K surveys.
- retries: [local: different title states] Both starts touch the printer buffer. The title-wipe return supplies a measured display-memory tail.
- environment: [none: the pilot interpreter, Next ROM and local reference files were available]
- hand-rolled: [tool nexclash.survey] The independent PC map diagnoses the earlier gate. Subsequent 48K surveys use the corrected limit.
- scratch: [local: private game fixtures] Input comparison, coverage replay, tail and trainer experiments depend on this title's addresses and stay in the pilot folder.

## Stage log

- 2026-11-28. Intake rechecked on base e759250. Original-release comparison, full caller census, two trainer controls and plain boot completed. Five supplemental recordings, two failed rendering experiments, one user brief. Coverage and stage 1 feasibility remain open.
