# The learning loop (every stage; CLAUDE.md "End of every stage")

**At each stage, incorporate or disposition reusable learning and keep the record consistent.**
`python tools/learncheck.py` (via doccheck and PR CI) checks structure; the session checks substance.
Capture lessons and reusable scripts before the container disappears.

## 1. Source refresh and verification freeze
Git only: refresh when starting development or before final verification, with `git status` clean
and no verification running. Read the Next session block first. Do not merge at every stage.
Then `git fetch origin main`, `git log --oneline HEAD..origin/main`, `git diff --stat HEAD...origin/main`;
read what changed in docs/techniques and in the docs your stage uses; `git merge origin/main`.
`python -m nexclash.records deps <game>` says what the game's stamp depends on: a merge that touches
none of those files (docs, cards) invalidates nothing. If the merge must wait (a verification is
running, a conflict with work in flight), say in the Stage log line why and which main commit the
session's knowledge is from.
Freeze source and dependencies from the stamping run through delivery. Record source commit,
output hashes and stamp in the handoff. A required merge/fix changing those dependencies supersedes
the proof: use records plan and rerun the affected verification. Package users preserve the entire
modified package and manifest; do not run Git refresh or commit commands.

## 2. Capture (as you go)
games/<game>.md "## Lessons": one bullet per finding - a new fact, a failed approach, a probe that
worked, a coverage limit - in one or two lines (observation, evidence, limit), starting with its
disposition tag. Mark observed / inferred / demonstrated. Only "- " bullets (continuation lines
indented) count; any other line in the section fails, so nothing is silently skipped. A stage with
no reusable finding says so: `- [none: <why>]` (e.g. "hardware report only, nothing new"). A script that answered a question another
game may ask goes to tools/probes/ (its README) the same day, not to a scratch folder.

## 2b. Friction sweep (stage end; learncheck)
games/<game>.md "## Friction": five bullets, each `- <key>: [tag] <answer>` (tags as below,
`[none: why]` allowed): `reuse` (written from scratch, reusable by another game?), `retries` (a
toolkit / verifier mistake that cost more than one attempt), `environment` (a git / harness /
network workaround), `hand-rolled` (a missing command done by hand), `scratch` (scratchpad
scripts: each kept in tools/probes/ or dropped, why). Toolkit lessons count, not only game facts.
A `[local]` lesson naming shared code (simpool, rzx, z80tonex, ...) fails: it is a tool / doc / backlog.

## 3. Dispositions (one or more per lesson, each must resolve)
| Tag | Meaning | learncheck checks |
|---|---|---|
| `[card <id> §<section>]` | incorporated into a technique card (amended, or a new candidate) | card id, section heading |
| `[doc BRIEFING A1]` / `[doc docs/<X>.md §Heading]` / `[doc CLAUDE.md §Heading]` | a platform / toolkit fact in a shared doc | section resolves |
| `[tool <ref>]` | implemented in shared code now | `nexclash.py <cmd>`, `nexclash.<module>`, `<module>.<function>` or a path resolves |
| `[backlog C2 #N]` | a shared capability requested, not built | BRIEFING C2 item exists |
| `[probe tools/probes/<x>.py]` | kept as a reproducible probe | file, README row, docstring fields |
| `[local: <reason>]` | true for this game only | a reason |
| `[deferred C2 #N\|Open: reconsider when <condition>]` | unresolved; evidence kept there | target exists, a condition |
| `[none: <why>]` | this stage found nothing reusable (stated, not skipped) | a reason |

Docs and cards change at once (they rebuild nothing). Executable changes keep their gates: a probe
first, tested in `selftest --tools`; promotion to a shared command when a second game uses it
(tools/probes/README.md); shared runtime code: `selftest --canary`, the maintainers' `--affected`.
A game-specific fix is never assumed to generalise: `[local: ...]` is a valid outcome.

## 4. Cards (docs/techniques/STANDARD.md)
A new or revised card is schema 4. A candidate has a source (`examples` or `sources`, external
allowed), a `**Assumptions.**` line and a `**Validation gap.**` line. `active` needs scoped local
evidence: a record whose `results` has `pass` for an application of the card. Schema-3 cards are
migrated when next revised. Card changes are reviewed in the PR (a wrong card steers future work):
the PR says what changed and why. Then `python tools/techindex.py` regenerates the index.

## 5. Technique use (does the catalogue help?)
games/<game>.md "## Technique use": one line per card or probe consulted,
`- <card id | tools/probes/<x>.py>: used | helped | no help: <why> | corrected: <what>`.
`python tools/learncheck.py --usage` totals them per card: DISTINCT games and individual uses apart
(two lines from one game are one game - cross-game validation needs distinct games). A card that
never helps, or keeps being corrected, is the next one to revise or deprecate.

## 6. Scope
Enforced on game files with "## Lessons", and on every record's game file changed against
origin/main: it needs "## Lessons" + "## Technique use" and a lesson added or changed since the merge
base (or a `[none: <why>]` line). One that still has the old "## Lesson candidates" fails: migrate it
when revisited. Untouched old files stay as they are (MAINTAIN "Lesson consolidation" handles them).
Under CI a missing merge base fails (the workflow fetches the full history).

## 7. Record reconciliation
The record's `techniques` lists every card the build applies (application, target, `owns`) and its
`results` what was proven (status, scope, evidence); the `Techniques:` line in games/<game>.md
names the same ids (techindex checks the match). Update both when the implementation changes.
