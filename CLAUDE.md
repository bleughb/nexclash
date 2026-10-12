# Agent instructions - nexclash (Spectrum Next colour-clash remover, GPL-3.0-or-later)

`.z80` -> `.nex` with game figures as Next hardware sprites; game logic proven identical by
differential tests against real recordings. Two kinds of session use this file:
- **Add a game** (a user ran `nexclash.py new`): their SESSION.md has the game, snapshot and RZX.
- **Maintain** (the maintainers): toolkit work, releases, merging contributions.

Never put game data (.z80/.rzx/.nex/.tap/...) in this repo or a contribution: the user's files
stay on their machine; the maintainers' reference files live in the private repo bleughb/specnext.

## Setup
`pip install skoolkit --break-system-packages`. sjasmplus only for .asm edits (docs/BRIEFING.md 0;
clone it OUTSIDE the package).

## Read only what the task needs (start: ~150 lines)
- Add a game: this file -> docs/PLAYBOOK.md -> the nearest engine as a template (simplest:
  nexclash/chuckie.py + asm/chuckie_hooks.asm + games/chuckie_egg.md; full-redraw / 128K:
  rainbow; back-buffer composer: wally; Codemasters TID engine: generic builder). Look things up
  in docs/BRIEFING.md (platform, toolkit) and docs/LEARNINGS.md (lessons) by section when a
  question comes up - do not read them end to end.
- Maintain: STATUS.md, then games/<game>.md for the game in hand.
- Read code only in modules you will change.

## Rules (the maintainers' standing rules - contributions are checked against them)
- Style: terse. Results, decisions and files first.
- Verify the original bytes at every patch site (the engine refuses a snapshot that differs).
- Test every change differentially against the RZX: all registers (AF' included unless a
  documented convergence check applies) and all memory outside the never-read draw buffers,
  sprite pixels against the original plot, and no jumps into the middle of a patched instruction.
- Cover paths the RZX does not reach with unit tests: guard edges (converted vs passthrough must
  match the guard), table-full cases, and a negative control. The negative control must use the
  broken patch's own tables (restore only run-time state from captured states).
- Keep changes additive and limited to the new engine (one module, one .asm, one profile, one
  games/ file, a dispatch line in nexclash.py cmd_auto, a verified.json entry).
- Ask the user before decisions that change what they see (which figures become sprites,
  colours, anything left on the ULA).
- Do not change another game's output. Regression check = `python selftest.py --smoke` (rebuilds
  Chuckie Egg only, under a second; needs the private references) after touching shared code
  (nexclash.py, z80tonex, build, verify, nextboot, ...). Do NOT run the full selftest or other
  games' verifications in a game session: the full selftest (~1.5 h) runs only for releases.
  Without the references, say in the contribution note that shared code changed.
- Never run `pkill -f <name>` when your own command line contains <name>.
- 128K start-up tail must end below 0xC000.
- Shell heredocs that write docs: quote the delimiter (`<<'EOF'`).

## End of every task
- Update games/<game>.md (facts, decisions, status, hardware checklist), STATUS.md (one row),
  docs/VERIFICATION.md (results + output MD5s), docs/profiles/verified.json (snapshot MD5 ->
  output MD5s), docs/LEARNINGS.md (GENERAL lessons only). History lives in git.
- Add-a-game session: `python nexclash.py contribute <game> --report <the _report.txt>` and give
  the user the zip + the upload step from CONTRIBUTING.md.
- Release (maintainers): bump VERSION, merge, then publish a release with tag v<VERSION> in the
  GitHub UI: the release workflow builds the zip (tools/make_package.py; version = the tag) and
  attaches it. Missing zip: Actions -> release -> Run workflow with the tag.
  Before a release (not per game): full `python selftest.py` must reproduce every MD5.
- Maintainers: commit on a branch, push, open a PR (message = what changed + verification). New
  game's files go in the private repo: specnext/reference/<game>/ (snapshot, recordings, and the
  built <game>.nex + <game>_sprites.nex), listed in its reference/README.md.
- Reply: results, the .nex files, a short hardware checklist.

## Layout
| Path | What |
|---|---|
| nexclash.py | CLI: patch / new / contribute (users), auto / identify / record / convert / verify / rzx |
| selftest.py | maintainers' acceptance test (needs the private reference files) |
| nexclash/ | toolkit modules + engines (chuckie, dizzy5, dizzy6, rainbow, wally, ...); userflow.py = patch/new/contribute |
| asm/ | hook sources (sjasmplus --zxnext); regenerate the profile hex after any edit |
| docs/profiles/ | per-game profiles (hook hex read by the engines), signatures.json, verified.json |
| games/ | one file per game, named like its folder in specnext/reference/ (facts, decisions, status, open items, checklist); tid_engine.md = shared TID engine facts |
| docs/ | BRIEFING, LEARNINGS, VERIFICATION, PLAYBOOK, RECORDING_CHECKLIST, NEXT_REGISTERS, contribute.json |
| tools/ | make_package.py (release zip), merge_contribution.py, prototypes |
