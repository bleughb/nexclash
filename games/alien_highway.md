# Alien Highway

Vortex, 1986. Version 1.0 builds a tape-target NXC with hardware sprites and two optional trainers. The original game draws the visible figures while its road copier is running. The hardware layer returns when its new patterns and colours are ready.

## Inputs and boot

The recording starts at $89CA with SP=$FFFF, IM 2 and interrupts disabled. Both archive recordings are the same 53,962 frames and have one snapshot. The main Z80 is still in BASIC PAUSE at $1F3E. The main Vortex Speedlock TZX supplies only 208 bytes of the required state through the toolkit. The TOSEC TAP in the record supplies 47,221 bytes in 14 copies. Six residual runs hold 555 bytes of start-state data. Zero instruction executions overlapped them during the entire recording. The reconstructed 48K RAM is exact. Its 6,912-byte loading screen begins at tape offset 1,989.

The plain and sprite NEXes use an untouched startup tail at $6EB0. A 339-byte span was available. Both tails use 53 bytes. The plain build uses the original 48K ROM, including the byte the recording reads at $0004. The original printer buffer is preserved. DivMMC automap starts disabled. Ordinary and NEXLOAD starts return to the original entry state in simulation. Record inputs, dependencies and output hashes are in docs/records/alien_highway.json.

## Renderer and scope

Highway Encounter's four masked plotters match the first 16 normalized instructions at all four entries. Its sorter matches 15/16. The scene builder matches 5/16 and the copier 9/16. The scene and screen-copy addresses were identified from Alien Highway's recording. All four plotters still execute. They also accumulate coverage for black and ink in a private plane. The visible figure image uses the game's depth order, working bitmap and road mask. It adds no outline. One uniform source attribute covered all figure pixels on every recorded completed draw, including the cyan title and a blackout.

The 18 road strips contain 363 cells. Their bounding tiles use 98 fixed hardware slots out of 128. At most 48 of those tiles had visible figure pixels in the host replay. Without batching the figures into common tiles, 8-by-8 pieces reached 156 slots. Preclipping a separate pattern for every figure and position needed 721 patterns. The renderer rotates a spare half-pattern and selects a new pattern after upload. It preserves original screen writes and uses original scenery beneath the sprites. Four bulk-clear paths and the scene entry discard stale figures at transitions.

Highway Encounter times sprite changes against its screen copy. Here all ten callers enter the copier at $913D. That hook hides the sprite layer before the first game write. The return path uploads the new tile patterns, sets the palette, then shows the layer. The same rule covers stationary figures when the road moves beneath them. Four bulk clears also hide the layer before a scene change. The game continues reading and writing its ULA screen.

Sorting stays at the incoming clock. A hook at $8F6C starts accelerated drawing. The four plot counts and number of dirty road cells determine the original work budget. The hook measures time already spent and waits out the remainder. The 20,091 measured sort-to-copy intervals contained zero game input or sound operations. Uploads use the toolkit's DMA sprite-port transfer or its OTIR CPU fallback.

## Verification

| Measurement | Outcome |
| --- | --- |
| Original route | 53,962 recorded frames. Both archive copies are byte-identical. The run covered 31 gameplay zones and reached zone 32 at completion. 10/10 copier callers, 4/4 scene callers, 49 scene builds and 0 accepted interrupts. |
| Figure activity | 151,780 plot calls, 60 graphics, 211 source/phase pairs, 20,092 road copies. |
| Completed drawings | An independent original-plotter comparison checked 30,627,337 figure pixels. Zero differed. Removing the road mask caused 565,267 differences across 4,926 draws. |
| Original colours | 20,030 draws with white ink, 60 bright cyan, one black and one empty. Zero splits across a figure on this route. Both private sprite sheets contain 61 source records. |
| Three consecutive JNext windows | 116, 97 and 113 frames. Zero errors across 403,293 visible hardware pixels. The ULA carried the picture alone in 136 frames. The previous build had 14,576 wrong pixels in 89 of these 326 frames. |
| Three JNext pace trials | 300, 300 and 188 intervals. Elapsed time changed by +0.179%, +0.216% and +0.016%. All 20-update windows fell within -0.812% to +0.311%. |
| Native update state | R, X, Y, zone and energy matched on 791/791 updates. All three 6,912-byte screens matched. The hardware covered 2,752, 1,762 and 1,618 correct pixels. |
| Transfer selection in JNext | 3,293 uploads per path, 101 intervals, elapsed time +0.200% with DMA and +0.196% with CPU. Both matched 102/102 states and 2,752/2,752 hardware pixels. |
| Engine controls | 12/12 mutated patch sites refused. 244/244 masks matched the original plotters. All four broken masks and one bad palette were detected. |
| 2,000-frame timing control | Fixed build had zero wrong pixels. Removing only the four-byte copy-entry hide produced 42,036 wrong pixels at 235 recording boundaries and 51,179 at scanout in 309 physical frames. |
| Full native replay | 53,962 recorded boundaries, 20,092 publications and 30,627,337 independently checked figure pixels. Zero wrong pixels in 63,495,697 boundary samples or 58,395,736 scanout samples. Elapsed time +0.155%. |
| Full timing control | Removing only the four-byte hide restored 1,265,702 wrong boundary pixels on 7,996 frames and 1,607,237 wrong scanout pixels on 10,757 physical frames. All 20,092 completed images still matched. |
| Full forced-CPU replay | Same 53,962 frames, 20,092 publications and 63,495,697 boundary pixels. Zero wrong pixels in 56,766,654 scanout samples. Elapsed time +0.155%. |
| Original and release state | 1,615,027 recorded port inputs. Registers and game RAM CRC32 agreed at 53,949 frame boundaries and 212,111 hook returns. Rolling I/O hashes agreed for 108,207 screen reads and 3,198,116 even-port writes. Between SkoolKit and OverSpec only undocumented flag bits 3/5 differed on 2,220 boundaries. The two OverSpec builds agreed on those bits too. |

The native OverSpec probe replays the assembled original and the release, then repeats with only the copy-entry hide disabled. It compares the real ULA and sprite RGB at each recorded boundary and during scanout. An independent mask checks opacity at publication. Original game port reads supply the recorded inputs. Registers, game RAM checksums, screen-read and even-port output sequences are checked against the plain execution. Thirteen recording boundaries land inside displaced instructions. Those 13 samples use the enclosing hook return. Beam sampling continues through the hook.

## Trainers

- Infinite Time replaces DEC HL at $8935 with NOP. A captured timer update went from 1,500 to 1,499 with the option off and stayed at 1,500 with it on.
- Infinite Energy replaces RET Z at $99F3 with RET. Captured damage took energy from 21 to 19 with four changed HUD bytes. The option kept 21 with zero HUD changes.
- Both archive Immunity entries change the high address byte of LD HL,($9A31). On captured damage, the game writes to $612A/$612B instead of the HUD at $5284/$5285. The alternate entry also breaks CP $11 at $98E6, changes a damage-loop count from 30 to 35 and still allows energy loss. Both entries were dropped. The repeated Infinite Time entry was deduplicated.
- All four combinations of the retained trainers changed exactly 0, 1, 1 and 2 expected game bytes on both the original and sprite paths. Both trainers default to off.

The original Vortex Speedlock load at $89CA matches the recording's entire 49,152-byte RAM. At the same title poll the unflagged TOSEC Vortex TAP and unpacked main Z80 match the original throughout $8800 to $A8FE, including all five addresses in the supplied POK files, the energy reset and both defeat tests. Both defeat paths set the death flag with zero energy and leave it clear with 1 or 21. A further published variant at 39410 duplicates Infinite Energy on all 38 captured damage entries.

Two additional practice POKEs were derived independently. They are documented separately from the two 1.0 menu trainers.

- One-point damage (`POKE 39455,0`) ends the damage loop after one energy unit. All 38 captured damage entries returned the expected energy. A four-point hit took 16 to 15.
- Open the final barrier (`POKE 35334,8`) uses the regular removal path before all seven stations are charged. It removed the barrier on 43/43 recorded decisions with fewer than seven charges and matched stock on the six decisions at seven. In a late-game test the seventh charge was withheld just before the gate. With the POKE enabled at that decision, playback reached the ending at six and completed all 53,962 frames. Stock kept the barrier and diverged at frame 50,698. Applying the POKE from the title diverges from stock input timing at frame 617.

## Reproduction and hardware checklist

Use the inputs named in the record. Set NEXCLASH_JNEXT_CARD to a readable NextZXOS card image. Keep the pinned overspec-classic.zip beside the recording. The full verifier compiles a temporary observed core. With the maintainer environment and assembler ready, run from the checkout:

```sh
python tools/asm2profile.py --check alien_highway
python selftest.py --game alien_highway --verify --stamp
python nexclash.py patch "$NEXCLASH_REFERENCE/alien_highway/start.z80" --no-record --nex -o /tmp/alien-highway
```

- [ ] Cold boot the patch on a physical Next. Check the loading picture, menu options, keyboard start and DivMMC automap.
- [ ] Drive beside another figure, fire, take damage, change zones and restart. Watch the black edges while the road scrolls.
- [ ] Compare pace, screen transitions and beeper sound with the tape. Check DMA and CPU transfers on real cores and watch for raster tearing.
- [ ] Exercise both trainers independently and together. Check that timer and energy fall with both off.

## Stage log

- Stage 0. Identified the replay, recovered a tape target and reconstructed its start RAM.
- Stage 1. Mapped the four shared plotters. Chose the original colours, including black figure pixels, and applied hardware sprites to every figure drawn by those plotters.
- Stage 2. Built the overlay. Independent native windows caught stale edges after publication. Hiding the layer at the copier entry cleared all three windows. Whole-route replay exposed a pace difference that the short JNext trials missed. The limiter now budgets the actual original drawing work.

- Stage 3. Full verify and stamp passed on 2026-11-28. The native replay compiles the declared OverSpec archive. The two NEX outputs matched their recorded hashes.

## Lessons

- [local: the road has a stepped copy table] A rectangular footprint includes pixels the game never copies.
- [local: the copier spans frame boundaries] All 20,092 completed drawings can agree while a moving image still shows old edges. Test the beam as well as the completed image.
- [local: archive pokes change instruction operands] The damage write destination exposed both unsafe immunity entries.

## Friction

- reuse: [none: the original plotters and toolkit timing and transfer libraries covered the renderer]
- retries: [local: two failed publication positions] A global hide at copier entry gave the ULA sole ownership during updates.
- environment: [local: two emulator timing models] Whole-route timing required the original draw and dirty-cell counts.
- hand-rolled: [local: stepped road and copy timing] The original plotters provided the mask oracle. An instrumented OverSpec core sampled scanout.
- scratch: [local: private recording and emulator images] The shipped replay probe builds its temporary core in the test folder.

## Technique use

- patch.pace-limiter: used the original work budget for the draw and copy interval using original plotter and dirty-cell costs.
- verify.update-locked-pace: used paired update landmarks and sliding windows at three checkpoints.
- patch.scenery-edge-masks: used the original road-cell mask.

## Open and next session

Stage 4 needs a physical Next run. The recordings contain one distinct route. It had no original attribute split across a moving figure. Additional routes, physical raster and DMA timing, and exact audio waveform timing remain open. Enhanced colours are deferred.
