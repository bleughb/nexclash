# TID engine (Oliver Twins, Codemasters): Treasure Island Dizzy, Fantasy World Dizzy, Magicland Dizzy

48K. Generic builder (nexclash/build.py, identify.py, templates.json) for Fantasy World and
Magicland (altrom default); dedicated builder nexclash/dizzy_patch.py for Treasure Island (bubble
virtual read; printer only). Profiles: docs/profiles/tid_treasure_island_dizzy.json,
dizzy3_fantasy_world_dizzy.json, dizzy4_magicland_dizzy.json; signatures.json.
Reference inputs (selftest INPUTS, by MD5): treasure_island_dizzy.z80 (dizzy2_game.z80),
treasure_island_title.z80 (dizzy2.z80), fantasy_world_dizzy.z80 ("(a)" keyboard snapshot) + .rzx,
magicland_dizzy.z80 + .rzx.

| Output | MD5 | Status |
|---|---|---|
| dizzy2_game_sprites.nex (Treasure Island, printer) | 8b4d0847d68fce3215bd43a0e116e682 | verified |
| dizzy2_title_sprites.nex / dizzy2.nex (title) | 85e054fe4bce8e4b3a8e336aac432f58 / 70890aba7d821fba8a41e63636eb58be | verified |
| dizzy3.nex / dizzy4.nex (plain) | cd620010e2f61af0002e76718945716f / 09eb18496cff334ea17bfc0b0c94585d | verified |
| dizzy3_sprites.nex / dizzy4_sprites.nex (altrom) | 9182f2f8b4b0dc55b59a69728568b403 / bf137d41d3cc08221bf6fdda153c9de2 (baselined 2026-10-11) | hardware untested |
| `--strategy printer` dizzy3 / `--strategy slot1` dizzy4 (old builds) | c09213beaec1572c0228985dae89bd77 / d3b37c05d4c47ada07294fa2d7c1ae76 | verified |

Plain TID build runs on hardware.

## Engine and per-game facts
- Player = 39 frames, 24 px wide, <= 21 rows; masked plot; pre-shifts not stored.
  103 unique 16x16 4-bit patterns (all three games).
- Plotter: entry `LD (workspace),A`; inputs A=frame, E=X in 4-px units, L=bottom row+1;
  signature `A1 A8 D9 47 AE 12 70` at plotter+115 (+116 in Dizzy 6: entry followed by PUSH IX); 7 screen writes `LD (HL),B`
  (preceded by `LD (DE),A`); DI inside, may end EI/RET (then entered by JP).
- Eraser: `DI / LD (spsave),SP` (+5 = continue); restores screen from an XOR undo
  buffer: col, height, row-ptr (2 bytes), then 4 bytes per row; 4 screen writes
  `LD (HL),A` after XOR C / XOR B.
- Plot entry block copies X/Y/frame to "old" copies, loads E/L/A, then CALL or JP plotter.
- Room wipe: `LD IX,nn / LD A,136 / LD DE,1` (+4 continue); zero-fills the play area.
- Box routine (inventory/dialogue, overwrites play area): `LD A,(nn) / ADD A,4 / SRL A / LD (nn),A`.
- In-game ISR: DI, pushes, frame counter, `CALL Z,tick` then `CALL sound` <- hide slot.
- Pixel test: `LD C,A / LD B,0 / SRL C / JR C` (+8 AND 240 read, +13 AND 15 read).
- Frame table: word offsets; graphics base = table + 78 (39 entries).
- Title-screen ISR = beeper music, timing-critical: NEVER hook it.
Per game (all verified; full maps in the *_dizzy*.json profiles):
| | Treasure Island | Fantasy World | Magicland |
|---|---|---|---|
| plotter / eraser | 39774 / 40087 | 56705 / 57020 | 39744 / 40059 |
| plot site | CALL at 61578 | JP at 63940 | JP at 40445 |
| undo buffer | 40149 | 57083 | 23552 (sysvars area) |
| frame table | 40249 | 57183 | 24644 |
| wipe / box | 44931 / none | 61865 / 62343 | 37091 / 37690 |
| ISR hide call | 61362 | 63725 | 65380 |
| pixel test | 62333 | 64672 | 41268 |
| logic reads player pixels? | YES (bubbles at 63000 -> virtual read) | no | no |
| printer buffer | free | free | USED (bit-reverse table for mirrored objects) |
| ROM used | - | no | no |
| stack | - | SP 0x5FF2 | SP 0xA2F9, low-water 0xA2BD, code below it |
Game quirks: Fantasy World byte 62569=255 enables Kempston (use the keyboard snapshot);
Fantasy World and Dizzy 1 execute `LD R,A`; Magicland's object plotter self-modifies
36775 (NOP/XOR (HL)) and 36772 (JP 36795 = mirrored path via 0x5B00 table).

## Open
- Treasure Island's game snapshot: the auto-recorder gets no response to input (start/controls
  not found) - needs --start/--keys or a user RZX.
- Hardware-test the Fantasy World / Magicland altrom builds.
- TID `--poke` cheat option (immunity 29289,201) not built.
