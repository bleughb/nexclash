# Monty is Innocent (Gremlin Graphics, 1985, 48K) - new engine

Techniques: `detect.gameplay-screen-readers`, `detect.graphics-record-layout`, `patch.xor-overlay-keep-ula`, `patch.whole-altrom-image`, `patch.restore-speed`

## Next session
Stage 3 (prove + deliver) done 2026-11-22; Stage 4 (hardware + colour rounds) next. First release = clash fix
(figures as sprites in the game's own colours, the guard painter off) + checked cheats. Inputs (local, not in the
repo): rzxarchive montyinnocent.rzx (6,241 frames, 128K machine, the 48K game), its snapshot extracted; the release
targets TOSEC "Monty is Innocent (1985)(Gremlin Graphics Software).z80" (48K, the game running; same code). Survey:
803dad54 scratchpad innocent/survey/. Release: jattree/nxc patch 1.0 (sprite build MD5
d0db334343c56eda63414a5615e4250e), pushed when the owner's quick test passes. Evidence record docs/records/monty_is_innocent.json
(verified + stamped 2026-11-22; reference files to be added to specnext). Open: a longer recording (later rooms, the
gun, a guard caught), a board run of this build.

## Observed engine (static reading + probes)
- One XOR plotter 0xD52E (54574): the previous image at the old place ((24960) image, (24958) x, (24959) y; y 195 =
  none) and the new one (HL, C x, B y), 24 rows x 3 bytes, bottom row first at screen row 191 - y, pre-shifted for
  x & 6 (+144 a step). 20 call sites: Sam Stoat (the player: 56130 moves, 55673 first draw), Monty (later rooms:
  55139 / 55746), guards (54955 / 54897 / 52378, IX = record at 24962 + 8k: +0 y, +1 x, +2/3 image, +6 ink),
  and panel icons, room items, the title and the ending, which stay on the ULA.
- Guard painter 0xD5D8 (store 54766): over a 3 x 4 block, cells whose ink equals E get ink D. The guard routine
  restores its old area (ink -> 7) and paints the new (7 -> ink) each time it enters new cells: the clash.
- Only the painter changes attributes in play (probe: the room fill 54707, the clear 55526, the tile printer 54681
  aside). Composite screen pixels are read only by the plotter's own XOR. The game runs code at 0x5B00 (JP 23296).
- Screen clear 55506 runs before every room and the ending.

## Design (standing default: figures as sprites in the game's own colours, colour paint off)
- Overlay: every pixel write stays; figure f (0 Sam, 1 Monty, 2-4 guards) = four 16 x 16 4-bit sprites 4f..4f+3
  over the drawn 24 x 24 image (bytes 0-1 / byte 2, rows 23-8 / 7-0), chosen by the caller's return address
  (guards by IX). Guards in their record's ink, Sam and Monty white.
- Sites: 54574 PUSH HL/BC/DE -> JP e_plot (stateless; resumes at 54577); 54766 -> NOP; 55506 -> JP e_cls (hide 20).
- Start-up: tail below SP (0x5FFF, dead stack: never read before written), printer buffer kept (the game's code).
- Pace: a fast path (every row on screen, no per-row checks, lower sprites' clear rows not rewritten) brought the
  hook from 33,300 to 14,800 T at 28 MHz a plot: about 3% of a frame at 3.5 MHz.

## Verification (nexclash/monty_is_innocent.py)
- Events at every hook and every painter call (original vs patched from the same state, registers but R, all RAM;
  the patched painter writes no attribute). After each figure plot, the figure's XOR layer against its four sprites;
  a first draw (old y 195) or a screen clear starts a figure's layer.
- Full recording, 6,241 frames: IDENTICAL. 7,846 plots (7,531 figure plots), 38 screen clears, 1,989 painter
  calls, 1,015,749 sprite pixels compared, 3,806 attribute bytes not painted. 328 unit cases ok; 6 broken builds
  caught (wrong row, ink lost, hook silent, clear leaves sprites, resume late, painter on).
- Board (Tang, hov2-p1r2, dirty sprites + automap on): the build before the speed-up loads and runs its menu; the
  board's key input did not get past the menu (as Monty on the Run).

## Cheats (archive .pok, each checked against the code)
Infinite lives 56473 DEC A -> OR A; Guards do not catch you 56440 (the death routine reached by JP from the guard
collision test, 54804) -> RET.

## Lessons
- [local: verifier and the fast simulator] the C replay calls before() only at hooks and interrupts: an interior of
  a patched entry hit once means an interrupt between its first instructions; accept sequence and interrupt returns.
- [local: negative controls] a broken hook can run away in the event simulator: event() reports it as a failure.
- [local: this game's player is not Monty] check who a figure is (render its images) before naming it in player-facing notes.

## Friction
- reuse: [local: the evidence record staged from the scratchpad (TOSEC snapshot, rzxarchive recording, archive .pok)]
- retries: [local: the record's first rebuild gave the output MD5s; they were written in and the views regenerated before the stamp]
- environment: [local: the reference files are not yet in specnext; the record was verified from a scratch reference folder]
- hand-rolled: [none: the record was written with the records module's own checks and selftest]
- scratch: [none: the staging script stays in the session's scratchpad]

## Technique use
- detect.gameplay-screen-readers: helped: `scan --writers` showed only the plotter reads figure pixels.
- detect.graphics-record-layout: used: guard records (position, image, ink) found from the plot callers.
- patch.xor-overlay-keep-ula: used: the plotter's XOR kept, four sprites per figure over it.
- patch.whole-altrom-image: used: Sinclair's 48K ROM as the alt ROM image, hooks at 0x386E.
- patch.restore-speed: used: 28 MHz inside each hook, back to 3.5 MHz on the way out.
