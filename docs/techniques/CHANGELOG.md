# Nexclash technique standard - changelog

Kept apart from the standard so agents reading it do not load the history (index-first, token
budget). Maintainers read this; agents read the standard.

## v2 -> v3 (Claude review against the repo + GPT-6's re-read of the games)

| v2 | v3 | Why |
|---|---|---|
| A patch contract described the state at routine return | Three checks: **State, Time, Display**, during execution as well as at return | Fireman round 2 (interrupt inside a non-re-entrant plot) and round 1 (half-done plot visible) both passed state-at-return checks |
| Investigation procedure built on Spectrum Analyser (GUI) | Built on nexclash's own commands; external tools optional | survey / scan / preview / cost / isr already do this headless; v2 ran none of its procedure |
| Worked examples: Great Escape + a detection card | Fireman (patch, with rejected fixes) and Atic Atac (detection to design) | The project's own recorded failures show what the standard must prevent; Great Escape kept as an appendix |
| Six initial cards, mostly detection | Eight cards ranked by hardware rounds already lost | Pixel-writer / copy-source detection is largely done by the survey today |
| Each card names its own `requires` predicates | One predicate registry, names shared with survey.json | Otherwise names drift and no matcher can use them |
| New structure checker | Extend tools/doccheck.py | It already checks references and size budgets |
| Silent on re-verification | Records list technique applications | So a shared technique change finds every dependent application |
| - | Tracked unit, visibility timing, approved visual changes, workload-specific performance, failure lookup | GPT-6's re-read: Atic Atac, Commando, Cyclone, Midnight Resistance, Fireman |

## v3 -> v3.1 -> v3.2 (Grok's two reviews)

| Change | Where |
|---|---|
| Index-first retrieval is a hard CLAUDE.md rule | §12, §13 step 4 |
| Optimise cards need a doccheck-checked `Measurements` subsection | §6 |
| `owns` has a fixed, checkable shape | §6 |
| Verify cards state what must hold; engine harnesses still run the checks | §4 |
| Matcher sets predicates only from existing survey.json fields | §5 |
| Two mandatory Display-proof forms | §2 |
| Card lifecycle with `superseded_by` | §6 |
| Smaller first slice; shared code only after a trial | §13 |
| v3.2: stack room is a Time contract item, not an `owns` range | §6 |
| v3.2: the record JSON is the one authoritative place for a game's concrete recipe | §3, §6 |
| v3.2: index.json entry schema | §12 |
| v3.2: `detect.tracked-unit` gets a stated probe and stop rule before it can become `active` | §11 |

## v3.2 -> v3.3 (GPT-6's review of v3.2)

| Change | Where |
|---|---|
| Predicates state `evaluation` (auto / manual / proposed); composition is manual: survey has no composition field and `scan --writers` does not classify XOR | §5, §7 |
| Cards hold verification requirements; records hold results (`not_run` / `pass` / `fail` / `partial`, build, scope, evidence) | §2 |
| Recipe entries are applications with id, card revision, target scope and phase; list order is not run-time order | §3 |
| Resource overlap is a review trigger needing a recorded reason; ranges carry bank / page | §6 |
| Re-verification by every dependent application and coverage, not one representative; doc-only card edits rebuild nothing | §13 |
| Fireman example: "not re-entrant"; eligibility is not selection | §9 |
| Appendix A: Commando already removes sprite pixels behind solid scenery | App. A |
| "One full engine module per session" softened to targeted reads by default, justified exceptions | §12, §13 |

## v3.3 -> v3.4 (consistency pass from Grok and GPT-6; frozen for the pilot)

| Change | Where |
|---|---|
| A recipe is a list of applications with explicit run-time constraints, not an "ordered list of cards" | §8 |
| An application may span several phases (`phases`); `order` is keyed by phase plus `cross` constraints between phases (entry before exit, ISR deferred to the outermost exit) | §3, §6 |
| `owns` example uses the qualified schema: memory as page/bank + offset, alt ROM image identity; overlap compared by physical page + offset | §6 |
| Eligibility rule: every `requires` true, every `rejects` false; unknown or conflicted defers and names the probe | §5 |
| Storage table repaired (two rows had fallen outside it) | §3 |
| "interrupts off: n/a" applies only to interrupt stack headroom; hooks always need room for their own calls and pushes | §6 |
| 100-200 words per candidate is a ceiling; usually ID, fit, blocker, next probe | §12 |
| Pilot runs against a baseline: a comparable existing-workflow game, same measures | §13 |
| Whole-module reading exceptions go in the session's Stage log line, not the game's technical notes | §12 |
| `detect.tracked-unit` stays `candidate` until a second game exercises the row-mask path | §11 |
| Changelog moved out of the standard into this file | - |

## 2026-10-27 - optional external investigation examples

User-requested catalogue additions; the v3.4 schema and pilot workflow stay frozen.
- Three candidate detection cards: drawing parameters, graphics record layout, buffer layout/producer.
- Tracked-unit revision 2 adds Quazatron's composite draw-list example and the parameter probe.
- External Lua sources are pinned and source-reviewed only; addresses/formats remain game-specific.
- No scripts imported, runtime code changed, game applications added or verification results claimed.

## v3.4 -> schema 4 cards + the learning loop (2026-10-27, Cauldron; GPT-6's proposal, Claude's checks)

| Before | After | Why |
|---|---|---|
| Lesson candidates in games/<game>.md, promoted later by a consolidation pass | Every lesson dispositioned in its stage (card / doc / tool / backlog / probe / local / deferred), checked by tools/learncheck.py inside doccheck (docs/LEARNING.md) | Cauldron's lessons, a scratch script and a card warning waited for a pass that does not come |
| Candidate cards with examples only | Schema 4: candidates state Assumptions + Validation gap + a source; `active` needs a record `pass` result | Candidates stay useful before validation; promotion needs local evidence |
| No record of whether a card helped | games/<game>.md "## Technique use"; `learncheck --usage` totals | The catalogue should improve through use, not only grow |
| Investigation scripts in scratch folders | tools/probes/ with invocation, limits, a smoke test in `selftest --tools` | Reproducible, promotable to a shared command |
| New: patch.attribute-shadow (candidate); revised: patch.xor-overlay-keep-ula r2, detect.gameplay-screen-readers r2 | | Cauldron Q8; the overlay's other-writers failure; compiled-BASIC readers, `scan --writers` lists readers |
