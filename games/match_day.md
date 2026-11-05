# Match Day (Ocean, 1985; Jon Ritman / Chris Clarke) - engine `matchday`

48K. Code: nexclash/matchday.py (facts, shadow model, sheets, preview, build, verify, unit tests,
recolour), asm/matchday_hooks.asm, docs/profiles/match_day.json (after any .asm edit:
`python tools/asm2profile.py match_day`). Dispatch: nexclash/engines.py, `is_matchday` (profile
signature).
Reference (specnext/reference/match_day/): Match_Day_1985_Ocean.z80 + Match_Day_1985_Ocean.rzx
(Dean, 2026-10-20; 6210 frames, 124 s: title, menu, walk-on scene, the first ~6 match minutes with
a goal and a keeper dive) + Match_Day_spectrumcomputing.rzx (50403 frames, 1008 s; from
spectrumcomputing.co.uk entry 3067, supplied by Dean 2026-10-20; its own start snapshot: code
identical at every plotter / line writer, 13 bytes of game state differ). Manual: gamesdatabase.org scan (image only, no text layer).

    python -m nexclash.matchday sheet   Match_Day_1985_Ocean.z80 Match_Day_1985_Ocean.rzx Match_Day_spectrumcomputing.rzx -o match_day
    python -m nexclash.matchday preview Match_Day_1985_Ocean.z80 Match_Day_1985_Ocean.rzx --at 2200,3760,5400,6100
    python nexclash.py auto Match_Day_1985_Ocean.z80 --rzx Match_Day_1985_Ocean.rzx --rzx Match_Day_spectrumcomputing.rzx --no-record

## Status
Phase A done and agreed (2026-10-20 16:43). Phase B (build) in progress.

## Snapshot (0b)
- 48K, PC 0x0038 (in the ROM IM 1 handler), DI, IM 1, I=0x3F, SP 0xBDBC, border 0. Title/menu.
- In game: IM 2, I=0x3B, vector 0x3BFF -> 0xFFFF (x4729 in the RZX); menus run IM 1 (x1231).
- ISR (`isr`): reads the interrupted IY (ROM keyboard scan: LD C,(IY+7) at 764...), uses AF'
  (35320, 35352, 45917), <= 24 bytes of stack, OUT (254) only. Slots never touched: 3, 6.
- Plain conversion: tail 0xBD5C (converter default, checked safe).
- RZX: one segment; SZX snapshot with a ZXPR block (skoolkit warns "unsupported", harmless).

## Game facts (from the code + the RZX)
- Every figure is drawn by XOR straight to the screen; each draw erases the old image and draws
  the new one in ONE pass (old XOR new per byte; separate old / new loops when the address moved).
- Players: 0x8B45, IX = object record (27 bytes). 16 pitch objects at 0xB4FC + 27k (k = 0..15),
  the spare 0xB6AC (the keeper's second half while diving, also walk-on scene). Callers 0x821F loop
  (return 0x8223), 0x8250 loop (0x825A), 0x826D (single). The depth sort SWAPS whole records, so a
  figure changes IX between frames: identify a figure by its buffer pair (IX+0x14..0x17).
  - Fields: +0 flags (bit 0 = upper-body variant, bit 5 = which buffer, bit 6 = bottom-edge
    path), +3 frame, +5 x, +7 y, +8/9 new screen address, +0x0E STRIP colour, +0x0F SOCKS colour,
    +0x10 upper-body frame, +0x14/+0x16 the two image buffers (3 bytes x rows).
  - 0x8DEC builds an image: HL = graphics, B = rows/2 (TWO rows per iteration), A&6 = shift
    (0 / 2 / 4 / 6 px: 0x8E04, 0x8E9B, 0x8E1C+0x8E30 RLD, 0x8E57 stack). 28-row frames at
    0xC460 + 56n (n = 0..119; 72.. = the keeper's dive, left half 2k / right half 2k+1, 16 px apart);
    the 0x8CDA path: the frame's lower 14 rows + an 18-row upper body at 0xDDC0 + 36u (u = 0..17:
    arms up, headers, throw-ins), upper body first in the buffer.
  - 0x8ECE dispatches on ($93AC) (old + new row counts) to the XOR loops 0x8EF0-0x9165 (unrolled,
    clipped at the screen edges); the draw runs from the buffer's end = bottom row, upwards.
  - Cell paints 0x9168-0x9348 (writers 0x934E / 0x9369 / 0x937D): old cells back to the pitch ink
    ($93A5), new cells: bottom 1-2 cell rows (BIT 2 of y) IX+0x0F, 3 rows above IX+0x0E.
  - Socks indicator (Dean, 2026-10-20: "the player is indicated on-screen by his socks turning the
    colour of the rest of his strip"): 0x82BD-0x82CD writes the controlled players' IX+0x0F
    from $897F / $8981.
- Ball: 0x9FCF: shadow (B=1) then ball (5 rows) through 0xA046 (XOR old + new, 2 bytes a row);
  graphics 0xA111 + 14 * (x & 7) (pre-shifted); off screen = address 0x2000 (a ROM write).
- Scenery writers, all stay on the ULA: XOR line / block writers (pitch lines, boxes, goals, net):
  0x5F2A / 0x5F2E, 0x62D3 / 0x62DB, 0xE73B-0xEBED, 0xEC50-0xECB1, 0xEF3F-0xEF74, 0xF049-0xF0BA, 0xF198-0xF1C9; overwriters: screen
  clears 0x87DF / 0xEFAD, crowd copier 0x9936-0x9987 + 0x99DF attrs, the walk-on scene's 2x plotter
  0x95A6 (overwrites), text 0x5F2B.., 0x6136.., HUD.
- Pixel readers (an2 pass over BOTH recordings, 56k frames): every read of a figure byte is a writer
  reading the byte it rewrites (XOR writers, overwriters, the crowd LDI once); no collision or logic
  reads the screen -> no virtual reads needed.
- Shadow model (matchday.Capture): figure XOR writes into a 1-bit shadow, overwriters clear the
  shadow at the bytes they write; ULA XOR shadow = scenery only, checked by eye on 5 frames
  (preview) and by the per-figure footprints (XOR of the footprints == the shadow).
- Overwriters on figure bytes in the RZX: 0x9973 crowd copier x4 (a figure at the top edge), 0xEFB3
  screen clear x145 (end of the match part): both handled by the overwriter rule.
- Menus: "Main Menu", "Change Match Details" (length, difficulty, players, computer opponent,
  Colours: strip colours, border), "Change Team Names", pause key, "FINAL SCORE", "Kick Off",
  "Start Second Half", "Begin Extra Time", "MATCH TO BE DECIDED BY REPLAY" (strings at 0x5Fxx-0x7Exx).
  Team colours come from the menu at run time -> sprites must take IX+0x0E / IX+0x0F live.

## Coverage (sheet, both recordings)
- Frames drawn 0-115 (of 120), upper bodies 0-17 (all), ball all 8 shifts. Frames 116-119 (one dive
  pair look-alike + two halves) only "From the code" (2 figures). Dive halves are joined on the
  sheet only as matching pairs (2k left + 2k+1 right): the alternate-frame lag mixes steps.

## Dean's decisions (2026-10-20)
- Players SOLID: the see-through pixels (paper enclosed by the figure, `matchday.enclosed`) in the
  PITCH GREEN, opaque (14:08; replaces "opposite team's colours" 14:01 and "black" 14:05): the
  lines behind a player no longer show through. Preview: match_day_PREVIEW_solid.png.
- Bottom edge: as the original (figures drawn over the score line, no clipping).
- Keeper dive "torn in half" (Dean, from the preview): the ORIGINAL tears the same way - the keeper
  and the spare object 0xB6AC are drawn on alternate frames, so while the camera scrolls one half
  lags one update (~4 px; RZX frame 3760: halves 12 px apart instead of 8 by ink, frames 92/93 fit
  exactly 16 px apart). Fix (Dean 14:08: "still has a tear" = fix it): the spare half's sprite is
  shifted by (camera x at its draw - camera x at the keeper half's draw) (camera = 0xE60B), so
  both halves sit where they would at the same camera position; the shadow model and the logic
  unchanged. Preview: match_day_PREVIEW_dive.png (top original, bottom planned, frames 3746-3790).
- No further recording of his own (14:08); then supplied the spectrumcomputing.co.uk RZX (14:13),
  which covers all but frames 116-119 (unit tests for those).
- Sheet: Dean paints it later; build with the defaults (roles) until then, recolour afterwards.

## Phase A proposal - AGREED by Dean 2026-10-20 16:43 ("1-3, i agree"; no messages over the pitch)
- Sprites: every player (both teams, keepers, the dive joined), ball, ball shadow. ULA: pitch,
  lines, goals, crowd, clock, score, menus, the walk-on scene (2x overwriting plotter, no clash
  problem on a still screen).
- Colours by ROLE: sheet swatch 1 (orange) = the object's STRIP colour (IX+0x0E), swatch 2 (lilac)
  = its SOCKS colour (IX+0x0F), both from the game at run time (menu colours and the socks
  indicator keep working), swatches 3-15 fixed colours. Default: the bottom 8 rows SOCKS, the rest
  STRIP; ball / shadow white. Paper bits are paintable (outline / filled gaps).
- Depth: lower on the screen (nearer) in front; ball by its ground (shadow) position; shadow under
  every player.

## Open (ask, do not decide)
(none from phase A; Dean found no message window over the pitch either)

## Patch design (phase B)
- Every plotter keeps running; its 42 screen / attribute writes become NOPs (matchday.SCREEN_NOPS:
  the player XOR loops 0x8EF9..0x914E, the cell paints 0x9356..0x9385, the ball 0xA048..0xA05F),
  so registers and game memory stay the original's and the ULA keeps only the scenery.
- Hooks in alt ROM image 1 at 0x2300-0x2C51 (ROM 0x22CB-0x3BFE is never read: scan, both
  recordings; 0x3BFF/0x3C00 = the game's IM 2 vector FF FF stays ROM; nothing at 0x3D00-0x3DFF).
  Sites (original bytes checked): 0x8DEC e_bd (image build), 0x8D63 e_clr (the 4-row clear),
  0x8B5C e_pl (CALL 0x8ECE, the XOR draw), 0x9D15 e_ball (CALL 0x9FCF), 0x817F e_frame (match
  loop pass), 0xE62C e_cls (screen clear at match set-up), 0x819D e_exit (match loop exit).
- State: RAM page 26 at MMU slot 6 only while a hook runs (slot 6 = the only slot the IM 2 handler
  never touches -> interrupts stay ON); row tables (4-bit nibbles per graphics row, colours and
  the green fill baked in) pages 28-31, one row's page at slot 6 while a pattern is built. Hook
  stack 0x5BA8-0x5BFF (printer buffer bytes the game never touches). Hooks run at 28 MHz.
- Images: each figure keeps a ring of its last builds / clears (dest, graphics row, shift, seq);
  e_pl rebuilds the shown image row by row from the newest entry covering each buffer row (the
  game reuses, partly rebuilds and clears its two buffers per figure). Figure k = buffer pair
  index (IX+0x14 - 0xB736) / 192 (the depth sort swaps records). Patterns double buffered (built
  while the other shows, switched in e_frame).
- Colours: per-sprite palette offset per (strip, socks) pair (index 1 = IX+0x0E, 2 = IX+0x0F;
  16 banks, allocated on demand), fixed colours 3-15, fill = palette index 7 (pitch green 0x14).
- e_frame: sprites in depth order (shadow first, then players and ball by bottom y: lower =
  in front), the dive's spare half 0xB6AC shifted by the camera difference (Dean's tear fix).
- Recolour: RECOLOUR / recolour() (no rebuild); colours file docs/profiles/match_day_colours.json
  (none yet = the role defaults).

## Verification notes
- The verify models the new image AS AT THE DRAW (0x8ECE): 0x8D63 clears the top 4 rows of the
  buffer just drawn later in the same call (RZX frame 3882: an arm-up figure at the right edge;
  the model read the buffer after the call and reported the hand as "sprite differs").
- Explained notes (original behaviour): "edge-dispatch debris" (the game dispatches its XOR loop
  on old + new column counts at the screen edge and leaves stray columns) and "sprite shows the
  image column the original culls at the screen edge" (2 columns drawn of a 3-column shifted image);
  both exercised by the unit walks off / onto both edges.

## Hardware risk review (6b, 2026-10-20)
- DivMMC: no hook code at 0x3D00-0x3DFF (code ends 0x2C51).
- Interrupts in hooks: per-instruction interrupt-safety check + negative control (state page at
  slot 3 detected).
- Raster: sprites switch in e_frame, not raster-synced: possible tearing of a moving figure -> checklist.
- Speed: hooks ~14,900 T per TV frame at 28 MHz (quick run, 4500 frames; the match loop runs one
  pass per ~3 frames) -> compare game speed with the plain build.
- IM 2 vector at 0x3BFF read from the alt ROM image: left FF FF (the build refuses longer hooks).

## Hardware round 1 (Dean, 2026-10-20 18:42; builds 5bda1d78 plain / 6188bacd sprites)
- Title (loader) screen bottom third garbage, menu key icons solid yellow, team names missing - in
  BOTH builds. Cause: the game keeps icons / picture data (0x5B00-0x5B72) and team names
  (0x5B90-0x5BFF: RITMAN ROVERS, CLARKE P R, the cup teams) in the 48K printer buffer, and NextZXOS
  keeps its paging routines + system variables there (manual ch. 24: SWAP 0x5B00.., BANKM 0x5B5C,
  BANK678 0x5B67, TSTACK): the .nex loader writes them after loading bank 5. The boot simulator
  did not model it (all-OK boot). Fix: z80tonex `keep_printer_buffer` (opt-in; the stub copies the
  snapshot's 256 bytes back before the tail), nextboot `nexload=True` (the boot check starts with the
  buffer overwritten). Both Match Day builds use them.
- The hook stack 0x5BA8-0x5BFF (round 1) sat on the cup team names (never read in either RZX): now
  every hook saves the 88 bytes on entry and puts them back on exit (ENTERST / LEAVEST); verify
  compares them; negative control (no restore) detected.
- Slowdown: the match loop has NO frame sync (no HALT / FRAMES wait), so hook time = lost speed
  (~+25 % in round 1). The game's own player draw (0x8B45) is 38.6 % of all frame time; round 2 runs
  the figure image builds (e_bd), the XOR draw loop (e_pl -> 0x8ECE, writes NOPed) and the ball
  routine (e_ball) at 28 MHz: +2.7 % real time per frame vs the original (verify's Speed line counts
  28 MHz T / 6).
- 28 MHz and the sound: the IM 2 handler (0x89F0..0x8A22, via 0xFFFF / 0xFFF4) plays beeper sound
  with timed loops (0xB381..). An interrupt landing in 28 MHz code (round 1: inside a hook) ran it at
  28 MHz. Round 2: the alt ROM's IM 2 vector word (0x3BFF) -> isr_w (speed into NextReg 0x7F, 3.5
  MHz, JP 0xFFFF), the handler's exit 0x8A20 POP HL / EI / RET -> JP isr_x (speed back). No stack
  depth added: the match stack's deepest point 0x89A8 has game variables 18 bytes below (0x898A..),
  and the game takes interrupts with SP inside its 0xFFB8 copy buffer (shift-6 copy builder).
- See-through fill dark green (0x14): the pitch is attr 0x67 = BRIGHT green; fill = 0x1C (index 13).

## Rework (opt-in): whole alt ROM image + start-up tail (engine matchday_v2, `--altrom-fill whole`)
Ported from Jon Attree's .nxc work, 2026-11-04: refactor-unpinned 70a2529 (the tail, the verifier's alt ROM model;
built, not verified) combined with pilot runs/match_day 4a6493d (the IM 1 handler compared at every 0x0038 and the
rom3_left negative; its .nxc d7a7aaf9 was the alt ROM fix only). Not published as a .nxc: the proof is the
verification below. Dean's files and build (f0aecd13 / 612761ec, pin rom3) are untouched and stay the default.
- What and why:
  - Whole alt ROM image: the shared fill (z80tonex, `--altrom-fill whole`) writes Sinclair's ROM + the hooks over
    all of 0x0000-0x3FFF. Before, only 0x2300-0x3C01 went over NextZXOS's ROM3, whose IM 1 handler CALLs 0x386E and
    UDG print JPs to 0x387E: here 0xFF bytes (RST 38). The menus run IM 1; only NextZXOS's DivMMC trap hid it.
  - Start-up tail at 0xBE00 in both builds (TAIL_ADDR): the converter's default put it below SP (0xBD5D plain,
    0xBD77 sprites), on the trophy screen's attribute data 0xBD40-0xBDBB (read first by PC 46378, frame 140):
    white blocks and colour squares under the trophy. 0xBDC0-0xBFFF is written first by PC 34581 in both RZX.
  - Verifier: the alt ROM image as the Next holds it (nextboot.alt_image), the IM 1 handler run against the
    original's at every 0x0038 (NextZXOS's ROM3 modelled: enNextZX.rom, a record input), bytes outside the hooks
    = Sinclair's; `auto` proves the tail with nextboot.rom_paths.
- Kept apart: nexclash/matchday_v2.py (a copy of matchday.py with those changes; Dean's hooks, profile and colours
  read, not copied); engines.py picks it before `matchday` for `--altrom-fill whole`, the opt-in the pin names.
- Builds (= refactor-unpinned's): plain 02fd1835, sprites ec0706e9.
- Results: `auto --altrom-fill whole` with both recordings (the record's rework recipe; 2026-11-04, ~48 min):
  plain 02fd1835, sprites ec0706e9, boot OK; match_day.rzx 6,211 frames IDENTICAL (36,605 objects, 1.80M sprite
  pixels, IM 1 handler = the original's at all 1,232 interrupts), spectrumcomputing 50,404 frames IDENTICAL (376,695
  objects, 20.6M sprite pixels, 1,073 IM 1 interrupts); unit 461 cases PASS, 3 negative controls detected; rom3_left
  detected at 1,232 of 1,232 IM 1 interrupts; the old tail (0xBD5D) detected by rom_paths (read before written).
  ROM paths: the sprite build runs every ROM byte as recorded (reads only its IM 2 vector 0x3BFF-0x3C00); both
  tails never read before written. Speed +2.3 % / +3.5 % (simulated, as Dean's). `selftest --game match_day`:
  Dean's builds and the rework's rebuilt = recorded.
  JNext 1.1.104 headless (read-only card copy, a key at the title, frame +50): the trophy screen drawn clean in
  both rework builds, corrupted in Dean's 612761ec / f0aecd13 (specnext match_day/match_day_v2_JNEXT_trophy.png).
- Hardware: none. Checklist: below, plus the trophy screen after the title (clean), the menus (IM 1).

## Hardware checklist
- Plain match_day.nex and match_day_sprites.nex both start (title, menu, match).
- Players, ball and shadow as sprites; no clash; pitch lines hidden behind players (green fill).
- Team colours from the Colours menu; the controlled player's socks indicator.
- Keeper dive joined (no tear); depth: nearer players in front, ball by its shadow.
- Bottom edge: figures over the score line as in the original; both side edges while scrolling.
- Half time, full time, replay / extra time screens: no sprites left over.
- Game speed equal to the plain build (round 2: +2.7 % measured); match sound / music at its normal
  pitch and tempo; any tearing.
- Title picture, menu icons, team names (and the cup's team names) intact in both builds.

## Lessons
- [card patch.whole-altrom-image §Use / do not use] opt-in rework available: whole alt ROM image (see card patch.whole-altrom-image): its menus run IM 1 into 0xFF bytes once DivMMC no longer traps 0x0038 (RST 38 recursion; runs/altrom_audit; ROM paths: 0x004A from frame 1). Output pinned.
- [tool nextboot.rom_paths] opt-in rework available: start-up tail. The trophy corruption is the tail the converter put below SP (0xBD5D plain, 0xBD77 sprites) on the trophy screen's attribute data 0xBD40-0xBDBB, read first by PC 46378 at frame 140; not the printer buffer, not the alt ROM. JNext: restoring those bytes at game start draws it clean. Fix: tail 0xBE00 (0xBDC0-0xBFFF written first by PC 34581 in both RZX); trial on refactor-unpinned (70a2529, JNext clean, not fully verified). Output pinned. New builds: `auto` proves every tail.

- [card patch.whole-altrom-image §Verification] (rework, 2026-11-04) with the shared whole fill the verifier's
  model comes from nextboot.alt_image, so the old-image negative (rom3_left) is a flag on the patch, not a second
  build; detected by the IM 1 check at every menu interrupt. The tail proof's negative (the old tail) runs
  rom_paths on a build kept out of `auto`'s own .nex list.

## Technique use
- patch.whole-altrom-image: no help: rework not applied, output pinned (record pin)
- patch.whole-altrom-image: used: matchday_v2 builds with the shared whole fill and verifies against the Next's image

## Friction
- reuse: [tool nextboot.rom_paths] the tail proof and the alt ROM model are the shared ones; only the IM 1 check is per engine
- retries: [none: both builds equal refactor-unpinned's first time]
- environment: [none: headless JNext with HOME in the scratchpad, a read-only card copy]
- hand-rolled: [local: one JNext key script for the trophy capture] (a key at the title, frames +50 and +450)
- scratch: [none: JNext scripts stayed in the session scratchpad; the capture is in specnext]
