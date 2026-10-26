# Cauldron (Palace Software, 1985; 48K) - engine `cauldron` (hardware round 1: menu hang fix sent)

## Next session
Stage: 2 again (Dean's hardware round 1, 2026-10-27), then 3    Branch: claude/cauldron
State: d4302eef hung at the menu on a Next (keys dead); 5830cbbd (whole alt ROM from the build)
  sent for a hardware test - quick 2000 IDENTICAL, unit PASS, boot OK with a foreign ROM3.
Inputs: specnext/reference/cauldron/ (cauldron.rzx: its embedded snapshot is the build input)
Start with: Dean's result for 5830cbbd ("Hardware rounds"). Then the two engine changes he asked
  for ("Decisions", round 3): (1) outline: every sprite opaque black on the 4-neighbour pixels of its
  ink (Dizzy 1 fill/outline model; images up to 32 px wide need a 3rd sprite column / row when the
  outline grows past 32: 31115 is 32 x 32); (2) no figure attribute painting on the ULA (the clash
  in Dean's screenshot: witch over the cottage roof turns it cyan) - plotter body paints a shadow
  attribute map in a Next page, the game's ATTR / PEEK reads of painted cells (obs. 10: 0x9077-
  0x90FC, 0x6B39 / 0x6B56, and the plotter's own old-attr tests) read the shadow; every other attr
  writer (PO-ATTR via PR-ALL, 0xC9F0 restore, 0xCE7F box, CLS) keeps the shadow equal. Then quick
  2000 + 9000, colour map + sheets + recolour (paint_clear for the outline), full verify --stamp.
Read: PLAYBOOK 5-7, this file ("Decisions", "Hardware rounds", "Build design", "Open"),
  docs/COLOURS.md, dizzy1.py fill_mask / part_from_writes (outline), docs/techniques/index.json
  (virtual attribute read: no card yet).
Open: see "Open"; CSpect "very slow" with d4302eef not explained yet (ask: plain .nex speed too?).

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
- `inspect` WARNING "loader snapshot" is a false positive here: the BASIC loader (tape load to
  0x6018 then `JP 0x6018`) is still in memory and PC is in ROM only because of the interrupt.
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
  values from a shadow (design stated to Dean 2026-10-27; his explicit go-ahead not yet given).

## Stage 2 analysis (2026-10-26; scratch probes, not in the repo)
- Build input: the RZX's embedded snapshot = RZX block 0x30, flags 2 (zlib), a .z80 (39,419
  bytes, MD5 2f0ef98e5c59552663b15d5eb1175236); 11,994 bytes of RAM differ from the delivered .z80
  (= stage 0's 11,283 + 711). Plain .nex of it: converts, converter default tail (no proven-safe
  tail, as stage 0). `inspect` gives the same false "loader snapshot" WARNING (PC 0x0039, SP 0x5FDA).
- 0x6357 (RZX copy, 25431-25562): descriptor at HL = gfx lo/hi, x, y (BASIC: screen row 175 - y
  first, then down), rows, width (bytes), attr type, attr value. Per pixel row: ROM PIXEL-ADD
  (0x22AA), then the row's cells painted (type 2: ROM PO-ATTR; 0: old = ATTR-T -> value; 1: old =
  value -> ATTR-T), then width graphic bytes XORed (shifted: 2 bytes each). Ends RET 25562; 25563
  is the IM 2 setup entry, so the exit cannot take a JP: an entry hook must CALL the body (25434).
  No stores into the routine (no self-modification). Entry bytes 5E 23 56.
- 14 call sites (list in "Rendering model" obs. 4), all `CALL 0x6357` with HL = the descriptor
  the compiled BASIC just POKEd. One entry hook covers every figure.
- Whole RZX (84,638 plots): 93 graphics, never written (shapes can be precomputed); images up to
  32 rows x 4 bytes (31115: 32 x 32 px; others <= 24 x 24) -> up to 3 x 2 16-px sprites when shifted.
  Types: 1 33,915, 2 31,808, 0 18,915.
- XOR parity alone is wrong: ROM CLS (0x0D6B) and the clear 0xB2A0 (rows 64-191) wipe drawn
  figures without an erase plot (parity model reaches 243 "live"); with clears modelled, max 5 live
  in frames 1-3000. The clears must reset the sprite set (card phase "clear").
- **The bottom-third scroll (0xDED2 left / 0xDEEA right, screen rows 128-191, one byte per call)
  carries plotted images with it**: ground decorations (e.g. gfx 51594 at x 8, rows 152-175, drawn
  by the 27799/31236 pair) stay drawn while the landscape scrolls under them, never re-plotted at
  the new place (frames 2684-2702, scroll.png). A sprite there would not move. -> design question.
- Whole RZX with clears modelled: max 17 live images (frame 41,972); 27 images straddle row 64
  when 0xB2A0 clears (top part survives on the ULA); scrolls with a live image in the band: 1,568
  (callers 27799/31236 only).
- **Other writers break XOR parity too** (seq probe, frames 2598-2645): the witch drawn at (8, 23)
  at 2602 is overwritten between 2604 and 2624 by a writer that is neither a plot nor a scroll
  (ROM PO-CHAR scenery printing likely, obs. 11); the game's next XOR draw (2624) lands on clean
  ground and its erase (2638) puts the image back as residue. So "live" must end when ANY other
  writer (PO-CHAR, tile 0xB378, scrolls, clears, CLS) touches the image's rectangle, not only
  at a matching plot. Max 17 live is therefore an upper bound.

## Build design (stage 2 part 2, 2026-10-26)
Engine `cauldron` (nexclash/cauldron.py, asm/cauldron_hooks.asm, docs/profiles/cauldron.json). Overlay:
the game still draws the ULA exactly as the original; hooks put 4-bit sprites on every live image.
Facts behind it (whole-RZX probe, scratch): 84,638 plots, descriptors only at 0x60B7-0x60EF, 93
graphics at 0xA5D2-0xEB84 (one geometry each: rows 8/16/24/32 x width 2/3/4), types 0/1/2; PR-ALL
53,334 (3,753 with OVER 1), tile 0xB366 28,399 (always char-aligned), scrolls 1,760 left / 3,552
right, clear 0xB2A0 110, CL-LINE 64 (B = 24 x 32 = CLS, B = 2 x 32), CL-SCROLL 0, IM 2 set-up 0.
- Key = (graphic, x, y, rows, width): one XOR plot toggles it (the same key's next plot erases).
  States (table in Next page 26 at slot 6, 128 entries): none (absent), live (sprite slot 0-27, or
  "no sprite"), tainted. Plot: none -> live, live -> none, tainted -> tainted. Touch by another
  writer (rectangle in rows x byte columns): a CLEAR whose rectangle holds the whole key -> none;
  any other touch of a live / tainted key -> tainted (its sprite hidden). Tainted keys never get a
  sprite again until a clear (Q6 + the Open "dropped-key replot rule": residue stays ULA-only).
  Model over the probe: max 10 live, max 33 entries; 44 live keys tainted, 583 plots of tainted keys.
- Overflow: table full -> new keys not recorded (no sprites; the recorded ones go on as before)
  until a clear of the whole screen (CL-LINE 24 = CLS). A plot whose geometry the plotter cannot
  draw (y > 175, rows 0, width 0, y + 1 < rows: PIXEL-ADD stops it part way, or width 0 XORs 256
  bytes a line) -> every entry tainted + overflow. A plot reaching past column 31 (the ULA row wraps;
  12 plots in the RZX) -> live with no sprite, rectangle = the whole screen; wider than 4 bytes or
  taller than 32 rows (never seen) -> live with no sprite.
- Sprites: slot s = sprites 4s..4s+3 (2 x 2 of 16 x 16, the unshifted image at pixel x), 4-bit
  patterns 4s..4s+3 uploaded at the draw (512 bytes from the game's graphic, converted at run time,
  so no static graphic list); colour = ink of the image's first cell after the plotter's first
  paint of it (type 0: v if old = ATTR-T; 2: PO-ATTR(old); other: ATTR-T if old = v; black -> 8).
- Sites (original bytes checked): RAM 0x6357 5E 23 56 -> JP e_plot (the hook does the 3
  instructions, CALLs the body 0x635A, RET 0x63DA comes back to it; draw: sprite shown BEFORE the
  body; erase: hidden AFTER it); 0xB2A0 21 00 48 clear rows 64-191; 0xB366 6F 26 00 tile cell at
  (45972); 0xDED2 21 00 50 / 0xDEEA 21 FF 57 scrolls (taint rows 128-191, cols 0-30 / 1-31). ROM
  (alt ROM, slot 0 bytes via patch.altrom0, a new optional z80tonex / nextboot field): 0x0B9B 3A 91
  5C PR-ALL (HL = the cell; screen only; taint; not a cell's top line -> the whole screen), 0x0E44
  C5 CD 9B CL-LINE (B lines from the bottom: clear; B 0 or > 24 -> taint all), 0x0E00 CD 9B 0E
  CL-SCROLL (taint all; ROM PO-SCR calls 0x0E00 directly, 0x0DFE falls into it; never reached in
  the RZX: unit test). ROM scan: no other jump into the replaced bytes.
- Hooks: alt ROM 0x386E-0x3CFF; page 26 mapped at slot 6 only while the tables are used (no game
  read then; descriptor copied first through the stack); interrupts left as the game has them (the
  ROM IM 1 handler touches slots 0 and 2 only; IY, I, stack room checked); 28 MHz inside hooks,
  3.5 MHz for the original body. Printer buffer put back (the game reads 0x5B00 / 0x5B01).
- Verify: at every site original vs patched to the return / site + 3 (registers, memory outside dead
  stack, interrupt safety); sprite layer = model after every event and at the body start of a plot
  (draw: new image already up; erase: old still up); each plot's screen change = its key's image;
  any screen write by a non-plot PC into a live key's rectangle = failure (proves the touch hooks
  cover every writer); interiors never jumped into.
- Shared code (additive, default off): z80tonex.altrom_fill / build_stub + nextboot.check take
  `patch.altrom0` (ROM bytes below 0x2000); ENGINE_CONTRACT patch object. `selftest --canary` PASSED.
- Not in this part: colour map, sheets, recolour (Open).
Techniques: `detect.gameplay-screen-readers`, `patch.xor-overlay-keep-ula`, `patch.display-atomic-switch`

## Results (stage 2, 2026-10-26)
Build from the RZX snapshot: plain `Cauldron_1985_Palace_Software_a.nex` b5b211f1fc6103ec0d42711dcc29cd0d,
sprites `..._sprites.nex` d4302eeff4bec044f61cc028fda8c3d4, both boot OK (nextboot.check, tail 0x5E00).
- `auto --quick 2000`: 1,029 plots (516 draw / 513 erase), PR-ALL 4,359, scroll right 160, CL-LINE 4;
  256,742 sprite pixels, 1,029 transient checks, 32,571 plot screen bytes -> IDENTICAL; unit PASS.
- `auto --quick 9000`: 6,448 plots (3,228 draw / 3,216 erase / 4 no sprite), PR-ALL 9,594, tile 795,
  scrolls 256 left / 512 right, clear 3, CL-LINE 6, CL-SCROLL 0; 2,030,681 sprite pixels, 921,684
  table bytes, 6,448 transient checks, 185,079 plot screen bytes, 39.3M interrupt-safety points, max 5
  live keys / 7 entries -> IDENTICAL. Colour rule = first cell ink at the plot exit 3,228 / 3,228.
  Hook cost per frame: mean 2,765 T, max 45,288 T (a frame of text printing: ~300 T per PR-ALL).
- Unit: 43 cases (draw / erase as captured; table full, overflow, no free slot, past column 31, too
  wide, tainted and no-sprite keys, 4 bad geometries; colour types 0-2, INK / PAPER 9, MASK-T; every
  touch site incl. CL-SCROLL, printer buffer, non-aligned cell, scroll columns 0 / 31, clears inside /
  straddling / in overflow, CL-LINE 0 / 2 / 24 / 25) PASS; 9 negative controls on their own code all
  caught (X off by one, erase never hidden, scroll / clear / PR-ALL touch broken, tainted key re-armed,
  table full missed, overflow kept by a full clear, INK 9 ignored).
- Full verification: not run (stage 3). ~25 min (quick 9000 took ~3 min).

## Hardware rounds
Round 1 (2026-10-27): d4302eef hung at the menu (keys dead). Cause (analysis; hardware result of
the fix pending): the game reads keys through ROM KEY-SCAN 0x028E / K-TEST 0x031E (its INKEY$
runtime at 0x61C2) and prints / clears / plots through ROM too. The Next fills the alt ROM from
NextZXOS's ROM3 (not Sinclair's), then the build wrote only 0x386E-0x3BB3 (hooks, over NextZXOS
data at 0x3B00-) and the 3 JPs below 0x2000; the verifier ran Sinclair's ROM (BRIEFING C2 #5).
Fix 5830cbbd: the stub writes the WHOLE 16K image from the build (patch.altrom_low = page 25 with
0x0000-0x1FFF + JPs; altrom = 0x2000-0x4000 from page 24); the image the game reads is the one
verified, byte for byte. Check: cauldron.rom3_independent boots with a ROM3 that differs in every
byte (negative control: the old partial image fails it, 15,546 bytes). Shared code (additive,
default off): z80tonex.altrom_fill `low` (replaces altrom0), nextboot boot / check `sysrom=`;
`selftest --canary` PASSED. quick 2000: same counters as stage 2, IDENTICAL; unit 43 + 9 PASS.

## Open
- Hardware result of 5830cbbd (menu keys, play). CSpect "very slow" with d4302eef: unexplained
  (hook cost measured mean 2,765 T / frame); ask whether the plain .nex is slow there too.
- Outline (Q7) and no figure attribute painting + shadow attribute reads (Q8): not built.
- Colour map + colour sheets + recolour (PLAYBOOK 5, COLOURS.md): not built yet (stage 3 sends the
  sheets: build them first; patterns are converted at run time, so a colour map needs an override
  table keyed by graphic byte in a Next page).
- IM 2 path (0x63DB, never reached): with I = 0xFE an interrupt inside a hook that maps page 26 at
  slot 6 runs the BASIC handler at 25576 with page 26 there; unit-test or hook 0x63DB if a recording
  ever reaches it.
- ROM PLOT / DRAW (PLOT-SUB 0x22E5) and other ROM screen writers: never reached; the verifier fails
  any unhooked write into a live image's rectangle, so a recording that reaches one shows it.
- Bit-level check of the POINT readers (obs. 9) if a shadow design is ever wanted.
- IM 2 path (0x63DB, handler 25576): when is it used? Not in this recording.

## Lesson candidates
- A game that runs ROM code (KEY-SCAN, PRINT, CLS) from an alt ROM image whose rest is copied
  from the SYSTEM ROM3 runs NextZXOS's ROM on hardware, not the one verified: Cauldron hung at the
  menu, keys dead. Write the whole image from the build (patch.altrom_low) and prove it with a
  foreign-ROM3 boot (nextboot sysrom=). Candidate: make that the altrom default (BRIEFING C2 #5).
- A ROM routine as a writer (PR-ALL, CL-LINE, CL-SCROLL) is hooked with a JP in the alt ROM image
  below 0x2000 (patch.altrom0, new); scan the whole ROM for jumps into the replaced bytes first
  (Cauldron: PO-SCR CALLs 0x0E00, inside CL-SCROLL's 0x0DFE).
- An entry hook can run the routine's body itself (CALL body; its RET comes back) when the exit
  cannot take a JP (Cauldron: 0x63DB, the next routine, starts right after the RET): one site gives
  both "show at entry" and "hide at exit"; the body sees 4 more stack bytes (dead stack).
- XOR overlay without a fixed object table: key = (graphic, x, y, rows, width); one plot toggles it;
  other writers taint it (no sprite until a clear holds it whole). Proof: any screen write outside
  the plotter into a live key's rectangle fails the verify, so a missed writer cannot hide.
- XOR parity per image is not "on the screen": overwrite writers (ROM PO-CHAR scenery, scrolls,
  clears) wipe or move XOR figures without an erase plot, and the game's next XOR then lands on
  clean ground (Cauldron frames 2602-2638). An overlay's live set must end at any other writer's
  touch; check with a byte trace of the figure's rows between plots, not only plot counts.
  (patch.xor-overlay-keep-ula has no such failure row yet.)
- `inspect` flags "loader snapshot" when PC is in ROM because an IM 1 interrupt was just taken
  with the BASIC loader still in memory (Cauldron): check the stacked return address before
  treating it as a loader.
- An RZX's embedded snapshot can be a different build of the game than the .z80 delivered with
  it (Cauldron: 11,283 bytes differ, code shifted): the survey analyses the RZX's copy. The survey
  could compare the two start states and warn (BRIEFING C2 candidate).
- Compiled BASIC games read the screen through runtime PEEK / POINT / ATTR routines: find those
  routines first, then classify reads by their return address (Cauldron).
- Figure-cell attribute painting can have gameplay readers (Cauldron ATTR neighbour tests); a
  card for "virtual attribute read" would cover keeping clash-free colours with such readers.

## Stage log
- 2026-10-27 hardware round 1 (menu hang -> whole alt ROM from the build; outline + clash requests recorded): ~45 tool calls, 3 user rounds.
- 2026-10-26 stage 0+1 (survey, patch plan, design question; pilot): see Pilot log.
- 2026-10-26 stage 1 answers: RZX snapshot, all figures sprites, overlay, keep attr painting (3a), defaults 4/5.
- 2026-10-26 stage 2 part 1 (analysis: snapshot extract, plotter decode, 3 whole-RZX probes, Q6): ~85 tool calls, ~1h20, 2 user rounds.
- 2026-10-26 stage 2 part 2 (engine: module, asm, profile, verify, 43 unit cases + 9 negatives, quick 2000 + 9000 PASS, record; shared altrom0 + canary): ~100 tool calls, 0 user rounds. Whole engine modules read: none (fireman template functions only).

## Pilot log
Technique-card pilot, stage 0 + 1, 2026-10-26: ~85 tool calls (4 failed), ~78 min to the design
question (~58 min of it the survey); 3 cards opened, 5 judged from index.json, none corrected later.
Costliest besides the survey: finding the .z80 / RZX mismatch only at call ~60 (lesson candidate).
Full log in git history.
