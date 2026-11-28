# Batman (Ocean, 1986, 48K)

## Next session

Batman 1.0 keeps the Spectrum picture. Next, run the hardware checklist below on the owner's test copy. The maintainer owns commits on `add-batman`. Private inputs are under `$NEXCLASH_REFERENCE/batman/`. The pilot work directory is `pilot/runs/batman/to-test/` in the 2026-11-02 evidence tree.

For the later Enhanced round, start with `python -m nexclash.batman --check-plots "$NEXCLASH_REFERENCE/batman/batman1.rzx"`. Trace creation, removal and reassignment through the five draw lists. Verify ownership for enemies, effects, pickups and both player nodes before implementing hardware sprites. Require zero incorrect visible pixels and zero stale sprites through room changes, then measure the complete upload against the four-tick pace.

## Intake and build target

- The Ocean archive snapshot starts at the joystick selection screen, PC 0xFFFF, SP 0xFFE8, IM 2, interrupts disabled. Its MD5 is `af9f1a6fb79c47bdf9a3ac15a5fef9c7`. On Sinclair hardware the ROM bytes at 0x39FF and 0x3A00 are FF, yielding vector 0xFFFF.
- `batman1.rzx` is the isometric game. Its 48K start has MD5 `9730b0dd1ac81ed2aa18545e921547cf`. All 109,603 frames replay. The recorded start and player target differ in 540 RAM bytes, BC' and R. Substituting the target under the archive inputs desynchronises at frame 34,729 with 9 unused port reads. Keep each recording paired with its own start.
- The 128K `batman.rzx` replays 50,443 frames and shows a side-scrolling game. The survey accepts its 128K start and analyses 401 frame boundaries. `BATMANPUAJ.RZX` replays 10,021 frames and identifies itself as the 1989 PUAJ Edition. Neither has the three Ocean routine signatures at the sampled addresses. A fresh 1,197-frame scripted recording from the Ocean target reached 154 redraws and 130 player updates.
- The patch takes the Ocean archive snapshot directly. The Ocean TAP has six blocks with valid XOR checksums. Its 6,912-byte loading screen starts at offset 111, MD5 `8605b0815d9a3378997df5df8ba843e5`. SCR1 and `build_screen=nex` display it while patching. Pressing Enter adds no timed screen hold.

## Display decisions

Batman and the scenery use the same ink on black. In the first room that ink is white. Other rooms can choose another ink. Overlap within the room causes no attribute clash, so the default uses the original ULA drawing, including the HUD, black detail and foreground masks. The boot uses the toolkit's normal 50 Hz, 3.5 MHz start, DivMMC automap off and the sprite layer disabled. The game uses zero hardware sprites. Both cheats default off.

## Feasibility

The Head Over Heels original build keeps its original display. Its Enhanced engine produces a Layer 2 image. Its copy, edge and render-begin counterparts in Batman ran 67,200, 400 and 56,600 times. It supplies no per-object sprite owner or lifetime at the final copy.

Batman draws a dirty rectangle at 0x8D35. Five CALLs to 0x8D9D walk draw lists. A node at 0x8DAA supplies an object, and 0x8E1D dispatches a clipped fragment to one of twelve masked blitters. Alternate BC points into 0xA000, alternate DE to ink and alternate HL to mask. Rows advance six bytes with eight-bit wrap of the destination low byte. The width is one to five bytes. Each byte becomes `(old & mask) | ink`. The copier at 0x82EA has separate room and UI callers. The original game keeps every one of these writes.

- **Plotter coverage.** The full recording reaches all five list CALLs, all twelve inner loops and all three direct CALLs to 0x8D24. It tests 1,006,286 objects for intersection and dispatches 228,285 visible fragments. All 228,285 return checks pass, covering 10,558,519 destination bytes. The 2,001-boundary survey's nine warnings concern one attribute-fill caller and eight callers of the text/HUD routine. The full object census is separate from that short survey.
- **Depth.** Player links 0x8F1A and 0x8F2C account for 53,166 fragments, one to 24 rows high. Later draws cover 1,749,117 player pixel samples. Putting the uncut player in front gives 907,888 visibly wrong samples. Testing whether the final bitmap bit equals the player's bit falsely assigns 841,229 covered samples to Batman. Clipping the two player nodes on every later opaque write gives zero wrong ink bits in 9,594,321 visible player samples. Of those, 6,006,914 are opaque black. These counts include repeated redraws.
- **Object identity.** The full run uses 67 node addresses and 90 graphic IDs. One node draws 51 IDs over time. Comparing drawable nodes with the game's scheduled-update list at rectangle entry misses 2,334 player dispatches. Twelve non-player graphic IDs appear both inside and outside that list. Graphic ID 52 matches the pickup lookup and also has four drawings outside the update list. Membership alone cannot select every required figure.
- **Pace.** The game polls 0x6592 at 0x663E and reloads it with four. The short archive survey accepted 2,000 interrupts. In a 400-frame cut beginning at frame 1,500, 0x8DAE took 35.9% of measured time, with 3,455 calls, 597 T median, 23,246 T maximum and up to 57 calls per frame. One call was still running at the cut boundary. Most calls only test intersection. No measured budget yet covers pattern generation, transfer and commit for the busiest affected scene.
- **DMA.** The ink, opaque black and ownership operations above require per-bit work. Byte-copy DMA or DDMA can move completed patterns. Measure complete uploads, update order, interrupt and sound timing with the CPU fallback before selecting a core-gated DDMA route.

For Enhanced, maintain per-object visibility through later draws, identify each moving figure and retire stale sprites when nodes are reused. The checked player clipping rule gives a reference for the later colour and depth work.

## Plain reference and checks

`python -m nexclash.batman --plain SOURCE.z80 OUTPUT.nex` builds the original picture from either supported start. The normal converter refuses an automatic tail with SP in the top 16K. The reference reuses the toolkit's Sinclair alt-ROM bootstrap, restores the NEXLOAD printer buffer and puts all 53 temporary tail bytes at 0x7BFF back before PC 0xFFFF. DivMMC automap is off.

Batman reads ROM byte 2 at 0x96E8 and 0x96EB when the object link is zero. It holds 0x11 in the 48K ROM and 0x01 in the supplied Next ROM. With the Next ROM, the target replay first diverged at sample 663, with main RAM different at 110 samples and registers at 446. Restoring the Sinclair ROM and tail gives the results below.

| Start | Plain NEX MD5 | Input frames | Frame-boundary samples | RAM or register differences |
|---|---|---:|---:|---:|
| Ocean archive | `0d606cdd8fddf6d61e7bc5add1c6d0cf` | 1,197 | 1,198 | 0 |
| Archive replay | `63fe4b4ff42c761f94ac1913fb9e30a7` | 109,603 | 109,604 | 0 |

Both starts pass simulated boot with and without NEXLOAD workspace corruption. All 49,152 game RAM bytes compare, including the tail. R is 20 for the target and 105 for the archive replay. The frame check supplies the modeled post-boot memory and registers to 48K replay. It compares a digest of all game RAM and 27 register fields (including PC and R) at each boundary. Flipping one byte of the NEX's saved tail makes the boot check identify the incorrect byte at 0x7BFF. Native pace, audio and hardware behaviour remain open.

## Cheats and package

The Ocean POK contains 34 entries at 30 addresses. Each ran separately from the player target through the same 1,197-frame script. All 34 reached room drawing and the player update, and eight changed the final screen. Two had their advertised effects confirmed in a separate hazard test. The menu offers those two.

| Trainer | Instruction change | In-play result |
|---|---|---|
| Infinite lives | 36798, change the operand of `SUB 1` to 0 | Death still runs. The BCD count stays at ten instead of dropping to nine. |
| Immunity | 39908, change `RET NZ` to `RET` | The tested enemy contact leaves the death timer at zero. |

All four combinations ran from the same recorded collision for 200 frames each. Without Immunity, 122 frames had a nonzero death timer, peaking at 12. With Immunity the timer stayed zero throughout. Three captured death paths and three captured damage paths also confirmed the chosen instruction effects.

The second Infinite Lives entry at 36797 changes an opcode and consumes later instructions as an operand. The alternate immunity at 39915 still enters the sound path. Startup resets the proposed inventory, bonus counters and life count. Five display cheats change the picture. The remaining movement, bonus, interaction and sound entries need their own event tests. The pilot report lists all 34 dispositions.

To reproduce the package, stage the record's Ocean snapshot as `Batman.z80` with `batman.scr` beside it, then run `python nexclash.py patch Batman.z80 --nex -o build`. The package selects the plain output with its tape picture. The owner needs only `Batman.nxc` and `Batman.z80` to play. With the cheats off the bare NEX is 105,728 bytes, MD5 `b09d9c7fa45c4a25df8102c73dbbc780`. Adding Immunity, Infinite lives or both changes exactly 1, 1 or 2 bytes respectively.

The owner's NXC is 22,564 bytes, MD5 `fee8e3c65d2e5296dd86357616042f62`. OverSpec launched that package from its menu four times. All four combinations showed the selected cheats, the Ocean loading picture and movement in the first room. In each run, 2,618 room pixels changed after holding Q and P. The bare builds use at most bank 47 and carry no construction sites for the three game RAM banks.

## Hardware checklist and open work

On a physical Next, open the NXC with both cheats off. Check the loading picture and the switch to the keyboard menu. Walk behind scenery, pick up an item, change rooms and restart. Compare busy-room pace and beeper sound with the Spectrum game. Try a contact with each cheat alone and both together. Record the board, core and NextZXOS version with the results. Full-game completion, physical loader behaviour and native audio timing are open.

Techniques: `patch.whole-altrom-image`, `patch.loader-screen-from-game-file`, `detect.buffer-layout-producer`, `detect.tracked-unit`, `detect.drawing-parameters`. The build recipe is in `docs/records/batman.json`.

## Technique use

- patch.whole-altrom-image: used to supply the Sinclair ROM byte read through a null object link.
- patch.loader-screen-from-game-file: helped select the SCR1 route for the snapshot target.
- detect.buffer-layout-producer: helped trace the screen copy to the six-byte-stride rectangle and its writers.
- detect.tracked-unit: helped distinguish player fragments, object links and reused node addresses.
- detect.drawing-parameters: helped verify register, mask, ink, width and row-wrap assumptions on actual returns.

## Lessons

- [local: Batman drawing order] A black pixel can belong to the player or to a later object. Colour equality lost the distinction 841,229 times.
- [local: Batman object lists] The two player links can be drawn when absent from the scheduled-update list. Room art and pickups also reuse graphic IDs.
- [local: Batman empty object link] A null link leads the geometry routine to byte 2 of the Sinclair ROM. Restoring all RAM at entry alone did not reproduce play.

## Friction

- reuse: [local: Batman renderer] Reused the existing plain bootstrap and kept the masked-plot measurements in the Batman module.
- retries: [local: Batman menu state] Replaying archive input from the player's snapshot failed late. A separate scripted run covers that exact start.
- environment: [none: the supplied interpreter, emulator and private staging paths sufficed]
- hand-rolled: [local: Batman depth] A per-bit player owner model measures black-on-black occlusion independently of final ink.
- scratch: [local: Batman diagnostic evidence] Raw captures, trainer branches and work probes stay in the pilot directory. The reproducible plot check is in the repository.

## Stage log

- 2026-11-28, stages 0 and 1, about 23 minutes, roughly 90 tool calls, no owner rounds. Investigated the Head Over Heels code for its display target, geometry and boot restoration. Recorded the feasibility blocker and delivered the separately labelled plain diagnostic.
- 2026-11-28, stages 2 and 3. The maintainer chose the original presentation for 1.0. Both full recordings passed. The 371-second ROM audit found all four used ROM bytes correct on both outputs for each recording. The rebuild and verification were stamped. Delivered the NXC, target, player instructions and four captures for hardware review.
