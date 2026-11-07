# Atic Atac v1.4 rework: the pace limiter (opt-in; games/atic_atac.md "Rework (opt-in)" is v1.3)

## Rework (opt-in): Atic Atac .nxc v1.4, the pace limiter (engine atic_atac_v14, `NEXCLASH_REWORK=atic_atac_v14`)
Jon Attree, 2026-11-06: the published v1.3 ran slightly FAST (JNext 1.2.0 sweep, the published method: busy -2.79%); his
rule is within 2% and never faster. v1.4 = v1.3 (atic_atac_v13, untouched: a copy as atic_atac_v14.py,
asm/atic_atac_v14_hooks.asm + _qaop.asm, docs/profiles/atic_atac_v14*.json) + the limiter. Picture, both colour sets,
the QAOP + Space toggle and the trainers as v1.3; R still changes with the hooks (as v1.3: the verifier excludes R).
- Why it ran fast: the row hooks draw a row 13-52 units (1 unit = 1/64 line = 3.5 T) faster than the original
  blitter, which at 3.5 MHz also pays ULA contention on the screen and its stack (rows on paper lines ~290 cycles of
  28 MHz more than in the border); a setup hook costs more than the two instructions it displaces. Shorter masked
  stretches also made the build miss fewer interrupts (v1.3 busy 452 ISRs in 500 frames, original 421): the game's
  clock and its FRAMES waits (0x9746 beeps until FRAMES changes) count interrupts, so the game is partly frame-locked.
- The limiter (asm "pace limiter"; hook RAM V_DEBT 0x5BA9, V_L0, V_FR, V_PG; variables end 0x5BB0): each figure
  setup (h_setm / h_seta) is the account. Open: interrupts since the last setup x KISR (the ROM ISR runs at 28 MHz
  when it lands in a hook, 17-19% of them), window start on the video line (NR 0x1E / 0x1F). Close: T = V_DEBT +
  the rows this plot draws through the row hooks (min(h, y + 1); none for x >= 192) x the set's saving at this shift
  (CRA / CRB, JNext 1.2.0 means original minus v1.3 over quiet, busy and sound) + SETK; the hook waits on the video
  line at the caller's clock until T has passed since the window start, whatever the interrupt state (each plot then
  lasts as the original's, masked stretches included); V_DEBT = T - the lines taken (carried, -192 .. +312 lines).
  Hooks slower than their original (text 23, scenery drawers 87, room line 39, character setup 60 units) take
  their extra off V_DEBT (pace_debit), so later plots wait less. SETK -76 = 6 original + 6 painter NOPs - 106 entry
  and exit outside the measured interval + 18 margin. Hooks keep every register; the wait gives up after 2048 polls.
- Verifier: models NR 0x1E / 0x1F from the wall clock (3.5 MHz T / 224, 312 lines); HSTK_MIN follows the new
  variables; limiter_units (setups with interrupts off / on, 0 / 20 lines ahead; the limiter removed must not wait).
- Results (2026-11-06; pilot runs/atic_atac/v14): builds sprites bc9657c5, Enhanced b0209166, QAOP 9b6e6753 / f7376520;
  all four IDENTICAL on walk1, walk2, t (per build 21,003 frames, 40,623 setups, 666,275 rows, 45.1M sprite pixels);
  units per set 1,483 cases, controls 3/3, rework negatives 22/22, 432 incoming-clock cases; limiter 72 cases,
  limiter removed detected 36/36; toggle keys 924 / 832, both negatives detected. Pace (published method, 10 runs a
  scene, JNext 1.2.0 = 1.1.104): busy +0.83%, sound +0.53%, quiet +14.53% (encounters; encounter-free runs -0.3 to
  +1.2%); v1.3 -1.83% / -1.74% / +12.85%; limiter removed busy -1.74%. Flicker 3 windows clean; soak 15 min clean.
  Hardware: none. Real-hardware caveat: NR 0x1E / 0x1F and 312 lines (50 Hz) assumed; contention figures are JNext's.

## Shared pace library (engine refactor, 2026-11-07): not ported, by decision
- Interrupts: v1.4 runs Sinclair's IM 1 handler untouched from the alt ROM image and credits each interrupt from
  FRAMES (KISR 44 units). hlib_pace leaves interrupt time out only through an ISR wrapper (hold / resume): 0x0038 would
  have to change, and the image outside the hooks is Sinclair's by design.
- Debt: v1.4's is signed and carries "ahead" time up to +312 lines (WMAX waits of 300 lines). The per-shift costs (CRA /
  CRB) were tuned against that over ten builds (runs/atic_atac/v14 b14v14b..j). hlib_pace's debt is behind-only, so
  the port is a re-tune, and the published pace (10 runs a scene: busy +0.83 %, sound +0.53 %) a re-proof.
- RAM: the printer buffer is full (variables 0x5B80-0x5BAF, the hook stack down to HSTK_MIN 0x5BC2, atic_atac_v14.py). The library's 26 bytes
  could go only in the shadow page's table area (0x7800-), which is at slot 3 only part of each hook. Every pace call would
  need that mapping, so the room is not clean.
