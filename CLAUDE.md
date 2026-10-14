# Agent instructions - nexclash (Spectrum Next colour-clash remover, GPL-3.0-or-later)

`.z80` -> `.nex` with game figures as Next hardware sprites; game logic proven identical by
differential tests against real recordings. Two kinds of session use this file:
- **Add a game** (a user ran `nexclash.py new`): their SESSION.md has the game, snapshot and RZX.
- **Maintain** (the maintainers): toolkit work, releases, merging contributions.

A maintainer session that adds a game is an add-a-game session for the engine work (engine files
only, `--canary` after shared changes, no rebuilding other games while developing) and a maintainer
session at the end: the game's files go to specnext, then branch + PR, and before the merge
`selftest.py --affected --verify --stamp` (re-verifies every game the change reaches; hours: run it
in a separate worktree, LEARNINGS 2.6). Contributors never run that step; maintainers always do.

Never put game data (.z80/.rzx/.nex/.tap/...) in this repo or a contribution: the user's files
stay on their machine; the maintainers' reference files live in the private repo bleughb/specnext.

## New game: the whole job (the user's prompt only names the game and attaches its files)
1. Setup: clone bleughb/nexclash and bleughb/specnext side by side (maintainers; a contributor has
   the package). Cloud session: attach both repos with push access first (LEARNINGS 2.6).
2. Inputs: the attached .z80 + .rzx -> specnext/reference/<game>/ (maintainers). Folder and
   games/<game>.md named after the game (lower case, underscores). The game may already have
   notes and files (STATUS.md, games/<game>.md, specnext/reference/<game>/): read them first.
   No usable recording (none, or one that desyncs: the tools print a WARNING with the frame) ->
   ask the user for a Fuse recording (docs/RECORDING_CHECKLIST.md) before phase A.
3. Follow docs/PLAYBOOK.md phases A-C. Phase A ends with ONE question to the user, with preview
   frames: which figures become sprites, what stays on the ULA, depth - and the COLOUR SHEETS
   (every game, Dean 2026-10-13/14; PLAYBOOK 3b), built with nexclash/coloursheet.py, 1:1, 8x8
   palette swatches: `<game>_PAINTING_SPRITES.png` (every graphic once, multi-part figures joined;
   the user paints it) and `<game>_REFERENCE_ALL_SPRITES.png` (every figure whole, as the build
   colours it; not read back). The painted sheet becomes docs/profiles/<game>_colours.json, which
   the engine applies per pixel. Never guess
   these; if the prompt already says, confirm with the preview.
4. Long runs (full verify, selftest): `setsid nohup` + poll (LEARNINGS 2.6) - plain `&` dies.
5. While developing: engine files only, `selftest.py --canary` after any shared change.
6. End: "End of every task" below - games/<game>.md, record, views, VERIFICATION, capture
   questions; references + built .nex files + both colour sheets and the painting sheet's
   _layout.json to specnext
   (the colours json, once painted, goes in the record's data list); PRs in both repos (maintainers) or
   `contribute` (contributors); maintainers: `selftest.py --affected --verify --stamp` in a
   separate worktree before the merge (Rainbow Islands stays excluded).
7. Reply: results, the .nex files, a short hardware checklist.

## Setup
`pip install skoolkit --break-system-packages`. sjasmplus (only for .asm edits) is bundled and
pinned: `python tools/asm2profile.py <engine>` assembles and updates the profile (never build
or download another version; tools/sjasmplus/README.md).

## Read only what the task needs (start: ~150 lines)
- Add a game: this file -> docs/PLAYBOOK.md -> the nearest engine as a template (simplest:
  nexclash/chuckie.py + asm/chuckie_hooks.asm + games/chuckie_egg.md; full-redraw / 128K:
  rainbow; back-buffer composer: wally (interrupts off) or midres (interrupts on, all RAM used: hook
  page at slot 5, scratch-buffer redirect, cached sprites); Codemasters TID engine: generic builder). Look things up
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
  broken patch's own tables: restore only the run-time byte ranges of captured states (a copy of
  the whole state area silently puts the good tables back and the control passes - Smash TV).
- Keep changes additive and limited to the new engine (one module, one .asm, one profile, one
  games/ file, a dispatch line in nexclash.py cmd_auto, an evidence record docs/records/<game>.json).
- Ask the user before decisions that change what they see (which figures become sprites,
  colours, anything left on the ULA).
- Do not change another game's output. After touching shared code (anything outside your engine's
  module / .asm / profile) run `python selftest.py --canary` (needs the private references). Two
  stages (Dean, 2026-10-13): stage 1 = Chuckie Egg rebuilt, MD5s, under a second - it validates the
  tool chain. If it fails, stage 2 runs by itself: Midnight Resistance rebuilt + a 300-frame
  differential verify (~1 min; 128K, alt ROM, interrupts on, paged hook RAM, pattern cache) and
  says whether the TOOL CHAIN is broken (fix that first) or the fault is Chuckie Egg's. Any selftest
  run that fails a game runs stage 2 the same way. The canaries are the records marked "canary":
  1 / 2; keep both on the latest tools (never pinned), adapt them in the same PR as a tool change.
  Rainbow Islands is EXCLUDED from every automatic check (record "excluded"; Dean, 2026-10-13: too
  slow, being reworked): never re-verify it unless asked; `--game rainbow` runs it explicitly. Do NOT rebuild or verify other games in a game session: the
  maintainers' `selftest.py --affected` finds every game a change reaches (docs/records keep the
  hashes of each game's dependencies) and rebuilds those. Without the references, say in the
  contribution note that shared code changed.
- Never `pkill -f` / kill by `pgrep -f` pattern: it matches your own shell whenever the pattern
  appears anywhere in that command line (it has, twice). Find the PID, kill the PID.
- The start-up tail must end below 0xC000, 48K too: the stub runs with its own bank 10 at
  0xC000-0xFFFF and the tail's OUT 0x7FFD maps bank 0 back under the PC (El Capitan Trueno: tail
  below SP at 0xFF97, boot never reached the game). choose_tail_addr checks it only for 128K;
  run nextboot.check on plain builds too.
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
- Add-a-game session: `python nexclash.py contribute <game> --report <the _report.txt>` and give
  the user the zip + the upload step from CONTRIBUTING.md.
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
