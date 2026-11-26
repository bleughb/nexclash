# Winter Sports (Electric Dreams Software, 1985) - engine `winter_sports` (six events in one .nex; Downhill on Layer 2)

## Next session
Stage: 3-4 (plain .nex played on hardware; sprites build: Downhill / Slalom / Giant Slalom on Layer 2, simulator + JNext only)  State: 2026-11-22
Inputs: specnext/reference/winter_sports/ (menu .z80, .tap, [h].tzx, the delivered .nex); the user's files, no RZX
Start with: the same treatment for the other five events one at a time (each has its own renderer: survey first); the sprites build is hardware-confirmed
Read: ## Downhill stage 1, ## Downhill stage 2, ## Evidence
Open: events 1-5 (Ice Hockey, Ski Jumping, Speed Skating, Bobsled, Biathlon); hand-painting of the panorama (the automatic paint is a first pass);
the Bleepload re-release is not an accepted tape set (its SCREEN$ is inside the turbo loader)

    python nexclash.py auto winter_sports.z80 --tape "Winter Sports (1985)(Electric Dreams Software).tap" --no-record

Outputs: `winter_sports.nex` (plain, byte-identical to the hardware-tested file) and `winter_sports_sprites.nex`.

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
  event A -> Exit -> event B works. The rebuilt .nex is byte-identical to the delivered one (md5 8dc688fa980454c63f98bc0e802d5f88; `auto`'s plain
  output adds the DivMMC automap-off start: 518144ff82bc534b5fa33a7df8d49176, the record's).
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
  self-modified SET n,(HL) (0x8A9A, 0x8AFA, 0x8B1A) from the gate list at (34757) (3 bytes per gate: two position values and a kind that the code compares with 2, 3 and 4: meaning not yet decoded); then 0x8999 copies the 128 rows
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
Risks: transparent-paper priority between the ULA and Layer 2 (hardware to check); the gate kinds 2-4 in the gate list (not yet decoded: do they change how a pole is drawn or coloured?); Slalom and Giant Slalom
(same event code, other courses: not yet surveyed); the other five events have their own renderers (each needs its own stage 0-1).

**The one question for the user:** paint the panorama automatically (clean colours, sky / mountains / snow / forest / slope; a first build in one round) and refine by hand later, or hold the
build until you have painted it? Recommended: automatic first.

## Downhill stage 2 (the build, 2026-11-22: auto-painted panorama on Layer 2)
The user chose "auto-paint first". Code: nexclash/winter_sports_dh.py (hooks, patch of the event-0 block), nexclash/winter_sports_paint.py (the painter).
- **What changes** (event 0 only; the block is patched in the embedded copy, every site checked against its original bytes): 0x8C16 (the scroll) becomes `JP 0x9400`;
  0x8BF6 (`LD A,56 / LD (35818),A`, the heading's start value, once per run) becomes `CALL 0x9491` + 2 NOPs; the panorama at 0xA000-0xAFFF is zeroed (the game's buffer then holds only poles);
  the 16 x 32 attribute map at 0xB000 becomes 0x78 (ink black, paper white, bright); the hook, its variables and the 16-entry pad table sit in 0x9400-0x95xx (zero in the tape block, untouched in the runs).
- **Hook** (154 bytes including INIT): the first call enables the view (NextReg 0x12 = 28: Layer 2 in banks 28-30; 0x15 = 0x08 "SUL": ULA over Layer 2; 0x18 clip window x 8-119, y 40-167;
  0x14 = 0xE3, 0x43 = 0; ULA palette entry 31 (bright paper 7) = 0xE3 so the pane's paper is transparent; 0x69 = 0x80). Every call it does what the original did with the heading
  (`(35818)` = heading), keeps the original's counter (35815) and its own view count (one pixel step per call whose heading differs, as the original: it lags a fast turn), pads the step to the
  original's measured time (50,232-53,881 T by the counter, table at 0x9508) and writes NextReg 0x16 = 120 - view. The menu's loader hook (hybrid build only) switches Layer 2 off and puts palette entry 31 back to white before every event load.
- **Panorama:** the 256 x 128 bitmap (1 = the game's ink) is classified (sky above row 24, clouds, mountain, ridge lines, forest, dithered haze, slope) and painted with gradients, ordered-dithered to RGB332 (0xE3 never used);
  rows 40-167 of the 256 x 192 Layer 2 picture. Where the painting is wrong or dull, say so and it is changed in the painter (or painted by hand later).
- **Evidence.** Simulator (`verify_downhill`): the same key script (start, a run, two turns, 3,600 frames) through the original and the hybrid: the original's own panes sit at the
  one-pixel-step model's position at 581 / 581 updates, the hybrid's Layer 2 scroll register at 580 / 580; update counts 581 / 580; at the 412 updates where heading, last-seen heading and scroll
  agree the hybrid's ULA pane OR the panorama window equals the original's pane at 401 (11 have a pole one pixel off while the heading changes: the heading is read at two different instants and the interrupt lands
  differently); the heading by update is not compared (a one-update shift drifts). `unit_downhill`: the 16 steps take the original's T within 150, the counter and view move as the original's, NextReg 0x16 = 120 - view,
  an unchanged heading takes < 400 T. Negative controls: a wrong-sign scroll register fails every update, a rotated pad table fails 15 of 17 cases.
  JNext 1.2.0: Downhill, Slalom, Giant Slalom play with the painted panorama at the same game state as the plain build at the same frames; GAME OVER, then the options, Exit, Ice Hockey: no panorama, no magenta,
  the rink as in the plain build. Hardware (user, 2026-11-22): the sprites build tests and plays OK on a real Next (the transparency and clip-window risk did not bite). Not covered: the other five events.

## Event plugins (the contract for converting Ice Hockey, Ski Jumping, Speed Skating, Bobsled, Biathlon; 2026-11-22)
**Priorities (user, 2026-11-22), in order.** (1) The DEFAULT build of every event is smoother, similar gameplay in the ORIGINAL 16 colours: the speed of play stays the
original's, the picture may be redrawn per pixel (Layer 2, sprites, hi-colour, whatever removes the attribute clash) but only the 16 Spectrum colours
(winter_sports_common.SPECCY) appear. (2) Anything beyond that (extended colours, painted scenery, effects) is an OPTION the player turns on in the .nxc menu, never the default.

**How options reach the player.** One .nxc holds the whole game: the default build, one colour set ("Enhanced": every plugin's extended colours together) and the toggles
(an .nxc has at most 4 toggles for the whole game; "Original pace" is the first). A set or toggle is the byte difference from the default, so its bytes must be picture data / flag
bytes the default does not share with another option (nxc.py refuses overlapping writes). Plugins therefore take `enhanced` and `original_pace` and put extended colours in their own
picture banks (BANK_PLAN) and the pace flag in one data byte. NAME_outputs.json (winter_sports.auto) tells nxcout what is what; `make_nxc` builds NAME.nxc for the TAPE as target with the
menu snapshot as start state and reads every combination back.

**A plugin** is nexclash/winter_sports_<event>.py (see winter_sports_dh.py, the worked example, and winter_sports_dh_test.py) with `INDEX`, `BANKS` (inside BANK_PLAN[INDEX]), `patch_event(block, enhanced,
original_pace) -> (block, {bank: bytes})`, `disable_code()` (NextReg writes the menu's loader hook runs before ANY event loads: put the display back), `tests(patch, z80, say) -> (ok, lines)`, and a line in
`winter_sports.PLUGINS`. Helpers: winter_sports_common.py (`Asm` assembler with labels, `Block` (checked reads / writes by runtime address), `SPECCY`, `pace_wrapper`, `CADENCE`).
The shared parts are measured and tested once (the loader hook, the loading screen, the NEX layout); a plugin owns only its event's bytes: patch sites are checked against the original bytes, hook
code goes in free bytes of the event's own block (find a zero run in the tape block that no run touched: survey `scan --writers`), variables there too.

**Rules learned in Downhill (apply them, or say why not).**
- Find the game's per-update loop and its drawing call first; the cheapest honest pace fix is the wrapper `pace_wrapper(call)`: halt to the frame interrupt, draw at 28 MHz (NextReg 0x07 = 3) inside the vertical
  blank, 3.5 MHz back; the game's own sound / timing loops (the beeper routine at 0xFE44 runs with interrupts off) must stay at 3.5 MHz, so only the drawing is sped up. Measure the original's update interval over a run
  (mean, spread) and pick the cadence whose mean is within a few percent (Downhill: 2.24 frames per update originally, cadence 2).
- Prove display-only before replacing a display routine: trace every read of the screen / attributes / buffers (`simrun` hooks, `on_read`); what the game reads back must stay as the game writes it.
- The ULA transparent trick (bright white paper = NextReg 0x14's colour 0xE3, NextReg 0x15 = 0x08 ULA over Layer 2, a clip window): works on hardware (Downhill, user 2026-11-22). Layer 2 uses banks via NextReg 0x12; its
  palette is the default RRRGGGBB; `SPECCY` values are the toolkit's 16 colours (do not use 0xE3 except as transparent).
- Test as Downhill does: the same key script through the original (tape served at ROM 0x0562) and the build, per-update comparison where the runs can be aligned (scroll / state models, not heading by update),
  unit tests calling the hooks with measured T-states, negative controls that must fail. `winter_sports._sim` models NextReg 0x50 and 0x07; `_exec` in the Downhill test module adds HALT and the 28 MHz time scale.
- JNext (script frames = program frame + 500; screenshot frames = program frame) for the pictures: C:\1NEXT\wintersports_work\jrun.py / jall.py; event snapshots from tapeload.py / runall.py.

**Banks.** Events 12-26 (tape blocks), 27 (menu screen), per plugin BANK_PLAN: 0: 28-30, 1: 31-33, 2: 34-36, 3: 37-39, 4: 40-42, 5: 43-45 (banks 46/47 are the alt-ROM sources of other builds: never).

## Events 1-5 (2026-11-22): pace-only plugins
Ice Hockey (nexclash/winter_sports_ice_hockey.py), Speed Skating (_speed_skating), Bobsled (_bobsled) and Biathlon (_biathlon) are plugins built on winter_sports_pace.PaceEvent: each of the event's screen-copy call
sites becomes a wrapper (winter_sports_common.draw_wrapper): halt to the frame interrupt (N frames where the loop is free-running), the copy at 28 MHz (NextReg 0x07 = 3), 3.5 MHz back; the
beeper (blocking, interrupts off) is never sped up (tests: no port 0xFE write while fast). Per event, found with C:\1NEXT\wintersports_work\findloop.py / freecheck.py (work folder, not in the repo):
- Ice Hockey: 0x7809 (the rink, 423,000 T) from 0x7FC1 and 0x8063; halts 5; interval 6.80 -> 6.40 frames (-5.8 %); wrappers 0xF42A, mode byte 0xF48A.
- Speed Skating: 0x8BFE (78,600 T) from 0x84C3 (loop 0x841E..0x84F1, interrupts on after 0x848F); halts 1; 9.10 -> 8.50 (-6.6 %); wrapper 0xC390, mode byte 0xC3C0; the race starts with SPACE on the ready screen (port 0x7FFE bit 0 at 0x8415).
- Bobsled: 0x87E6 (a row-blit, 28,400 T) from 0x7A43 (`DI / CALL / EI`, the run), 0x8446, 0x8554; self-paced (its delay loops set the speed: 8 frames per update at a standstill to 2 at speed), halts 1; 2.29 -> 2.23 (-2.8 %); wrappers 0xC390, mode byte 0xC420.
- Biathlon: 0x81E8 (set-up + the 152,000-byte copy 0x80FD) from 0x8270 and the attribute copy 0x8202 from 0x8273; halts 1 / 0; 11.46 -> 11.25 (-1.9 %); wrappers 0xACAE, mode byte 0xAD0E; SPACE starts the race (0x89B1).
Free memory: only zero runs that stay zero through menu, options and a run (freecheck): the runs at 0x9E3D-0xABFF of events 1-4 are written when the event starts and must not be used.
Tests per plugin (winter_sports_pace.PaceEvent.tests): the key script through the original (tape served at ROM 0x0562) and the build, update interval mean within 8 %, no beeper write at 28 MHz, 3.5 MHz restored at every marker, each wrapper transparent
(from a copy of the build's state, halts NOPed, its registers and memory equal the plain call's), negative controls (a wrapper that leaves 28 MHz on; one that calls a bare RET instead of the routine) caught.
**Not done:** Ski Jumping stays the plain conversion: the jump needs a key at the right moment (the loop at 0x864F is the GAME OVER exit; without a key the jump ends GAME OVER by ~frame 2200) and its jump control was not found; no per-pixel clash fix and no Enhanced colours for events 1-5; no
hardware test of events 1,3,4,5 and of the new Downhill default. Events keep their original colours; the Enhanced set changes Downhill only.

## Lessons
- [local: this game's pace] An event's pacing decides the smoothing: Downhill is free-running (an even cadence of halts at the original's mean fits), Bobsled paces itself with delay loops (a single halt, never a cadence), Ice Hockey and
  Speed Skating are draw- or logic-bound (halts chosen by measuring the mean interval). Measure the original's update interval over a run before choosing, and compare means within a few percent.
- [local: this game's free memory] A zero run in a tape block is not free: Bobsled's and Ice Hockey's runs at 0x9E3D-0xABFF are written when the event starts (the snapshot is taken after that). Only use runs that stay zero through
  menu, options and a run (freecheck over the whole flow, from the menu).
- [local: this game's keys] A snapshot that sits in a delay loop is waiting for a key: Speed Skating and Biathlon start the race on SPACE (port 0x7FFE bit 0), Ski Jumping's loop at 0x864F is the GAME OVER exit. Read the port the loop polls before guessing keys.
- [none: the shared wrapper (winter_sports_common.draw_wrapper) and the pace plugin (winter_sports_pace) are in this game's engine modules; no other game uses them yet]
- [local: a speed latch must not sit on the timed path] The wrappers wrote NR 7 = 0 after every drawing and the
  display-off code did too (F8 lost; Codex review C6). A latch read after the halt moved Speed Skating's frame-edge
  pacing by 3 % (-6.0 % -> -8.8 %, over the 8 % limit); SPD_IN now runs before the halt and writes the player's speed
  into the wrapper's own exit NEXTREG 7,n, so after the halt the wrapper runs as before.
- [local: an event load must not undo the menu's speed] SPD_OUT restored the latched speed at every event load, so an
  F8 in the menu was undone (Codex review). It restores only while a drawing was left unfinished: SPD_IN clears the
  ACT mark before the halt, the wrapper's exit sets it with LD (nn),SP (no register or flag touched). Wrapper slots
  grew from 44 to 48 bytes (the mode bytes above moved with them).

## Technique use
- patch.hybrid-display-replacement: helped: Downhill's left view (display-only, proven by read-back tracing) moved to Layer 2 with the game's own pole drawing left on the ULA (2026-11-22)
- patch.pace-limiter: no help: events 1-5 use a halt-to-interrupt wrapper with the drawing at 28 MHz instead; Downhill's pad table is the limiter's original-pace form (2026-11-22)
- detect.routine-removal: no help: read-back tracing of screen / buffer reads (simrun on_read) answered display-only without removing the routine
- patch.restore-speed: used: a latch per window (the player's speed written into the wrapper's exit NEXTREG), read
  before the frame wait so the timed path stays as it was

## Friction
- reuse: [tool nexclash.winter_sports_pace] the tear-free fast-draw plugin (wrapper, transparency test, negative controls) is generic for events that copy their screen with one routine
- retries: [local: this game's key flows] several runs to find what starts each event's race (SPACE on the ready screen) and which zero runs are really free
- environment: [none: no workaround needed]
- hand-rolled: [local: this game's work folder] callprof / findloop / freecheck / varwatch / tapeload / jrun scripts in C:\1NEXT\wintersports_work were hand-rolled for the surveys and JNext pictures
- scratch: [none: the scratch scripts answer game-specific questions; the reusable parts are in winter_sports_pace and winter_sports_dh_test]
- retries: [local: the speed latch lesson above] the first C6 latch (after the halt) failed Speed Skating's 8 % limit
