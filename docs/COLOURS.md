# Colour sheets and recolour (PLAYBOOK stage 3-4; read when you build or read back a sheet)

The rules for the colour sheets the user paints, the read-back into the colour map, and `recolour`.
Moved out of PLAYBOOK 3b (2026-10-26) so a session reads them only when it works on colours. Since
2026-10-26 the sheets go out with the first sprite build (stage 3), not with the design question:
recolour makes a repaint free (no rebuild, no re-verify), so colour is not a design decision.
"Phase-A question" below = that delivery.

- COLOUR SHEET - every game from Midnight Resistance on (Dean, 2026-10-13). Colours are not
  settled in words: the user paints them.
  - What to send (with the first sprite build since 2026-10-26, before that with the phase-A question; Dean 2026-10-14, rules of 2026-10-19 for ALL games):
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

- Pixel art is the user's. Say so: an AI is not a good pixel artist (it sees a pixel grid
  coarsely). The AI prepares the sheets - cells or frames copied exactly as the game draws them,
  each distinct look once - and builds the user's drawing in; it does not draw drafts by rules.
  (Trueno: automatic drafts cost many rounds; a copied sheet and the user's hand took minutes.)
