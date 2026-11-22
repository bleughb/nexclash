# Optional front end in free banks: an intro the .nxc can carry, trainers intact

```json
{
  "schema": 4,
  "id": "patch.optional-front-end-in-free-banks",
  "revision": 1,
  "kind": "patch",
  "title": "Optional front end in free banks: an intro the .nxc can carry, trainers intact",
  "question": "Can an extra program before the game (an intro, a showpiece) be a .nxc option, with the game's trainers still working?",
  "tags": ["intro", "front-end", "nxc", "toggle", "trainers", "free-banks", "stub", "nex-layout"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["setup"],
  "order": {"cross": ["the front end runs before the stub's start of the game and gives the machine back as the stub would leave it"]},
  "owns": {"next_pages": "param"},
  "examples": ["r_type"],
  "sources": ["games/r_type.md Next session and Lessons (intro as an .nxc option, 2026-11-22)",
              "nexclash/r_type_intro.py, asm/r_type_intro.asm (commit fd2038b)"]
}
```

## Use / do not use
Use when the owner wants an optional program before the game (an animated title, a 3D showpiece) and the build ships as a .nxc. A .nxc rebuilds and pokes trainers into the banks its NEX header lists; data past the banks is not carried, and a front end that loads the game's banks from its open file hides them from the trainers. So: put the front end in NEX banks the game never maps, in the same build; the option only changes the stub's start to jump to it; it puts back the replaced stub bytes and starts the game as the stub would. Both builds need the same bank list and length (nxc toggles).
Do not use when the free banks do not fit the RAM target (2 MB Next: banks up to 111), or when the front end must change game banks (then it is part of the game build, not an option).

**Assumptions.** The game never maps the chosen banks during play (all levels, attract, game over); the front end needs no bank the game's start state uses.

**Validation gap.** One game (R-Type: code bank 8, 90 pages of pictures, 289 ship pictures). Emulator flow checks; the owner's Next ran the .nxc build, but the option-on run is not recorded as a scoped pass.

## Recognise
A front end built as a separate NEX that reads the game from its file; "no .nxc yet" because data lies past the NEX banks; .nxc trainers that never take effect behind an intro.

## Probe and stop
List the pages the game maps over a whole run (MMU / 7FFD writes, later levels included) and the pages its NEX header lists: free = neither. Size the front end against them; stop if it does not fit the RAM target.

## Contract
- State: at the jump into the game every game bank equals the option-off build (byte compare); the stub's replaced bytes are back; Next registers the front end changed (MMU, speed, layers, NR 0x8E) restored.
- Time: before the game only; nothing runs once the game starts.
- Display: software = return/boundary only; hardware = checklist item "option on: front end, then the game; option off: the game as before"

## Resources owned
NEX banks no game state uses (R-Type: code bank 8, PICTURE_PAGES); the stub bytes at the jump.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| trainers do nothing with the intro | game banks loaded from the file by the front end | where the trainer's bank comes from | front end in free banks of the same build | trainers patched into the front end's loader |
| .nxc toggle refused | option builds differ in length | compare bank lists | same banks in both builds | - |
| crash or wrong start after the front end | stub bytes or registers not restored | compare the machine at the game's first instruction | restore everything the stub sets | - |
| corruption in a later level | a "free" bank is used late | page-use scan over all levels | other banks | - |

## Verification
Game pages at the jump into the game = option-off build; both builds reach the title; nxc.py checks every toggle and trainer combination (LEARNINGS 2.4).

## Evidence
R-Type fd2038b: the "Advanced intro screen" toggle; auto writes both builds and the .nxc with 4 TipShop trainers. The earlier separate intro NEX (RC1) could not be a .nxc and blocked the trainers.
