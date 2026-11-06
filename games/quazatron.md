# Quazatron (Hewson, 1986; 48K) - colourisation, engine not yet built (stages 0-1, emulator only)

## Next session
Stage: 2 (build, session 2 of the build: verifier + pace)    State: 2026-11-06 session 1: engine 'quazatron' built
(opt-in NEXCLASH_REWORK=quazatron, UNPROVEN): scenery canvas on Layer 2 + droid sprites painted by parts (v3, owner
approved), fast-scroll and smooth options; JNext 1.1.104 reaches play in colour and scrolls. No verifier, no pace
limiter, no menu. Handoff: pilot runs/quazatron/HANDOFF-SESSION2.md (start there), SCOPE.md "Session 1".
Inputs (pilot run folder runs/quazatron, private): the archive's "Quazatron (1986)(Hewson Consultants)[aka
Ziggurat].z80", md5 ac51eb58af87fdac9c0c7077db98c90a; recordings work/b1, work/b2, work/c1 (rec.rzx, Kempston).
Start with: "Build plan" below; the reference model is the pilot's work/cmodel.py (port it into the verifier).

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
- patch.pace-limiter: used: planned for the B07D clone and the debt.

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
