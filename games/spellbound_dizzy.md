# Spellbound Dizzy (Dizzy V) - engine `dizzy5`

48K, BASIC loader-stage snapshot. Code: nexclash/dizzy5.py, nexclash/loader.py (REQUIRED),
asm/dizzy5_hooks.asm. Profile: docs/profiles/dizzy5_spellbound_dizzy.json. Reference files (private repo,
specnext/reference/spellbound_dizzy/): Dizzy_V.z80 (md5 703c934a; optional selftest input dizzy5.z80)
and Dizzy_V_auto.rzx.

| Output | MD5 | Status |
|---|---|---|
| Dizzy_V_sprites.nex (altrom) | 1f33c467e6aa55585cea79cfbb24bcfe | verified; hardware untested |
| Dizzy_V.nex | c99189f3274a4803f0b25b0217206bdb | |
| `--strategy slot1` | a59c1fd91ec5c32e549526dbc08d2e69 | (00a7c496... had an EMPTY font page: blank dialogue on hardware) |

## Loader-stage snapshots
Symptoms: PC in ROM (BASIC `PAUSE 0` before `RANDOMIZE USR`), engine found only as an inert
copy or not at all. Fix: pre-run the recording to the first frame boundary where the engine is
identified and live, finish any LDIR, and take THAT state - before hardware detection (Kempston
checks), or the detection result gets baked in (phantom input). The sprite build starts from
that state; the plain build keeps the original snapshot. The Dizzy V session wrote
`loader.prerun(rzx, test)` for this.

BASIC loader snapshot: `PAUSE 0` before `USR 24180`; 45725 copies 21,501 bytes 24192 -> 23296;
Kempston detect at 45807; IM2 with I=149. Engine: ISR 38036 draws OR erases one action per
interrupt from a request/state flag pair (44748/44749) - so no deferred hide; plotter 40060,
eraser 40386; frame table 61194 (height, pointer; rows of 3 mask/graphic pairs); X in 4-px
units, mirrored when bit 7 of 44739 is clear; undo buffer 46088, size 4 x max frame height
(96 bytes; variables follow at 46192+, so do not assume 128); 37 frames (48K). Visual-only
overwrites while drawn: 37671, 52211-52222. Room wipe 52104 runs only while Dizzy is erased.
Reads only the ROM font. At the plot hook AF, BC, DE, HL and the alternate set are dead, but
EXX / EX AF,AF' parity must stay even (the ISR restores registers by set). Verified against
Dean's RZX (below); still wanted: a recording with the inventory and a lost life, and a hardware
test. Built by dizzy5.py + loader.py (loader.prerun replays the RZX until
the engine is live, writes GAME_start.z80). Slot-1 page = ROM copy (from skoolkit.ROM48) with hooks at
0x3800-0x3CFF (altrom default: the same bytes 0x3800-0x3A1E into alt image 1); tail in the undo buffer (0xB408); 102 patterns. Verified: auto RZX (470 plots) and
Dean's RZX (dzzy5rzx, 1,400 plots, dialogue boxes) - all identical. Output MD5s in
docs/VERIFICATION.md. Dean's RZX is NOT in specnext/reference (only Dizzy_V_auto.rzx): upload it so
selftest can repeat that verification.
FIRST HARDWARE BUILD HAD BLANK DIALOGUE TEXT: the slot-1 page had been built from
Snapshot.memory[0:0x4000], which is ZEROS for .z80 files - always take ROM bytes from skoolkit.ROM48.

## Open / hardware checklist
1. Dialogue text visible (font-page fix), inventory and dialogue boxes hide Dizzy.
2. The game writes 7FFD every interrupt: hooks must survive it (altrom: yes by design).
3. Player animates, mirrored correctly, no clash; room changes clean.
