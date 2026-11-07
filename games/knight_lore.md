# Knight Lore (Ultimate Play The Game, 1984; 48K) - engine `knight_lore` (pilot game: emulator only)

## Next session
Stage: 4 (owner review + hardware). Hardware: untested. The owner approved the Enhanced look and the room floors
("knight lore is good!", 2026-11-07); the .nxc v1.0 review package awaits his play.
Repository layout (2026-11-07, on main 213a238): `nexclash/knight_lore.py`, `asm/knight_lore_hooks.asm` with its
includes `asm/knight_lore_{packed,actor,grid_commit,sprite_cache}.asm` and `asm/knight_lore_palette.inc`,
`docs/profiles/knight_lore.json`, `docs/profiles/knight_lore_sound_sites.json`. Build:
`python -m nexclash.knight_lore SNAPSHOT ASSETS OUT.nex` (Enhanced) or `... SNAPSHOT - OUT.nex --original` (default).
ASSETS (page-*.bin, floor-selector.bin) are Spec256-derived art: private reference inputs, never in the repository.
Registered (2026-11-07): `is_knight_lore` in nexclash/engines.py (profile signature at 55044, 48K only); `auto`
builds the default `knight_lore.nex` and boot-checks it (registers with R, RAM, converter loader and NEXLOAD), and
docs/records/knight_lore.json makes `selftest --game knight_lore` rebuild it (MD5). The Enhanced set needs the private
ASSETS, so selftest does not rebuild it. `verify` and `unit_tests` raise NotImplementedError (as New Zealand Story's):
not done: an in-repository verifier and unit tests, and a generic `selftest --verify --stamp`; the proof recipes are the
pilot run's (runs/knight_lore/release-20261106/work). Both builds made from this repository are byte-identical to the
pilot's frozen ones, so its proof carries.

## Input and presentation
Target `Knight Lore (1984)(Ultimate Play The Game).z80`, MD5 `0f2006bf897b786f48e8dd3d68924046`, the original 48K
beeper game. The build input is a bootstrap of it (pilot `work/bootstrap.py`, MD5 `af32432ce87b3b094fadfe379f3abe1d`).
Default: the original game unchanged (its rooms are monochrome: no clash), with the whole Sinclair alt ROM.
Enhanced, off by default: painted figures from the Spec256 conversion's colours over the original room geometry, and
four floors (Spec256 backgrounds) chosen per room from the original room records: 46 square, 34 narrow X, 24 narrow Y,
24 grass/fence. Colour credit: the Spec256 team. Patch by Jon Attree.
The source art had graphic 89 flipped vertically in place; after normalising, all 15,366 unique mask/ink bytes match
the original. All 186 graphic IDs are decoded from the original table. Only the player's exterior black mask padding is
trimmed; original ink, coloured pixels, enclosed black and other figures' masks stay. No white edge is added.

## Renderer
The original's complete clear/plot order is kept. A colour canvas holds the exact final pixels: dynamic colours 0..125
and static duplicates 128..253 share the same RGB9 entries; 254 passes the original ULA ink through and 255 is
transparent, so no second ownership plane is written. Source X orientations are precomputed; Y orientation walks the
source rows in reverse. Opaque black stays opaque.
Dynamic pixels become native 16x16 screen-grid hardware sprites. A 256-byte comparison follows every cache-hash match;
live patterns and this publication's patterns are never replaced. Layer 2 holds static pixels, with holes under the
hardware figures. Two display buffers keep separate dirty bits. A cache-union overflow uses an exact full-colour staging
frame before rebuilding the sprites. The 128-room initial-state census peaks at 50 dynamic tiles (initial states only).
Publication covers every old/new active sprite row and every changed Layer 2 row; retired sprites keep their old X/Y
while disabled. The upload and flip finish inside a reserved 14-line interval; full-screen redraws need vertical blank.

## CPU, memory and original pace
Shared hlib_iff, hlib_speed, hlib_r, hlib_pace and the ordinary-DMA capability/fallback (hlib_dma), unchanged. Both
builds carry the whole hidden Sinclair ROM. A 53-byte temporary start-up tail restores the RAM it overwrote and every
original entry register, R included, before resuming.
Enhanced runs the original actor and drawing spans at 28 MHz. Whole sound effects and the pause routine run at the
incoming clock, with their own silence delays, call depth, I/O values and carrier periods. Game-over and new-game exits
close an open actor window and restore the incoming speed.
Added rendering cost is repaid from the original pure delay at B035: its 33,285 T budget, 5,121 M1 increments and final
AF/HL/B are kept; the outer DJNZ stays original. A paced replacement of a pure wait, not every original delay opcode.
Pace is counted at AFC7 with IX 23560 (the player's own update) against the same original state and R seed.
Highest loaded 16K bank 47 (hidden ROM pages 94/95): fits the loader's 1MB allocation. No AY music in the original.
Recorded gameplay hook entries all have interrupts off. Synthetic accepted-IRQ tests are scoped apart: no ISR R
contribution is claimed for an artificial interrupt inside R capture/restore. No ISR wrapper in this IFF0 game.

## Pace (JNext 1.1.104, three R seeds a scene)
| Scene | U20-200 | U20-221 | U1-221 |
|---|---|---|---|
| busy room 12 | -0.83, -0.68, -0.16% | -0.37, -0.85, +0.35% | +0.17, -0.92, +1.45% |
| quiet room 44 | +1.72, +1.74, +1.68% | +1.74, +1.75, +1.63% | +1.77, +1.82, +1.71% |
| sound room E3 | -1.25, -1.02, -1.25% | -1.04, -1.14, -1.28% | -0.28, -0.36, -0.48% |

All 1,989 paired player states equal (R, registers, objects, room, XYZ, lives, IFF). Cold redraw: the original's room
draw (update 2) takes 391 ms (room 44), 543 ms (room 12), 601 ms (room E3); Enhanced adds about 70 ms to it and 100 to
140 ms to the next update, about 0.2 s per room entry, then the limiter repays it.

## Trainers
Six archive trainers, behaviour-checked against this release: infinite lives; infinite days; stop the visible sundial;
nine starting lives; any object in the cauldron; werewolf safe at the cauldron. The last branch operand is translated
from 20 to 23: 20 lands inside an instruction, 23 skips the lethal change and keeps visibility. The sundial option
freezes the visible cycle, not the hidden phase counter. Nine lives writes 10, as the first respawn decrements it.
Inventory, parameterised or one-shot day changes, duplicate lives and novelty options are left out.

## Evidence (pilot run release-20261106)
- Two 24,000-frame input recordings: 16,212 publication checks against original registers, game RAM, object state,
  the monochrome bitmap and an independent ordered colour oracle (exact hook bytes and dead stack excluded). Menus,
  transformations, deaths, game over and restart. 9 of 9 broken controls detected.
- Six native 12,000-frame soaks: 20,385 player updates, no errors, no sprite overflow, no beeper write at the wrong clock.
  Publication: 1,980 samples safe; the unsafe-wait negative fails 121 of 220. Eighteen published pictures match.
- 248 hook ABI cases, 128 whole-sound wrapper cases, 300 compositor cases, cache collision/eviction/protection cases.
- Real dot-command loader on disposable card copies: default, Enhanced and Enhanced with all six trainers byte-exact.
Frozen hook ROM SHA-256 `10083e7dba7eaacf630e98646587aa232c435c78136693e4bbf40b8c91d117a2`.
Known issues: a room entry costs about 0.2 s more than the original before the limiter repays it. Synthetic IFF1
interrupts inside R capture/restore can lose the ISR's R contribution (gameplay is IFF0). Missing: hardware; natural
full-game completion; a generic verify and stamp.

## Hardware checklist
Default and Enhanced: room entries (pause length against the original), transformations, deaths, the cauldron, each
trainer, the loading screen; look for tearing at publication; beeper effects against the original. Record board/core.

## Lessons
- [local: the original Filmation masks establish this game's ownership] A final monochrome buffer does not establish
  coloured pixel ownership; keep the original opaque masks and plot order, coincident ink included.
- [local: this game's overlapping static blocks invalidate its candidate filter] Geometry-only redraw filtering failed:
  an unchanged overlapping static block can repaint colours outside a moving actor's old/new bounds.
- [local: this approved palette fits the tagged encoding exactly] Tagged palette duplicates remove an owner plane.
- [local: this archive bootstrap and ROM baseline differ] R must match at player updates, including the bootstrap and
  hidden ROM; a plain NEX on a different ROM is not a valid original baseline.
- [local: this game's death route returns to a quiet room] A busy fixture that dies and returns to a quiet room cannot
  give busy-scene pace from its average: compare sustained busy periods.
- [local: the measured compositor spans exceed this game's video frame] Account held work in bounded chunks; a
  multi-frame hold cannot come off a modulo-one-frame line interval without checkpoints.
- [local: this game's cache has independently tested collisions] Pattern hashes only narrow the search; compare bytes.
- [doc docs/LEARNING.md §1. Source refresh and verification freeze] Integration onto main 213a238 (2026-11-07):
  includes moved into asm/, the palette INCBIN turned into DB lines, private art read from a directory: the profile and
  both NEX files rebuild byte for byte, so the proof carried; shown by rebuilding, not assumed.
- [local: this game's Enhanced art is a private input] Register what the repository can rebuild: `auto` and the record
  cover the default build only; a build that needs private files keeps its own command and is named as such.

## Friction
- reuse: [local: the Filmation renderer is per game; Alien 8 has its own copy]
- retries: [local: pace candidates before the bounded held-time accounting are superseded and kept as diagnosis]
- environment: [local: the run-relative includes and INCBIN needed moving for a repository build]
- hand-rolled: [local: replay oracle, native pace and loader checks are pilot scripts, not toolkit commands]
- scratch: [none: no scratch files in the toolkit]

## Technique use
- patch.whole-altrom-image: used; both modes restore the complete Sinclair ROM and erase the start-up tail.
- patch.pace-limiter: used; bounded actor/drawing windows and original pure-wait debt match the scene pace.
- patch.display-atomic-switch: used; protected live patterns and one bounded sprite/Layer 2 publication.

## Stage log
2026-11-07: release round in the pilot: approved art and floors, renderer, pace, replays, soaks, real-loader checks.
2026-11-07: integrated on main 213a238 (branch nexttang/knight-lore-1.0): repository-relative includes and assets,
byte-identical rebuild of the profile and both builds; selftest --tools and --canary, asm2profile --check, doccheck
PASS; .nxc v1.0 review package with real-loader runs on NextZXOS v2.09 and 26.11 card copies.
2026-11-07: engine registered (detector, `auto` for the default build with a boot check, record); rebased on b37b4f3.
