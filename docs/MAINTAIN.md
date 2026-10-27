# Maintainers (Dean and sessions with push access to bleughb/nexclash)

Read this for: a maintainer's game session at stage 3 or 5 (PR, specnext files), merging a
contribution, a release, lesson consolidation. An add-a-game session by a contributor never needs it.
(Moved out of CLAUDE.md 2026-10-26, unchanged in substance, so every session does not load it.)

## Repos and setup
- Clone bleughb/nexclash and bleughb/specnext side by side; a cloud session attaches both with push
  access first (LEARNINGS 2.6). specnext is large: a sparse checkout of `reference/<game>` is enough
  for one game.
- New game inputs: the attached .z80 + .rzx -> specnext/reference/<game>/; no .z80 but a Fuse RZX ->
  its first snapshot is the .z80 (LEARNINGS 2.4).

## Commit, PR and the private files
- Commit on a branch, push, open a PR (message = what changed + verification). GitHub API details
  (no GraphQL, stacked PRs): LEARNINGS 2.6.
- A new game's files go in the private repo: specnext/reference/<game>/ (snapshot, recordings, the
  built <game>.nex + <game>_sprites.nex, both colour sheets + the painting sheet's _layout.json; the
  colours json, once painted, goes in the record's data list), listed in its reference/README.md
  (edit by grepping for the game's heading; the index is long).
- Every PR runs .github/workflows/checks.yml (learncheck self-check + doccheck, no game data); keep
  "checks / doccheck" a required status check on main (Settings -> Branches).
- Before the merge: `selftest.py --affected --verify --stamp` in a separate worktree (LEARNINGS 2.6) -
  it re-verifies only what else the change reached. Contributors never run it.

## Checks only maintainers run
- Canaries: the records marked "canary": 1 / 2 (stage 1 = Chuckie Egg rebuilt, MD5s, ~1 s; stage 2 =
  Midnight Resistance rebuilt + a 300-frame verify, ~2 min, says whether the TOOL CHAIN or Chuckie
  Egg is at fault; selftest.py --help). Keep both on the latest tools.
- Rainbow Islands (both engines) and Everyone's a Wally (frozen) are EXCLUDED from every automatic
  check (record "excluded"; Dean, 2026-10-13 / 14: too slow, being reworked / superseded): never
  re-verify them unless asked; `--game rainbow` runs one explicitly.
- `--affected` finds every game a change reaches (docs/records keep the hashes of each game's
  dependencies) and rebuilds / re-verifies those; `--full` re-verifies every game (hours) - only when
  verification code changed throughout.
- Without push access (other people's sessions; Dean 2026-10-21) selftest.py probes `git push
  --dry-run` once and refuses --affected / --full / release runs / --game on an existing game with
  exit 3 (NEXCLASH_MAINTAINER=1 only for maintainers working offline). Why: those runs rebuild and
  re-verify every game a change reaches - hours, the maintainers' job before a merge.

## A contribution arrived
`python tools/merge_contribution.py nexclash_contribution_<GAME>.zip` (branch + file list), review
against CLAUDE.md's rules, put a copy of the game in specnext/reference/, then `selftest.py --game
<game> --verify --stamp` and `--affected --verify --stamp`; PR; merge. Plain-diff contributions and
re-deriving their MD5s: LEARNINGS 2.6 (last two items).

## Release
Bump VERSION, merge, then publish a release with tag v<VERSION> in the GitHub UI: the release
workflow builds the zip (tools/make_package.py; version = the tag) and attaches it. Missing zip:
Actions -> release -> Run workflow with the tag. Before a release: `python selftest.py --stamp`
(every game rebuilt + the re-verifications due) must PASS.

## Lesson consolidation (old notes; new lessons are dispositioned at once, docs/LEARNING.md)
Since 2026-10-27 every stage dispositions its own lessons (card / doc / tool / backlog / probe /
local / deferred; learncheck checks them). What is left for maintainers:
- Review card changes in each PR: an incorrect card steers future implementations.
- Promote a candidate card to `active` only with scoped local evidence (a record `pass` result)
  and count cross-game validation in DISTINCT games (`--usage` "games N"), not in uses; a probe to a
  shared command when a second game uses it (tools/probes/README.md).
- `python tools/learncheck.py --usage`: cards that never help or keep being corrected -> revise or
  deprecate.
- Old games still with "## Lesson candidates": migrated when the game is next touched (learncheck
  fails a changed file that still has them). A lesson seen in two or more games goes into LEARNINGS
  / BRIEFING, merged into the existing line on the same subject (grep first), never beside it.
Then `python tools/doccheck.py` must report every file within its budget.
