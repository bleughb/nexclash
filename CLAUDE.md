# Agent instructions - nexclash (Spectrum Next colour-clash remover, GPL-3.0-or-later)

`.z80` -> `.nex` with game figures as Next hardware sprites; game logic proven identical by
differential tests against real recordings. Three kinds of session use this file:
- **Add a game** (a user ran `nexclash.py new`): their SESSION.md has the game, snapshot and RZX.
- **New game, maintainer** (the prompt names a game and attaches its snapshot + RZX): see
  "New game (maintainer session)" below.
- **Maintain** (the maintainers): toolkit work, releases, merging contributions.

Never put game data (.z80/.rzx/.nex/.tap/...) in this repo or a contribution: the user's files
stay on their machine; the maintainers' reference files live in the private repo bleughb/specnext.

## Setup
`pip install skoolkit --break-system-packages`. sjasmplus (only for .asm edits) is bundled and
pinned: `python tools/asm2profile.py <engine>` assembles and updates the profile (never build
or download another version; tools/sjasmplus/README.md).

## New game (maintainer session)
The short prompt is enough; these are the steps it relies on (all other rules below apply):
1. Clone bleughb/nexclash and bleughb/specnext side by side (`<work>/nexclash`,
   `<work>/specnext`): selftest finds the private references in `../specnext/reference`. Either
   unreachable: stop and say so. Work on a new branch in each.
2. Copy the attached snapshot + RZX into `specnext/reference/<game>/` (`<game>` = lower-case
   snake case, e.g. midnight_resistance; the same name for games/<game>.md and
   docs/records/<game>.json), keep the file names, list them in specnext's reference/README.md.
3. Setup check: `python selftest.py --smoke` and `--tools` PASS before you change anything.
4. Build and verify as for "Add a game" (reading order below, Rules, PLAYBOOK).
5. Finish with "End of every task" plus: `python selftest.py --game <game> --verify --stamp` and
   `python selftest.py --affected` (rebuilds the games your shared-code changes reach, seconds;
   leave the re-verifications it lists as due - they run when the PR is merged); copy the built
   `<game>.nex` + `<game>_sprites.nex` into `specnext/reference/<game>/`; push both branches and
   open a PR in each repo; do not merge, no release. No `contribute` zip (that is for users).

## Read only what the task needs (start: ~150 lines)
- Add a game / new game (maintainer): this file -> docs/PLAYBOOK.md -> the nearest engine as a template (simplest:
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
  games/ file, a dispatch line in nexclash.py cmd_auto, an evidence record docs/records/<game>.json).
- Ask the user before decisions that change what they see (which figures become sprites,
  colours, anything left on the ULA).
- Do not change another game's output. After touching shared code (anything outside your engine's
  module / .asm / profile) run `python selftest.py --smoke` (Chuckie Egg rebuild, under a second;
  needs the private references). Do NOT verify other games in a game session; only a maintainer
  session also runs `selftest.py --affected` (it rebuilds every game a change reaches - docs/records
  keep the hashes of each game's dependencies - and lists the re-verifications due at merge).
  Without the references, say in the contribution note that shared code changed.
- Never `pkill -f` / kill by `pgrep -f` pattern: it matches your own shell whenever the pattern
  appears anywhere in that command line (it has, twice). Find the PID, kill the PID.
- 128K start-up tail must end below 0xC000.
- Shell heredocs that write docs: quote the delimiter (`<<'EOF'`).
- Analysis: use the shared commands (`inspect`, `scan`, `isr`, `cost`; BRIEFING C4) before writing a
  one-off script. If one falls short, IMPROVE IT (keep its existing output lines and arguments, add
  a golden check in selftest.py tools_check, run `python selftest.py --tools`) instead of copying
  it into the engine. Verification harnesses stay per engine (Dean's decision).

## End of every task
- Update games/<game>.md (facts, decisions, status, hardware checklist); the game's evidence
  record docs/records/<game>.json (copy the nearest one: inputs + MD5s (`path` under the private
  reference repo: maintainers fill it), modules, data, rebuild
  recipe with the build decisions from the run's <name>_decisions.json, verify recipe, outputs,
  status row), then `python -m nexclash.records views` - it writes STATUS.md's table,
  VERIFICATION.md's checksum list and verified.json (never edit those by hand; selftest fails
  when they are stale); docs/VERIFICATION.md (your verification results section);
  docs/LEARNINGS.md (GENERAL lessons only). History lives in git.
- Capture (before the commit; nothing learned may stay only in the chat). Answer each, write
  every "yes" to the file named, then say in the reply which lines were added:
  1. Did I need a fact or rule the docs did not give (my own knowledge, a source, trial and
     error)? -> BRIEFING (platform / toolkit fact) or LEARNINGS (lesson).
  2. Did a doc give a rule WITHOUT its reason, or a wrong / incomplete one? -> fix it there,
     with the reason (an unexplained limit gets broken).
  3. Did hardware or an emulator fail where the toolkit passed? -> LEARNINGS lesson + BRIEFING
     A1 "simulator blind spots", and a check in the toolkit if one is possible.
  4. Did a mistake recur that a doc already warns about? -> make that warning sharper.
  5. Something not done or not proven? -> games/<game>.md Open, or BRIEFING C2 if general.
- Add-a-game session (users): `python nexclash.py contribute <game> --report <the _report.txt>` and
  give the user the zip + the upload step from CONTRIBUTING.md. Maintainer session: see "New game".
- Release (maintainers): bump VERSION, merge, then publish a release with tag v<VERSION> in the
  GitHub UI: the release workflow builds the zip (tools/make_package.py; version = the tag) and
  attaches it. Missing zip: Actions -> release -> Run workflow with the tag.
  Before a release: `python selftest.py --stamp` (every game rebuilt + the re-verifications
  due) must PASS. Before merging a PR: `python selftest.py --affected --verify --stamp`.
  `--full` (every game re-verified, ~2.5 h) only when verification code changed throughout.
- Maintainers: commit on a branch, push, open a PR (message = what changed + verification). New
  game's files go in the private repo: specnext/reference/<game>/ (snapshot, recordings, and the
  built <game>.nex + <game>_sprites.nex), listed in its reference/README.md.
- Reply: results, the .nex files, a short hardware checklist.

## Layout
| Path | What |
|---|---|
| nexclash.py | CLI: patch / new / contribute (users), auto / identify / record / convert / verify / rzx, analysis: inspect / scan / isr / cost |
| selftest.py | maintainers' acceptance test, driven by docs/records (needs the private reference files) |
| nexclash/ | toolkit modules + engines (chuckie, dizzy5, dizzy6, rainbow, wally, ...); userflow.py = patch/new/contribute; simrun + snapinfo/memscan/isrinfo/drawcost = the analysis commands |
| asm/ | hook sources; after any edit `python tools/asm2profile.py <engine>` (pinned sjasmplus -> profile hex); dizzy5_hooks.asm is the exception: dizzy5.py emits the bytes, selftest (Dizzy V record check) compares them |
| docs/profiles/ | per-game profiles (hook hex read by the engines), signatures.json, verified.json (generated) |
| docs/records/ | one evidence record per game: inputs, dependencies, rebuild / verify recipes, outputs, status, check stamps (nexclash/records.py) |
| games/ | one file per game, named like its folder in specnext/reference/ (facts, decisions, status, open items, checklist); tid_engine.md = shared TID engine facts |
| docs/ | BRIEFING, LEARNINGS, VERIFICATION, PLAYBOOK, RECORDING_CHECKLIST, NEXT_REGISTERS, contribute.json |
| tools/ | asm2profile.py (asm -> profile hex, --check --all), sjasmplus/ (pinned assembler), make_package.py (release zip), merge_contribution.py, prototypes |
