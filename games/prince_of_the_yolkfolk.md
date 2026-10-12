# Prince of the Yolkfolk (Dizzy 6) - engine `tid_mirror`

48K. Code: nexclash/dizzy6.py (TidPatch slot1 + unpatched plotter/eraser copy at 0x2000 for the
mirror calls; nexclash.py _auto_dizzy6). Profile: docs/profiles/dizzy6_prince_of_the_yolkfolk.json.
Reference files (private repo,
specnext/reference/prince_of_the_yolkfolk/): Dizzy6.z80 (md5 dd6cd7a3), try1.rzx, try2.rzx, try3.rzx.
Not in selftest yet.

| Output | MD5 | Status |
|---|---|---|
| Dizzy6.nex | e02faca34df9504cc1f2f162e0ef791e | |
| Dizzy6_sprites.nex (slot1) | f491e1f6621559ccc4d36de3535ff5d0 | verified (try1.rzx 1,537 plots, auto RZX 29, 780-case mirror selftest); hardware untested |

Stays slot1: the self-modifying plotter copy needs RAM at 0x2000; tail in the player undo buffer
23552 (88 bytes, write-first). Relies on locked 7FFD writes not remapping MMU (VHDL; hardware to
confirm with this build).

## Facts
Dizzy 6 / Prince of the Yolkfolk (48K .z80 v1, PC 65021 = IM2 vector -> JP 61478, SP 40085,
DI; full map in dizzy6_prince_of_the_yolkfolk.json): plotter 38351 / eraser 38667 (code ends
38721; variables 38721-38740 follow), player plot site JP at 38974, undo buffer selected by
pointer 38731 (eraser `LD SP,(38731)`, plotter `LD DE,(38731)`): player 23552, mirror 23652;
frame table 25849; wipe 36389 (IX 23848); box 36988 (var 38348); ISR hide call 61507 (tick
37108); pixel test 39792. SECOND FIGURE: actor handlers 33655/33669 (reached via room/actor
tables, not CALLs) draw a MIRRORED player copy (X = 58 - X, frame via map at 33757) with
CALL plotter at 33741 and CALL eraser at 33680 after `LD BC,23652 / LD (38731),BC`, then restore
the pointer to 23552. Printer buffer USED; ROM not read and never written (0x0000-0x3FFF, both RZX); dead stack 48 bytes (low-water 40037);
no player-dependent pixel tests; screen writers over the player at 36213-36273 are xor/keep
(object plot), 36074/37030 overwrite. No RZX has reached the mirror actor yet (room unknown).

## Open
- Record a pass through the mirror room (verify that path against real play).
- evidence.json not updated for 'tid_mirror' (_auto_dizzy6 skips _learn).
- Possible hybrid: alt ROM hooks + plotter copy in a slot-0 RAM page (IM2 game).
