# Techniques - Spectrum Next methods and other projects (reference, mostly documented)

Look things up here by heading; do not read it end to end. Moved out of LEARNINGS (2026-10-20),
which keeps only lessons that cost a debugging cycle. Each entry says where it comes from and
whether it is hardware-tested; an untested technique is proven by the first engine that uses it
(simulator model + hardware test, BRIEFING C2 #28 for the test recipe).

## 1. Faster sprite / tilemap I/O, DMA, copper, raster, palettes
Researched 2026-10-19 (guide r3 chapters Sprites / DMA / Copper / Interrupts, core 3.01.09
nextreg.txt + ports.txt + changelog, KevB's copper timing notes in github.com/varmfskii/zxnext_code
zx_next_notes/copper; github.com/stevemonks/ZXSpectrumNextMachineCodeGuides;
github.com/breakintoprogram/lib-spectrum-next lib/dma.z80; full guide r3 review: GUIDE_R3_REVIEW.md). Nothing here is simulated or hardware-tested: the first engine that uses one
implements it in the simulator (NEXT_REGISTERS "SIMULATOR TRAP") and records the hardware result.
Register / port detail: NEXT_REGISTERS.md "Not used yet". Cost estimates are 3.5 MHz T-states.

### 1.0 Measured costs on a board (tools/hwtests/nextbench, core 3.02.00, 2026-10-22)
Microseconds per call on a real Next (raster-line timing, call overhead subtracted). These are
HARDWARE-MEASURED; the estimates in the rest of this section are not. 28 MHz = the hooks' speed.

| Work | Technique | 3.5 MHz | 28 MHz | 28 MHz per byte |
|---|---|---|---|---|
| copy 256 B | LDIR | 1548.6 | 220.5 | 0.861 |
| | LDI x256 unrolled | 1250.7 | 185.6 | 0.725 |
| | stack (POP / PUSH) | 961.1 | 145.6 | 0.569 |
| | LDIRX | 1546.4 | 221.1 | 0.864 |
| | DMA | 394.1 WRONG | 60.2 | |
| copy 2K | LDIR | 12289.7 | 1755.9 | 0.857 |
| | DMA | 2451.7 WRONG | 381.6 | 0.179 |
| DMA set-up | DMA 1 byte (program + start) | 102.6 WRONG | 14.7 | |
| | program only (no ENABLE) | 94.3 | 13.5 | |
| fill 256 B | LDIR / PUSH / DMA | 1539.7 / 419.0 / 395.1 WRONG | 220.2 / 57.4 / 60.2 | 0.860 / 0.224 / ~0.18 |
| sprite pattern 256 B -> 0x5B | OTIR / OUTI unrolled / OUTINB / DMA | 1546.4 / 1252.4 / 1255.8 / 402.8 | 221.3 / 186.7 / 186.7 / 61.6 | 0.864 / 0.729 / 0.729 / 0.184 |
| one sprite's 4 attributes | port 0x57 / NEXTREG $34-$38 (constant values) | 30.5 / 28.6 | 4.5 / 4.5 | |
| one register | NEXTREG n,v / NEXTREG n,A / OUT 243B + 253B | 5.7 / 6.8 / 14.9 | 0.9 / 1.0 / 2.2 | |
| paging | NEXTREG $56 / OUT 0x7FFD | 5.5 / 8.2 | 0.9 / 1.2 | |
| one 8x8 cell | ULA (8 B + attr) / tilemap entry / Layer 2 (64 B) | 61.6 / 7.3 / 360.9 | 9.4 / 1.1 / 53.8 | |
| scroll | tilemap or Layer 2 offset regs / copy one 256 B screen band | 11.4 / 1538.9 | 1.6 / 220.5 | |
| palette entry | NEXTREG $43 / $40 / $41 | 17.1 | 2.7 | |
| copper list 32 instructions | NEXTREG $60 / OUT $253B loop (DJNZ count) | 800.7 / 773.2 | 123.4 / 115.7 | |

What it says:
- DMA set-up is ~14.5 us at 28 MHz (~13.5 of it writing the 16-byte program); after that 0.18 us a
  byte, memory or port. Break-even at 28 MHz: vs LDIR ~21 bytes, vs unrolled LDI / OUTI ~27, vs a
  stack copy ~37; vs a PUSH fill ~330 bytes. Rewriting only the changed DMA registers would cut
  the set-up (not measured).
- DMA at 3.5 MHz gives WRONG copies on core 3.02.00 (every check failed; the core changelog fixes
  it in 3.02.02); at 28 MHz every DMA copy / fill was right. Use DMA only at 28 MHz, or require
  core 3.02.02+.
- 28 MHz is ~6.3-7x 3.5 MHz, not 8x: each memory read adds a wait state, so (T + reads) / 8
  (LEARNINGS 2.1f): LDIR 21 T + 3 reads -> 3.0 T a byte at 3.5 MHz terms = 0.857 us (measured 0.861).
- Sprite pattern upload: DMA is ~3x OUTI for a 256-byte pattern and ~1.8x for a 64-byte one
  (14.5 + 64 x 0.18 = 26 us vs 47 us). OUTINB = OUTI. Sprite attributes: port and NEXTREG the
  same here only because v1's NEXTREG side wrote constants (`NEXTREG $35,32`); with values loaded
  from memory, as hooks do (`LD A,(HL) : NEXTREG $35,A : INC HL`), NEXTREG is slower: 1.0b, 4.6 vs
  6.7 us.
- NEXTREG is 2.4x faster than the port pair; MMU paging (NEXTREG) a little faster than OUT 0x7FFD.
- An 8x8 cell: a tilemap entry is ~8x cheaper than the ULA cell and ~50x cheaper than a Layer 2
  cell; hardware scroll costs 1.6 us against 220 us per 256 bytes copied.
- Copper upload: the port loop is slightly faster than NEXTREG $60 per byte at 28 MHz. v1 counted
  the 64 bytes with DJNZ (~3.9 us an instruction by NEXTREG $60); 1.0b's loop counts with a 16-bit
  DE (it also loads 256 instructions), hence its higher 160.7 us for the same 32 instructions.

### 1.0b Sizes, reuse and the copper (tools/hwtests/nextbench v2, core 3.02.00, 2026-10-22)
Same board, same method; R chosen per row. Microseconds per call at 28 MHz (3.5 MHz on the photos,
specnext reference/hwtests/nextbench/; every 3.5 MHz CPU row again matched its T-state count).
v2's line read could return a line up to 3 lines late (LEARNINGS 2.3; fixed in v3): at 28 MHz that
is under 1 % on the rows below (one read is far shorter than a line there). v3 on the same board
(2026-10-22, 5 runs): NO value varied between runs beyond its rounding (variation page "none"), and
its 28 MHz means agree with this table within 0.5 % (LDIR 2048 1754.7, DMA 2048 380.5, stack 2048
1154.2, PUSH fill 2048 459.1, OUTI 2048 1405.7, NEXTREG 0.9): the table stands, and one run of a
technique is a reliable figure on a given core. DMA at 3.5 MHz (still wrong copies on 3.02.00):
1 B 102.7, 16 B 117.8, 256 B 393.9, 2 KB 2441.4 us; port uploads 64 B 182.3, 256 B 401.6.

| Copy (bytes) | 1 | 16 | 64 | 256 | 1024 | 2048 |
|---|---|---|---|---|---|---|
| LDIR | 2.0 | 14.9 | 56.1 | 220.9 | 881.3 | 1759.6 |
| LDI unrolled | 2.0 | 12.2 | 44.8 | 175.2 | 704.8 | 1407.1 |
| stack (POP / PUSH unrolled) | - | 11.2 | 38.3 | 146.6 | 578.7 | 1157.5 |
| DMA, full program each call | 14.7 | 17.5 | 26.1 | 60.4 | 197.7 | 380.9 |
| DMA, addresses + length only (rtg) | | 13.2 | | 56.1 | | 376.7 |
| DMA, LOAD + ENABLE only (same transfer again) | | | | 49.3 | | |
| DMA burst mode | | | | 60.4 | | 380.9 |

| Other (28 MHz) | sizes -> us |
|---|---|
| fill LDIR / PUSH / DMA | 16: 14.4 / 7.6 / 17.5; 256: 220.5 / 59.1 / 60.4; 2048: 1759.6 / 459.5 / 380.9 |
| sprite pattern OTIR / OUTI / DMA | 64: 56.8 / 45.9 / 27.2; 128: 111.7 / 89.3 / 38.7; 256: 221.7 / 176.5 / 61.7; 2048: 1766.6 / 1409.6 / 382.3 |
| sprite attributes (4 bytes, values from memory) port 0x57 / NEXTREG $34-$38 | 1 sprite: 4.6 / 6.7; 32 sprites: 111.7 / 243.4 |
| hide 128 sprites: NEXTREG $78 post-increment / port 0x57 records / $15 off | 188.7 / 441.9 / 0.9 |
| NEXTREG n,v / n,A / port pair / read a NextReg | 0.9 / 1.0 / 2.3 / 1.9 |
| MMU 1 slot / 4 slots / OUT 0x7FFD | 0.9 / 3.6 / 1.2 |
| 8x8 cell ULA / tilemap entry / Layer 2 | 9.5 / 1.1 / 54.0 |
| tilemap base $6E / Layer 2 bank $12 / shadow screen flip + back | 0.9 / 0.9 / 2.1 |
| palette 1 entry 8-bit / 16 entries / 1 entry 9-bit / select ($43) | 2.7 / 32.8 / 3.6 / 0.9 |
| copper load 8 / 32 / 256 instructions by NEXTREG $60 | 42.1 / 160.7 / 1267.9 |
| copper load 8 / 32 / 256 by OUT $253B | 39.0 / 143.0 / 1122.1 |
| copper start + stop | 1.8 |
| LDIR 256 while the copper loops MOVEs | 220.9 (= without) |

Copper function rows: CP WAIT (WAIT line 120 -> MOVE seen by the CPU) at line 120 at 28 MHz (v2: 122
at 3.5 MHz, which was v2's late line read; v3 reads 120 at both speeds) - copper line numbers = the
$1E / $1F raster line. CP APART:
0 of 256 palette entries wrong while the copper looped MOVE $7F and the CPU wrote / read the palette
by NEXTREG and the port pair. CP SHARE: 255 of 256 wrong with the copper looping MOVE $40.

What v2 adds:
- DMA set-up depends on what is rewritten: full 16-byte program ~14.5 us, addresses + length
  (11 bytes) ~10.3, LOAD + ENABLE (3 bytes) ~3.5; then 0.179 us a byte. Keep the ports
  programmed and only re-run / retarget: break-even vs LDIR drops to ~5 bytes (re-run) / ~15
  (retarget), vs a stack copy ~9 / ~26. Burst mode = continuous here (no prescaler).
- Copy below ~37 bytes with a fresh DMA program: stack copy (needs fixed addresses / SP games),
  else unrolled LDI. Fills up to ~300 bytes: PUSH.
- Sprite attributes in bulk: port 0x57 (OTIR) is 2.2x faster than NEXTREG per sprite; hiding a run
  of sprites: NEXTREG $78 with post-increment is 2.3x faster than the port.
- The copper does NOT slow CPU memory work and does NOT disturb CPU NEXTREG / port-pair access to
  other registers (CP APART 0): it is usable next to the hooks as long as the two never drive one
  register pair (CP SHARE confirms that rule). Its WAIT lines are the CPU's raster lines.
- Copper lists: the port loop is ~12 % faster than NEXTREG $60; ~2.2 us a byte = ~4.4 us an
  instruction at 28 MHz by the port loop (~5.0 by NEXTREG $60), so reload only what changed.
- Sprite attributes in bulk: write port 0x303B = first sprite, then the 5 bytes per sprite
  (= $35..$39 in order) to port 0x57; the sprite index advances after each sprite's last byte
  (4 bytes when byte 3 bit 6 = 0), wraps 127 -> 0. OTIR 21 T/byte = ~105 T/sprite, unrolled OUTI
  16 T/byte; our hooks pay ~180 T/sprite ($34 select + 5 x LD A,(DE) / NEXTREG / INC DE).
  WHY it can break: 0x303B ALSO sets the pattern-upload slot (same write, bits 6:0 + bit 7), so a
  loop that uploads a pattern then writes that sprite's attributes (Rainbow piece loop) must
  become two passes - all patterns first, then one 0x303B + all attributes. And a sprite whose
  byte 3 has bit 6 = 0 takes only 4 bytes: a HIDE record written as byte 3 = 0 inside a
  5-bytes-per-sprite stream shifts every later sprite by one byte. Hide with byte 3 = $40 (no
  pattern, byte 4 follows) in a 5-byte stream.
- Random-access fast attributes (github.com/serdjukdev/ZxNextStudio-TechDemo code/render/sprite.asm):
  set NextReg $09 bit 4 (lockstep) ONCE in setup; then `NEXTREG $34,n` also moves port 0x57's index,
  and a sprite costs NEXTREG $34 (17 T) + 5 x OUT (C),r (12 T, C = $57) = ~77 T instead of ~180 T,
  in any order, without restructuring a pattern-then-attributes loop. Caveat: with lockstep every
  $34 write also moves the PATTERN pointer (bit 7 = +128 bytes), so finish a pattern upload before
  selecting the next sprite. Same demo uploads patterns with an unrolled OUTINB (DUP 128: 16 T/byte
  vs OTIR 21 T/byte, B untouched).
- Mercenary Next (Mike Dailly, github.com/mikedailly/MercenaryDisassembly, 2025): a 48K game
  disassembled with SkoolKit (sna2skool -c ctl) whose line draw is patched to Layer 2 - the closest
  published relative of nexclash. Techniques:
  * Runtime-switchable patches: a table of (site, hook, 3 saved original bytes); Apply writes
    JP hook at each site, Remove puts the saved bytes back, and the key G toggles enhanced <->
    original (plus CPU 14 <-> 3.5 MHz) while playing. One .nex gives a live hardware A/B
    (BRIEFING C2 #29). Sites must be RAM (alt-ROM sites cannot be switched back).
  * Layer 2 drawn by the CPU through port 0x123B instead of MMU paging: %11001011 maps all 48K of
    the SHADOW Layer 2 ($13) for read+write over 0x0000-0xBFFF (the stack included: DI, no
    calls), so a pixel is LD (HL),c with H = y, L = x; %00000010 unmaps (display stays on).
  * Double buffering = draw into $13 via 0x123B bit 3, flip = swap $12 / $13 (two NEXTREGs).
  * WRITE-only mapping splits reads from writes (em00k Tilemap_with_data_at_0000, 2023): 0x123B bit 0
    set and bit 2 clear sends WRITES to 0x0000-0x3FFF into Layer 2 (bits 7:6 = which 16K), while
    READS and instruction fetches still come from what MMU slots 0/1 hold (his tile data page:
    `LDI` copies data page -> Layer 2 at the same address). Shipped use: Mike Dailly's Next ray
    caster (blog part 4, 2023) maps the whole 48K Layer 2 WRITE-only over 0x0000-0xBFFF and pages
    its generated span renderers into the ROM slots for READ, so D = screen row with no paging in
    the inner loop (LDWS / LDIX straight from texture to screen). For us, a CANDIDATE (not tested): hook
    code in the alt ROM (slot 0) could write Layer 2 directly, with no MMU slot to free and no page
    to map back - Layer 2 plots without touching slots 2-7 (dizzy1 / wally2 map pages today). To
    check first: that write-mapping wins over the alt ROM ($8C) at 0x0000-0x3FFF on hardware, that
    the game's ISR never writes 0x0000-0x3FFF while it is on (turn it off before any EI), and that
    nextboot / verify model a write-only 0x123B (they model the port; whether reads stay on the
    ROM is unchecked).
  * The Layer 2 scroll offset ($16/$17) moves the game's window origin to Layer 2 (0,0) and the
    clip ($18) trims it, so game coordinates need no adds per pixel.
  * Ring-buffer scrolling (em00k L2TopDownWorldScroll, 320x256 Layer 2, 16x16 tiles, 2026-10-20):
    the screen buffer wraps (X 0-319 via $16 + $71 bit 0, Y 0-255 via $17), so a scroll moves only
    the offsets, and ONE new column (16 tiles) or row (20 tiles) is drawn when a tile edge is
    crossed - not the whole screen. The new column / row lands just past the right / bottom edge,
    and the Layer 2 clip ($18) hides it while it is drawn. For us: a game that scrolls by redrawing
    its whole screen could have the redraw replaced like this ONLY where the game never reads the
    picture back. Not for Rainbow: its blit is inside the game's own 1.2 ms per frame
    (games/rainbow_islands.md), so the hooks would save nothing.
  * Line colour by self-modifying the immediate operand of every plotter (`ld (hl),n`) from a
    table of patch addresses - one write per colour change, nothing in the inner loop.
  * Boot: game RAM loaded into high banks, copied down by the .nex start code; the ULA picture is
    left running underneath (Layer 2 over it, SLU).
- Happy Next Year 2026 (Leonis, source supplied by Dean 2026-10-19) confirms and adds:
  * 4-byte attribute records: with byte 3 bit 6 = 0 a sprite takes 4 bytes on port 0x57, so
    "hide all" = one 0x303B select + 4 x OUT 0 per sprite (the 5-byte-stream trap above does not
    apply to an all-4-byte stream). Only for 8-bit patterns: our 4-bit sprites need byte 4.
  * Double-buffered PATTERN slots: upload the next frame's images by DMA (0x303B + memory ->
    port 0x5B) into the slot set NOT on screen, spread over two frames (4 + 5 patterns), then flip
    which set the attributes use - no half-updated sprite is ever displayed (generalises the
    Commando flicker rule in LEARNINGS 1.4 and the pattern cache).
  * Per-frame copper rebuild: patch the list in RAM, stop the copper ($62/$61 = 0), DMA the list to
    port 0x253B with $60 selected, restart in mode 11 - all done after a $1E/$1F wait for the line
    AFTER THE LIST'S LAST WAIT (192 only when the list ends above it), so the list is never
    half-written while the beam uses it. em00k's zx-next-copper-wobble (2021) has WAITs down to
    line 255 and glitched in CSpect until the rewrite waited for line 250+. A per-line WAIT + MOVE
    $16 pair gives a per-scanline Layer 2 X offset (raster wobble); MOVE $17 per line does the same
    vertically (a line repeated or skipped = stretch / squash).
  * Static WAIT skeleton (Dean's copper-bar demos, ZX Basic, 2026-10-20): build the list ONCE with
    one WAIT per scanline (+ two MOVE $44 per line), then per frame rewrite only the MOVE data bytes
    and DMA the list up. WHY: WAITs must appear in increasing raster order - a WAIT for a line the
    beam has passed holds the rest of the list until the next frame (inferred from the guide's
    WAIT description, not tested) - so lists rebuilt per frame from moving objects must be sorted;
    a fixed per-line skeleton never needs sorting, and overlaps resolve by write order. Cost: 6
    bytes per line (192 lines = 1154 bytes of the 2048).
  * Per-line palette colour: $43 = $90 (Layer 2 palette 1st, auto-increment OFF), $40 = index once,
    then per line MOVE $44 x2 (9-bit colour) recolours that one entry down the screen - copper bars
    behind a Layer 2 cleared to that index. The changed entry stops matching $14 (a COLOUR
    compare), so 'transparent' pixels become visible: a game layer whose entry the copper rewrites
    loses its see-through pixels. Same demos: $64 = 33 aligns copper line 0 with the 320x256 Layer 2
    top (not checked against KevB's tables).
  * DMA fill by overlap: memory -> memory with destination = source + 1 (the LDIR fill idiom)
    fills a block, e.g. a 257-byte IM2 vector table; alternative to fixed-port-A fill.
  * UNVERIFIED claim in its Copper.asm: copper MOVEs to NextReg $15 "reset clipping values", so the
    demo uses a second list without $15 while clip windows animate. Not in the core spec; test
    before driving $15 from a copper list that coexists with $19/$1A/$1B clips.
- NextReg $34 and port 0x303B are SEPARATE sprite indices unless NextReg $09 bit 4 (lockstep) is
  set. Never mix $34/$35-$39 writes and 0x57 writes on one assumption of "the current sprite";
  hooks that only use NEXTREG keep working whatever 0x57 did, and the reverse.
- $75-$79 = $35-$39 with sprite-number post-increment on EACH write (nextreg.txt). Useful where a
  run of sprites gets one attribute: hide sprites a..b = NEXTREG $34,a then NEXTREG $78,0 per
  sprite (20 T) instead of $34 + $38 per sprite (37 T + loop) - every hook's hide loop.
- Relative sprites: an anchor followed by relatives (byte 4 bits 7:6 = 01; anchor byte 4 bit 5 = 1
  makes them unified, 0 composite; guide r3 Sprites example) moves,
  hides, mirrors and (unified) scales the whole group with ONE anchor write; relatives hold 8-bit
  offsets and can take the anchor's pattern number as a base. Candidate for multi-sprite figures
  (2x2 boxes) - but a mirrored unified group mirrors as one image, so the per-engine "swap the left
  and right quads" logic (BRIEFING A1) must go, and the pixel check must cover it.
- zxnDMA (port 0x6B since core 3.01.02; 0x0B = Zilog-compatible DMA): memory -> memory, memory ->
  fixed port (0x5B patterns, 0x57 attributes, 0x253B with a NextReg selected on 0x243B). With
  port cycle length 2 a byte costs ~4 cycles vs LDIR 21 / OTIR 21 T - but only with the timing
  byte sent for BOTH ports (WR1/WR2 bit 6 + byte %00000010); without it the DMA uses standard Z80
  cycle timing. Program upload (~15-25 bytes by OTIR) costs ~400 T, so it pays from ~30 bytes;
  registers persist between transfers, so a repeat with a new address needs only WR0 (+ WR4) +
  $CF load + $87 enable. Exact form (em00k ninja-sprite-dma, per 256-byte sprite pattern): program
  everything ONCE (port B = 0x5B, length 256), then per pattern `OUT (0x6B)` x5: $1D (WR0: transfer
  A->B, port-A address bytes follow, no length), address low, address high, $CF, $87 - ~87 T with
  the pattern slot already set on 0x303B. So a re-armed DMA pays from a few bytes, not ~30: worth it
  for the per-commit pattern uploads (midres / renegade caches) when the source is linear in memory.
  Continuous mode (WR4 bits 6:5 = 01) holds the bus to the end; never use
  WR4 mode 00 or WR0 operation 10/11 (they act as continuous / transfer today but are Zilog byte /
  search modes and may change). FILL = port A FIXED memory (WR1 %00100100) pointing at one byte holding the value,
  port B incrementing: clears a shadow / map / buffer at DMA speed (lib-spectrum-next FillDMA).
  Fixed memory -> fixed port 0x5B fills pattern RAM the same way (Rainbow setup zeroes 16K with an
  OUT loop). Library code wraps the program OTIR in DI/EI because an ISR that also programs the
  DMA would interleave its bytes with ours; hooks may skip the DI only when neither the game's ISR
  nor a hook called from it writes port 0x6B / 0x0B (original Spectrum games never do; check any
  128K/Next-aware title's port writes first).
  WHY it can break: the CPU cannot see a pulse-mode interrupt while the DMA owns the bus, and the
  ULA pulse lasts ~30 T at 3.5 MHz, so a transfer across the interrupt LOSES the game's frame
  interrupt (DI does not help; the pulse is gone). Engines with interrupts ON (midres, dizzy1,
  chuckie; BRIEFING A3) may only DMA where the interrupt cannot fall (raster known, A1:
  interrupt near line 248) or in pieces shorter than the gap. Pieces are cheap: WR6 $D3
  (Continue) resets the byte counter and keeps the pointers, so after the first program each
  further chunk is `$D3, $87` (2 OUTs) continuing where the last ended. Burst mode + prescaler
  (WR2 timing byte bit 5 + prescaler byte; rate = 875 kHz / prescaler, scaled by video timing $11)
  hands the bus back to the CPU between bytes, so the pulse interrupt is seen - slow, but safe for
  background copies (specnext.com/the-zxndma; hardware to confirm). Hardware IM2 mode ($C0 bit 0 +
  $CC-$CE) can let interrupts break into a DMA, but we run pulse mode and the game's own IM/ISR.
- Copper (NextRegs $60-$63, $64): 1024 16-bit instructions in its own 2K write-only RAM, WAIT
  line 0-311 + horizontal 0-55 (8-pixel steps), MOVE value -> NextReg 0x01-0x7F ONLY (7-bit field:
  $8C, $C0-$CE, $B8+ are out of reach), mode 11 restarts the list every frame, so `WAIT 176 / MOVE
  $6E,x / HALT` re-applies x every frame at line 176. No CPU or DMA time is taken.
  Uses for us: apply a finished tilemap (base $6E, clip $1B, $6B on/off) or a sprite attribute
  list at a fixed safe line instead of a CPU raster busy-wait; the CPU only flips one byte of the
  list ($61/$62 = byte index, $60 = data; $62 with an unchanged mode only moves the index).
  WHY it can break: copper MOVEs to $34 change the CPU's selected sprite between two of its
  NEXTREGs - with copper-driven sprites, the CPU must not use $34-$39 (use 0x57: separate index).
  The same holds for EVERY register pair with an internal index: $40/$41/$44 (palette index), $1C
  with $18/$19/$1A/$1B (clip index), $34/$35-$39, $61/$62 with $60/$63: the copper and the CPU must
  never both drive one pair. A list that holds two maps / two attribute sets needs both to be
  complete before the flip byte changes (the copper reads it at its line, any frame). Patching a
  live list byte: $61/$62 = byte index with the SAME mode bits (11), then ONE write to $60 ($63
  commits only pairs); guide r3 companion code copper/ does exactly this. Uploading a list by DMA:
  select $63 on port 0x243B, then DMA memory -> fixed port 0x253B. A .nex can also carry a
  2048-byte copper block (NEX format, wiki NEX_file_format; how the loader applies it is not
  documented there).
- Raster numbering: Active Video Line ($1E/$1F), line interrupt ($22/$23) and copper WAIT all
  count from ULA pixel row 0 UNLESS NextReg $64 (core 3.01.05+) is non-zero: it offsets all three
  (changelog 3.01.05). Frame length differs by timing: 48K 312 lines, 128K 311, HDMI 312 (60 Hz:
  262/261); display rows 0-191, then border + blanking. A raster wait that assumes 312 lines or
  offset 0 is a hardware-only fault (BRIEFING C2 #26).
  The freeze trap (a Next developer's note, 2026-10-22; matches Gen4's patch_copper_y): with $64 = 0
  the line just above ULA row 0 is the LAST line of the frame, numbered 260, 261, 310, 311 or 319
  by mode. A copper WAIT or a CPU poll for a line the current mode does not have (311 in VGA 60 Hz)
  never fires: the copper holds, the CPU loops forever. With $64 = 32 the top border starts the
  count (ULA row 0 = line 32, the line above it = 31 in every mode) and the lines a mode lacks are
  all at the bottom: wait only for lines below the shortest frame you support (261 lines at 60 Hz).
  Open: the copper demos above say $64 = 33 aligns the 320x256 Layer 2 top - one line apart from
  this note; a board test (BRIEFING C2 #28) settles it. Our code assumes $64 = 0 (and a frame of at
  least 258 lines: nextbench frame_sync, Rainbow rsafe), so the stub must reset $64 (C2 #26), and the
  F3 key (50 / 60 Hz) changes the frame length under a running game.
- Tilemap attribute byte (2-byte entries): bits 7:4 palette offset (used), bit 3 X mirror, bit 2 Y
  mirror, bit 1 rotate 90 clockwise (with the mirrors: 0/90/180/270), bit 0 ULA over the tile.
  A tile that is another's mirror or rotation needs NO definition of its own: dedupe tile
  definitions by orientation before running out of the shared budget (Rainbow: 176). Tilemap
  scroll is per pixel ($2F/$30 X 0-319, $31 Y 0-255, wraps; stevemonks guide SimpleTileMap):
  a map can follow a pixel scroll by offsetting $30/$31 instead of switching the layer off - the
  clip window ($1B) stays fixed, so rows that wrap in must be built too.
  $6B bit 0 = 1 FORCES the whole tilemap over the ULA and overrides the per-tile bit 0 (core
  nextreg.txt): per-tile "ULA over this tile" only works with $6B bit 0 = 0 (Rainbow writes $6B =
  $81 today; its tiles all have bit 0 = 0, so $80 would show the same picture). 512-tile mode ($6B
  bit 1) turns attribute bit 0 into tile bit 8 (no per-tile ULA priority); it does not help when
  the limit is memory (bank 7 = 8K for map + definitions). When memory IS the limit, two $6B bits
  shrink it (em00k's "Hardware Tilemaps", NextBuild Patreon, 2026-10-20; text mode bits per the wiki
  Tilemap page, NOT tested): bit 5 = 1-byte map entries (every tile takes the $6C default attribute,
  so no per-tile palette offset or mirror): a 40x32 map is 1280 bytes instead of 2560. Bit 3 = text
  mode: 1-bit tile definitions, 8 bytes instead of 32, and the attribute's bits 7:1 are a 7-bit
  palette offset that colours the set bits. Spectrum cell graphics are 1-bit already, so text mode
  holds 4x the definitions in the same 8K, coloured per tile like ULA ink - a candidate for the
  Rainbow tile budget (games/rainbow_islands.md Open 1). Stencil mode ($68 bit 0): pixel = ULA AND
  tilemap colour, transparent if either is. Tilemap transparency $4C is compared before the
  palette offset (soft reset $0F; our setups write 0).
- Hardware ground truth: github.com/MrKWatkins/ZXSpectrumNextTests (Ped7g's Next test suite, .snx
  per test with board photos + emulator screenshots, 2026-10-20). Run the matching test before
  trusting an emulator for a feature. Results that bear on us:
  * Copper: CSpect 2.11.1 and ZEsarUX 8.0 BAD, MAME 0.282 OK, board core 3.01.05 OK. Copper WAIT
    compares the horizontal position as >= on the current line: a WAIT for an h already passed ON
    THE SAME LINE does not wait (no roll-over into the next frame). Rewriting $61/$62 with the same
    mode bits does not disturb a running list (already in the Copper bullet above; the test proves it on hardware).
  * Sprites (Sprites/ScanlineDelay, core 3.00.07+): the sprite engine swaps its line buffer at sprite
    X = -1, so an attribute change shows ONE scanline later; to change a sprite from line N on,
    write it before copper WAIT(line N-2, h ~50). A commit racing the beam tears by whole lines.
  * Raster line read (Timing/ScanlineReadingAndInterrupt): a board with core 3.01.00 at 3.5 MHz
    sometimes READ A WRONG VALUE from $1F (a wait for line 224 fired near 192). $1E and $1F are
    also two reads: crossing line 255 -> 256 between them gives a value 256 lines off. For a beam
    test read the pair until two consecutive reads agree (rainbow_z80n rsafe); for TIMING that loop
    returns a late line - read LSB, MSB, LSB instead (LEARNINGS 2.3, nextbench v3). Core 3.02.00 at
    3.5 MHz showed no wrong $1F read in nextbench v3 (5 x 176 timed reads, lines 0-~230).
  * DMA (base/DMA) runs at 28 MHz only (NextReg 7 = 3): it never covered 3.5 MHz, where nextbench
    found wrong copies on 3.02.00. Its "short init" also restarts with CONTINUE ($D3: length reset,
    addresses kept) instead of LOAD - a cheaper re-run than our rrun (LOAD + ENABLE), not measured.
  * Layer 2 over ROM (Graphics/Layer2Port, board core 3.01.05 + MAME OK): write-over-ROM and
    read-over-ROM (data, CODE, even the IM1 handler fetched from Layer 2) for 16K / 48K, visible
    and shadow; bank offset form (0x123B bit 4). It does NOT test the alt ROM ($8C): the template
    for BRIEFING C2 #30.
  * NextReg defaults: CSpect 2.9.2 and ZEsarUX 8.0 BAD, MAME 0.282 OK.
  * Also there: ZX48_ZX128/Z80IntSkip (EI / DD / FD blocks inhibit interrupts; LD A,I / LD A,R
    IFF2 bug - we read it twice anyway, PLAYBOOK 4), Interrupts/HaltAfterDisable, Timing/
    Changing8kBank (cost of an MMU swap), DMA, Z80N opcodes.
- Sprites BETWEEN the ULA and the tilemap (Mike Dailly, lemmings.info "Putting sprites between ULA
  and tilemap"; NOT tested, bit meanings from his post): the tilemap belongs to the ULA layer, so
  the normal $15 orders can only put both above or both below the sprites. Layer order $15 bits
  4:2 = %110 (the first blend mode) with $68 bits 6:5 = %01 (no blending) gives (U|T) S (T|U): ULA
  and tilemap BOTH in front of the sprites, then the per-tile attribute bit 0 ("ULA over this
  tile"; $6C for 1-byte maps, and $6B bit 0 must be 0) moves that tile BEHIND the sprites. So depth
  per 8x8 cell: foreground scenery as tiles (or the ULA) in front of figures, the rest behind -
  an alternative to masked sprites for a depth rule (Commando masks, LEARNINGS 1.4) when the
  foreground is cell-aligned. BRIEFING C2 #32.
- Palette control $43 is TWO things at once: bits 6:4 pick the palette to EDIT, bits 3:1 the ACTIVE
  second/first palette for sprites / Layer 2 / ULA and bit 0 ULANext; bit 7 = 1 turns
  auto-increment OFF. Every $43 write therefore also re-selects the displayed palettes (fine while
  everything uses first palettes, as all our builds do). Each layer has two palettes: flipping
  bits 3:1 recolours a whole layer in one write (cheap colour animation, e.g. pulsing items).
- Layer 2 per-colour priority (guide r3 Palette/Layer 2): the second $44 write for a LAYER 2
  palette entry has bit 7 = priority - pixels in that colour draw above ALL layers, sprites
  included, whatever $15 says. Candidate for depth: Layer 2 foreground pieces in front of a
  hardware-sprite player (Dizzy 1 draws figures on Layer 2; the "sprites cannot sit behind some
  objects" limit in LEARNINGS 1.4 is about the ULA). Needs the colour twice (one entry with, one without).
- ULA palette: classic ULA uses indices 0-7 ink, 8-15 bright ink, 16-23 paper, 24-31 bright paper
  (border from paper). Paper and ink entries are separate, so ONE paper colour can be set equal to
  the global transparency $14 (compared with the colour, not an index) to see the layer behind
  wherever that paper shows, without touching inks. Candidate for Rainbow layer B.
- Line interrupt: do NOT enable it ($22 bit 1 / $C4 bit 1) under a game in pulse mode: it raises the
  same /INT, so the GAME's ISR runs a second time per frame (frame counters, music, input). The
  ULA interrupt can also be disabled there ($22 bit 2) - never under a game. For hook timing use
  the copper or a $1E/$1F poll.

## 2. Techniques from other projects (by topic)

Read from the source of the projects listed in 2.9 (licence, what was read, reviews of their code
before reuse). NONE of them was run by us: a figure from their comments is marked as theirs, a cost
"by 1.0b" is our board figure applied to their code. The source is named first in each bullet.
Section 1 cites other projects too (Mercenary Next, Happy Next Year, em00k's ring-buffer scroller,
Ped7g's test suite) where a technique there is mostly about one Next feature.

### 2.1 Copper
- Load a list by DMA (l2scroller start_copper / TransferDMAPort; Gen4; Speedball; Happy Next Year
  in section 1): stop the copper, index 0 ($61 / $62), select $60 on port $243B (DI between the
  select and the DMA: Gen4), DMA memory -> fixed port $253B, start. Mode 11 restarts the list every
  frame by itself; mode 01 runs it once per start, so Gen4 / Speedball restart it every frame.
  Cost by 1.0b (port-DMA figures, not measured as such): ~14.5 us + 0.36 us an instruction at 28 MHz
  against ~4.4 us an instruction by an OUT loop - ~10x for long lists; Gen4's ~1150-byte list
  ~14.5 + 1150 x 0.18 = ~225 us against ~2.5 ms (zxnext-copper-samples, Gen4).
- Patch the list in RAM, reload it whole every frame (Gen4): WAIT + MOVE tilemap X ($30) + two MOVEs
  of palette index 1 (9-bit) per line, 144 lines, ~1.2 KB; per frame the MOVE values get a sine
  wobble per line and a rolling 90-line colour gradient. Grodan / scoopex rebuild their raster lists
  from tables every frame by a NEXTREG $60 loop instead (stop $62, $61 = 0, load, start): ~4.4 us an
  instruction at 28 MHz (1.0b).
- Rewrite a RUNNING list (zx-next-copper-wobble): each frame the CPU rewrites all 256 x 3
  instructions by NEXTREG $60 (~1.5 KB; by 1.0b's copper load by NEXTREG $60, ~5 us an instruction
  = ~3.8 ms at 28 MHz - DMA would take ~0.3 ms) into the list the copper is running, then sets $61
  = 0 / $62 = mode 11: the index goes back to 0, and rewriting the same mode bits does not restart a
  running list (section 1, Copper). It tolerates a frame that mixes old and new values. If a frame
  must not: stop the copper ($62 = 0) before the writes, or build the list in RAM and load it by
  DMA.
- Upload only the half not running (zxnext-copper-samples): mode 11, and from a line interrupt that
  alternates between line 200 and line 10 (one compare register, two calls a frame) upload only the
  HALF of the list the copper is not executing; the $61 / $62 write includes the mode bits, so
  setting the write index does not stop the list.
- End of list: WAIT line 511 (%10000001,255), a line that never comes = HALT until the restart
  (zx-next-copper-wobble).
- WAIT near a line's end (zxnext-copper-samples, commit "Handle copper matching near end of lines"):
  the last ~128 dots of a line are never matched by a WAIT; a WAIT for an h there waits until that
  line comes round next FRAME. Wait for (line + 1, 0) instead.
- Raster counters and the top border:
  * zxnext-copper-samples: copper raster counters follow the machine type (NextReg $03) and 50 /
    60 Hz only, not the VGA / HDMI mode: 896 dots a line at 48K timing, 912 at 128K / Next, 312 /
    311 lines (264 at 60 Hz by their notes; Gen4 / DynaTile and "Raster numbering" in section 1 say
    262 / 261 - not checked on a board); WAIT h = dot / 16.
  * Gen4 patch_copper_y converts display Y (32 border lines above ULA line 0) to copper lines: Y -
    32, and a negative result wraps to (lines per frame) + (Y - 32), the line count read from the
    video mode (312 HDMI / 48K, 311 128K, 320 Pentagon, 262 / 261 at 60 Hz; DynaTile / Tilemap carry
    the same table). A list that touches the top border must do the same: those lines belong to the
    END of the copper's frame and their numbers depend on the mode.
  * zx-next-copper-wobble paces the CPU on $1F LSB = 250 (a line every mode has; l2scroller too);
    its README's "now works in CSpect after correctly waiting for the last line" and a
    commented-out $64 = 31 are the same top-border numbering issue as the freeze trap ("Raster
    numbering" in section 1).
- Per-line effects:
  * Layer 2 offsets per line (zx-next-copper-wobble): WAIT line n / MOVE $16 / MOVE $17 from a sine
    table on every line; the Y offset per line picks which picture row a screen line shows (stretch
    / wave with no redraw). WAIT encoded as NEXTREG $60,$80 / $60,line. The sine table is 256 bytes
    duplicated (DUP 2) so `ADD HL,A` with A = 0-255 plus an offset never needs a wrap.
  * One scrolled band (l2scroller): WAIT 184 / MOVE $16 = n, WAIT 192 / MOVE $16 = 0, HALT - a
    4-instruction list reloaded every frame by DMA with n + 1 (the drawing side: 2.2).
  * Palette bars: MOVE $40 / $41 per line (Spreadpoint's DNA gradient; Grodan / scoopex rasters).
  * Status bar over a scrolling tilemap (Tilemap): at the bar's line the copper MOVEs the tilemap X
    / Y offsets ($2F-$31), the clip window ($1C / $1B) and a palette entry, and a second WAIT where
    the circular 32-row map wraps changes Y again, so the map can scroll through its buffer while
    the bar stays still. Speedball's HUD: a 5-instruction list (WAIT line 215, tilemap scroll 0,
    HUD tile definitions via $6F). For us: Rainbow already clips the tilemap to the play area and
    switches it off when a render's scroll is not a multiple of 8 (never seen), so no split is
    needed there; a game that scrolls by pixels with a HUD would use this split instead of
    redrawing.
  * More tiles than one tile bank holds (Grodan backdrop.s): the copper rewrites the
    tile-definition base ($6F) and the default tile attribute ($6C, palette offset) at band
    boundaries (WAIT 80, ...), so each horizontal band of the screen has its own tile set and
    colours. For us: Rainbow's 176-tile cache (games/rainbow_islands.md, tile budget) could get one
    set per screen band - but tile definitions must sit in bank 5 / bank 7 (16K each; Rainbow uses
    bank 7's first 8K), so memory, not the copper, is the limit.
  * Sprite priority mid-frame (Gen4): MOVE $15 bit 6 at a line (which sprite number is on top), so
    the two halves of the screen overlap their sprites in opposite order.
  * Sound by copper: 2.6.

### 2.2 Layer 2 and ULA: drawing and scrolling
- Copy from banked memory into Layer 2 in ONE address window (l2scroller): the source pages sit in
  MMU slots 0 / 1 ($0000-$3FFF) and port $123B maps the Layer 2 third for WRITES only over the same
  $0000-$3FFF (value yy000011: write enable + visible, bits 7:6 = which 64-line third). Reads still
  come from the MMU pages, writes go to Layer 2, so an LDIR whose HL and DE both point into
  $0000-$3FFF copies picture data straight into Layer 2 with no buffer ("WRITE-only mapping" in
  section 1). Data pages at MMU 0/1 cover the ROM's IM 1 handler at $0038: interrupts must be off.
- Circular buffer, draw only the new edge:
  * l2scroller: the scrolled band (2.1) wraps (X offset mod 256), so each frame the CPU draws just
    ONE 1-pixel column (8 bytes) of the current letter at x = n - 1, the column that has just
    scrolled round to the right edge: 8 bytes of drawing a frame.
  * zxnext_layer2_tilemap: the Layer 2 offsets ($16 / $71 / $17) move the picture; per step only
    the newly exposed pixel ROW (or column) is drawn across the screen - 8 bytes of every tile along
    the edge, at the wrapped position (mod 192 / mod 320 by Ped7g's look-up tables) - into a
    circular Layer 2. A scroll costs one line of drawing, not a screen copy (the same idea as
    em00k's ring-buffer scroller in section 1).
- A SOFTWARE tilemap drawn into Layer 2 (zxnext_layer2_tilemap): full-colour 8x8 tiles, 512 of them
  in two 8K pages, map + per-tile attributes rotate / X / Y mirror like the hardware tilemap,
  256x192 or 320x256.
- LDWS in its natural job (zxnext_layer2_tilemap): (DE) = (HL), INC L, INC D. In 320x256 Layer 2
  (column-major, address = x * 256 + y) INC D is the next pixel to the right, so 8 x LDWS draws a
  tile row and ADD DE,$F801 steps to the next line; in 256x192 (row-major) INC D is the next line,
  so the same instruction draws a tile column. Tiles are stored once; the 8 orientations are 8
  unrolled routines, picked per resolution (a 256x192 "normal" tile is the 320x256 "rotated +
  mirrored" one, drawn with LDI). LDWS 14 T a byte vs LDI 16 T, and the source stays in one
  256-byte page. Our Rainbow note says LDWS is not useful there (per-nibble transparency); it fits
  wherever an engine copies whole OPAQUE blocks into Layer 2 (1.0: an 8x8 Layer 2 cell by LDI 54
  us at 28 MHz) - wally2 / dizzy1 draw figures with transparency, so not there as they stand.
- Layer 2 16K banks mapped as two MMU slots (zxnext_layer2_tilemap bank_set_16k) at the 64-line /
  64-column boundary.
- Plot order (l2scroller): "snake" ordering tested (rows stored alternately left-to-right /
  right-to-left so the plot never returns to the left edge); the author found plain row-by-row LDIR
  ("typewriter") quickest.
- Loading a picture (zx-next-copper-wobble): Layer 2 bank 12 ($12) loaded as 8K pages 24-29 from
  tut.bmp (incbin skipping the 1078-byte header + palette; the file's height is +192 = stored
  bottom-up, so the art must have been flipped beforehand, and its palette is NOT loaded: pixel
  bytes must already be colours of the default Layer 2 palette, RGB332).
- Compressed data over pages (Next Point dzx7_paged): ZX7 decompression whose source pointer steps
  to the next 8K page at the slot-6 boundary (Layer 2 screens).
- ULA hardware scroll $26 / $27 (Grodan layer_ula.s): the classic screen scrolled by NextReg, no
  redraw (also in our C2 #26 reset list).
- A Layer 2 bitmap background scrolled by $16 behind sprite rows (Gen4, 2.4).

### 2.3 Hardware tilemap
- Streaming more tiles than the slots hold (DynaTile): a map of up to 1500 "software" tiles goes
  through the 355 hardware tile slots of a 4-bit tilemap: per software tile a reference count and
  its hardware slot, per slot its software tile, free slots in a linked list. A tile scrolling in
  takes a slot only on its first use (count 0 -> 1) and uploads its 32 bytes; a slot goes back to
  the free list when its count drops to 0. O(1) per tile, no search. Upload by DMA with a split
  program (2.5). For us: Rainbow's tile cache (games/rainbow_islands.md, "Objects on the tilemap")
  rebuilds per render from a key (hash + 16 probes) because its tiles are COMPOSED from objects, not
  copied, so a count-and-free-list allocator fits only where a cell's tile has a fixed source (a map
  tile); DMA helps only for copied tiles.
- Coarse scroll by re-copying the map (Speedball): a 40x32 tilemap with 16-bit entries, 512 tiles;
  coarse vertical scroll by re-copying all 31 visible map rows (2,480 bytes) into the tilemap by DMA
  every frame (~460 us at 28 MHz, no circular buffer), fine scroll by $31 = (Y AND 7) - 8 (hides the
  8 top border lines). It sets $6E = $E0 while the map is written at page 14 offset 0: works only if
  a bank-7 address wraps within its 8K (our inference from the code, not tested).
- Status bar split and a tile set per screen band: 2.1.

### 2.4 Sprites
- Multi-sprite figures as anchor + relatives:
  * Next Point (Aseprite): each animation frame is ONE blob in a banked page: 5 attribute bytes per
    16x16 sprite (anchor + unified relatives, offsets baked in by their converter) followed by the
    8-bit patterns. A frame CHANGE sends the attributes by OTIR to $57 and the patterns by DMA to
    $5B; a plain move writes only the anchor (NEXTREG $34 + X, Y, attr 2, attr 4: 5 writes).
    Pattern slots are allocated per skin at start-up (max patterns over its frames), attribute
    slots per entity. The anchor-only move, in a shipped game.
  * Speedball: ten 32x32 figures, each = one 4-bit anchor + 3 COMPOSITE relatives at (+16,0),
    (0,+16), (+16,+16) with pattern-relative numbers: the 4 patterns sit as 4 x 128 contiguous bytes
    (anchor N, +N6 half, N+1, N+1 +N6) so ONE 512-byte DMA to port $5B fills a figure. A 4-bit
    pattern number n is selected on port $303B as `RRC n` (slot n >> 1, bit 7 = the 128-byte half).
  * Gen4 sprite rows: per row 3 anchors 128 px apart, each with 7 unified relatives
    (pattern-relative, cycling through a pattern range); scrolling a row = new anchor X (9-bit: X8
    in byte 2) in the buffer; the parallax speeds of the rows come from a small table updated each
    frame, over a Layer 2 bitmap background scrolled by $16.
  * For us: figures that move as one take anchor-only writes (5 NEXTREGs instead of 20 per 2x2
    figure) - but composite relatives do not mirror as a group, so a left-facing figure still needs
    its offsets swapped, as our engines do now.
- Patterns only when the frame changes, by DMA: Speedball re-sends a figure's patterns only when its
  animation frame changes (an "uploaded" flag cleared by the animation timer; the timers start
  staggered so uploads spread over frames); Next Point the same per frame change. Our pattern-slot
  caches (Commando, Smash TV) with DMA on a miss: ~107 us per 512 bytes against ~350 us by OUTI at
  28 MHz (1.0b).
- Attributes every frame with lockstep (Speedball): NEXTREG $35-$38 + $79 with NextReg $09 bit 4;
  $79 post-increments the sprite number, so no $34 per sprite; 20 NEXTREGs per figure. The 3
  relatives never change: writing only the anchor (select $34 + 5 registers) would do.
- Sprite "bobs" (UnitedForces): patterns by OTIR to $5B once, attributes per frame by OUT to $57.
- Multiplexing by chained line interrupts (Gen4, hardware IM2 mode): a table of (handler, line)
  pairs; each handler acknowledges ($C8 bit 1), EIs at once (the frame interrupt may nest),
  rewrites the line-interrupt line ($22 / $23) and PATCHES vector table entry 0 with the next
  handler, then re-sends a band's sprite attributes from RAM buffers to port $57 starting at sprite
  0 - the same hardware sprites reused for the next band once the beam has passed. Two "update"
  handlers rebuild the buffers of the half the beam is not showing.

### 2.5 DMA
- Split program (DynaTile): the length and port modes written once, then per transfer only
  addresses + LOAD + ENABLE (9 bytes; our "rtg" row in 1.0b: ~13 us + 0.18 us a byte, ~19 us for a
  32-byte tile vs ~28 us by LDIR).
- Fill from a fixed-address source (UnitedForces: clear a buffer, then swap screen thirds).
- Copper lists, sprite patterns and tilemap rows by DMA: 2.1, 2.4, 2.3.

### 2.6 Interrupts and sound
- Hardware IM2 mode is the norm in Next-native code (every seedy1812 port, DynaTile, Tilemap,
  Next Point, zxnext-copper-samples, NextMasterSystem): $C0 bit 0, $C4-$C6 enables, $CC-$CE (which
  interrupts may stop a running DMA). Variants: ULA interrupt only, the handler counts frames and
  acknowledges $C8 bit 0 (Speedball); the line interrupt as the frame interrupt (DynaTile / Tilemap:
  $C0 = 1 + table bits 7:5, $C4 = 2, $22 / $23 line 192); ULA interrupt off and line interrupt on,
  vector table entry 0 = line interrupt (zxnext-copper-samples; our NEXT_REGISTERS $C0 note: line =
  highest priority). We run pulse mode under the game's own IM / ISR (BRIEFING C2 #34).
- Held interrupts (NextMasterSystem; source read 2026-10-20): `NEXTREG $C0,1` (+ $C4/$C5/$C6
  enables, I = table page) makes the Next HOLD each interrupt until it is acknowledged (RETI), so
  runtime code may run with interrupts OFF for as long as it likes and no frame interrupt is lost -
  unlike pulse mode, where a DI longer than the INT pulse drops the interrupt. Their IM2 vector does
  the acknowledging RETI itself, straight into the game's own handler ($0038) with the interrupted
  PC on the stack, so the game's handler (ending in EI; RET or RETI) is unchanged. A frame event
  that arrives while the game's handler still runs is held and delivered from the handler's return
  slot (`isr_tramp`). The runtime owns I, so the game's `LD A,I` / `LD I,A` are trapped and served
  from a shadow I (Wonder Boy III keeps flags in I). For us: BRIEFING C2 #34. Board-tested
  2026-10-20 (tools/hwtests/im2hold): held over a 3-frame DI; vector $16; and a handler ending
  plain RET leaves the interrupt unacknowledged and NO later interrupt arrives until a RETI runs -
  why their RETI goes first and the game's handler after it.
- Gotchas (Next Point comments): change $C0 read-modify-write (NextZXOS since core 3.01.10 runs the
  stackless NMI, $C0 bit 3); clear the status registers $C8-$CA with $FF before enabling; CTC
  interrupts arrived although $C5 was 0, so start the CTC only after setting hardware IM2 mode; the
  ULA handler EIs at once so a CTC sample interrupt is never delayed by the frame work.
- F8 (speed) and F3 (50 / 60 Hz) keys off: every seedy1812 port writes NextReg $06 AND $5F at start
  - the guard BRIEFING C2 #26 proposes for our stub.
- Sample sound by copper (zxnext-copper-samples): the copper plays 8-bit stereo PCM at ~11 kHz by
  MOVEs to the DAC mirror NextRegs (DAC_B / DAC_C) with a WAIT between ticks - sound with no CPU
  timing at all.
- Sample sound by CTC timer interrupt (Next Point): CTC channel 0 interrupts at ~16 kHz (control
  word $85, time constant 109: "28 MHz / (16 x (1 + 109))"; the clock source is from their comment,
  not checked) in hardware IM2 mode (vector 3); the handler maps the sample's 8K page at slot 6,
  sends one byte to a DAC port per channel (two channels: DAC ports M0 and L1), steps the page at
  the 8K boundary, acknowledges (NEXTREG $C9,1: CTC 0 status) and RETIs. Cost: roughly 200-350 T
  per interrupt with both channels playing (estimated from the code, not counted), 16,000 a second
  = a tenth to a sixth of 28 MHz - against nothing per sample for the copper player. CTC channel 1
  runs a second timer (palette fade steps).
- For us: C2 #37 (beeper replay) has two candidate players: copper-driven (no CPU per sample, one
  frame of latency) or a CTC interrupt (~10 % CPU at 16 kHz; needs hardware IM2 mode, C2 #34).
- Sprite multiplexing by chained line interrupts: 2.4.

### 2.7 Arithmetic (ped7g/ZXSpectrumNextMisc)
- MUL-based arithmetic with T counts - 16x8, 24x8, 32x8+8, 16x16 multiplies; E / 10 in 33-60 T (MUL
  + BSRL); HL mod 40 / 192 / 320 / 640 (192 = screen rows, 320 / 640 = Layer 2 widths); `nibrrca`
  (rotate both nibbles with RRCA + TEST $88 + RET PE / XOR $88); detectZ80N (ED 24 00 00 = MIRROR A
  on a Z80N, safe NOPs elsewhere); findVLinesCount (lines per frame from the $1F wrap: tight IN
  loop, as our frame_sync). Their tests also pass on our z80n.py (tools/hwtests/README, z80ntest
  section). For us: the address sums in hooks (Rainbow speed idea 4: x32 / x64 + base) - MUL D,E is
  8 T but needs D / E free.

### 2.8 Patching another machine's games (NextMasterSystem)
NextMasterSystem runs Master System games' own Z80 code on the Next by patching every I/O site into
a call to a runtime that drives tilemap, sprites, copper and AY - our method on another machine,
with per-game "overlays" (patch lists + switches + native code pages) matched by cart CRC32. Its
interrupt handling is in 2.6 (held interrupts). Design notes (docs/design.md there):
- Runtime owns ONE slot (7) for the whole game; parts 2-4 BORROW a game slot only while they run,
  with written rules (which part may call which, who restores slot N from `cur_mmu`) and a
  build-time page-end check (tools/check-layout). Our hook-page rules (midres slot 5) are the same
  idea, kept less formally.
- Interrupts while a borrowed page is mapped: the IM2 entry first maps the GAME's page back under
  the handler and puts its own trampoline in the handler's return slot; the trampoline maps the
  borrowed page again and resumes. So the game's ISR always sees its own memory, whatever slot the
  runtime borrowed - the alternative when no slot is free of the ISR (BRIEFING C2 #33).
- Every exit from runtime to game code carries a label prefix (`mx_`); a MAME script puts entry
  breakpoints on every handler and exit breakpoints on every `mx_` label and reports runtime cycles
  per frame vs game cycles on the real core model (BRIEFING C2 #1: our missing hook-cost measure).
- Costed features are per-game switches applied by patching CALL targets at start: switched off,
  the frame runs exactly the instructions it ran without the feature (zero cost, nothing to verify
  for games that do not use it). A rare check is ARMED only when needed: a JP written over an exit
  for ~5 s after the rare event, written back after.
- A run of patched OUTs in a row is compiled once into one block transfer and cached by site
  address + mapped pages (code copied to RAM is never cached: it can change under the same page).
- Converted graphics prepared ahead: the whole cart is converted to Next tile rows at start (~1.1 s
  per 256K) and tiles written whole from ROM are COPIED, not converted. nexclash builds offline, so
  the same pre-conversion can happen in Python at build time (Next RAM store, LEARNINGS 2.5).
- A display-off / display-on pair the original did inside the vertical blank can land in the
  picture on the slower machine: they HOLD the off-write until the matching on-write or a timeout,
  so the screen does not flash. Same class of fault as our hide/show flicker rule (LEARNINGS 1.4).
Source (src/runtime/fw*.asm, tools/sitescan.py, docs/*.md, read 2026-10-20):
- Trap frame: entry = `EX (SP),HL; PUSH AF; LD A,I; DI`, then the game's IFF2 decides whether an
  `EI` or a `NOP` is written into the exit just before its `RET` (EI's one-instruction delay means
  no interrupt lands before the RET). Then it switches to its own stack and keeps the game's BC / DE
  / AF at fixed addresses, so handlers may use every register. One LD A,I read only: that relies on
  the Next's LD A,I being safe (Ped7g Z80IntSkip v5.0 tests exactly this; we read twice, PLAYBOOK 4,
  until that test is photographed on a board).
- Patch form for a 2-byte site: `RST v` + one inline byte (the operation / port code) = exactly the
  bytes of `OUT (n),A` / `IN A,(n)`, so no neighbour is touched. The vector is a free RST of the
  game, or the game's own `DI; IM 1` bytes at $0000-$0002 (start moved to $0003, the runtime does DI
  + IM 2). For us: the alt ROM holds every RST target, so an RST that neither the game nor any ROM
  routine it calls ever runs (proved by `scan`) can carry a hook dispatcher - a 2-byte site where a
  3-byte CALL would cross into bytes the game rewrites (Dizzy 1, 2.1). Not used yet.
- Speed rule at 28 MHz (MAME tbblue, measured with breakpoints printing totalcycles [MAME]): a
  native instruction costs its Z80 T-states + 1 cycle per MEMORY READ (its own opcode / operand
  bytes and the data it reads; writes and I/O add nothing). 311 lines x 1,824 = 567,264 cycles a 50
  Hz frame. A hook cost estimate from the simulator's T-states becomes T + reads in 28 MHz cycles
  (= (T + reads) / 8 in 3.5 MHz T-states, as in 1.0), not T / 8 (BRIEFING C2 #1). A single trapped
  I/O instruction cost them ~1,000-2,100 cycles, which is why loops of OUTs are compiled into one
  trace call.
- Static site scanner (sitescan.py, ~5,600 lines, stdlib only): recursive-descent disassembly from
  the reset / interrupt vectors, following proven jumps, plus emulator PC logs as extra entry
  points, unreached byte patterns rated by how code-like their neighbours are, a per-routine cost
  model, and "pattern rules" - code shapes that broke or slowed earlier games. Our `scan` is dynamic
  only (what the RZX ran); a static pass would find the plot callers no recording reaches (PLAYBOOK
  3b "list every caller from the code"; BRIEFING C2 #11). Design worth copying: per routine a
  data-flow pass with abstract values (constant / value at entry / table base + index / stack bytes
  relative to entry SP), routine summaries (returns? skips inline bytes? keeps which registers?),
  repeated to a fixed point; jump tables read until an entry stops looking like code; `PUSH nn; RET`
  and `EX (SP),HL` inline-argument calls; task switches (`LD SP,x; RET`) listed, not followed;
  OBJECT HANDLER FIELDS: a `LD L,(IX+d) / LD H,(IX+d+1) / JP (HL)` dispatcher marks field d, and
  every store of a constant, table word or caller-passed pair into (IX+d) becomes an entry - exactly
  how most games reach their plot calls (per-object update routines). Byte scans rate unreached
  patterns: a setter just before, a JP/CALL that targets it, 32 bytes before decoding as a chain
  ending exactly there, valid code after; NOP / RST-heavy neighbourhoods rate low (tile data).
- Pattern rule "mailbox race": a RAM byte the interrupt handler reads and clears, written twice by
  the foreground with different values before the handler runs; on the slower machine the handler
  can land between the two stores and one value is lost (My Hero, checked in MAME). Our hooks also
  change where interrupts land (BRIEFING A1 blind spot).
- Frame cost model per routine (costliest path, loop counts from DJNZ / DEC r / DEC rr + OR pattern
  with B or rr known from the caller), split interrupt / foreground, flags "TEAR RISK" when the
  interrupt handler keeps interrupts off past the Next's ULA interrupt line. Our `cost` measures
  from the RZX instead; the static model would rate routines no recording reaches.
- Library pages: a replacement routine shared by several games is one source file that starts with
  its CONTRACT (the routine it replaces, the scanner rule that finds it, each entry's registers in
  and out, flags and interrupt state, what it needs from the game), and the build fails when two
  games' copies differ.

### 2.9 Sources (licence, what was read, reuse reviews)
All read 2026-10-22 unless noted; none run by us. "Ideas only" = no licence file: no code copied
into the repo without the author's permission. GPL-3.0, MIT, Unlicense and CC0 are compatible with
ours.
- l2scroller (github.com/em00k/l2scroller; ideas only; ~650 lines, every .asm read; hardware.inc
  is Ped7g's constants file): a text scroller on the bottom 8 lines of a 256x192 Layer 2 picture.
  Reuse review:
  * get_xy_pos_l2 (D = y, E = x -> Layer 2 third mapped for writes over $0000-$3FFF, D = y AND 63):
    sound, 256x192 only. Leaves the write overlay ON (the caller turns it off: OUT $123B,2).
  * straight_plot (source WxH image from banks into Layer 2, row by row): right for sources up to
    16K only - the bank-crossing test `LD A,H : OR $C0 : CALL Z,.nextbanks` is never zero (meant
    AND), and .nextbanks itself is wrong (multiplies the bank by 4, its AND result discarded). It
    also maps data pages at MMU 0/1, over the ROM's IM 1 handler at $0038, without a DI (it works
    because nothing enables interrupts). Fix both before reuse.
  * snake_plot: experimental and broken (its .check_line compares A after get_xy_pos_l2 has changed
    it); not used by the demo. L2Line: infinite loop (B never decremented); unused.
  * clsL2: clears FIVE 16K banks from the Layer 2 bank (320x256 size) although the picture is
    256x192 (3 banks): it wipes two banks beyond Layer 2. Use 3 for 256x192.
  * plot_l2: one pixel by the write overlay; correct (turns writes off after).
  * Scroller (update_scroller / scroll_text): correct. The copper list's own MOVE value byte
    (init_copper.layer2_xoffset - 1) is the scroll position; the column drawn at x = that value,
    before update_copper adds 1, appears at screen x 255. Leaves MMU 0 = the font page and the
    Layer 2 write overlay on.
  * start_copper / TransferDMAPort: the copper-by-DMA loader (2.1) - correct, the reusable core.
- zx-next-copper-wobble (github.com/em00k/zx-next-copper-wobble; GPL-3.0; 200 lines, all of
  main.asm read): a 256x192 Layer 2 picture wobbled per line by the copper. Reuse review: the list
  builder is correct for lines 0-255 (lines 192-255 are border / blanking and harmless); the copper
  is never stopped, so a frame mixes old and new values (2.1: stop it first, or load by DMA).
- zxnext_layer2_tilemap (github.com/vmorilla/zxnext_layer2_tilemap, a copy of benbaker76's demo;
  MIT; z88dk C + asm): software tilemap in Layer 2.
- Next Point (github.com/vmorilla/next-point; GPL-3.0; z88dk C + asm): a released tennis game for
  the White Next contest, runs on hardware and CSpect.
- seedy1812 demo ports (github.com/seedy1812): scoopex, Grodan-And-Kvack-Kvack (ideas only),
  UnitedForces, Spreadpoint (GPL-3.0); Gen4 and Speedball_demo (ideas only; code read in full);
  DynaTile (ideas only) and Tilemap (GPL-3.0).
- ped7g/ZXSpectrumNextMisc (MIT / Unlicense): snippets.
- zxnext-copper-samples (github.com/shadowphiar/zxnext-copper-samples; CC0; z88dk C).
- NextMasterSystem (github.com/StalePixels/NextMasterSystem; ideas only; src/runtime/fw*.asm,
  tools/sitescan.py and docs/*.md read 2026-10-20).
