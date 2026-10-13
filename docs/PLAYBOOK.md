# Playbook: one game

Budget rule: known engine -> aim for 4 tool runs and one short report.
Only disassemble routines the tools flag as unclassified.

Phases (a long game may be one session per phase; each starts from games/<game>.md, never from
chat history): A = steps 0-4 + design approval by the user; B = steps 5-6 (toolkit PASS);
C = hardware rounds and fixes. Write decisions and open questions to games/<game>.md as they
happen, so a new session can pick up any phase.
Why: Commando took five hardware rounds, each finding something a step below now covers.

("The user" below = whoever runs the session: Dean in maintainer sessions, the contributor in an
add-a-game session.)

## 0. Inputs (ask once, up front)
- `.z80` snapshot, 48K or 128K, ideally at the title screen or in game, keyboard controls (not
  joystick mode - e.g. Fantasy World Dizzy byte 62569=255 enables Kempston and caused phantom
  input). A loader snapshot works but needs extra steps (0b).
- RZX recording made per RECORDING_CHECKLIST.md, from that same snapshot.

## 0b. Snapshot check (before anything else, ~10 min)
`python nexclash.py inspect GAME.z80` answers most of it (and lists a loader's BASIC + USR targets).
Is it in-game, the title screen, or a LOADER (BASIC program running, PC in ROM)? 48K or 128K?
Which ROM is selected, which interrupt mode, where is the stack? A 128K BASIC loader pages
ROM 0, which the Next does not have (Commando's first builds crashed on the first key). Record
the answers in games/<game>.md.

## 1. Plain conversion
`python nexclash.py convert GAME.z80 [--rzx R]` -> ask the user to test it on the Next.
(128K recordings: leave out --rzx - analyse() wraps 48K memory only and stops with "N port
reading(s) left for frame 0"; prove the tail with `scan --range` instead.)
Check where the tail went (the converter prints it). It must be in memory the
game never touches (step 3 proves this: `scan`); override with `--tail ADDR`.

## 2. Identify the engine
`python nexclash.py identify GAME.z80` covers the TID and Dizzy 1 engines (docs/profiles/
signatures.json); the dedicated engines (Chuckie Egg, Wally, Rainbow, Commando, Midnight Resistance)
are recognised by their own checks in `auto` (is_chuckie / is_wally / is_rainbow / is_commando /
is_midres, profile `signature`),
so `identify` says unknown for them. Search the snapshot for these byte signatures.
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
- writes to any intended patch site (self-modifying code)

## 3b. Visual survey and preview (design approval BEFORE building)
- `preview GAME.z80 --rzx R --at F,F,... --plot ENTRY ... [--buffer A:S:L] -o sheet.png` shows
  what each plot routine draws per caller (the figure kinds to ask about); `scan --range BUF
  --writers` lists every routine that draws into the screen / buffer first.
- Render still frames (ULA + planned sprites) from the RZX at several points and, where the
  recording does not reach them, from later levels: figures against every kind of scenery they
  overlap. Use the frames to settle with the user in ONE round: which figures, colours, solid or
  see-through, and the overlap (depth) rule - the game's own rule, always in front, or another.
  (Commando: depth, solid bodies and solid objects were settled across three hardware rounds
  from the user's photos; preview frames would have settled them first.)
- Speed budget: `cost GAME.z80 --rzx R --at PLOTTER --group IX` gives the original's cost per
  draw (T-states), draws per frame and per object; set the allowed hook cost per draw now, and design to it (caching, fewer
  uploads). Commando's first solid hooks cost ~18x the original draw and were redesigned.
  Measure the HOOK cost too, before the user tests: T per game frame of the patched runs in the
  verifier's pair runs (no tool yet, BRIEFING C2 #11); code under NEXTREG $07=3 runs ~7-8x faster
  than the simulator's T suggests. Midnight Resistance's first commit cost ~1.5 TV frames per game
  frame; a pattern-slot cache brought it to 15-60K T.

## 4. Decide the design (decision table)
| Finding | Action |
|---|---|
| Logic reads player pixels (result changes) | virtual read: screen XOR undo buffer (masked) or XOR graphic (XOR engine) |
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
| Hook code in the alt ROM / slot-1 page | never at 0x3D00-0x3DFF (Commando crashed with code there; probable cause DivMMC automap on fetch - BRIEFING A1); data there was fine |
| Hook state needs RAM, interrupts on, game uses all RAM | a Next page in a slot the ISR never touches (2-5; isr slot scan), mapped only while a hook runs (Midnight Resistance slot 5) |
| Back-buffer composer, plotters share an address helper | replace the CALL target; plot into a scratch copy of the buffer; patch loop exits to map back (LEARNINGS 2.1) |

## 5. Build
Hooks: asm/<engine>_hooks.asm with `SAVEBIN "<prefix>_<key>.bin"` per block and
`"hooks": {"source": "asm/<engine>_hooks.asm", ...}` in the profile; after every edit
`python tools/asm2profile.py <engine>` (pinned sjasmplus -> profile hex + symbols).
Copy the nearest builder (TID-engine: build.py TidPatch;
XOR: dizzy1_patch.py; non-Codemasters: chuckie.py (simplest), wally.py, rainbow.py, commando.py
(128K BASIC loader, front end, depth, cached solid sprites), midres.py (interrupts on, hook page at
slot 5, CALL-target redirect into a scratch buffer, sprites built at a commit with a pattern-slot
cache, per-cell colours)), change the profile block and site list, rebuild the asm.
Every site keeps its original-byte check.

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
Also simulate the start-up tail: registers restored, no game memory touched.

Long runs (the full `auto` with verification, selftest): start them with `setsid nohup ... &` and
poll - a plain background job dies silently when the turn ends (LEARNINGS 2.6).
Iterate fast (BRIEFING C3b ITERATE): while developing use `--quick N` (a few hundred frames for a
first check, 2000 before handing over) and the unit tests on 1-2 captured states (minutes). Run the full `auto` ONCE, on the build that goes to the user (Commando ran
the ~55 min full check five or six times).

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
the STATUS row), then `python -m nexclash.records views` (regenerates STATUS / VERIFICATION
checksums / verified.json). Check it: `python -m nexclash.records deps <game>` lists what your
game's evidence depends on; the maintainers' selftest stamps it. Touched shared code (e.g. the
dispatch line in nexclash.py)? `python selftest.py --canary`.
