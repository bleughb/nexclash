# Loading screen from the tape: a side input for a .z80 game, shown by the .nxc at ENTER

```json
{
  "schema": 4,
  "id": "patch.loading-screen-from-tape",
  "revision": 1,
  "kind": "patch",
  "title": "Loading screen from the tape: a side input for a .z80 game, shown by the .nxc at ENTER",
  "question": "The player's .z80 holds no loading screen; how does the build, and its .nxc, show the original one?",
  "tags": ["loading-screen", "scr", "tape", "side-input", "nxc", "build_screen", "delivery"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["setup"],
  "order": {},
  "owns": {},
  "examples": ["r_type"],
  "sources": ["games/r_type.md Lessons (loading screen, tape as a target, card test 2026-11-22)",
              "jattree/nxc PR 9: INF1 build_screen (an offset, or nex) and the key made during the menu"]
}
```

## Use / do not use
Use for a game whose loading screen is not in the snapshot. First check: search the .z80's RAM for the screen in 64-byte pieces (R-Type: 0 of 107 found; the game had drawn over it). Then take the tape's SCREEN$ block as a side input beside the snapshot, checked by MD5, never in this repo (game data). The build carries it as the NEX loading screen (the `_loading` variant). For the .nxc: `nxc.py set GAME.nxc GAME.z80 build_screen nex` has the NXC loader decode the patch's own loading screen at ENTER, after the patch's keyed check, for any game file kind. It needs a ULA screen alone and the NEXCLASH loader from nxc PR 9 on the card. `build_screen=N` (a byte offset) is for a tape target that holds the screen as it is.
Do not try a tape as a second .nxc target when its loader transforms data: `nxc.py add-dump` takes another dump only if it rebuilds the same banks (a tape: at most 8 KB not on it). R-Type's tape was refused (79,829 bytes): its level blocks load at C4AE and the game stores them converted in banks 1, 3, 4, 6, 7.

**Assumptions.** The tape's screen is the one the owner wants; the .nxc's loading screen is a plain ULA screen (NEX header byte 10 = 2).

**Validation gap.** One game on hardware (R-Type, 2026-11-22). nexclash auto does not yet set build_screen (games/r_type.md Open).

## Recognise
A `_loading` build is wanted but the snapshot's screen is the game's own (a title or spec screen); the .nxc menu shows no picture at ENTER.

## Probe and stop
The 64-byte search above; MD5 of the SCREEN$ block (tape offset of its data); `nxc.py set ... build_screen nex` refuses a screen that is not a ULA screen alone: stop and keep the menu's Patching line.

## Contract
- State: none at run time; the game's RAM is untouched (the NEX writes the screen before the game starts).
- Time: the loader's patch check (R-Type 577 KB: 2.7 s at 28 MHz) is made while the menu waits, so the screen is up at once after a few seconds on the menu.
- Display: software = return/boundary only; hardware = checklist item "loading screen at ENTER with Patching and 24 dots, then the game"

## Resources owned
None in the game; the NXC loader's own page during its menu.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| noise instead of the screen at ENTER | an older NEXCLASH on the card reads `nex` as offset 0 (the .z80's first 6,912 bytes) | which /dot/NEXCLASH | copy NEXCLASH with the .nxc | - |
| no picture, Patching... only | build_screen unset or not a ULA screen | `nxc.py` info | set it | - |
| add-dump refused | the tape's data is converted at load | bytes not on the tape | ship the .z80 only | a tape target |

## Verification
On the harness the screen at unlock equals the side input except the Patching line, and the .nex built is byte-exact without the key; on the Next, the checklist item.

## Evidence
R-Type: r_type_loading.scr (tape block, MD5-checked), `_loading` builds 727b938f / 52a9b013; nxc PR 9 tested on the owner's Next 2026-11-22 after copying both files.
