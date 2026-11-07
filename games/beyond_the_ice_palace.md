# Beyond the Ice Palace (Elite, 1988; 128K, AY) - engine `ice_palace` (emulator only)

## Next session
Stage: 4 (hardware + owner review)    State: registered engine, stamped 2026-11-06; JNext only, never on a Next.
Inputs: specnext/reference/beyond_the_ice_palace/ (beyond_the_ice_palace.z80 md5 1c1af477, intake / explore / death
recordings, the tape's loading screen .scr, the translated .pok). Verify with NEXCLASH_NEXT_ROM = enNextZX.rom.
Start with: the hardware checklist below. Open: under "Open".

Techniques: `detect.buffer-layout-producer`, `detect.tracked-unit`, `detect.drawing-parameters`, `patch.restore-speed`,
`patch.preserve-r`, `patch.pace-limiter` (recipe and results: docs/records/beyond_the_ice_palace.json)

Scope (Jon, 2026-11-06): archive cheats and an original-colour clash fix only. No Enhanced set, no outlines, no
repainting, no speed option. Patch by Jon Attree.

## Import (2026-11-06)
Ported from Jon Attree's private review build (pilot runs/beyond_the_ice_palace, clone base bd1528c), which was a
standalone module with its own run-folder harness. Now a registered engine (nexclash/engines.py, `auto`), the hook
bytes read from the profile, and the pilot's verifiers moved into the module (`verify`, `unit_tests`, `boot_check`)
with what they compare unchanged; `verify` also counts jumps into patched instructions and site bytes the game rewrites.
The build is byte-identical: `beyond_the_ice_palace_sprites_loading.nex` = the reviewed d53ac5f52471b674354caf96cd94221e.
- Pace library: main's asm/lib/hlib_pace.asm is the newer library, which moved every hook (another .nex). The engine
  DEFINEs HLIB_PACE_V1 (the first library byte for byte, as Cobra, Gryzor and Cauldron 1.1): the bytes it was verified
  with. Moving to the current library would need the JNext pace and real-loader proof again.
- Speed: already on the shared HLIB_SPEED_IN / _OUT latch (V_SPEED; the copier keeps its own across its exit hook).
- IFF: the hooks read no IFF; the two LD A,R are R as a value (hooklib.iff_audit 'value'). No DI added.
- No plain build: the snapshot's SP is in the paged top 16K, so the converter has no tail place; a tail at 0x5B00
  without the hooks' boot code is read by the game (intake frame 1353, PC 0x7089).
- Shared code (two small fixes, other builds unchanged): nextboot.load_nex skips a header loading screen (this is the
  first build with one); the ROM path check credits bytes a build's own boot code puts back before the game starts
  (nextboot.boot_restores; only builds whose tail jumps to boot code, not to the game).

## Source
Beyond the Ice Palace (1988)(Elite Systems)(128K).z80, MD5 1c1af4775bc0114f7b94edb7de2d4070. Real AY edition; bank 1
is used by the sound player. The loading screen is the matching tape's (6,912 bytes, record input). The boot restores
all original 0x5B00-0x5BFF bytes, registers and R, including after NEXLOAD has overwritten the printer buffer.

Cheats (the .nxc, all off by default): the archive's POK labelled 128K has 48K addresses. Translated by matching the
instructions, each executed with and without the change (pilot work/cheats.py):

| Cheat | Address | Original -> selected |
|---|---:|---:|
| Start with 99 lives | 0x6FFC | 09 -> 63 |
| Infinite lives | 0x7354 | 35 -> B6 |
| Immunity | 0x74E0 | 20 -> 18 |
| Immune to bats | 0x6AF9 | CC -> 3A |
| Infinite spirits | 0x717E | 35 -> B6 |

The original HUD shows at most nine hearts with 99 lives.

## Observed renderer
- Main update starts 0x6ABB; player pointer 0x9A09, camera X/Y 0x6DAE/0x6DB0. Main code disables interrupts and
  explicitly calls the sound service 0x7B93 between phases.
- Background bitmap: 0x6E18, linear 32-byte rows in 0xE400-0xF5FF. Clear at 0x6CDE.
- Figure plotter 0xBEE6: masked 32-row drawing, IDs in A (bit 7 mirror), world X in HL, Y in DE. Player callers
  0x7407 and 0x7457; enemy caller 0x7C9A. Mask lookup 0xF700; mirror table 0xF600; scratch 0xE200 for shifted graphics.
- Projectile plotter 0xBD9F, caller 0x8ECE: 16-row, 16-pixel drawing. Particle effect 0x7F86 draws directly with
  R-dependent pixels. Player damage routine 0x7499 XORs random pixels into the completed player bitmap.
- Figure colour boxes: player 0x9EC6, enemies 0x9E7B (original attributes 0x9F1E, flashing override). Background
  attribute routine 0x6CE7 runs afterwards, overwriting figure colours where tiles overlap: the visible clash.
- Screen copy 0x6C03 copies 28 columns, 128 bitmap rows and 16 attribute rows to ULA x16-239 / y64-191. Callers
  0x6B36, 0x79CF, 0x94D9. Back-buffer colours 0xE100-0xE33F.
- Plotter IDs: large 0-49 (63 an off-screen sentinel), small 0-13. Masks are built by running the original
  initialisers 0xE0D9 / 0xE0E9 and plotters on the player's snapshot (no graphics stored); unused IDs are transparent
  and flagged if met.

## Build design
Original drawing and collision buffers and gameplay routines stay intact. Visible plot calls are recorded; at the
screen copy the completed bitmap of each figure goes through its original mask into hardware patterns, so damage
sparkle and overlaps stay. The ULA bitmap is unchanged; scenery attributes come from a clean background pass; figures
are sprites in their original ink. No outline. Hooks restore the incoming speed, MMU and R. Pattern uploads use
alternate halves; attributes are published together. Empty quadrants are skipped. 64 quadrants an update (peak 24 in
the recordings, 26 in native busy captures). The copier window runs preparation at 28 MHz, then the pace limiter
waits for the original's time. Hooks add no DI.

## Verify (what it checks)
`auto` / `selftest.py --game beyond_the_ice_palace --verify`: per recording, two replays. Paired calls: every hook call
run original and patched from the same state; all registers with R and PC, NextREGs 7 / 0x50 / 0x55 back, memory
outside the sites, the dead stack and (copier) the attribute rows, the original's I/O; jumps into patched
instructions; site bytes. Pixel oracle: after each screen copy, the sprite layer against the original plotters run on
black / white buffers for every figure drawn since (no hook table used); a wrong-x negative. Boot tail with and
without NEXLOAD. Unit: every site at four incoming clocks (0x79CF from a copier state), 64 IDs x mirror x phase and the
viewport edges, eight broken builds (R, speed, MMU, position, mask, reset, one pattern buffer, no limiter).
The recordings are scripted keys from the pilot's 128K frame model (no human player); death.rzx starts from a
one-life fixture (explore's frame 9,999, 0x7AC0 = 1, 0x7AD1 bit 5 cleared).

## Results
Stamped run (`selftest.py --game beyond_the_ice_palace --verify --stamp`, 2026-11-06, NextZXOS ROM3 of enNextZX.rom
modelled; simulation only), on main with HLIB_PACE_V1:
- Rebuild: `beyond_the_ice_palace_sprites_loading.nex` d53ac5f5 (the reviewed build), `_sprites.nex` da668eb8.
- Verify IDENTICAL: 24,700 frames, 105,855 paired calls with R (intake 8,437, explore 93,819, death 3,599), as in the
  pilot; no jump into a patched instruction, no site rewritten. Pixel oracle: 4,644 screen copies, 2,983,486 figure
  pixels, wrong-x negative detected on each recording; peak 24 quadrants, no overflow, no unknown ID.
- 7 of 8 sites reached (0x79CF by unit cases only). Unit: 32 clock cases, 298 figure / edge cases, 8 of 8 negatives.
- Boot: registers with R and RAM 0x4000-0xFFFF as the snapshot, plain start and after NEXLOAD.
- ROM path check pass on all three recordings (the tail put back by the boot code).

Pilot only (JNext 1.1.104; not rerun in the repo, the build is the same bytes):
- Pace, 3 scenes x 3 repeated 200-update trials, player update 0x6ABB: quiet 12.36677 -> 12.34548 Hz (-0.17 %), busy
  9.84945 -> 9.80012 (-0.50 %), sound-heavy 9.95241 -> 9.91541 (-0.37 %). Player state and R match each update.
- AY: busy and sound-heavy each give the same 3,068 ordered register / value writes; within an update the writes
  move by -1.56 to +7.17 ms (sample-identical audio is not claimed).
- Native pictures: the ULA bitmap identical; all 3,568 shown sprite pixels in three scenes match the snapshot's
  sprite layer.
- Real `.NEXCLASH` loader on private card copies: cheats off and all five on rebuilt byte for byte, reached play
  (294 / 279 updates), the live cheat bytes correct.

## Hardware checklist (nothing here has run on hardware)
- Starts on the tape's loading screen, then play; title music and in-game AY as the original.
- Player white against green / yellow scenery; bats green; scenery keeps its own colours with no colour box.
- Movement, jumping, shooting, spirit use; cave edges; death, respawn, game over and attract.
- Pace as the original in quiet and busy scenes.
- Each cheat alone and all together from the .nxc menu.

## Open
- Hardware: untested. Owner review of the build: not recorded.
- Full natural completion of every level: untested. 0x79CF has unit coverage only.
- The current pace library (without HLIB_PACE_V1): not adopted (new bytes; needs the JNext pace and loader proof).

## Lessons
- [tool nextboot.load_nex] demonstrated: the boot model read a .nex with a header loading screen (byte 10 = 2) as banks from offset 512 and failed to find the tail; it now skips the screen as NEXLOAD does (nex_screen_size). This is the first build with one.
- [tool nextboot.boot_restores] demonstrated: a tail that jumps to the build's own boot code, which puts 0x5B00-0x5BFF back, was reported as read before written; the ROM path check now boots on to the game's PC and credits bytes back to the snapshot's. Builds whose tail jumps to the game are unchanged.
- [tool asm/lib/hlib_pace.asm] observed: main's pace library moved this engine's bytes; DEFINE HLIB_PACE_V1 keeps the verified build (as Cobra, Gryzor and Cauldron 1.1).
- [local: this archive's mismatched trainer addresses] Match instructions and control flow before importing a release-labelled POK; all five translations are behaviour-tested.
- [local: this game's original effects read R] The particle and damage routines require R preservation even inside rendering.
- [local: this game's 32-row signed edge arithmetic] Use a 16-bit height test; treating positive Y=232 as negative created phantom pixels at the top.
- [local: this game's long preparation can cross a whole video frame] Sampling the pace timer after each object avoids missed wraps and busy-scene slowdown.

## Friction
- reuse: [local: the pilot's verifiers moved into the module unchanged in what they compare; nothing else to share]
- retries: [tool nextboot.boot_restores] the first `auto` failed the ROM path check twice (no tail found, then a tail the boot code had put back)
- environment: [local: the public reference repository is not used for this game's files; they are staged privately for the maintainers]
- hand-rolled: [none: the shared commands covered the port]
- scratch: [none: the pilot's run-folder scripts stay there (JNext pace, pictures, cheats, loader); none added to the repo]

## Technique use
- detect.buffer-layout-producer: helped: located the copier and its terrain / figure writers.
- detect.tracked-unit: helped: separated frame records from persistent game objects.
- detect.drawing-parameters: helped: derived both plotter families and their camera / clipping rules.
- patch.restore-speed: used: the shared latch; the every-site clock matrix covers it.
- patch.preserve-r: helped: the particle and damage effects read R.
- patch.pace-limiter: helped: ORIGINAL pace with a 28 MHz copier; the timer sampled after every object.

## Stage log
- 2026-11-06, stages 0-3 (pilot): original-colour clash fix and translated cheats built; replay, geometry, negatives,
  native pictures and pace passed; private review package.
- 2026-11-06, port (1 session, ~60 tool calls, no user rounds): registered engine, byte-identical on main with
  HLIB_PACE_V1; two nextboot fixes; stamped (Results).
