# Agent instructions - nexclash (Spectrum Next colour-clash remover, GPL-3.0-or-later)

`.z80` -> `.nex` with game figures as Next hardware sprites; game logic proven identical by
differential tests against real recordings. Two kinds of session use this file:
- **Add a game** (a user ran `nexclash.py new`): their SESSION.md has the game, snapshot and RZX.
- **Maintain** (the maintainers): toolkit work, releases, merging contributions.

A maintainer session that adds a game works like an add-a-game session until the end, then takes
the maintainer steps in "End of every task" (specnext, PRs, the merge check).

Never put game data (.z80/.rzx/.nex/.tap/...) in this repo or a contribution: the user's files
stay on their machine; the maintainers' reference files live in the private repo bleughb/specnext.

## New game: the whole job (the user's prompt only names the game and attaches its files)
1. Setup: clone bleughb/nexclash and bleughb/specnext side by side (maintainers; a contributor has
   the package). Cloud session: attach both repos with push access first (LEARNINGS 2.6).
2. Inputs: the attached .z80 + .rzx -> specnext/reference/<game>/ (maintainers); no .z80 but a Fuse
   RZX -> its first snapshot is the .z80 (LEARNINGS 2.4). Folder and
   games/<game>.md named after the game (lower case, underscores). The game may already have
   notes and files (STATUS.md, games/<game>.md, specnext/reference/<game>/): read them first.
   No usable recording (none, or one that desyncs: the tools print a WARNING with the frame) ->
   ask the user for a Fuse recording (docs/RECORDING_CHECKLIST.md) before phase A.
3. Follow docs/PLAYBOOK.md phases A-C. Phase A ends with ONE question to the user, with preview
   frames and the colour sheets (PLAYBOOK 3b is the one place for the sheet rules): which figures
   become sprites, what stays on the ULA, depth, colours. Never guess these; if the prompt already
   says, confirm with the preview. Every engine with a sheet also gets `recolour` (PLAYBOOK 3b).
4. Long runs (full verify, selftest): `setsid nohup` + poll (LEARNINGS 2.6) - plain `&` dies.
5. While developing: engine files only, `selftest.py --canary` after any shared change. Iterate with
   `--quick 2000` (PLAYBOOK 6); the full `auto` runs ONCE, on the build that goes to the user.
6. End: "End of every task" below. The game's one full verification is `selftest.py --game
   <record> --verify --stamp` on the committed record (PLAYBOOK 6).

## Setup
`pip install -r requirements.txt --break-system-packages` (SkoolKit + Pillow; a fresh cloud
container has neither - the first `python -m nexclash.<engine>` fails without them). sjasmplus (only for .asm edits) is bundled and
pinned: `python tools/asm2profile.py <engine>` assembles and updates the profile (never build
or download another version; tools/sjasmplus/README.md).

## Read only what the task needs (start: this file + PLAYBOOK, ~400 lines)
- Add a game: this file -> docs/PLAYBOOK.md -> the nearest engine as a template (PLAYBOOK 5 has
  the table; simplest: nexclash/chuckie.py + asm/chuckie_hooks.asm + games/chuckie_egg.md). Look things up
  in docs/BRIEFING.md (platform and toolkit facts, C2 = the backlog), docs/LEARNINGS.md (lessons,
  2.1 grouped by question) and docs/TECHNIQUES.md (Next techniques, other projects) by section
  when a question comes up - do not read them end to end.
- Testing in MAME (many users do): `grep -n '\[MAME\]' docs/*.md` (LEARNINGS 2.7).
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
  games/ file, one line in nexclash/engines.py, an evidence record docs/records/<game>.json).
  engines.py is rebuild-only in records.plan() (it only picks the module), so a new game's PR
  re-verifies the new game alone - never put other code there (engines.py docstring).
- Speed: every simulator a verifier builds per event comes from `simpool.machine(Sim, mem, regs,
  slot)` (one slot per simulator alive at once: 'o', 'p', 'c'); building one costs ~3 ms, more than
  the code it runs (Lode Runner verify 112 s -> 35 s, identical output). Profile before guessing:
  `python -m cProfile -s tottime nexclash.py auto ... --quick 300 | head -30`.
- Ask the user before decisions that change what they see (which figures become sprites,
  colours, anything left on the ULA). Phase A settles them in one question; a new one that comes up
  later (phase C, a figure the first recording never showed) gets its own question - never decide it.
- Do not change another game's output. After touching shared code (anything outside your engine's
  module / .asm / profile) run `python selftest.py --canary` (needs the private references; stage 1
  = Chuckie Egg rebuilt, MD5s, ~1 s; only if it fails, stage 2 = Midnight Resistance rebuilt + a
  300-frame verify, ~2 min, says whether the TOOL CHAIN or Chuckie Egg is at fault; selftest.py
  --help). The canaries are the records marked "canary": 1 / 2; keep both on the latest tools.
  Rainbow Islands is EXCLUDED from every automatic check (record "excluded"; Dean, 2026-10-13: too
  slow, being reworked): never re-verify it unless asked; `--game rainbow` runs it explicitly. Do NOT rebuild or verify other games in a game session: the
  maintainers' `selftest.py --affected` finds every game a change reaches (docs/records keep the
  hashes of each game's dependencies) and rebuilds those. Without the references, say in the
  contribution note that shared code changed.
- Never `pkill -f` / kill by `pgrep -f` pattern: it matches your own shell whenever the pattern
  appears anywhere in that command line, even as part of a directory name (it has, twice). List
  with `pgrep -fa` in one command, read it, kill the PID in the next.
- The start-up tail must end below 0xC000, 48K too: the stub runs with its own bank 10 at
  0xC000-0xFFFF and the tail's OUT 0x7FFD maps bank 0 back under the PC (El Capitan Trueno: tail
  below SP at 0xFF97, boot never reached the game). z80tonex.choose_tail_addr refuses such a tail
  (48K and 128K) and nextboot.check catches it; `nexclash.py patch` skips nextboot.check (BRIEFING
  C2 #6), so run it on plain builds.
- Shell heredocs that write docs: quote the delimiter (`<<'EOF'`), or the shell runs every
  backticked example in the text (2026-10-11: it cloned sjasmplus into the repo and ran a pkill).
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
  due) must PASS. `--full` (every game re-verified, hours) only when verification code changed
  throughout.
- Maintainers: commit on a branch, push, open a PR (message = what changed + verification). New
  game's files go in the private repo: specnext/reference/<game>/ (snapshot, recordings, the built
  <game>.nex + <game>_sprites.nex, both colour sheets + the painting sheet's _layout.json; the
  colours json, once painted, goes in the record's data list), listed in its reference/README.md.
  Before the merge: `selftest.py --affected --verify --stamp` in a separate worktree (LEARNINGS
  2.6) - it re-verifies only what else the change reached. Contributors never run it.
- Reply: results, the .nex files, a short hardware checklist.

## Layout
| Path | What |
|---|---|
| nexclash.py | CLI: patch / new / contribute (users), auto / identify / record / convert / verify / rzx, analysis: inspect / scan / isr / cost |
| selftest.py | maintainers' acceptance test, driven by docs/records (needs the private reference files) |
| nexclash/ | toolkit modules + engines (chuckie, commando, dizzy1, dizzy5, dizzy6, jetpac, loderunner, midres, rainbow, renegade, smashtv, wally, wally2; build.py = TID generic); engines.py = auto's engine table; simpool.py = reusable verify simulators; userflow.py = patch/new/contribute; simrun + snapinfo/memscan/isrinfo/drawcost = the analysis commands |
| asm/ | hook sources; after any edit `python tools/asm2profile.py <engine>` (pinned sjasmplus -> profile hex); dizzy5_hooks.asm is the exception: dizzy5.py emits the bytes, selftest (Dizzy V record check) compares them |
| docs/profiles/ | per-game profiles (hook hex read by the engines), signatures.json, verified.json (generated) |
| docs/records/ | one evidence record per game: inputs, dependencies, rebuild / verify recipes, outputs, status, check stamps (nexclash/records.py) |
| games/ | one file per game, named like its folder in specnext/reference/ (facts, decisions, status, open items, checklist); tid_engine.md = shared TID engine facts |
| docs/ | PLAYBOOK (the steps), BRIEFING (facts + backlog C2), LEARNINGS (lessons), TECHNIQUES (Next techniques, other projects), VERIFICATION (results log), RECORDING_CHECKLIST, NEXT_REGISTERS, GUIDE_R3_REVIEW (dev guide r3 checked against these docs), contribute.json |
| tools/ | asm2profile.py (asm -> profile hex, --check --all), sjasmplus/ (pinned assembler), hwtests/ (hardware test .nex sources + build.py), make_package.py (release zip), merge_contribution.py, prototypes |
