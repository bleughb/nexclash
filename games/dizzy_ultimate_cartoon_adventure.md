# Dizzy: The Ultimate Cartoon Adventure (Dizzy 1) - XOR engine, every figure on Layer 2

48K. Engine nexclash/dizzy1.py (`dizzy1_xor`; replaces the old printer-buffer builder
dizzy1_patch.py, which moved only Dizzy to a sprite), hooks asm/dizzy1_hooks.asm, profile
docs/profiles/dizzy1_ultimate_cartoon_adventure.json, colours docs/profiles/dizzy1_colours.json
(Dean's painted sheet, 2026-10-14). Reference files (private repo, specnext/reference/
dizzy_ultimate_cartoon_adventure/): the snapshot (md5 0659328f; selftest input dizzy1.z80),
dizzy1rzx (selftest input dizzy1.rzx), the colour sheets + painting layout, Dean's painted sheet
(dizzy1_PAINTING_SPRITES_painted.png).

| Output | MD5 |
|---|---|
| dizzy1_sprites.nex | 38e1a4916eaf8548d9ba8886861ca147 (Dean's painted colours; altrom + Layer 2) |
| dizzy1.nex | 7892b2e0f1f3f9f19165516db307cbe0 (unchanged) |

## Build (2026-10-14, Midnight Resistance standard)
- Every figure the game draws leaves the ULA: Dizzy, creatures, items, carts, clouds, the wizard,
  spider threads, egg + rope dots (every caller of both plotters from the code). Objects show on
  LAYER 2 (Dean 2026-10-14, chosen over hardware sprites): per-pixel colour, exact for every path.
  DIZZY is hardware sprites 0-3, always in front of every object (Dean 2026-10-14, after the first
  hardware test: on one shared XOR layer Dizzy and the grease gun cancelled each other's pixels).
- Hardware round 1 (16a00451, Dean 2026-10-14): runs well; Dizzy mixed with objects he touched
  (fixed: sprite in front); collectables change colour - that is the game's own pulse (the item
  handler cycles IX+15 through 1-7, 56418 / 57625), KEPT by Dean's choice (painted pixels stay
  fixed).
- Stay on the ULA: room tiles (58546), score digits / lives (62670 / 62691 / 62736), item name
  (60746). Figure pixels inside an effect strip (types 3 / 7: scrolling / rotating rectangles) are
  folded back to the ULA before the effect runs (the original garbles them there too).
- Method: converted writes go to a 1-bit SHADOW screen + shadow attributes (page 26, slot 3 during
  a hook) instead of the ULA, so ULA XOR shadow == the original screen at every moment (XOR is
  linear). Layer 2 shows the shadow: pixel set = the figure's colour, clear = transparent. XOR
  parity (double draws cancel) is therefore the original's by construction.
- Solid figures (Dean 2026-10-14): a figure's ENCLOSED paper (paper pixels not reachable from
  outside the frame through paper, 4-connected - Dizzy's eyes and mouth, the inside of a bottle) is
  opaque black by default, for every figure. A fill shadow (page 27) is XORed with the interior
  bits of each converted write, so the fill appears and disappears with the figure's ink (same XOR
  parity); display only - logic never sees it. Pixel rule: ink -> its colour; else this graphic's
  own interior -> its fill colour (another figure's interior -> black); else transparent; a pixel
  painted transparent shows nothing.
- Painted colours (Dean 2026-10-14): his painted sheet -> dizzy1_colours.json (1,846 pixels
  recoloured, 109 transparent, 633 graphics bytes; nothing ambiguous). 264 painted pixels were
  ignored: black on paper OPEN to the outside of a figure (the door's gaps, one "from the code"
  figure, edge pixels of 13 Dizzy frames). Outside paper is see-through by design; making it solid
  would need the reader to mark painted outside paper as fill (engine change: ask Dean first).
  Dizzy now takes 92 sprite patterns (88 with default colours).
- Colours: per pixel the painted colour of its graphics bit (plane pages 40-54, 8 bytes per graphics
  byte: 8 colour nibbles, interior mask, transparent mask, has-colours flag; keys: G = plotter 2
  graphics address, D = Dizzy frame 0-38 byte, the shifted copies 39-77 share them). Painting sheet:
  interior pixels are paintable (black by default); painting an opaque pixel (ink or interior) the
  sheet's GREY (RGB 100,100,100, the box background) makes it TRANSPARENT (e.g. inside the grease
  gun's handle), painting a colour back over it undoes that. Else the default: Dizzy bright white; plotter 2 figures that paint their cells
  (B bit 0/1) the bright ink of C ^ 7 (the colour they show on the rooms' white-ink cells; their
  attribute XOR goes to the shadow attributes, so they no longer recolour the scenery); others
  bright white.
- Dizzy: his writes go to his own shadow (page 28; ULA ^ objects ^ Dizzy == the original), not to
  Layer 2. Sprites 0-3 (2x2, 4-bit; 88 patterns built from frames 0-38 with the interiors black and
  the painted colours / transparency; the shifted copies are the same frames 4 px right) at x = 4E,
  y = 192 - L - rows. The sprite follows the XOR parity: a plot of the image shown = the erase, which
  only marks it pending (the draw follows at once in all 1,175 RZX cases, often across an
  interrupt: hiding there would flicker); any other plot = the draw. A pending erase is hidden at the
  next plotter-2 call or room wipe (death / room change). A plot the original skips (y + rows >= 200,
  8 bits) changes nothing.
- Logic reads stay the original's: collision 60244 / 60251 read ULA ^ objects ^ Dizzy (virtual
  read), the attribute read 58712 reads ULA ^ shadow attributes.
- Hooks: alt ROM image 1 at 0x2000- (1,984 bytes incl. the sprite table) (the game reads no ROM byte above 0x0369); variables +
  hook stack 0x5B40-0x5BC0 (printer buffer: never touched by the game, RZX scan; the interrupt
  handler's own stack is 0x5BCF-0x5BFE); tail at 0x5B00. Interrupts stay on: the in-game handler is
  the ROM's 0x0038 (keeps every register, reads IY) at every hook site in the RZX (verify checks it).
- Speed: the game has NO frame sync (no HALT in play, nothing reads FRAMES but the ROM), so hook
  time slows it directly. Both plotter entries switch to 28 MHz for the whole plot and swap the
  return address for a ROM trampoline (t_p2 / t_dz: dead slot rewritten with the original value,
  back to 3.5 MHz); the small hooks switch speed at their first / last instruction. Measured over
  the RZX: see the auto Speed line and docs/VERIFICATION.md (the median frame is faster than the
  original; a room change pauses up to about two frames longer: the wipe folds three shadows).

## Facts
- Snapshot: PC 63496 (title), IM 2 (I 0xFE; vector JP at 65021, rewritten by the game: 63578 =
  title music handler, which DECs the interrupted B / C and sets carry; 0x0038 = ROM handler in
  play, set at 63611), EI, SP 65534; the game stack in play is 23549 down to 0x5BCF.
- Plotter 1 (Dizzy) 58113: pure XOR, entered 59488 (erase) / 59515 (draw); screen write 58184;
  frames 0-38 + pre-shifted copies 39-77 (exactly frames 0-38 four pixels right, checked); graphics
  24290-29049 (crosses into slot 3: hooks read the byte before slot 3 changes).
- Plotter 2 57983: byte-aligned, clips to columns 1-30, frame table 53148 / data 43485, 256 frames
  (font 0-40, room tiles, objects). Attribute routine 58702 (B bit 0 before / bit 1 after, colour C).
  Self-modified by the game: 58079 = XOR C (0xA9) / OR C (0xB1) / LD A,C (0x79) and 58709 = XOR (HL)
  (0xAE) / NOP (0x00): the room renderer (58460) uses OR / LD and NOP for its tiles, 58575 restores
  XOR; 58010 = row helper 57771 or 57797 (clipped rows, 54811 from 56946 / 56972 / 57433; 76 calls
  in the RZX). The hooks compute the original's new byte from the virtual old one for every mode.
- Every caller of plotter 2 (static scan of all RAM + RZX): 54805 (object records: 256 x 20 bytes
  at 38365; +1 x, +2 y, +3 frame, +4 type, +6 animation, +15 colour; drawing types 1, 2, 4, 5, 6,
  8; 23 call sites via 54766 / 54762 / 54811), 54958 (spider threads, frame 73), 58546 (room
  renderer), 60698 / 60723 (egg + rope dots, frames 160-164), 60746 (item name), 62670 / 62691
  (score digits), 62736 (lives). Plotter 1: only 59488 / 59515. Every screen-addressing routine
  uses the line table 23750 (built at 58197): the plotters' row helpers, the wipe 58634, the effects
  55964 / 56092 / 56178 / 57104, the collision probes 56542 / 60158 (which read through 60228).
- Logic reads figure pixels only in the collision test 60228 and figure-coloured cells only through
  58712 (callers 56676, 58436, 60132, 60215: 884 reads of a figure cell in the RZX).
- Room wipe 58634 (lines 40-183, columns 1-30) + attribute wipe 58666 (rows 5-22): the hooks fold
  the shadow there first (ULA ^= shadow, shadow = 0, Layer 2 cleared; the game zeroes the ULA next).
- Executes `LD R,A` (machine.py re-runs such frames with exact counting).

## Verification (2026-10-14)
`auto` with dizzy1.rzx: every hooked routine forked from the real state (whole plotter calls to
their return, attribute reads, wipes; segments for the collision reads and effect folds), original
vs patched compared: all registers (AF' included), all memory, screen / attributes as ULA ^ shadow
== the original, Layer 2 pixels against an independent Python model of the shadow and colours;
per hook instruction IY / I / IFF / IM / alternate set unchanged, hook stack room for an interrupt,
no pushes below the game SP, slot 3 and 3.5 MHz restored, no fetch at 0x3D00-0x3DFF; the ROM
handler installed; no unhooked instruction reads or writes a byte / cell holding figure bits; the
game never writes a patch site; patch-site interiors only reached sequentially. Unit tests (paths
the RZX misses or reaches without figures): every plotter mode (XOR / OR / LD x attribute XOR /
NOP) converted and kept, kept / HUD / converted / Dizzy draws over figure bits, rows past line 191,
attribute and collision reads outside the screen, every effect branch with figures inside run to
its end, wipes with figures everywhere, a synthetic colour map (incl. the shifted Dizzy copies and a
wrong check byte); negative controls: no virtual read, no fold (rotator, wipe), room renderer
converted, hook stack too deep, colour map left out. Results: docs/VERIFICATION.md.

## Hardware checklist (Dizzy1 sprite build, CSpect first: new memory layout + Layer 2)
1. Boots to the title; title music plays normally; any key starts the game.
2. Dizzy walks / jumps without flicker or trails; no Dizzy pixels left on the scenery; he is
   always in front of items and creatures (e.g. standing at the grease gun: no mixed pixels).
3. Creatures, items, clouds, carts: no attribute colour blocks around them any more (the clash is
   gone); they show in their own colours over the scenery.
3a. Figures are solid: Dizzy's eyes and mouth are black, scenery does not show through them.
3b. Painted colours: Dizzy's red gloves and boots, objects as on the reference sheet; pixels
    painted grey are see-through. Collectables still pulse (the original's pulse; painted pixels
    stay fixed).
3c. Dizzy disappears cleanly when he dies / changes room (no frozen Dizzy left behind).
4. Spider threads and the egg-and-rope dots draw and disappear cleanly.
5. Objects fall and land on Dizzy as before (collision); picking items up works; the item name
   line and score / lives update.
6. Room changes: no figure left over from the previous room; the new room draws completely.
7. Game speed: Dizzy and the creatures move at the original speed (the Next build should not feel
   slower; room changes may pause a frame longer).
8. Scrolling cloud / sign strips: a figure passing through may leave pixels there (the original
   does the same).
9. Lose all lives -> title -> new game: everything resets.

## Open
- Hardware test of 38e1a491 (checklist above).
- Painted black on see-through paper (264 pixels, see Build) is ignored: ask Dean whether those
  areas (e.g. the door's gaps) should become solid.
- Repainting: paint the new dizzy1_PAINTING_SPRITES.png (drawn with the current map; its layout
  carries the map, so only changed pixels edit it) -> `colours` -> rebuild + re-verify.
- `python -m nexclash.dizzy1 preview` draws figures in the DEFAULT colours (Dizzy plain white), not
  the colour map: the 2026-10-14 painted previews came from a one-off script (per pixel: the
  graphics byte that drew it -> colour_entry / clear_entry). Fold that into `preview`.
- A recording that reaches later rooms (the sheet's "from the code" group shows the figures no
  recording drew yet).
- Generalise into a generic XOR-parity template (STATUS open work 3).
