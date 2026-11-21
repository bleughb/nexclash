# Winter Sports (Electric Dreams Software, 1985) - engine `winter_sports` (plain build, six events in one .nex)

## Next session
Stage: 3 (plain .nex delivered and played; no sprite build)  State: engine, record and notes on branch winter-sports-engine (2026-11-22)
Inputs: specnext/reference/winter_sports/ (menu .z80, .tap, [h].tzx, the delivered .nex); the user's files, no RZX
Start with: the user's answer to the Downhill stage-1 question (end of ## Downhill stage 1), then the removal experiment and the build
Read: PLAYBOOK stage 1-2, ## Events, ## Downhill stage 1, ## Evidence
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
free runs (diff of option screens and gameplay snapshots). High Scores display works from the main menu (H) and an event menu (JNext). Not covered: High Scores name entry, two-player modes, joystick, 60 Hz.

## Evidence
- `python selftest.py REF --game winter_sports --verify` (no recording): for each event the patched menu (hook + NextReg 0x50 model) and the
  original menu (loads answered at ROM 0x0562 from the tape) run from the snapshot with the same keys; after 900 frames 0x4000-0xFFFF agree
  (0 bytes differ outside the hook, its variables, the system variables 0x5C00-0x5C7F and the stack 0x5F80-0x5FFF: the copy takes frames the trap does not)
  and I, IM, IFF agree. Unit tests call the hook directly: 12 headers (6 events x 2 destinations), 6 data blocks (bytes, IX advanced, ROM back),
  and a negative control (pages shifted by one: all 6 data cases fail).
- JNext 1.2.0 (headless): menu -> option screen -> keys -> S: Downhill, Ice Hockey, Ski Jumping, Bobsled, Biathlon, Speed Skating reach play;
  event A -> Exit -> event B works. The rebuilt .nex is byte-identical to the delivered one (md5 8dc688fa980454c63f98bc0e802d5f88).
- Hardware: the .nex loads and Downhill ran (user, 2026-11-22).

## Downhill stage 1 (survey and design, 2026-11-22; Downhill = event 0 = Downhill / Slalom / Giant Slalom)
Nothing is built; the free runs and the tables below are what the design stands on. Hardware: not touched.

**Key script that starts and steers a descent** (simulator, from the menu snapshot with the tape served at ROM 0x0562; frames from the start):
`20-28:1; 1600-1630:K; 1700-1730:Q; 1770-1800:A; 1840-1870:O; 1910-1940:P; 2000-2060:S` reaches the ready screen (snapshot at frame 2250);
then `10-:Q; 300-340:O; 500-540:P` from that snapshot holds the first defined key (speed up) and steers: the descent runs, gates pass/fail,
the time counts (survey of 900 frames). The same in JNext, program frames: `400:1 (8), 600:K (30), 700:Q, 770:A, 840:O, 910:P (30 each),
1000:S (60), 1200:Q held 900, 1500:O (30), 1700:P (30)`. Without a held speed-up key nothing moves (the first survey, 600 frames of no
input, saw only the speed bars drawn).

**Screen** (character cells): rows 0-2 HUD text (0xF826, called from 0xF844 / 0xF84C), left pane cols 1-14 x rows 5-20 (112 x 128 px) the
first-person view, right pane cols 17-30 x rows 5-20 the overhead course map (grey, the track line and the gates), row 23 the CONTROL / SPEED bars
(0x90DF / 0x910A / 0x9110, called from 0x842F, 0x8464, 0x8473). Per update the loop at 0x83AE calls 0x84B0, which calls 0x8954 (the left view),
then scrolls the map pane with a 127-row LDIR loop (0x84FA) from the row-address table 0xF5E0 (the game's own table of 128 screen rows).

**Left view = a static panorama + poles** (disassembly of 0x8954 / 0x8B49 / 0x8C16 and the buffer scans):
- 0xA000-0xABFF is a 256 x 128 monochrome bitmap, 32 bytes per row: the mountain skyline, the forest silhouette and the slope (rendered from memory: it is the picture);
  0xB207 is the 128 x 14-byte working buffer; 0xB000 the attribute buffer (stride 32; rows 0x3D / 0x3C: whole-row colours, so the colour boundaries are cell-stepped).
- 0x8C16 scrolls the buffer horizontally one pixel per change of the heading variable (33500 = 0x82DC), 14 x RR (HL) per row; 0x8BFB reloads it from 0xA009 on a direction change.
- 0x8B49 erases last update's poles (undo list at 0x8B95, LD (HL),0 stepping 28); 0x8A16-0x8B1A draw the gate poles: vertical lines made with
  self-modified SET n,(HL) (0x8A9A, 0x8AFA, 0x8B1A) from the gate list at (34757) (gate record: 3 bytes: x, kind, colour code); then 0x8999 copies the 128 rows
  to the ULA through 0xF5E0 and 0x89AF the 16 x 14 attribute cells to 0x58A1.
- Writers of the buffers (scan --writers, 600 frames): 0x8B69 (poles erased), 0x8A9A / 0x8AFA (poles), 0x8C4E-0x8C60.. (the scroll); no other routine reads or writes 0xB000-0xBFFF.
- Read-back: tracing every read of 0x4000-0x5AFF over 700 frames, only 0x84FA / 0x8508 (map-pane scroll, cols 17-30) and 0x83F1 (cols 24-27, rows 5-14, 81 reads) read screen memory.
  The left pane (cols 1-14) and its attributes are never read by the game: the view is display-only in these runs (the formal removal experiment, detect.routine-removal, is still to run).
- Clash as the user sees it: the forest / slope edge and the mountain outlines step in 8 x 8 attribute blocks; the poles are black ink on the cell's paper.

**Pace.** 415 updates in 900 frames; update interval min 1.24, median 1.91, mean 2.14, max 5.66 frames (continuous values: free-running, not locked to the frame);
0x8954 takes median 99,486 T of a median 133,498 T update (75 %). Any hook that makes the view cheaper makes the game faster unless the update is padded back
(patch.pace-limiter); the descent's TIME counter ran 1.10 s per 112 frames in the survey shots (to confirm whether it counts frames or updates before the limiter is designed).

**Free memory** (untouched in the 900-frame run): 0x5C49-0x5FC3, 0x91F0-0x9F9E, 0xC000-0xE0FE and 0xE101-0xF549 (the IM 2 vector table is 0xE000-0xE100, vector 0xE0FF -> 0x9F9F);
bank-0 top 16K is otherwise unused by the event. The loader hook (0x6C00, 0x6D00-0x6D03) is outside all of it. IM 2 handler: 378 distinct instructions, 7FFD and AF' used, needs 38 free stack bytes.

**Design (recommended: the hybrid display, patch.hybrid-display-replacement).** The left view moves to Layer 2 as a painted panorama scrolled by hardware:
1. A 256 x 128 painted copy of the 0xA000 bitmap (first an automatic classification into sky / mountain / snow / forest / slope from the pixels and the attribute rows, then
   the user's own painting through the colour-sheet workflow) is uploaded once to Layer 2; NextReg 0x16 (Layer 2 scroll X) follows the game's heading variable 0x82DC.
   The ULA copy of the panorama is no longer drawn: the 0x8C16 scroll and the 0x8BFB reload are replaced by the register write.
2. The poles stay exactly as the game draws them, as ULA pixels (the erase list, the SET loops and the gate list are untouched), over Layer 2: the left pane's attribute paper is
   set to the ULA transparent colour so the panorama shows through and the black poles stay opaque. The HUD, the map pane and the bars stay on the ULA.
3. The update is padded back to the original interval (median 1.91 frames) with the pace limiter.
Rejected: poles as hardware sprites (1 px wide, up to about 100 px tall, several per update: 8 sprites each); Timex 8 x 1 hi-colour (fixes the vertical steps only, and needs the
0x6000 attribute screen where the menu code sits); a Layer 2 re-implementation of the whole renderer (the game's own routines already give the poles and the heading for free).
Risks: transparent-paper priority between the ULA and Layer 2 (hardware to check); the gate colour codes in the gate list (not yet decoded: are any poles coloured?); Slalom and Giant Slalom
(same event code, other courses: not yet surveyed); the other five events have their own renderers (each needs its own stage 0-1).

**The one question for the user:** paint the panorama automatically (clean colours, sky / mountains / snow / forest / slope; a first build in one round) and refine by hand later, or hold the
build until you have painted it? Recommended: automatic first.
