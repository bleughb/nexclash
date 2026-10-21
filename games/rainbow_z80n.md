# Rainbow Islands (Ocean, 128K), Z80N version - engine `rainbow_z80n`, record `rainbow_z80n`

The Rainbow Islands entry going forward (user, 2026-10-21). Forked from engine `rainbow`
(games/rainbow_islands.md, record `rainbow`), which is DEPRECATED: kept unchanged for reference only,
built with `--engine rainbow`. Everything in games/rainbow_islands.md - game facts, memory map, Dean's
decisions, hardware history, the open items - applies here unless this file says otherwise; read it
first. This file lists only what differs.

Inputs (private repo): specnext/reference/rainbow_islands/rainbow.z80 (4c98b980), rainbow.rzx
(55046d18), rainbownew.rzx (47bb2b16), the LeeBee bookmarks - the same files as the deprecated
version, not copied. Builds: specnext/reference/rainbow_z80n/.

    python nexclash.py auto rainbow.z80 --rzx rainbow.rzx --rzx rainbownew.rzx   (rainbow_z80n is the default)
    python nexclash.py auto rainbow.z80 --no-record --engine rainbow              (the deprecated version)

Code: nexclash/rainbow_z80n.py, asm/rainbow_z80n_hooks.asm, docs/profiles/rainbow_z80n.json (after any
.asm edit: `python tools/asm2profile.py rainbow_z80n`), record docs/records/rainbow_z80n.json,
dispatch: nexclash/engines.py (rainbow_z80n first; `--engine rainbow` = the deprecated engine, whose
record's recipe passes it). nexclash/rainbow.py itself stays: commando, midres, wally, wally2 and
renegade import its NextState / _machine / _run / _BankMem.

## What differs from `rainbow` (fork point = cf017271, 2026-10-21)
1. Verifier: Z80N from nexclash/z80n.py (`z80n.install` in `_machine`) instead of rainbow.py's own
   NEXTREG / SWAPNIB handlers. NEXTREG now costs 20 / 17 T (board-checked, tools/hwtests/z80ntest)
   where rainbow.py counted 0 T: the simulated raster line (NextState.line, from T) and every T
   count in the reports (tsmax, long frames, speed) now include the hooks' 110 NEXTREG sites (MMU
   paging $50-$53 on every hook entry / exit), so they are no longer optimistic.
2. Hooks: Z80N instructions where they replace a plain-Z80 sequence with the same result, every one
   checked for registers and flags read afterwards (none of the replaced flags or registers is read):
   | Instruction | Sites | Was | Saves |
   |---|---|---|---|
   | SWAPNIB | 11 (+ the 2 the fork already had) | 4x RRCA / RLCA (each followed by AND / OR, or a jump on Z set before the rotates) | 8 T, 2 bytes each |
   | MIRROR A | conversion loop `.lp` (per mirrored stream byte) | the MIRTAB lookup through H/L | 10 T |
   | MIRROR A | background mirrored rows `.fm` (per byte) | PUSH HL / LD H,$F5 / LD L,A / LD A,(HL) / POP HL (the game's own table, a bit reversal in every hooked state - unit test rev_ok) | 31 T |
   | ADD HL,A | X position (per piece), map entry `.clr` | LD E,A / LD D,0 / ADD HL,DE; LD C,A / LD B,0 / ADD HL,BC (the pair is dead after) | 14 T |
   Page 26 code 32 bytes shorter. Not changed: the x64 / x8 address multiplications (a barrel shift
   would clobber DE / B that the code still uses; a plain-Z80 rewrite is faster anyway), OUTI
   pattern writes (OUTINB is the same 16 T), MIRTAB (still built; unused by the hooks now).
3. Unit tests: the Z80N self-test is z80n.selfcheck; `Z80N_USED` (rainbow_z80n.py) must equal the
   .asm's Z80N instructions; one negative control PER instruction (that one ED xx run as SkoolKit's
   silent NOP must be detected) instead of the SWAPNIB-only one.

Core: SWAPNIB / MIRROR A / ADD HL,A are in every Z80N core; the build needs the tilemap in bank 7
(as before: a recent core).

## Status
(filled in by the verification below)

## Open
- Everything open in games/rainbow_islands.md (painted colours + recolour, bookmark verify of the
  boss rounds, Dean's rework).
- Hardware: run the new build next to the deprecated cf017271 (checklist below).
- The simulated timing statistics (long frames, tsmax) with NEXTREG counted: compare with the
  deprecated engine's on the same recording.

## Hardware checklist
1. Boots; play as with cf017271: figures, collectables, rainbows, music the same.
2. Mirrored figures and backgrounds (player facing left, mirrored tiles): drawn exactly as before.
3. Busy scenes: at least as smooth as cf017271 (the hooks are a little shorter).
