# Redirect the game's own plotters into a scratch buffer

```json
{
  "schema": 3,
  "id": "patch.scratch-redirect",
  "revision": 1,
  "kind": "patch",
  "title": "Redirect the game's own plotters into a scratch buffer",
  "question": "Can the game's plotters draw a figure somewhere the screen never shows, unchanged, so the hook can turn it into a sprite?",
  "tags": ["back-buffer", "scratch", "redirect", "paging", "sprites"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": ["render.target.back_buffer", "plot.call_target_redirectable", "mem.hook_page_slot_free"],
  "rejects": ["screen.gameplay_reads_figure_pixels"],
  "conflicts": [],
  "phases": ["entry", "exit", "commit"],
  "order": {
    "entry": {"after": []},
    "exit": {"after": []},
    "commit": {"after": []},
    "cross": ["every plotter loop exit maps the address back before the game sees it",
              "the scratch page is unmapped and the CPU speed restored at every exit"]
  },
  "owns": {"mmu_slots": "param", "memory": "param", "sprite_ids": "param"},
  "examples": ["midnight_resistance", "smash_tv"],
  "sources": []
}
```

## Use / do not use
Replace the shared CALL target (or entry) that gives the plotters their buffer address, so a
converted figure is drawn by the game's own unchanged loop into a scratch copy of the buffer, and
build its sprite at the commit. Use for back-buffer composers whose plotters share an address
helper. Do not use when gameplay reads the buffer's figure pixels, or when no slot is free from the
ISR while interrupts are on.

## Recognise
- A back buffer copied to the screen by a block copy (survey: block-copy rows).
- Several plotters calling one address helper (Midnight Resistance: CALL 0x7EC1 at 5 sites).
- Plotters that use SP as a row pointer (Smash TV: `LD (op),SP`): redirect at entry with a
  trampoline instead.

## Probe and stop
1. `render.target.back_buffer`: the copy and its source range.
2. `plot.call_target_redirectable`: disassemble each plotter's entry.
3. `isr GAME.z80 --rzx R`: a slot the handler never touches (Midnight Resistance: slots 2, 4, 5).
4. Every loop exit of every converted plotter (JP NZ / DJNZ / RET paths).
Stop when each exit has a map-back and the slot is proven free.

## Contract
- State: the game's loop runs unchanged; the buffer bytes under a converted figure are what the
  original would leave minus the figure; flags at loop exits redone on the real address (Midnight
  Resistance FIXDEF: ADD HL,BC flags).
- Time: page mapped only inside hooks; 28 MHz inside, 3.5 MHz restored. Hook stack: in the hook
  page; interrupt headroom when IFF is on (Midnight Resistance: interrupts on, ISR uses 20 bytes).
- Display: converted figures appear at the commit, not as the screen copy passes (approved).
- Display: software = return/boundary only; hardware = checklist item "figures appear every frame; none left after level end or shop"

## Resources owned
Scratch page(s) and their slots, hook state in the page, sprites; values in the record.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| A figure stuck on screen after level end (Midnight Resistance) | a loop exit (shop / next level) not hiding | list every exit of the game loop | hide all sprites on that exit | - |
| Plot corrupts game memory | a loop exit not mapped back | static list of exits | FIX table on every exit | - |
| Commit writes wrong sprites past 51 | 8-bit SPR + N*5 overflow | full-table unit case | 16-bit arithmetic | - |

## Verification
Registers and memory at every converted plot and commit; sprite layer = the original plots' bytes;
interrupt safety after every hook instruction; negative control; full-table and exit unit cases.

## Evidence
- games/midnight_resistance.md "Patch (phase B)"; games/smash_tv.md (slot 7 scratch); BRIEFING A3
  (slot5 / slot7 rows); PLAYBOOK 4 (back-buffer row).
- `grep -n 'def model_decide\|def verify\|def _isafe' nexclash/midres.py`; asm labels `decide`,
  `commit`, `x_m`: asm/midres_hooks.asm; `e_s8`, `commit`: asm/smashtv_hooks.asm.
