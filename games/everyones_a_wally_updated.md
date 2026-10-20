# Everyone's a Wally, updated (Mikro-Gen) - engine `wally2`, record `everyones_a_wally_updated`

A new game to the 2026-10-14 standard (every figure converted, painted per-pixel colours, paintable
outlines, recolour). The first version (engine `wally`, games/everyones_a_wally.md, record `wally`)
is FROZEN (record "excluded"; Dean 2026-10-14): wally.py, asm/wally_hooks.asm, its profile and its
builds stay as they are.

Inputs (private repo): specnext/reference/everyones_a_wally/wally.z80 (a9eeb555...) and
wallyrzx.rzx (72c7d1f6...; 11 autosave snapshots, stripped by the tools: 15,225 frames) - the same
files as the frozen version, not copied. Sheets and previews: specnext/reference/everyones_a_wally_updated/.

    python -m nexclash.wally2 sheet wallyrzx.rzx --z80 wally.z80 -o everyones_a_wally_updated \
        --preview 0,40,228,738,741,805,1312,1410

    python nexclash.py auto wally.z80 --rzx wallyrzx.rzx            (wally2 is the default)
    python nexclash.py auto wally.z80 --no-record --engine wally     (the frozen first version)
    python -m nexclash.wally2 colours PAINTED.png                    (painted sheet -> colours json)
    python nexclash.py recolour everyones_a_wally_updated_sprites.nex PAINTED.png   (seconds)

Code: nexclash/wally2.py, asm/wally2_hooks.asm, docs/profiles/everyones_a_wally_updated.json
(after any .asm edit: `python tools/asm2profile.py everyones_a_wally_updated`), record
docs/records/everyones_a_wally_updated.json, dispatch: nexclash/engines.py (wally2 first;
`--engine wally` = the frozen engine, the frozen record's recipe passes it).

| Output | MD5 | Status |
|---|---|---|
| everyones_a_wally_updated.nex (plain, tail 0x6B00) | 2e615b3e7ae995e6d6a6ed9e3f586d4d | boot sim OK (= the frozen plain build) |
| everyones_a_wally_updated_sprites.nex | 31c3ef131330d26238b01a69b35c647e | RZX IDENTICAL, unit PASS, recolour PASS; default colours (nothing painted); hardware untested |

## Status
Phase A done 2026-10-14; Dean answered (decisions below). Phase B done 2026-10-14 (build, full RZX
IDENTICAL, unit + negative control, recolour). Phase C (hardware) next: checklist below.

## Snapshot (0b)
128K snapshot of a 48K game: 7FFD 0x10 (ROM 1, bank 0), PC 46319 = control menu (1-3 input, 4
starts), IM 1, DI, SP 0xFBF2. Never writes 7FFD, never reads the ROM, beeper only.
Interrupts: `isr` over the whole RZX: 0 interrupts accepted (DI throughout) - hooks need no IX/IY /
stack-room rules, every slot is free of ISR use.

## Rendering model (back-buffer composer)
- Room entry: the room is drawn straight to the screen (tile / char printer 46940, tiles 47087, clear
  47379), then 47552 / 47567 save screen lines 64-191 to the clean store 0x5B00-0x6AFF and the
  attributes to 0xFE00.
- Every render: 61090 restores the clean store into the back buffer (0x6B00-0x7AFF, row y at
  0x6300 + y*32; attributes 0xFC00-0xFDFF, cell 0xFB00 + (y & 248)*4 + x/8); the room logic plots
  objects (B, C, 61329 paints), the render (47574, from 33096 / 33216 / 46104) plots the gang (A),
  47611 copies pixels (row table 33400, unrolled LDI 47653), 47637 copies the attributes.
  Other paths with A + copy: 61487/61490 and 61887/61890 (walk-in / walk-out sequences), 33099.
- A restore can come with no commit since the last plots (render 805: intro-walk B plots, then a
  room change and 61090): those plots never reach the screen - the hooks must drop pending sprites
  at 61090 (LEARNINGS 2.1). Seen twice in the RZX.
- Buffer writers over the whole RZX (`scan --writers`): only plotters A, B, C, 61329 and the LDI copy -
  nothing else draws figures. Game logic never reads the buffer or the screen as data.
- Screen-only writers (stay on the ULA): HUD (lines 0-63: 47019/47021, 47426, 59275), room tiles /
  text 46940-46957 and 47087, clear 47344-47359 / 47379 / 47397.

## Figures (every plotter caller, from the code)
| Plotter | Draws | Callers | In the RZX |
|---|---|---|---|
| A 45286 | gang member, 16x32 masked, IY = descriptor 48231..48235 (+0 frame 0-7, +5 x, +10 y, +15 room, +30 attr, +35/+40 gfx base; data base + frame*128), paints (IY+30) into 2-3 x 4-5 cells | 47597 (render), 61487, 61887 | all 3; 4,299 plots, frames 0-7, all 5 descriptors |
| B 43168 | masked 16x16, A = frame, data 33656 + A*32 (rows mask L, mask R, gfx L, gfx R), pos 43064/43065 | 21: 60787 60823 61544 61560 61777 62044 62055 62184 62237 62350 62361 62416 62430 62514 62664 62752 62795 63041 63171 63280 63708 | 5 of 21 (60823 61544 61560 62184 62514); 1,058 plots |
| C 43069 | OR-only 16x16 (no mask: see-through), data 33656 + A*32 (rows gfx L, gfx R) | 15: 61150 62288 62298 62605 62712 62854 62866 62880 62892 63249 63337 63448 63534 63904 64050 | 8 of 15 (61150 62288 62298 62854 62866 62880 62892 63534); 3,003 plots |
| 61329 | paints the last B/C plot's cells with (62063) | 62192 62857 62869 62883 62895 | after B 62184 and the four C 6285x/6288x |

- 33251 mirrors graphics IN PLACE: the gang's 37816-43063 whenever a member turns (the RZX shows
  their bytes changing: 2,000+ plots of mirrored frames) and 35064-35255 (B frames 44-49) from 61511.
  The build finds the orientation by a 16-bit check of the bytes as plotted against the snapshot's
  bytes and their mirror (no state to track); colour keys use the snapshot's orientation.
- Constant frames from the code (sheet group "From the code"): B 61544:48 61777:74 (also 72)
  62044/62055:122 62237:41 62350/62361:120 62416:48 62514:50 62664:52 62752/62795:54 63280:118;
  C 62298:100 62605:43 63337:86 63448:87 64050:109. The other callers take the frame from a table
  or a variable: only a recording shows them.
- Max per render in the RZX: 9 plots shown (11 drawn once, 2 of them wiped by a restore).
- Cost of the original per draw (`cost`, 4,000 frames): A median 12,478 T, B 5,152 T, C 2,231 T;
  A = 4.7 % of frame time. Hook budget: no more than the original per draw (wall time; at 28 MHz
  hook T count ~1/8).

## Dean's decisions (2026-10-14, answer to the phase-A question)
- Colours: an object takes the colour the game paints it (61329); no colour clash is the goal - one
  colour per figure, never the scenery cells' inks. Gang member: its own colour (IY+30). Painted
  pixels (the sheet) override.
- Outline: black, added on the left / right / up / down neighbours of the ink only - NOT on
  diagonals. (The masks' own opaque paper is not the outline rule.)
- Message windows / pause over the play area: Dean unsure -> searched (2026-10-14): over the whole
  RZX every direct write to the play area (36 episodes) is a room draw followed by the clean-store
  save 47552; nothing else draws there. Covered anyway: the play-area clear 47362 (every room change,
  walk-in / walk-out, from 47447 60745 60961 61452 61848) hides Layer 2 until the next commit.
- No test cheat.
- Not commented (taken as agreed): every figure a sprite (A, B, C), HUD / tiles / text on the ULA,
  depth = plot order, figures in front of the scenery; no new recording for now (the sheet covers
  what wallyrzx.rzx drew + the constant frames from the code).

## Build (phase B, 2026-10-14)
- Every figure (A, B, C) on Layer 2, not hardware sprites: Dean's outline rule needs one pixel past
  the 16-pixel graphic on every side (18 x 18 / 18 x 34), and Layer 2 keeps the game's plot order as
  the depth exactly (as Dizzy 1's figures). Double buffered: banks 16-18 / 19-21 ($12), the commit
  (47637, after the pixel copy) clears what it drew into the hidden buffer two commits before (box
  list), draws this render's plots, shows it ($12), Layer 2 on ($69 bit 7).
- Canvases (wally2.canvas): per graphic 18 x (rows + 2) bytes, built at build time from the snapshot's
  graphics and the colour map: code (ink / outline / painted clear), "the figure's run-time colour"
  or a fixed palette index. 40 gang + 133 B + 134 C graphics, 14 pages (44-57) the game never reads.
  Table (page 27): canvas page / offset and the 16-bit checks as stored and as mirrored.
- A plot converts when: fewer than 24 plots this render, y 64-160 (A) / 64-168 (B, C), x <= 240, the
  graphic in range and its bytes match a check; otherwise the original plotter runs (ULA). The hook
  emulates the plotter's end state exactly (registers, the game stack PUSH AF, (43067), self-modified
  operands) and skips the buffer / attribute writes, so the ULA keeps the clean scenery colours.
- Colour per figure: A = ink of (IY+30); B / C = ink of the attribute-buffer cell under the centre,
  replaced by the ink of (62063) when 61329 paints the plot; outline black; the map per pixel on top.
- Joined figures: consecutive B-B or C-C plots from different callers with 16x16 boxes at most one
  pixel apart are one figure (the two-part objects, the fountain's jets): their outlines are drawn
  first, then their inks, so no outline runs through a figure; other figures in plot order.
- 61090 (restore) drops the plots since the last commit; 47362 (play-area clear) hides Layer 2.
- Memory: alt ROM stubs 0x386E-0x38E9 (+ register block; nothing at 0x3D00-0x3DFF), page 26 at slot 0
  during hooks (code 0x0100, INKTAB 0x1800, plot list 0x1900, box lists 0x1B00 / 0x1C80), page 27 at
  slot 1 in plot hooks, canvas pages at slot 1 and Layer 2 pages at slot 2 only in the commit. All
  MMU slots restored (verified). .nex 393,728 bytes.
- Speed: plot hooks run at 28 MHz ($07 = 3, back to 0 at every exit); commit mean ~0.3 frame, max
  ~1.3 frames of 3.5 MHz time (simulator T / 8) - about what the removed original plotting cost.

## Verification (detail: docs/VERIFICATION.md)
wallyrzx.rzx: 15,225 frames, A 4,299 / B 1,058 / C 3,003 plots converted, 3,938 commits, 3,900
restores, 36 clears, 2,219,552 Layer 2 pixels - IDENTICAL (registers incl. AF', memory, staged plot
vs wally2.Model, canvas ink vs the original's bytes, the whole Layer 2 image at every commit). Unit:
930 position / guard cases, 921 graphic cases (stored, mirrored, changed byte), joined pairs + commits,
commit rounds (no stale pixels), restore; negative control 3/3. Recolour {} and a synthetic map =
the corresponding builds byte for byte.

## Hardware checklist (round 1; try CSpect first - memory layout and set-up are new)
1. Boots to the control menu (1-3 input, 4 starts); beeper sound unchanged.
2. Gang members: each in its own colour with a black outline on left/right/up/down only (no
   diagonal corners), animating and turning; the scenery around them keeps its colours (no clash).
3. Objects (enemies, items, the fountain's jets, the arrows): one colour each, black outline; the
   two-part objects show no outline line through the middle.
4. Depth: gang members in front of objects; later plots in front of earlier ones.
5. Room changes: the old figures vanish as the new room draws; no stale pixels or figure left over.
6. Edges: a figure at the left / right screen edge and at the top of the play area (line 64) clips
   cleanly; the top panel (lines 0-63) is never covered.
7. Speed against the original in a busy room (several gang members + objects); any tearing (a
   figure split for a frame) while moving.
8. Walk-in / walk-out sequences, game over, the end of the game: nothing left over a screen without
   play.
9. Faults: Fuse "Record from snapshot" on wally.z80, autosave off, send the RZX (or a photo / video).

## Proposal (phase A, as sent)
- Every figure a sprite: A (2 sprites of 16x16 each), B, C (C as see-through sprites, as the
  original ORs them). Nothing figure-like stays on the ULA; HUD, room tiles, text stay ULA.
- The ULA keeps the clean scenery and its own colours: A's attribute painting and 61329's paint go to
  the sprites only (no clash).
- Depth: the game's own rule - sprites in plot order, later plots in front (objects, then the gang in
  descriptor order 48235 -> 48231); every figure in front of the scenery (the back buffer always
  composes figures over scenery, so this is exact).
- Colours (defaults until painted): gang member = its attribute ink (IY+30); object = the 61329 paint
  if the game paints it, else the ink of the scenery cell under each pixel at run time (as the
  original shows it); masked outline (mask 0, gfx 0) = black; C paper transparent. Painted pixels
  (per graphics byte and bit, the sheet) override; outlines paintable on every graphic
  (paint_clear), also around C objects within their 16x16 box.
- Recolour from the start (RECOLOUR + recolour(), colours only in banks the game never reads).

## Open
- Hardware round 1 (checklist above).
- Dean paints everyones_a_wally_updated_PAINTING_SPRITES.png (any time): `python -m nexclash.wally2
  colours PAINTED.png` -> docs/profiles/everyones_a_wally_updated_colours.json (add it to the record's
  data list), rebuild + verify + stamp; or `recolour` for a quick look.
- Longer RZX: 16 B and 7 C callers never reached; the sheet shows only what wallyrzx.rzx drew (+ the
  constant frames from the code). Their graphics are converted already (all 307 have canvases).
- The commit is not raster-synced: the Layer 2 bank switch can tear for one frame (hardware to say).
- Commit cost worst case ~1.3 frames: optimise the draw loop if the game feels slower.
