# Dizzy: The Ultimate Cartoon Adventure (Dizzy 1) - Layer 2 figures and player sprites

48K. Engine nexclash/dizzy1.py (`dizzy1_xor`; replaces the old printer-buffer builder
dizzy1_patch.py, which moved only Dizzy to a sprite), hooks asm/dizzy1_hooks.asm, profile
docs/profiles/dizzy1_ultimate_cartoon_adventure.json, colours docs/profiles/dizzy1_colours.json
(Dean's painted sheet, 2026-10-14). Reference files (private repo, specnext/reference/
dizzy_ultimate_cartoon_adventure/): the snapshot (md5 0659328f; selftest input dizzy1.z80),
dizzy1rzx (selftest input dizzy1.rzx), the colour sheets + painting layout, Dean's painted sheet
(dizzy1_PAINTING_SPRITES_painted.png).

## Version 1.2 release (2026-11-07)
Published default art retained; approved Enhanced colours by Jao Paulo (Spec256), optional and off by
default. Graphics match all 78 player and 256 object records; no executable bytes from the colour
conversion. Pixel-key artwork can be imported with `python -m nexclash.dizzy1 enhanced-paint`.
The Enhanced map is a private input, not part of this source contribution.

Both modes use the caller-speed latch, R preservation at every hook/inner continuation, hlib_pace drawing
windows, full hidden ROM and no added DI. Enhanced caches scenery lazily on first figure overlap,
bulk-copies complete colour bytes and skips unchanged pixels. Highest data bank 42, loading bank 43,
hidden ROM 47: both modes fit 1MB. Original movement, sound and collision logic remain unchanged.

| Final engine output (before loading screen) | MD5 |
|---|---|
| dizzy1_sprites.nex | ead92ef747096582da450f162d78e545 |
| dizzy1_enhanced.nex | 1e2853767d0f90cc243352641b1b2df9 |

Source-frozen `selftest.py --game dizzy1 --verify --stamp`: PASS, no ROM-path waiver. Each mode completes
6,346 recording frames, 7,086 converted/1,356 kept object plots and 2,364 player plots. Default: 3,976,720
compared figure pixels, 126 unit cases, 15/15 faults caught. Enhanced: 4,287,960 pixels, 136 cases,
22/22 faults caught. All 780 used ROM bytes match the recording in both patched modes.

Native pace uses completed CALL 59515 (return 59518), three rooms and three seeds, 240 measured updates
per trial with 251 matched states. Percent elapsed-time penalty: negative is faster.

| Mode | Quiet trials | Busy trials | Worst 20-update window |
|---|---|---|---|
| Default | -1.069 to +0.859% | -2.800 to +0.033% | +1.163% |
| Enhanced | -1.846 to -0.020% | -1.732 to +0.042% | +1.095% |

Additional Enhanced death stress: +1.344% busy, +1.522% worst window. Thus within the 2% tolerance,
not a claim of zero penalty at every instant. Sound: ordered FE values/player updates match in two
scenes; every write at 3.5 MHz; uninterrupted same-instruction periods differ by at most 6 T (1.714 us).
Five-minute native soak passes. Flicker: no lost/misaligned sprites or one-frame picture transients;
room redraw yields two transient raw-attribute events versus one originally (warning retained).

Release NXC v1.2 MD5 cea8a16d8931b6157a930522e18017a2; loading NEXs default 9b793fa3e0e709b154f75e687d1ae4c4,
Enhanced b8a8e84e13636c42d732256d34f7afaf. Real .NEXCLASH on disposable v2.10 cards passes default,
Enhanced and Enhanced+four trainers, byte-exact rebuild and native play in each. Each trainer also
passes separate original/default/Enhanced enabled-versus-disabled routine checks. Four fixed-value
archive cheats; user-input POKs omitted. Original loading screen retained. No physical-hardware test
or natural full-game completion is claimed. Original scrolling/rotating effect strips keep Spectrum rendering.

Historical output (2026-10-14):

| Output | MD5 |
|---|---|
| dizzy1_sprites.nex | 38e1a4916eaf8548d9ba8886861ca147 (Dean's painted colours; altrom + Layer 2) |
| dizzy1.nex | 7892b2e0f1f3f9f19165516db307cbe0 (unchanged) |

## Build (2026-10-14, Midnight Resistance standard)
- Every figure the game draws leaves the ULA: Dizzy, creatures, items, carts, clouds, the wizard,
  spider threads, egg + rope dots (every caller of both plotters from the code). Objects show on
  LAYER 2 (Dean 2026-10-14, chosen over hardware sprites): per-pixel colour, exact for every path.
  DIZZY is hardware sprites 0-3, always in front of every object (Dean 2026-10-14, after the first
  hardware test: on one shared XOR layer Dizzy and the grease gun cancelled each other's pixels).
- Hardware round 1 (16a00451, Dean 2026-10-14): runs well; Dizzy mixed with objects he touched
  (fixed: sprite in front); collectables change colour - that is the game's own pulse (the item
  handler cycles IX+15 through 1-7, 56418 / 57625), KEPT by Dean's choice (painted pixels stay
  fixed).
- Hardware round 2 (83ea050d, Dean 2026-10-14): works on hardware, "looks to be perfect".
- Stay on the ULA: room tiles (58546), score digits / lives (62670 / 62691 / 62736), item name
  (60746). Figure pixels inside an effect strip (types 3 / 7: scrolling / rotating rectangles) are
  folded back to the ULA before the effect runs (the original garbles them there too).
- Method: converted writes go to a 1-bit SHADOW screen + shadow attributes (page 26, slot 3 during
  a hook) instead of the ULA, so ULA XOR shadow == the original screen at every moment (XOR is
  linear). Layer 2 shows the shadow: pixel set = the figure's colour, clear = transparent. XOR
  parity (double draws cancel) is therefore the original's by construction.
- Solid figures (Dean 2026-10-14): a figure's ENCLOSED paper (paper pixels not reachable from
  outside the frame through paper, 4-connected - Dizzy's eyes and mouth, the inside of a bottle) is
  opaque black by default, for every figure. A fill shadow (page 27) is XORed with the interior
  bits of each converted write, so the fill appears and disappears with the figure's ink (same XOR
  parity); display only - logic never sees it. Pixel rule: ink -> its colour; else this graphic's
  own interior -> its fill colour (another figure's interior -> black); else transparent; a pixel
  painted transparent shows nothing.
- Painted colours (Dean 2026-10-14): his painted sheet -> dizzy1_colours.json (1,846 pixels
  recoloured, 109 transparent, 633 graphics bytes; nothing ambiguous). 264 painted pixels were
  ignored: black on paper OPEN to the outside of a figure (the door's gaps, one "from the code"
  figure, edge pixels of 13 Dizzy frames). Outside paper is see-through by design; making it solid
  would need the reader to mark painted outside paper as fill (engine change: ask Dean first).
  Done the same day (Dean: outlines): outside paper is now paintable (Colours below); the earlier
  painting's 264 pixels would apply if re-read with a paint_clear layout - Dean's outlined painting
  (79218527) supersedes it.
  Dizzy now takes 92 sprite patterns (88 with default colours).
- Colours: per pixel the painted colour of its graphics bit (plane pages 40-54, 8 bytes per graphics
  byte: 8 colour nibbles, interior mask, transparent mask, has-colours flag; keys: G = plotter 2
  graphics address, D = Dizzy frame 0-38 byte, the shifted copies 39-77 share them). Painting sheet:
  interior pixels are paintable (black by default), and so is every other PAPER pixel of a graphic's
  bytes (OUTLINES, Dean 2026-10-14: "borders will be required in MANY future games"): a paper bit
  painted a colour is drawn opaque in it (fill_mask = interior | painted paper: plane byte 4, the
  fill shadow and Dizzy's patterns), painting it grey again makes it transparent. Only bits of the
  graphics bytes are paintable (paint beyond a graphic's byte span is reported, ignored); on Layer 2
  an outline follows the fill rule above (two figures' outlines on the same pixel cancel by XOR
  parity, another figure's outline over a fill shows black, ink always wins). Painting an opaque pixel (ink or interior) the
  sheet's GREY (RGB 100,100,100, the box background) makes it TRANSPARENT (e.g. inside the grease
  gun's handle), painting a colour back over it undoes that. Else the default: Dizzy bright white; plotter 2 figures that paint their cells
  (B bit 0/1) the bright ink of C ^ 7 (the colour they show on the rooms' white-ink cells; their
  attribute XOR goes to the shadow attributes, so they no longer recolour the scenery); others
  bright white.
- Dizzy: his writes go to his own shadow (page 28; ULA ^ objects ^ Dizzy == the original), not to
  Layer 2. Sprites 0-3 (2x2, 4-bit; 88 patterns built from frames 0-38 with the interiors black and
  the painted colours / transparency; the shifted copies are the same frames 4 px right) at x = 4E,
  y = 192 - L - rows. The sprite follows the XOR parity: a plot of the image shown = the erase, which
  only marks it pending (the draw follows at once in all 1,175 RZX cases, often across an
  interrupt: hiding there would flicker); any other plot = the draw. A pending erase is hidden at the
  next plotter-2 call or room wipe (death / room change). A plot the original skips (y + rows >= 200,
  8 bits) changes nothing.
- Logic reads stay the original's: collision 60244 / 60251 read ULA ^ objects ^ Dizzy (virtual
  read), the attribute read 58712 reads ULA ^ shadow attributes.
- Hooks: alt ROM image 1 at 0x2000- (1,984 bytes incl. the sprite table) (the game reads no ROM byte above 0x0369); variables +
  hook stack 0x5B40-0x5BC0 (printer buffer: never touched by the game, RZX scan; the interrupt
  handler's own stack is 0x5BCF-0x5BFE); tail at 0x5B00. Interrupts stay on: the in-game handler is
  the ROM's 0x0038 (keeps every register, reads IY) at every hook site in the RZX (verify checks it).
- Speed: the game has NO frame sync (no HALT in play, nothing reads FRAMES but the ROM), so hook
  time slows it directly. Both plotter entries switch to 28 MHz for the whole plot and swap the
  return address for a ROM trampoline (t_p2 / t_dz: dead slot rewritten with the original value,
  back to 3.5 MHz); the small hooks switch speed at their first / last instruction. Measured over
  the RZX: see the auto Speed line and docs/VERIFICATION.md (the median frame is faster than the
  original; a room change pauses up to about two frames longer: the wipe folds three shadows).

## Recolour (legacy/default map)
`python nexclash.py recolour dizzy1_sprites.nex PAINTED.png` uses the adjacent paint_clear layout
(or `--layout`) and writes a new painted NEX/map without overwriting the input. Only the colour
banks change; original game behaviour and verification are retained. The engine checks hook bytes,
patch sites, facts, interiors and graphic-input MD5s before recolouring. The selftest compares
recolour with full builds for both the default and empty maps. Grey RGB 100,100,100 means transparent;
only pixels within each graphic's byte span can be painted. Historical layouts without paint_clear
cannot import outside-ink outlines. To change the default map, update dizzy1_colours.json and rebuild,
verify and stamp. Enhanced uses `enhanced-sheet`/`enhanced-paint` and its own private map instead.

## Facts
- Snapshot: PC 63496 (title), IM 2 (I 0xFE; vector JP at 65021, rewritten by the game: 63578 =
  title music handler, which DECs the interrupted B / C and sets carry; 0x0038 = ROM handler in
  play, set at 63611), EI, SP 65534; the game stack in play is 23549 down to 0x5BCF.
- Plotter 1 (Dizzy) 58113: pure XOR, entered 59488 (erase) / 59515 (draw); screen write 58184;
  frames 0-38 + pre-shifted copies 39-77 (exactly frames 0-38 four pixels right, checked); graphics
  24290-29049 (crosses into slot 3: hooks read the byte before slot 3 changes).
- Plotter 2 57983: byte-aligned, clips to columns 1-30, frame table 53148 / data 43485, 256 frames
  (font 0-40, room tiles, objects). Attribute routine 58702 (B bit 0 before / bit 1 after, colour C).
  Self-modified by the game: 58079 = XOR C (0xA9) / OR C (0xB1) / LD A,C (0x79) and 58709 = XOR (HL)
  (0xAE) / NOP (0x00): the room renderer (58460) uses OR / LD and NOP for its tiles, 58575 restores
  XOR; 58010 = row helper 57771 or 57797 (clipped rows, 54811 from 56946 / 56972 / 57433; 76 calls
  in the RZX). The hooks compute the original's new byte from the virtual old one for every mode.
- Every caller of plotter 2 (static scan of all RAM + RZX): 54805 (object records: 256 x 20 bytes
  at 38365; +1 x, +2 y, +3 frame, +4 type, +6 animation, +15 colour; drawing types 1, 2, 4, 5, 6,
  8; 23 call sites via 54766 / 54762 / 54811), 54958 (spider threads, frame 73), 58546 (room
  renderer), 60698 / 60723 (egg + rope dots, frames 160-164), 60746 (item name), 62670 / 62691
  (score digits), 62736 (lives). Plotter 1: only 59488 / 59515. Every screen-addressing routine
  uses the line table 23750 (built at 58197): the plotters' row helpers, the wipe 58634, the effects
  55964 / 56092 / 56178 / 57104, the collision probes 56542 / 60158 (which read through 60228).
- Logic reads figure pixels only in the collision test 60228 and figure-coloured cells only through
  58712 (callers 56676, 58436, 60132, 60215: 884 reads of a figure cell in the RZX).
- Room wipe 58634 (lines 40-183, columns 1-30) + attribute wipe 58666 (rows 5-22): the hooks fold
  the shadow there first (ULA ^= shadow, shadow = 0, Layer 2 cleared; the game zeroes the ULA next).
- Executes `LD R,A` (machine.py re-runs such frames with exact counting).

## Verification (2026-10-14)
`auto` with dizzy1.rzx: every hooked routine forked from the real state (whole plotter calls to
their return, attribute reads, wipes; segments for the collision reads and effect folds), original
vs patched compared: all registers (AF' included), all memory, screen / attributes as ULA ^ shadow
== the original, Layer 2 pixels against an independent Python model of the shadow and colours;
per hook instruction IY / I / IFF / IM / alternate set unchanged, hook stack room for an interrupt,
no pushes below the game SP, slot 3 and 3.5 MHz restored, no fetch at 0x3D00-0x3DFF; the ROM
handler installed; no unhooked instruction reads or writes a byte / cell holding figure bits; the
game never writes a patch site; patch-site interiors only reached sequentially. Unit tests (paths
the RZX misses or reaches without figures): every plotter mode (XOR / OR / LD x attribute XOR /
NOP) converted and kept, kept / HUD / converted / Dizzy draws over figure bits, rows past line 191,
attribute and collision reads outside the screen, every effect branch with figures inside run to
its end, wipes with figures everywhere, a synthetic colour map (incl. the shifted Dizzy copies and a
wrong check byte); negative controls: no virtual read, no fold (rotator, wipe), room renderer
converted, hook stack too deep, colour map left out. Results: docs/VERIFICATION.md.

## Hardware checklist
No physical test is claimed for version 1.2. On the exact release build check title/beeper sound,
walking/jumping, solid figures over scenery, item pickup/collision, clean room changes and deaths,
all-lives-lost/title/new-game reset, both colour options, and each trainer. Scrolling strips retain
the original rendering. Historical hardware reports below apply only to their named older builds.

## Open
- Version 1.2 needs a physical test and a recording of later rooms/natural completion.
- Original screen-copy/rotate effects retain Spectrum rendering; editable pixels cannot exceed their
  graphics byte span. Dense player paintings can exceed the 128-pattern limit (the build refuses them).
- Archive POK value-input options are not supported by the package menu.
- The older `preview` command uses default colours; use the Enhanced sheet/export path for Enhanced.

## Speed restored (2026-11-07, shared engine refactor, goal 2)
- Three latches (HLIB_SPEED_IN): V_SPDP for plotter 2 (e_p2 .. t_p2), V_SPDD for the Dizzy plotter (e_dz .. t_dz) and
  V_SPDH for every other hook, since those can run inside a plotter's 28 MHz window. Each latch is taken on the hook
  stack, after the switch, so the game's dead stack stays as the original's. Exits give the speed back instead of
  NEXTREG 7,0 (t_p2 / t_dz and the collision reads through V_A, keeping A and the flags).
- The verifier's hook simulator answers NR reads (0x243B / 0x253B) from its NextREG state; before, a read gave 0xFF.
  HSTK_MIN (the lowest hook SP allowed) was 0x5B58 + 18 while the variables already ran to 0x5B65: now 0x5B6A + 18.
- Sprites 6ac7a3d6 -> 07d09c80; plain unchanged. dizzy1.rzx PASSED (6,346 frames, 7,086 plotter-2 calls converted,
  2,364 Dizzy draws, 2,050,456 figure pixels), unit 55 cases, negative controls 11/11; stamped.
- JNext pace: not measured. The game has no frame sync, and the automatic probe found no routine run 2-50 times a
  second in play (Space-to-start profile).

## Pace back to 1.0's (2026-11-08)
- Problem: with the speed restore (07d09c80) the game ran 1.3-1.7% slower than the original and 1.6-1.8% slower than 1.0
  (JNext pace, seeds 2 / 3 / 5). The game has no frame sync, so every T at 3.5 MHz in a hook is game time. JNext counts
  per update (seed 2): collision reads 60244 / 60251 10.7, plotter 2 2.6, Dizzy plotter 1.0, attribute read 0.7, type-3
  effect 0.1. HLIB_SPEED_IN needs the hook stack, so it ran after the stack switch: 97 T at 3.5 MHz plus the code
  before it (e_ar: its whole cell-address copy, ~190 T), where 1.0 had a 20 T NEXTREG 7,3 first.
- Fix 1: DZ_SPEED_IN (engine-local macro), every hook's first instructions: LD (V_A),A / LD A,0x25 / IN A,(0x3B) /
  NEXTREG 7,3 (51 T at the caller's clock, no stack, flags kept), the raw NR 7 byte kept in V_RAW; spd_p / spd_d /
  spd_h latch it on the hook stack at 28 MHz. Port 0x243B stays selecting NR 7 (setup selects it at start); a read
  without NR 7's layout (bits 7-6 and 3-2 set: the selection was moved, by an NMI say) keeps the latch's last speed
  and selects NR 7 again. e_ar runs its copy at 28 MHz; its exit switches the stack back before the speed.
- Fix 2: the collision routine 60228 (CALLed from 56647 / 60037 / 60099; 29 bytes checked) is one hook, e_col, run
  whole at 28 MHz (PUSH BC / PUSH HL written to the game stack as the original, the virtual read, AND 240 / AND 15,
  POP / POP / RET), instead of two hooks per call at 60244 / 60251 around a routine at 3.5 MHz. That gives back the
  51 T the latch still costs over 1.0's switch.
- Verifier: ENTRY (entry speed, 0x243B selection, other NextREGs) for every hook pair; exit speed = entry speed and
  0x243B left at NR 7 checked on every pair. Unit cases: every hook kind entered at NR 7 = 1 / 2 / 3, the effects at
  1, every kind with the selection moved (NR 0x53 selected: last speed kept, NR 7 selected again), the collision
  routine on both nibbles over figure bits and off the screen. New negatives: a moved selection taken as NR 7, and
  t_p2 exiting at a fixed 3.5 MHz. HSTK_MIN 0x5B6B + 18 (V_RAW at 0x5B6A).
- JNext pace (nexclash.pace, probe 58113 = the Dizzy plotter, once per update; the plain build as the original; no
  lockstep check, as before). Penalty, all / quiet third / busy third:

| build | seed 2 (340 upd.) | seed 3 (100) | seed 5 (340) |
|---|---|---|---|
| published 1.0 (68c1317a) | -0.28 / -0.42 / -0.33% | - | -0.05 / +0.03 / +0.11% |
| speed restore 07d09c80 | +1.34 / +1.21 / +1.32% | +1.69 / +1.94 / +1.86% | +1.70 / +1.72 / +1.99% |
| fix 1 only 6392675b | +0.32 / +0.15 / +0.28% | +0.43 / +0.64 / +0.49% | +0.52 / +0.59 / +0.69% |
| fixes 1 + 2 953cf4e7 | -0.33 / -0.51 / -0.39% | -0.27 / -0.00 / -0.01% | -0.15 / -0.07 / -0.03% |

- Sprites 07d09c80 -> 953cf4e7; plain unchanged. dizzy1.rzx PASSED (6,346 frames, 7,086 plotter-2 calls converted, 2,364
  Dizzy draws, 40,881 collision calls, 2,050,456 figure pixels), unit 83 cases, negative controls 13/13; stamped. Replay:
  hooks add -1,204 T a frame (median of the frames with hook work, 28 MHz parts / 8). JNext loader run (private card copy): menu v1.1, title, play; /tmp/NEXCLASH.NEX = the bare .nex.

## Lessons
- [local: Enhanced intake, 2026-11-07] The colour conversion's graphics match all 78 player frames and 256 plotter-2
  images, but its snapshot differs in state, title data and the lives instruction. Import colours by graphics address;
  never copy its executable snapshot. All 36 existing patch-site/fact checks match.
- [local: refresh audit in pilot dizzy_enhanced/work/audit_refresh.py] The inherited CMP excluded R. Including R exposed
  differences at seven hook sites in the first 400 replay frames; the legacy result was not an R proof; the new hooks and verifier cover it.
- [local: pilot dizzy_enhanced/work/pace-profile.json] Use the draw call at 59515 for player updates. The old 58113
  probe counts both erase and draw. Check position, animation, room and lives at each update; reject divergent trials.
- [local: this engine's hook RAM] The verifier's lowest-SP bound named the variables' end as 0x5B58 while they ran to
  0x5B65 (observed in the code): corrected with the new latch bytes (0x5B69).
- [card patch.restore-speed §Failure lookup] A short hook can run inside a plotter's 28 MHz window: a latch per window
  (three here), as the card's "a latch per level" row says.
- [card patch.restore-speed §Failure lookup] In a game with no frame sync the latch's own time is game time:
  HLIB_SPEED_IN after the stack switch cost 1.6% here (15 hook calls an update). Read NR 7 first without the stack
  (51 T), latch at 28 MHz, and hook a whole small routine rather than its reads (measured, JNext pace).

- [local: original-draw coverage] Check display pixels touched by the original as well as by the patch. A missing
  scenery hook writes nothing; following only patched writes let that negative control escape.
- [local: multi-room pace] Opening-room timings missed a room-transition penalty. Bench original-recording room
  starts separately, at the player draw call, with state equality and repeated quiet/busy trials.
- [local: scenery cache] A cleared validity flag makes backing pixels transparent. Read neither stale colours nor
  a stale OR tile after a wipe; compare the effective backing pixels and catch missing invalidation.

- [local: native update observer] A JNext execute event can occur both before and after an accepted interrupt at
  the same CALL. Rearm at the actual return; count completed player updates, never both notifications.
- [local: input schedule] P pauses this release. Use Z/X/SPACE, and allow ten idle updates before input because
  the first two recorded-start draws can be less than one video frame apart while key changes are frame-queued.
- [local: lazy backing] Flag 2 means scenery is still in visible Layer 2; materialise its backup only at first
  overlap. Compare the effective backing, poison the unused storage, and detect missing materialisation.
- [local: sound evidence] Compare ordered FE values at matched updates and periods at the same OUT instruction.
  Port counts per wall second alone mix game pace with pitch; report interrupt-free edge variation separately.
- [local: trainer intake] POK value 256 requests user input. Omit unsupported value-input trainers explicitly;
  do not turn them into zero pokes. Translate the lives address by checking the actual DEC A instruction.

## Technique use
- patch.restore-speed: helped: three latches, one per window (2026-11-07); its 97 T latch was too slow for a game
  without frame sync: an engine-local 51 T first-instruction read (2026-11-08).

## Friction
- reuse: [tool asm/lib/hlib_speed.asm] the shared latch macros
- retries: [local: repeated native quiet/busy and death-stress trials exposed extra scenery/particle cost; optimisation candidates remain in the private pilot evidence]
- environment: [local: JNEXT_CONFIG_DIR isolates JNext without changing HOME; master cards are read-only, actual-loader tests use disposable copies]
- hand-rolled: [local: a JNext profile for the pace (start keys from screenshots), kept in the pilot run folder]
- scratch: [none: no scratch scripts in the repo]

## Next session
- Stage 3 complete: version 1.2 on game/dizzy-enhanced from main c09c54d. Full stamped acceptance,
  repeated native pace, sound, soak, and three-mode disposable-card loader checks passed.
- Packaging handoff and exact outputs are in the private pilot runs/dizzy_enhanced folder.
  Keep the approved colour map and published default art; do not overwrite DIZZY_PAINTING_SPRITES.png.
- Physical testing and natural full-game completion remain unclaimed. No pushes or shared-card writes.

## Stage log
- 2026-11-07: Enhanced intake; fetched main, matched the published release and all graphics, produced three-room
  colour proposal, audited inherited refresh/pace checks. Jon approved the proposal; full source-frozen verification, native checks and release packaging passed.
