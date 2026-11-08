# Colour sheets and recolour (PLAYBOOK stage 3-4; read when you build or read back a sheet)

Sheets, read-back, `recolour` and painter (PLAYBOOK 3b). Send sheets with the first
sprite build (stage 3); the user can then repaint without rebuilding the engine.

- PALETTE STANDARD (Jon 2026-11-07; .nxc COLOUR-STANDARD.md). Nothing breaks for painters: sheet rules
  unchanged; new sheets pick colours from the master palette, the Next's standard 256 (RRRGGGBB;
  `nexclash/master_palette.py`, with the nearest master). Why: one shade in every game; shades cost no
  speed or memory, colours per figure do (15 per 4-bit sheet, the norm; 8-bit sprites or Layer 2 only
  when needed). Default mode: the Spectrum's colours, all in the master. A shade outside it where it
  matters: say so in the patch notes. Existing games keep their colours until their next update;
  `tools/palette_check.py` lists them (warns, never fails).

- COLOUR SHEET - every game from Midnight Resistance on (Dean, 2026-10-13). Colours are not
  settled in words: the user paints them.
  - What to send (Dean 2026-10-14; rules of 2026-10-19, ALL games):
    - `<game>_PAINTING_SPRITES.png`: the fewest WHOLE figures that show every graphics byte
      (`coloursheet.choose`, then `write(..., unique=False)`), in the colours the build draws today.
      Shared pixels use one map entry: `read` prefers a changed copy over an unchanged
      one and rejects conflicting paints. Partial figures looked corrupted; older engines
      using unique=True remain in BRIEFING C2.
    - `<game>_REFERENCE_ALL_SPRITES.png` (`unique=False`, every figure): to see the result; not read back.
    - Items with their own colours (collectables, fruit): ONE COPY PER COLOUR the game draws them in,
      each painted apart (its own keys).
    - Many figures -> split: one sheet per level, one for the collectables, one for the player
      (`<game>_<PART>_PAINTING_SPRITES.png` / `_REFERENCE_ALL_SPRITES.png`, PART = PLAYER, ISLAND1..,
      LEVEL1.., COLLECTABLES).
    - Join a figure's pieces by the GAME's own object (a hook in the routine that builds its draw
      list tags every piece), not by boxes that touch: two figures side by
      side, or a figure next to a thrown weapon, were merged into one ("overlapping sprites").
    - "Every level": the recordings must reach every level, boss and collectable; cut a whole-game
      playthrough into one RZX per level (`rzx.scan` / `rzx.cut`, replay with `rzx.trace`: LEARNINGS).
      Report coverage per level (graphics bytes drawn vs the level's data): a gap visible, not guessed.
  - Sheet rules (Dean): 1:1 (one PNG pixel = one Spectrum pixel; an enlarged sheet is too big to
    paint), multi-part figures JOINED as the game draws them, a row of 8x8 swatches of the sprite
    palette at the top, no text (1-15 for 4bpp; the full declared palette for indexed Layer 2). "Paintable only" (2026-10-14): inside a figure's box only
    the pixels the read-back uses are grey (or coloured); a part's gap, paper the engine cannot draw
    and a pixel already shown on an earlier figure keep the background colour (read back as no paint).
  - Read-back: the user paints, keeps the size, sends it back -> the colour map
    `docs/profiles/<record>_colours.json`. <record> = the evidence record's name (dizzy1_colours.json),
    NOT the reference folder's name: the engine's COLOURS constant loads exactly that path (any
    other name is never read); no file = the defaults. The rule is per PIXEL, not per 8x8
    cell: only bits of the graphics bytes a plot draws exist in the map, so paint outside them
    is reported and ignored - graphics with no spare paper column
    need wider staging, or keys of their own for the pixels outside the bytes (Cauldron: an outline
    ring per image, key graphic:WxR:line,col). Patterns built at run time: the map goes into per-image override tables the upload applies
    (docs/techniques/patch.runtime-colour-map.md). The painting layout keeps the map it was drawn with: a repaint changes only
    the pixels whose colour changed; painting a pixel back to its default removes its entry.
    Re-send both sheets after each read-back (recolour redraws them: below). Later levels the RZX does not reach: a second sheet
    from a later recording, read into the same colours file.
  - Transparent and outline pixels: engines may draw opaque non-ink pixels (code 2: an outline, or
    Dizzy 1's enclosed paper, black by default). TRANSPARENT: `coloursheet.read(..., clear=True)`
    reads the sheet's grey on an opaque pixel as transparent (Dean 2026-10-14: "there will always be
    items that need them"). OUTLINES (Dean 2026-10-14: "borders will be required in MANY future
    games"): give every bit of a plot's graphics bytes, paper bits as code 0, and write the sheets
    with `coloursheet.write(..., paint_clear=True)`; a paper bit with a colour nibble is then opaque
    in that colour (Dizzy 1: fill_mask).
  - Maps: indexes 0-15 use eight hex nibbles; wider entries use eight integers, never
    variable-width hex. Both load. Wide palettes only: unchanged equal-RGB pixels keep
    their index. Default/transparent is not opaque black.
  - Code: shared nexclash/coloursheet.py does the sheet side (joining plots into figures, the
    fewest figures showing every part, PNG, layout, read-back, merge, redraw); its docstring defines
    the part format the engine supplies. Templates:
    midres.sheet_part / capture; OUTLINES dizzy1 (part_from_writes: paper bits as code 0; fill_mask)
    and cauldron (ring keys); CLI `python -m nexclash.<engine> sheet RZX`. A capture strips Fuse
    autosave snapshots first (rzxplay desyncs on them; midres.capture).
  - Where: the PNG and its `_layout.json` hold game graphics: specnext/reference/<game>/ only.
- RECOLOUR - every engine with a colour sheet (Dean 2026-10-14: "ALL games have this easy
  ability"); shared half nexclash/recolour.py, steps in .claude/skills/recolour.
  - Routine use (one command): `python nexclash.py recolour BUILD.nex
    PAINTED.png` (layout beside the PNG, `X_painted.png` -> `X_layout.json`; engine found by the
    .nex). It MERGES the painting onto the map the build holds, found by reproduction
    (`recolour(build, map)` = the build byte for byte): the .nex's `_colours.json` sidecar, the
    build default or empty; `--onto MAP` names it, `--replace` starts from the sheet's map. Pixel
    states (default / colour / transparent) merge three ways (`coloursheet.merge`), so an old sheet
    cannot wipe newer paint. Refused, nothing written: a pixel painted two ways, a pixel changed on
    the sheet and since, a build no map reproduces, a sheet of another identity. Output, all or
    nothing: .nex, colours json, both sheets redrawn from their OWN layouts (`coloursheet.redraw`,
    no capture; a missing one is reported) + layouts, `_report.json`. A painting becomes the build
    default only by copying its `_colours.json` to docs/profiles/<record>_colours.json, then
    rebuild + verify + stamp.
  - Engine contract (docs/ENGINE_CONTRACT.md OPTIONAL; templates cauldron.py, dizzy1.py):
    `RECOLOUR = {'game', 'output', 'colours', 'clear', 'note'}`; `recolour(nex_bytes, cmap) ->
    (bytes, info)` on `recolour.banks()` / `splice()`, rewriting only banks the GAME never reads
    (patterns, Layer 2, palettes, colour tables) and refusing a .nex that is not its build of the
    expected snapshot (sites, hook code, graphics MD5); the map loaded through
    `recolour.build_colours_path(COLOURS)` (selftest: recolour turns the empty-map and default
    builds into each other byte for byte); the sheet writer passes
    `identity=colour_identity(peek)` to `coloursheet.write`.
  - Identity: `colour_identity(peek)` -> {schema 1; game (record); engine (module); keys (key
    scheme + version: what a key and bit mean); inputs (MD5 of every game byte the keys and colour
    banks derive from); geometry (MD5 of engine data the keys follow beyond those bytes - Cauldron's
    image list - or None)}. ONE function for the producer (sheet, capture memory) and the consumer
    (recolour, the .nex via `recolour.nex_peek`, 48K; a 128K engine adds `nex_peek`); any field
    differing -> refused. No identity (layouts before 2026-10-27, or no function): "unverified" in
    the report; build checks still apply. Change the keys meaning -> bump `keys`.

- PAINTER - the default first step of an Enhanced set (Dean, Jon 2026-11-04; refactor plan 19-22):
  `python -m nexclash.paint regions SHEET_layout.json -o D` (regions, guesses, D/parts.json: label one
  key frame per family), `paint SHEET_layout.json --parts D/parts.json -o D` (painted sheet for
  `recolour`, compare.png, look sheet: CUT 0), `export` / `import` (repaint anywhere; recolour puts it
  back). Parts follow the drawn lines; no white outline; block or row colouring only if the author
  asks. It follows the game's pixels, not hand drawing (Trueno); the author's labels and touch-ups win.
