# Cauldron (Palace Software, 1985; 48K) - engine `cauldron` (colour map; 43c1ca49 works on the Next)

## Next session
Stage: 4 (hardware + colour round 3)    Branch: claude/cauldron (PR to main: process + Cauldron)
State: 43c1ca49 = 55ed40f8 + colour map, sheets, recolour; full verification IDENTICAL, stamped
  2026-10-27 ("Results"); sheets in specnext reference/cauldron/; works on the Next (Dean).
Inputs: specnext/reference/cauldron/ (cauldron.rzx: its embedded snapshot is the build input)
Start with: Dean's painted sheet: `python nexclash.py
  recolour Cauldron_1985_Palace_Software_a_sprites.nex PAINTED.png` (layout next to the PNG); send
  the _painted.nex + both sheets re-drawn with the map. Making it the default: COLOURS.md RECOLOUR.
Read: COLOURS.md, this file ("Colour map", "Open"), card patch.runtime-colour-map.

Reference: specnext reference/cauldron/. Status: stages 0-2 done (engine 2026-10-26); stage 2 analysis 2026-10-26
(technique-card pilot). Analysis scripts are scratch (not in the repo): a one-off screen-reader
probe (detect.gameplay-screen-readers has no shared command yet, BRIEFING C2 candidate).

## Inputs (2026-10-26)
- Cauldron_1985_Palace_Software_a.z80 (39,878 bytes, 48K), cauldron.rzx (89,595 frames, ~30 min,
  1 segment, no autosaves, no desync).
- **The RZX does not start from this .z80** (observed, 2026-10-26): its embedded Z80 snapshot has
  the same screen and entry (0x6018 `JP 0x63F8`) but 11,283 bytes of 0x6018-0xFFFF and 711 bytes
  of sysvars/BASIC differ: the compiled-BASIC body (0x6D9E-0x7Fxx at least) is laid out
  differently (e.g. `CALL 0x6275` sites at 29140/29149/29164 in the RZX's copy, 29191/29200/29215
  in the .z80). A different build or variant of the game. Everything the survey and the probes
  measured is the RZX's copy. Identical in both (checked at frame 2000): 0x6275 helper, 0x6357
  plotter, 0x61D8-0x61FF PEEK/POINT, 0xB29C-0xB380, 0xC9D8-0xC9F3, 0xCE74-0xCE90, 0xDED2-0xDF30.
  -> Q0 in the design question.

## Snapshot facts (PLAYBOOK 0b)
- 48K, IM 1, I = 0x3F, DI (an interrupt was just accepted: PC 0x0038, stacked return 0x613E is
  game code), SP 0x5FF6, border 0. RAMTOP 24599; game 0x6018-0xFFFF resident.
- ISR: ROM IM 1 only, 89,377 interrupts, 126 distinct handler instructions, all in ROM (observed,
  whole RZX). Reads IY (keep IY), needs >= 18 free stack bytes. MMU slots touched 0 and 2 only;
  1, 3-7 never. 0x63DB sets IM 2 (vector table 0xFEFF -> 25576) - never executed in this
  recording (unknown handler).
- Free RAM (local evidence only): 0x5B02-0x5BFF, 0x5D52-0x5FB9, 0x62DE-0x6347, 0xA306-0xA49B,
  0xBDA6-0xBDF5. Lowest SP 0x5FBA. Plain .nex: no proven-safe tail (converter default), boot OK.
- Main program is compiled BASIC (inferred from its runtime): 0x61D8 PEEK (`LD L,(HL)`), 0x61DB IN,
  0x61F1 POINT (ROM PIXEL-ADD + bit test), 0x6275 USR-style indirect call (`CALL 0x627B` ->
  `JP (HL)`), 0x627E RND, 0x6130 multiply, 25089 ATTR(y,x).

## Rendering model (PLAYBOOK 2)
Coverage gate: 2 unreached `CALL 0x6275` sites, both non-figure: 40167 (CLS + 0xC4AE: ROM
PR-STRING of a 162-char message, a text screen) and 31131 (USR (41337) = (41321)+142/166 =
57042/57066, the scrollers below, reached via other sites; (41321) = 56900 all recording). No new
recording needed for coverage.

Observations (basis / scope; scope = cauldron.rzx 89,596 frames unless stated):
| # | Routine | Observation | Basis |
|---|---|---|---|
| 1 | 0x6357 figure plotter (14 callers) | target ULA bitmap + attributes, direct (no back buffer) | observed (static + writers) |
| 2 | 0x6357 | composition XOR: all pixel writes XOR the old byte (0x63BE/0x63C2 `XOR D/E` shifted pair, 0x63CD `XOR (HL)` aligned) | observed (static) |
| 3 | 0x6357 | attributes: per cell, overwrite when the old attr equals ATTR-T (23693) or the graphic's; type 2 via ROM PO-ATTR 0x0BE4 | observed (static); exact rule inferred |
| 4 | 0x6357 | lifecycle: paired draw/erase - callers in matched pairs 38810/39537 (19,865/19,587), 27799/31236 (12,448/12,407), 35390/35210 (9,390/9,389), 39708/39824 (380/375), 28441/28585 (234/234); unpaired 31115 (276), 40860/40577/40483 (20/14/10) | inferred (counts) |
| 5 | 0x6357 | tracked unit: one call = one whole image from a descriptor at HL (graphic ptr, x, y, rows, width per row, drawn upward) | inferred (static); partial draws unknown |
| 6 | 0x6357 | object identity: descriptor pointer HL per caller | observed (static) |
| 7 | 0x6357 | cost: median 23,090 T, max 55,615 T per call (~1/3 frame); 84,629 calls in 59,155 frames | observed |
| 8 | 0x6357 | execution: main loop only (ISR is ROM, calls no game code) | observed |
| 9 | gameplay readers | POINT reads bytes holding figure bits: 114 of 530 POINT reads (0x6B87/0x6BA8 = POINT(px-1, py-18) around the position in 41297/41355; 0x9DE1, 0x9E3F) | observed at byte level; bit level inferred |
| 10 | gameplay readers | ATTR reads cells the plotter painted: 3,794 of 37,416 attr PEEKs (0x9077-0x90FC: ATTR of the 4 neighbours of (41537,41539) -> 41527...; 0x6B39/0x6B56: ATTR(21,28)/ATTR(21,4) = 65) | observed (painted-cell tracking) |
| 11 | other writers on figure bits | ROM PO-CHAR 0x0BBC 15,777; tile writer 0xB378 1,204; ROM CLS 0x0E59 6; clear 0xB2A6 1. On figure-painted attrs: 0xC9F0 47,955 (bottom-third attr restore), 0xCE7F 16,061 (6x5 attr box at 0x58E6), ROM 0x0E80 24 | observed |
| 12 | 0x6275 USR helper (17 sites) | not a plotter: routes to overwrite writers - 0xDED2/0xDEEA byte-step scroll of the bottom third (0x5000, 64 rows) + 0xDF04 its attributes; 0xB366 8x8 tiles (font at (45970)); 0xB2A0 clear 0x4800-0x57FF + attrs; 0xC9DB/0xC9E7 save/restore bottom-third attrs (51700); 0xCE74 attr box; 0xC4AE text screens. 4 caller groups draw nothing (logic) | observed |
| 13 | text | ROM printing (0x0B24 via PRINT-OUT 0x162C): HUD and messages; ROM CLS 0x0E44 | observed |
| 4b | 0x6357 figure kinds (preview --plot 0x6357, frames 1-44,800) | paired movers over the play area: 0x6C9A/0x7A07, 0x898D/0x8A41, 0x979D/0x9A74, 0x6F1C/0x6FAC; a fixed 24x24 image at x 96-119, y 107-130 (0x9B1F/0x9B93); unpaired bottom-left x 24-95, y 144-175 (0x798E); a plot into the HUD's top-right scroll x 216-247, y 0-23 (0x9E84, the collected-item icon); 0x9F9F (5 calls) | observed; which figure is which: from the sheet, not settled |
| 14 | hazards | self-modification at sites: not checked (no LD (nn) scan yet); IM 2 path at 0x63DB not reached | unknown |

## Patch plan (STANDARD 4-5; cards opened: 3)
Cards opened: detect.gameplay-screen-readers (applied: POINT reads figure bytes, obs. 9; ATTR reads
painted cells, obs. 10), patch.xor-overlay-keep-ula (chosen: XOR, figures in front Q2; plots ~1/3
frame -> patch.display-atomic-switch), patch.xor-shadow (REJECTED: POINT readers need the ULA
pixels; revisit only with a bit-level POINT check). From index.json alone: scratch-redirect
(rejected, no back buffer), isr-deferral (rejected, ISR is ROM only), pattern-cache (not needed),
tracked-unit (obs. 5). Overwrite scenery / tile / scroll / clear writers and ROM text: no card;
they stay on the ULA and are the "other writers" the overlay follows. Attribute painting with
readers: no card for a virtual attribute read (decision table 4 nearest; lesson candidate).
Full text in git history.

## Design question (sent 2026-10-26)
Q0 start snapshot, Q1 which figures, Q2 depth, Q3 attribute painting, Q4 colours, Q5 menus / text
screens; the answers (and the options as asked) are in "Decisions"; full text in git history.

## Decisions
User answers 2026-10-26 (stage 1, round 1):
- Q0: build from the RZX's embedded snapshot (the copy the recording proves).
- Q1: every 0x6357 caller a sprite, incl. the cauldron-spot image and the HUD item icon (default 1).
- Q2: figures in front - overlay (patch.xor-overlay-keep-ula), XOR kept on the ULA (default 3).
- Q3: keep the figure-cell attribute painting (3a): clash halo stays, ATTR readers untouched.
- Q4: figure colour = its cell ink until painted (default 4).
- Q5: Layer 2 + sprites off on the text screens (0xC4AE family) and the control menu (default 5);
  always-ask items (solid vs see-through, outline) left at the defaults.
User answer 2026-10-26 (stage 2, round 2):
- Q6: a figure that any other writer touches (PO-CHAR scenery, tile 0xB378, the bottom-third
  scrolls, the clears, CLS) loses its sprite at that moment; the ULA keeps whatever the original
  left (moved, half-wiped or residue), exactly as the original shows it. No scrolling sprites.

User report 2026-10-27 (hardware round 1, screenshots from CSpect):
- Sprite build d4302eef: hangs at the control menu on the Next, keys do not respond, after a few
  seconds; runs in CSpect but very slow, with graphical issues.
- Q7 (Dean): every sprite needs a border - left / right / up / down neighbour pixels only. Colour
  not answered: black proposed (paintable on the sheet).
- Q8 (Dean): the scenery must not clash when a figure passes over it (reverses Q3 = 3a): remove
  the figure-cell attribute painting from the ULA; the game's attribute readers get the original
  values from a shadow. Go-ahead for both: Dean 2026-10-27 (after the hardware round); outline
  black by default (proposed, not objected; paintable on the sheet).

## Stage 2 analysis (2026-10-26; scratch probes)
- Build input: RZX block 0x30 (zlib) = a .z80, MD5 2f0ef98e...; 11,994 RAM bytes differ from the .z80.
- 0x6357: descriptor at HL = gfx lo/hi, x, y (row 175 - y), rows, width, attr type, value; per row
  PIXEL-ADD, cells painted (2: PO-ATTR; 0 / 1 via ATTR-P), then XOR. 0x63DB follows the RET.
- 93 graphics, never written, up to 32 x 32. XOR parity is not "on screen" (clears, scrolls, text
  wipe figures: frames 2602-2638) -> Q6. Max 17 live. Details: git history.

## Build design (stage 2 part 2, 2026-10-26; round 2 below changes sprites and attributes)
Overlay: the game draws the ULA pixels as the original; hooks put 4-bit sprites on every live image.
Key = (graphic, x, y, rows, width), a plot toggles it; other writers taint (sprite hidden), a clear
holding it whole forgets it; table (page 26 at slot 6, 128 entries) full -> overflow until a full
clear. Colour = first cell ink after the first paint (black -> 8). Sites: RAM 0x6357 (hook runs the
body: draw shown before, erase hidden after), 0xB2A0, 0xB366, 0xDED2 / 0xDEEA; ROM PR-ALL 0x0B9B,
CL-LINE 0x0E44, CL-SCROLL 0x0E00 (JPs in the build's own alt ROM image). Hooks in alt ROM 0x386E-,
28 MHz, interrupts as the game has them. Details: git history.

## Build design round 2 (2026-10-27: Q7 outline, Q8 no clash)
- Q8 attribute shadow: page 27 at slot 4 (0x8000-, mapped only in hooks; the ROM IM 1 handler
  never touches slot 4) holds the original's attribute file (SH = attr + 0x2800). The plotter body
  runs as a copy in page 27 (OR 0x80 for OR 0x58; type 2 PO-ATTR on the shadow), so its painting
  never reaches the ULA. Every other attribute access (whole-RZX `scan --writers` on 0x5800-0x5AFF:
  11 writers, 10 readers) is a hook: PEEK / ATTR runtime 0x61D8 (attrs from the shadow), PO-ATTR
  0x0BE4 (on the ULA from its own value, then on the shadow), CL-LINE (rows into the shadow after it;
  B 0 / > 24: ULA = shadow first), CL-SCROLL (ULA = shadow first, all back after), bottom-third save
  0xC9DB (buffer = the shadow; (ULA, shadow) pairs kept) / restore 0xC9E7 (shadow = buffer; ULA = the
  saved ULA colour where the buffer still holds that save), box 0xCE74, room fill 0xB2AC, room cell
  write 0xB33E / read 0xB361, attribute scrolls 0xDF04 / 0xDF17 (each run on ULA and shadow,
  registers and flags as the original's: the shadow run last). The game's memory equals the
  original's everywhere but the ULA attribute file.
- Q7 outline: patterns built at the draw in page 27: ink bits on a canvas at (+1, +1), outline =
  4-neighbours of ink not ink, 2 pixels per byte through a 16-entry table (ink nibble / 8 / 0). A
  slot = 9 sprites + 9 patterns (3 x 3 grid at (x - 1, y0 - 1), UNC x UNR used); 14 slots.
- Verify adds: events spanning a hooked routine to its caller's return (plot, PO-ATTR, CL-LINE,
  CL-SCROLL; nested sites skipped), the ULA attribute model (Model.attrs) and the shadow vs the
  original after every event, and outside the hooked routines any attribute write, or a read of a
  cell whose ULA value differs, fails.

## Colour map (stage 4, 2026-10-27; card patch.runtime-colour-map)
- Keys, one per canvas pixel (the image + its 1-pixel outline ring, (8 w + 2) x (rows + 2)): inside
  the graphic's bytes the graphics byte (hex address, check = its value; shared by every image that
  draws it), the ring per image (`G:WxR:line,col`). Paint: a colour (ink, outline or paper ->
  opaque) or transparent (any pixel). docs/profiles/cauldron_colours.json; none = today's colours.
- Build (`colour_tables`): per painted image a transparent mask (5 bytes a canvas line) + a colour
  stream (2 pixels a byte, `stream_stride(w)` = 4 x canvas bytes read a line) in pages 28-35 (banks
  14-17), index at page 28 (count + 7-byte entries). `upload` -> `ovfind` after the outline: masked
  pixels out of both canvases (the outline stays the real ink's), page at slot 6 while the patterns
  are written: byte = (TT AND KEEP[v]) OR v (KEEP at page 27 0x0800). Unpainted: the old path.
- 93 images (profile `colour_images`, whole-RZX `capture` in 70 s); worst case all painted ~48K.
  The game never reads pages 28-35: `recolour` splices banks 14-17 only (refuses another build:
  graphics MD5 `colour_inputs`, sites, bank 12, pages 26 / 27).
- Sheets (`python -m nexclash.cauldron sheet RZX`): one figure per image in its most frequent ink
  (92; D710 3 x 24 draws nothing), the whole canvas grey = paintable; ring keys are per image, so
  the painting sheet shows every image. Read-back: `colours PNG` or `nexclash.py recolour`.

Techniques: `detect.gameplay-screen-readers`, `patch.xor-overlay-keep-ula`, `patch.display-atomic-switch`, `patch.attribute-shadow` (recipe and results: docs/records/cauldron.json)

## Results
- Stage 2 (2026-10-26, d4302eef): quick 2000 + 9000 IDENTICAL, unit 43 + 9 PASS.
- Round 2 (2026-10-27): sprites 55ed40f88d103cfd2fc9474199fe7f9d (plain unchanged b5b211f1), boot OK
  also with a foreign ROM3. quick 9000: 6,448 plots (3,228 draw / 3,216 erase / 4 no sprite), PR-ALL
  9,594, tile 795, scrolls 256 / 512, clear 3, CL-LINE 6; 9,847,336 sprite pixels (ink + outline),
  1,662,970 table bytes, 6,448 transient checks, 185,079 plot screen bytes, 74.2M interrupt-safety
  points -> IDENTICAL; colour rule 3,228 / 3,228. Hook cost mean 5,701 T / frame (was 2,765: outline
  upload, double PO-ATTR), max 45,474 T. Unit 75 cases + 17 negative controls (8 new: plotter paints
  the ULA, no outline, PEEK reads the ULA, PO-ATTR twice on the ULA, restore ignores the save, scroll /
  box / CL-LINE skip the shadow) PASS. CL-LINE B 0 / 25 cases dropped: the original never returns.
- Full verification (stamped 2026-10-27, 55ed40f8): 89,596 frames IDENTICAL - 84,638 plots (42,188
  draw / 41,855 erase / 595 no sprite), PR-ALL 53,334, tile 28,399, scrolls 1,760 / 3,552, clear 110,
  CL-LINE 64; 188.6M sprite pixels, 32.4M table bytes, 2.86M plot screen bytes, 936M interrupt-safety
  points, max 10 live keys / 33 entries; attributes: PEEK 103,930, PO-ATTR 53,334, save 182, restore
  6,051, box 15,236, room fill 110, room cell 14,319 / 9,406, scrolls 1,760 / 3,552, 583M bytes
  compared, no unhooked access. Colour rule 42,188 / 42,188. Hook cost mean 7,611 T, max 130,678 T
  (one frame, ~2 frames' worth: a room draw + text).

- Colour map (2026-10-27, 43c1ca49; plain unchanged b5b211f1): full verification stamped, 89,596
  frames IDENTICAL with the same counters as round 2 (952M interrupt-safety points), unit 87 cases
  (12 colour: every image geometry, shifts, screen edges, wrong check bytes) + 20 negative controls
  (+ map left out, transparent mask ignored, check byte not checked) PASS; recolour = full build
  both ways (selftest guard). Hook cost mean 7,801 T (was 7,611: the index search). Synthetic
  painting (1,593 entries, 30 images): read back, recolour = full build with the map (50572718),
  quick 2000 IDENTICAL; a tampered page 27 is refused.

## Hardware rounds
Round 1 (2026-10-27): d4302eef hung at the menu (keys dead). 5830cbbd (fix below) boots and runs at
full speed on the Next (Dean 2026-10-27), which confirms the cause: the game reads keys through ROM KEY-SCAN 0x028E / K-TEST 0x031E (its INKEY$
runtime at 0x61C2) and prints / clears / plots through ROM too. The Next fills the alt ROM from
NextZXOS's ROM3 (not Sinclair's), then the build wrote only 0x386E-0x3BB3 (hooks, over NextZXOS
data at 0x3B00-) and the 3 JPs below 0x2000; the verifier ran Sinclair's ROM (BRIEFING C2 #5).
Fix 5830cbbd: the stub writes the WHOLE 16K image from the build (patch.altrom_low = page 25 with
0x0000-0x1FFF + JPs; altrom = 0x2000-0x4000 from page 24); the image the game reads is the one
verified, byte for byte. Check: cauldron.rom3_independent boots with a ROM3 that differs in every
byte (negative control: the old partial image fails it, 15,546 bytes). Shared code (additive,
default off): z80tonex.altrom_fill `low` (replaces altrom0), nextboot boot / check `sysrom=`;
`selftest --canary` PASSED. quick 2000: same counters as stage 2, IDENTICAL; unit 43 + 9 PASS.

Round 2 (2026-10-27): 55ed40f8 (outline + no clash) works on the Next (Dean 2026-10-27).

Round 3 (2026-10-27): 43c1ca49 works on the Next (Dean 2026-10-27); no painting reported yet. Checklist: boots, menu keys work, full speed, looks
exactly as 55ed40f8 (no map); then a test painting through recolour: painted colours shown,
unpainted images unchanged, transparent pixels show the scenery (try CSpect first: +4 banks).

## Open
- CSpect "very slow" with d4302eef: unexplained
  (hook cost measured mean 2,765 T / frame); ask whether the plain .nex is slow there too.
- CL-SCROLL (never reached) shows the original's clash colours until the cells are written again.
- Hook cost doubled (outline upload): speed on hardware to watch.
- Colour map: the painting path is proven in software (unit cases, synthetic painting quick run);
  no painting on hardware yet. Images drawn in several inks (65 of 93: the cell-ink rule) show one
  ink on the sheet; a painted pixel is that colour in every room.
- IM 2 path (0x63DB, never reached): with I = 0xFE an interrupt inside a hook that maps page 26 at
  slot 6 runs the BASIC handler at 25576 with page 26 there; unit-test or hook 0x63DB if a recording
  ever reaches it.
- ROM PLOT / DRAW (PLOT-SUB 0x22E5) and other ROM screen writers: never reached; the verifier fails
  any unhooked write into a live image's rectangle, so a recording that reaches one shows it.
- Bit-level check of the POINT readers (obs. 9) if a shadow design is ever wanted.

## Lessons
- [card patch.attribute-shadow §Use] Clash-free figures when logic reads painted cells: original
  attributes in a shadow page, plotter paints it, every attribute reader / writer hooked; verify
  that no code outside the hooks reads a differing cell (Q8; observed, quick 9,000 + hardware).
- [doc docs/ENGINE_CONTRACT.md §Verify loop] A hook that runs the routine to the caller's return
  nests the sites inside it: the replay skips them until the span ends (PO-ATTR in the plot body).
- [doc LEARNINGS 1.3] [tool nextboot.check] [deferred C2 #5: reconsider when the maintainers can
  re-verify every altrom game with the whole image as default] ROM code run from an alt ROM whose
  rest is the system ROM3 is NextZXOS's on hardware: the menu hung, keys dead (observed, round 1).
- [doc docs/ENGINE_CONTRACT.md §The patch object] ROM routines below 0x2000 (PR-ALL, CL-LINE,
  CL-SCROLL, PO-ATTR) hooked by JPs in the build's own image; scan the ROM for jumps into the
  replaced bytes first (PO-SCR CALLs 0x0E00 inside CL-SCROLL).
- [doc docs/ENGINE_CONTRACT.md §Verify loop] An entry hook can CALL the routine's body when no
  exit JP fits (0x63DB starts right after the RET): show at entry, hide after the body.
- [card patch.xor-overlay-keep-ula §Recognise] XOR overlay without an object table: key =
  (graphic, x, y, rows, width), a plot toggles it, other writers taint it.
- [card patch.xor-overlay-keep-ula §Failure lookup] XOR parity is not "on screen": clears,
  scrolls and text wipe or move figures without an erase (frames 2602-2638).
- [backlog C2 #42] `inspect` "loader snapshot" WARNING when PC is in ROM only because of an IM 1
  interrupt (stacked return = game code).
- [backlog C2 #41] The RZX's embedded snapshot was a different build than the delivered .z80
  (11,283 bytes, code shifted); the survey should compare the two.
- [card detect.gameplay-screen-readers §Probe and stop] Compiled BASIC reads the screen through
  runtime PEEK / POINT / ATTR routines: find them, class reads by return address; the card's
  "no shared command" for listing readers was wrong (`scan --writers` lists readers): corrected.
- [probe tools/probes/rzx_census.py] Counts and first frame of given PCs over a whole recording
  with the C simulator (~4 min for 90K frames vs ~1 h in Python): which quick run reaches a hook.
- [local: the original itself never returns from CL-LINE with B 0 or > 24 (it clears over the
  stack), so those unit cases were dropped; no other game known to call CL-LINE that way]
- [deferred Open: reconsider when a hardware round reports a slowdown] Hook cost doubled with the
  outline upload (mean 5,701 T / frame); the upload could build only the grid cells in use.
- [doc docs/LEARNING.md §The learning loop] Lessons left as candidates, scratch scripts and a
  stale branch (main had new cards) were the gap; the loop and learncheck now enforce it.

- [card patch.runtime-colour-map §Use / do not use] Patterns built at run time take a colour map as
  per-image override tables (mask + colour stream) in pages the game never reads, applied at the
  upload; recolour splices only those banks (observed: 12 unit cases, synthetic painting quick 2000).
- [doc docs/COLOURS.md §Colour sheets and recolour] An outline ring lies outside the graphic's bytes:
  per-image ring keys make it paintable without widening the graphic (observed, Cauldron sheets).
- [backlog C2 #43] coloursheet.write crashes on a figure with no opaque pixel (image D710).
- [local: the verifier wired NEXTREG by hand; it now uses z80n.install as CLAUDE.md says (MUL D,E and
  ADD HL,A in the upload needed it); the rule already exists, the round-1 engine predated it]
- [doc docs/COLOURS.md §Colour sheets and recolour] A whole-RZX sheet capture through rzx.trace takes
  ~70 s for 90K frames (the census probe's method; COLOURS.md already names rzx.trace).

## Technique use
- patch.xor-overlay-keep-ula: helped (the design; lacked the other-writers failure row: corrected)
- detect.gameplay-screen-readers: corrected: listing readers has a shared command; compiled BASIC method added
- patch.xor-shadow: no help: rejected (POINT reads figure pixels), as the card predicted
- patch.display-atomic-switch: used (draw shown at entry, erase hidden after the body)
- patch.attribute-shadow: used (written from this game)
- tools/probes/rzx_census.py: helped (first frame of each attribute hook, plot geometries)
- patch.runtime-colour-map: used (written from this game; candidate)
- patch.xor-overlay-keep-ula: helped (its canvas-at-the-draw upload is where the map applies)

## Stage log
- 2026-10-27 stage 4 colour round (capture, colour tables + upload override, sheets, recolour, 12 unit cases + 3 negatives, card patch.runtime-colour-map, full verify stamped): ~75 tool calls, 2 user rounds (merge questions).
- 2026-10-27 stage 3 for round 2 (full verify stamped) + learning loop (docs/LEARNING.md, learncheck, probes, schema-4 cards; Cauldron migrated; main merged at the stage boundary, knowledge revision 639d585): ~40 tool calls, 2 user rounds.
- 2026-10-27 round 2 (Q7 outline + Q8 attribute shadow: 12 new sites, page 27, verify spans + attribute model, 32 new unit cases, 8 negatives; quick 9000 PASS): ~70 tool calls, 1 user round.
- 2026-10-27 hardware round 1 (menu hang -> whole alt ROM from the build; outline + clash requests recorded): ~45 tool calls, 3 user rounds.
- 2026-10-26 stage 0+1 (survey, patch plan, design question; pilot): see Pilot log.
- 2026-10-26 stage 1 answers: RZX snapshot, all figures sprites, overlay, keep attr painting (3a), defaults 4/5.
- 2026-10-26 stage 2 part 1 (analysis: snapshot extract, plotter decode, 3 whole-RZX probes, Q6): ~85 tool calls, ~1h20, 2 user rounds.
- 2026-10-26 stage 2 part 2 (engine: module, asm, profile, verify, 43 unit cases + 9 negatives, quick 2000 + 9000 PASS, record; shared altrom0 + canary): ~100 tool calls, 0 user rounds. Whole engine modules read: none (fireman template functions only).

## Pilot log
Technique-card pilot, stage 0 + 1, 2026-10-26: ~85 tool calls, ~78 min to the design question
(~58 min the survey); 3 cards opened, 5 judged from index.json. Full log in git history.
