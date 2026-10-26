# Agent instructions - nexclash (Spectrum Next colour-clash remover, GPL-3.0-or-later)

`.z80` -> `.nex` with game figures as Next hardware sprites; game logic proven identical by
differential tests against real recordings. Sessions: **add a game** (a contributor's SESSION.md, or
a maintainer's prompt) and **maintain** (toolkit, releases, contributions: docs/MAINTAIN.md).
Never put game data (.z80/.rzx/.nex/.tap/...) in this repo or a contribution: the user's files stay
on their machine; the maintainers' reference files live in the private repo bleughb/specnext.

## A game, stage by stage (docs/PLAYBOOK.md; one session per stage)
0. Intake: `python -m nexclash.survey GAME.z80 --rzx R` -> survey.md. Callers the recording never
   reached, or a recording that desyncs (WARNING with the frame) -> ask for a recording first.
1. Design: ONE question - the design defaults + this game's exceptions, preview, plain .nex (3c).
2. Build: engine files only; `--quick 2000` runs; the evidence record written.
3. Prove + deliver: the one full verification, `selftest.py --game <record> --verify --stamp`
   (6a); sprite build + colour sheets (docs/COLOURS.md) + hardware checklist to the user.
4. Hardware + colour rounds: recolour (skill) for paintings; fixes as stage 2-3.
5. Close: "End of every stage" below.
Each stage ends with the "Next session" block in games/<game>.md and the prompt for the next chat
(PLAYBOOK "Sessions"); a continuing session starts from that block, never from chat history, then
refreshes its knowledge from main at a safe boundary (docs/LEARNING.md 1: fetch, read the incoming
changes, merge). The game may already have notes and files (games/<game>.md, STATUS.md): read them
first. Names: folder and games/<game>.md after the game, lower case, underscores.

## Setup
`pip install -r requirements.txt --break-system-packages` (SkoolKit + Pillow; a fresh cloud
container has neither). sjasmplus (only for .asm edits) is bundled and pinned: `python
tools/asm2profile.py <engine>` assembles and updates the profile (never build or download another
version; tools/sjasmplus/README.md). Maintainers: repos and private files in docs/MAINTAIN.md.

## Tokens: read, write and print as little as the task needs
- Read: this file, PLAYBOOK intro + your stage, games/<game>.md, survey.md. Look things up in
  BRIEFING (platform + toolkit facts, C2 = backlog), LEARNINGS (lessons), TECHNIQUES (Next techniques):
  `grep -n '^#' FILE` is the map, then grep the subject and Read +-30 lines - never end to end.
  MAME: `grep -n '\[MAME\]' docs/*.md`.
- Patch plan first (PLAYBOOK 2): docs/techniques/index.json (whole, ~1.3K tokens), then at most 3
  cards, then only the functions a card names (`grep -n '^def \|^class ' FILE`); a whole engine
  module needs a reason in the Stage log line. Engine files: docs/ENGINE_CONTRACT.md. Read code
  only in modules you will change; do not re-read a file you just wrote.
- Write: change existing files with Edit, never rewrite a large file whole; write a new engine in
  stages (sites, hooks, verify, unit tests), each checked before the next.
- Print: a command that may print more than ~50 lines: `CMD 2>&1 | tee run.log | tail -30; grep -E
  'WARNING|FAILED|!' run.log | head -20` (tail alone drops the early desync WARNING; the pipe hides
  the exit code). Reports: `grep -E 'Verify|Unit|Result|!'`. Disassemble only flagged routines.
- Replies: never re-summarize earlier turns or paste results already in files; say what changed.
- Long runs: `setsid nohup` + one `sleep 540; tail -3 LOG` per poll, call timeout 10 min (LEARNINGS
  2.6) - plain `&` dies, faster polls resend the conversation for nothing. Where the harness
  blocks a foreground sleep (claude.ai, 2026-10-26), wait instead with ONE background command
  `until grep -q 'DONE-LINE\|Traceback' LOG; do sleep 20; done` (a single completion notice).
- No subagents unless the user asks: each starts cold and re-reads the docs.

## Rules (contributions are checked against them)
- Style: terse. Results, decisions and files first.
- Verify the original bytes at every patch site (the engine refuses a snapshot that differs).
- Z80N instructions may always be used in hooks; a verifier gets them from `z80n.install(sim,
  nextreg)` (all 29) - never write another per-engine copy.
- Test every change differentially against the RZX (what to compare: PLAYBOOK 6): all registers,
  all memory outside the never-read draw buffers, sprite pixels against the original plot, no jumps
  into the middle of a patched instruction.
- Cover paths the RZX does not reach with unit tests: guard edges, table-full cases, and a negative
  control that uses the broken patch's own tables - restore only the run-time byte ranges of captured
  states (a copy of the whole state area puts the good tables back and the control passes: Smash TV).
- Keep changes additive and limited to the new engine: one module, one .asm, one profile, one
  games/ file, one line in nexclash/engines.py, one record docs/records/<game>.json. engines.py is
  rebuild-only (it only picks the module), so a new game re-verifies alone - no other code there.
- Speed: every simulator a verifier builds per event comes from `simpool.machine(Sim, mem, regs,
  slot)` (~3 ms each, more than the code it runs). Profile before guessing: `python -m cProfile -s
  tottime nexclash.py auto ... --quick 300 | head -30`.
- Ask the user before decisions that change what they see (figures, colours, anything left on the
  ULA): the stage-1 question; a new one later (a figure the first recording never showed) gets its
  own question - never decide it.
- Do not change another game's output. After touching shared code (anything outside your engine's
  module / .asm / profile) run `python selftest.py --canary`; never rebuild or verify other games
  (the maintainers' `--affected` does, docs/MAINTAIN.md). Without the references, say in the
  contribution note that shared code changed. Without push access selftest.py refuses the other runs.
- Never `pkill -f` / kill by `pgrep -f` pattern (it matches your own shell): `pgrep -fa`, read, kill
  the PID in the next command. No `pgrep -f` in ANY loop condition (`until ... && ! pgrep -f X`
  too: the loop's own command line contains X, never ends; recurred at stage 1): `kill -0 PID` or the log.
- The start-up tail must end below 0xC000, 48K too (the stub's bank 10 sits at 0xC000-0xFFFF;
  Trueno never booted). z80tonex.choose_tail_addr refuses such a tail; nextboot.check catches it.
- Shell heredocs that write docs: quote the delimiter (`<<'EOF'`), or the shell runs every
  backticked example in the text (it once cloned sjasmplus into the repo and ran a pkill).
- Analysis: the shared commands first (`survey`, `inspect`, `scan`, `isr`, `cost`, `preview`;
  BRIEFING C4). One falls short -> IMPROVE IT (keep its output lines and arguments, add a golden
  check in selftest.py tools_check, `python selftest.py --tools`), do not copy it into the engine.
  Verification harnesses stay per engine (Dean's decision).

## End of every stage
- games/<game>.md: facts, decisions, status, results (counters, MD5s), hardware checklist, Stage
  log line, Next session block. docs/VERIFICATION.md is no longer appended to (2026-10-26): the
  results live in games/<game>.md and the record.
- At stage 2-3: the evidence record docs/records/<game>.json (PLAYBOOK 7), then `python -m
  nexclash.records views` (writes STATUS.md's table, VERIFICATION.md's checksum list, verified.json;
  never edit those by hand - selftest fails when they are stale).
- Learning loop (docs/LEARNING.md; a stage is not complete without it): every finding a line in
  games/<game>.md "## Lessons" with its disposition tag (card / doc / tool / backlog / probe / local
  / deferred), each acted on now: card or doc amended, useful scripts kept in tools/probes/, wrong
  or reasonless rules fixed in place, recurring mistakes' warnings sharpened, hardware-only failures
  in BRIEFING A1. "## Technique use": which cards / probes helped. Record matches the build. Grep
  before adding a line anywhere; sharpen the existing one. Say in the reply what you wrote.
- `python tools/doccheck.py` (references, budgets, cards, learncheck) must PASS.
- Contributors: `python nexclash.py contribute <game> --report <the _report.txt>`, give the user the
  zip + the upload step from CONTRIBUTING.md. Maintainers: PR + private files (docs/MAINTAIN.md).
- Reply: results, the .nex files, a short hardware checklist, the next session's prompt.

## Layout
| Path | What |
|---|---|
| nexclash.py | CLI: patch / new / contribute (users), auto / identify / record / convert / verify / recolour / rzx, analysis: inspect / scan / isr / cost / preview |
| selftest.py | maintainers' acceptance test, driven by docs/records (needs the private reference files) |
| nexclash/ | toolkit modules + engines (one module per engine: nexclash/engines.py; games: STATUS.md; build.py = TID generic); simpool.py = reusable verify simulators; userflow.py = patch/new/contribute; survey (`python -m nexclash.survey`) + simrun + snapinfo/memscan/isrinfo/drawcost = the analysis commands |
| asm/ | hook sources; after any edit `python tools/asm2profile.py <engine>`; dizzy5_hooks.asm is the exception: dizzy5.py emits the bytes, selftest compares them |
| docs/profiles/ | per-game profiles (hook hex read by the engines), signatures.json, verified.json (generated) |
| docs/records/ | one evidence record per game: inputs, dependencies, rebuild / verify recipes, outputs, status, check stamps (nexclash/records.py) |
| games/ | one file per game, named like its folder in specnext/reference/ (facts, decisions, status, results, open items, checklist, lesson candidates, Next session); tid_engine.md = shared TID facts |
| docs/ | LEARNING (learning loop), techniques/ (STANDARD, cards, index.json), PLAYBOOK (the stages), ENGINE_CONTRACT (what an engine provides; doccheck-checked), COLOURS (colour sheets, recolour), MAINTAIN (maintainers), BRIEFING (facts + backlog C2), LEARNINGS (lessons), TECHNIQUES (Next techniques, other projects), VERIFICATION (results log to 2026-10-25 + generated checksums), RECORDING_CHECKLIST, NEXT_REGISTERS, GUIDE_R3_REVIEW, contribute.json |
| tools/ | doccheck.py (+ learncheck.py), probes/ (kept probes), asm2profile.py, sjasmplus/ (pinned assembler), hwtests/, make_package.py (release zip), merge_contribution.py, prototypes |
