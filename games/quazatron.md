# Quazatron (Hewson, 1986; 48K) - colourisation, engine not yet built (stages 0-1, emulator only)

## Next session
Stage: 4 (hardware + colour)    State: v1.2 published (jattree/nxc ea2a22f, the pilot clone's 9248a85), upstreamed
2026-11-07 (engine refactor session 3). The engine now runs the shared pace library (hlib_pace, nested hooks) in place
of its own limiter: v1.3, a review build only, not published, not yet played by the owner (below, "Shared pace
library"). Emulator only; no board run. Open: Centred view's edge cells (821 of 14,765 frames show a few pixels no
view drew).
Inputs (pilot run folder runs/quazatron, private): the archive's "Quazatron (1986)(Hewson Consultants)[aka
Ziggurat].z80", md5 ac51eb58af87fdac9c0c7077db98c90a; recordings work/b1, b2, c1, s3/d1, u2, u3, s8/t5, r6, r7, r8.
Start with: pilot runs/quazatron/HANDOFF-SESSION10.md; proofs: work/s10/runall10.sh (negs10.py), agg10.py.

Techniques: `detect.buffer-layout-producer`, `detect.drawing-parameters`, `verify.model-reconstruction`,
`verify.paint-follows-drawing`, `patch.pace-limiter`, `patch.preserve-r`, `patch.restore-speed`

## Inputs
Snapshot at the game's own CONTROL SELECTION screen (IM 2, I = 0x9C, ISR 0xE6E6 -> 0xBD2D beeper); not mid-game,
no pokes (the .pok's original bytes match). 48K only: no 128K release in the archive, no .256. Tape: no standard
6,912-byte screen (headerless code blocks), so no loading screen to add.
Controls for recordings: 4 (Kempston), ENTER, then fire. Plain .nex (converter default) reaches play in JNext.

## Rendering model (PLAYBOOK 2)
| Stage | Code | Buffer |
|---|---|---|
| clear a column strip to ink | C044 (calls BE82, D02D, D10D) | 0x8078-0x82DF, 4 bytes a line |
| draw a list into a strip or a block | B07D/B07F (8 call sites BE2E, D04D, DCF6-DD62) | parts 1 byte wide: mask (CPL/AND), OR or overwrite, op bytes self-modified at B0C9-B0E5 |
| paste a column into the background | C1A5 (BFEC, BFFB); 2-byte path C1DC on scroll | 0x8300-0x95FF, 152 lines x 32, linear |
| background to screen | C05A (9 call sites) | the play area, 152 lines |
| background under a droid into its block | C20D (C23D loop) | blocks 0xE700+ (32 px wide) |
| block to screen | B424 via the dirty list 0xA2D1 (E656) | |
| scroll | E117/E126/E135/E14F (LDDR/LDIR in place: 16 px or 8 lines), then the new strip, then C05A | |
In play the attributes are black ink on the deck's paper (0x60 = bright green), the void 0x61; written once per view
from the column-height table B024 (C0C3-C11B). Masks therefore draw the surfaces (paper); ink is the linework.
Droids are never occluded: a block = background + the droid's lists.

## Clash: kind D (one colour per deck), none
Figures never change attributes. The owner's ask is colour, not a clash fix.

## Design (proposal; a human would have decided: colours, Layer 2 over sprites)
Colour shadow: a byte per pixel for the strip, the background, the blocks and the play area, holding the final
Layer 2 value - paper pixels a colour from the drawing list's role (floor, wall, ramp, arrow panel, fringe, object,
pad) in the deck's hue, droids a colour per type, ink pixels 0xE3 (transparent: the ULA shows them, black linework
and the original's blue void unchanged). Layer 2 clipped to the 152-line play area, on at C05A, off at B2C9 and when
the printer (B1FB) writes into the play area (static, transfer game). Mock-up: pilot out/quazatron_colour_mockup.png.

## Pace facts
Not frame-locked: each update ends with a delay DD80-DD91 of (6 - AF09) x 8 x 256 x 16 T (AF09 = droid blocks drawn).
Any added hook time slows the game unless repaid. B07D is 33.5 % of frame time, C05A 130k T a call (26 calls in
3,005 frames), B424 5.7 %. R is read in the ISR's path (LD A,R at 46513).

## Build plan (2.5-3 sessions)
1. Hooks: B07D as a clone of B07D/B07F in the hook page (same instructions at 28 MHz, the same stores to the
   game's self-modified bytes, the mirror inline, the original's T per part counted, a pace window to that time);
   post-hooks for C044, C1A5, C20D, B424, C05A and the 4 scroll moves paying into the debt; Layer 2 on/off; set-up
   converts the stale buffers once (the strip's rows below a short column still hold the snapshot's bytes).
2. Verifier: lockstep at every site, game memory and registers identical (hooks only read game memory), every
   shadow byte = the model (work/cmodel.py), every-site clock matrix, negatives.
3. JNext: pace (10 trials a scene from a probe in E656), flicker, soak, menu; .nxc with the archive's two cheats.
4. v1.1 smooth scrolling: Layer 2 offset on the in-place moves, 2 px a frame toward the game's offset (one step of
   lag), droids as sprites from the same offset.

## Cheats (proven in the simulator, same inputs, work/cheats.py)
Infinite Lives (58347-9 = JP 0xE0DC): the death path is entered and returns to play, no end screen. Infinite Power
(58238 = 0, 58255-6 = JR +65): the death path never runs. Without either, power reaches 0 at frame 3,274 and the game
ends. Neither asks for a value.

## Bug hunt
16 seeds x 20,000 frames of random play (8 with the power cheat): no stall, no code run outside the game; decks
0-3 of the first city and the transfer game reached. No bug found, so no fix is proposed.

## Open
- (done 2026-11-06) The player and droid classes: keyed from the draw record (A320 byte 1 bit 7 = the player, byte 7
  = the A000 type); SCOPE.md "Session 1: inventory".
- Scenery lists of the other decks and cities: unknown lists fall back to the deck's floor tone.
- Never run on hardware. JNext only.

## Lessons
- [local: this engine's history] A branch published from an older main is upstreamed by checking that main's copy of
  the engine equals the branch's base, then taking the branch's files and judging each main-only fix against them
  (#112 here: superseded by iffq); builds and the published .nxc compared byte for byte, the proof matrix rerun.
- [card patch.iff-safe-read §Recognise] Reading LD A,I twice back to back is not enough: the second read can be the
  one an interrupt lands on. Only an after-an-off second read is safe (the shared audit flags the pair).
- [local: this game's drawing] observed: every enemy type draws the same 4 body frames; only the number plate (DDB0, two font characters) differs, so a per-type colour must come from the draw record (A320 byte 7), never from the body list.
- [local: this game's hooks] observed: an ISR hook that sets the game's speed for the ISR body must put the interrupted speed back afterwards (CALL the body), or every interrupt that lands in a 28 MHz hook leaves the rest of the hook at 3.5 MHz (fast build 21% slower in JNext until fixed).
- [deferred Open: reconsider when the pace limiter is built (session 2)] observed: JNext runs of different builds play different games (deck colour and droids follow timing), so pace must be measured update-keyed in lockstep (nexclash.pace), never from free-running logs.
- [local: this game's drawing] observed: masks over an ink fill draw the surfaces; colouring by the list that cleared a pixel follows the drawing (verified by eye on the mock-up), where colouring by the list that set it gave nothing.
- [local: this game's pace] observed: the update delay scales with the droid count (DD80), so hook time is not absorbed by a frame lock; it must be repaid.
- [local: this game's pace] observed: with 4-5 blocks the delay is only 33-66k T, and with 6 or more there is none; per-update sprite pattern uploads (about 20k T) alone overran it, so an image-keyed pattern cache came before any limiter tuning.
- [local: this game's pace] observed: a debt kept through the menu (the ISR hook's cost every frame, no delay to repay it) made the first 25 updates of play run 15% fast; the debt is capped at one frame and cleared at the screen clear.
- [local: this game's pace] observed: a scroll move (LDDR / LDIR of a fixed length on uncontended RAM) has an exact original time, so it is a pace window that can repay a step's hook time; the strip render and copy are not exact (contended screen writes).
- [local: this game's pace] observed: JNext's 28 MHz runs this game's routines only 5 to 6.5 times as fast as 3.5 MHz (wait states at 28 MHz; contention at 3.5 MHz), and the ratio moves with the routine (BE38 5.0 to 6.0 by strip, E656 about 6.2, C05A about 6.6): a game routine run fast in a pace window needs its ratio measured per routine in JNext, and a strip render whose ratio varies stays at the game's clock.
- [local: this game's pace] observed: a pace window that counts its time from the ISR hook alone loses a frame when an interrupt lands in a ROM trampoline (the ISR's ROM path does not count); counting at every nested hook's close too keeps every gap under a frame.
- [local: this game's pace] observed: the ISR plays the sound effects (B060 / B065, BD2D); a sound that starts or ends one update apart in two runs moves every update's time by about 50k T for its length, so the pace lockstep compares B065 and B060 too.
- [deferred Open: reconsider when the engine is built] inferred: the colour shadow can hold final Layer 2 bytes with ink transparent, so no conversion is needed at the copies.
- [card patch.pace-limiter §Failure lookup] observed: a window ticked only at each interrupt, its reading left standing before the ISR's hold, is read again a whole frame later: one wrap is allowed, so that frame is lost (Centred view +10% slow); after the resume the window must go on from now.
- [card patch.pace-limiter §Failure lookup] observed: an ISR that ticks an open window while a nested hook is open counts the hook's time so far in the window, scaled by K (colour 1-1.5% slower); the ISR must leave the window alone inside a nest.
- [local: this engine's pace] observed: the library's readings sit before its own sums, so a nested hook's measuring work falls outside both readings; with about 100 nested hooks in a scroll strip it adds 2% unless counted as a constant (C_LIB).

## Friction
- reuse: [local: the colour model (pilot work/cmodel.py) is this game's verifier reference, not shared code]
- retries: [local: the model first followed LDIR as one block per call; SkoolKit runs one iteration per execution]
- environment: [none: no workarounds needed]
- hand-rolled: [local: the bug hunt's stall check (pilot work/bughunt.py) is game-specific]
- scratch: [local: all scripts stay in the pilot run folder; none added to the repo]

## Technique use
- detect.buffer-layout-producer: helped: found the strip, background and block buffers.
- detect.drawing-parameters: helped: the B07F part format and its op bytes.
- verify.model-reconstruction: used: the colour model reproduces every buffer exactly.
- verify.paint-follows-drawing: helped: colour by drawing list, not by attribute blocks.
- patch.pace-limiter: helped: v1.0-1.2 its own copy; v1.3 the shared library, nested hooks (hlib_nest_*) for WNEST.

## Stage log
- 2026-11-06 stages 0-1 (pilot runs/quazatron): scope, colour model, mock-up, scroll and pace measurements, cheats
  proven, bug hunt; engine not built (budget).
- 2026-11-06 stage 2 session 1 (pilot runs/quazatron): inventory (A000 / A320 fields, 32 types in 9 plate classes,
  one static set of 46 scenery lists for every deck, at most 7 records on screen), droid painting by regions (mock-ups
  v2, v3; approved), engine built around a wrapping Layer 2 canvas + sprites, fast-scroll and smooth options; JNext
  play in colour; burst timings. Not proven: verifier, pace, menu are session 2.
- 2026-11-06 stage 2 session 2 (pilot runs/quazatron): the pace limiter (t_dly at DD8A: the delay loop starts shorter
  by the debt, R exact; pace windows on the scroll moves with fast scroll off), an image-keyed sprite pattern cache, a
  faster ink pass and paste; verifier: sprites = model at every E656, the lock at every frame, the every-site clock
  matrix, negatives; pace trials in JNext (fixture: R read and the ISR's RNG call constant in all builds); the menu
  (main line Colour, toggle Smooth scrolling, the two .pok trainers) and the .nxc package.
- 2026-11-06 stage 2 session 3 (pilot runs/quazatron): game-routine pace windows (E656 in every update, C05A's
  scroll-step copy with fast scroll off: 28 MHz, the original's time from JNext-measured ratios, the debt repaid,
  the rest waited on the video line); the scroll moves run in the hook page (an interrupt in them takes the
  hook-page path: its body at the game's speed, left out of the window); BE38 back at the game's clock with fast
  scroll off; ROLETAB moved to the sprite store page; a monochrome gate (V_MONO): the .nxc base is the monochrome
  build and Colour is its Enhanced colours set, as Nightshade and Pyjamarama offer theirs; a recording with t_su
  (the down-scroll edge lowered in its own first snapshot, test only).

- 2026-11-07 shared engine refactor: the IFF read in qline / mvtick made safe (goal 1); 0 user rounds.
- 2026-11-07 shared engine refactor session 3: v1.2 upstreamed (builds = the published .nxc, proof matrix rerun); 0 user rounds.
## Session 4 (2026-11-06): v1.1, Centred view (opt-in toggle; changes the game logic)
- Trigger: the edge bursts (E1AF: 8 steps past x 9 / 247, y 24 / 151) never start (E1B3 -> JP E1EC). Before each update
  (E0DC: CALL c_pre, was CALL D5BB) c_pre, pure Z80 at 0x3CAC in the alt ROM image, takes ONE scroll step (the game's
  own E0FB .. E1AC) when the player (AF94, AF95) is more than one step off the centre (128, 88): x < 112 or x >= 145,
  y < 80 or y >= 97. After the step: the game's copy (C05A), AF2B = 0, then D5BB as a normal update, so droids move
  (D666 / C30F freeze them while AF2B is set). At most one step an update; AF2B 1-6 (special modes): no step.
- Droids outside the view: C300 marks them off-screen and D5BB skips their logic (D61A-D633): frozen, not despawned;
  shots leaving the view are removed (D92D). The view therefore decides which droids are active, in the original too;
  Centred view changes where the view is, not that rule.
- Deck edges: the game has no edge check (none in the original either); the view follows the player into the void
  beside the deck. Every settled scroll's background equals a full render at the same origin (verifier).
- Engine: VCENTRE (0x4CE2) implies fast scroll + smooth (p_pre); a step's time is a window (mv_in .. cw_close) whose
  length (ISR bodies left out) replaces the debt added inside it, repaid from the game's delay; the glide moved to
  page 27 (slot 6, inside isr_step only) with v1.0's rule unchanged for Smooth alone and glide_c for Centred view.
- Proof: the reference game = the original + the same patches and c_pre (the verifier injects c_pre into the replay's
  ROM; rzx.trace rom=); quazatron.verify checks the rule at every decision and the full-render equality at every step.

## Session 5 (2026-11-06): Centred view made smooth
- Camera = the player: page 27 (`cam`, at slot 7 inside the ISR) moves the shown player Pd at a constant speed toward
  each update's player over the mean of the last 4 update intervals + 2 frames (one update of latency, about 0.1 s);
  the shown origin is exactly Pd - (128, 88); the player's groups at Pd, droids and shots where the game put them
  against the view their records belong to (fixes v1.1's 16 px sprite jump after each step's commit).
- The frame step runs every frame: also from the ISR's hook-page path (isr_in), except while p_spr writes the sprite
  ports; SPOS through slot 0. Interrupts in the alt ROM still skip it (about 1 frame in 1,000).
- Edge: c_pre steps per axis when the player moves that way (AF90 / AF91: screen x with dx + dy, y with dy - dx) and has
  passed the centre, so the game's view leads the camera; a canvas-area clamp holds the camera at deck starts.

## Session 6 (2026-11-06): interrupts, camera filter
- Missed ULA interrupts (also in v1.0, about 2% on a walk): `LD A,I` read during an interrupt's acceptance gives IFF2 0
  and `RET PO` then left interrupts off (now read twice); mvtick's DI covered its whole poll (now only the update);
  the pace waits' polls held interrupts off most of the time (now 256 DJNZ with them on after each). About 0.4% remain.
- Centred view's camera is a velocity filter (page 27 `filt`; `CamModel` in the verifier is the same arithmetic):
  steady px a frame while walking, no overshoot past the player when he stops, about 6 frames behind.

## Session 7 (2026-11-06): v1.2, Cursor keys + Space
- A data-only menu toggle: option 2 on CONTROL SELECTION (the game's own cursor-keys table at AFE5: 7, 6, 5, 8, which
  the Next's cursor keys and an emulator's arrow keys press) is preselected (AFC4 = 2) and its fire key 0 becomes SPACE
  (AFF2: EFFE -> 7FFE). P still pauses (B6AA) and fire resumes. The game's Kempston path (B645) has no room for keys
  without a new hook, and the ROM hook area is full, so the game's own cursor option carries it.
- Measured on v1.1: Centred view runs slower than the original while scrolling (busy +5.4%, scroll +6.9% per update
  against the original's non-scrolling updates): a step's work is repaid only from the game's delay. Open.

## Session 8 (2026-11-06): Centred view's pace, the Kempston key map, the IFF read
- Space: c_pre moved from the alt ROM to RAM at 0x5B40 (the printer buffer above the start-up tail; the game never reads
  or writes 0x5B40-0x5BFF: work/s8/ramfree.py on c1 and b2). That freed 110 ROM bytes for two trampolines; the ISR's
  hook-page path now takes only PCs below the page's code end (c_pre runs at game level).
- Pace: a pace window on the game's figure compositing (DC24 .. DD79, JP t_cmp / CALL t_cmpo, Centred builds only): it
  runs at 28 MHz, its original time is its 28 MHz time x KCMP (6.31; JNext 6.10 time-weighted over 1,805 updates), and
  the saving repays a scroll step's debt. DEBTCAP 4 -> 8 frames. Centred pace: quiet -0.3%, busy +0.9%, scroll +3.8%
  (v1.1 +2.2 / +5.4 / +6.9). Long scrolling is still slower than 2%.
- Cursor keys + Space: kmap (pure Z80 at 0x5BB0) folds 5 / 6 / 7 / 8 and SPACE into the game's Kempston read at B645.
- iffq: LD A,I read once more only when the first shows interrupts off (either read showing them on decides).

## Session 9 (2026-11-06): step costs, the interrupt guard, droid and shot interpolation
- Space: page 25 (bank 12's upper half, unused before) is a second code page, mapped at slot 1 (0x2000) only while a
  page-26 stub calls into it (`nextreg 0x51,XPAGE` ... `nextreg 0x51,0xFF`): x_tags, x_clr, x_paste, x_inks, x_recell
  moved there. It carries a copy of the ROM trampolines at their own addresses, so an interrupt taken in it reaches
  t_isr as from the alt ROM; t_isr takes a PC below 0x3800 as hook-page code. Page 26 has about 350 bytes free again.
  Nothing writes slot 0 or 1 (the simulator, like a ROM, drops such writes): the frame step only reads S0 there.
- Cheaper scroll steps: the tag strip keeps only the columns the paste takes (16 on a 16-px step: x_clr and x_tags clip
  to W); a full-height strip clears as one block; the ink tag is 8 (TINK8: the deck's bright black, was 0) and
  x_paste flags a wholly pasted cell 8, so a deck cell needs no recell; x_recell unrolled per ink kind. JNext walk:
  a step's copy + inks 73k -> 50k T, strip 62k -> 53k T (3.5 MHz T of wall time).
- The Centred step window (mv_in .. cw_close) now stays open over a second step in the same update (horizontal, then
  vertical): mv_in restarted it and lost the first step's time from the debt (about 68k T an update with two steps).
- KCMP 101 -> 96 (6.0), calibrated in lockstep against the Centred REFERENCE game (the original with Centred view's
  logic only: work/s9/mkref.py, test only): the reference pays each step at 3.5 MHz, so its time without the step is
  the target (work/s9/anal9c.py). The per-update measure against the original's non-scrolling updates (sessions 7-8)
  compares different games and moves by several % between trials.
- Interrupts: at 28 MHz the ULA interrupt is 32 T long, shorter than one poll's DI (about 400 T), so a poll whose DI
  covered it lost it. mvtick, after a poll that reads a line in 244-248 (JNext takes the interrupt at line 248), waits
  about 7 lines with interrupts on instead of 2, so no poll's DI starts in the interrupt's line.
- Droids and shots glide (Centred view): each droid's or shot's group is matched to the nearest group of the same key
  (an enemy's type; else its image) in the last update, within 24 px on each axis; it is drawn at its last place and
  glides to the new one over the last update's interval (the frame step's FCT = IR x 256 / IT). New ones: no glide.
  Display only; the verifier runs the same matching and glide every frame.
## Session 10 (2026-11-06): depth order, edge cells, Space also fires (v1.2 as published)
- Depth: p_pre set NR 0x15 = 0x01 (sprite 127 on top) while p_spr gives the front record's groups the lowest numbers:
  every overlap was the wrong way round. Now 0x41 (sprite 0 on top). The records are already in the game's depth order
  (key (y >> 1) - (x >> 1) + 128, kept sorted by C265); the original composites in that order (3,020 of 3,039 pairs
  nearer in front, 19 with a third figure, none farther in front). Verifier check_depth; negative prio.
- Centred view's edges: pasted cells keep their known ink (x_rcink), a view's first copy snaps the shown origin (FRSH2),
  the canvas outside a new view and the camera box's corners take the void's ink (x_ffill, cfill). Per-frame display
  check disp_frame: 821 of 14,765 Centred frames still show a few pixels no view drew (v1.2's draft: 36%).
- Space also fires: one data byte (AFF2 0xEF -> 0x6F): option 2's fire reads rows EFFE and 7FFE together, so 0 or
  SPACE fires. The session 8 key map is gone.

## Upstream (2026-11-07, shared engine refactor session 3)
- The clone's 9248a85 engine files (asm, module, profile) over main's v1.1 + #112: main's v1.1 equals the clone's
  v1.1 byte for byte, and v1.2's iffq (session 8) already reads LD A,I again only after an off, so #112's qline /
  mvtick change is superseded, not merged. Pinned sjasmplus output IDENTICAL to the profile.
- Builds: the 17 outputs equal the clone's session 10 builds, and the published .nxc (jattree/nxc ea2a22f) applied
  with nexclash-patch's tools/nxc.py --bare gives the same .nex for all 16 option combinations (Colour, Smooth
  scrolling, Centred view, Space also fires).
- Proof, session 10's matrix (negs10.py) on this checkout: 43 replays, game state IDENTICAL in all; 88,174,592 canvas
  pixels, 114,583 groups, 99,689 frames locked, 8,664 clock cases, 34,281 filter frames, 632,321 depth pixels;
  negatives 16/16 DETECTED. The aggregate equals session 10's agg10.json. Display: the 9 Centred runs as above.

## Interrupts: the IFF read made safe on v1.1 (2026-11-07, shared engine refactor, goal 1)
- v1.1's qline read `LD A,I` twice back to back and trusted the second (hooklib.iff_audit 'pair'); fixed with the second
  read only after an off, as v1.2's iffq already did. Proof: work/s4 negs4.py, IDENTICAL on 10 recordings x 4 states;
  JNext walks and 10-minute soaks as before. Superseded in v1.3: qline, mvtick and iffq are gone (shared library).

## Shared pace library (2026-11-08, engine refactor goal 2): v1.3, review build
- qline, dlines, mvtick, wown, fw_wait's sums and isr_in / isr_out are the shared library now (hlib_pace: open, wait,
  hold / resume, debt_add, nest_open / close for v1.2's WNEST). TCODE_END 0x4AFC (IPV 0x4B00).
- Fixed against v1.2 in JNext (engine only; the library is unchanged):
  - Lost frame wraps: the window's reading stood before an ISR's hold until the next interrupt, a frame later
    (Centred view +10%). wsync (isr_out, wskipc) restarts it after every ISR, as v1.2's MVL = now.
  - An ISR inside a nested hook ticked the window (the hook's time x K). NESTF: the ISR leaves it alone.
  - The library's sums after its readings were in no count: C_LIBP / C_LIB (1 + 8 sixteenths a nested hook) go to
    the debt; WNS takes A / 8 + C_LIBP out of the routine's time, as WNEST did.
- Pace (JNext, trials9: pace fixture, 10 trials a scene, lockstep vs the original; Centred vs the Centred reference,
  step time left out). v1.3 / v1.2 (main, measured the same day):

  | Scene | mono | colour | Smooth | Centred |
  |---|---|---|---|---|
  | quiet | +0.88 / +0.52% | +0.73 / +0.63% | +0.90 / +0.56% | -0.20 / -0.16% |
  | busy | +0.81 / +0.45% | +0.80 / +0.45% | +1.01 / +0.71% | no lockstep |
  | scroll | +1.14 / +1.04% | +1.07 / +1.02% | +1.06 / +0.90% | +1.00 / +1.47% |

  Every trial -1.14% .. +1.95%; the original's scroll bursts colour +1.49% (+1.73%), mono +1.60% (+1.61%).
- Proofs (v1.2's matrix, pilot s5/qz runall): 43 replays and 16 negatives equal to v1.2's logs line for line
  (175,717 frames, 8,664 clock cases; 16/16 detected): the picture is unchanged. Review build: pilot
  runs/quazatron/rebuild-20261108 (not published).
