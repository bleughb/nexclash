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

## Plotters and writers (RZX frames 0-4000; `scan --writers`, `preview --plot`, `cost`)
- 47440 (0xB950) = THE figure plotter, 13 CALL sites (49769 ISR-side, 49899, 51190, 51514, 51533,
  52133, 59852, 59864, 60059, 60097, ...). A = object slot (0, 1, 2); slot state at 48374.. (frame
  48374, x 48375, y 48376, old pos 48440-48443...). One call = DIFFERENTIAL move: XOR of old image and
  new image (two shifted graphics via 48409 / 48416), rows from the table at 49220, XORed onto the
  screen (writes 48047/48059/48071/48083, 47897-47905, 48165-48183), then the attribute routine
  48223 (cell colouring: A = (attr ^ E) & D ^ E where flag bit 6 of the 48452 table is clear)
  writes 48351. Stores the new position at the end (48207-48220). Cost: median 25,462 T per call,
  34.3 % of frame time (3828 calls in 4001 frames, max 3 per frame).
- Callers by slot (preview_plot_47440.png): slot 0 = fireman (49769 from the ISR-side routine at
  49740; 2061 calls; also the cut-scene/transition callers 49899, 51190, 51514, 51533, 52133);
  slots 1 and 2 = the two moving room figures (the skull / bulb / UFO-like things; setup 59852,
  59864; per frame 60059 and 60097: 531 calls each in 4000 frames).
- Not figures (stay on the ULA): 31353 / 31503 (RL/RR (HL) scroller, x156000), 46049 (text print),
  49953 (screen decompress), 50619 (screen clear LDIR), 50349 (room redraw), 51906 / 59725 /
  59367 (attribute fills: flash / colour cycling), HUD frame.
- Screen READS by game logic: 49868 / 51159 / 51421 = LD A,(DE) at the address 50319 returns for
  (x = 48375, y = 48376 + 25): two bytes tested for non-zero (movement/landing collision against
  scenery). Possible overlap with the figures' own XORed pixels: needs the differential
  "virtual read" decision (PLAYBOOK 4) - to be proven by the verifier, not assumed.
- Frames rendered: reference/<game>/preview_frames.png, preview_plot_47440.png (colour = caller).

## Dean's decisions (2026-10-25, phase A answer)
- ALL moving figures become sprites (fireman, both moving room figures, cut-scene figures: every
  caller of 47440), AND the collectable items become sprites too.
- Depth: no preference -> default: sprites always in front of the scenery. Colours: no preference ->
  default: the colours the game's attribute routine gives today, then painting sheets (PLAYBOOK 3b) and
  `recolour`. (Defaults chosen by the agent on Dean's "no preference"; revisit if hardware looks wrong.)

## Collectables (found 2026-10-25)
- Per-room object table: pointer table at 55021 + 2*room (room = (49612)); each room has 5 entries of
  3 bytes (id, x, y); id 0 = empty slot. Current room's table address is cached in (60584).
- Routines: 60487 (find first non-empty entry), 60518 (pickup test: figure box vs each entry, entry
  box +26 wide / +34 high, returns id), 60727 (clear entry with id C: drop/pick-up bookkeeping),
  53107 (find a free entry), 53126 (write dropped object: id, x (48375), y (48376)+16).
- Drawing: the room draw at ~60621-60690 writes each object's 7 rows with plain stores (60683 LD
  (HL),A; 56 writes in the first 4000 frames), address from 60699 ((x,y) -> screen address);
  60780 is a second plain-store site (8 rows from 30000 + 8*(60456)+...). Graphics id table: names at
  57881.., pointer table 57863; object count 32 (ids 1-32?). To be classified: where the graphic bytes
  come from per id, how the screen cell is erased on pickup (room redraw? 52305?), attribute use.
- Counts: collectables are drawn by overwrite (not XOR), so the build needs the hide/show model of
  PLAYBOOK 4 (overwriting writers), not the XOR parity model.

## Open (next session)
- Classify the object draw (60621-60690, 60780) and erase path; find every room/figure caller.
- Free memory for hook state (all 8 slots touched by the ISR), tail address, alt-ROM hooks possible?
- Engine: dizzy1.py (pure XOR + shadow screen) vs a differential-plot hook at 47440; sheet code
  (midres.sheet_part template); evidence record; full verification once.
