# The New Zealand Story (Ocean, 1989, 128K) - NOT imported: PARTIAL (refactor phase 7, 2026-11-04)

## Next session
Stage: import PARTIAL    State: the approved build is not in this repo; no engine, no record, nothing in engines.py.
Approved: New Zealand Story v1.1 .nxc (nexclash-patch patches/, nex_md5 70174ecb, toggle Smooth scrolling), made from
Jon Attree's .nxc work in runs/new_zealand_story (stage 1: work/build.py; colour: colour/build/make.py, gen.py,
hooks.asm; 1.1 speed pass: colour/speedup, its sources hashed in the run clone's probe snapshot nzs_speedup/sources.json).
Start with: the decisions under "Open" (the owner's and the maintainers').

## Why it stops (checked 2026-11-04 against refactor 884d31a)
- Not an engine: three run-folder stages built on each other, none a nexclash module. Stage 1 turns the tape set into
  a multiload .nex (the 36 world blocks raw in banks 12-21, a 12-byte stub in bank 1, a loader hook in bank 11) from a
  start state taken in an emulator (sim/title500.z80); make.py reads that .nex back and adds the colour (tilemap
  scenery generated from the game's own map and char sets by gen.py, painted sprite programs, hooks in alt ROM image 1
  and pages 14-15, 46-80); the speed pass edits the hooks (speedup/work/edit_engine.py). The run clone
  (runs/new_zealand_story/colour/nexclash) holds the 1.1 sources only as a probe snapshot, "not an upstream engine
  registration".
- Inputs: a tape SET. The game is two files, Side A .tap (or .tzx) and Side B .tzx (block 37 is on side B only).
  `nexclash.py auto` / `patch` take one snapshot; a record's inputs are one snapshot plus RZX recordings
  (selftest.stage copies only those two lists, so extra files ride in "recordings"), and no command builds from
  tape files. The .nxc format accepts the set; NexClash itself cannot take it.
- Proof: not RZX. The replays are JSON input logs (sim/rec_*.json) run on the run's own Next simulator
  (colour/tools/simnext.py, 3,004 lines; nzmach.py), 52 replays / 141,000 frames, plus JNext pace and flicker runs.
  A verify(patch, rzx_path) per the contract would be a new verifier, not a port.
- So the rebuild cannot be proven byte for byte in today's tree without writing the engine: per the import brief this
  game stops here.

## Open
- To import: one module that does stage 1 + colour + speed from the two tapes and the start state; a record input
  form for a tape set (or the start state as the snapshot and both tapes staged beside it); the simnext replay as
  this engine's verify, or RZX recordings made for it. Maintainers decide the input form (shared: selftest, records).
- Alt ROM: image 1 is ROM3 + hooks (INTEGRATION.md "Alt ROM"), written over 0x2000-0x3FFF only: check it against the
  whole-image default (REFACTOR item 1) when it is imported.

## Lessons
- [deferred Open: reconsider when the maintainers choose an input form for tape sets] A game whose approved build
  starts from a tape set and an emulator start state has no path into the records (one snapshot + RZX) or `auto`.
- [local: NZS was built as run-folder stages, never as an engine] An import needs the stages folded into one module
  and a verifier on the contract's terms; neither exists for this game.

## Technique use
- patch.whole-altrom-image: no help: not imported; its image 1 is ROM3 + hooks over 0x2000-0x3FFF, to check at the import

## Friction
- reuse: [none: nothing ported]
- retries: [none: nothing run]
- environment: [none: nothing run]
- hand-rolled: [none: nothing ported]
- scratch: [none: no scratch files]
