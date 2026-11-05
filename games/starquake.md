# Starquake (Bubble Bus Software, 1985, 48K) - engine `starquake` (pilot game: unattended, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: imported into the repo 2026-11-04 (record starquake, stamped); JNext only, never on a Next.
Inputs: specnext/reference/starquake/ (starquake.z80 md5 b94691b0, t1, b1-b3 (from an in-play state with cheats poked), m1-m5,
starquake_loading.scr). Verify with NEXCLASH_NEXT_ROM = enNextZX.rom from the card (else the ROM3 negative cannot be seen).
Start with: the hardware checklist below. Open: under "Open".

## Import (2026-11-04)
Ported from Jon Attree's .nxc work, 2026-11-04 (pilot clone runs/starquake, base d7abd1c, head f20f2ea). Published .nxc:
Starquake v1.0 (md5 ad7b8da0, github.com/jattree/nxc), build starquake_sprites_loading.
Rebuild in today's tree = the approved build: plain f447d9b3, sprites 4efee172, sprites_loading 2e2f107e = `nxc.py --bare`
of the published .nxc on b94691b0. No pin: the engine writes the whole alt ROM image itself (altrom 0x2000-0x4000 +
altrom_low), which the new default leaves alone, so both fills give the same bytes.
Moved into the engine (the pilot used work/build.py and loading/work/mkload.py): build() and auto(); the loading-screen
hold (asm `loading` module, SAVEBIN blocks loading / loadend; the build puts bank 5's own screen at loading.picture, so the
.asm holds no game data), loading_nex(). The loading screen is a record input listed with the recordings (records have no
other slot for a non-recording input). verify's ROM3 comes from nextboot.system_rom3() ($NEXCLASH_NEXT_ROM), not the
pilot's SQ_ROM3 path; the fill-see-through negative reads the snapshot it is given.
Not registered for `recolour`: the colour map is the engine's own format (drop_outline, pixels), not coloursheet's, so
the shared tool and its selftest guard cannot read it (recolour_own_map() kept, unrun). No shared code changed.
ROM path check (new builds): every ROM byte the game runs is as recorded; WARNING: the game reads 43 printer-buffer
bytes before writing them (first 0x5BC0, PC 55724, frame 576 of t1), which the .nex leaves as NEXLOAD wrote them. The
approved build has it too (plain as well); a fix (keep_printer_buffer) changes the .nex: an opt-in rework, a hardware item.

## Hardware checklist
Tape screen shows, a key or 5 s leaves it; menu, define keys (from boot and after a game over) with no stray sprites; BLOB
and the enemies solid sprites in their own ink, black inside, no outline; scenery keeps its colours as BLOB passes; room
changes and screen clears leave no sprite; the high-score table and quit prompt; trainers 1-4. Watch: anything wrong in the
first room's list or the panel at the start (the printer-buffer warning above).

## Snapshot
Archive "Starquake (1985)(Bubble Bus).z80", b94691b08d31386d3e5661d04e6c164f, 48K, at the title menu (PC 0xDA3B in RAM, the
menu's beeper tune, DI, IM 1). No 128K release exists (archive: 48K only; [a]/[a2]/[a3] are alternates, [h] hacks). No .256 in
Spec256-256-all38. Keys: menu 0 = start (KEYBOARD OPQAM selected), play O left, P right, Q up, A down, M fire. ZXDB: not looked up (no network).
Tape "Starquake (1985)(Bubble Bus).tap": BASIC, a 6,912-byte screen at 16384, the game: the loading screen is that block
(loading/screen.scr md5 f95de364), held by the stub in bank 22 until a key or 5 s (method of Knight Tyme's loading stub).

## Rendering model (read, every address checked)
0xD9C8 once per game frame (after the HALT wait 0xA57B): CALL 0xDF70 plot, CALL 0xD8B1 paint, then logic.
- 0xDF70: six objects, record 0xDD18 + 32i. XOR erase at the old place (+0/1 line-table pointer, +2/3 image, +4 x byte), new
  place from +5 x, +6 y, +7/8 image base: image = base + (x AND 6) * 24, line table 0xDDDE + 2 * (175 - y) (entry k = line 16 + k),
  stored back to +0..+4, XOR drawn. 24 x 16 images, 48 bytes; the four shifted copies of a base are different animation frames.
  BLOB 0xE074 + 48n, 52 images; enemies and effects 0xA548 + 48n (0xAFC8 and up used), 144 slots. Object 0 is BLOB.
- 0xD8B1: each object's ink (+9, 0-7) into the cells under it whose paper bit 5 is clear; its last rows can run past 0x5AFF into
  0x5B00-0x5B1F, which the collision code (0xD338-0xD3B0, attribute < 64 = solid) reads. 0xD964: the room's own coloured cells
  (list at 0x5B20) put back. This paint is the clash: scenery cells take the figure's ink, figures take nothing.
- Other screen writers: 0xDB3B (cell-aligned XOR tiles with their own attribute: items, platforms), the room builder 0xEACD /
  0xEAFF, ROM print for menus. All cell-aligned with their own colours: left on the ULA.
- Clears: 0x5FD0 (whole screen; from 0x6194, 0x6618, 0x672A), 0xA647 (play area; 0xA45F, jump table 0xA412). The Cheops pyramid
  screen comes after 0xA647.

## Clash check (work/clash_check.py, 5,000 frames of random play, 20,504 plots, at the end of each frame's draw pass)
3.8 % of figure plots share a cell with scenery ink, which then shows in the figure's ink; 25,837 scenery pixels recoloured;
4.77 % of figure pixels not in the figure's own colour (cells with paper bit 5, item cells). Kind A. Owner: clash. png in
out/starquake_fix.png column 1 (BLOB cyan in a cyan cave, green inside a green enemy).

## Design (defaults taken: a human would have decided)
1. All six objects (BLOB, every enemy, shots, explosions) are sprites; items, platforms, lifts, teleports, scenery, HUD, text stay ULA
   (cell-aligned, own colours). 2. Depth: BLOB on top, then objects 1-5 in order; all in front of the ULA. 3. Colours: the game's own
   ink (+9), bright. 4. Solid figures: ink, holes and gaps of 1-2 px black (closing + hole fill), one-pixel outline white, black for
   a white figure (BLOB, shots), never on ink, ring-enclosed gaps filled with the outline colour. Small shots keep the outline (they
   are white, so it is black). 5. No menu or window over play needs Layer 2 handling; clears hide every figure sprite.
Hooks (asm/starquake_hooks.asm, alt ROM 0x386E, stateless but for a 12-byte image cache): e_pl at 0xD9CE (CALL 0xD8B1): per object
the image the plot drew (+2/3) -> pattern set (196 x 512 bytes, banks 13-19, pages 26-38), uploaded only when it changes, 4 sprites
2 x 2 at X = 8 * (+4) - 4, Y = line - 8; saves 0x5800-0x5AFF to page 38. e_un at 0xD964: puts the attributes back, then the list.
The plot keeps every ULA write: the solid sprite covers the XOR pixels. The game runs the same instructions in the same order.

## Results (2026-11-04)
| Output | MD5 | Status |
|---|---|---|
| out/starquake.nex (plain) | f447d9b3d937837d2427e021002a9648 | boot sim OK, reaches play in JNext |
| out/starquake_sprites.nex | 4efee1728e8092cdfd9f0e4ad859cf52 (was 50c75321) | boot sim OK, replay IDENTICAL, reaches play in JNext |
| out/starquake_sprites_loading.nex | 2e2f107e95cf80ea9412ba7023e819ee (was 3ed426eb) | tape's screen, bank 22 stub; reaches play in JNext and through the real loader |
| out/starquake.nxc | 30763c45b5805b7e5ee807015cc71984 | apply byte-exact; card_test10 copy: loader output = apply, default and cheats 1+2 (926d55c1) |
Import verify (selftest --game starquake --verify --stamp, 2026-11-04, ROM model NextZXOS ROM3 8c34d957): all 9
recordings IDENTICAL (40,884 frames), 12 of 12 negatives DETECTED (11 on m1, the paint overflow on b1), rebuild = the
recorded MD5s; ROM paths: every ROM byte the sprite builds run is as recorded; printer-buffer WARNING on every recording
but m5 (43-67 bytes read before written, first 0x5BC0 or 0x5B04).
Pilot replay (work/vlog/): t1 2,563, b1 8,001, b2 8,001, b3 8,062 frames, all IDENTICAL. Three simulators: original, patched, original with
each frame's paint undone; patched vs original all memory but the screen; patched vs paint-undone everything, bitmap with the six
images XORed out (frames ending inside the plot or a clear skipped: 389). Hooks: e_pl 21,212, e_un 21,212, e_rc 163, e_cls 5; 87,769
figure plots (model ink = plotted pixels), 19,191,258 sprite pixels against the model, 168 hides checked, 21,212 attribute restores.
Negatives (work/vlog/neg_final.log, neg_ovf.log): x+1, wrong page, BC clobbered, MMU7 left, BLOB not hidden, no e_un, plot store kept,
outline missing: DETECTED on b2; paint overflow store removed: DETECTED on b1 (frame 5398 is where it matters); tile store 0xDB51
removed: DETECTED. The room-list store 0xD978 removed was not detected: with the paint undone first it writes what is there already.
Outline census (work/canvas_check.py): 196 images, 16,174 outline pixels, ring complete, never at the canvas edge, no see-through hole.
Speed: hook 1,471.9M T counted at 3.5 MHz over 26,627 frames, 55K per frame, run at 28 MHz (about 7-9K of 69,888); JNext plain and
sprites identical at frame 1200 with the same keys. Cheats (work/cheats.py, 6,000 frames random play, original code): lives held at
4 or more (0 without), energy bars 0 and 2 held at 127, immunity lives held, no aliens 1,213 alien draws against 13,190; dropped:
No Rays (lives 2 against 0, not clear), Infinite Powers (same numbers as energy), key/card/door/access (not reached), Lives (0-255).

## Open
Hardware, CSpect: never run. Speed on a board (JNext: plain and sprites identical at frame 1200). 64 of 196 image slots never drawn
on a recording (enemy types not met; slots 0-55 are probably not graphics). The Cheops pyramids, teleports with codes, the core
assembly and the ending not played. Colour sheet in sheets/ (1:1, layout json); recolour() rewrites the store banks (not run on
a painting). Evidence record, doccheck, selftest stamp: not done (pilot).

## Lessons
- [doc BRIEFING C2 #5] NextZXOS ROM3 is not free at 0x386E: Its IM 1 handler CALLs 0x386E and its UDG print JPs 0x387E. Hooks written
  there over a ROM3-filled alt image run on every interrupt; write the whole image (altrom_low) and verify against ROM3.
- [local: a build step outside the engine] The approved .nex came from a script after the engine (mkload.py); importing it
  meant moving that step into build(), with its stub in the engine's .asm and the game's picture taken at build time.
- [local: loading screen as an input] The tape screen the build needs rides in the record's recordings list (md5-checked, staged beside the snapshot).
- [local: pre-shifted copies can be different frames] Starquake's four shifts of an image are four animation frames; model the image
  the plot drew, not the base plus a shift.
- [local: NOPing a painter can drop a write the game reads] The paint ran past the attribute area into 0x5B00, read by collision:
  save and restore the attributes round the painter instead of removing its stores. A full-memory lockstep found it (b1 frame 5398).
- [local: a reference with the paint undone] Compare the patched attributes against the original run with each frame's paint undone
  by the verifier, so a lost game store in the attribute area is caught.

## Techniques
Techniques: `patch.whole-altrom-image` (docs/records/starquake.json)

## Technique use
- patch.whole-altrom-image: helped: the crash was NextZXOS ROM3 code round the hooks; the card's rule (every byte from the build) fixed it.

## Stage log
- 2026-11-04: imported into the repo (refactor phase 7): rebuild = the published v1.0, full verify stamped. 0 user rounds.
- 2026-11-04 stages 0-3 in one session (pilot, unattended, after a usage-limit stop); 0 user rounds.

## Enhanced-colour check (2026-11-04, owner's standing step): MODERATE, not built
No .256 in Spec256-256-all38. Figures are 24 x 16 line art in one ink with some inner detail (eyes, mouths, BLOB's face), not
silhouettes, but small. Scenery: flip-screen rooms built by 0xEACD / 0xEAFF in whole cells with their own attributes, no scroll,
so a per-tile layer could recolour figures and scenery to one design (the room map format not read). BLOB (white) already reads
apart from the coloured enemies: colour would add looks more than play. Mock-up (rule-based tones, not a build):
runs/starquake/out/starquake_enhanced_mockup.png, work/mockup.py.

## Owner round 2026-11-04: define-keys crash, no outline
- Crash (owner in JNext: "starquake defining key crashes", four red figures and a white BLOB over the redefine screen). Cause:
  the alt ROM image is filled from NextZXOS's ROM3, and ROM3 has code of its own at 0x386E-0x3BF4: its IM 1 handler
  does CALL 0x386E (0x004A; KEY-INT moved there) and its UDG print does JP 0x387E (0x0B52). The build wrote only
  0x386E-0x3ABF over it, so every interrupt ran e_pl (sprites from the six records, paint, no KEY-INT) and the first arrow
  UDG the define-keys screen prints jumped into the middle of e_pl (unbalanced stack): sprites, hang, reset to NextZXOS.
  The menu title's dots are UDGs too, so the old build also hung at every menu redraw (after a game over). The verifier
  ran Sinclair's ROM, so it never saw ROM3's code. Fix: altrom (0x2000, 0x4000) + altrom_low (Sinclair 0x0000-0x1FFF),
  as Cauldron; _machine builds the patched image from ROM3 (work/rom/enNextZX.rom from the card) the way the stub does;
  negative _rom3_left (the old fill) DETECTED on t1, m1, b2. Evidence: work/dk/rom3repro.py, png/starquake_definekeys_jnext.png.
- No outline by default (docs/profiles/starquake_colours.json drop_outline 1): ink, black fill in holes. Negatives
  replaced: 'white outline drawn' and 'BLOB's black fill see-through', both DETECTED. Census work/canvas_check2.py: 0 faults.
  Mock-up png/starquake_nooutline.png (work/dk/figscan.py, nooutline_png.py): ink-edge pixels on scenery of the figure's
  own colour 0.2% over 14,765 sampled plots. Where it is weakest: white BLOB and its white shot against the white hover
  pad / white scenery (BLOB's old outline was black, so over black nothing changes); sparse spinners (images 64-67) read
  as dotted rings, as in the original.
- New recordings rzx/m1-m5 (work/dk/rec_menu.py): define keys, options 1-5, game over, define again from the post-game
  menu, play with new keys, Kempston/cursor/Sinclair, quit prompt N and Y (goodbye, reset). All 9 recordings IDENTICAL.
- Game logic note: the game reseeds its random numbers from FRAMES on entering a room (0xA486), so enemies depend on the
  frame of entry; JNext plain vs sprites match exactly with the key script shifted one frame (stub length).
- out/starquake.nxc bfa83a05 (prev 30763c45 kept as out/starquake.prev.nxc, old .nex in out/prev_30763c45/).
