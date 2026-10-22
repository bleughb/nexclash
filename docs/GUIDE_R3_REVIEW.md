# Review: ZX Spectrum Next Assembler Developer Guide r3 vs our docs (2026-10-19)

Source: github.com/tomaz/zx-next-dev-guide, commit ad8dfb2 (2023-03-27), LaTeX source (every
`chapter-*.tex`, `ports.tex`, `tables.tex`, `instructions.tex`, `defines*.tex`) and its companion
code (`samples/`). Checked against BRIEFING, LEARNINGS, NEXT_REGISTERS, PLAYBOOK, the hook sources
and, where guide and docs disagreed, core 3.01.09 `nextreg.txt` / `ports.txt` / `changelog.md`
(BRIEFING A0 2b). Everything new is "documented" (BRIEFING A0 rules) until a test backs it.

Legend: OK = matches our docs. NEW = added (file in brackets). CONFLICT = guide and another source
disagree (resolution given). Nothing here changed a build.

## Introduction, Next overview
Tooling (sjasmplus 1.18.2, CSpect 2.13, DeZog), changelog, licence. Nothing for us.

## Ports and registers (port table, NextReg list, access examples)
- OK: NEXTREG n,A 17 T / n,n 20 T; reading a NextReg costs 45-51 T (no fast read); 0x303B sets the
  attribute index AND the pattern slot; $35-$39 = attribute bytes ("1-5" in the guide, "0-4" here).
- NEW: ports decoded on the low byte only (0x0B, 0x1F, 0x37, 0x57, 0x5B, 0x6B, 0xDF, 0xFF): an
  original game's stray OUT can reach sprite / DMA hardware [LEARNINGS 1.3].

## Memory map and paging
- OK: 8K/16K banks, MMU $50-$57, $FF = ROM in slots 0/1, legacy + MMU interchangeable (most recent
  wins), 7FFD bit 5 lock, ULA always reads bank 5 (or 7), $8E shortcut.
- NEW: unexpanded Next = pages 0-95 (PLAYBOOK said "check against an unexpanded Next" without the
  number) [LEARNINGS 1.3, PLAYBOOK]; default bank roles (bank 7 = shadow screen + NextZXOS
  workspace, default Layer 2 banks) [LEARNINGS 1.3]. Rainbow (pages <= 63, bank 7 checked empty) OK.
- NEW: 0x123B can page Layer 2 into 0x0000-0x3FFF for reads/writes; the stub writes 0 (safe)
  [NEXT_REGISTERS ports].

## DMA (read in full)
- OK with TECHNIQUES 1 / NEXT_REGISTERS: WR0-WR6, command bytes, continuous mode, port 0x6B since
  core 3.01.02, interrupts lost while the DMA owns the bus.
- NEW [TECHNIQUES 1]: the ~4 cycles/byte figure needs the timing byte on BOTH ports (default =
  Z80 cycle timing); registers persist (repeat = WR0 + load + enable); WR6 $D3 Continue makes
  chunked transfers 2 OUTs each; burst mode + prescaler leaves the CPU able to take interrupts;
  WR4 mode 00 / WR0 op 10-11 must not be used (Zilog modes, may change); read mask / status byte
  00E1101T (byte counter bytes swapped on core 3.00.05).
- CONFLICT (inside the guide): WR4 text names port B address bits as both 3/2 and 3/4; all
  examples set bits 3 and 2 ($AD). Use the examples.
- The old wiki claim "DMA slows above 7 MHz with Layer 2 on" is outdated (guide).

## Palette
- OK: $40/$41/$43, auto-increment values $10/$20/$30.
- NEW [TECHNIQUES 1, NEXT_REGISTERS $43]: $43 bit 7 = 1 turns auto-increment OFF; bits 3:1 select
  the DISPLAYED palette per layer and bit 0 ULANext, so every $43 write also sets them; two
  palettes per layer (one-write recolour).
- NEW [TECHNIQUES 1]: Layer 2 per-colour PRIORITY (second $44 write, bit 7) draws that colour above
  every layer, sprites included - a depth tool for Layer 2 builds (Dizzy 1).
- NEW [TECHNIQUES 1, games/rainbow_islands.md Open 0]: classic ULA palette = ink 0-15, paper
  16-31, separately editable - one paper colour can be made transparent via $14.

## ULA layer
OK throughout (layout, attributes, PIXELAD/PIXELDN/SETAE, shadow screen 7FFD bit 3). Nothing new.

## Layer 2
- OK: $12 bank, 0x123B bit 1 visible, 256x192 layout (page = first + y/32).
- CONFLICT: the guide calls $14 a transparent "index"; core nextreg.txt: a COLOUR compared with the
  top 8 bits of the 9-bit colour. BRIEFING A1 (colour compare) is right [NEXT_REGISTERS $14].
- NEW [BRIEFING C2 #26]: Dizzy 1 writes only $12 and relies on defaults for $70 (resolution),
  $16/$17/$71 (scroll), $18 (clip).
- Info only: 320x256 / 640x256 modes (column-major, 5 banks, cover the border), $69 aliases.

## Tilemap (+ core nextreg.txt)
- OK: 2-byte entries, palette offset per tile, $4C before the offset, $1B clip (X doubled), bank 7
  via $6E/$6F bit 7 (core 3.01.08; the guide predates it and says bank 5 only).
- NEW / CONFLICT WITH A PLAN [TECHNIQUES 1, rainbow Open 0]: $6B bit 0 = 1 forces the tilemap over
  the ULA and overrides the per-tile ULA-over bit; Rainbow writes $81, so its layer-B plan needs $80.
- NEW [TECHNIQUES 1, rainbow Open 1]: 512-tile mode (attribute bit 0 becomes tile bit 8) does not
  help Rainbow (the limit is bank 7's 8K); double-buffering the map there costs 80 of 176 tiles.
- NEW [TECHNIQUES 1]: stencil mode ($68 bit 0), text mode ($6B bit 3), $68 bit 7 ULA off.

## Sprites (read in full)
- OK: pattern RAM, 4-bit anchor halves (the guide's relative-sprite N6 row reads the other way -
  already flagged in LEARNINGS 1.4), $4B, 0x303B status, $15 bit 6, $19 clip, $75-$79 increment on
  each write, composite vs unified inheritance.
- NEW [TECHNIQUES 1]: in a 0x57 stream, a hide record with byte 3 = 0 is 4 bytes long and shifts
  every later sprite - hide with $40.
- NEW [NEXT_REGISTERS 0x303B]: the same write selects the attribute index (bits 6:0) for 0x57.

## Copper (read in full, plus companion code copper/)
- OK with TECHNIQUES 1 (instructions, modes, $63 pairs, MOVE range 0x01-0x7F, line 0 = ULA row 0).
- NEW [TECHNIQUES 1]: every index-sharing register pair ($40/$41/$44, $1C with $18-$1B, $34 with
  $35-$39, $61/$62 with $60/$63) must not be driven by both copper and CPU; live patch = same-mode
  $61/$62 + one $60 write; DMA upload = $63 selected on 0x243B, DMA to 0x253B; NEX files can carry
  a 2048-byte copper block (wiki NEX_file_format).

## Sound (incl. the $06 / $08 register notes)
- AY programming: not used by us.
- NEW [NEXT_REGISTERS $06, BRIEFING C2 #26]: $06 bit 7 (F8 speed key) and bit 5 (F3 50/60 Hz key)
  stay enabled - a player can undo the forced 50 Hz or change the CPU speed mid-game.
- NEW [NEXT_REGISTERS $08]: full bit list; bit 6 = 1 DISABLES contention (the tail clears it: OK);
  bit 0 Issue 2 keyboard (compatibility knob, unused).

## Keyboard
OK (port FE matrix). $B0/$B1 extended keys, $68 bit 4 translation - nothing needed.

## Interrupts (read in full, plus samples im1 / im2 / im2safe / im2hw)
- OK: pulse mode ($C0 = 0), $22/$23 line interrupt (fires as the previous line's pixels end),
  hardware IM2 vectors and DMA interruption only in hardware IM2 mode.
- NEW [LEARNINGS 1.4, NEXT_REGISTERS $C8]: $C8 bits clear by WRITING 1 (Rainbow's diagnostic does).
- NEW [BRIEFING C2 #26]: ULA interrupt can be off via $22 bit 2 or $C4 bit 0.
- CONFLICT: $C4 soft-reset value - core nextreg.txt $83 (line bit set), guide "bit 1 = 0 after
  reset". Unresolved; only matters for the stub guard in C2 #26.
- NEW [LEARNINGS 1.1] (core changelog): undocumented IM 2 opcode ED 7E works from core 3.01.08.

## Zilog Z80 chapter (read in full)
Standard and undocumented Z80 behaviour (SkoolKit models it).
- NEW [LEARNINGS 1.1]: R changes with every M1, so hook code changes R (games reading LD A,R);
  the toolkit already tracks it, the docs did not say why.
- Info: no interrupt right after EI or inside DD/FD prefix runs; LDIR can be interrupted between
  iterations.

## Instruction reference (glance tables, "up close", sorted lists, alphabetical)
Standard Z80 rows scanned for Next-specific notes; every Z80N row compared with NEXT_REGISTERS.
- OK: encodings and T-states of every Z80N instruction NEXT_REGISTERS listed.
- NEW [NEXT_REGISTERS Z80N]: LDDX/LDDRX (mirrored transparent copy), LDPIRX (pattern fill), LDWS
  (column copy for Layer 2), JP (C); TEST n leaves NF undefined.
- CONFLICT [NEXT_REGISTERS]: guide - LDIX family leaves flags unchanged; wiki - flags change like
  LDI on core 3.02. Keep "assume changed". RESOLVED 2026-10-21: core 3.02.05 t80n VHDL sets them
  like LDI (shared I_BT path); nexclash/z80n.py follows it.
- NEW, IMPORTANT [LEARNINGS 1.1, BRIEFING A1 blind spots, NEXT_REGISTERS]: on the Next the block
  I/O instructions (INI..OTDR) leave SF/HF/PV undefined, NF = 1, CF unchanged; the simulator
  computes real-Z80 flags, so verify cannot prove flags after them. All hooks checked: none
  leaves those flags live (Trueno's `ensure` does, but its caller overwrites them with OR A).
- Info: OUT (C),0 outputs 0 on the Next.

## Companion code (samples/)
copper, im1, im2, im2safe, im2hw, layer2-256x192/320x256/640x256, sound, sprites, tilemap: same
material as their chapters (findings above). Extra confirmations: DMA fill with port A fixed
(layer2 clear in copper/), SAVENEX CFG "preserve next registers 0 = set to defaults".

## Follow-up: opcode tables (same day)
Ped7g's Z80N table (table.specnext.dev / ped.7gods.org; source on GitHub, ZXSpectrumNextMisc
Z80_ISA_tools/web_table) and the wiki's Extended_Z80_instruction_set compared with the above;
clrhome.org/table is the Z80-only original (undocumented opcodes in red).
- CORRECTED [LEARNINGS 1.1, BRIEFING A1, NEXT_REGISTERS]: after block I/O only ZF is reliable. The
  guide's "NF = 1, CF unchanged" is contradicted by the wiki errata (2022: carry IS modified) and
  the table (all flags but Z unknown).
- SETTLED [NEXT_REGISTERS]: LDIX/LDDX/LDIRX/LDDRX change flags like LDI etc. - wiki note 2025, tested
  on core 3.02.x; guide and table predate the test. LDPIRX untested: assume changed.
- TEST n NF: table 0, wiki and guide unknown - do not rely on it. ADD rr,A carry: wiki 2025 "most
  probably always reset" - still treated as undefined.
- NEW [NEXT_REGISTERS]: NEXTREG leaves the port 0x243B selection alone; barrel-shift masks (B&31,
  BRLC B&15); PIXELAD undefined for D >= 192.
- NEW [LEARNINGS 1.1]: the 29 Z80N opcodes are 2-byte NOPs on a stock Z80 - a game executing one
  behaves differently on the Next only.

## Follow-up: open-source Next titles (itch.io playlist, same day)
Of the itch.io "Complete ZX Spectrum Next Playlist" (64 of 174 pages checked), full source was
offered by 4: ZxNext Studio TechDemo (GitHub, read: lockstep $09 + OUT to $57 attributes, unrolled
OUTINB pattern upload -> TECHNIQUES 1), CosmoScroll (page claims the port source is in
github.com/abodelot/cosmoscroll - neither branch holds Next code), Happy Next Year 2026 and
Z-machine Loader (itch.io downloads, unreachable from the sandbox). Happy Next Year 2026's .asm
files were then supplied by Dean and read in full -> TECHNIQUES 1 (4-byte attribute records,
double-buffered pattern slots, per-frame copper rebuild by DMA, DMA overlap fill, unverified
$15-resets-clip claim).

## Open after this review
- Which NextRegs NEXLOAD resets (NEX byte 134 = 0) - decides BRIEFING C2 #26.
- $C4 soft-reset value (core $83 vs guide).
- Everything in TECHNIQUES 1: untested; the first engine to use a technique teaches the simulator
  and records the hardware result.
