# Hybrid: keep the original game logic, replace its display with Next layers

```json
{
  "schema": 4,
  "id": "patch.hybrid-display-replacement",
  "revision": 1,
  "kind": "patch",
  "title": "Hybrid: keep the original game logic, replace its display with Next layers",
  "question": "Can the game's own display work be replaced by tilemap / Layer 2 / sprites while its logic, pace and sound stay original?",
  "tags": ["hybrid", "tilemap", "sprites", "copper", "renderer", "equivalence"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["routine.display_only_effects"],
  "rejects": ["screen.gameplay_reads_figure_pixels"],
  "conflicts": [],
  "phases": ["commit", "menu"],
  "order": {"commit": {"after": ["patch.timed-side-effect-replay"]},
            "cross": ["layers hide on every exit from gameplay before the game draws a menu",
                      "replaced display time is padded back (patch.pace-limiter)"]},
  "owns": {"next_pages": "param", "sprite_ids": "param", "pattern_slots": "param", "hook_state": ["CW_WOQ"]},
  "examples": ["inferno"],
  "sources": ["specnext reference/inferno/build/hybrid.md (plan, hardware rounds 2026-11-09)"]
}
```

## Use / do not use
When the removal experiment (detect.routine-removal) shows a routine's effects are display-only:
run the original game logic and producers, take scenery from the game's own map and actors from
its own lists, and draw them on Next layers. Reclaim the replaced display time for rendering work,
then pad to the original duration so pace is unchanged. Keep any gameplay call inside the routine
(Inferno 9804) and any sound it makes. Not when logic reads the figures it draws.

**Assumptions.** A clean source exists (Inferno: tile map 9B00 at 8F7C, actor lists C100); the
HUD and menus can stay on the ULA under a layer priority that shows them.

**Validation gap.** Inferno only; hardware by eye (all levels, intro, restart); freshness
(publication rate, display age) not measured on hardware.

## Recognise
- detect.routine-removal sets `routine.display_only_effects` true.
- Exact preservation of a big routine dominates the cost (Inferno's copier window milestones).

## Probe and stop
1. detect.routine-removal; detect.pacing-structure (what time the routine occupies).
2. Measure the replaceable part (Inferno: copier write-out 980B, 38-70k T, no beeper).
3. First visible build: original display untouched, sprites over it; then the scenery layer; then
   replace the write-out; then one Copper commit. Hardware after each.
Stop when one level plays on hardware with the replaced display.

## Contract
- State: game RAM equal to the original outside display memory and the replaced routine's pages;
  R supplied from the recording in replays where the game reads it.
- Time: replaced work + pad = original duration (within the measured tolerance); unfinished
  rendering is dropped, the display keeps the last complete frame. Hook stack: as the window;
  interrupt headroom: interrupts off in the replaced section.
- Display: sprites, tilemap and enables committed together (patch.display-atomic-switch); both
  layers hidden at every exit from gameplay (Inferno modal_exit at 901C).
- Display: software = return/boundary only; hardware = checklist item "menus, death, shop and level changes show no stale layers"

## Resources owned
Pages for the tilemap and pattern store, sprite IDs, pattern slots: values in the record.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| Menu shows only the top rows | layers left on over the ULA menu | exit paths | hide at the common exit | per-menu hooks |
| Ghosting, "bad v-sync" | layers switch mid-frame, separately | commit timing | one Copper commit at line 224 | - |
| Game too fast | write-out removed, no pad | pace | pad to original time | - |

## Verification
Replay with supplied R: game RAM equal at each loop point; unit test of the replacement hook against
the original instruction with a negative control (no pad -> early); hardware checklist above.

## Evidence
- `grep -n '^wo_go\|^modal_exit\|^wk_select' asm/inferno_hooks.asm`; nexclash/inferno.py
  copier_window_build (`--cw-driver --cw-full`).
- hybrid.md hardware lines (observed by the user, not measured).
