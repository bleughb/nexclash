# Solomon's Key (U.S. Gold / Probe, 1987, 48K) - engine `solomons_key` (pilot game: unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-05 (record solomons_key); JNext only, never on a Next.
Inputs: specnext/reference/solomons_key/ (solomons_key.z80 md5 23ee5b21 = TOSEC "Solomon's Key (1987)(U.S. Gold).z80";
sk_d1, sk_o1, sk_l0, sk_l1, sk_h1, sk_x1). Verify with NEXCLASH_NEXT_ROM = enNextZX.rom from the card.
Start with: the hardware checklist below. Open: under "Open".

Techniques: `detect.gameplay-screen-readers`, `patch.whole-altrom-image`, `patch.restore-speed`, `patch.preserve-r`,
`patch.pace-limiter`, `verify.update-locked-pace` (recipe and results: docs/records/solomons_key.json)

## Import (2026-11-05)
Ported from Jon Attree's .nxc work, 2026-11-05 (pilot clone runs/solomons_key/nexclash, base d7abd1c, head 2d3cdaf). The
owner approved the look of that build in JNext on 2026-11-03 (solomons_key_sprites.nex 962b1671: bright white ink, black
solid body) and its Spec256 set 3ac85f5d ("good"). Its .nxc was never published. A new build, not a byte rebuild: the
pattern bank and the Enhanced palette are byte-equal to the approved builds' (pilot work2/enhanced.py); the hooks move.
- Hooks in alt ROM image 1 at 0x386E (patch.whole-altrom-image), the whole image Sinclair's ROM: the game's delay 39194
  LDIRs ROM 0x0000-0x01F3 onto itself, and the old slot-1 page left that on NextZXOS's ROM3 (the ROM path check failed).
  The hooks' state is in page SPAGE at slot 6 (0xC000) inside a hook only: the stack is at the top of memory.
- e_plot, post and e_cls at 28 MHz with the caller's speed latched and restored (patch.restore-speed); e_pad at the
  caller's clock.
- R as the original's (patch.preserve-r; the game reads R at 53434 for the beeper's noise).
- Pace ORIGINAL (patch.pace-limiter's debt, at the game's own clock): below.
- The tape's loading screen (a standard SCREEN$ block of the TOSEC .tap) held before the title, lunar_jetman's stub.
Published .nxc: Solomon's Key v1.0 (pilot runs/solomons_key/out/solomons_key_v1.0.nxc), target the TOSEC .z80.

## Pace (2026-11-05)
No interrupts and no frame sync: a pass's time is its work, and 38032 pads each pass with (10 - figures) calls of the delay
39194 (LDIR of BC = 500: 10,605 T each). Every hook adds its time over the original's to a debt (32 bits, 1/256 steps of
21 T, `dadd`; each path's time a constant K_* measured on the verifier, and LOWT per dirty block: the post loop's own time
plus the blit's extra contention, as the build's blit reads the clean copy (rows 104-191 in contended memory, where the
original's compose buffer is not; LOWC = 2.3 T a byte, measured in JNext: a build with only that change +0.39 %)). e_pad
(CALL 39194 in the padding) runs the delay up to 499 steps shorter and leaves its own time in the debt; over CAP (2,048
steps) after a pad the rest is let go. The verifier checks every hook's debt change against its modelled time over the
original's (_time: real time at the hook's clocks, 28 MHz = T / 8) at every event of every recording.

## Inputs
Snapshot: archive "Solomon's Key (1987)(U.S. Gold).z80", md5 23ee5b2123dbc8a9a5daccbd51db4db0, no [t], [h], [c] or [a]. ZXDB lookup answered 502, so the entry is not confirmed. 48K, title menu, music playing, DI; PC in RAM, no BASIC involved. No 128K release in the archive. All the game's 18 rooms (0-16, secret 20) are in this file: no multiload.
Keys: 1 starts, held until the tune reaches its key test (a press of about 2 s). O left, P right, Q jump, A crouch, SPACE make or break a block, V fireball, CAPS + SYMBOL pause. Keyboard is the menu's default.
Recordings, no Fuse and no human: work/rec.py, random walks. Cheats change bytes in the RZX's own snapshot, never a build.
| Recording | Cheats | Reaches |
|---|---|---|
| sk_o1 | none | room 0, six lives lost to the timer, game over, high score table, title, restart |
| sk_d1 | lives, time, fireballs, room skip | rooms 0-14, with deaths by enemies |
| sk_l0 | + immunity | rooms 0-16 |
| sk_l1 | + immunity | rooms 0-14, another seed |
| sk_h1 | + immunity, starts in room 20 | the secret room |
| sk_x1 | door open and always reached | the level end's own path through all rooms, wrap after room 16 |
Room skip: the game's own unused debug routine 38009 ('0' next, '9' previous) called in place of the QWERT restart test.
Plot callers: NOT reached: 46771, 46930, 53910, 54072 (enemy states; all go through the same entry hook). Levels were walked at random: no room was solved by play, and the door and key routes were forced in sk_x1.

## Clash
Kind A. work/census.py at the end of each draw pass, rooms 0-16 (sk_l0): 35.0 % of plots span several attribute values, 4.7 % of figure ink pixels show a colour other than white. Room 0 alone (sk_o1): 9.6 % and 2.5 %. Figures never write attributes and have no colour of their own: they take the ink of whichever cell they cross, white on brick, cyan or yellow on a block. Scenery's colours never change. Menu: controls only, no option changes the drawing. Owner's eye: clash (queue); numbers agree.

## Rendering model
Back-buffer composer. Clean scenery at 0x5B00, compose buffer at 0x7300, each 32 x 192. Main loop 37799: 38712 restores last pass's dirty blocks clean -> compose, the logic plots figures, 38551 copies each dirty 3 x 16 block compose -> screen. One plotter, 38093: A frame, E x, D y, 16 lines x 2 bytes mask then graphics at 56866 + 64A, AND then OR. Self-modified 38146 (LD D,115) is 91 while 39554 stamps scenery into the clean copy. Interrupts off all game: no ISR (`isr`: 0 accepted). No frame sync: 38032 pads the pass by the number of plots.
Player: 43209 mirrors frames 48-58 in place when he turns, toggling (43300). Hardware mirror does the same, read at plot time.
Readers of the screen: none in play (scan); ROM: only the delay LDIR at 39203, which copies memory onto itself and is harmless with the hook page mapped.

## Design (defaults, unattended)
| Site | Original | Now |
|---|---|---|
| 38093 | PUSH AF, BC, DE | log the plot if 38146 = 115, then the same |
| 37970 | CALL 38551 | CALL e_cp: the blit, then the log as sprites, the rest hidden |
| 38584, 38656 | LD B,115 | LD B,91: the blit's source is the clean copy |
| 39097 | LD HL,23295 | hide all, empty the log; the screen clear before every other screen |
| 38047 | CALL 39194 (operand) | CALL e_pad: the pass padding's delay, shorter by the debt |
Every byte of game memory stays as the original's, the screen's figures apart. Hooks in alt ROM image 1 (0x386E-0x3AFC),
state in page 24 at slot 6 inside a hook. Sprites: one 16 x 16 4-bit per plot, in plot order, patterns for frames 0-127
uploaded once at start from bank 11. Nibbles: 1 bright white ink, 2 black solid body (mask 0, graphic 0), 0 transparent.
Clip y >= 8, as the blit leaves the HUD line alone. Tail at 0x9000: the tile map, cleared before any read at every level
build. Hook cost (verifier, real time at 28 MHz): plot 199 T, commit 261 T + 60 T a sprite + 16 T a dirty block, against
a pass of about 175,000 T; all of it repaid in padded passes.

## Differences from the original, by design
Accepted by the verifier only after recomputing the byte: (1) a mid-pass restore (38730, a tile changes under a figure) wipes figures from the compose buffer, so the original blinks them off for a pass; a sprite stays. (2) A tile stamped after this pass's restore shows a pass sooner. And F': the blit's last ADD HL,BC sets H and bits 3, 5 from the source address; every EX AF,AF' in live code (38604, 38634, 38676, 38706, 39638, 39643, music 48957-48996) overwrites the flags before any test, so no code reads it.

## Results (2026-11-05; simulation only)
Builds: solomons_key.nex 3ad529e4, solomons_key_sprites.nex 80e83ae3, Enhanced a3971c4b (pilot work2/enhanced.py; bank 11
and the setup's 16 palette bytes only), with the loading screen 00958c19 / 0e5b3281 (loading_nex); boot OK.
| Recording | Frames | Blits | Plots | Clears | Pads | Padded passes, no debt left | Verify |
|---|---|---|---|---|---|---|---|
| sk_d1 | 26884 | 8489 | 52875 | 37 | 35457 | 7083 of 7209 | IDENTICAL |
| sk_o1 | 45189 | 11995 | 57569 | 30 | 62655 | 11995 of 11995 | IDENTICAL |
| sk_l0 | 52454 | 17966 | 125645 | 18 | 61785 | 13819 of 14031 | IDENTICAL |
| sk_l1 | 52428 | 15375 | 115355 | 15 | 44587 | 10777 of 11026 | IDENTICAL |
| sk_h1 | 3216 | 1049 | 8935 | 1 | 1643 | 960 of 979 | IDENTICAL |
| sk_x1 | 5193 | 0 | 1772 | 43 | 0 | - | IDENTICAL |
Every hook ran (plot, commit, clear, pad; sk_x1 has no blits). Every hook's debt change equals its modelled time over the
original's at every event (pilot work2/verify_all.py). Unit PASS: 128 frames, 8 edges, order, rest hidden, full log,
scenery, clear, mirror flag, 16 pad cases (debt 0 to 2^24 steps), setup; every-site clock matrix 196 cases. ROM paths:
both builds, every ROM byte the game runs or reads as recorded (the delay's 500 bytes); the tail never read before written.
Negatives on sk_d1 2,000 frames, 12 of 12 DETECTED: plot logs x as y, plot hook clobbers HL, commit loses x bit 8, commit
drops N6, old sprites stay, mirror flag ignored, R one off after a plot, plot time not in the debt, pad delay length wrong,
pad flags wrong, forced 3.5 MHz exit (replayed at 7 MHz), blit source not changed.
JNext 1.1.104 (pilot runs/solomons_key/jn2), pace: pilot work2/trials.py, probe 37799, lockstep on the pass and bonus
counters, 10 trials a scene, 400 passes each:
| Scene | approved build 962b1671 | this build | Enhanced, approved 3ac85f5d | Enhanced, this build |
|---|---|---|---|---|
| quiet | +2.11 % | +0.12 % | +2.11 % | +0.12 % |
| busy | +2.06 % | +0.15 % | +2.08 % | +0.15 % |
| sound (fireballs, blocks) | +2.02 % | +0.09 % | +2.05 % | +0.09 % |
| level 10, busy (fixture, 5 trials) | +2.19 % | -0.01 % | | |
FLICKER-SOAK-PENDING

## Defaults taken (a human would have decided)
1. Every figure a sprite, including block flashes, enemies, the player, fireballs, flames. 2. Scenery, HUD, text on the ULA; also blocks, the door, key and items, which the game stamps into the clean copy and so never had clash of their own. 3. Depth: plot order, all over the scenery. 4. Colours: bright white ink, as on an empty cell; black solid body. 5. A blink in the original (above) is not reproduced.

## Lessons
- [local: a mirrored-in-place frame set looks like corrupt sprites until the graphics are compared with the snapshot at run time] The first composite check failed on the player only; a diff of the graphics between frames found 43209.
- [local: a composite check against the original's screen finds the game's own one-pass glitches] Both one-pass effects above came from the check, not from reading the code.
- [local: skipping past the last room by the debug routine crashes the game into ROM and poisons every later scan] A recording that ran past room 16 showed ROM writers and made free memory look used: read the level count first.
- [local: an instruction count per recording says nothing of the state of the scan] 'untouched' from one room is not 'untouched': room 0's free memory held other rooms' data, so the tail moved to write-first memory proven on all rooms.
- [local: a tune without interrupts tests its keys only between notes] Single key presses are missed for seconds at this menu.
- [local: this game's pace] demonstrated: the game pads each pass to ten figures' time with its own delay, so every hook's time can be repaid there to the T-state; a debt with a constant time for every path, checked at every event, gave +0.1 % in JNext against the approved build's +2.1 %.
- [local: this game's blit] demonstrated: the build's blit source (the clean copy, all in contended memory) costs time the original's compose buffer did not (+0.39 % with no other change); counted in the debt as 2.3 T a byte of rows 104-191.
- [local: this engine's model] observed: the 2026-11-03 verifier ran NEXTREG in 0 T (its own ED handlers); z80n.install counts 20 / 17 T, which the pace accounting needs.
- [local: this game's stack] observed: the stack is at the top of memory, so the state page maps at slot 6, not 7.

## Friction
- reuse: [local: the debt and pad method is this engine's; card patch.pace-limiter names a raster limiter, not a delay to shorten]
- retries: [local: a 24-bit debt wrapped in long unpadded stretches and a 16-bit block sum overflowed; both found by the per-event check]
- environment: [local: NEXCLASH_NEXT_ROM (enNextZX.rom) and NEXCLASH_JNEXT_CARD point into other pilot runs, read only]
- hand-rolled: [local: the real-time model (_runt: 28 MHz = T / 8) is this verifier's]
- scratch: [none: scratch scripts stay in the pilot run folder, none added to the repo]

## Technique use
- detect.gameplay-screen-readers: helped: no reader of the screen in play, so the ULA may differ.
- patch.whole-altrom-image: helped: the ROM path check found the delay reading NextZXOS's ROM3 under the old slot-1 page.
- patch.restore-speed: helped: the 7 MHz replay and the matrix caught the forced exit.
- patch.preserve-r: helped: R compared at every hook.
- patch.pace-limiter: helped: its debt idea, repaid by the game's own padding instead of a wait on the raster.
- patch.scratch-redirect: no help: inverted, the blit reads the clean copy and the plotter is untouched (as Altered Beast).
- optimise.pattern-cache: no help: static graphics, all frames fit the pattern memory, so nothing to cache.

## Hardware checklist (nothing here has run on hardware)
1. Loads to the tape's loading screen (5 s or a key), then the title with the tune; hold 1 about 2 s: room 0 builds.
2. White figures stay white over cyan and yellow blocks; no black blocks around them; the HUD line unclipped.
3. Player turns: mirror matches direction, no flash. SPACE makes and breaks blocks under him.
4. Game over, high score entry, title, restart: no figures left over the screens.
5. V fireball, secret room, every enemy kind: nothing missing. Enhanced (menu): the painted colours.
6. Pace: the bonus counts down as in the plain build, in a quiet room and a busy one; F8 mid-game keeps its speed.

## Stage log
- 2026-11-03 stages 0-3 in one session (batch, unattended): stage 0-1 20 min, stage 2 15, stage 3 20, about 45 tool calls, 0 user rounds.
- 2026-11-05 import (pilot runs/solomons_key/nexclash2 on refactor-final f6b8ac0): hooks in the whole alt ROM image, 28 MHz
  with the speed latch, R, the pace debt repaid at the padding, every-site matrix, negatives, loading screen, pace / flicker /
  soak in JNext, .nxc v1.0.

## Open
- Hardware, CSpect: never run.
- Rooms never solved by play; the 4 unreached callers; level-end reached only by cheat.
- Passes with ten figures or more have no padding: their hooks' time (about 2 % of such a pass) is repaid by the next
  padded passes, up to CAP; the contention charge is an average.
