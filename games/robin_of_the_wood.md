# Robin of the Wood (Odin Computer Graphics 1985, 128K) - engine `robin_of_the_wood` (emulator only)

## Next session
Stage: 4 (owner's look)    State: imported into the repo 2026-11-04 (record robin_of_the_wood, stamped); JNext only,
never on a Next. Owner: Enhanced deferred, so the .nxc is not published.
Inputs: specnext/reference/robin_of_the_wood/ (robin_of_the_wood.z80 md5 d2fa7f2e, journey, lifecycle, bishop_coverage,
robin_of_the_wood.scr). Start with: the owner's review of the default and Enhanced sets.

## Import (2026-11-04)
Ported from Jon Attree's .nxc work, 2026-11-04 (pilot clone runs/robin_of_the_wood, base d7abd1c, head 9e104bf). The
owner's build: runs/robin_of_the_wood/out/robin_of_the_wood.nxc e0c97d69 (no version, not published; Enhanced deferred).
Rebuild in today's tree = that build: sprites 1d07361f and Enhanced 8cb14933 = `nxc.py --bare` (default / `--colours
Enhanced`) of e0c97d69 on d2fa7f2e; also plain d6e8b01e, and the two builds without the loading screen (7cedff6b,
425259de). Pinned (record "pin"): `altrom_fill` rom3, the fill it was made with (NextZXOS's ROM3 + the hook bytes); the
new whole-image default gives Enhanced c5da7c77 (opt-in rework: `--altrom-fill whole`).
Moved into the engine: the detector is_robin_of_the_wood (every patch site's original bytes; the pilot was not
registered in engines.py), build_all() and auto(), the loading hold (asm `loading` module, SAVEBIN loading / loadend;
bank 5's own screen put in at build time; the pilot used work/mkload.py), loading_nex(), and verify() (the pilot's
work/enh/verify_enh.py and work/fix2_reference.py as one function, the same checks; the figure inventory now read from
the snapshot's tables, not work/figure_inventory.json). Left in the pilot folder: the PNG captures, the "previous"
negative (needs the 9304cc0e build and its profile), IRQ injection (check_irq_enh.py, 806 placements) and the item
fixtures (check_items_enh.py). No simulated boot: nextboot.check models 48K paging only, and the pilot ran none.
No shared code changed.

## Results (import, 2026-11-04)
selftest --game robin_of_the_wood --verify --stamp: journey 38,618, lifecycle 6,188, bishop_coverage 931 frames (45,737)
IDENTICAL, default and Enhanced; 154,532 hook calls per set; every asset negative forked at a commit DETECTED; unit census
1,088 cases (every graphic, facing, phase) = the reference, seam control 1,088/1,088; 27 of 27 negatives DETECTED on
lifecycle (12 default, 15 Enhanced; Enhanced "outside" is refused by the build's silhouette guard; Enhanced "hollow" left
out: it corrupts the default art the Enhanced paint replaces, UNDETECTED in the pilot too, enh_hollow is its form).

## Hardware checklist
Tape screen, a key or 5 s; Robin, guards, Ent, bishop, witch and creatures solid sprites in their own hues, no white
fringe; arrows and items; room changes and the menu leave no sprite; death, game over, restart; music every frame;
Enhanced from the menu: black hair, skin face, grey-mail guards with red shields; trainer 1.


Standalone engine: `nexclash/robin_of_the_wood.py`; hooks:
`asm/robin_of_the_wood_hooks.asm`; profile: `docs/profiles/robin_of_the_wood.json`.
The specified Odin 128K snapshot has MD5 `d2fa7f2eeb8ccb75c30edbacb432a8b5`.
The standalone build entry refuses other dumps. This engine is not auto-registered.

Round 2 follows the owner's explicit rule: no outline or exterior paper, close
bounded 1–2 pixel seams, fill the resulting interior in the figure's own hue.
Original ink colours and explicitly drawn black detail remain. Six darker fill
shades occupy unused palette entries; guards and Ent select their own sprite
palette banks. There is no Enhanced set. The 73 pointer entries contain 68 unique
graphics; both bitmap and tiled renderers, flying arrows and world-item IDs 0–7
are handled. Menu/HUD/scenery rendering remains ULA.

Evidence lives beside this owned clone in `../work/fix2/`, with the current report
at `../REPORT.md` and 3x original/previous/new comparison `../png/robin_fix2.png`.
Three continuous recordings total 45,737 frames IDENTICAL, all eight hooks run,
90,713 individual figure checks pass, and 36 deliberate corruptions are detected.
The static census covers every table entry, facing and vertical phase plus items
and arrows (1,177 cases). IRQ injection passes 806 placements. Quest equipment
not collected in gameplay is separately fixture-tested; the ending is unplayed.

JNext headless reaches play; apply and actual Browser-loader output are byte-exact
for default and archive trainer-on builds. Measured 3,000-frame speed is 3,090
loops against 3,164 plain (2.34% fewer). Music IRQs remain every 50Hz frame; PCM
sound effects differ. Owner visual approval is pending. Hardware was never run.

## Enhanced colour set (2026-11-04)

Owner's ask: Robin with black hair and a skin-coloured face, and Enhanced colour as an option.
`nexclash/robin_enhanced.py` paints every figure by parts inside the default's exact opaque pixels
(`build(..., enhanced_set=True)`, CLI `--enhanced`); the default build is byte-identical to before
(`1d07361f` with the loading screen). Each figure type has its own sprite palette bank (Robin 3,
guards 4, Ent 5, bishop 6, witch 7, creatures 8; items and arrows keep bank 0); the setup routine
loads 144 entries instead of 48. The build refuses any Enhanced variant whose opaque set differs
from the default's. Robin's head boxes in the tiled fighting/archery frames, the facings and the
bow/crosier boxes were read by eye from the ink (tables in the module). Hands are not separated.
Hair is a near-black brown (73,36,36) with darker strands (36,36,0) so the head shows on black
ground. Round 3 (owner): the face follows a face's contour (robin_head: profile along the drawn front edge,
hair behind, hood collar under the chin; front view framed by hair with a rounded shaded jaw; isolated ink dots
kept as features); no belt line; guards in grey mail with the drawn shield red as one piece (SHIELD_BOX).
Evidence: `../work/enh/`, sheet `../png/robin_enhanced_sheet.png`.

## Lessons
- [local: unregistered engine] The pilot built Robin from a module entry that refused other dumps, never through
  `auto`; importing it meant a detector and auto() so the record's rebuild and verify run as for every engine.
- [local: verifier spread over scripts] The replay, its reference and the inventory were three scripts with
  module globals and monkeypatches; one function keeps the checks and restores what it patches when it returns.

## Technique use
- patch.whole-altrom-image: no help: the build is pinned to the old fill (rom3); the card is its opt-in rework.

## Stage log
- 2026-11-04: imported into the repo (refactor phase 7): rebuild = the owner's e0c97d69, record pinned, full verify stamped.
