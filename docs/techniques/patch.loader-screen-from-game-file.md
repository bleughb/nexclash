# Show the game's own loading screen while the .nxc loader patches

```json
{
  "schema": 4,
  "id": "patch.loader-screen-from-game-file",
  "revision": 1,
  "kind": "patch",
  "title": "Show the game's own loading screen while the .nxc loader patches",
  "question": "Can the player see the game's loading screen from the moment they press ENTER, without the patch carrying a copy of it?",
  "tags": ["nxc", "loader", "loading-screen", "delivery", "tape", "toggle", "trainer"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["setup"],
  "order": {},
  "owns": {},
  "examples": ["castle_master"],
  "sources": ["jattree/nxc PR 9 (branch build-screen, open 2026-11-22): firmware/nexclash.asm scr_first / scr_bank, spec/NXC-FORMAT.md build_screen, tests/test_nexclash_build_screen.py",
              "specnext reference/castle_master/nxc/cm_nxc_make.sh, build/cm_loader_test.py"]
}
```

## Use / do not use
The loader reads 6,912 bytes at a given offset of the player's own game file straight to the screen
when the options are confirmed, then prints "Patching" and one dot per bank built. The patch stores
only the offset: INF1 key `build_screen=<decimal offset below 65536>` (`nxc.py set PATCH GAME
build_screen N`). Use for a tape or snapshot whose screen sits uncompressed in the file. Do not hold
a screen inside the build instead (first try: a 4.4 s wait in setup).

**Assumptions.** The loader on the card has the key (jattree/nxc after PR 9); an older loader ignores
it and nothing changes. The screen is whole and uncompressed at one offset in every accepted file.

**Validation gap.** One game on one Next (the owner, 2026-11-22: "works perfectly"); the pushed
loader build ran on the harness only. A short black blink remains before the game starts (the
BASIC handler's CLS; fixing it needs NXCHAND.BAS).

## Recognise
- A .tap: the SCREEN$ block's data follows its header (Castle Master: offset 513).

## Probe and stop
1. Find the offset: the block of 6,912 bytes + flag and checksum; render it (`scr2png`) and compare
   with the game's screen.
2. `nxc.py make` with the key; run the harness test with the player's real file.

Stop when the harness shows the screen before the first bank and the made file's MD5 is right.

## Contract
- State: the made .nex is unchanged by the key. The loader writes 0x4000-0x5AFF and two system
  variables (the harness reports "the caller's page 10 changed": expected).
- Time: one seek and read at ENTER; a dot costs a few hundred T a bank. Hook stack: n/a (loader);
  interrupt headroom: interrupts off: n/a.
- Display: the build still boots with the game's screen in its image (setup copies it to 0x4000),
  so the picture stays through the start.
- Display: software = return/boundary only; hardware = checklist item "ENTER shows the loading screen at once, dots advance, the game starts"

## Resources owned
None in the game.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| "no change" on hardware | the card's dot/NEXCLASH was never replaced | the file's MD5 on the card | copy the new loader | rebuilding the patch |
| the screen appears late | it was shown after the unlock step | - | read it first, at ENTER | a screen inside the patch |
| a crash from loader code | a call into the part overwritten after the menu, or menu-page code run at the wrong address | harness trace | resident routines only; menu page at its own slot | - |
| "Game file is damaged" on a short file | a checked read | - | a plain read that tolerates a short count | - |
| the patch's MD5 changes each make | a new nonce per make | - | compare the made .nex, not the .nxc | - |

## Verification
Loader harness (`py -3.13`, the `z80` package; 3.15 has no wheel): with the key the screen bytes at
0x4000 = the file's before the first bank; without it, and on the fix-off route, nothing is drawn.
Every toggle and trainer combination is made and its .nex compared (LEARNINGS 2.3). Negative control:
a wrong offset shows the wrong bytes.

## Evidence
- games/castle_master.md M3e (observed on hardware by the owner; cheats unplayed).
- `grep -n 'scr_first\|scr_bank\|key_build_screen' firmware/nexclash.asm` (jattree/nxc, branch build-screen).
