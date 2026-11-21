# Winter Sports (Electric Dreams Software, 1985) - engine `winter_sports` (plain build, six events in one .nex)

## Next session
Stage: 3 (plain .nex delivered and played; no sprite build)  State: engine, record and notes on branch winter-sports-engine (2026-11-22)
Inputs: specnext/reference/winter_sports/ (menu .z80, .tap, [h].tzx, the delivered .nex); the user's files, no RZX
Start with: a sprite build for ONE event (Downhill first): `python -m nexclash.survey` on the event snapshots (below), find its plotter(s)
Read: PLAYBOOK stage 1, ## Events, ## Evidence
Open: hardware report for events 2-6 and the loading screen duration; sprite builds (each event has its own drawing code);
RZX per event if proof by differential replay is wanted; the Bleepload re-release (.tzx / [a].tzx) is not an accepted tape set
(its SCREEN$ is inside the turbo loader; the event blocks are identical)

    python nexclash.py auto winter_sports.z80 --tape "Winter Sports (1985)(Electric Dreams Software).tap" --no-record

## Sources (five files compared, 2026-11-22)
- `.tap` = `[h].tzx`: the original release, standard 19-byte headers `wisp-1..6` (CODE, 32,824 bytes at 0x7500).
- `.tzx` and `[a].tzx`: the Firebird "Silver Range" re-release with the Bleepload turbo loader; the two differ only in pulse
  timings/pauses and block labels. All six event blocks are byte-identical in all four tapes.
- The `.z80` is the 48K menu snapshot (v1, PC 0x0038, SP 0x5FEA).
- The menu code (0x6000, `wispc0`) reads each event with its OWN loader (0x627E -> ROM 0x0562): a 22-byte flag-FF pseudo-header
  (the Bleepload tape has these as 24-byte blocks; the .tap has standard headers instead, so the menu cannot load events from the
  .tap as it stands), then the event block to 0x7500. The wanted header is the table 0x63C0 + 22 k (pointer in 0x6296).

## Events
k = 0 Downhill/Slalom/Giant Slalom, 1 Ice Hockey, 2 Ski Jumping, 3 Speed Skating, 4 Bobsled, 5 Biathlon (main menu keys 1,4,5,6,7,8; 2 and 3
also load event 0). Each event: K, four control keys (Q A O P), then S (Speed Skating: 1 player, event 3-7, then S).

## Build (nexclash/winter_sports.py)
One 335,104-byte .nex: events in banks 12-26 (5 pages each), menu screen backup bank 27, a 127-byte hook at 0x6C00 (the stale loader bytes
0x6503-0x74FF: no event or the menu touched them in the runs), `JP 0x6C00` at 0x627E (site checked: 14 08 15 f3). Header request: copy the
wanted header, note k. Data request: copy the event's pages through MMU0 (NextReg 0x50) with interrupts off, restore 0x50 = 0xFF,
border, EI, carry set. Loading screen: the tape's SCREEN$ is the NEX ULA loading screen (flags 0x82) and bank 5's screen; the stub's setup
(0xD000) waits 260 frames (raster line 192 counted via NextReg 0x1F) then copies the menu screen back: JNext log SETUP F=500, game start
F=761 = 5.2 s on top of the load time.

## Pacing measurement
The plain build changes no game timing: no hook runs per frame. The one hook runs inside the menu's tape load, which on a tape took minutes; here
it copies 32,824 bytes with LDIR (about 12 frames) with interrupts off. Simulator: patched and original menus reach the same option screen
state (checks below). Hardware: Downhill ran (user, 2026-11-22).

## Dependency investigation
The hook's consumers: the menu's loader only (callers at 0x6182 header, 0x621A event; both read carry and IX/DE after). It uses the stack (RET),
the border system variable 0x5C48, NextReg 0x50 (restored to 0xFF) and its own 8 bytes of variables at 0x6D00. The events never touched 0x6503-0x74FF in the
free runs (diff of option screens and gameplay snapshots). Not covered: High Scores entry, two-player modes, joystick, 60 Hz.

## Evidence
- `python selftest.py REF --game winter_sports --verify` (no recording): for each event the patched menu (hook + NextReg 0x50 model) and the
  original menu (loads answered at ROM 0x0562 from the tape) run from the snapshot with the same keys; after 900 frames 0x4000-0xFFFF agree
  (0 bytes differ outside the hook, its variables, the system variables 0x5C00-0x5C7F and the stack 0x5F80-0x5FFF: the copy takes frames the trap does not)
  and I, IM, IFF agree. Unit tests call the hook directly: 12 headers (6 events x 2 destinations), 6 data blocks (bytes, IX advanced, ROM back),
  and a negative control (pages shifted by one: all 6 data cases fail).
- JNext 1.2.0 (headless): menu -> option screen -> keys -> S: Downhill, Ice Hockey, Ski Jumping, Bobsled, Biathlon, Speed Skating reach play;
  event A -> Exit -> event B works. The rebuilt .nex is byte-identical to the delivered one (md5 8dc688fa980454c63f98bc0e802d5f88).
- Hardware: the .nex loads and Downhill ran (user, 2026-11-22).
