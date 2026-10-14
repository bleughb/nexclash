# Everyone's a Wally, updated (Mikro-Gen) - engine `wally2`, record `everyones_a_wally_updated`

A new game to the 2026-10-14 standard (every figure a sprite, painted per-pixel colours, paintable
outlines, recolour). The first version (engine `wally`, games/everyones_a_wally.md, record `wally`)
is FROZEN (record "excluded"; Dean 2026-10-14): wally.py, asm/wally_hooks.asm, its profile and its
builds stay as they are.

Inputs (private repo): specnext/reference/everyones_a_wally/wally.z80 (a9eeb555...) and
wallyrzx.rzx (72c7d1f6...; 11 autosave snapshots, stripped by the tools: 15,225 frames) - the same
files as the frozen version, not copied. Sheets and previews: specnext/reference/everyones_a_wally_updated/.

    python -m nexclash.wally2 sheet wallyrzx.rzx --z80 wally.z80 -o everyones_a_wally_updated \
        --preview 0,40,228,738,741,805,1312,1410

Code so far: nexclash/wally2.py (capture, colour sheets, preview; no patch yet). Planned files:
asm/wally2_hooks.asm, docs/profiles/everyones_a_wally_updated.json (+ _colours.json once painted),
docs/records/everyones_a_wally_updated.json (written in phase B with the first build), dispatch in
nexclash.py cmd_auto (decide in phase B how `auto` picks wally2 over the frozen wally for the same
snapshot without changing the frozen build's recipe).

## Status
Phase A done 2026-10-14 (analysis, preview, both colour sheets); waiting for Dean's answer to the
phase-A question below. Phase B (build + verify) not started.

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

- 33251 mirrors 35064-35255 (B frames 44-49) IN PLACE when 61511 toggles (61510) (from 61527, the
  walk-in sequence). Not exercised by the RZX. Colour keys use the unmirrored orientation
  (wally2.canonical); the hooks must do the same (phase B).
- Constant frames from the code (sheet group "From the code"): B 61544:48 61777:74 (also 72)
  62044/62055:122 62237:41 62350/62361:120 62416:48 62514:50 62664:52 62752/62795:54 63280:118;
  C 62298:100 62605:43 63337:86 63448:87 64050:109. The other callers take the frame from a table
  or a variable: only a recording shows them.
- Max per render in the RZX: 11 plots (5 A + 2 B + 4 C).
- Cost of the original per draw (`cost`, 4,000 frames): A median 12,478 T, B 5,152 T, C 2,231 T;
  A = 4.7 % of frame time. Hook budget: no more than the original per draw (wall time; at 28 MHz
  hook T count ~1/8), patterns cached by graphic + colours.

## Proposal (phase A; Dean decides)
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

## Phase-A question (2026-10-14, sent with the preview and both sheets)
Sprites (all of A/B/C), ULA (HUD, tiles, text), depth (plot order), colour defaults and the sheets,
plus: a longer recording (16 B and 7 C callers not reached: other rooms, tasks, items), whether the
game opens message windows over the play area, and a temporary immortality cheat for the rounds.

## Open
- Answer to the phase-A question.
- Longer RZX: the sheet covers only what wallyrzx.rzx drew (+ the constant frames from the code).
- Mirror block 35064-35255 and the walk-in / walk-out paths (61487, 61887, 33099): unit tests (phase B).
- Dispatch: `auto` on wally.z80 must reach wally2 while the frozen record still rebuilds its own
  outputs (`selftest.py --game wally`).
