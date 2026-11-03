# Nemesis the Warlock (Martech 1987, 48K) - https://spectrumcomputing.co.uk/entry/3387/ZX-Spectrum/Nemesis_the_Warlock

## Next session
Stage: 3 (prove + deliver)  State: engine built 2026-11-02; quick runs PASS (## Results); record written
Inputs: specnext/reference/nemesis_the_warlock/ (snapshot, rzx)    Branch: claude/festive-einstein-sx8txv
Start with: `python selftest.py --game nemesis_the_warlock --verify --stamp` (detached; ~15 min for 135K frames)
Read: PLAYBOOK stage 3, docs/COLOURS.md (sheets: not built yet), BRIEFING A1 (6b review)
Open: colour sheets + recolour not built (colours are the room attribute, fixed rule); permanent stamps (corpses?) stay on the ULA - tell the user

## Facts
- Inputs: only a SPIN 0.6 RZX (1 segment, 134,980 frames, no autosaves). Its embedded Z80 snapshot
  is the .z80 (LEARNINGS 2.4); no separate snapshot from the user.
- Snapshot: 48K, PC 0x6FDD (RAM, in game code after load), IM 1, DI, I=0x3F, SP 0x6FA0, RAMTOP 28599,
  entry USR 28600. Interrupts never accepted in the whole recording (game runs DI).
- Survey: engine unknown; GATE OK. Play area 0x7D9A = block copy of a back buffer (68,314 T/call,
  27,656 calls) -> back-buffer game; 0x7D28 = 8-byte cell plotter (224K calls, 11 callers);
  0x80D6 attrs; 0x93E9 full-screen draw (title/message screens); 0x954D status panel.
- Plain conversion: simulated boot OK; tail location not proven safe (survey WARNING) - prove with
  `scan --range` at stage 1.
- Screens seen (preview.png): play area with yellow-on-olive platforms, status panel "THE DEATH OF
  TORQUEMADA", a message screen (green text on brown).

## Screens without play / over play (found in code 2026-11-02; user unsure)
- No pause and no window drawn over the play area found. Every non-play screen is FULL SCREEN
  (0x93E9 = clear + draw), so Layer 2 / sprites must be off or cleared while it shows:
  - Title + options menu: 0x921E draws it, JP 0x8F11 polls keys 1-5 (row 0xF7FE): 1/2/3 pick a
    control set (key table at 51960), 4 = define keys, 5 = start. Reached in the recording.
  - Define keys 0x8FE0-0x9080: full screen, prompts STAB / JUMP / DUCK / LEFT / RIGHT / MASSACRE
    (strings at 36993-37066). NOT reached in the recording (survey "untouched" 0x8FA7-0x90CA).
  - Message screen (call 0x93E9 at 0x702F, start of a game/level): green text on brown
    ("YOU MAY RUN BUT YOU CANNOT HIDE DEVIANT..."), seen in preview.png.
- In play: CAPS+SPACE (ROM BREAK-KEY 0x1F54 at 0x72C4) then SPACE -> 0x7300: if (byte) = 122
  draws via 0x7D31 and sets 4 attribute cells of the top panel row (22532/3, 22554/5) to 127.
  An in-play action on the ULA panel, not a pause; reached 21 times.
- Ask the user for a recording that uses "define keys" (option 4) if that screen must be proven.

## Design (stage 1 observations, 2026-11-02)
- Rendering model: back-buffer composer [observed]. Buffer 0x5CF6 (23798), 32 bytes per pixel line,
  linear; 0x7D9A copies 28 x 120 of it (from 0x5DF8) to screen 0x4022.. (rows 1-15) with LDI.
  Attributes are not per figure: platforms red, background cyan, set per room (0x80D6).
- Figure plotters [observed], masked AND/OR into the buffer with save-under to IY:
  - 0x7A24 (31268) 32x32 facing right; 0x7A82 (31362) facing left (mirror table 62394).
    51930 = 4/5 -> 24-wide variants 0x7FBF / 0x8000 / 0x80A2 / 0x80BB [inferred from code].
  - Restore (save-under back): 0x7B61 (31585), 0x7B8B (31627).
  - 8x8 masked plot 0x79ED + restore 0x7A11: no CALL found [inferred unused].
  - Callers: 0x710A / 0x7110 = Nemesis (player); 0x851A / 0x8520 = enemies (terminators etc.);
    0x7161 / 0x7169 = a third figure kind (few calls).
- Scenery / objects: block blitters 0x82C3 (OR), 0x8300 (copy), 0x834E (masked) with inline
  parameters (POP IX), buffer base 23798 [observed].
- Depth: figures are masked over everything already in the buffer, nothing drawn after them
  [observed] -> sprites always in front of the scenery = the game's own rule.
- Cards: patch.scratch-redirect REJECTED (plotters take HL directly; no shared address helper);
  plan = hook the two plot entries (and the 24-wide variants): skip the buffer write, keep the
  save-under (restore then writes back unchanged bytes), build the sprite from DE (mask+image) at HL.
  detect.gameplay-screen-readers: to run in stage 2 on the buffer readers listed in Open.

## Build plan (stage 1 end, 2026-11-02)
- Every plot / restore site (CALL / CALL cc, from the snapshot):
  plot 32 right 0x7A24: 0x7107 (player), 0x74C2, 0x715E (Z), 0x8517 (Z, enemies)
  plot 32 left  0x7A82: 0x710D (player), 0x7166 (NZ), 0x851D (NZ, enemies)
  plot 8x8 0x79ED: 0x70EE (NZ, when (51808) != 0; DE = 32412) ; restore 8x8 0x7A11: 0x7144 (NZ)
  restore 32 0x7B61: 0x7134, 0x74CE, 0x86A2 (Z) ; 0x7B8B: 0x713A, 0x86AA (NZ)
  copy 0x7D9A: 0x70AE, 0x711D, 0x74C5, 0x9217 (title) ; main frame: 0x7107 plot player,
  0x711A CALL 0x83A9 (enemies plot), 0x711D copy, 0x7120 CALL 0x8613 (enemies restore), 0x7134 restore.
- Method (no card fits exactly; candidate new card "overlay from save-under"): the plotters run
  UNCHANGED, so all game memory (buffer, save-under areas) stays bit-identical to the original
  and the verifier compares everything except the ULA pixel area. Hooks:
  1. plot entries 0x79ED / 0x7A24 / 0x7A82 (and 24-wide 0x7FBF.. via 51930=4/5): log
     (HL buffer addr, IY save area, DE graphic, kind) to a per-frame list, then the original.
  2. copy 0x7D9A exit: for the logged figures in REVERSE order, write each save-under rectangle
     (the background before that figure) onto the screen (buffer line L = screen y L, column c
     = screen column c, visible lines 8-127, columns 2-29), then build sprites from DE
     (mask AND, image OR; mirror via table 62394 for left) and clear the list.
     Colour: cell ink where the game sets one, else the cell paper; mask-outline pixels = paper (solid).
  3. full-screen screens (0x93E9 entry, title 0x921E): sprites off ($15), list cleared.
- Hooks in alt ROM image 1 (`altrom`, decision table); interrupts are off all game (isr: 0 accepted).
- Cost: original plot ~? T (cost --at 0x7A24); copy 68K T/frame; set a budget before writing asm.

## Engine (stage 2, 2026-11-02)
- nexclash/nemesis.py + asm/nemesis_hooks.asm + docs/profiles/nemesis_the_warlock.json; hooks and
  state in RAM page 24 at MMU slot 1 (0x2000-0x3FFF; the game reads no ROM there); tail 0x5E00 (back
  buffer, write-first). Sites: 31213 / 31268 / 31362 (plot log), 32154 (copy -> post), 37865 (cls).
- post (after each copy): palette 1 / 2 = room attribute (51800) ink / paper; save-unders back onto
  the screen, last figure first; 4 sprites (2x2, 4-bit) per figure, pattern cache 32 x (graphic, width).
- Plots with the save-under in ROM (IY = 0: 0x7162, when (51932) is set) are PERMANENT stamps into
  the buffer (no restore): scenery, left on the ULA [observed: model check failed until excluded].
- Verifier: original replay; per plot the hook vs the original instruction; per copy the hook from
  the original's RET (first 20 copies run e_cp in full): registers, all game memory except the ULA
  pixels, ULA = background model (save-unders), sprite layer = figure model (mask / image, mirror),
  palette = room attribute, and the model itself = original screen (background + figures).

## Results
- quick 2000 (2026-11-02): 475 copies (20 full), plots 710 right / 795 left / 52 8x8, 517,912 sprite
  pixels IDENTICAL; unit: edges 252, 8x8 16, 16 overlapping, stamp, negative control 1/1 PASS.
- Speed (post hook, 28 MHz): 53,447 T mean / 242,166 T max (~8.9K / 40K T at 3.5 MHz); cache
  misses ~0.13 per frame (34 graphics in 2000 frames).
- quick 20000 (2026-11-03, after the XOR / wrap fixes): 4,715 copies, plots 9,544 / 10,753 / 598,
  XOR effects 1,136, 6,470,310 sprite pixels IDENTICAL in 2 min; speed 12.6K T mean / 54K max (3.5 MHz).
  It found two cases 2000 frames missed: an XOR-90 effect (0x89F9 / 0x8A06) toggling buffer bytes
  under a figure (now logged as events, undone and redone around the save-unders) and a figure at
  column 31 wrapping 3 bytes onto the next line's column 2 (left on the ULA, as the original shows).
- Builds: plain f1497589ddf479e34d42f6ab0618954d, sprites 36c8a2e8a7e50c092d4740099e446696.

## Decisions
- 2026-11-02 user: plain .nex runs on CSpect (hardware not yet).
- 1, 2, 3, 5: defaults (every figure a sprite; scenery/HUD/text on ULA; figures in front = game's
  rule; sprites off while full-screen menus are up).
- 4 (user, verbatim): "if game defines a colour, use it, otherwise same as background paper
  colour". Reading: sprite ink = the attribute ink the game sets in the figure's cells; where the
  game sets none for a pixel (mask outline / unset), the room's paper colour. Confirm with the
  first sheet.
- 6 (user 2026-11-02): SOLID sprites (mask-outline pixels opaque in the paper colour). Spikes: not
  answered; they are scenery in the buffer (blitters 0x82C3..), so they stay on the ULA by rule 2.

## Lessons
- [card detect.buffer-layout-producer §Contract] Overlay from save-under: with a masked back-buffer plotter that saves the background (IY), the hooks leave the plotters and all game memory untouched and rebuild the screen from the save-unders after the copy; the verifier then compares ALL game memory. Card amended with this as a second producer pattern.
- [local: game-specific] A plot whose save-under pointer is in ROM is a permanent stamp (scenery), not a figure: check every plot caller's save pointer before treating it as a sprite.
- [doc docs/PLAYBOOK.md §6. Verify (differential test)] Quick runs: 2000 frames missed two rare cases that 20000 found (XOR effect under a figure, column-31 wrap): when a game verifies at ~10K frames/min, run the quick check at 20000 before stage 3. PLAYBOOK 6 amended.
- [local: measured here; the PLAYBOOK speed budget already asks for it] Row address arithmetic per row cost 3x the copy itself (620 T/row): compute visible row range + screen address once, step with the next-line routine.
- [local: one-off extraction; a later game with only an RZX should add an `rzx extract` command] SPIN RZX snapshot blocks are zlib-compressed Z80 (flag 2); extracted with a 10-line block parse; no CLI command extracts the first snapshot to a file.

## Technique use
- detect.buffer-layout-producer: helped: copy -> buffer -> masked plotters with save-under found in 3 scans

## Stage log
- 2026-11-02 stage 0: ~2 h wall (survey ~1.8 h for 135K frames), ~25 tool calls, 4 user rounds; menus found in code.
- 2026-11-02 stage 2: ~3 h, ~60 tool calls, 1 user round (engine, quick runs, record).
- 2026-11-02 stage 2 start: plan + every call site; broke before code (session ~65 calls, PLAYBOOK Sessions).
- 2026-11-02 stage 1: ~40 min, ~20 tool calls, 2 user rounds (design answered, item 6 open).
