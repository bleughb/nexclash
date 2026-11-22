# Art from the game's own unpacker: build from the player's snapshot, store only where to look

```json
{
  "schema": 4,
  "id": "patch.art-from-own-unpacker",
  "revision": 1,
  "kind": "patch",
  "title": "Art from the game's own unpacker: build from the player's snapshot, store only where to look",
  "question": "The build needs the game's graphics (figures, scenery, pictures) converted ahead of time; how can it get them without storing game data in the repo?",
  "tags": ["build", "graphics", "unpacker", "simulator", "catalogue", "game-data", "levels", "side-input"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["setup"],
  "order": {},
  "owns": {},
  "examples": ["r_type"],
  "sources": ["games/r_type.md Next session (level graphics) and Lessons (art without storing it; the snapshot is the picture)",
              "nexclash/r_type.py, r_type_figures.py, docs/profiles/r_type_catalogue.json.gz (commit c3a40bc)"]
}
```

## Use / do not use
Use when converted art (sprite patterns, Layer 2 scenery, colour maps, a title picture) comes from data the game unpacks at run time, e.g. one packed level at a time. Store a catalogue of where to look (level, address, ink, geometry), never bits or attributes. At build time run the game's own unpacker in the simulator on the player's snapshot, once per level, and read the art from its output; check each unpacked image by a SHA-256 kept in the profile, so a different snapshot is refused rather than half-built. A still picture the snapshot already shows (R-Type: its own screen is the original specification screen) is read from the snapshot the same way.
Do not use when the unpacker needs what the simulator does not give (tape loading, live hardware detection, interrupt timing): capture from the recording, or take a side input checked by MD5 (patch.loading-screen-from-tape).

**Assumptions.** The unpacker is reachable with a known entry and level number and writes only memory the build then reads; its output does not depend on play state.

**Validation gap.** One game (R-Type: ten level images). Paging inside the unpacker (a 7FFD write) must be emulated as the game does it.

## Recognise
The figure corpus or scenery tables in a prototype hold graphics bytes; the game unpacks a level at its start (R-Type: 8F31..8F4E, level data at C4BC).

## Probe and stop
Run the unpacker in the simulator for every level and hash the result; compare the art built from the catalogue with the prototype's stored corpus. Stop if one differs: the catalogue misses geometry or the unpacker run is wrong.

## Contract
- State: build time only; the game's code and data at run time are as without it.
- Time: build time (seconds per level); nothing at run time.
- Display: software = return/boundary only; hardware = checklist item "figures and scenery look as in the original, every level"

## Resources owned
None at run time; at build time a simulator per level.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| hash differs | another version or dump of the game | which level's hash | refuse with the expected MD5 | building anyway |
| corpus differs in a few figures | the catalogue lacks geometry (size, flips, ink) | per-figure diff | add the field | storing those figures' bits |
| unpacker writes unexpected memory | paging (7FFD) not emulated | trace its writes | emulate the paging | - |

## Verification
The ported module rebuilds the prototype's .nex byte for byte (R-Type: a52841b4 = RC1's game build). Hashes of every unpacked image in the profile; the figure corpus rebuilt exactly from catalogue + snapshot.

## Evidence
R-Type c3a40bc: catalogue level / address / ink + geometry only; corpus equal; ten SHA-256 checks; the specnext prototype's hook asm moved unchanged (asm2profile output byte-identical) and the module's build byte-exact with RC1.
