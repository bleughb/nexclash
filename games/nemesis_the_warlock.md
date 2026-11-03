# Nemesis the Warlock (Martech 1987, 48K) - https://spectrumcomputing.co.uk/entry/3387/ZX-Spectrum/Nemesis_the_Warlock

## Next session
Stage: 4 (hardware round 2, when the user reports)  State: round 1 OK on hardware (basic play, 2026-11-03)
Inputs: specnext/reference/nemesis_the_warlock/ (snapshot, rzx, both .nex)    Branch: claude/festive-einstein-sx8txv
Start with: the user's report from longer play (later levels, define keys, speed)
Read: PLAYBOOK stage 4, ## Engine, ## Hardware checklist
Open: colour sheets not built (fixed rule); stamps (bodies) on the ULA; speed spikes (87K T max)

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

## Colour map (stage 3 gap closed, 2026-11-03)
- Card patch.runtime-colour-map. Patterns are built on a cache miss per (graphic, width); per
  painted image an AND / OR pair per pattern byte (1024 bytes, builder's output order), index at
  page 26 (count, g lo, g hi, w, page, address), streams pages 26-37 (banks 13-18, 95 images max),
  mapped at slot 0 only inside `build` (then 0xFF = ROM; interrupts off all game). `pout` applies
  the pair. Unpainted images: one flag test per byte.
- Keys: image byte '%04X' (check = its value), bit 0 = leftmost as stored; codes 1 ink (palette 1 =
  room ink), 2 solid paper (palette 2 = room paper), 0 clear (paintable, paint_clear). Palette
  3-15 fixed: black, blue, red, magenta, green, cyan, yellow, white, bright red / magenta / green /
  yellow / white (bright blue / cyan left out: 16 > 15). Painting with swatch 1 / 2 = follow the room.
- Images: 89 (profile colour_images; whole-RZX capture 94 s; graphics never change: 0 differ);
  colour_inputs 91c5e0503aaba7bf7d26217773467a3a / 20512 bytes.
- Sheets: `python -m nexclash.nemesis sheet RZX Z80 -o DIR` (89 figures each; shown in room
  attribute 40 = black ink on cyan, the commonest). Recolour: `python nexclash.py recolour`.

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
- FULL (selftest --game --verify --stamp, 2026-11-03): 134,977 frames, 27,656 copies (20 full),
  plots 77,738 right / 78,789 left / 4,517 8x8, 2 clears, 29,412 XOR effects, 47,173,776 sprite
  pixels IDENTICAL; unit PASS; boot OK both builds; rebuild MD5s match. Speed over the whole
  recording: 17.1K T mean / 86.9K T max per frame (3.5 MHz equivalent).
- Builds: plain f1497589ddf479e34d42f6ab0618954d, sprites 36c8a2e8a7e50c092d4740099e446696.

## Hardware checklist (round 1)
1. nemesis_the_warlock.nex (plain) starts and plays as before (CSpect: yes, 2026-11-02).
2. _sprites.nex: title and menu show no sprites; define keys (option 4) screen clean.
3. In play: Nemesis and the enemies solid, black ink / cyan fill, no colour change over red platforms.
4. Figures at the left / right edges of the play area clip at its border (no sprite over the side panels).
5. Bodies (permanent stamps) stay on the screen as before (ULA colours).
6. Speed: the game is no slower than the plain build in normal play; note any stutter when a new
   enemy type first appears (pattern build, up to ~1.2 frames).
7. Message screens between levels: no sprites left over them.

## Hardware rounds
- Round 1 (2026-11-03, sprites 36c8a2e8): user "all ok for now with a basic game play" - checklist
  1-7 no faults seen. Not yet covered: later levels, define keys screen, long-play speed.

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
- [doc CLAUDE.md §Rules] I wrote `kill -0 $(pgrep -o -f X)` in a wait loop - the warned pattern in a new form; CLAUDE.md's rule now names it.
- [doc docs/PLAYBOOK.md §6. Verify (differential test)] Quick runs: 2000 frames missed two rare cases that 20000 found (XOR effect under a figure, column-31 wrap): run 20000 before stage 3 when the verifier is fast.
- [local: measured here; the PLAYBOOK speed budget already asks for it] Row address arithmetic per row cost 3x the copy itself (620 T/row): compute visible row range + screen address once, step with the next-line routine.
- [tool nexclash.py rzx] SPIN RZX snapshot blocks are zlib-compressed (flag 2); I parsed them by hand. Now `nexclash.py rzx extract` (golden check in selftest --tools); MAINTAIN points to it. (Was mis-tagged local.)
- [doc docs/ENGINE_CONTRACT.md §Verify loop] Return shortcut: verify a hook on a long routine from the original's state at its RET (full runs for the first 20 calls): full verify 14 min instead of hours.
- [doc docs/ENGINE_CONTRACT.md §Verify loop] simpool.machine pools one simulator per slot name: my original and patched XOR runs shared slot 'p' and the second reset the first (false "memory differs", one retry).
- [card verify.model-reconstruction §Use] Rebuilding the original screen from the model at every event caught both rare bugs (XOR effect, wrap) the hook-vs-model check could not: new verify card.
- [doc docs/LEARNING.md §2b. Friction sweep] Not captured at first: toolkit and environment lessons were treated as engineering, not findings, and learncheck checked form, not coverage. Added the friction sweep and a check that a local-tagged lesson does not name shared code (learncheck).

- [card patch.runtime-colour-map §Evidence] Second game for the card: a pattern builder with no canvas takes the stream in its own output order (AND / OR pair per byte); a palette with run-time entries leaves fewer fixed colours. Card evidence + validation gap amended.
- [local: game-specific] `po` is a Z80 condition code (call po = CALL parity odd): sjasmplus refused the routine name; renamed pout.

## Friction
- reuse: [doc docs/ENGINE_CONTRACT.md §Verify loop] the return shortcut and per-event slots; [card verify.model-reconstruction §Use] the model rebuild check.
- retries: [doc docs/ENGINE_CONTRACT.md §Verify loop] simpool slot clash; e_x1 ending in its own RET never reached the verifier's stop address [local: an asm slip in this engine, caught by "did not return"].
- environment: [doc LEARNINGS 2.6] shallow clone without a remote-tracking ref (stop hook "no remote branch"); a force push the classifier refused was not needed (fast-forward) [none: no doc change].
- hand-rolled: [tool nexclash.py rzx] snapshot extraction from an RZX.
- scratch: [probe tools/probes/attr_census.py] kept; probe_model / probe2 / probe_keys / probe_prof dropped [none: they monkeypatch nemesis.py functions; nothing for another game].

## Technique use
- patch.runtime-colour-map: helped: Cauldron template (tables, recolour, identity) reused nearly as is
- detect.buffer-layout-producer: helped: copy -> buffer -> masked plotters with save-under found in 3 scans

## Stage log
- 2026-11-02 stage 0: ~2 h wall (survey ~1.8 h for 135K frames), ~25 tool calls, 4 user rounds; menus found in code.
- 2026-11-03 learning capture: rzx extract, attr_census probe, verify card, contract / LEARNINGS / LEARNING 2b, learncheck friction sweep.
- 2026-11-03 stage 4 round 1: hardware OK (basic play), 1 user round, no code change.
- 2026-11-03 stage 3: ~30 min, ~10 tool calls, 0 user rounds (full verification 14 min).
- 2026-11-02 stage 2: ~3 h, ~60 tool calls, 1 user round (engine, quick runs, record).
- 2026-11-02 stage 2 start: plan + every call site; broke before code (session ~65 calls, PLAYBOOK Sessions).
- 2026-11-02 stage 1: ~40 min, ~20 tool calls, 2 user rounds (design answered, item 6 open).
