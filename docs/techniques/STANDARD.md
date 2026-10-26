# Nexclash technique documentation standard - v3.4

26 October 2026. **Frozen for the pilot** (section 13): changes only from what the pilot shows.
Specification only: no code changed, no game re-verified. Every game fact below is cited to
games/<game>.md and was checked there.

## 0. Status and history

v2 (GPT-6 Astra) proposed technique cards. v3 grounded them in the repo: State / Time / Display
checks, nexclash commands instead of a GUI analyser, Fireman and Atic Atac as worked examples, one
predicate registry. v3.1-v3.2 (Grok) made retrieval index-first and the schemas checkable. v3.3
(GPT-6) separated tool capability from proposals and requirements from results, and introduced
applications. v3.4 is a consistency pass by both. Full history with reasons:
docs/techniques/CHANGELOG.md (maintainers; agents need not read it).

## 1. Decision

Document a technique as a reusable decision procedure:
**question -> observations -> probe -> conclusion -> permitted action -> verification.**
A card must let the next agent decide without rereading another game's module.

- Exact-game detection (engines.py `is_<engine>`) stays as the fast path for supported builds.
- An unknown game is investigated per routine and per figure class, never per game: one game
  can mix drawing systems (Match Day: an overwriting plotter beside its normal ones).
- No engine name is needed before investigating behaviour.
- The catalogue must be able to answer "no suitable technique yet". A failed match never forces a
  familiar template.

## 2. The three checks every patch contract covers

| Check | Covers | Verified today | Gap |
|---|---|---|---|
| **State** | registers, memory, gameplay behaviour; every read the game makes sees the original's value | per-hook differential tests in every engine (PLAYBOOK 6) | - |
| **Time** | interrupts, re-entrancy, frame cost, update order; can added hook time make two operations overlap that never did? | interrupt safety per hook instruction (Commando, Midnight Resistance); interrupt injection (Fireman only) | no shared hook-cost tool (BRIEFING C2 #1); injection is per engine |
| **Display** | what is visible during the routine as well as after it: flicker, intermediate states, occlusion, intentional changes | sprite pixels against the model at return; old + new image covered from plot entry to exit (Fireman only) | no shared check that nothing visible changes wrongly while a hook runs |

A card states all three. "Not applicable" is allowed with one line of reason. The gaps go to
BRIEFING C2 as toolkit work (section 11), otherwise cards promise checks nothing runs.

**Mandatory Display wording.** Until the shared Display check exists, every patch card's Display
proof uses exactly one of these forms, and doccheck rejects a card without one:
- `Display: software = return/boundary only; hardware = checklist item "<item>"`
- `Display: software = entry-to-exit coverage (<engine>.<function>); hardware = checklist item "<item>"`
An agent never reports a Display proof it did not run.

**Requirements vs results.** A card states what a technique *requires* to be checked. It never
records that a check passed. Results live in the game's record, per application:

```json
"results": [{"application": "fireman.plot.isr-deferral", "check": "time.interrupt-injection",
  "status": "pass", "build": "53f2665e", "scope": "20 injection points in 2 main-loop plots",
  "evidence": "games/incredible_shrinking_fireman-add-OPUS.md#hardware-round-2"}]
```
`status` is one of `not_run`, `pass`, `fail`, `partial`. A hardware checklist item named in a card
means a test is specified, not done; it becomes `pass` only when the user reports it. Likewise
"every read the game makes sees the original's value" is the guarantee to meet; a record states the
coverage actually tested (which recording, which frames, which unit cases).

## 3. Storage

| Where | What |
|---|---|
| `docs/techniques/<id>.md` | one card, 300-600 words: a JSON metadata block + the fixed template (section 6). Size budget enforced by doccheck |
| `docs/techniques/predicates.json` | the predicate registry (section 5). Hand-maintained, the one place a predicate is defined |
| `docs/techniques/index.json` | generated from card metadata, never edited by hand |
| `games/<game>.md` | application: addresses, decisions, evidence, and the reasoning for each card choice. A `Techniques:` line names the card IDs and points to the record; it never repeats `owns` values |
| `docs/records/<game>.json` | build and verification authority, and the **one authoritative recipe**: `"techniques": [{"application", "id", "revision", "target", "phases", "params", "owns"}]`, plus `results` (§2). doccheck fails if the games/ line lists IDs the record does not |
| `specnext/reference/<game>/` | raw traces, recordings, images, logs (private) |
| TECHNIQUES.md, LEARNINGS.md | stay; cards link to their lines. Material moves only when a card replaces it |

A technique can apply several times in one game, so each recipe entry is an **application**:
- `application`: a short unique name (`atic_atac.figures.xor-shadow`)
- `revision`: the card revision it was written against
- `target`: the routines or figure class it covers (e.g. plot entries 0x9F4A / 0x9F56 / 0x9FCA;
  or "pocket icons: excluded")
- `phases`: where it runs, one or more of `setup`, `entry`, `exit`, `commit`, `isr`, `clear`,
  `menu` (`commit` = a hook at the game's frame or buffer-copy point; detect applications use
  `[]`: they produce observations, not run-time code). An
  application can span several (Fireman's ISR deferral: `entry` counts depth, `isr` defers,
  `exit` runs the deferred handler).

List order is the order applications were designed in, **not** a run-time sequence: entry hooks,
exit hooks and the interrupt handler are conditional paths. Run-time constraints are explicit, in
the card's `order` (§6): within a phase, and across phases.

Capture and disposition in the same stage (docs/LEARNING.md, since 2026-10-27): a lesson in
games/<game>.md "## Lessons" carries its disposition (an amended or new card, a doc, a tool, a
backlog item, a kept probe, local, deferred). It becomes a card when it is reusable or prevents a
costly repeat. A different address is an application, not a new card. New / revised cards are
schema 4: a candidate states `**Assumptions.**` and `**Validation gap.**`; `active` needs scoped
local evidence (a record `pass` result).

## 4. Card kinds and observation axes

Four kinds:

| Kind | Output | Does not establish |
|---|---|---|
| detect | a scoped observation | that a patch is safe |
| patch | a transformation with preconditions and preserved invariants | that every application passes |
| optimise | a semantics-preserving alternative with measured, workload-specific cost | a universal speed-up |
| verify | a check with stated coverage and a negative control | behaviour beyond that coverage |

A verify card says **what must be true** and how a broken build is caught. It does not replace the
harness: ENGINE_CONTRACT's per-engine `verify` / `unit_tests` still run the checks until shared
technique code exists (section 13, step 8).

Rendering behaviour is recorded as observations on these axes:

- **target:** ULA bitmap, attributes, back buffer, Layer 2, mixed
- **composition:** XOR, masked AND/OR, overwrite, tile redraw, OR-only, mixed, unknown
- **lifecycle:** paired draw/erase, delta update, full redraw, unknown
- **tracked unit:** pixel, row, partial image, whole figure, composite object (several draws), unknown
- **object identity:** table slot, pointer, caller return address, register pushed, reconstructed, unknown
- **screen dependency:** gameplay reader observed, rendering-only readers within stated scope, unknown
- **execution:** main loop, ISR, both, unknown; re-entrant yes / no / unknown
- **hazards:** self-modification, bank switching, alternate entries past the hooked entry, overlap, no frame sync, unknown

Every observation carries **basis** (observed / inferred / unknown / conflicted) and **scope**
(which recording, which frames, static or run). Banked code records bank + CPU address; loader
snapshots record the phase (an inert relocated copy matches signatures too: BRIEFING B2b).

## 5. Predicates and matching

`predicates.json` defines each predicate once:

```json
{
  "render.composition.xor": {
    "means": "every write by the routine to the target is XOR of the old byte",
    "true_when": "every screen-writing instruction of the routine is XOR of the byte read (e.g. LD A,(DE) / XOR (HL) / LD (HL),A), over the stated scope",
    "false_when": "any write in scope is overwrite / OR / AND",
    "evaluation": "manual",
    "survey_field": null,
    "survey_field_proposed": "routines[].composition",
    "probe": "scan GAME.z80 --rzx R --range 0x4000-0x57FF --writers lists the writing PCs; disassemble those PCs and classify by hand (PLAYBOOK 2)"
  }
}
```

**Existing vs proposed tool capability.** Every predicate states `evaluation`: `auto` (a field the
tools emit today), `manual` (an agent judges from tool output and disassembly) or `proposed` (a
field that does not exist yet). Today: survey reports writers, callers, T per call, ISR, free memory
and block-copy counts; `scan --writers` lists writing PCs and ranks them, but does **not** classify
XOR vs overwrite; the survey emits no composition field. So `render.composition.*` starts manual.
An agent never treats a writer listing as evidence of a composition it does not report.

Rules:
- **Matching is conservative.** The matcher sets a predicate only from a structured survey.json
  field that exists. Everything else is `unknown` with its probe, for the agent to settle. Most
  predicates will be agent-judged at first; the tooling must not claim automatic matching it does
  not do.
- Predicates evaluate to **true / false / unknown / conflicted**.
- **Eligibility:** a card is eligible only when every `requires` predicate is true **and** every
  `rejects` predicate is false. A false `requires` or a true `rejects` excludes it (reason saved).
  Any `requires` or `rejects` predicate that is unknown or conflicted defers the card and names the
  next probe; a safety condition is never assumed false to make a card eligible.
- Eligible is not approved: the design still goes to the user (stage 1).
- **Not seen is not absent.** "No reader in this recording" is scoped evidence. Survey "free
  RAM" is local evidence (Atic Atac: four survey "free" spans held other characters' graphics).
- A rejected card is saved with its reason so the next agent does not retry it.
- Changing the snapshot, code, tool semantics or a card's preconditions invalidates the conclusions
  that relied on them. Old results stay, tied to their original inputs.

## 6. Card template

First block: metadata. Rest: fixed Markdown sections.

```json
{
  "schema": 3,
  "id": "patch.isr-deferral",
  "revision": 1,
  "kind": "patch",
  "title": "Defer the game's ISR while a non-re-entrant hooked routine runs",
  "question": "Can added hook time let an interrupt land inside a routine the ISR also calls?",
  "tags": ["interrupt", "re-entrancy", "timing"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["exec.isr_calls_routine", "exec.routine_not_reentrant", "hook.adds_time"],
  "rejects": ["exec.isr_must_run_on_time"],
  "conflicts": [],
  "phases": ["entry", "isr", "exit"],
  "order": {
    "entry": {"after": ["patch.plot-entry-exit-hooks"]},
    "exit":  {"before": ["patch.display-atomic-switch"]},
    "cross": ["entry increments DEPTH before the plot runs",
              "a deferred ISR runs only at the exit that returns DEPTH to 0"]
  },
  "owns": {"vectors": ["im2"], "hook_state": ["DEPTH", "PENDING"]},
  "examples": ["games/incredible_shrinking_fireman-add-OPUS.md#hardware-round-2"],
  "sources": []
}
```

**Use / do not use.** Goal, positive conditions, disqualifiers, unknowns, each as a registry
predicate.

**Recognise.** A few discriminating signals and likely false positives. Prefer relationships
between operations over fixed addresses.

**Probe and stop.** The nexclash command(s), expected output, what to do on positive / negative /
inconclusive. Stop when the question is answered within a recorded scope.

**Contract.**
- State: transformation, preconditions, equivalence boundary (what is excluded from comparison).
- Time: interrupt state, re-entrancy, cost budget, ordering against other cards (`order`), and
  stack room, in two parts: `hook stack: N bytes for its own calls and pushes` (always required)
  and `interrupt headroom: M more bytes at every hook instruction while IFF is on` ("interrupts
  off: n/a" applies to this second part only). Stack depth is a run-time property checked per
  instruction (Commando, Midnight Resistance), so it lives here, not as an `owns` range.
- Display: when replacement graphics become visible (entry, exit, deferred hide, atomic switch);
  approved visual changes listed explicitly; mask polarity and coordinate units stated.

**Resources owned.** Declared in the metadata `owns` block with a fixed shape, so two cards in one
recipe can be checked for collisions without reading asm. In the card, the parameterised form
(`"sprite_ids": "param"`); the actual values live only in the game's record (§3):

```json
"owns": {
  "mmu_slots": [6],
  "memory": [
    {"space": "next_page", "page": 26, "offset": ["0x0000", "0x01FF"], "mapped_at": "slot 6"},
    {"space": "game_ram", "bank": 5, "offset": ["0x1D00", "0x1DFF"], "cpu": ["0x5D00", "0x5DFF"]},
    {"space": "alt_rom", "image": 1, "offset": ["0x386E", "0x39FE"]}
  ],
  "sprite_ids": [[0, 4], [5, 28]],  "pattern_slots": [[0, 63]],
  "registers_clobbered": [],        "vectors": ["im2"],
  "speed": "28MHz-inside-hook",     "hook_state": ["DEPTH", "PENDING"]
}
```
Ranges are inclusive. Memory is identified **physically**: Next page + offset, game bank + offset,
or alt ROM image + offset; `mapped_at` / `cpu` are informative. Overlap is compared on the physical
identity, so the same CPU address in two pages is not an overlap, and the same page mapped into
two different slots still is. doccheck validates the shape; a recipe check **reports** overlaps
between applications.
An overlap is a review trigger, not automatically a conflict: it passes only with a recorded
reason in the record (`"overlap_ok": {"with": "<application>", "why": "exclusive use | save/restore |
non-overlapping lifetime", "note": "..."}`). Two hooks may share scratch space if neither runs
inside the other; an interrupt-time application sharing it needs the reason spelled out. IY/IX are listed under `registers_clobbered` only if the hook changes them at any instruction
while interrupts are on (Commando's menu logo: a hook used IY).

**Measurements (optimise cards; required, doccheck-checked).** A `### Measurements` subsection
with, per workload: payload (what is cached or moved), hit / miss rate, worst scene, setup cost,
CPU speed and core, and when it does not help (Cyclone: 157 distinct images in 682 renders). No
bare "faster".

**Lifecycle.** `candidate` -> `active` -> `deprecated` (with `superseded_by`). A new lesson extends
or supersedes an existing card; it never forks a third overlapping one. A deprecated card keeps its
evidence and points to its successor.

**Failure lookup.** Rows of symptom -> cause -> probe -> fix -> rejected fixes (with reasons).

**Verification.** Minimum checks for State / Time / Display; a negative control the verifier must
catch; coverage gaps; hardware obligations separate from software checks.

**Evidence.** Exact functions and asm labels (`grep -n` targets), game application sections, each
claim marked observed / inferred / unknown. No blanket "verified" on a card.

## 7. Investigation procedure (nexclash commands first)

| Question | Command | Notes |
|---|---|---|
| What kind of snapshot? | `nexclash.py inspect GAME.z80` | loader, 48K/128K, ROM, IM, stack |
| Who draws, how often, at what cost, from where? | `python -m nexclash.survey GAME.z80 --rzx R` | survey.md + survey.json; coverage gate for unreached callers |
| Which writers touch a range? | `scan GAME.z80 --rzx R --range LO-HI --writers` | ranks writing PCs; XOR vs overwrite is classified by hand from their disassembly (no tool does it yet) |
| What does each plot routine draw, per caller? | `preview GAME.z80 --rzx R --plot ENTRY` | figure kinds for the design question |
| Cost per draw, per object? | `cost GAME.z80 --rzx R --at PLOTTER --group IX` | also checks a surprising survey row |
| What must hooks keep intact for the ISR? | `isr GAME.z80 --rzx R` | IY/IX reads, stack, slots touched |
| Does logic read figure pixels? | no shared command yet | Atic Atac used a one-off pass; candidate for a shared probe (section 11) |

Then: trace a copy upstream to its producer (a block copy into the screen points at a back buffer);
list every CALL/JP into each plotter, including entries past the hooked one; list every write
into the routine's own code (self-modification); compare a second object and an animation change
before settling object identity. Spectrum Analyser and SkoolKit control files are optional aids;
record which tool actually produced an observation.

## 8. Composition

A recipe is the game's list of technique **applications** (§3) with **explicit run-time
constraints**. A tag list is not enough, and list order is not run-time order.
- State the constraints that matter, per phase and across phases (card `order`, §6): hide vs plot,
  28 MHz inside hooks vs the ISR, menu vs play, entry vs exit hooks, an ISR deferred to the
  outermost exit.
- Check resource ownership for collisions (slots, pages, sprite IDs, pattern slots, IY/IX use).
- Test the combination: individually valid cards can interfere (Fireman: overlay hooks + the
  game's own ISR plotting = round 2).

## 9. Worked patch example: Fireman, interrupt re-entrancy

Source: games/incredible_shrinking_fireman-add-OPUS.md, hardware rounds 1-2.

**Observations.**
- Plotter 0xB950 is not re-entrant: globals 0xBD17-0xBD41 and a self-modified operand 0xBCD2
  (observed, static + RZX).
- The ISR 0xC24C plots too: the fireman (0xC269) and the room figures (observed).
- The original never nests only because of timing: in frames where the ISR plots, main-loop plots
  end at least 2.0K T before the interrupt (observed, this recording).
- The hooks add up to 16K T per frame (observed).

**Failure (round 2, build 400d0d11).** Room 5: extra white firemen, garbage over the LIVES box;
"the correct sprite is under the table". The interrupt landed inside a main-loop plot, the ISR's
plot overwrote the globals, and the outer plot carried on with the wrong figure. Every state check
at hook boundaries had passed.

**Rejected fixes.**
- Save/restore the globals: the ISR plots the *same* object, so the outer plot would XOR a stale image.
- Hold interrupts in hardware: the ISR overruns frames, so the main code would starve.

**Fix.** The IM 2 jump at 0xFFF4 goes to a hook that, while a plot runs (DEPTH > 0, counted by the
entry and exit hooks), sets PENDING and returns. The exit hook, back at depth 0, enters 0xC24C with
the plot's caller as return address. The game rewrites 0xFFF4 on restart (its set-up at 0xC234,
RZX frame 32335), so that operand is patched too. The verifier's "game wrote a patch site" check
caught it on the first stamping run.

**Verification.** Every deferral in the RZX checked (handler entered once, at depth 0, returning
to the caller). Interrupts injected at 20 points inside 2 main-loop plots: patched plot intact
(the original corrupts 19 of 20 in one of them). Negative control: deferral removed -> detected.

**Display, round 1 (build dc65565c).** The XOR plot takes 24-27K T, about a third of a frame,
and over 97% of plots run while the beam draws. Moving the sprite at the plot's exit left the
half-done ULA plot visible for that time (flicker). The toolkit could not see it, because it
checked state at hook boundaries. Fix: an entry hook shows the new image on pending sprites before
the plot runs, and the exit switches to them, so old and new images are covered throughout.

**What the standard would have asked first.** Time: "is the routine **not** re-entrant, does the
ISR call it, and does the hook add time?" All three true makes `patch.isr-deferral` an eligible
candidate, still subject to its rejection conditions (e.g. an ISR that must run on time) and the
design question; it is not selected automatically. Display: "when does
the replacement become visible relative to the original's intermediate states?"

## 10. Worked detection-to-design example: Atic Atac

Source: games/atic_atac.md, Engine / Decisions / Build design.

| Question | Observation (basis, scope) | Conclusion |
|---|---|---|
| Composition? | two row blitters 0x9EDC / 0x9F21, each call XORs one row of 2-3 bytes (observed, whole RZX) | XOR family: shadow or overlay |
| Tracked unit? | row calls ~235-247 T each; busy frames 85-86 calls (observed) | hook per **figure**, not per row |
| Gameplay reads figure pixels? | every non-plotter read is a drawer's own read-modify-write (observed, this recording only) | no virtual read; the gap stays a named limit |
| Other writers break ULA = scenery ^ figures? | play-area clear, pocket icons, scenery drawers with run-time op bytes, room-line OR, text printer (observed) | 1-bit shadow screen; non-XOR writers keep the invariant |
| Layer 2 or sprites? | one shared XOR layer cancels touching figures (Dizzy 1 hardware round 1) | per-image hardware sprites |
| Is every plot a whole image? | **correction:** the appear/death effect draws one row per plot; the first reading took heights from static bytes (observed, stage 2 part 2) | image groups with a 24-bit row mask |
| Is the survey's "free RAM" free? | four spans hold other characters' graphics, untouched by this recording | not free; no game RAM used |
| Self-modification at sites? | op bytes rewritten at 0x99D7, 0x9A36, 0x9A78, 0x9ADD, 0x9B88 | sites moved off them; op read at run time |

**What it shows.** "XOR" alone did not choose the design. The tracked unit, the interfering
writers and the cost per call did. Per-image parity once kept 18 slices plus the figure visible
while the original's screen was blank, a ghost the per-image pixel check could not see: a Display
check by tracked unit, not by draw call.

## 11. Initial catalogue (ranked by hardware rounds already lost)

| ID | Kind | Evidence |
|---|---|---|
| `patch.isr-deferral` | patch | Fireman round 2 |
| `patch.display-atomic-switch` | patch | Commando (hide/show flicker; fixed by building in other pattern memory and switching attributes last), Fireman round 1, Atic Atac pending entries |
| `detect.tracked-unit` (partial-image grouping) | detect | Atic Atac rows and slices, Rainbow Islands bosses as several objects |
| `patch.xor-shadow` | patch | Dizzy 1, Atic Atac |
| `patch.xor-overlay-keep-ula` | patch | Fireman (logic reads XOR figure pixels, figures in front) |
| `patch.scratch-redirect` | patch | Midnight Resistance, Smash TV |
| `optimise.pattern-cache` | optimise | Midnight Resistance (tank scenes 340-410K T, 16 entries thrash; 32 need more page room), Commando, Target Renegade, Cyclone (157 distinct images in 682 renders: a bigger cache does not help) |
| `detect.gameplay-screen-readers` | detect | TID bubbles read Dizzy's pixels; Dizzy 1 falling objects; Dizzy 3/4 where a virtual read would be wrong |

`detect.tracked-unit` is the softest of the eight and stays `candidate` until its card states a
crisp rule: **probe** = for each plot entry, compare the rows / bytes one call draws with the
object's full graphic (height byte or row count), across normal play and every effect the
recording reaches (Atic Atac: the appear / death effect); **stop** = every entry is classed as
whole image, partial image (with how parts join: row mask, quarter, slice) or composite object, or
the unclassed entries are named as unknowns. It answers only "what unit must the hooks and the
Display check track", nothing else. It stays `candidate` until a second game exercises the
row-mask (partial image) path; Atic Atac alone does not make it `active`.

Approved visual changes are recorded per application, never claimed as equivalence. Cyclone: the
1 px outline can lie over foreground scenery, and dithered shadows show scenery differently.

**Toolkit work these cards need** (to BRIEFING C2):
1. Hook-cost line in `auto` (existing C2 #1), reported per workload: worst scene, cache hits/misses.
2. A shared interrupt-injection check (generalise Fireman's).
3. A shared Display check: nothing visible changes wrongly between hook entry and exit.
4. A shared gameplay-screen-reader probe (Atic Atac's one-off pass as a command).

## 12. Retrieval and authoring discipline

- **index.json entry** (generated from card metadata; the generator and CLAUDE.md rely on exactly
  these fields, so an agent never needs to open a card to shortlist):
  ```json
  {"id": "patch.isr-deferral", "kind": "patch", "lifecycle": "candidate", "superseded_by": null,
   "question": "Can added hook time let an interrupt land inside a routine the ISR also calls?",
   "summary": "Count hook depth; defer the game's ISR to the outermost hook exit.",
   "requires": ["exec.isr_calls_routine", "exec.routine_not_reentrant", "hook.adds_time"],
   "rejects": ["exec.isr_must_run_on_time"], "conflicts": [], "tags": ["interrupt", "re-entrancy"],
   "examples": ["incredible_shrinking_fireman-add-OPUS"], "path": "docs/techniques/patch.isr-deferral.md"}
  ```
  `summary` is one line, taken from the card's first sentence under "Use / do not use".
- **Index first, as a hard rule in CLAUDE.md** (as firm as the size budgets): search
  `docs/techniques/index.json` by question and observed predicates; open a full card only after
  selecting it from the index. Return at most three candidates first; say how many more exist.
  Per candidate, usually just: ID, why it fits, its blocker, the next probe. 100-200 words is a
  ceiling, not a target. This is what keeps 40 cards cheap.
- Read example functions only after a card is selected. Default: targeted function reads (the
  card's `grep -n` targets), never a whole engine module. Reading a whole module is an exception,
  noted with its reason in the session's Stage log line (games/<game>.md keeps technical findings
  and decisions, not agent housekeeping). No fixed per-session limit: a hard cap would push work
  into extra sessions that reload the same context.
- At close, write only new facts and changed conclusions. Supersede a wrong rule with its reason.
- Measurements state CPU speed, core, payload and setup cost, never a bare "faster".

## 13. Adoption plan and acceptance

1. Scaffolding: the template, predicates.json with only the ~15 predicates the eight cards use,
   the eight cards in section 11, the index.json generator.
2. doccheck.py: card schema, mandatory sections (incl. the Display wording and optimise
   Measurements), predicate names resolve, `owns` shape, lifecycle values, size budget.
3. Annotate 2-3 games only (Fireman OPUS, Atic Atac, and Midnight Resistance or Chuckie Egg):
   the record's `techniques` recipe with concrete `owns` values, and the `Techniques:` line in
   games/<game>.md pointing to it. Docs only, no rebuild, no MD5 change.
   The rest are tagged as each game is next touched.
4. CLAUDE.md and PLAYBOOK stages 1-2, a one-page delta: "identify the patch plan", index first,
   targeted function reads by default, the retrieval protocol in section 12.
5. Survey Candidates block (card, reason, unknowns, next probe, what to read), only once
   predicates have `survey_field`s worth emitting.
6. Trial on one unknown game **against a baseline**: a comparable game done with the existing
   workflow (similar rendering model and size; or the same stage re-run the old way). Record for
   both: total input / output tokens, tool calls, repeated reads of the same file, wall time to an
   approved design, wrong technique selections, user rounds (the Stage log already records most).
   Without the baseline the trial shows whether the workflow works, not whether it saves enough to
   adopt.
7. Toolkit gaps from section 11, Display check last (hardest).
8. Only after the trial: shared technique code by the rule of three. When shared runtime code
   changes, records.py finds **every dependent application**, rebuilds and runs the automated
   checks for all of their games (MD5s, boot, quick checks), and selects re-verifications by
   behaviour and coverage (paging, interrupts on/off, partial images, configuration), not one
   fixed representative per technique. A documentation-only card revision rebuilds nothing.

**Acceptance.** A new agent can state what is known, which card is eligible, what blocks it, the
next smallest probe, and the State / Time / Display proof required, without opening an unrelated
game module.

## Appendix A. External example kept from v2 (not checked here)

v2 derived a foreground-clipped masked composition from the Great Escape disassembly
(dpt.github.io/The-Great-Escape, routines E2A2 and B916). nexclash already does occlusion of a
different kind: Commando removes sprite pixels inside a solid scenery object's shape when the
figure is behind it (walk-box depth rule; games/commando.md). The Great Escape formula itself,
a separate foreground-allowance mask combined into the masked plot, is unported and unverified,
and no local snapshot was matched, so it is a candidate card (`patch.foreground-clipped-sprite`),
not in the initial catalogue; Commando's solid-shape removal is its nearest local evidence. Its lesson stands: never
generalise "mask" to one polarity across games.

## Appendix B. Sources

- nexclash repo: CLAUDE.md, docs/PLAYBOOK.md, BRIEFING.md (A3, B2b, C2), LEARNINGS.md (2.1),
  nexclash/records.py, games/*.md (Fireman OPUS, Atic Atac, Commando, Cyclone, Midnight
  Resistance, Dizzy 1, TID engine).
- v2 sources kept as optional aids: Spectrum Analyser manual (colourclash.co.uk), 8BitAnalysers Lua
  wiki, SkoolKit control-file docs, Great Escape disassembly. Not run in either review.
