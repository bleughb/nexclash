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
Wiki pages are read with web_fetch (search first: the fetch tool only opens URLs seen in results).

Partial decoding (wiki note): legacy devices test only some address bits. Next ports ignore the
top byte where OTIR must work (0x57, 0x5B). The ULA answers on any even port (A0=0). With 48K or
128K timing, 7FFD answers on A15=0 and A1:0=01, ignoring A14 (VHDL); with +3 timing A14 must be 1.

## NextRegs (write with NEXTREG; read by selecting via 0x243B, then reading 0x253B)
| Reg | Wiki page | What we use it for | Where |
|---|---|---|---|
| $03 | Machine Type Register | display timing 48K/128K (bits 6:4, bit 7 = allow change); written last in the tail. Does NOT stop 7FFD decoding | z80tonex tail |
| $05 | Peripheral 1 Setting Register | bit 2 cleared = 50 Hz (unless --allow-60hz) | z80tonex stub |
| $06 | Peripheral 2 Setting Register | bit 4 cleared = divMMC automap / DRIVE-button NMI off (the A1 table used to say $0A) | z80tonex stub |
| $07 | CPU Speed Register | 0 = 3.5 MHz for games; 3 = 28 MHz inside Rainbow hooks, 0 on exit | stub, rainbow_hooks |
| $08 | Peripheral 3 Setting Register | contention; bit 7 write 1 = clear the 7FFD lock (0 does nothing; read 1 = unlocked) | tail, altrom stub |
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
| $40 / $41 / $43 | Palette Index / Palette Value (8-bit) / ULA Palette Control | $43=$20 selects sprite palette 0 with auto-increment; $43=$30 the tilemap palette | setup templates, Rainbow setup |
| $4B | Sprite Transparency Index Register | 0 = index 0 transparent (reset value $E3; 4-bit uses the low nibble) | setup |
| $50-$57 | MMU slot 0-7 Registers | 8K page per slot; $FF in slot 0/1 = ROM (or the alt ROM) | stub, tail, hooks |
| $7F | User Storage 0 Register | "player drawn" flag (slot1/altrom TID hooks); Rainbow: tile-cache flush request | hooks |
| $8C | Alternate ROM Register | $C0 write mode (fill), $80 enable read-only; hardware-tested 2026-09-27 | altrom stub, tail |
| $C0 | Interrupt Control Register | 0 = pulse interrupt mode (Next IM2 hardware vectors off) | z80tonex stub |
| $8E | Memory Mapping Register | not used; writes act like 7FFD/DFFD/1FFD port writes | - |

## Ports
| Port | Wiki page | Use |
|---|---|---|
| 0x243B / 0x253B | TBBlue Register Select / Access | read NextRegs ($7F, $08, $05, $06) |
| 0x303B | Sprite Status/Slot Select | write: pattern slot (bits 5:0, bit 7 = +128 bytes); read: bit 1 = too many sprites on a line, bit 0 = collision (the read clears both) |
| 0x5B | Sprite Pattern Upload | pattern bytes; auto-advance (256-byte blocks by OTIR) |
| 0x7FFD | Memory Paging Control | bit 5 = lock; unlocked writes also reset MMU0/1 to ROM and MMU6/7 to the bank |
| 0x1FFD | Plus 3 Memory Paging Control | bit 2 + 7FFD bit 4 select the ROM (ROM3 = 48K = alt image 1) |
| 0xDFFD | Next Memory Bank Select | not used (bank MSBs) |
| 0xFE | ULA Control Port | border (restored by the tail) |

## Not used yet, candidates (see docs/BRIEFING.md A0)
- Copper ($60-$64): could write sprite attributes at fixed raster lines without the CPU.
- zxnDMA (port 0x6B): fast pattern uploads from RAM to port 0x5B.
- Line interrupt ($22/$23): per-line timing.
- Sprite attribute auto-increment registers ($75-$79).

## Z80N (extended Z80) instructions
References:
- Opcode matrix (Z80, undocumented Z80 and Z80N in one table, with sizes, timings and flags per
  opcode): https://ped.7gods.org/Z80N_table_ClrHome.html (Ped7g; he also maintains sjasmplus).
- Descriptions, T-states and errata: SpecNext Wiki "Extended_Z80_instruction_set"
  https://wiki.specnext.dev/Extended_Z80_instruction_set ; matrix mirror: https://table.specnext.dev/

What nexclash uses: ONLY `NEXTREG n,n` (ED 91 reg val, 20 T) and `NEXTREG n,A` (ED 92 reg, 17 T)
in every hook, stub and tail (checked 2026-09-29: asm sources + all hex blobs). Nothing else.

SIMULATOR TRAP (tested): SkoolKit's Simulator executes any Z80N ED opcode as a 2-byte NOP without
an error (e.g. ED 24 MIRROR A leaves A unchanged). nextboot and the hook verifiers handle ED 91/92
through `after_ED`. If hook code ever uses another Z80N instruction, implement it in the simulator
first (after_ED[op]) or every differential test silently runs the wrong code.

Z80N instructions worth using in future hooks (all 2 bytes unless noted):
| Instruction | Encoding | T | Use for us | Caveat |
|---|---|---|---|---|
| MIRROR A | ED 24 | 8 | bit-reverse a graphics byte (mirrored frames without a 256-byte table) | - |
| SWAPNIB | ED 23 | 8 | nibble swap when packing 4-bit sprite pixels | - |
| MUL D,E | ED 30 | 8 | DE = D*E (table offsets, frame*size) | flags unchanged |
| ADD HL/DE/BC,A | ED 31/32/33 | 8 | pointer + unsigned A | carry NOT preserved (undefined/reset, wiki notes 3.1.5 / 3.02) |
| ADD HL/DE/BC,nn | ED 34/35/36 lo hi | 16 | pointer + constant | 4 bytes |
| PUSH nn | ED 8A hi lo | 23 | push a constant | operand is BIG-endian (only one) |
| OUTINB | ED 90 | 16 | OUTI without decrementing B: pattern uploads to 0x5B with a fixed port | flags undefined |
| PIXELAD / PIXELDN / SETAE | ED 94 / 93 / 95 | 8 each | ULA pixel address from D=y, E=x; next line; pixel mask | - |
| LDIX / LDIRX | ED A4 / B4 | 16 / 21 | copy skipping bytes equal to A (transparent blit) | flags change like LDI/LDIR on 3.02 (wiki) |
| TEST n | ED 27 n | 11 | AND flags, A kept | 3 bytes |
| BSLA/BSRA/BSRL/BSRF/BRLC DE,B | ED 28-2C | 8 | barrel shifts of DE by B | - |
Timings on the wiki are marked as from limited testing. At 28 MHz (Rainbow hooks) the CPU also adds
wait states; do not count cycles for timing-critical code.
