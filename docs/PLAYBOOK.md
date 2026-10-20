# Playbook: one game

Budget rule: a game the tools already convert (`auto` PASS) -> a few tool runs and one short report.
A new engine is phases A-C below; keep each phase to one session where possible.
Only disassemble routines the tools flag as unclassified.

Phases (a long game may be one session per phase; each starts from games/<game>.md, never from
chat history): A = steps 0-4 + design approval by the user; B = steps 5-6 (toolkit PASS);
C = hardware rounds and fixes. Write decisions and open questions to games/<game>.md as they
happen, so a new session can pick up any phase.
Why: Commando took five hardware rounds, each finding something a step below now covers.
Rounds on a long game (phase C): offer to collect the user's whole list in one pass through the
game, fix all of it, then check everything in ONE new pass; never restart the emulator unasked.
Why: the places are far from the start, and every restart costs the user the walk there
(El Capitan Trueno, 2026-10-13).

("The user" below = whoever runs the session: Dean in maintainer sessions, the contributor in an
add-a-game session.)

## 0. Inputs (ask once, up front)
- `.z80` snapshot, 48K or 128K, ideally at the title screen or in game, keyboard controls (not
  joystick mode - e.g. Fantasy World Dizzy byte 62569=255 enables Kempston and caused phantom
  input). A loader snapshot works but needs extra steps (0b).
- RZX recording made per RECORDING_CHECKLIST.md, from that same snapshot.
- Menus and windows: ask whether the game opens a pause, menus or message windows over the play
  area (and the screens without play: end of a part, codes). They are drawn in the ULA, so Layer 2
  and the sprites cover them (step 4). If the user does not know, offer to find them in the code:
  PC and stack while one is up, the key poll that leads there (Trueno: pause menu, access code).
- A test cheat: offer to find one now (immortality: the store of the reduced energy -> NOP),
  marked TEMPORARY in games/<game>.md; remove it before delivery and check the game over.
  Why: rounds reach far into the game only with it (Trueno).

## 0b. Snapshot check (before anything else, ~10 min)
`python nexclash.py inspect GAME.z80` answers most of it (and lists a loader's BASIC + USR targets).
Is it in-game, the title screen, or a LOADER (BASIC program running, PC in ROM)? 48K or 128K?
Which ROM is selected, which interrupt mode, where is the stack? A 128K BASIC loader pages
ROM 0, which the Next does not have (Commando's first builds crashed on the first key). Record
the answers in games/<game>.md.

## 1. Plain conversion
`python nexclash.py convert GAME.z80 [--rzx R]` -> ask the user to test it on the Next.
(128K recordings: leave out --rzx - analyse() wraps 48K memory only and stops with "N port
reading(s) left for frame 0"; prove the tail with `scan --range` instead.)
Check where the tail went (the converter prints it). It must be in memory the
game never touches (step 3 proves this: `scan`); override with `--tail ADDR`.

## 2. Identify the engine
`python nexclash.py identify GAME.z80` covers the TID and Dizzy 1 engines (docs/profiles/
signatures.json); the dedicated engines are recognised by their own checks in `auto`
(is_<engine>, profile `signature`; the table is nexclash/engines.py), so `identify` says unknown
for them (BRIEFING C2 #18). Search the snapshot for their byte signatures. A new engine adds one
line to nexclash/engines.py.
If a known engine matches, align its plotter/eraser instruction-by-instruction
against the known game's (normalise 4-5 digit operands to N; where the opcode
text matches, the numbers map old->new). Then locate by pattern:
plot entry (JP/CALL to plotter), eraser (DI / LD (spsave),SP), screen-write
sites (LD (HL),B after LD (DE),A in plotter; LD (HL),A after XOR C/B in
eraser), wipe (LD IX,nn / LD A,136 / LD DE,1), box (LD A,(nn) / ADD A,4 /
SRL A / LD (nn),A), ISR (IM2 vector -> handler; the CALL after the logic-tick
CALL is the hide slot), pixel test (LD C,A / LD B,0 / SRL C / JR C).
Verify every site's original bytes before building.

Unknown engine: `scan GAME.z80 --rzx R --range 0x4000-0x5AFF --writers` ranks the screen writers
(and finds a back buffer: a big LDI/LDIR/stack writer copying from RAM; scan that range --writers
too), `preview --plot ENTRY` shows what each plot routine draws per caller; classify the inner
loop (masked AND/XOR/OR, pure XOR, LDIR/stack blit, attribute-cell), then continue from step 3.
Classify the RENDERING MODEL first - it picks the hook pattern (BRIEFING A3, decision table 4):
XOR to screen, masked + undo buffer, back-buffer composer, full redraw / tilemap, differential OR.

## 3. One analysis pass over the RZX
Shared commands first: `isr GAME.z80 --rzx R` (what hooks must keep intact for the interrupt
handler: IY/IX reads, stack, paging), `scan GAME.z80 --rzx R --range LO-HI` (free memory for hook
state; also `--frames N --keys K --after ENTRY` for the start-up path no recording covers).
Then, per engine, track "player drawn" from the plotter's/eraser's own screen writes. Report:
- plot/erase/wipe/box/ISR counts, split by drawn/not drawn (double draws? erase
  while not drawn?)
- every non-player routine that READS or WRITES bytes containing the player's
  pixels while drawn, by PC
- for each writer: XOR (safe), nibble-replace, or overwrite (disassemble only these)
- pixel/collision tests: does the result change if the player is removed?
  Needs an exact "patched screen" model: player writes skipped; XOR writers
  apply their delta; overwriters/nibble-replacers apply their rule; any
  UNCLASSIFIED write to a byte where the screens differ must be reported
- memory never read or written, ROM use, stack low-water mark
- writes to any intended patch site (self-modifying code) - and to the bytes AROUND it that a hook
  would emulate or jump back into: list every LD (nn),A / LD (nn),HL into the routine's code first
  (Dizzy 1 rewrites 58079 and 58709 next to its write sites; the first site at 58707 covered 58709)

## 3b. Visual survey and preview (design approval BEFORE building)
- `preview GAME.z80 --rzx R --at F,F,... --plot ENTRY ... [--buffer A:S:L] -o sheet.png` shows
  (with --rzx, `--every N` needs `--stop` too: without it the run ends after 500 frames)
  what each plot routine draws per caller (the figure kinds to ask about); `scan --range BUF
  --writers` lists every routine that draws into the screen / buffer first.
- Render still frames (ULA + planned sprites) from the RZX at several points and, where the
  recording does not reach them, from later levels: figures against every kind of scenery they
  overlap. Use the frames to settle with the user in ONE round: which figures, colours, solid or
  see-through, and the overlap (depth) rule - the game's own rule, always in front, or another.
  (Commando: depth, solid bodies and solid objects were settled across three hardware rounds
  from the user's photos; preview frames would have settled them first.)
- Every figure is a sprite by default (Dean, 2026-10-13: "make everything possible a sprite"): list
  every caller of each plotter from the code (not only those the RZX shows) and convert them all;
  what stays on the ULA (scenery, HUD, text, cases the hooks cannot do) is the question to ask.
  The sheet still shows only what the recording drew: ask for a recording that reaches every
  level, weapon and collectable the user can, before the sheet goes out.
- COLOUR SHEET - every game from Midnight Resistance on (Dean, 2026-10-13). Colours are not
  settled in words: the user paints them.
  - What to send (with the phase-A question; Dean 2026-10-14, rules of 2026-10-19 for ALL games):
    - `<game>_PAINTING_SPRITES.png`: the fewest WHOLE figures that show every graphics byte
      (`coloursheet.choose`, then `write(..., unique=False)`), in the colours the build draws today.
      Why whole: "only the new pixels" of a figure that shares graphics with an earlier one looked
      like corrupted characters to Dean. A pixel shown in two figures is one colour-map entry: `read`
      takes a changed copy over an unchanged one and reports two different paints. (Engines written
      before Rainbow still write unique=True: BRIEFING C2.)
    - `<game>_REFERENCE_ALL_SPRITES.png` (`unique=False`, every figure): to see the result; not read back.
    - Items with their own colours (collectables, fruit): ONE COPY PER COLOUR the game draws them in,
      each painted apart (its own keys).
    - Many figures -> split: one sheet per level, one for the collectables, one for the player
      (`<game>_<PART>_PAINTING_SPRITES.png` / `_REFERENCE_ALL_SPRITES.png`, PART = PLAYER, ISLAND1..,
      LEVEL1.., COLLECTABLES).
    - Join a figure's pieces by the GAME's own object (the routine that builds one object's draw
      list: a hook there tags every piece it allocates), not by boxes that touch: two figures side by
      side, or a figure next to a thrown weapon, were merged into one ("overlapping sprites").
    - "Every level": the recordings must reach every level, boss and collectable. A whole-game
      playthrough (Rainbow: rainbowislands_LeeBee.rzx, 195k frames) is cut into BOOKMARKS, one RZX per
      level (`rzx.scan` finds the frames where the level variable changes, `rzx.cut` writes an RZX that
      starts there); the full file is never replayed again. Replays use `rzx.trace` (C simulator with
      hooks: the whole playthrough in ~10 min; the Python simulator takes hours). Report coverage per
      level: graphics bytes drawn vs the level's graphics data, so a gap is visible, not guessed.
  - Sheet rules (Dean): 1:1 (one PNG pixel = one Spectrum pixel; an enlarged sheet is too big to
    paint), multi-part figures JOINED as the game draws them, a row of 8x8 swatches of the sprite
    palette (1-15) at the top, no text. "Paintable only" (2026-10-14): inside a figure's box only
    the pixels the read-back uses are grey (or coloured); a part's gap, paper the engine cannot draw
    and a pixel already shown on an earlier figure keep the background colour (read back as no paint).
  - Read-back: the user paints, keeps the size, sends it back -> the colour map
    `docs/profiles/<record>_colours.json`. <record> = the evidence record's name (dizzy1_colours.json),
    NOT the reference folder's name: the engine's COLOURS constant loads exactly that path and any
    other name is silently never read; no file = the defaults. The rule is per PIXEL, not per 8x8
    cell: only bits of the graphics bytes a plot draws exist in the map, so paint outside them
    (beyond a graphic's byte span) is reported and ignored - graphics with no spare paper column
    need wider staging. The painting layout keeps the map it was drawn with: a repaint changes only
    the pixels whose colour changed; painting a pixel back to its default removes its entry.
    Re-send both sheets after each read-back. Later levels the RZX does not reach: a second sheet
    from a later recording, read into the same colours file.
  - Transparent and outline pixels: engines may draw opaque non-ink pixels (code 2: an outline, or
    Dizzy 1's enclosed paper, black by default). TRANSPARENT: `coloursheet.read(..., clear=True)`
    reads the sheet's grey on an opaque pixel as transparent (Dean 2026-10-14: "there will always be
    items that need them"). OUTLINES (Dean 2026-10-14: "borders will be required in MANY future
    games"): give every bit of a plot's graphics bytes, paper bits as code 0, and write the sheets
    with `coloursheet.write(..., paint_clear=True)`; a paper bit with a colour nibble is then opaque
    in that colour (Dizzy 1: fill_mask).
  - Code: shared nexclash/coloursheet.py does the sheet side (joining a frame's plots into figures,
    the fewest figures that show every part, PNG, layout JSON, read-back, the colours file). The
    engine supplies the parts: per plot its staging pixels, each with a colour-map key (one graphics
    byte = 8 pixels), bit, ink / outline / clear code and today's colour. Templates: midres.sheet_part
    / capture, CLI `python -m nexclash.<engine> sheet RZX` / `colours painted.png`; for OUTLINES
    dizzy1 (part_from_writes lists every bit of the bytes drawn, paper as code 0; fill_mask turns
    painted paper into opaque pixels in the plane, the sprite patterns and the verify model). A
    capture must strip Fuse autosave snapshots from the RZX first, as auto does before verify
    (midres.capture does; rzxplay desyncs on them otherwise).
  - Where: the PNG and its `_layout.json` hold game graphics: specnext/reference/<game>/ only.
- RECOLOUR - every engine with a colour sheet (Dean, 2026-10-14: "ALL games have this easy
  ability"). A repaint must not need a rebuild + re-verify: `python nexclash.py recolour
  <game>_sprites.nex PAINTED.png` writes `<game>_sprites_painted.nex` + its `_colours.json` in about
  a second (layout found next to the PNG, `X_painted.png` -> `X_layout.json`; the engine is found by
  the .nex). Shared half: nexclash/recolour.py. The engine adds two names (template: dizzy1.py):
  `RECOLOUR = {'game', 'output', 'colours', 'clear', 'note'}` and `recolour(nex_bytes, cmap) ->
  (bytes, info)`, built on `recolour.banks()` / `splice()`. Design rule that makes it safe: put every
  colour-dependent byte (sprite patterns, Layer 2 pixels, palettes, per-figure colour tables) in banks
  the GAME never reads, so a colour change cannot change the logic the verification proved; the
  engine's recolour checks everything else in the .nex is its own build of the expected snapshot
  (patch sites, hook code, the MD5 of the graphics bytes the colours come from) and refuses
  otherwise. The engine loads its map through `recolour.build_colours_path(COLOURS)` (honours
  $NEXCLASH_COLOURS), because the selftest guard builds the game a second time with an empty map and
  requires recolour to turn each build into the other byte for byte (dizzy1: a recolour that forgot
  bank 27 failed it). A painting becomes the build default only by copying its `_colours.json` to
  docs/profiles/<record>_colours.json, then rebuild + verify + stamp as usual.
- Speed budget: `cost GAME.z80 --rzx R --at PLOTTER --group IX` gives the original's cost per
  draw (T-states), draws per frame and per object; set the allowed hook cost per draw now, and design to it (caching, fewer
  uploads). Commando's first solid hooks cost ~18x the original draw and were redesigned.
  Measure the HOOK cost too, before the user tests: T per game frame of the patched runs in the
  verifier's pair runs (no tool yet, BRIEFING C2 #1); code under NEXTREG $07=3 costs (T + memory reads)
  / 8 in 3.5 MHz T - about 6x faster, not 8x (LEARNINGS 2.1f). Midnight Resistance's first commit cost ~1.5 TV frames per game
  frame; a pattern-slot cache brought it to 15-60K T.

- Pixel art is the user's. Say so: an AI is not a good pixel artist (it sees a pixel grid
  coarsely). The AI prepares the sheets - cells or frames copied exactly as the game draws them,
  each distinct look once - and builds the user's drawing in; it does not draw drafts by rules.
  (Trueno: automatic drafts cost many rounds; a copied sheet and the user's hand took minutes.)

## 4. Decide the design (decision table)
| Finding | Action |
|---|---|
| Logic reads player pixels (result changes) | virtual read: screen XOR undo buffer (masked) or XOR graphic (XOR engine) |
| No dependency | NO virtual read (it becomes wrong after an overwriter covers the player) |
| Boxes/panels overwrite the player while drawn | hide sprite at box entry; reappears at next plot |
| Double draws (XOR engine) | parity model: each XOR draw/erase toggles visibility |
| Erase + redraw in same frame | deferred hide at end of the in-game ISR (TID engine) |
| Title ISR plays beeper music | never hook it |
| Patch memory (default) | `altrom`: hooks in alt ROM image 1 (BRIEFING A3; no RAM page, survives 7FFD); hook state in RAM the scan proves untouched (and zero, or explained) |
| Game reads the ROM bytes the hooks need | older strategies (BRIEFING A3 choice rule): printer buffer free (access scan) -> trampolines at 0x5B00; else game never reads ROM -> RAM page at MMU slot 1 (0x386E-0x3CFF), flag in NextReg $7F, compact tail in dead stack |
| Hooks page memory in slot 0 | DI around paging; read IFF with LD A,I twice (NMOS quirk) |
| Interrupts on at the hook sites | hooks never write IX/IY/I or IFF and keep SP on a stack with room, at EVERY instruction (the game's ISR may read them: Commando IY+7) |
| Figure moves (redraw) | never hide at entry and show at exit (flicker): build the new image in other pattern memory, switch the attributes last |
| Menu, pause or message window drawn in the ULA over the play area | wrap its routine: Layer 2 and sprites off (NEXTREG $69 / $15) while it is up, on at its return; NEXTREG keeps every register and flag (Trueno e_mnu). Switching them off also hides whatever the hooks removed from the ULA: plan what the user sees there |
| A screen shown without the normal screen build (end of a part, a special or clear mode) | clear or hide Layer 2 and the sprites on that path, or the old screen's layers stay over it (Trueno: access code screen, the dragon's screen) |
| Code reaches the plotter past the hooked entry | search every CALL/JP to every plotter address: such figures bypass the hook and keep the original drawing path (Trueno: the dragon's energy bar via 0x82E4, its colours lost with the clean-attribute copy) |
| Snapshot taken with the title or menu already on screen | a patch to drawing code does not show the first time: patch the snapshot's screen memory too (Trueno: a menu item removed) |
| Scenery clash: the original cut the scenery along cell edges (black cells), or an object painted the wall around it in its colour | fix cells: those cells redrawn in Layer 2 WITHOUT the palette priority bit (figures stay in front), per screen, from a sheet the user draws; the ULA stays original; mark them so a screen change clears them |
| Per-screen Layer 2 tables | count the pages: one 8K page per screen adds up (Trueno: pages 60-83); check the highest page against an unexpanded Next (1024K = 8K pages 0-95; LEARNINGS 1.3), pack screens per page when many |
| Hook code in the alt ROM / slot-1 page | never at 0x3D00-0x3DFF (Commando crashed with code there; probable cause DivMMC automap on fetch - BRIEFING A1); data there was fine |
| Hook state needs RAM, interrupts on, game uses all RAM | a Next page in a slot the ISR never touches (2-5; isr slot scan), mapped only while a hook runs (Midnight Resistance slot 5) |
| Back-buffer composer, plotters share an address helper | replace the CALL target; plot into a scratch copy of the buffer; patch loop exits to map back (LEARNINGS 2.1) |
| Pure XOR to the screen, many figure kinds / partial draws / thin pieces (Dizzy 1) | 1-bit shadow screen: converted writes XOR the shadow, ULA ^ shadow = original; figures on Layer 2; non-XOR writers put the change into shadow or ULA; effects fold the shadow back (LEARNINGS 2.1) |
| Game has no frame sync (no HALT, FRAMES unread) | hook time = slowdown: run whole plots at 28 MHz (entry hook + return-address trampoline), measure the Speed line |
| The game rewrites bytes in or next to a site | move the site off them; read the rewritten instruction at run time in the hook |

## 5. Build
Hooks: asm/<engine>_hooks.asm with `SAVEBIN "<prefix>_<key>.bin"` per block and
`"hooks": {"source": "asm/<engine>_hooks.asm", ...}` in the profile; after every edit
`python tools/asm2profile.py <engine>` (pinned sjasmplus -> profile hex + symbols).
Copy the nearest engine (module + asm + profile + games/ file; STATUS.md lists every engine):
| Engine | Template for |
|---|---|
| build.py TidPatch | Codemasters TID engine (generic builder) |
| chuckie.py | the simplest: 48K, stateless alt-ROM hooks (no RAM page), interrupts on |
| jetpac.py | 16K game, run-time graphics buffers, no RZX (free runs with a key schedule) |
| loderunner.py | XOR plotter, hooks in RAM (the game reads the alt ROM), figures printed as tiles |
| dizzy1.py | pure XOR to the screen: 1-bit shadow screen + Layer 2, outlines, plots at 28 MHz |
| wally.py / wally2.py | back-buffer composer, interrupts off / every figure on a double-buffered Layer 2 |
| midres.py | interrupts on, all RAM used: hook page at slot 5, CALL-target redirect into a scratch buffer, pattern-slot cache, per-pixel colour map |
| smashtv.py | the game's own plotters into a scratch buffer at slot 7, no frame sync, see-through outline |
| commando.py | 128K BASIC loader, front end, depth from walk boxes, cached solid sprites |
| renegade.py | alt ROM images 0 + 1, loading-screen front end |
| rainbow.py | full redraw / tile composer, 128K (large; excluded from automatic checks) |
Change the profile block and site list, rebuild the asm.
Every site keeps its original-byte check.
Colour map (every game, PLAYBOOK 3b): the sprite builder applies `<record>_colours.json` per pixel -
key = the graphics byte the pixel comes from, a non-zero nibble replaces the default colour of an
opaque pixel - and, in an engine with outlines (paint_clear), makes a PAPER pixel opaque in that
colour (Dizzy 1: fill_mask; its verify model and negative controls must cover it) - and a check of
the graphics bytes stored with the entry (other graphics at that
address in a later level -> defaults). Store it where the build can read it at sprite-build time
(midres: Next pages 28.. at slot 4 during the commit, page tables in the hook page, MidresPatch
store_pages / asm `ovl`). A build with no colours file = today's defaults.

## 6. Verify (differential test)
At every patched routine in the real recording: copy the machine state, run the
original and the patched routine to their return, compare all registers
(except R/T/MEMPTR; AF' included), all memory outside the never-read draw buffers (patch area
and sites excluded; dead stack only where a documented convergence check applies - a hook that
returns into the game's own loop must leave it identical), the patched screen against the
model, and the sprite pixels against the original plot (masked figures: run the plot on a 0x00
and a 0xFF buffer for ink / paper / transparent, midres.truth). With interrupts on at the hooks,
also check interrupt safety after every hook instruction (IX, IY, I, IFF, stack room; Commando,
midres) with a negative control. Every mismatch must be explained or fixed.
Colour map: the expected sprite layer uses the map too (midres.expected_layer / map_colour); unit
cases with a synthetic map per figure, a wrong check byte (must be ignored) and a negative control
(the map left out of the build, informative cases only); once the user's colours file exists, the
full RZX run uses it.
Also simulate the start-up tail: registers restored, no game memory touched.

Long runs (the full verification, selftest): detached + polled, LEARNINGS 2.6.
Iterate fast (the two levels: BRIEFING C3b): while developing use `--quick N` and the unit tests on 1-2
captured states (minutes). N must reach the first call of every hook the unit tests capture
states from, or the run FAILS for lack of a state (Lode Runner at 300 frames: "no captured draw
state"; Commando: "no plot reused a cached image"): start at 2000. One quick run per change; read
its counters before changing anything else.
The full verification runs ONCE, on the build that goes to the user, and it is the stamping run:
write the evidence record first (step 7), commit, then `python selftest.py --game <record> --verify
--stamp` (the record's verify recipe + the rebuild MD5s; it stamps the record, so the maintainers'
`--affected` before the merge has nothing left to do for this game). Never a separate full `auto`
as well (Commando ran the ~55 min full check five or six times).
Unit cases: cross only the inputs that interact. Every graphic x every position edge is one
product; colours, slots and similar independent inputs need each value once, on a few graphics -
not every combination (Jetpac's 5,616 graphic cases are 117 graphics x 8 positions x 3 inks x 2
slots; 117 x 8 + the inks and slots once each covers the same guard edges).

## 6b. Hardware risk review (before every build the user tests)
Go through BRIEFING A1 "Simulator blind spots" item by item for what changed since the last
hardware round (DivMMC trap, interrupts inside hooks, raster/tearing, speed, emulator
differences); each item must be covered by a toolkit check or named in the hardware checklist.
Ask the user to try CSpect first if a build changes memory layout or start-up.

## 7. Deliver
`<game>_sprites.nex`, `<game>.nex`, builder, asm sources; a short results
table; a hardware checklist. Add the new profile (and signature if a new
engine) to docs/profiles/, games/<game>.md, and the evidence record docs/records/<game>.json
(copy the nearest engine's record; `modules` = the modules your build imports, `own_modules` /
`data` = your engine's files, `rebuild.decisions` = the run's <name>_decisions.json, `status` =
the STATUS row), then `python -m nexclash.records views` (regenerates STATUS / VERIFICATION
checksums / verified.json). Check it: `python -m nexclash.records deps <game>` lists what your
game's evidence depends on; the one full verification (step 6) stamps it. The engine's line in
nexclash/engines.py is not shared code (rebuild-only); anything else outside your engine is:
`python selftest.py --canary`.
