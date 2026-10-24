# The Incredible Shrinking Fireman (Mastertronic, 1986) - engine: none yet (phase A in progress)

Reference: specnext/reference/incredible_shrinking_fireman/ (incredible_shrinking_fireman.z80 from
Incredible_Shrinking_Fireman_The_1986_Mastertronic.z80, + .rzx "incrediblefireman.rzx", Dean 2026-10-25).
No STATUS row / evidence record / engine yet.

## Snapshot (PLAYBOOK 0b)
- 48K, PC 50468 (RAM), IM 2 I=0x39 (vector 0x39FF -> table of 0x00 bytes, handler entered at 0xFFFF), EI,
  SP 24970, RAMTOP 24999. BASIC loader program still in memory (USR 23296), but the game is running.
- Recording: 1 segment, 32492 frames (650 s). Full-length Python replays are slow: use --stop N and detach.

## ISR (`isr`, whole recording)
- Reads IX of the interrupted code (LD A,(IX+0) 48345, LD (IX+0),A 48351, INC IX 48355): hooks with
  interrupts on must keep IX. Uses R (59713), EXX (47993...), AF' (31350...). Up to 42 bytes of stack
  below SP. All 8 slots touched: no free slot for hook state yet.

## Screen survey (first 4000 frames)
- Room-based platformer: HUD frame with LIVES at the top, fireman (player), objects, enemies
  (frames at 500/1500/2500/3500 looked at).
- Screen writers (hot): 48047/48059/48071/48083 (x89745 each) = XOR plotter inner loop of the routine
  at ~47890-48222: pure XOR of a shifted 4-byte-wide sprite (and a 3-byte tail), per-row table at 48431,
  buffer ptrs 48407-48447; it saves its state at the end (48208-48220) = XOR draw / erase pairs.
  Also 31503 x156000, 50619 x65520, 48351 x30715, 31353 x20800, 49953 (not yet classified).
- Rendering model (provisional): pure XOR to the screen -> dizzy1 pattern (1-bit shadow screen) is the
  nearest template; attribute routine at 48223 (cell address -> 22528 + ...) to be classified.

## Open (next session)
- Classify 31503 / 50619 / 48351 / 31353 / 49953; list every caller of the plotter at 47890.
- `cost`, `scan --range` for free memory, then the preview sheet with --plot ENTRY.
- Phase A question to Dean (with preview frames + colour sheets): which figures become sprites,
  depth, colours. Not asked yet.
