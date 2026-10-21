# Next hardware reference card: ports, NextRegs and Z80N instructions used by nexclash

Index of every port and register: SpecNext Wiki "Board feature control"
https://wiki.specnext.dev/Board_feature_control (one page per port/register, linked from there).
The wiki says it is copied by hand from the core's spec. When wiki and spec differ, the spec
wins: `nextreg.txt`, `ports.txt` and `changelog.md` in the core repo
(GitLab SpectrumNext/ZX_Spectrum_Next_FPGA, cores/zxnext/). The sandbox cannot reach GitLab, so use
the GitHub mirror of core 3.01.09 instead:
`git clone --depth 1 https://github.com/avlixa/zx_spectrum_next_03.01.09` (files nextreg.txt,
ports.txt, src/zxnext.vhd). Dean's core may be newer; record the core version with any new fact.
There is also a searchable view of the spec at https://explorer.specnext.dev/ (under development).
Wiki pages are read with WebFetch (search first: the fetch tool only opens URLs seen in results).

Partial decoding (wiki note): legacy devices test only some address bits. Next ports ignore the
top byte where OTIR must work (0x57, 0x5B). The ULA answers on any even port (A0=0). With 48K or
128K timing, 7FFD answers on A15=0 and A1:0=01, ignoring A14 (VHDL); with +3 timing A14 must be 1.

## NextRegs (write with NEXTREG; read by selecting via 0x243B, then reading 0x253B)
| Reg | Wiki page | What we use it for | Where |
|---|---|---|---|
| $03 | Machine Type Register | display timing 48K/128K (bits 6:4, bit 7 = allow change); written last in the tail. Does NOT stop 7FFD decoding | z80tonex tail |
| $05 | Peripheral 1 Setting Register | bit 2 cleared = 50 Hz (unless `nexclash.py ... --allow-60hz`); a new rate takes effect at the NEXT frame and $05 reads back the OLD rate until then - work from the value written, not a read (NextMasterSystem design notes) | z80tonex stub |
| $06 | Peripheral 2 Setting Register | bit 4 cleared = divMMC automap / DRIVE-button NMI off (the A1 table used to say $0A). Yet code at 0x3D00-0x3DFF crashed Commando: probably not every automap entry point (BRIEFING A1, C2 #24). NOT cleared: bit 7 = F8 CPU-speed key, bit 5 = F3 50/60 Hz key (both 1 after soft reset: a player can change speed / refresh mid-game, C2 #26); bits 1:0 audio chip mode | z80tonex stub |
| $07 | CPU Speed Register | 0 = 3.5 MHz for games; 3 = 28 MHz inside the Rainbow and Commando hooks, 0 on exit | stub, rainbow_hooks, commando_hooks |
| $08 | Peripheral 3 Setting Register | bit 7 write 1 = clear the 7FFD lock (0 does nothing; read 1 = unlocked); bit 6 = 1 DISABLES contention (the tail's AND $30 clears it: contention on); bit 5 ABC/ACB, 4 speaker, 3 DACs, 2 port FF read, 1 TurboSound, 0 = Issue 2 keyboard (an early game that reads EAR on port FE may need it; not used) | tail, altrom stub |
| $15 | Sprite and Layers System Register | bit 0 sprites visible; bits 4:2 layer order (default SLU, global) | hooks, setup |
| $19 / $1C | Clip Window Sprites / Clip Window Control | $1C bit 1 resets the sprite clip index, then X1,X2,Y1,Y2 to $19 | Rainbow / Wally setup |
| $1B | Clip Window Tilemap | $1C bit 3 resets its index, then X1,X2 (2-pixel units), Y1,Y2 | Rainbow commit (x 16-143, y 48..47+N) |
| $1E / $1F | Active Video Line MSB / LSB | read via 0x243B/0x253B; line 0 = first ULA pixel row; commit waits while the beam is in the play area | Rainbow raster wait |
| $2F-$31 | Tilemap Offset X MSB/LSB, Y | 0 | Rainbow setup |
| $4C | Tilemap Transparency Index | 0 | Rainbow setup |
| $6B | Tilemap Control | 0x81 = on, 40x32, 2-byte entries, tilemap over the ULA; 0 = off | Rainbow commit / sprites-off stubs |
| $6C | Default Tilemap Attribute | 0 | Rainbow setup |
| $6E / $6F | Tilemap Base Address / Tile Definitions Base | bit 7 = bank 7 (first 8K only = page 14; recent core), low bits = offset in 256-byte units ($6E 0x80, $6F 0x80 + 0x0A) | Rainbow commit |
| $34 | Sprite port-mirror Index Register | selects the sprite for $35-$39 | all hooks |
| $35-$39 | Sprite Attribute 0-4 Registers | X, Y, flags (X8, mirror), pattern + visible, 4-bit/anchor; no auto-increment ($75-$79 would) | all hooks |
| $40 / $41 / $43 | Palette Index / Palette Value (8-bit) / ULA Palette Control | $43=$20 selects sprite palette 0 with auto-increment; $43=$30 the tilemap palette. $43 bit 7 = 1 turns auto-increment OFF; bits 3:1 select the DISPLAYED second palette (sprites / Layer 2 / ULA), bit 0 ULANext - every $43 write sets them too (TECHNIQUES 1) | setup templates, Rainbow setup |
| $4B | Sprite Transparency Index Register | 0 = index 0 transparent (reset value $E3; 4-bit uses the low nibble) | setup |
| $50-$57 | MMU slot 0-7 Registers | 8K page per slot; $FF in slot 0/1 = ROM (or the alt ROM) | stub, tail, hooks |
| $7F | User Storage 0 Register | "player drawn" flag (slot1/altrom TID hooks); Rainbow: tile-cache flush request | hooks |
| $8C | Alternate ROM Register | $C0 write mode (fill), $80 enable read-only; hardware-tested 2026-09-27 | altrom stub, tail |
| $C0 | Interrupt Control Register | 0 = pulse interrupt mode (Next IM2 hardware vectors off; bit 3 stackless NMI off) | z80tonex stub |
| $14 | Global Transparency Colour | Layer 2 / ULA / LoRes transparency, a COLOUR compared with the top 8 bits of the 9-bit colour (guide r3 calls it an index - core nextreg.txt is right); soft reset $E3 | (Dizzy 1 Layer 2 relies on the default) |
| $C8 | INT Status 0 | bit 0 ULA, bit 1 line interrupt happened since cleared; WRITE 1 clears | Rainbow diagnostic build |
| $8E | Memory Mapping Register | not used; writes act like 7FFD/DFFD/1FFD port writes | - |

## Ports
| Port | Wiki page | Use |
|---|---|---|
| 0x243B / 0x253B | TBBlue Register Select / Access | read NextRegs ($7F, $08, $05, $06) |
| 0x303B | Sprite Status/Slot Select | write: pattern slot for 0x5B (bits 5:0, bit 7 = +128 bytes) AND, from the same write, the attribute index for 0x57 (bits 6:0, sprite 0-127); read: bit 1 = too many sprites on a line, bit 0 = collision (the read clears both) |
| 0x5B | Sprite Pattern Upload | pattern bytes; auto-advance (256-byte blocks by OTIR). Low byte decoded only: Rainbow (2026-10-19) uploads by unrolled OUTI with any B |
| 0x57 | Sprite Attribute Upload | 4 or 5 bytes per sprite in $35..$39 order (4 when byte 3 bit 6 = 0); index set by a 0x303B write (which also sets the pattern slot); advances after each sprite, wraps 127 -> 0. Low byte decoded only. Rainbow commit (2026-10-19): 0x303B = sprite, 5 x OUTI; NextState models it (simulated; hardware to confirm) |
| 0x7FFD | Memory Paging Control | bit 5 = lock; unlocked writes also reset MMU0/1 to ROM and MMU6/7 to the bank; bit 3 = ULA shows bank 7 (shadow screen) |
| 0x123B | Layer 2 Access Port | bit 1 visible (alias $69 bit 7); bit 0 write-paging / bit 2 read-paging of Layer 2 into 0x0000-0x3FFF, bits 7:6 which 16K (11 = all 48K over slots 0-2), bit 3 shadow banks ($13), bit 4 = offset form (core 3.0.7+). The stub writes 0 (no paging into ROM space) |
| 0x1FFD | Plus 3 Memory Paging Control | bit 2 + 7FFD bit 4 select the ROM (ROM3 = 48K = alt image 1) |
| 0xDFFD | Next Memory Bank Select | not used (bank MSBs) |
| 0xFE | ULA Control Port | border (restored by the tail) |

## Not used yet: documented, untested (why / when to use: TECHNIQUES 1)
Sources: core 3.01.09 nextreg.txt / ports.txt, guide r3 (Sprites, DMA, Copper, Interrupts), KevB copper
timing (github.com/varmfskii/zxnext_code, zx_next_notes/copper). Researched 2026-10-19.
| Reg / port | What | Notes |
|---|---|---|
| $09 bit 4 | lockstep $34 with 0x303B | off by default: $34 and 0x303B are separate sprite indices |
| $75-$79 | $35-$39 with sprite number post-increment | each write increments (nextreg.txt); `NEXTREG $78,0` per sprite = hide a run |
| $37 bit 0 / $39 bits 7:6 (relative sprites) | anchor + composite / unified relatives | relatives: 8-bit X/Y offsets, visibility ANDed with the anchor, optional pattern / palette offset from the anchor; unified = mirror/rotate/scale as one image |
| port 0x6B | zxnDMA (core 3.1.2+; 0x0B = Zilog DMA) | WR0-WR6 program by OTIR; WR1/WR2 timing byte = cycle length 2..4; WR4 bits 6:5 = 01 continuous, 10 burst; WR6 $CF load, $87 enable, $83 disable, $D3 continue (repeat from current pointers), $C3 reset, $BB + mask / $BF / $A7 read status; WR1 %00100100 = port A fixed memory (fill). Holds the bus: pulse interrupts are lost |
| $60 / $63 | copper data upload (byte / whole instruction) | $63 commits only after both bytes: no half instruction runs |
| $61 / $62 | copper upload index (11 bits) + mode $62 bits 7:6 | 00 stop, 01 reset+run, 10 resume, 11 reset+run + restart each frame; same mode again = index change only |
| copper WAIT / MOVE | `1HHHHHHV VVVVVVVV` / `0RRRRRRR DDDDDDDD`, HALT = $FFFF, NOOP = 0 | MOVE reaches NextRegs 0x01-0x7F only; WAIT H 0-55 in 8-pixel steps (max usable 52-55 by timing); stored big-endian |
| $64 | vertical line offset (core 3.1.5+) | added to copper, line interrupt and $1E/$1F line numbers; 0 = ULA row 0 is line 0 |
| $22 / $23 | line interrupt: $22 bit 1 enable, bit 0 + $23 = line, bit 2 = ULA interrupt OFF, bit 7 (read) = /INT asserted | fires as the previous line's pixels end; shares /INT with the ULA in pulse mode (never enable under a game) |
| $C0 bit 0, $C4-$CE | hardware IM2 mode, interrupt enables / status / which may break a DMA | vectors: line 0 (highest), CTC 3-10, ULA 11; we stay in pulse mode ($C0 = 0, stub) |

## Z80N (extended Z80) instructions
References:
- Opcode matrix (Z80, undocumented Z80 and Z80N in one table, with sizes, timings and flags per
  opcode): https://ped.7gods.org/Z80N_table_ClrHome.html (Ped7g; he also maintains sjasmplus).
- Descriptions, T-states and errata: SpecNext Wiki "Extended_Z80_instruction_set"
  https://wiki.specnext.dev/Extended_Z80_instruction_set ; matrix mirror: https://table.specnext.dev/
- The matrix's SOURCE is on GitHub (reachable from the sandbox, unlike the two sites above):
  github.com/ped7g/ZXSpectrumNextMisc Z80_ISA_tools/web_table/Z80N_table_ClrHome.html - each cell's
  `axis` attribute = "flags|size|T|description", flag characters in order C N P/V H Z S ('-'
  unaffected, '+' as defined, P parity, V overflow, 0/1, '*' exceptional, blank unknown); the 29
  Z80N cells have class "nn". Original Z80-only table (undocumented opcodes in red):
  https://clrhome.org/table/ . Guide r3 + wiki + this table compared 2026-10-19 (GUIDE_R3_REVIEW).

What nexclash uses (NEXTREG does NOT change the register selected on port 0x243B, so a hook's
NEXTREGs never disturb a game's own 0x243B/0x253B access): `NEXTREG n,n` (ED 91 reg val, 20 T) and `NEXTREG n,A` (ED 92 reg, 17 T) in
every hook, stub and tail, and SWAPNIB (ED 23) in the Rainbow hooks only (since 4dce14af; simulated
by rainbow._swapnib, exhaustive self-test + a SWAPNIB-as-NOP control). Nothing else (asm sources:
`grep -i -E "swapnib|mirror|mul |outinb|pixel|ldirx|ldix|test |bs[lr]"` asm/*.asm).

BLOCK I/O FLAGS (documented): on the Next only ZF is reliable after INI/IND/INIR/INDR/OUTI/OUTD/OTIR/
OTDR (guide r3, wiki errata 2022 and Ped7g's table disagree on the rest); SkoolKit computes real-Z80
flags. Never leave those flags live in a hook (LEARNINGS 1.1).

SIMULATOR TRAP (tested): SkoolKit's Simulator executes any Z80N ED opcode as a 2-byte NOP without
an error (e.g. ED 24 MIRROR A leaves A unchanged). nextboot and the hook verifiers handle ED 91/92
through `after_ED`. If hook code ever uses another Z80N instruction, implement it in the simulator
first (after_ED[op]) or every differential test silently runs the wrong code. Since 2026-10-21
`nexclash/z80n.install(sim, nextreg)` does that for all 29 from the core 3.02.05 VHDL (t80n_mcode.vhd,
t80n.vhd; guide r3 4.15; MAME z80.lst as a cross-check). Where the VHDL settles a caveat below:
ADD rr,A sets CF = 0; OUTINB and JP (C) leave the flags unchanged; LDPIRX flags as LDIX (bits 5/3
unsure). Hooks still must not read a flag the guide calls undefined.

Z80N instructions worth using in future hooks (all 2 bytes unless noted):
| Instruction | Encoding | T | Use for us | Caveat |
|---|---|---|---|---|
| MIRROR A | ED 24 | 8 | bit-reverse a graphics byte (mirrored frames without a 256-byte table) | - |
| SWAPNIB | ED 23 | 8 | nibble swap when packing 4-bit sprite pixels (USED by Rainbow) | - |
| MUL D,E | ED 30 | 8 | DE = D*E (table offsets, frame*size) | flags unchanged |
| ADD HL/DE/BC,A | ED 31/32/33 | 8 | pointer + unsigned A | carry NOT preserved (undefined/reset, wiki notes 3.1.5 / 3.02) |
| ADD HL/DE/BC,nn | ED 34/35/36 lo hi | 16 | pointer + constant | 4 bytes |
| PUSH nn | ED 8A hi lo | 23 | push a constant | operand is BIG-endian (only one) |
| OUTINB | ED 90 | 16 | OUTI without decrementing B: pattern uploads to 0x5B with a fixed port | flags undefined |
| PIXELAD / PIXELDN / SETAE | ED 94 / 93 / 95 | 8 each | ULA pixel address from D=y, E=x; next line; pixel mask (A = $80 >> (E&7)) | PIXELAD undefined for D >= 192; flags unchanged. PIXELAD always returns a 0x4000-based address: retarget H for a screen or shadow copy elsewhere (OR $A0 for 0xE000, lemmings.info 'Advanced programming'); PIXELDN works at any base |
| LDIX / LDIRX | ED A4 / B4 | 16 / 21 | copy skipping bytes equal to A (transparent blit) | flags change like LDI/LDIR - wiki note 2025, TESTED on core 3.02.x; the guide r3 and Ped7g's table still say unchanged (written before that test): assume CHANGED |
| LDDX / LDDRX | ED AC / BC | 16 / 21 | like LDD/LDDR but DE INCREMENTS while HL decrements, skipping bytes = A: horizontally MIRRORED transparent copy of 8-bit pixels (Layer 2 figures) | flags as LDIX |
| LDPIRX | ED B7 | 16 / 21 | pattern fill: source = (HL & $FFF8) + (E & 7), HL fixed, DE incrementing, skip bytes = A | 8-byte aligned table; WRONG RESULT on core 3.02.00 (board 2026-10-21, z80ntest), fixed in 3.02.02 per the core changelog: needs core 3.02.02+ |
| LDWS | ED A5 | 14 | (DE) <- (HL), INC L, INC D: copy down a Layer 2 column (256x192: D = row) | source stays in one 256-byte block; flags of ADD D,1 (CF = D was $FF; board 2026-10-21, not INC D's kept CF) |
| JP (C) | ED 98 | 13 | PC[13:0] = IN(C) << 6 (streamed code) | flags undefined; never needed by hooks |
| TEST n | ED 27 n | 11 | AND flags, A kept | 3 bytes; NF: 0 in Ped7g's table, unknown in the wiki and guide - do not rely on it |
| BSLA/BSRA/BSRL/BSRF/BRLC DE,B | ED 28-2C | 8 | barrel shifts of DE by B: BSLA/BSRA/BSRL/BSRF shift by B&31 (BSRA copies bit 15, BSRF fills 1s), BRLC rotates left by B&15 | flags unchanged |
Timings on the wiki are marked as from limited testing. At 28 MHz (Rainbow hooks) the CPU also adds
wait states; do not count cycles for timing-critical code.
