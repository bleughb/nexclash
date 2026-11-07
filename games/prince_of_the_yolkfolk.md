# Prince of the Yolkfolk (Dizzy 6) - engine `tid_mirror`

48K. Code: nexclash/dizzy6.py (TidPatch slot1 + unpatched plotter/eraser copy at 0x2000 for the
mirror calls; nexclash.py _auto_dizzy6). Profile: docs/profiles/dizzy6_prince_of_the_yolkfolk.json.
Reference files (private repo,
specnext/reference/prince_of_the_yolkfolk/): Dizzy6.z80 (md5 dd6cd7a3), try1.rzx, try2.rzx, try3.rzx.
In selftest (docs/records/dizzy6.json): rebuild from stored decisions; verify against try1.rzx (~3 min).

| Output | MD5 | Status |
|---|---|---|
| Dizzy6.nex | e02faca34df9504cc1f2f162e0ef791e | |
| Dizzy6_sprites.nex (slot1) | f491e1f6621559ccc4d36de3535ff5d0 | verified (try1.rzx 1,537 plots, auto RZX 29, 780-case mirror selftest); hardware untested |

Stays slot1: the self-modifying plotter copy needs RAM at 0x2000; tail in the player undo buffer
23552 (88 bytes, write-first). Relies on locked 7FFD writes not remapping MMU (VHDL; hardware to
confirm with this build).

## Facts
Dizzy 6 / Prince of the Yolkfolk (48K .z80 v1, PC 65021 = IM2 vector -> JP 61478, SP 40085,
DI; full map in dizzy6_prince_of_the_yolkfolk.json): plotter 38351 / eraser 38667 (code ends
38721; variables 38721-38740 follow), player plot site JP at 38974, undo buffer selected by
pointer 38731 (eraser `LD SP,(38731)`, plotter `LD DE,(38731)`): player 23552, mirror 23652;
frame table 25849; wipe 36389 (IX 23848); box 36988 (var 38348); ISR hide call 61507 (tick
37108); pixel test 39792. SECOND FIGURE: actor handlers 33655/33669 (reached via room/actor
tables, not CALLs) draw a MIRRORED player copy (X = 58 - X, frame via map at 33757) with
CALL plotter at 33741 and CALL eraser at 33680 after `LD BC,23652 / LD (38731),BC`, then restore
the pointer to 23552. Printer buffer USED; ROM not read and never written (0x0000-0x3FFF, both RZX); dead stack 48 bytes (low-water 40037);
no player-dependent pixel tests; screen writers over the player at 36213-36273 are xor/keep
(object plot), 36074/37030 overwrite. No RZX has reached the mirror actor yet (room unknown).

## Open
- Record a pass through the mirror room (verify that path against real play).
- evidence.json not updated for 'tid_mirror' (_auto_dizzy6 skips _learn).
- Possible hybrid: alt ROM hooks + plotter copy in a slot-0 RAM page (IM2 game).

## Rework (opt-in) v128: the 128K release (engine `yolk128`; Jon Attree, 2026-11-06)
Dean's builds (e02faca3 / f491e1f6) are untouched and stay his record's; `selftest --game dizzy6` rebuilds them and
this rework = recorded.
- Why: the 128K release plays AY music. The game ISR (0xF026) CALLs 0x78DA after the hide call at 0xF043, which pages
  bank 3 (OUT 0x7FFD = 0x13), CALLs 0xC0E4 and pages bank 0 back (0x10): an unlocked 7FFD write every frame, which
  resets MMU slots 0/1 to ROM, so Dean's slot-1 RAM page cannot stay mapped. identify() finds Dean's profile in banks
  5 / 2 / 0, every patch site and the mirror calls the same bytes.
- Input: TOSEC `...(128K)[a][a][aka Dizzy VI - Prince of the Yolkfolk].z80` (292c1b1c): saved at the title in the
  game's key test 0x90B2 (DI, SP 0x9C8F). The main dump (f48f63cc) is saved inside the interrupt handler (return
  0xF046 on the stack, interrupts already re-enabled by that key test) and carries the Infinite Lives POKE (0x78AB =
  0xB6); the [a2] dump (f9a741d2) is saved in the BASIC loader at the loading screen and runs the 128K ROMs first.
- `nexclash/yolk128.py` (Dean's build.TidPatch altrom and dizzy6.layout / relocated_copy: used, not copied): whole alt
  ROM image 1 = Sinclair's ROM + Dean's hooks at 0x386E + his mirror copy at 0x2000 (the game never runs or reads that
  ROM: the verifier counts every ROM access); image 0 = the 128K ROM 0. The actor's plot CALL (0x83CD) goes to the
  copy in the alt ROM (the plotter half never writes to itself). The actor's erase CALL (0x8390, always after the
  actor's own DI) goes to a trampoline: NEXTREG 0x51,24 (RAM page 24, the alt ROM's copy source: the same bytes) and
  JP the eraser copy, whose self-modified operand then lands in RAM; its last six bytes (LD SP,(spsave) / EI / RET)
  JP to their copy behind NEXTREG 0x51,0xFF, so the eraser runs on the original's stack. Tail in the undo buffer
  0x5C00 (Dean's decision, 53 of 88 bytes; never read before written in any recording); the printer buffer (the
  bit-reverse table at 0x5B00) put back after NEXLOAD; the plot hook at 28 MHz between Magicland's head / tail
  (incoming speed latched on the stack, restored before JP plotter); the other hooks and the trampoline never touch
  NR 7. A 128K copy of the TID verifier with the mirror events (the original routine on the patched-screen model
  against the copy; the model then follows the mirrored Dizzy, who stays on the ULA), guards for ROM access, R, the
  hook stack (above the code end 0x9C32), slot 1 left on page 24, alt ROM writes and the tail.
- The mirror: room 40 "DOUBLE TROUBLE!", object 54 (0x7DD8, type 18; handlers 0x8377 first draw / 0x8385 update via
  the tables 0x7F31 / 0x7F69). Rooms: 0x9763 (start room 31 "TRAPPED"); objects 0x7AAE, 77 x 15 bytes (room, type).
  The game's developer room skip: 0x77C2 = 0, then hold C with X / Z (room +-1) or M / K (+-25); SPACE leaves it.
  The mirror recordings poke 0x77C2 = 0 into their first snapshot and use it to reach room 40.
- Keys: SPACE starts at the title and jumps, Z / X walk, ENTER the inventory, Q quits. Game loop: 0x7864 waits for 4
  frames on the ISR counter 0x976F; 0x786E runs once per update (the pace probe). Dizzy x / y: 0x974D / 0x974E.
- R: no LD A,R / LD R,A runs in any recording.
- Results (2026-11-06): plain 6ace08da, sprites 74e0da60, boot OK. mirror1 / mirror2 (6,013 / 6,330 frames in room 40)
  and walk1-3 (12,008 / 12,015 / 12,163 frames): every hook event identical (8,182 plots, 8,779 sprite pictures
  pixel-perfect, 8,686 erases, 18,603 ISR, 130 wipes, 90 boxes, 1,022 mirror plots, 989 mirror erases); mirror1,
  mirror2, walk2 IDENTICAL; walk1 / walk3 FAILED on 5 of 171,382 pixel tests (0x48C5 / 0x4DC6, PC 0x9B78 / 0x9B7D):
  an object drawn over Dizzy (0x8D76 / 0x8D7E) and then his eraser's XOR (0x972C) leaves a hole or a ghost pixel in
  the original that the build does not have (Magicland's PARTIAL; Dean's 48K build has the same design). 2 mirror1
  plots differ only in B (the original plots over the mirrored Dizzy's pixels): B is dead (20,000 instructions on
  with either value: same RAM and registers). 8 negatives detected; clock matrix 7 sites x 4 clocks = 28 PASS, forced
  3.5 MHz exit detected; ROM paths pass; tail never read before written; hook stack low water 0x9C5F.
  JNext: pace ORIGINAL (probe 0x786E, 10 trials a scene, lockstep in all 30: +0.00 % everywhere; AY 700 data writes a
  second, as the original); flicker 0 / 0 / 0; soak 15 min: no freeze, one LOOP warning on the 4-frame wait 0x7864 with
  Dizzy moving (viewed). Cheats: Infinite Lives, five immunities, Extra energy, 20 cherries kept (simulator);
  Animation speed (asks a value) and the second Infinite lives (writes into the AY paging routine 0x78B2: the game
  stops) dropped. Loading screen from the tape (headerless 6,912-byte block), stub in bank 13.
- Enhanced: EASY for Dizzy: all 39 frames (4,602 bytes) byte-identical to Treasure Island Dizzy's, which the .256
  colours. The mirrored Dizzy stays on the ULA (2-colour) in an Enhanced set too. Mock-up: pilot
  runs/dean_prince_of_the_yolkfolk/out/yolk_enhanced_mockup.png.
- Hardware: none.

## Lessons
- [local: a self-modifying routine copy can run from the alt ROM image when its RAM twin (the stub's copy source page)
  is mapped at slot 1 only around the call, with interrupts already off; identical bytes in both views make the switch
  safe]
- [local: the TOSEC main 128K dump carries the Infinite Lives POKE (0x78AB = 0xB6): diff dumps before choosing]
- [local: a game's developer room skip (0x77C2 = 0, C + direction) reaches a far room for a recording honestly]

## Technique use
- patch.restore-speed: used (the plot hook's head / tail, Magicland's: the incoming speed latched on the stack)
- verify.update-locked-pace: helped (probe 0x786E)

## Friction
- reuse: [tool nextboot.rom_paths] the ROM path and tail checks; the boot check, pace, flicker and soak ran on the 128K build unchanged
- retries: [local: the room skip needs C held until the room changes and a SPACE tap to leave it]
- environment: [none: headless JNext with HOME in the run folder, the read-only card]
- hand-rolled: [local: bot recorder on SkoolKit's C simulator; pace trials from Fantasy World's script]
- scratch: [none: scripts stay in the pilot run folder runs/dean_prince_of_the_yolkfolk/work]
