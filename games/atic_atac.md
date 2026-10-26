# Atic Atac (Ultimate Play The Game, 1983; 48K) - engine atic_atac (stage 2 done: built + verified in software)

## Next session
Stage: 3 (prove + deliver)    State: engine complete 2026-10-26; full RZX already IDENTICAL (Results)
Inputs: specnext/reference/atic_atac/ (snapshot, AticAtac.rzx)    Branch: claude/atic_atac (both repos)
Start with: `python selftest.py --game atic_atac --verify --stamp` (the one full verification, ~12 min
  replay + ~1.5 min unit tests), then `python -m nexclash.records views`; colour sheets (docs/COLOURS.md:
  this engine has no sheet capture yet - write `sheets` / `capture` for the group images, or ask Dean
  whether default inks are enough for the first hardware round); hardware checklist below to Dean
Read: this file (Build design, Results, Open), PLAYBOOK stage 3, docs/COLOURS.md
Open: speed on hardware (setups ~2.5k T each); game-over path not recorded; menus / pause asked

Reference: specnext reference/atic_atac/ (Dean, 2026-10-26).

    python -m nexclash.survey Atic_Atac_1983_Ultimate_Play_The_Game_a.z80 --rzx AticAtac.rzx

| Output | MD5 | Status |
|---|---|---|
| atic_atac.nex (plain, tail 0x5B00) | e710fa8785802f1aa51f214d95c82343 | boot sim OK; hardware untested |
| atic_atac_sprites.nex (from the start state) | 59493b7563e6dd1c7141a6763cf52d73 | software IDENTICAL (full RZX), unit PASS; hardware untested |

## Intake (stage 0, 2026-10-26)
- Snapshot: 48K, LOADER state. PC 0x5B89 inside a descramble loop at 0x5B80 (USR 23424 from the
  one-line BASIC loader): `LD HL,24575 / LD BC,124 / XOR A / RRD / INC HL / DJNZ / DEC C / JR NZ`,
  then `JP 24576` (game entry). IM 1 (ROM ISR), I = 0x3F, SP 0x5FE7, RAMTOP 24574, border 0.
- CORRECTION (stage 1, 2026-10-26): the RZX embeds its OWN snapshot (rzxinfo: start address 41446 =
  0xA1E6, game running, code already descrambled); only the .z80 is at the loader (PC 0x5B89).
  So no prerun is needed for the recording; the nex start state is the .z80 run to JP 24576
  (simrun.free_run stop_pc=24576, 2 frames) written with get_state/write_snapshot. loader.prerun's
  test sees memory only and, on this RZX, returns frame 0 = the embedded snapshot.
- Recording: AticAtac.rzx, 18,278 frames (6 min), no autosave snapshots, no desync. Plays to the
  escape ("Congratulations, you have escaped", 5:46, score 8060, 39%). Rooms with stairs, doors,
  monsters, the chicken meter and the scroll panel all seen (preview.png).
- Engine: unknown (identify). ISR: ROM IM 1 only, reads IY (keep IY), 16 bytes below SP.
- Lowest SP 0x5DD8 (whole recording, loader phase included).

## Screen writers (survey, routine -> what it draws)
| Routine | Calls | What (preview) |
|---|---|---|
| 0x9F21 (40737) from 0x9EAC | 557,574 | figures (monsters, player, items): byte plotter, 178 T median |
| 0x9EDC (40668) from 0x9EA3 | 546,381 | figures, second plotter (pair with 0x9F21: draw / erase or the two shifts) |
| 0x9C61 (40033) from 0x9D08 / 0x9C5D / 0x9CC7 | 183,564 | room outlines: one byte per call (line drawing) |
| 0x8093 (32915) from 0x9150 / 0x973D | 126 | play-area clear (24 x 192 bytes) on every room change |
| 0x9980 (39296) from 0x920E | 38,939 | attributes only (room / figure colours) |
| 0x7EB2 (32434) from 0x7DE7 / 0x7E0E | 14,847 | attributes of the side panel (x 200-247: chicken, lives) |

Coverage GATE: one unreached CALL, 35893 (0x8C35) -> 0x8093, reached by `JP Z,35893` at 36516. It
is the GAME OVER path: clear the play area, print "GAME OVER" (string at 35929 via 41459), wait,
`JP 31785`. Not a figure plotter -> the gate passes; the game-over screen is untested by the
recording (stage 3 checks it with a test cheat off, or a second recording that loses every life).

## Engine (stage 1 analysis, 2026-10-26; start state = .z80 run to JP 24576)
- Rendering model: PURE XOR to the screen for every figure. Two row blitters, 0x9EDC (40668) and
  0x9F21 (40737), one CALL site each (0x9EA0 / 0x9EA9) inside the row loop at 0x9E9B; each call XORs
  one row of 2-3 bytes. The pixel shift is a self-modified JR at 0x9EE4 / 0x9F29 (written at 0x9F91
  = 40849: LD (40677),A), shared row-advance at 0x9F03. Figure-level entries: 0x9F40 / 0x9F45 /
  0x9F4A / 0x9F56 / 0x9F74 / 0x9F80 (draw object IX). Object records at 0xEA90.. (IX groups in cost).
- No logic reads figure pixels (figdep, whole recording): every non-plotter read of a byte holding
  figure pixels is a drawer's own read-modify-write - room-line OR (HL) 0x9C75 x1150, and the
  scenery-object drawers' run-time op (XOR/OR (HL)) at 0x99D7 x265, 0x9A78 x83, 0x9B88 x16,
  0x9ADD x14, 0x9A36 x2. No collision or decision reads the screen -> no virtual read.
- Writers that change figure bits (they break ULA = scenery ^ figures):
  0x809F play-area clear 0x8093 (room change 0x914D / escape 0x973A / game over 0x8C35);
  0xA190/0xA193 = 0xA185, zero a 2x20 cell then re-plot via 0x9F4A (IX = 0xA17D; from 0xA16E and the
  3-slot loop at 0xA2F3: the pocket icons in the panel);
  scenery-object drawers 0x99D8 / 0x9ADE / 0x9B89 / 0x9A79 / 0x9A37 (op at the NOP before each
  picked by 0x9D19: B&3 = 0 LD, 1 OR, 2-3 XOR (HL)); room-line OR 0x9C76; text printer 0xA1E6
  (8-row glyph LD (HL),A; the escape message over the play area, frame 18184).
  Counts, whole recording (writes / of them changing figure bits): 0x809F 17894/9587, 0xA190
  3834/3834, 0xA193 2200/2200, 0x9C76 1150/145, 0x99D8 712/343, 0x9ADE 475/209, 0x9B89 447/188,
  0x9A79 332/169, 0x9A37 16/7, 0xA1E6 15/3.
- Panel: only the pocket-icon record IX 0xA17D plots into the panel (cols 25-30, panelix, frames
  1-2500); every other figure record stays in cols 0-22.
- Colour = attribute painting: per figure 0x91FE -> 0x9980 (paint, table 0x9985 -> 0x9D25..0x9E55;
  0xFF entries take (24090)) and 0x9962 -> 0x7E85. That painting IS the clash (wall lines in a
  figure's cells take its ink, plain.png frames).
- Scenery on the ULA: room outlines 0x9C61 (OR, from 0x9D08 / 0x9C5D / 0x9CC7), objects above,
  panel 0x7EB2 (attrs, x 200-247: chicken), play-area clear 0x8093.
- Cost: plotters 0x9F21 / 0x9EDC median 247 / 235 T per row call, ~10 % of frame time each;
  typical frames 18 or 34 calls, busiest 85-86 -> hook per FIGURE (the 0x9F4A.. entries), not per row.
- ISR: ROM IM 1; reads IY; 16 bytes below SP; never touches slots 1, 3-7. Lowest SP 0x5DD8.
- Free RAM (survey, whole recording): 0xD2EE-0xEA8F (6050 bytes), 0xB786-0xBA57, 0xB536-0xB6F1,
  0xBB60-0xBCCD, 0x5B00-0x5BFF, 0x5CB1-0x5DD7.
- Planned pattern (decision table): 1-bit shadow screen (Dizzy 1 row): converted XORs go to the
  shadow, ULA ^ shadow = original; non-XOR writers above fold their change into shadow / ULA; play-
  area clear empties both and hides every sprite; attribute painting of figure cells skipped
  (colour moves to the sprite). Design to be confirmed by the stage-1 answer.

## Decisions
Design approved by Dean 2026-10-26 (stage-1 question: "1 to 5 the defaults are ok"):
1. Every figure a sprite (player, monsters, items, thrown weapons, monster-appearance sparkle);
   the pocket icons in the panel (IX 0xA17D) stay on the ULA with the panel.
2. Scenery on the ULA: room outlines, doors (incl. open/close), furniture, scroll panel, chicken,
   score, time.
3. Depth: sprites in front of everything. Solid inside (below), not see-through.
4. Colours: each figure's own ink; the figure-cell attribute painting is skipped (walls keep the
   room colour); recolour later from the painted sheet.
5. Play-area clear (room change, game over, escape): hide every sprite there.
Effects: the player's death and the monster-appearance animation are sprites (Dean: "correct").
Outlines: yes, every sprite outlined, and the inside of the mask is NOT transparent: fill the
  area enclosed by the outline (Dean 2026-10-26).

## Build design (stage 2, 2026-10-26; written before the first quick run)
Facts found for it (stage 2 analysis, whole recording):
- Every figure plot is ONE whole image: the row loop 0x9E9B is entered only from two setups that
  each end `LD A,(DE) / LD (2408x),A`: main set 0x9F97 (graphic (24085) at x,y = (24086),(24087))
  and alt set 0x9FC1 (graphic IX+0 at IX+3, IX+4). Graphic = DE -> height byte h, then h rows of
  2 bytes, drawn UPWARD from line y (bottom row first); pixel x = L (shift x & 7; JR offset 232 =
  aligned). Entries: 0x9FCA erase IX + draw new (32,300 calls, from 0x8E8E), 0x9F4A IX only
  (1,228), 0x9F56 new only (357); 0x9F40 / 0x9F45 / 0x9F74 have no caller.
- XOR parity per image key (DE, x, y), reset at each play-area clear 0x8093 (127): closes exactly
  (0 left at the end); at most 9 images shown at once (frame 10452).
- The graphic pointer table 0xA4BE is indexed by id-1 for ids 1-255 (211 real entries; ids 240-255
  point into the ROM, the screen, the stack and variables: no game image). h = 0 draws nothing.
- CORRECTION (stage 2 part 2): the player's appear / death effect 0x8CD8 (IX 0xEA90) does NOT draw
  tall strips. It draws ONE ROW k of the figure per plot: table entry of id IX+7 -> G + 2k, the byte
  there (row k-1's second byte) poked to 1 = height, plot via 0x9F4A at y = base - k, both put back
  (0x8D03 / 0x8D0F). Death: the shown figure, then rows k = 17..0 XOR it away top-down; appear: rows
  0..17 bottom-up, then the next move XOR-erases the whole figure. The part-1 reading took the
  heights from the static bytes. Recording: 54 slices (appear, death, re-appear).
- Graphics change at run time only there (writes to 0xA4BE-0xEA8F: 0x8CEC-0x8D11 the effect, 0x8BB1
  -0x8C13 a pointer at 0xA626 + room tables, restored before any plot uses them); the verifier checks
  every plot's graphic bytes against the snapshot.
- The survey's "free RAM" spans 0xB536-, 0xB786-, 0xBB60-, 0xD2EE- hold graphics (the other two
  characters and more): untouched by this recording, NOT free. No game RAM is used by the build.
- Attribute readers (whole recording): 0x9782 (one cell 0x5AC1, frame colour cycle), 0x8C9F /
  0x8CAF (panel cells, FLASH toggle). Paint calls 0x920B (91FE -> 0x9980) never use a figure IX:
  that is the furniture painter (repaints every frame, 9D37 x146,660).
- FIGURE painter = 0xA01A (from 827B / 876C / 8784 / 8E91 / 92F2 / 9342, right after each plot):
  D = IX+5 (the figure's colour), E = (24090) (background); per move direction (handler table
  0xA064) it fills the figure's new cells with D (`LD (HL),D` at A07D A093 A0A6 A0BA A0D8 A113)
  and the vacated row / column with E. Writes over a shown figure: A07D x135,469, A093 x58,066,
  A0A6 x53,727, A0BA x31,114 ... (the cells the clash comes from).
- Game ROM reads: 0x0000-0x0052, 0x020A-0x0363, 0x1900-0x1A11, 0x38E0- (font etc.); 0x2000-0x38DF
  never touched -> alt ROM hooks there. Printer buffer 0x5B00-0x5BFF never touched.
- Op bytes rewritten at run time: 0x99D7 by 0x99CD, 0x9A36 by 0x9A0E, 0x9A78 by 0x9A54, 0x9ADD by
  0x9ACF, 0x9B88 by 0x9B61 (each `LD (op),A`, value from 0x9D19: 00 / B6 OR (HL) / AE XOR (HL)).

Design:
- Display: HARDWARE SPRITES, one composite per shown image (not Layer 2: one shared XOR layer
  cancels touching figures, Dizzy 1 hardware round 1; per-image sprites keep each figure solid).
- IMAGE GROUPS (part 2, after the slice fact above): an image is the group (G = the id's graphic in
  the snapshot, x, base line) with a 24-bit row mask. A plot of G toggles every row, a slice toggles
  row k (base = y + k); mask all = the stored image, none = pending, some = the image of those rows
  built by the hook (ink from the stored image, flood fill + outline as the store: `build`, ~2 per
  effect step). Per-image parity (DE, x, y) kept 18 slices + the figure as separate sprites while
  the original's screen was blank (death) - a ghost the per-image pixel check could not see.
  Image = (DE, h): 18 px wide with the outline -> 2 sprites across, ceil((rows+2)/16) down; rows
  above line 0 clipped (clip window = the 256x192 area, tiles wholly above it not shown).
- Patterns built at build time for all 255 ids (deduplicated by graphic address) from the
  snapshot's bytes (4-bit, 16x16; at most the bottom 192 rows, nothing above line 0 can show):
  ink = index 1 (colour = the sprite's palette offset = IX+5's ink + BRIGHT * 8), enclosed paper
  (4-connected flood from outside) and a 1-px outline (4-neighbours - left, right, up, down - of ink | interior; Dean 2026-10-26) = index 2
  black, rest index 0 transparent. Pattern store: Next pages, one tile row (2 patterns, 256 bytes)
  after another, an image never crosses a page; directory id -> (page, offset, tile rows).
- Pattern RAM in PAIRS: 64 pairs; sprite 2p / 2p+1 always shows 4-bit pattern 2p / 2p+1. A shown
  image owns one pair per visible tile row (free-pair bitmap); a draw uploads its tile rows (store
  page mapped at slot 7 for the copy, OTIR to port 0x5B at 28 MHz) and writes the sprite attributes
  (X = 31 + x + 16c, Y = 32 + y - h + 16r, i.e. the outline row above the top ink row).
- Colours: the figure painter's `LD (HL),D` writes become NOP (6 single-byte sites, no register
  effect): walls keep their colour; the E writes stay (as the original, they reset vacated cells).
  Attributes then differ from the original only in cells a figure painted; the verifier keeps the
  original's attributes alongside and checks every attribute READ sees the same byte.
- Sprite bookkeeping hooks at the two setup tails (sites 0x9F97 `1A3218`, 0x9FC1 `1A3219`, JP to
  alt ROM; the hook does LD A,(DE) / LD (2408x),A itself and jumps back): the plot's group toggled
  (above); a group not in the table takes the owner's pending entry or a free one (24 entries x 26
  bytes; at most 9 used in the recording). Erase marks the entry PENDING (still shown); a draw by the same owner (IX) reuses its
  sprites (no hide/show flicker across an interrupt; LEARNINGS 2.1d); a pending entry is hidden at
  the next setup by another owner or at the clear. x >= 192 (pocket icons, panel) = not converted.
- Pixels: 1-bit SHADOW screen (Next page at slot 3 while a hook runs: shadow address = screen
  address | 0x2000), so ULA ^ shadow == the original screen at every moment. Row hooks replace
  CALL 0x9EDC / CALL 0x9F21 at 0x9EA0 / 0x9EA9: same code, writes to the shadow (shift read from
  the self-modified JR at 40677 / 40746 at run time; E & 31 >= 24 -> the original blitter, ULA).
  Non-XOR writers keep the invariant (new ULA = op(ULA ^ sh, v) ^ sh): room-line OR 0x9C75,
  scenery-object drawers 0x99D7 / 0x9A36 / 0x9A78 / 0x9ADD / 0x9B88 (their op byte is rewritten by
  the game: site moved off it, op read at run time), text printer 0xA1E6. Play-area clear 0x8093:
  shadow zeroed, every sprite hidden, table emptied.
- Hooks: alt ROM image 1 (ROM read check: scan below), interrupts stay on (ROM IM 1 reads IY and
  touches slots 0, 2 only), 28 MHz inside each hook (the row hooks too: then cheaper than the
  original blitter). Pages during a setup hook: slot 3 = shadow page 26 (shadow, DIR 0x7800,
  entries 0x7C00, pair bitmap 0x7ED0), slot 7 = work page 28 (GADR id -> G at 0x0000, build grid
  0x0200, built patterns 0x0600 = tile rows 6-7), slot 6 = the store page while building. The
  object records 0xEA90.. are in slot 7: everything read through IX is read BEFORE the remap.
- Verify (PLAYBOOK 6, template dizzy1.verify): replay the patched machine; at each site run the
  original on ULA ^ shadow and the patched code, compare registers (CMP), memory outside the
  screen, ULA ^ shadow vs the original screen, the sprite set vs the parity model, each shown
  sprite's pixels vs the original plot of that image; interrupt safety; attribute reads see the
  original's value.

Files: asm/atic_atac_hooks.asm (2,118 bytes at 0x2000-0x2845 + 53-byte setup at 0xD000;
`python tools/asm2profile.py atic_atac`), docs/profiles/atic_atac.json (signature 0x9EDC blitter A),
nexclash/atic_atac.py (store, patch, start state, verify, unit tests, auto), the engines.py line,
docs/records/atic_atac.json.

## Results (stage 2, 2026-10-26)
    python nexclash.py auto Atic_Atac_1983_Ultimate_Play_The_Game_a.z80 --rzx AticAtac.rzx [--quick 2000]
- Build: start state = the .z80 run to JP 24576 (frame 2); 207 stored images, 388 tile rows (pages
  32-44); static check PASS; boot sim OK (nextboot + own banks: alt ROM, DIR, store, work page, setup).
- Verify, WHOLE recording (18,279 frames, 615 s): IDENTICAL, 0 failures. 65,698 plots of a stored
  graphic + 54 one-row slices, 66,312 sprite checks (entries vs the group model, pair bitmap, visible
  sprites, shadow vs the converted rows, every shown image's pixels and colour vs the original's
  plots), 47.3M sprite pixels; registers / memory / ULA ^ shadow / attributes / hook rules at every
  site; no unhooked read or write of a figure byte or a skipped attribute; max 9 entries.
- --quick 2000: PASSED (Verify IDENTICAL 59 s; Unit 1,473 cases + negative controls 3/3, 82 s).
- Unit cases: every stored image at 5 edge positions / colours (draw + erase), one-row slices of 24
  figures (every row, every shift), death (rows erased top-down) and appear (bottom-up, then the
  move) of 4 figures at 3 places, random row masks, the panel (x >= 192), a full table (26 images,
  24 shown), the clear with a full table, line / drawer (ops 00 / B6 / AE) / text over figure bits,
  text outside the pixel area. Negative controls (their own tables / code): store shifted one pixel,
  directory heights + 1, builder writing black as ink - all detected.
- Speed (T at 3.5 MHz, 28 MHz parts / 8, whole recording): hooks add ~7,000 T per frame on average
  (setups ~2.5k T each: the OTIR upload and the table scans; rows -62M T, cheaper than the original;
  text +5M T, the start screens). Whether the game has that much spare per frame: hardware.

## Hardware checklist (atic_atac_sprites.nex)
1. Boots to the game's start screens; text prints as the original; keys / joystick work.
2. Player appears row by row from the bottom (no extra copy left behind after the first move).
3. Figures solid with a black outline; no colour clash on walls when figures pass; colours = the
   figure's own ink.
4. Monsters' appearance sparkle, thrown weapons, items: sprites, no flicker when moving.
5. Death: the figure dissolves top-down and nothing is left where it stood; re-appears correctly.
6. Room change: no figure from the old room stays; doors open / close on the ULA as before.
7. Pocket icons in the panel unchanged (ULA); chicken, score, time as the original.
8. Speed: busy rooms (several monsters) at the original's pace.
9. The escape message and the end screen.

## Open
- Speed on hardware: setups cost ~2.5k T; if the game slows, skip the pattern upload when an entry
  shows the image it already holds (same pairs, same image), or keep the last uploaded image per pair.
- Colour sheets: no sheet capture for this engine yet (stage 3).
- Menus / message windows over the play area: asked 2026-10-26 (pause? the inventory?).
- Test cheat (immortality / no chicken drain): offered 2026-10-26.
- Game-over path (35893) not in the recording.

## Lesson candidates
- A .z80 at the loader does not mean the RZX is: an RZX carries its OWN start snapshot (rzxinfo
  "Start address"); the survey and every --rzx analysis start there. Stage 0 read the .z80's loader
  state as the recording's and planned a prerun that was not needed (loader.prerun then "finds"
  frame 0). Check `rzxinfo` in stage 0 before calling a recording loader-stage.
- A run-time screen-dependency check for an XOR engine is cheap with simrun hooks: shadow ^= each
  plotter delta, report non-plotter reads / writes where shadow != 0 (figdep, ~15 min for 18K
  frames). Candidate for a shared `scan --xor-owner ENTRY` option (BRIEFING C4).

- The survey's "Free RAM" list is memory the RECORDING never touched, not free memory: here 0xB536-,
  0xB786-, 0xBB60-, 0xD2EE- are graphics of the characters and figures the recording never drew
  (the graphic pointer table points into them). Check a span against the game's own tables (or a
  static reference scan) before putting anything there; the printer buffer / alt ROM need no such
  proof once the scan shows them untouched. Candidate: the survey line should say "untouched".
- An XOR plotter whose effect draws "graphics" from inside other data with heights up to 248 rows
  (Atic Atac's appear / death strips, ids past the real table) writes far above line 0, into ROM
  (discarded): a shadow address trick that offsets H would move those writes into RAM; check H per
  row (row hooks fall back to the original for H < 0x40).

- XOR parity per image key (graphic, x, y) breaks when a game composes an image from PARTS that
  XOR-cancel it (Atic Atac's death: 18 one-row slices over the shown figure; the screen ends blank,
  per-key parity shows 19 sprites). The per-image pixel check cannot see it (each sprite matches its
  own plot); only a global view does (union of sprites vs the screen). Group by what the parts
  belong to (the graphic + base line, a row mask) and check the group, not the part.
- A hook that remaps slot 6 / 7 hides the game RAM there from everything it reads afterwards, IX
  records included (Atic Atac: IX 0xEA90, colour read through IX+5 after slot 7 = work page: palette
  offset 0). Read every game byte first, then remap; a verifier memory model with the MMU slots
  catches it (it did: colours wrong in the 600-frame run).
- sjasmplus: `ld a,(EXPR)` is a memory READ even when EXPR is a constant expression - `ld a,(OB >>
  8)` loaded from 0x00E6 and the builder wrote a random page. Use an EQU (`OBH EQU 0xE6`) or no
  outer parentheses for immediates.
- Fork the patched and original runs on a memory model that maps pages BEFORE the overlay of this
  run's game writes: a hook reading a mapped page at an address the game wrote in the same run must
  see the page.

## Stage log
- 2026-10-26 stage 0 (intake): ~20 min wall, ~30 tool calls, 0 user rounds.
- 2026-10-26 stage 1 (design): ~1 h wall, ~60 tool calls, 2 user rounds (the design question + answer).
- 2026-10-26 stage 2 part 1 (build design + hooks asm): ~1.5 h wall, ~80 tool calls, 0 user rounds.
- 2026-10-26 stage 2 part 2 (engine module, store, verify, unit tests; slice effect found -> image
  groups + run-time builder; 3 hook bugs found by the verifier): ~3 h wall, ~110 tool calls, 1 resume.
