# Nightshade: rounds 7-11 (2026-11-05; moved from games/nightshade.md, its size budget)

## Round 7 (2026-11-05, owner: hand-painted colours, as for Target: Renegade)
- runs/nightshade/paint_v1/: painting sheets of b8c3754c's design. They are 1:1 PNGs, every graphic once in its
  stored orientation (the game's flip makes the mirrored facings), on (150,150,175), with swatch rows and layout JSONs:
  hero.png (22 graphics), items_bosses.png (16), monsters_effects.png (50). The hero's tunic is a magenta health
  marker. README.md gives the rules and the palette per group. tools/export.py makes the sheets; tools/import.py
  reads them back. The import snaps to swatches within 40 RGB, keeps silhouettes, keeps the health marker, gives one
  colour a code per group and reports overflow. --install puts the source in the clone and keeps the current nxc
  as prev.
- nightshade_paint.py: a painted source (NIGHTSHADE_PAINT_SOURCE, or nightshade_paint_source.json beside it) gives
  the codes and the palette; none installed now. Round trip: the untouched sheets read back to identical codes and
  palette, Enhanced .nex 37f97001 and default 1cf6b276, both byte-identical.

## Round 8 (2026-11-05, Jon's hand-painted sheets)
- Jon painted paint_v1/hero.png and items_bosses.png in place. monsters_effects.png came back unchanged. His sheets are
  backed up in paint_v1/jon_edit/ (SHA256SUMS), with the sheets as sent in jon_edit/sent/.
- His changes after snapping:
  - hero: 42 px. Each front and side frame's 3-pixel buckle became tunic; frame 16's left shoulder band became tunic
    (18 px).
  - Reaper: 80 px. The scythe blade repainted along its drawn edge on 68 and 6A; a wooden haft on 68.
- Brush-flow shades: 93 snapped back to the colour already there. 35 partial strokes resolved by the new mix model
  (the old colour blended with a swatch: the swatch at >= 50 %); 10 under 50 % kept their old colour (9 faint spills
  on black, 1 brown at 8995 (17,18)).
- No silhouette, background-inside, tunic or over-capacity flags. One palette entry is new: the reaper group's code 7
  = wood (0x88). The changes reach every type that shares a changed graphic (paint_v1/jon_edit/carried.txt).
- Installed as nexclash/nightshade_paint_source.json. Enhanced cf51af9f, default 1cf6b276.
- Proof: replay IDENTICAL default and Enhanced on a1, a2, rec1 and rec2; negatives 16 / 16; no-blink 62 / 62. The real
  loader is exact for default, Enhanced and Enhanced + Infinite Lives (44b9dc35). TAP1 --bare is exact.
- Review: paint_v1/jon_edit/review.png. JNext: png/enhanced_jon_v1_strip.png (front, back, three health colours,
  crowned imp, fire demon, slugs, sparkle).
- out/nightshade.nxc f4a79bd3 (prev b8c3754c kept as out/nightshade.prev_b8c3754c.nxc). Fresh sheets of the final
  colours are in paint_v2/, which round-trip to the installed source.

## Round 9 (2026-11-05, Jon's paint_v2/hero.png, saved 03:46)
- Only hero.png changed: 93 real pixels in 12 graphics; 52 shades snapped back. Backed up in paint_v2/jon_edit/.
- Changes:
  - The shoulder band under the hood is now tunic on back views 20, 21, 22 and 23 (matching 16), on 26 (rows 10-11)
    and on 27 (15-17,9). 2F (7,12) is tunic too.
  - 33 brush-flow mixes taken.
- Warnings:
  - Refused: 17 health-marker pixels on mask pixels. These are the left end of the front views' collar line: 1E, 28,
    29, 2A and 2B on row 12, 2F on row 11, and 27's collar row. The tunic is an ink code; a gap code in his health
    colour would need one of the three hero gap codes (belt, collar, face shade), which are all used.
  - 10 under-half strokes kept: 5 faint spills on black, and 5 partial edge strokes in the 21, 23, 26 and 2F bands.
- Installed. Enhanced 11dd0ce6, default 1cf6b276.
- Proof: replay IDENTICAL default and Enhanced on a1, a2, rec1 and rec2; negatives 16 / 16; no-blink 62 / 62. The real
  loader and TAP1 --bare are exact (Enhanced + Infinite Lives 99c319a5).
- out/nightshade.nxc e1cfcc42 (prev f4a79bd3). Review: paint_v2/jon_edit/review.png; strip png/enhanced_jon_v2_strip.png.
  Fresh sheets: paint_v3/.

## Round 10 (2026-11-05, pace pass before publishing; owner approved the look, fb8efe6 / e1cfcc42)
- See runs/nightshade/SPEED.md.
  - Default is at the original pace: quiet +0.44%, busy +0.28%, room +0.78%; before +22.1 / +12.8 / +20.4%.
  - Enhanced is +7.49 / +3.36 / +7.58% (before: busy +18.3%).
- The changes:
  - pace-matched blit hook, with debt from the other hooks;
  - pattern-build speed pass;
  - incoming CPU speed restored, never a fixed 3.5 MHz.
- Proof:
  - replay IDENTICAL in both sets on all four recordings;
  - 17 / 17 negatives (new: forced 3.5 MHz exit);
  - clock matrix 4 speeds x 2 sets pass;
  - no-blink, flicker and 15-minute soak clean;
  - loader and --bare exact.
- out/nightshade.nxc 378b872a, v1.0, PRF1 pace fields set.

## Round 11 (2026-11-05, Enhanced at the original pace; the seed-7 drift)
- See runs/nightshade/SPEED.md.
  - Enhanced (code images, ENHCIM, its own profile docs/profiles/nightshade_enh.json): quiet +0.23%, busy +0.06%,
    room +0.81%, 10 trials each.
  - Default byte-identical (697ee015).
- Enhanced screens are pixel-identical to the approved e1cfcc42's at the same game updates.
- Proof:
  - replay IDENTICAL in both sets;
  - 18 / 18 negatives (new: code image shift ignored);
  - clock matrix pass;
  - no-blink 75 / 75;
  - flicker and soak clean;
  - loader and --bare exact.
- The seed-7 drift is the pace tool's key delivery at frame edges (one 0x7EFE read in update 75 differs), not the build.
- out/nightshade.nxc 5785a638 (prev 378b872a). The asm source for the Enhanced build is generated
  (tools/nightshade_enh_asm.py).

## In this repo (2026-11-06): the painted source without the game's pixels
nexclash/nightshade_paint_source.json keeps the owner's painting as one code per figure pixel (ink or mask) of each
graphic, in the game's data order, plus 17 painted pixels outside a figure's ink and mask by position; the shapes
come from the player's snapshot at build time (nightshade_paint.paint_all). Builds unchanged (697ee015, ebe5cc72).

## Pace, v1.1 (pace audit of 2026-11-08; review build, not published)
Audit (pilot runs/pace-audit-20261108/REPORT-2.md): 1.0 whole +0.02 to +1.90%, quiet up to +2.45%, stretches of 20 updates up to +8.7%, against the rule (Jon, 2026-11-07: within 2% where the original runs steadily, faster fine where it lags, never slower). The debt was right but could only be repaid in the blit's window, 295 lines an update less what the window takes; a busy scene's figure hooks cost up to 560.
- Catch-up: with the debt over 32 lines at a figure hook's exit, the game's own code runs at 7 MHz to the next hook, which credits the gap x 2 (bc_gap, bc_ctl). The blit hook ends it: the update's logic after the blit has no hook for over a frame, and the line count could not credit it (first build: 5% fast). The debt's floor moved from -128 to -1,024 lines, so an over-win is carried and the blit's wait takes it out.
- Sound keeps its clock without paying for it: while catch-up is on, the first bytes of 0xC471 (a tone) and 0xC661 (a tune's note) are a CALL to s_sn; h_snd ends catch-up and gives the speed back, R exact. Off, those are the game's own bytes. A clear ends it too. The replay runs this with a debt forced at every figure hook (the model's beam barely moves, so a real debt never builds): that found the tune playing at 7 MHz.
- Enhanced: its figures in the blit hook can take over a frame, and the line count wrapped unseen, so the debt lost a frame an update in heavy scenes (+12% stretch). The hook now ticks once a figure. That also helps default a little.
- hlib_pace and hlib_speed stay out: the engine's own debt and speed latch predate them and fit its exact R count; hlib_pace would add no way to repay.
- Picture: pattern banks as 1.0. R: compared at every hook, as before, and after the blits; the new sound hook keeps it. Verifier: hook exit speed = 7 MHz in catch-up, else the speed the game runs at; every beeper write at that speed; three new negatives: the JP not set, the sound hook keeping the fast clock, R one off after it.
- Limits: rooms by script, interiors and bosses not reached; JNext's timing only. Before / after: pilot runs/nightshade/pacefix-20261108/NOTES.md.

