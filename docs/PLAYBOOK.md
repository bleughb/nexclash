# Playbook: one game, in stages

| Stage | Who | Ends with (the gate) |
|---|---|---|
| 0 Intake | tools: `python -m nexclash.survey` | the recording reaches every plotter's callers, or the user records more (before any design work) |
| 1 Design | session 1 | the design in games/<game>.md + ONE question to the user (defaults + exceptions, preview, plain .nex) |
| 2 Build | session 2 | quick runs PASS, evidence record written, committed |
| 3 Prove + deliver | session 3 (small) | the one full verification stamped; sprite build + colour sheets to the user |
| 4 Hardware + colour | one session per round | the user's checklist and painted sheet handled (recolour: seconds, no rebuild) |
| 5 Close | the session that finishes | status, lessons as candidates, contribution / PR |

Why this order (Dean 2026-10-26): tools do the mechanical work and the agent only the judgement;
cheap checks before expensive ones; the user is asked three times (recording, the design question,
hardware + painting), not five; colour comes after the build because recolour makes a repaint free.
Read this intro, "Sessions" and YOUR stage only (`grep -n '^# Stage' docs/PLAYBOOK.md`, then Read
with offset/limit); look the rest up when a step points there.

Budget rule: a game the tools already convert (`auto` PASS) -> a few tool runs and one short report.
Only disassemble routines the tools flag as unclassified.

Write decisions and open questions to games/<game>.md as they happen, so a new session can pick up
any stage - and in stage 2 the build's DESIGN too (sites, memory used, how each figure becomes a
sprite, what the verify checks), before the first quick run.
Why: Match Day (2026-10-20) lost the session's context mid-phase-B; the whole build existed only as
code and a running job, and the next turn had to rediscover it from files and the process list.
Why: Commando took five hardware rounds, each finding something a step below now covers.
Rounds on a long game (stage 4): offer to collect the user's whole list in one pass through the
game, fix all of it, then check everything in ONE new pass; never restart the emulator unasked.
Why: the places are far from the start, and every restart costs the user the walk there
(El Capitan Trueno, 2026-10-13).

("The user" below = whoever runs the session: Dean in maintainer sessions, the contributor in an
add-a-game session.)

## Sessions (one per stage; Dean 2026-10-26)
Every tool call resends the whole conversation, so cost grows with the session's length: a fresh
session that reads this file + games/<game>.md is far cheaper than hour five of an old one.
- One session per stage 1-3, one per hardware round (stage 4). A game the tools already convert
  (`auto` PASS) is one session. Stage 3 is its own small session ON PURPOSE: the full verification
  is polled for up to an hour, and polls of a short conversation cost little.
- A stage ends with the "Next session" block right under the title line of games/<game>.md, then
  commit (+ push, maintainers):
  ```
  ## Next session
  Stage: 2 (build)            State: design approved 2026-10-26 (Decisions below)
  Inputs: specnext/reference/<game>/ (snapshot, recordings)    Branch: claude/<game>
  Start with: <the first command>       Read: PLAYBOOK stage 2, nexclash/<template>.py <functions>
  Open: <anything not settled>
  ```
  and the reply gives the user the prompt for it (README "Continue a game"; contributors: SESSION.md).
- Stage log: one line per finished session under "## Stage log" in games/<game>.md: date, stage,
  wall time, tool calls (roughly), user rounds. It shows which stage costs the most.
- Mid-stage: when the session is long (roughly 80+ tool calls, or several hours) and a natural
  break comes (a quick run passed, a design step done), write the block, commit, and say so: the
  user starts a new session. Never break in the middle of an edit that does not build.
- The block replaces any older one; the facts it points to (decisions, design, open items) stay in
  their sections of games/<game>.md, written as they happen (above).

# Stage 0 - Intake (tools, before any design work)

## Survey (one command)
`python -m nexclash.survey GAME.z80 --rzx R [--rzx R2]` (~5 min for 8,600 frames, linear: 18,300
frames ~15 min, the analysis pass silent for ~12 - not a hang; `--stop N` for a first look) runs
the snapshot check (0b), the plain conversion with its boot check (1; 48K only), engine identification (2) and one analysis pass (3: screen writers by routine, callers, T per call,
ISR, free memory), then a preview pass, and writes `<game>_survey/`: survey.md (one page, ~2K
tokens), survey.json, preview.png (what each top plot routine draws, per caller), the plain .nex.
A KNOWN engine there -> `auto`, no stage 1-2. Read survey.md first; run the single commands below
only for what it leaves open. Its routine attribution is a shadow call stack (BRIEFING C4): a game
that drops return addresses or blits with SP can blur it - check a surprising row with `cost --at`.
Coverage gate (survey.md GATE line): every CALL / JP byte pattern to each top plot routine, and
which the recording reached. An unreached CALL to a FIGURE plotter in code that ran -> ask the user
for a recording that reaches it (RECORDING_CHECKLIST.md) BEFORE stage 1 (Cyclone needed a second
recording halfway through its build); to a text / score printer it is usually a message that did
not come up - note it in games/<game>.md.

## 0. Inputs (ask once, up front)
- `.z80` snapshot, 48K or 128K, ideally at the title screen or in game, keyboard controls (not
  joystick mode - e.g. Fantasy World Dizzy byte 62569=255 enables Kempston and caused phantom
  input). A loader snapshot works but needs extra steps (0b).
- RZX recording made per RECORDING_CHECKLIST.md, from that same snapshot.
- Menus and windows: ask whether the game opens a pause, menus or message windows over the play
  area (and the screens without play: end of a part, codes). They are drawn in the ULA, so Layer 2
  and the sprites cover them (step 4). If the user does not know, offer to find them in the code:
  PC and stack while one is up, the key poll that leads there (Trueno: pause menu, access code).
- A test cheat: offer to find one now (immortality: the store of the reduced energy -> NOP),
  marked TEMPORARY in games/<game>.md; remove it before delivery and check the game over.
  Why: rounds reach far into the game only with it (Trueno).

## 0b. Snapshot check (before anything else, ~10 min)
`python nexclash.py inspect GAME.z80` answers most of it (and lists a loader's BASIC + USR targets).
Is it in-game, the title screen, or a LOADER (BASIC program running, PC in ROM)? 48K or 128K?
Which ROM is selected, which interrupt mode, where is the stack? A 128K BASIC loader pages
ROM 0, which the Next does not have (Commando's first builds crashed on the first key). Record
the answers in games/<game>.md.

## 1. Plain conversion
`python nexclash.py convert GAME.z80 [--rzx R]` (survey does it). The user tests it on the Next
together with the design question (stage 1), not in a round of its own.
(128K recordings: leave out --rzx - analyse() wraps 48K memory only and stops with "N port
reading(s) left for frame 0"; prove the tail with `scan --range` instead.)
Check where the tail went (the converter prints it). It must be in memory the
game never touches (step 3 proves this: `scan`); override with `--tail ADDR`.

# Stage 1 - Design (session 1)

## 2. Identify the engine (fast path) or the patch plan
`python nexclash.py identify GAME.z80` covers the TID and Dizzy 1 engines (docs/profiles/
signatures.json); the dedicated engines are recognised by their own checks in `auto`
(is_<engine>, profile `signature`; the table is nexclash/engines.py), so `identify` says unknown
for them (BRIEFING C2 #18). Search the snapshot for their byte signatures. A new engine adds one
line to nexclash/engines.py.
If a known engine matches, align its plotter/eraser instruction-by-instruction
against the known game's (normalise 4-5 digit operands to N; where the opcode
text matches, the numbers map old->new). Then locate by pattern:
plot entry (JP/CALL to plotter), eraser (DI / LD (spsave),SP), screen-write
sites (LD (HL),B after LD (DE),A in plotter; LD (HL),A after XOR C/B in
eraser), wipe (LD IX,nn / LD A,136 / LD DE,1), box (LD A,(nn) / ADD A,4 /
SRL A / LD (nn),A), ISR (IM2 vector -> handler; the CALL after the logic-tick
CALL is the hide slot), pixel test (LD C,A / LD B,0 / SRL C / JR C).
Verify every site's original bytes before building.

Unknown engine: `scan GAME.z80 --rzx R --range 0x4000-0x5AFF --writers` ranks the screen writers
(and finds a back buffer: a big LDI/LDIR/stack writer copying from RAM; scan that range --writers
too), `preview --plot ENTRY` shows what each plot routine draws per caller; classify the inner
loop (masked AND/XOR/OR, pure XOR, LDIR/stack blit, attribute-cell), then continue from step 3.
Classify the RENDERING MODEL first - it picks the hook pattern (BRIEFING A3, decision table 4):
XOR to screen, masked + undo buffer, back-buffer composer, full redraw / tilemap, differential OR.
Patch plan (docs/techniques/STANDARD.md 4-5): per routine / figure class, write the observations
(each with basis observed / inferred / unknown, and scope) in games/<game>.md, then pick cards from
docs/techniques/index.json: eligible = every `requires` true and every `rejects` false; unknown ->
run the card's probe, never assume. Record the chosen applications (target, phases) and rejected
cards with reasons, then the design question (3c). No card fits: say so, design from table 4; a
reusable new method is a Lesson candidate for a card.

## 3. One analysis pass over the RZX
Shared commands first: `isr GAME.z80 --rzx R` (what hooks must keep intact for the interrupt
handler: IY/IX reads, stack, paging), `scan GAME.z80 --rzx R --range LO-HI` (free memory for hook
state; also `--frames N --keys K --after ENTRY` for the start-up path no recording covers).
Then, per engine, track "player drawn" from the plotter's/eraser's own screen writes. Report:
- plot/erase/wipe/box/ISR counts, split by drawn/not drawn (double draws? erase
  while not drawn?)
- every non-player routine that READS or WRITES bytes containing the player's
  pixels while drawn, by PC
- for each writer: XOR (safe), nibble-replace, or overwrite (disassemble only these)
- pixel/collision tests: does the result change if the player is removed?
  Needs an exact "patched screen" model: player writes skipped; XOR writers
  apply their delta; overwriters/nibble-replacers apply their rule; any
  UNCLASSIFIED write to a byte where the screens differ must be reported
- memory never read or written, ROM use, stack low-water mark
- writes to any intended patch site (self-modifying code) - and to the bytes AROUND it that a hook
  would emulate or jump back into: list every LD (nn),A / LD (nn),HL into the routine's code first
  (Dizzy 1 rewrites 58079 and 58709 next to its write sites; the first site at 58707 covered 58709)

## 3b. Colour sheets, recolour, speed budget (moved)
Colour sheets and recolour: docs/COLOURS.md (built in stage 2, sent in stage 3). Speed budget: 3c.

## 3c. Preview and the design question (design approval BEFORE building)
- `preview GAME.z80 --rzx R --at F,F,... --plot ENTRY ... [--buffer A:S:L] -o sheet.png` shows
  (with --rzx, `--every N` needs `--stop` too: without it the run ends after 500 frames)
  what each plot routine draws per caller (the figure kinds to ask about); `scan --range BUF
  --writers` lists every routine that draws into the screen / buffer first.
- Render still frames (ULA + planned sprites) from the RZX at several points and, where the
  recording does not reach them, from later levels: figures against every kind of scenery they
  overlap. Use the frames to settle with the user in ONE round: which figures, colours, solid or
  see-through, and the overlap (depth) rule - the game's own rule, always in front, or another.
  (Commando: depth, solid bodies and solid objects were settled across three hardware rounds
  from the user's photos; preview frames would have settled them first.)
- Design defaults (the stage-1 question is these + this game's exceptions; Dean 2026-10-26).
  Ask in ONE message, numbered, each line the default and what this game shows, so the user can
  answer "defaults" or "change 3":
  1. Every figure a sprite (Dean 2026-10-13), from every caller of each plotter.
  2. Scenery, HUD, score and text stay on the ULA.
  3. Depth: the game's own rule (behind what the original draws in front).
  4. Colours: the game's own (the figure's cell ink) until the user paints the sheet sent with
     the first sprite build (docs/COLOURS.md, stage 3); the painting is applied by recolour.
  5. Menus, pause and message windows over the play area: Layer 2 and sprites off while up (step 4).
  ALWAYS ASK, no default yet (list what the preview shows): bullets, explosions and other effects;
  solid or see-through figures; outlines; anything the hooks cannot convert.
  A new standing answer from the user -> add it here with the date.
  Attach the preview frames and the plain .nex (for its hardware test) to the same message.
- Every figure is a sprite by default (Dean, 2026-10-13: "make everything possible a sprite"): list
  every caller of each plotter from the code (not only those the RZX shows) and convert them all;
  what stays on the ULA (scenery, HUD, text, cases the hooks cannot do) is the question to ask.
  The sheet still shows only what the recording drew: ask for a recording that reaches every
  level, weapon and collectable the user can, before the sheet goes out.
- Speed budget: `cost GAME.z80 --rzx R --at PLOTTER --group IX` gives the original's cost per
  draw (T-states), draws per frame and per object; set the allowed hook cost per draw now, and design to it (caching, fewer
  uploads). Commando's first solid hooks cost ~18x the original draw and were redesigned.
  Measure the HOOK cost too, before the user tests: T per game frame of the patched runs in the
  verifier's pair runs (no tool yet, BRIEFING C2 #1); code under NEXTREG $07=3 costs (T + memory reads)
  / 8 in 3.5 MHz T - about 6x faster, not 8x (LEARNINGS 2.1f). Midnight Resistance's first commit cost ~1.5 TV frames per game
  frame; a pattern-slot cache brought it to 15-60K T.

## 4. Decide the design (decision table)
| Finding | Action |
|---|---|
| Logic reads player pixels (result changes) | virtual read: screen XOR undo buffer (masked) or XOR graphic (XOR engine) |
| Logic reads XOR-drawn figure pixels and the figures go in front | overlay instead: keep every ULA write, sprites exactly on the figure's ink pixels; check each plot's screen change = old ^ new image of the model (LEARNINGS 2.1d, Fireman) |
| No dependency | NO virtual read (it becomes wrong after an overwriter covers the player) |
| Boxes/panels overwrite the player while drawn | hide sprite at box entry; reappears at next plot |
| Double draws (XOR engine) | parity model: each XOR draw/erase toggles visibility |
| Erase + redraw in same frame | deferred hide at end of the in-game ISR (TID engine) |
| Title ISR plays beeper music | never hook it |
| Patch memory (default) | `altrom`: hooks in alt ROM image 1 (BRIEFING A3; no RAM page, survives 7FFD); hook state in RAM the scan proves untouched (and zero, or explained) |
| Game reads the ROM bytes the hooks need | older strategies (BRIEFING A3 choice rule): printer buffer free (access scan) -> trampolines at 0x5B00; else game never reads ROM -> RAM page at MMU slot 1 (0x386E-0x3CFF), flag in NextReg $7F, compact tail in dead stack |
| Hooks page memory in slot 0 | DI around paging; read IFF with LD A,I twice (NMOS quirk) |
| Interrupts on at the hook sites | hooks never write IX/IY/I or IFF and keep SP on a stack with room, at EVERY instruction (the game's ISR may read them: Commando IY+7) |
| Figure moves (redraw) | never hide at entry and show at exit (flicker): build the new image in other pattern memory, switch the attributes last |
| Menu, pause or message window drawn in the ULA over the play area | wrap its routine: Layer 2 and sprites off (NEXTREG $69 / $15) while it is up, on at its return; NEXTREG keeps every register and flag (Trueno e_mnu). Switching them off also hides whatever the hooks removed from the ULA: plan what the user sees there |
| A screen shown without the normal screen build (end of a part, a special or clear mode) | clear or hide Layer 2 and the sprites on that path, or the old screen's layers stay over it (Trueno: access code screen, the dragon's screen) |
| Code reaches the plotter past the hooked entry | search every CALL/JP to every plotter address: such figures bypass the hook and keep the original drawing path (Trueno: the dragon's energy bar via 0x82E4, its colours lost with the clean-attribute copy) |
| Snapshot taken with the title or menu already on screen | a patch to drawing code does not show the first time: patch the snapshot's screen memory too (Trueno: a menu item removed) |
| Scenery clash: the original cut the scenery along cell edges (black cells), or an object painted the wall around it in its colour | fix cells: those cells redrawn in Layer 2 WITHOUT the palette priority bit (figures stay in front), per screen, from a sheet the user draws; the ULA stays original; mark them so a screen change clears them |
| Per-screen Layer 2 tables | count the pages: one 8K page per screen adds up (Trueno: pages 60-83); check the highest page against an unexpanded Next (1024K = 8K pages 0-95; LEARNINGS 1.3), pack screens per page when many |
| Hook code in the alt ROM / slot-1 page | never at 0x3D00-0x3DFF (Commando crashed with code there; probable cause DivMMC automap on fetch - BRIEFING A1); data there was fine |
| Hook state needs RAM, interrupts on, game uses all RAM | a Next page in a slot the ISR never touches (2-5; isr slot scan), mapped only while a hook runs (Midnight Resistance slot 5) |
| Back-buffer composer, plotters share an address helper | replace the CALL target; plot into a scratch copy of the buffer; patch loop exits to map back (LEARNINGS 2.1) |
| Pure XOR to the screen, many figure kinds / partial draws / thin pieces (Dizzy 1) | 1-bit shadow screen: converted writes XOR the shadow, ULA ^ shadow = original; figures on Layer 2; non-XOR writers put the change into shadow or ULA; effects fold the shadow back (LEARNINGS 2.1) |
| Game has no frame sync (no HALT, FRAMES unread) | hook time = slowdown: run whole plots at 28 MHz (entry hook + return-address trampoline), measure the Speed line |
| The game rewrites bytes in or next to a site | move the site off them; read the rewritten instruction at run time in the hook |

Stage 1 ends: decisions in games/<game>.md, the question sent, the Next session block (stage 2).

# Stage 2 - Build (session 2)

## 5. Build
Hooks: asm/<engine>_hooks.asm with `SAVEBIN "<prefix>_<key>.bin"` per block and
`"hooks": {"source": "asm/<engine>_hooks.asm", ...}` in the profile; after every edit
`python tools/asm2profile.py <engine>` (pinned sjasmplus -> profile hex + symbols).
What the module must provide: docs/ENGINE_CONTRACT.md (doccheck-checked). The cards' example
functions first; then copy the nearest engine
(module + asm + profile + games/ file; STATUS.md lists every engine), one function at a time:
| Engine | Template for |
|---|---|
| build.py TidPatch | Codemasters TID engine (generic builder) |
| chuckie.py | the simplest: 48K, stateless alt-ROM hooks (no RAM page), interrupts on |
| jetpac.py | 16K game, run-time graphics buffers, no RZX (free runs with a key schedule) |
| loderunner.py | XOR plotter, hooks in RAM (the game reads the alt ROM), figures printed as tiles |
| dizzy1.py | pure XOR to the screen: 1-bit shadow screen + Layer 2, outlines, plots at 28 MHz |
| wally.py / wally2.py | back-buffer composer, interrupts off / every figure on a double-buffered Layer 2 |
| midres.py | interrupts on, all RAM used: hook page at slot 5, CALL-target redirect into a scratch buffer, pattern-slot cache, per-pixel colour map |
| smashtv.py | the game's own plotters into a scratch buffer at slot 7, no frame sync, see-through outline |
| commando.py | 128K BASIC loader, front end, depth from walk boxes, cached solid sprites |
| renegade.py | alt ROM images 0 + 1, loading-screen front end |
| rainbow.py | full redraw / tile composer, 128K (large; excluded from automatic checks) |
Change the profile block and site list, rebuild the asm.
Every site keeps its original-byte check.
Colour map (every game, docs/COLOURS.md): the sprite builder applies `<record>_colours.json` per pixel -
key = the graphics byte the pixel comes from, a non-zero nibble replaces the default colour of an
opaque pixel - and, in an engine with outlines (paint_clear), makes a PAPER pixel opaque in that
colour (Dizzy 1: fill_mask; its verify model and negative controls must cover it) - and a check of
the graphics bytes stored with the entry (other graphics at that
address in a later level -> defaults). Store it where the build can read it at sprite-build time
(midres: Next pages 28.. at slot 4 during the commit, page tables in the hook page, MidresPatch
store_pages / asm `ovl`). A build with no colours file = today's defaults.
Also build the colour-sheet capture and `recolour` now (docs/COLOURS.md): stage 3 sends the sheets.

## 6. Verify (differential test)
At every patched routine in the real recording: copy the machine state, run the
original and the patched routine to their return, compare all registers
(except R/T/MEMPTR; AF' included), all memory outside the never-read draw buffers (patch area
and sites excluded; dead stack only where a documented convergence check applies - a hook that
returns into the game's own loop must leave it identical), the patched screen against the
model, and the sprite pixels against the original plot (masked figures: run the plot on a 0x00
and a 0xFF buffer for ink / paper / transparent, midres.truth). With interrupts on at the hooks,
also check interrupt safety after every hook instruction (IX, IY, I, IFF, stack room; Commando,
midres) with a negative control. Every mismatch must be explained or fixed.
Colour map: the expected sprite layer uses the map too (midres.expected_layer / map_colour); unit
cases with a synthetic map per figure, a wrong check byte (must be ignored) and a negative control
(the map left out of the build, informative cases only); once the user's colours file exists, the
full RZX run uses it.
Also simulate the start-up tail: registers restored, no game memory touched.

Iterate fast (the two levels: BRIEFING C3b): while developing use `--quick N` and the unit tests on 1-2
captured states (minutes). N must reach the first call of every hook the unit tests capture
states from, or the run FAILS for lack of a state (Lode Runner at 300 frames: "no captured draw
state"; Commando: "no plot reused a cached image"): start at 2000. One quick run per change; read
its counters before changing anything else.
Unit cases: cross only the inputs that interact. Every graphic x every position edge is one
product; colours, slots and similar independent inputs need each value once, on a few graphics -
not every combination (Jetpac's 5,616 graphic cases are 117 graphics x 8 positions x 3 inks x 2
slots; 117 x 8 + the inks and slots once each covers the same guard edges).
Stage 2 ends: quick runs PASS (counters in games/<game>.md), the evidence record written (step 7),
committed; the Next session block (stage 3).

# Stage 3 - Prove and deliver (session 3, small)

## 6a. The one full verification
The full verification runs ONCE, on the build that goes to the user, and it is the stamping run:
write the evidence record first (step 7), commit, then `python selftest.py --game <record> --verify
--stamp` (the record's verify recipe + the rebuild MD5s; it stamps the record, so the maintainers'
`--affected` before the merge has nothing left to do for this game). Never a separate full `auto`
as well (Commando ran the ~55 min full check five or six times).
Long runs (the full verification, selftest): detached + polled, LEARNINGS 2.6: one
`sleep 540; tail -3 LOG` per poll (call timeout 10 min), nothing faster; write the record and the notes meanwhile.

## 6b. Hardware risk review (before every build the user tests)
Go through BRIEFING A1 "Simulator blind spots" item by item for what changed since the last
hardware round (DivMMC trap, interrupts inside hooks, raster/tearing, speed, emulator
differences); each item must be covered by a toolkit check or named in the hardware checklist.
Ask the user to try CSpect first if a build changes memory layout or start-up.

## 7. Deliver
`<game>_sprites.nex`, `<game>.nex`, builder, asm sources; a short results
table; a hardware checklist. Add the new profile (and signature if a new
engine) to docs/profiles/, games/<game>.md, and the evidence record docs/records/<game>.json
(copy the nearest engine's record; `modules` = the modules your build imports, `own_modules` /
`data` = your engine's files, `rebuild.decisions` = the run's <name>_decisions.json, `status` =
the STATUS row, `techniques` + `results` = the recipe and checks, docs/techniques/STANDARD.md 3), then
`python -m nexclash.records views` (regenerates STATUS / VERIFICATION
checksums / verified.json). Check it: `python -m nexclash.records deps <game>` lists what your
game's evidence depends on; the one full verification (6a) stamps it. The engine's line in
nexclash/engines.py is not shared code (rebuild-only); anything else outside your engine is:
`python selftest.py --canary`.
Send with the sprite build: the colour sheets (docs/COLOURS.md "What to send") and the hardware
checklist, so the user tests and paints in the same pass.

# Stage 4 - Hardware and colour rounds (one session per round)
- Collect the user's whole list per round (above); 6b before every build the user tests.
- A painted sheet: `recolour` (the recolour skill; seconds, no rebuild, no re-verify). Making the
  painting the build default is its own task (docs/COLOURS.md RECOLOUR: rebuild + verify + stamp).
- A fix: stage 2 rules (quick runs), then the full verification again as in 6a.
- A figure or screen the first recording never showed: its own question to the user (CLAUDE.md).

# Stage 5 - Close (the session that finishes the game, or a round)
CLAUDE.md "End of every stage": games/<game>.md (status, checklist, Stage log), the record and
`records views`, lesson candidates, `python tools/doccheck.py`; contributors `contribute`,
maintainers the PR (docs/MAINTAIN.md).
