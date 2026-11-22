# Jet Set Willy (Software Projects, 1984; 48K) - engine `jsw` (pilot game 2: unattended, no hardware)

## Next session
Stage: 4 (hardware + colour)    State: stages 0-3 done unattended; never run on a Next or in an emulator.
Inputs: the pilot's run folder (jet_set_willy.z80 md5 a4963e74; recordings work/*.rzx from `record --script`)
Start with: hardware checklist below on a real Next; then a human's answers to "Defaults taken".
Read: this file. Open: everything under "Open".
NEXLOAD fix (2026-11-22, Codex): the snapshot's stack is at 0x5BFC, in the printer buffer NEXLOAD overwrites; 1.0 / 1.1
kept no copy, so on a Next the first RET went to 0x5859 (modelled: nextboot.boot nexload=True). Both builds now set
keep_printer_buffer (the stub puts 0x5B00-0x5BFF back); published as 1.2. A board run of 1.2 is still owed.
Before any Enhanced build (Codex, same day): the picture verifier clears ink pixels painted the same index as their
paper (painted Bathroom item black: "picture differs" at 0x68B7); track the source ink mask, not the final index.

Techniques: `detect.buffer-layout-producer`, `detect.gameplay-screen-readers`, `patch.display-atomic-switch`, `patch.runtime-colour-map` (docs/records/jet_set_willy.json)

## Attic bug: fixed at the owner's request (2026-11-21)
The Attic's arrow (59901 = 213) writes outside the buffers and corrupts other rooms; both builds set 59901 = 82 at boot,
the known fix, with the code sheet's START_SITES. jsw_play1 enters the Attic at frame 14,351: the comparisons stop
there (counted), as the original's arrow writes outside the buffers in that room; each pass checks the fix is present.

## Code sheet: bypassed at the owner's request (2026-11-02)
Both builds start at the title with no code entered. The check is not removed: at boot 0x8791 (DD CB 21 FE -> C3 4F 87 00) jumps to the check's head 0x874F, past its ENTER test, and the four cells it reads (0x5950 87->08, 0x5953 07->10, 0x5956 07->20, 0x5959 07->10) hold this snapshot's code (85E4 = 0x1D, keys 1 2 4 2). So the game's own POP HL / CP (HL) / RET runs, flags included. Sites: `START_SITES` in nexclash/jsw.py, both builds; each keeps its original-byte check.
Later checks, looked for in the disassembly 0x8400-0xA000: nothing else calls 0x86C3; 0x9E00 (the code table) is read only at 0x8702, FRAMES 0x5C78 only at 0x86F3-0x86F8; 0x85E4 is written before each later read (title 0x88B2, game over 0x8C58); no LD A,R, no sum over code, LD SP only at 0x8409. Observed: the check's result already does nothing in this archive file: 0x86B0 is NOP NOP NOP and 0x86B3 is an unconditional JP 0x87CA, so a wrong code also reaches the title (tried on the original: keys 4 4 4 4, title, then The Bathroom). The bypass still enters the right code, so the flags match a correct entry.
What the replay does now: the recordings begin at the sheet and hold its key presses, and the builds never show it. The original runs them to the check's return (0x86B3), the build runs from the snapshot with no input to the same place, and lockstep starts there. At that point registers are identical on all recordings and memory differs only in the sheet's 12 other colour cells (0x5951-0x597A). The plain build then matches the original on all registers and whole RAM + screen at every pass start and blit, so the title has rewritten those cells and nothing later can tell. No longer applies: the code sheet itself, and its input loop, are not run by any build or compared (109 recording frames, reported). The boot state still comes from the same snapshot. A recording made on the new builds would have no sheet; recordings stay made from the original snapshot.

## Inputs
Snapshot: archive file "Jet Set Willy (1984)(Software Projects).z80" (ZXDB 0002589), md5 a4963e747af1145fe0f2710da592abc6. 48K, DI,
stopped at the colour-code sheet (PC 0x8791): decrypted, code 0x1D for this snapshot (keys 1, 2, 4, 2 then ENTER), then the title.
No Fuse and no human: recordings by `nexclash.py record --script` from work/bot.py, bot2.py (search over held keys on nexclash's Machine) and a written script:
- jsw_play1: search from the start to First Landing, the game's own WRITETYPER cheat, teleport to 58 rooms in turn and wander at random; game overs re-entered.
- jsw_rope: same start, then search until Willy is on a rope (room 31 grabbed, 90 frames on it; 25, 58, 18, 16 not) and walk off.
- jsw_idle: pause (A), colour cycle, resume, quit to the title (SHIFT+SPACE).

## Snapshot facts (PLAYBOOK 0b)
`inspect`: PC in RAM, no paging, IM 0, DI; no EI in the code; `isr`: 0 interrupts in 21768 frames. Stack at 0x5BFF down, lowest 0x5BF8; 0x5B00-0x5BF7 untouched and zero.
Keys: Q/W (and other top-row keys) left / right, SPACE (bottom row) jump, A-G pause, H-ENTER row music, ENTER starts.

## Rendering model (PLAYBOOK 2): back-buffer composer
Main loop 0x89AD, about 4.3 video frames per pass, no frame sync: 0x5E00 -> 0x5C00, 0x7000 -> 0x6000, figures into both, 0x89F5 0x6000 -> 0x4000, 0x8A26 0x5C00 -> 0x5800.
| Figure | Plot | Colour painted | Notes |
|---|---|---|---|
| Willy | 0x9660 into OR loop 0x9668, gfx 0x9D00 (0xB600 in room 29, a pig) | ink 7 over background cells only, background's bright | IX = row table, y = IXl / 2 |
| guardians (horizontal, vertical) | 0x922E CALL 0x9456, C=1 AND collision then OR | (IX+1): bit 3 bright, ink; paper kept | 95+99 in the room data |
| arrows | 0x928E-0x92A0: three rows, overwrites | ink 7 OR'd into the cell | The Attic's arrow writes outside the buffers (the game's known bug): its sprite sits at y=223, off screen |
| rope | 0x930E pixel OR, up to one pixel a row | none: takes the cell's colour | no RET path between 0x930E and 0x935E |
| items | 0x9449 into 0x969B, 8 rows, overwrites, gfx 0x80E1 | ink cycles 3-6, paper + bright kept | |
| Maria | 0x9563 CALL 0x9456, C=1 | 0x45 top pair, 0x07 bottom pair | room 35, 85DF=0 only |
| toilet | 0x95BB CALL 0x9668 | 0x07 | room 33 |
HUD (lives 0x89A3, score, time, room name), title, game-over scene (0x8C63-0x8C85, on the ULA directly): not hooked.
Screen flash 0x8A0B: 85CD has no writer but its own clear, so dead code (inferred from the disassembly), left as it is.

Readers (`scan --writers`, work/scan_ula.log, jsw_play1): the ULA is read only by LDIR fills and the title / code sheet; pause reads attributes to cycle them (0x8AF3). Logic reads 0x5C00 and 0x6000 only, which stay exact.

## Patch plan (STANDARD 4-5; cards opened: 3)
detect.buffer-layout-producer: 0x7000 / 0x5E00 are the clean layers. detect.gameplay-screen-readers: no logic reads the ULA, no virtual read needed.
patch.display-atomic-switch: applied: patterns are written at each plot into the bank not on show, then the attributes switch. patch.scratch-redirect rejected: the game's own buffer already is the scratch.
No card covers "change the blit source"; table 4 "back-buffer composer".

## Defaults taken (a human would have decided these; PLAYBOOK 3c, not asked in this pilot)
1. Every figure a sprite: Willy, guardians, arrows, ropes, items, Maria, toilet. Default.
2. Scenery, HUD, score, text, title stay on the ULA. Default. So the lives, the game-over scene and the code sheet keep their ULA colours.
3. Depth: game's own plot order, higher sprite on top; items last. Default.
4. Colours: each figure's own ink + the game's bright. No painting, no colour sheets built.
5. Pause: sprites off while the screen cycles colours (documented default). Figures vanish for the pause; the original keeps showing them.
ALWAYS-ASK, no default, decided here without a human:
- solid or see-through: items and arrows solid (they overwrite in the original), the rest see-through (OR). Follows the original's pixels.
- rope colour: the room's background ink for the whole rope. The original's rope takes each cell's colour, so a rope crossing other colours changes here.
- Maria: two sprites, 8 rows each, to keep her two colours.
- death flash: fills the ULA attributes; sprites stay in their own colours over it (the original shows figures in the flash colour).
- the end sequence: Maria's exit and the toilet follow the same hooks; Willy's end is never in a recording (unit cases only).

## Build design
Sites and hook behaviour: top of asm/jsw_hooks.asm. Memory: alt ROM image 1 at 0x386E, hook state 27 bytes at 0x5B60, tail 53 bytes at 0x5B00.
One sprite per plot in plot order; patterns 4-bit, written per plot at 28 MHz, bank flipped per pass (64 sprites, 2 banks = all 128 pattern slots). Rope: slices of up to 16 x 16 pixels, opened as the pixels leave the window; 16-byte row list in hook state.
Static palette, offset 0 only: index 1-7 normal blue..white, 8 black, 9-15 bright; a figure's colour is in its pattern nibbles (S_I ink, S_B paper of a solid figure). Blit hook hides sprites not plotted this pass (a death cuts a pass short; an arrow goes off screen). Room load, title, game over hide all.

## Colour map (docs/COLOURS.md; recolour, seconds, no rebuild)
Sheets: `python -m nexclash.jsw sheet GAME.z80 PREFIX`; the figures come from the code plus one short run of every room, not from the recordings: Willy 8 frames, the pig 8, Maria 4, toilet 4, 145 guardian frames, 37 rooms' items (206 figures), ink pixels only. Key = graphics byte (hex; check = its value), bit = pixel; nibble 0 = the game's colour.
The first palette prevented this: a figure's colour was its palette offset and the nibble only meant "ink of this offset", so one figure could not hold two colours and a painted index had no fixed colour. Changed to one fixed 15-colour palette with the colour in the pattern (same colours, same look as before; base MD5 changed; re-stamped).
Tables: Next pages 28-33 (banks 14-16), mapped at slot 7 inside an upload only, interrupts off, never by the game (card patch.runtime-colour-map). A flag per graphic means an unpainted figure costs two NEXTREGs and a read. Recolour rewrites only those banks. Unit: a synthetic map through a real run, each pixel checked (Willy, guardian, item), wrong check byte ignored, map left out detected. Negative: slot 7 left on a colour page. Selftest guard: recolour both ways = a full build.
Test repaint, a test only, nothing chosen for the build: top 4 rows of Willy's 8 frames in red on a copy of the sheet, work/paint/: 136 pixels, 44 map entries, banks 14 and 16 changed, 0.33 s. png/jnext_painted_hat_gameplay.png: Willy with a red hat in JNext.

## JNext (emulator, not hardware)
Sprite, plain and painted builds all boot to the title with no keys and reach The Bathroom on ENTER, with ENTER offered repeatedly until the title takes it (frames 500-1200): png/jnext_*.png. Compare: in the plain build Willy's legs turn cyan on the bath; in the sprite build they stay white. Only the start and a short look in one room were run.

## Verify (what it checks)
Lockstep: the whole patched game next to the original on the recording's IN values, from after the code sheet (interrupts off, so only the IN sequence decides). At every pass start and pixel blit: all registers but R / T / MEMPTR, memory outside the ULA, patch sites and dead stack. No jump into a patched instruction.
Per pixel blit: 0x7000 as copied + sprites in order (ink sets, paper nibble clears) = 0x6000 bit for bit; on a death frame, where the original stops mid-plot, the picture must hold every pixel of the original (counted). ULA pixels = 0x7000; ULA attributes = 0x5E00.
Unit: setup (palette, hidden, on); all 60 rooms from a clean load; Maria at 3 heights; 85DF=1, 2, 3 end game; slot guard (table full). Negatives: 11 broken builds on the real recordings, and through the unit cases.

## Results
Stamped 2026-11-02 (`selftest.py --game jet_set_willy --verify --stamp`), simulation only; the tool's report, quoted:
```
Plain     : jet_set_willy.nex  6b16cc651bdd51a2e971dd011a6458ab  boot OK  (tail 0x5B00)
Sprites   : jet_set_willy_sprites.nex  5048ef71783e08cf546f7e253afbe4a7  boot OK  tail 53 bytes at 0x5B00
Verify    : jsw_play1.rzx  21767 frames, 3161 passes, 3133 blits, pictures 3059 identical + 74 cut short -> IDENTICAL
            hooks: pass=3161 blit=3133 room=294 ttl=22 ovr=21 pau=0 res=0 wil=3032 toi=452 gua=7975 mar=42 arr=446 rop=4257 rfl=129 itm=3214
            rooms 58; on-screen sprites 16103; off-area pixels 1944 ( room 41=1944), over the HUD 0; T +15.4 %
Verify    : jsw_rope.rzx  5246 frames, 1122 passes, 1119 blits, pictures 1115 identical + 4 cut short -> IDENTICAL
            hooks: pass=1122 blit=1119 room=26 ttl=3 ovr=2 pau=0 res=0 wil=1107 toi=353 gua=1922 mar=0 arr=0 rop=11220 rfl=340 itm=883
            rooms 8; on-screen sprites 6533; off-area pixels 0 (), over the HUD 0; T +27.2 %
Verify    : jsw_idle.rzx  881 frames, 45 passes, 45 blits, pictures 45 identical + 0 cut short -> IDENTICAL
            hooks: pass=45 blit=45 room=1 ttl=1 ovr=0 pau=5 res=1 wil=45 toi=45 gua=45 mar=0 arr=0 rop=0 rfl=0 itm=45
            rooms 1; on-screen sprites 180; off-area pixels 0 (), over the HUD 0; T +6.2 %
Plain     : jsw_play1.rzx against the original from after the code sheet, all registers and whole RAM + screen, 6294 compares -> IDENTICAL
Plain     : jsw_rope.rzx against the original from after the code sheet, all registers and whole RAM + screen, 2241 compares -> IDENTICAL
Plain     : jsw_idle.rzx against the original from after the code sheet, all registers and whole RAM + screen, 90 compares -> IDENTICAL
Start     : code entry not replayed (recordings begin at the sheet, the builds never show it): frames skipped 109; after the check, registers differing 0, memory bytes 12 (the sheet's cells)
Coverage  : hooks that never ran in a recording: none
Speed     : hooks add 2.92 % of the T, estimated: (patched - original T) / 6, no real-machine timing
Colours   : sprite ink vs the original cell at its top left, informational: 22336 same, 399 not
Unit      : Maria gone 1, Maria 3, colour map 1, room 60, run to the toilet 1, setup 1, toilet end 1 -> PASS
            end game: 85DF at the end of the toilet run 2
            slot guard 1; hooks in unit cases: pass=1946 blit=1861 room=107 ttl=0 ovr=0 pau=0 res=0 wil=1763 toi=287 gua=5200 mar=46 arr=116 rop=4488 rfl=136 itm=2324
Negative  : plain bypass with a wrong code cell: DETECTED ['after the check: registers differ from a real entry!']
Negative  : pixel blit keeps the figures: DETECTED ('jsw_play1.rzx', 'ULA pixels are not the clean buffer!', (176, 'room', 33))
Negative  : attribute blit keeps the paint: DETECTED ('jsw_play1.rzx', 'ULA attributes are not the clean buffer!', (176, 'room', 33))
Negative  : sprites one row low: DETECTED ('jsw_play1.rzx', 'picture differs!', (176, '0x608f', 63, 18, 'room', 33, 'died', False))
Negative  : patterns inverted: DETECTED ('jsw_play1.rzx', 'picture differs!', (176, '0x606f', 170, 0, 'room', 33, 'died', False))
Negative  : Willy hook loses A: DETECTED ('jsw_play1.rzx', 'state differs at 0x89F5!', (176, [('mem 0x68B4', 60, 0)]))
Negative  : Willy hook never runs: DETECTED ('jsw_play1.rzx', 'picture differs!', (176, '0x68b4', 0, 60, 'room', 33, 'died', False))
Negative  : guardian hook never runs: DETECTED ('jsw_play1.rzx', 'picture differs!', (176, '0x608f', 0, 18, 'room', 33, 'died', False))
Negative  : arrow hook never runs: DETECTED ('jsw_play1.rzx', 'picture differs!', (5164, '0x619b', 0, 65, 'room', 11, 'died', False))
Negative  : rope hook never runs: DETECTED ('jsw_play1.rzx', 'picture differs!', (8426, '0x6010', 0, 128, 'room', 18, 'died', False))
Negative  : item hook never runs: DETECTED ('jsw_play1.rzx', 'picture differs!', (176, '0x68b7', 0, 31, 'room', 33, 'died', False))
Negative  : blit hook never hides: DETECTED ('jsw_play1.rzx', 'picture differs!', (299, '0x68b7', 31, 0, 'room', 33, 'died', False))
Negative  : slot 7 left on a colour page: DETECTED ('jsw_play1.rzx', 'state differs at 0x89F5!', (299, [('mem 0xE000', 160, 0)]))
Negative  : bypass with a wrong code cell: DETECTED ('jsw_play1.rzx', 'after the check: registers differ from a real entry!', ([(0, 29, 25), (1, 74, 155)], []))
Negative  : 13/13 detected on the real recordings; through the unit cases 9 seen
Result    : PASSED
```
Clash: png/jsw_side_by_side.png, png/jsw_zoom.png were rendered from the build before the palette change. JNext: png/jnext_*.png.

## Hardware checklist (nothing here has run on hardware)
1. Boot: straight to the title with no code sheet (at most a frame of it); tune as the original; ENTER starts in The Bathroom.
2. Willy and guardians crisp, in their own colours, no attribute change on what they cross.
3. Speed and sound against the plain .nex (no frame sync: any slowdown shows), most in rope rooms.
4. Ropes: The Cold Store, Swimming Pool, On the Roof: rope smooth, no tearing, Willy climbs it. Look at the slice joins.
5. Arrows: Under the Roof, Attic: arrow shows; Attic's off-screen arrow draws nothing over the HUD.
6. Items: colour cycling, pickup, score; Master Bedroom: Maria; Nightmare Room: the pig.
7. Pause (A): sprites off, colours cycle; any key resumes with sprites back.
8. Death flash, game over boot scene with no stray sprites; SHIFT+SPACE to the title with no stray sprites.
9. All items taken (or poke): Maria leaves, the run to the toilet, the end.
Hardware risk review (PLAYBOOK 6b): DivMMC: hooks at 0x386E-0x3C4x, not in 0x3D00-0x3DFF. Interrupts: never on. Raster: sprite attributes not synced to the beam, as the original; a simulator cannot show tearing. Speed: Results; no OUT $FE at 28 MHz, hooks restore NEXTREG $07 before returning. Sprite clip: over-border off assumed to hide y=223.

## Open
- Never run on hardware or an emulator with sprites: sprite/ULA composition is modelled, not observed.
- A human's answers to "Defaults taken".
- Coverage limits: no human play. The recordings are short visits (155 deaths in jsw_play1); 2-3 items collected; end game unit cases only; rooms 38, 59 only as unit cases; room 47 ('[', Tree Root's right exit points to it) in neither recordings nor the stamped unit run: one ad hoc 30-pass lockstep only (work/q2.py).
- Arrows and ropes are not on the sheets: arrows have no graphic in the figure tables, ropes are single pixels; they keep the game's colours. A human's call if they should be paintable.
- Items show one default ink on the sheet (index 3); unpainted they cycle as the game does; a painted item pixel holds its colour. Guardians drawn in several colours by the same graphic share one colour-map entry per pixel.
- Hook code is 1147 of 1150 bytes in the alt ROM range: no room left there.
- Knowledge refresh from main (LEARNING 1): skipped, no network by the pilot's rules; knowledge is from commit 1d2faa4.

## Lessons
- [local: the speed fix in 1 spare byte] The hooks keep the caller's CPU speed (F8): one spdin (latch HS+29, then
  28 MHz) and one spdout for every hook; the setup selects NR 7 on 0x243B once, so a read is one IN. The 48K ROM's
  free area holds 1150 bytes: inline HLIB_SPEED macros were 78 over; e_pass now runs at the caller's speed (four
  instructions cost less than a switch). Lockstep answers 0x253B from the NextReg state (a recorded IN otherwise)
  and turns the caller's speed 0-3 at every pass and blit; hook cost 2.79 % (main 2.76 %).
- [local: only this game's and Manic Miner's plotters allow it] demonstrated: the two-LDIR source change removes every figure from the ULA with all logic untouched; the first full lockstep run failed only on arrows (they overwrite, I had assumed OR), which the bit-exact picture check found at once.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: `survey` says "Generic engine unknown ... auto builds it" for a game no engine knows; its GATE CHECK here is two text-printer calls and code-sheet figure calls that ran before the snapshot.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: an InputRecording's `data` includes frame headers; slice it by each frame's start and end. Reading it whole silently desynchronised the run into what looked like a hang.
- [local: card not edited, shared docs left alone on the owner's rule] observed: patch.runtime-colour-map's slot and page assumptions hold for a second game; a flag per graphic gives the unpainted fast path without an index search.
- [local: this engine's auto] observed: a NOT DETECTED negative printed in a PASSED stamp, because that line did not count towards the result and the plain check skipped the start state; found on reading the report. Fixed, re-stamped.
- [local: this archive file] observed: the snapshot's code check is already neutered (0x86B0 NOPs, 0x86B3 JP unconditional) though it stops inside the sheet; found only because the bypass work read the code.
- [local: needs a human] inferred: JSW's clash is mild: guardians paint ink only and paper stays; the visible gain is Willy keeping his colour next to figures and scenery. Many of the overlaps in the evidence frames are from teleporting into scenery.
- [deferred Open: reconsider when a maintainer reviews the pilot] observed: a search bot must restore its start state when it fails, or the script it writes no longer replays (the bot's log and the recording disagreed; caught by per-room counts).

## Friction
- reuse: [local: the pilot's JSW engine ported as it was; the Attic fix is one START_SITES byte]
- retries: [local: the engine sat uncommitted in a worktree 155 commits behind main; carried onto main and re-stamped there]
- environment: [local: reference files in the e9ab1e50 scratchpad ref folder; not yet in specnext]
- hand-rolled: [none: the record came from the port as published; only the feasibility block was added]
- scratch: [none: nothing added to tools/]

## Technique use
- patch.runtime-colour-map: helped: design and verify list; tables direct-indexed here, no image index.
- detect.buffer-layout-producer: helped: named the question; the disassembly answered it.
- detect.gameplay-screen-readers: helped: `scan --writers` gave the proof in one run.
- patch.display-atomic-switch: helped: picked the two pattern banks; never tested on hardware.

## Stage log
- 2026-11-02 colour route + code sheet bypass (owner's requests, unattended): 25 min, ~14 tool calls.
- 2026-11-02 stages 0-3 in one session (pilot, unattended, one stamp restarted to add site checks): 55 min, ~45 tool calls, 0 user rounds.
