---
name: recolour
description: Recolour a game from a painted <game>_PAINTING_SPRITES.png - gives <game>_sprites_painted.nex + its _colours.json in seconds, no rebuild. Use when the user sends a painted colour sheet or says "recolour <game>".
---

# Recolour a game from a painted sheet

The user's whole prompt is usually just "recolour <game>" plus the painted PNG. Do exactly this,
nothing else (no rebuild, no verify, no doc edits unless something fails).

1. Setup (cloud session): attach bleughb/nexclash (read) and bleughb/specnext (push), clone both
   side by side; `pip install -r nexclash/requirements.txt --break-system-packages`.
   specnext is large: a sparse checkout of `reference/<folder>` is enough.
2. Find the game: docs/records/<game>.json (one per game; match the title); its `reference` is
   the folder in specnext/reference/, its `outputs.sprites.file` the built .nex. Engines that
   can recolour: `python -c "from nexclash import recolour; print(sorted(recolour.engines()))"`.
   Not listed -> tell the user this engine has no recolour yet (PLAYBOOK 3b "RECOLOUR" says what
   it needs) and stop.
3. Check the painted PNG has the same size as `<game>_PAINTING_SPRITES.png` in that folder
   (recolour refuses otherwise; tell the user, do not resize).
4. Work in the scratchpad on COPIES: the built .nex, the `_PAINTING_SPRITES_layout.json`, the PNG.
   `python nexclash/nexclash.py recolour <game>_sprites.nex PAINTED.png`
   (add `--layout` if the PNG's name does not lead to the layout). Grey 100,100,100 =
   transparent where the engine allows it. Only the sheet's grey and coloured pixels are read
   (engines with outlines - Dizzy 1 - also grey the paper inside a graphic's bytes); a `WARNING: N
   painted pixels were NOT used` line means paint landed elsewhere (or the layout is older than
   the sheet): tell the user how many and where, in one line.
5. A refusal is the answer: relay its reason (wrong .nex version, wrong sheet, ...). Do not work
   around it.
6. Send the user `<game>_sprites_painted.nex` and `<game>_sprites_painted_colours.json`
   (SendUserFile) with the md5 the command printed and its counts (pixels recoloured, banks).
7. Put the painted PNG in specnext/reference/<folder>/<game>_PAINTING_SPRITES_painted.png,
   commit ("<Game>: Dean's repainted sprite sheet (<date>)" + the md5) and push to main
   (fetch + rebase first).
8. Reply in two or three lines. Making the painting the build default (copy the colours json to
   docs/profiles/<game>_colours.json, rebuild, verify, stamp, PR) is a separate task: offer it,
   do not do it.
