# Playbook: one game

Budget rule: known engine -> aim for 4 tool runs and one short report.
Only disassemble routines the tools flag as unclassified.

## 0. Inputs (ask once, up front)
- `.z80` snapshot: 48K, title screen, keyboard controls (not joystick mode -
  e.g. Fantasy World Dizzy byte 62569=255 enables Kempston and caused phantom input).
- RZX recording made per RECORDING_CHECKLIST.md.

## 1. Plain conversion
`python z80tonex.py game.z80` -> ask Dean to test on the Next.
Check where the tail went (the converter prints it). It must be in memory the
game never touches (step 4 proves this); override with `--tail ADDR`.

## 2. Identify the engine
Search the snapshot for the byte signatures in docs/profiles/signatures.json.
If a known engine matches, align its plotter/eraser instruction-by-instruction
against the known game's (normalise 4-5 digit operands to N; where the opcode
text matches, the numbers map old->new). Then locate by pattern:
plot entry (JP/CALL to plotter), eraser (DI / LD (spsave),SP), screen-write
sites (LD (HL),B after LD (DE),A in plotter; LD (HL),A after XOR C/B in
eraser), wipe (LD IX,nn / LD A,136 / LD DE,1), box (LD A,(nn) / ADD A,4 /
SRL A / LD (nn),A), ISR (IM2 vector -> handler; the CALL after the logic-tick
CALL is the hide slot), pixel test (LD C,A / LD B,0 / SRL C / JR C).
Verify every site's original bytes before building.

Unknown engine: run a code map (`rzxplay.py --map`), rank screen writers by
volume, classify the inner loop (masked AND/XOR/OR, pure XOR, LDIR/stack blit,
attribute-cell), extract frames, then continue from step 3.

## 3. One analysis pass over the RZX
Track "player drawn" from the plotter's/eraser's own screen writes. Report:
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

## 4. Decide the design (decision table)
| Finding | Action |
|---|---|
| Logic reads player pixels (result changes) | virtual read: screen XOR undo buffer (masked) or XOR graphic (XOR engine) |
| No dependency | NO virtual read (it becomes wrong after an overwriter covers the player) |
| Boxes/panels overwrite the player while drawn | hide sprite at box entry; reappears at next plot |
| Double draws (XOR engine) | parity model: each XOR draw/erase toggles visibility |
| Erase + redraw in same frame | deferred hide at end of the in-game ISR (TID engine) |
| Title ISR plays beeper music | never hook it |
| Printer buffer free (access scan) | trampolines at 0x5B00 |
| No free RAM but game never uses ROM | patch in RAM page at MMU slot 1 (0x386E-0x3CFF), flag in NextReg $7F, compact tail in dead stack |
| Hooks page memory in slot 0 | DI around paging; read IFF with LD A,I twice (NMOS quirk) |

## 5. Build
Copy the nearest builder (TID-engine: build.py TidPatch;
XOR: dizzy1_patch.py; non-Codemasters: chuckie.py (simplest), wally.py, rainbow.py), change the profile block and site list, rebuild the asm.
Every site keeps its original-byte check.

## 6. Verify (differential test)
At every patched routine in the real recording: copy the machine state, run the
original and the patched routine to their return, compare all registers
(except R/T), all non-screen memory (excluding patch area, sites, dead stack),
the patched screen against the model, and the sprite pixels against the
player's pixels. Every mismatch must be explained or fixed.
Also simulate the start-up tail: registers restored, no game memory touched.

## 7. Deliver
`<game>_sprites.nex`, `<game>.nex`, builder, asm sources; a short results
table; a hardware checklist. Add the new profile (and signature if a new
engine) to docs/profiles/, and games/<game>.md + a STATUS.md row.
