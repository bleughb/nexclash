# Pac-Mania (Grandslam / Teque, 1988; the 128K release, AY music) - engine `pacmania`

Techniques: `detect.tracked-unit`, `patch.restore-speed`, `patch.preserve-r` (docs/records/pac_mania.json)

## Next session
Stage: 4 (hardware + owner play)    State: v1.0 review build (2026-11-07), JNext and simulator only, never on a Next.
Inputs: pilot run folder runs/pac_mania: files128/pac_mania_128k.z80 (md5 e9cb908b), v1/rzx/pm_*.rzx (8 recordings),
v1/files/start128.z80 (their start state), v1/files/pac_mania_128k-verified.pok. Handoff: runs/pac_mania/HANDOFF-V1.0.md.
Start with: the owner's play of out/pac_mania_v1.0-menu.nex; then the hardware checklist below.
Read: this file. Open: everything under "Open".

## Inputs
Snapshot: archive "Pac-Mania (1988)(Grandslam)(128K).z80", md5 e9cb908bc86661ff81732665741393cc. 128K, 7FFD 0x10, PC 0x1F3D:
BASIC's PAUSE 0 over the loading screen, then the direct command's ': RANDOMIZE USR 30000'. All game code from 0x6000 up is
byte-identical to the 48K-128K file the pilot used (md5 8ea4557d), bar 0x764A-0x764B and 0xB329-0xB32A; bank 1 holds the AY
music. 0x7530 checks for bank 1 (writes 0x11 / 0x10 to 7FFD) and sets 0xB332 = 1: the 128K music plays. The 48K-128K file is a
48K snapshot: music off. The 128K[a][a] file (fccddb99) is not used.
Start: the build starts at 0x7530 with interrupts off (its first instructions are CPL, DI), all memory as in the file. The
PAUSE / USR path runs through the 128 editor (ROM 0) and the 0x5B00 ROM-switching code, which NEXLOAD overwrites; skipping it
costs only the key press. The loading screen shows while the .nex loads (bank 5 first). Recordings start from that state
(v1/files/start128.z80).
Keys: 1 start; at the round picture SPACE picks (K then SPACE: round 2); then Z left, X right, O up, K down, SPACE jump.
2-4 keyboard or joysticks, H the table, M music on / off.
Recordings (no human player; v1/work/rec.py, the pilot's scripts with 200 frames more at the start; Sinclair's 48K ROM as ROM 1):
pm_first (random keys), pm_idle (no moves: game over, title), pm_lives / pm_l4 / pm_l5 (random keys, 0x8945 NOP),
pm_rounds (0x8945 NOP, 0x9601 RET, 0x8BD9 LD HL,1: every round, interludes, ending), pm_b11 / pm_b12 (the pilot's chase bot
scripts, 0x8945 NOP). 96,520 frames.

## Rendering model
Back buffer + undo. 0xA8FA: save under each figure (A9CA, 0x5CCB up), sort by y (A93A; pointers 0xA982), plot (AE73). 0xB090: blit the window, columns 2-21 of the buffer, lines 8-183, to the ULA's columns 1-20, rows 1-22 (75K T). 0xAB3B: restore. The buffer 0xE000-0xF7FF (bank 0) is a ring of 192 lines, 32 bytes each, with scroll (0xB3E6), rewritten at its edges; 0xAF53 shifts it 4 pixels.
One plotter, one call: AE73 from 0xA932. Record (0xB3B4, 4 bytes each, count 0xB335): x, y, frame, height. Frame 80 and 0xFF: nothing. Graphics 0xBB38 + 32 frame, 16 x 2 bytes; mask 0xC5F8 + 32 * (0xB418)[frame]; pixel = (buffer AND NOT mask) OR graphic.
Two frames are written at run time, top 8 rows: 85, the fruit score, 0x96B8 from 0xCC18 + 16 n (mask 0xCD18 + 16 n); 81, the ghost score, 0x9224 from 0xCBB8 + 16 n (mask 0xCCB8 + 16 n, n 0-5). No other code loads those addresses.
The play area has ONE attribute per round (0xB336, table 0x7FDF: 0x43-0x47, black paper), set once at 0x8DE8. 89DF paints two yellow cells wide in the fixed column 11-12 of rows 5-10 (height follows the jump) for Pac-Man, who stays at x 95, y 72 while the maze scrolls.
The ISR (IM 2, I 0xFD) pages bank 1 at 0xC000 for the music and bank 0 back: 7FFD values 0x10 / 0x11 only, never ROM 0, never locked.

## Design
| Site | Original | Patch |
|---|---|---|
| 0xAEED 0xAEF4 0xAEFB | LD (BC),A | NOP: the plotter runs on, same registers, buffer stays scenery |
| 0x8A17 0x8A1B | LD (HL),A | NOP: no yellow cells; the room's fill stays |
| 0x87AA 0x88E9 0x891B 0x7B9A | CALL 0xB090 | CALL e_bN: swaps the return address (same SP), blit, c_N commits all sprites from the game's own tables, JP back |
| 0xB094 | CALL 0xAF1F | CALL e_hide: a blit not returning to c_N hides all 12 sprites |
Hooks: alt ROM image 1 at 0x386E, 704 bytes; no DI / EI, no LD A,I; the ISR uses neither hooks nor NEXTREG. Every hook leaves R
as the original reaches the same point (lib/hlib_r.asm: O = 0 at every exit, E = 3, N = 2, delta -5); the commit runs at
28 MHz between HLIB_SPEED_IN / _OUT (lib/hlib_speed.asm), the caller's programmed speed restored. Hook RAM: 4 bytes at 0x5B70
(128K system variables N_STR1 / HD_, zero in the file; a read trace over 3,000 frames of title and play shows no game read of
0x5B00-0x5BFF at all, so NEXLOAD's printer buffer is harmless). Tail: 0x5E00-0x5E34, inside the save-under area 0x5CCB-, which
the game writes before it reads (same trace). hlib_iff: not used (no interrupt state is read or changed). hlib_pace: not used
(the build does no less work than the original; measured pace +0.4% to +0.5%, below).
26.11: the alt ROM image is the whole of Sinclair's 48K ROM plus the hooks (z80tonex ALTROM_FILL 'whole', bank 47), so the
game's early IM 1 ISR and KEY-SCAN (0x0038-0x02D8, before it sets IM 2) run Sinclair's code on v2.09 and v2.10 alike.
Sprites: slot n = n-th plotted (higher on top); 16x16 4-bit; 102 patterns: frames 0-85, 86-95 fruit score forms, 96-101 ghost score forms. Nibble 0 clear, 1 the figure's ink (palette offset), 2-14 fixed, 15 black paper. Clip window x 8-167, y 8-183. y from 0xB8 is y - 192.
Colours, default: record 0xB3B4 (Pac-Man) bright yellow in play, every other figure the room's ink, as the original's cells.
Enhanced (owner's look, approved 2026-11-03, docs/profiles/pac_mania_enhanced.json + ENHANCED_FIXED palette): Pac-Man yellow,
red mouth; ghost frames 20-31 red, 54-62 cyan, 45-53 orange; frightened 32-40, 82-84 blue; eyes white; rising 76-79 red; fruit
and scores from the MVV package's older Spec256 conversion, painter not established. Bank 11 and the palette are byte-identical
to the approved build (out/painted/pac_mania_enhanced.nex).

## Verify (what it checks)
v1/work/vf.py -> pacmania.verify: original and patched replayed side by side (Python Simulator, flat 64K view + the banks off
the top, swapped on 7FFD writes; Sinclair's 48K ROM as ROM 1 on both). Every frame: all registers with R (hooklib.CMP_R), PC,
the paging, RAM 0x5B00-0xFFFF but sites / hook RAM / the buffer, every bank off the top. At each plot pass: buffers equal. At
each blit's end: patched ULA + sprites = the original's ULA, attributes, each sprite's ink, the buffer untouched. Idle frames:
the same picture. Hooks: IX, IY, I, IFF unchanged, NR 7 back to its entry value, no other NEXTREG.
Unit (pacmania.unit_tests): 86 frames x 16 positions against the original plotter on 0x00 / 0xFF canvases, score forms, count
and frame guards, inks, e_hide both ways, and every hook at 4 incoming speeds x 7 R values (0x00, 0x05, 0x7A, 0x7F, 0x80, 0xFB,
0xFF): exit address, R, NR 7 and every register.
Negatives (v1/work/neg.py): 10 broken builds, unit + 3,000 frames of replay.

## Results
| Output | MD5 | Status |
|---|---|---|
| pac_mania_sprites.nex (default) | 431698a4d2e8a0a67ff50c44c4475b14 | 8 RZX IDENTICAL, unit PASS, boot OK (plain and NEXLOAD); JNext play; hardware untested |
| pac_mania_enhanced.nex | acfbc75c7ce9d78840fec348ae2f2654 | same code; patterns + palette = the approved 2026-11-03 build |
| pac_mania.nex (plain, starts at 0x7530) | 8763e062854c3f5d91f4e14083dd3bf4 | conversion only |
Verify, 96,520 frames, all IDENTICAL: pm_first 3,669, pm_idle 7,340, pm_lives 8,546, pm_rounds 16,566 (rounds 0-19),
pm_l4 15,561, pm_l5 15,550, pm_b11 14,644, pm_b12 14,644. Hook low SP 0x5FDA. 7FFD only 0x10 / 0x11.
Unit: 1,376 frame cases, 48 score forms, 13 count + 4 frame guards, inks, e_hide 2, hook cases 252 -> PASS.
Negatives 10 of 10: patterns one pixel right, y one line down, Pac-Man's ink, height ignored, no hide, R one off after c1, R one
off after e_hide (both desync the replay: the RNG reads R), c1 not restoring the speed, plotter writes left in, yellow cells
left in.
Pace (python -m nexclash.pace, JNext 1.1.104, original .z80 against the build, input keyed to updates, probe 0xA8FA, state
0xB36A-0xB36D + lives): seed 1 +0.50% (400 updates), seed 2 +1.03% (260, state diverged after), seed 3 -0.40% (480), round 2
-0.30% (420), Enhanced +0.37% (600). Steady 20-update windows +0.1% to +1.4%; the large single windows are a pause landing in
another window. AY writes per second equal (545-547).
Real loader (.NEXCLASH, private card copies v2.09 and v2.10): default, Enhanced, five trainers, all: /tmp/NEXCLASH.NEX
byte-exact, play reached, trainer bytes live, 0xB332 = 1.

## Cheats (archive POK, the same for every release; each tested alone, v1/work/cheats.py)
| Trainer | Address | Original -> value |
|---|---:|---:|
| Start with 9 lives (archive: Lives 1-128) | 0x86C6 | 04 -> 09 |
| Infinite lives | 0x8945 | 35 -> 00 |
| Turbo speed (archive: Turbo Pacman) | 0x86DE | B7 -> 00 |
| Infinite credits | 0x788F | 35 -> 00 |
| Immunity | 0x9601 | C0 -> C9 |
The panel shows at most five lives faces (the original's own).

## Open
- Hardware: never run on a Next.
- Pace: +0.4% to +0.5% steady (the R handling and the 3.5 MHz prologues of four hook calls an update); within +-2%.
- Frames 68-73 and some ghost-eaten / fruit score forms were not reached by any recording: unit cases cover their pixels.

## Lessons
- [local: a plotter with NOPed writes keeps every register and all timing] Removing only the store instructions made the patched run equal the original in every register at each frame boundary, bar A and F inside the plot and blit loops, which follow the bytes read.
- [local: a lockstep with fetches counted only outside hook ROM] Frames by RZX fetch count stay aligned when hooks run in ROM and each site keeps its fetch count (CALL for CALL, NOP for one-byte store). Whole-RAM, whole-register comparison per frame, 150 frames a second. Hold R across hooks if the game reads it.
- [local: scan --writers on one recording missed a run-time graphic] The first recording showed no writer in the graphics; a later one showed the score frame rewritten. The composite check found it, and a chase bot found the second one (ghost score) only after six recordings had passed. Treat "static graphics" as provisional until every recording has passed.
- [local: unit tests against the real plotter on canvases] Found the y ring wrap no recording had reached.
- [local: negative controls need a recording where they matter] Yellow cells left in is invisible in a yellow room; a frame-80 sprite is blank. Choose the recording, and the control, accordingly.

- [local: a 128K release paused in BASIC] The snapshot waits in a PAUSE whose statement returns through the 0x5B00 ROM-swap
  code and ROM 0; starting at the USR address with interrupts off avoids both, and a read trace showed the game itself never
  reads the printer buffer. Check what the BASIC path needs before keeping a snapshot's PC in ROM.
- [local: a CSimulator ROM swap after construction] Replacing skoolkit's Memory.roms tuple after the CSimulator is built does
  nothing: write the new ROM into the existing ROM buffer in place (v1/work/m128b.py). Recordings made the other way desync on
  the 48K ROM (IM 1 at 0x004B differs).

## Friction
- reuse: [local: the pilot's 128K frame model (runs/beyond_the_ice_palace work/m128.py) and nexclash.pace / nextboot.rom_paths used as they are]
- retries: [local: one round of recordings remade after the ROM-swap fix above; the verifier caught it at frame 1]
- environment: [local: JNext on private card copies; the v2.10 card shows a welcome page first (one more SPACE)]
- hand-rolled: [local: the 128K paging in the verifier (a flat view plus banks swapped on 7FFD) is this engine's own, as verifiers stay per engine]
- scratch: [local: the run's scripts stay in the pilot folder (v1/work), none in tools/]

## Technique use
- detect.gameplay-screen-readers: helped: only save, plot, restore and blit read the buffer.
- detect.tracked-unit: helped: one plot call draws one figure.

## Hardware checklist
Not run on hardware. Check: loading screen while loading, title music (AY), M toggles music, sprites at the view's edges, figures
entering at the top, Enhanced colours, a game over back to the title, all five cheats.

## Stage log
2026-11-03 stages 0-3 (48K form), unattended.
2026-11-07 v1.0: rebased on main 102091f; 128K release with AY; hooks restore R and speed (hlib_r, hlib_speed); 26.11 whole ROM
image; Enhanced set from the approved map; 8 new 128K recordings, IDENTICAL; 10 negatives; JNext pace, loader, cheats.
