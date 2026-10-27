---
name: recolour
description: Recolour a game from a painted <game>_PAINTING_SPRITES.png - gives <game>_sprites_painted.nex, its _colours.json and both sheets redrawn in the new colours, in seconds, no rebuild. Use when the user sends a painted colour sheet or says "recolour <game>".
---

# Recolour a game from a painted sheet

The user's whole prompt is usually just "recolour <game>" plus the painted PNG. Do exactly this,
nothing else (no rebuild, no verify, no doc edits unless something fails).

1. Setup (cloud session): attach bleughb/nexclash (read; push only if step 8's follow-up is taken - it ends in a nexclash PR)
   and bleughb/specnext (push), clone both
   side by side; `pip install -r nexclash/requirements.txt --break-system-packages`.
   specnext is large: a sparse checkout of `reference/<folder>` is enough.
2. Find the game: docs/records/<game>.json (one per game; match the title); its `reference` is
   the folder in specnext/reference/, its `outputs.sprites.file` the built .nex. Engines that
   can recolour: `python -c "from nexclash import recolour; print(sorted(recolour.engines()))"`.
   Not listed -> tell the user this engine has no recolour yet (docs/COLOURS.md "RECOLOUR" says what
   it needs) and stop.
3. Check the painted PNG has the same size as `<game>_PAINTING_SPRITES.png` in that folder
   (recolour refuses otherwise; tell the user, do not resize).
4. Work in the scratchpad on COPIES: the build the user runs now (the latest `_painted.nex` WITH its
   `_painted_colours.json` sidecar, else the built .nex), the `_PAINTING_SPRITES_layout.json` and
   `_REFERENCE_ALL_SPRITES_layout.json` of the sheet the user painted, the PNG.
   `python nexclash/nexclash.py recolour <build>.nex PAINTED.png`
   (add `--layout` if the PNG's name does not lead to the layout). The painting is MERGED onto the
   colours that build holds (the command finds them by reproducing the build: sidecar, build
   default, or none): only pixels the user changed change, so an older sheet cannot wipe newer
   paint. No map reproduces the build -> it refuses; ask the user for the colours json it was made
   with (`--onto`), or whether to start from this sheet alone (`--replace`). Grey 100,100,100 =
   transparent where the engine allows it. Only the sheet's grey and coloured pixels are read
   (engines with outlines - Dizzy 1 - also grey the paper inside a graphic's bytes); a `WARNING: N
   painted pixels were NOT used` line means paint landed elsewhere (or the layout is older than
   the sheet): tell the user how many and where, in one line.
5. A refusal is the answer: relay its reason (wrong .nex version, wrong sheet, a pixel painted two
   ways in two figures, a pixel changed on the sheet that also changed since the sheet was drawn -
   each listed with its figure). Do not work around it; nothing was written.
6. Send the user the bundle (SendUserFile): `<build>_painted.nex`, its `_colours.json` and the two
   refreshed sheets `<build>_painted_<game>_PAINTING_SPRITES.png` / `_REFERENCE_ALL_SPRITES.png`
   (paint the refreshed painting sheet next time), with the md5 and counts it printed. A `NOTE:` that
   a sheet is missing from the bundle (no reference layout) goes in the reply.
7. Put the painted PNG in specnext/reference/<folder>/<game>_PAINTING_SPRITES_painted.png and the
   bundle (painted .nex, colours json, refreshed sheets + layouts, report) beside it,
   commit ("<Game>: Dean's repainted sprite sheet (<date>)" + the md5) on a branch, push and open a
   PR in specnext (docs/MAINTAIN.md: maintainers commit on a branch); say in the reply it is ready to merge.
8. Reply in two or three lines. Making the painting the build default (copy the colours json to
   docs/profiles/<record>_colours.json - the record's name, e.g. dizzy1_colours.json - rebuild,
   verify, stamp, PR) is a separate task: offer it,
   do not do it.
