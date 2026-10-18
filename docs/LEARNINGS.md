# Learnings (each one cost a debugging cycle - apply them by default)

Two parts: PART 1 = MACHINE / HARDWARE (Z80, Spectrum 48K/128K, Spectrum Next).
PART 2 = GAMES / SOFTWARE (game engines, our toolkit, host tools, method).
General lessons only: facts about one game live in games/<game>.md, hardware results in STATUS.md.
Each line is settled unless marked otherwise.
Filled by the "Capture" step in CLAUDE.md (End of every task): every fact a session had to bring
in from outside the docs, every unexplained rule, every hardware-only failure ends up here or in
BRIEFING - with its reason.

# PART 1 - MACHINE / HARDWARE

## 1.1 Z80 CPU
- LD A,I: on NMOS Z80s P/V reads 0 if an interrupt is accepted during it.
  Read twice (`ld a,i / jp pe,ok / ld a,i`). SkoolKit models this.
- A hook inside an ISR must keep the EXX/EX AF,AF' parity: the handler restores by set.
- Block I/O flags differ on the Next (documented): after INI/IND/INIR/INDR/OUTI/OUTD/OTIR/OTDR
  only ZF (B reached 0) is reliable. Sources disagree on the rest - guide r3: SF/HF/PV undefined,
  NF = 1, CF unchanged; wiki Extended_Z80_instruction_set: C, S, H, P/V destroyed (errata 2022:
  carry IS modified); Ped7g's opcode table: every flag but Z unknown. A real Z80 - and SkoolKit,
  Fuse, the recordings - sets CF/HF from the data + L, NF = data bit 7, PV = parity. So the
  differential verify cannot prove any flag but Z after one of these. Rule: a hook must
  overwrite F (or POP AF) after a block I/O instruction before any branch on S/H/PV/N/C, and
  before returning to game code. Checked 2026-10-19: every hook complies (Trueno's `ensure`
  returns with OTIR flags, its only caller does OR A first). A GAME that tests those flags runs
  differently on the Next than in its Fuse recording - invisible to the toolkit.
- R changes with every M1 (prefixed opcodes +2, an accepted interrupt +1, bit 7 kept), so hook
  code always changes R. A game that reads R (LD A,R) for randomness diverges from the recording
  after the first hook: `isr` flags LD A,R; the engine simulators advance R for NEXTREG.
- ED 7E (undocumented IM 2) sets IM 2 only from core 3.01.08 on (core changelog). A game using it
  (copy protection does) misbehaves on older cores; check for ED 7E when a hardware report from
  an older core differs from the emulator. OUT (C),0 (ED 71) outputs 0 on the Next (NMOS
  behaviour; CMOS Z80s output $FF).
- On a stock Z80 an undefined ED-prefixed opcode is a 2-byte NOP; on the Next 29 of them are Z80N
  instructions (ED 23, 24, 27, 28-2C, 30-36, 8A, 90-95, 98, A4, A5, AC, B4, B7, BC; full list in
  NEXT_REGISTERS). A game that EXECUTES one (protection padding, a sloppy assembler, data run as
  code) changes behaviour on the Next only, and Fuse plus our simulator (which runs them as NOPs,
  NEXT_REGISTERS "SIMULATOR TRAP") never show it. Cheap check when a hardware report differs from
  the emulator: scan the RZX's executed addresses for those opcodes (`rzxplay.py --map` + the
  bytes; BRIEFING 0). Undocumented Z80 opcodes in general: clrhome.org/table (red cells).

## 1.2 Spectrum 48K/128K memory and paging
- 128K: an UNLOCKED 7FFD/1FFD write remaps the top 16K (C000-FFFF) at once. Code running there
  (e.g. a start-up tail) disappears from under the PC -> a 128K tail must end below 0xC000.
- 48K timing (NextReg $03) does NOT stop 7FFD/1FFD decoding (VHDL 3.01.09; the old belief was wrong and
  harmless). The lock that protects 48K games is 7FFD bit 5, written by the tail itself.

## 1.3 Spectrum Next: MMU, legacy paging, alt ROM, NextRegs
- `$8C alt ROM verified on hardware 2026-09-27: write-mode copy, read-only, 7FFD b4 switch, MMU $FF, IM1, font - all PASS; $8C=00 at NEX launch.`
  -> the alt ROM is the preferred patch location (hooks in 0x386E-0x3CFF, rest = exact ROM copy;
  survives 7FFD writes; no RAM page, no DI/paging per hook).
- Selecting ROM3 = 1FFD bit 2 + 7FFD bit 4 = alt image 1; LDIR 0000->0000 in write mode copies it.
- 0x386E-0x3CFF is all $FF in the 48K ROM (hook range). Register block goes after the hooks, not
  at 0x3FE0 (font).
- The alt ROM image is copied from the SYSTEM ROM3 (NextZXOS), not from Sinclair's 48K ROM, and
  NextZXOS has data at 0x3B00-0x3CFF. A patch that relies on 48K ROM bytes there must write them
  into the alt ROM itself (El Capitan Trueno: a 'map of 0xFF bytes' at 0x3B00 let the plotter draw
  into the ULA until the build copied 0xFF over 0x3B00-0x3CFF). nextboot.check uses rom48() for
  ROM3, so it cannot see this (BRIEFING C2).
- A legacy 1FFD/7FFD write from the stub remaps slots 6/7, where the stub runs: page the stub into
  slot 4 as an alias and run the paging + copy there (no stack), restore 6/7, jump back.
- UNLOCKED legacy paging writes (7FFD/1FFD) remap MMU slots (most recent change wins); map
  slot-1 RAM AFTER the tail's own paging writes. LOCKED (7FFD bit 5 = 1) writes to 7FFD/1FFD/DFFD
  are ignored with no MMU remap (VHDL 3.01.09), so a RAM slot-1 page survives them; NextReg $08
  bit 7 can only UNLOCK (write 1), never lock. Hardware confirmation pending (Dizzy 6 build).
- Pages mapped into slot 0 while interrupts are on = crash risk (IM1 vector at 0x38). DI around
  hook paging; hook pages must be read-only (TID bug: hook wrote into its own paged-in page).
- Code running in slot 0 cannot unmap slot 0: map/unmap from alt ROM stubs.
- The ULA reads bank 5 directly: remapping MMU slot 2/3 changes the CPU view only, so canvas pages
  mapped over the screen address range are invisible (used by the Rainbow Islands hooks).
- NextReg $7F (user register) is a safe flag store: write with NEXTREG, read via ports 243B/253B.
- NextReg $07 = 3 (28 MHz) inside a hook and 0 on exit works in the Rainbow build (runs on HW).
- Hooks that keep no state need no RAM page at all: code in the alt ROM, scratch on the game's
  own stack, output only through NEXTREG. Then interrupts may stay ON (IM2 handler in RAM; an
  interrupt between two NEXTREGs is harmless) - Chuckie Egg (hardware to confirm).
- A RAM page for hook state can stay mapped with interrupts ON if it sits in a slot the game's ISR
  never touches: an unlocked 7FFD write in the ISR resets only slots 0/1 and 6/7, so 2-5 survive.
  Prove it per game (full-RZX scan of the ISR's reads/writes/fetches per 8K slot) and map only
  while the hook runs (Midnight Resistance: page 26 at slot 5, ISR uses slots 0/3/7 only; runs on
  hardware 2026-10-13 with interrupts on through every hook).
- A game may READ the ROM as a machine check: Smash TV's entry does `LD A,(14446): CP 255` (0x386E
  is 0xFF only in the 48K ROM) and takes another path otherwise - hook code at 0x386E (the TID /
  Wally default) would have changed the game. List the ROM bytes a game reads as data after its
  entry (scan the RZX: reads below 0x4000 with PC >= 0x4000, LDIR copies aside) before placing
  hooks; keep every byte it reads as ROM (Smash TV: hooks at 0x2100-, 0x386E and the font kept).
- A 128K BASIC loader snapshot cannot run on the Next: 128K BASIC pages ROM 0 (the 128K editor)
  on every statement (Commando: plain = corruption, altrom = crash at the first key; alt image 0 is
  unfilled). Run the loader in SkoolKit (real 128K ROMs) to the game's USR entry, build from there,
  and redo any prompt the loader asks (Commando front end: PAUSE 0 + Y/N + POKE). Check the game
  itself never selects ROM 0 (7FFD bit 4) in the boot simulation and the RZX.
- Next ports that decode the LOW byte only (guide r3 port table): 0x0B (Zilog DMA), 0x1F (Kempston),
  0x37, 0x57 (sprite attributes), 0x5B (sprite patterns), 0x6B (zxnDMA), 0xDF (SpecDrum), 0xFF
  (Timex). An original game's OUT to ANY address ending in one of these reaches Next hardware (a
  stray OUT to xx57 moves sprites, xx0B/xx6B programs the DMA). The ULA answers any even port.
  When a hardware run shows sprite or memory corruption the emulator does not, list the game's
  OUT targets first. NextRegs $82-$85 can switch internal port decoding off (core spec) - not used.
- Memory size: an unexpanded Next has 1024K = 8K pages 0-95 (16K banks 0-47); 2048K = pages 0-223.
  Keep every page a build uses below 96 (Rainbow: highest 63). Bank 7 (pages 14/15) is the ULA
  shadow screen and NextZXOS workspace; the default Layer 2 sits at 16K banks 8-10 (NextZXOS moves
  it to 9-11, shadow 11-13) - only relevant when a build relies on those defaults (none do).

## 1.4 Spectrum Next: sprites and palette
- 4-bit anchor sprite, attr4: 0x80 = pattern-slot bytes 0-127, 0xC0 = bytes 128-255 (the guide's
  relative-sprite table reads the other way; matches sprites.py). Rainbow build runs on HW.
- Port 0x303B write = pattern slot (bits 5-0, bit 7 = +128 bytes); 256-byte uploads to 0x5B
  auto-advance to the next slot. A 4-bit pattern (128 bytes) whose rows 8-15 are always empty:
  zero pattern RAM once at setup, then per sprite select slot|(+128) and write only 64 bytes
  (Rainbow, 2026-09-29; hardware to confirm).
- NextReg $35-$39 set one attribute of the sprite selected by $34 (no increment); $38=0 hides.
- NextReg $4B defaults to E3: set 0 for 4-bit transparency (low nibble is used).
- NextReg $43=0x20 = edit sprite palette 0 with auto-increment; $40 index, $41 RRRGGGBB.
- NextReg $19 clip: reset the index with $1C bit 1, then write X1,X2,Y1,Y2; ULA-relative when
  sprites are not over the border.
- Per-scanline sprite limit: at least 100 unscaled 16x16 sprites per line are guaranteed (fewer when
  magnified); overflow sets port 0x303B read bit 1 (specnext.com/sprites, ports.txt). We use <= ~12
  per line: no risk. Layer order is global (NextReg $15 bits 4:2, SLU default): sprites cannot sit
  behind some ULA objects and in front of others (Wally limit stands).
- Sprite-to-sprite order: NextReg $15 bit 6 = 0 (reset) draws the HIGHER sprite number on top;
  1 flips it (guide r3 p.89; documented, Rainbow items rely on it - hardware to confirm). To put
  one class behind another, give it the lower numbers (Rainbow: items 0..NI-1, figures after).
- A dedicated 4-bit palette offset can hold the 15 Spectrum inks (index 1 black, 2-8 normal,
  9-15 bright; Next default ULA levels 0x02/A0/A2/14/16/B4/B6, bright 03/E0/E3/1C/1F/FC/FF): the
  ink becomes part of the PATTERN, one palette offset serves every ink (Rainbow offset 15).
- Tearing: change sprite attributes only while the beam is outside the sprites' area. Active
  video line = NextReg $1E (bit 0 = bit 8) / $1F, read via OUT 0x243B (select) + IN 0x253B; line
  0 = first ULA pixel row, play area rows 16-175 in Rainbow; the ULA interrupt is near line 248.
  Hook work that delays a commit into the visible area tears even if the original never did.
- Tilemap (layer 3) for cell-aligned objects: bank 7 via $6E/$6F bit 7 (first 8K only = Next page
  14; needs a recent core); 2-byte entries give a palette offset per tile: put a variable colour in
  the offset (pixel value fixed in the tile) so colour changes cost no tile rebuild. Draws under the
  sprites, over the ULA (attribute bit 0 = 0). Build the map in normal RAM and copy it at the
  raster-synced commit (no half-built map on screen). Use it when objects are cell-aligned and too
  many for the sprite budget (Rainbow: up to 114 object cells next to 84 figure sprites).
- Hardware-only timing problems (the simulation has no raster): Fuse cannot record a .nex. Build a
  DIAGNOSTIC variant that shows the suspect events as border colours (OUT 0xFE, EAR/MIC 0) and have
  the tester film the TV. Overrun detection: clear NextReg $C8 bit 0 at the frame start, read it at
  the frame end (set = an interrupt came during the frame). Clearing = WRITING 1 to the bit
  (`nextreg 0xC8,1`); writing 0 does nothing, and in hardware IM2 mode with interrupts on writes
  do not clear at all (guide r3 Interrupts). Hooks entered from a ROM stub inside the
  game's handler must not use the game's stack: jump to the hook page's code and jump back.
- Never put hook CODE at 0x3D00-0x3DFF in an alt ROM / slot-1 page: Commando 541e34e2 crashed at
  its first figure on hardware and in CSpect with code there, and ran once the code moved out
  (tables stayed there). Probable cause: the DivMMC (TR-DOS) automap on an instruction fetch at
  0x3Dxx, despite the stub clearing NextReg $06 bit 4 - not confirmed (BRIEFING A1, C2 #14).
  Invisible to the simulator; `auto` checks it statically and per instruction (Commando).
- Flicker: never hide a figure's sprites at plot entry and show them at exit (hidden for the
  whole call, often across the beam). Keep them visible, build the new image in OTHER pattern
  memory, then rewrite the attributes in one go (Commando).
- Pattern RAM as a content cache (when the working set fits; else Next RAM, 2.5): a figure shows
  far fewer distinct frames than plots (Commando: ~110 frames in 4,300 plots). Key each pattern slot by (graphics page, frame offset, lines);
  reuse = attributes only, no build, no upload. Evict only slots no visible sprite references
  (round robin); never share an image that was masked (depth). Negative control: a lookup that
  ignores one key field must fail the pixel check.

## 1.5 Spectrum Next: faster sprite / tilemap I/O, DMA, copper, raster (DOCUMENTED, none used yet)
Researched 2026-10-19 (guide r3 chapters Sprites / DMA / Copper / Interrupts, core 3.01.09
nextreg.txt + ports.txt + changelog, KevB's copper timing notes in github.com/varmfskii/zxnext_code
zx_next_notes/copper; github.com/stevemonks/ZXSpectrumNextMachineCodeGuides;
github.com/breakintoprogram/lib-spectrum-next lib/dma.z80; full guide r3 review: GUIDE_R3_REVIEW.md). Nothing here is simulated or hardware-tested: the first engine that uses one
implements it in the simulator (NEXT_REGISTERS "SIMULATOR TRAP") and records the hardware result.
Register / port detail: NEXT_REGISTERS.md "Not used yet". Cost estimates are 3.5 MHz T-states.
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
    (BRIEFING C2 #27). Sites must be RAM (alt-ROM sites cannot be switched back).
  * Layer 2 drawn by the CPU through port 0x123B instead of MMU paging: %11001011 maps all 48K of
    the SHADOW Layer 2 ($13) for read+write over 0x0000-0xBFFF (the stack included: DI, no
    calls), so a pixel is LD (HL),c with H = y, L = x; %00000010 unmaps (display stays on).
  * Double buffering = draw into $13 via 0x123B bit 3, flip = swap $12 / $13 (two NEXTREGs).
  * The Layer 2 scroll offset ($16/$17) moves the game's window origin to Layer 2 (0,0) and the
    clip ($18) trims it, so game coordinates need no adds per pixel.
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
    Commando flicker rule in 1.4 and the pattern cache).
  * Per-frame copper rebuild: patch the list in RAM, stop the copper ($62/$61 = 0), DMA the list to
    port 0x253B with $60 selected, restart in mode 11 - all done after a $1E/$1F wait for line
    192, so the list is never half-written while the beam uses it. A per-line WAIT + MOVE
    $16 pair gives a per-scanline Layer 2 X offset (raster wobble).
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
- zxnDMA (port 0x6B since core 3.1.2; 0x0B = Zilog-compatible DMA): memory -> memory, memory ->
  fixed port (0x5B patterns, 0x57 attributes, 0x253B with a NextReg selected on 0x243B). With
  port cycle length 2 a byte costs ~4 cycles vs LDIR 21 / OTIR 21 T - but only with the timing
  byte sent for BOTH ports (WR1/WR2 bit 6 + byte %00000010); without it the DMA uses standard Z80
  cycle timing. Program upload (~15-25 bytes by OTIR) costs ~400 T, so it pays from ~30 bytes;
  registers persist between transfers, so a repeat with a new address needs only WR0 (+ WR4) +
  $CF load + $87 enable. Continuous mode (WR4 bits 6:5 = 01) holds the bus to the end; never use
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
  count from ULA pixel row 0 UNLESS NextReg $64 (core 3.1.5+) is non-zero: it offsets all three
  (changelog 3.01.05). Frame length differs by timing: 48K 312 lines, 128K 311, HDMI 312 (60 Hz:
  262/261); display rows 0-191, then border + blanking. A raster wait that assumes 312 lines or
  offset 0 is a hardware-only fault (BRIEFING C2 #26).
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
  the limit is memory (bank 7 = 8K for map + definitions). Stencil mode ($68 bit 0): pixel = ULA AND
  tilemap colour, transparent if either is. Tilemap transparency $4C is compared before the
  palette offset (soft reset $0F; our setups write 0).
- Palette control $43 is TWO things at once: bits 6:4 pick the palette to EDIT, bits 3:1 the ACTIVE
  second/first palette for sprites / Layer 2 / ULA and bit 0 ULANext; bit 7 = 1 turns
  auto-increment OFF. Every $43 write therefore also re-selects the displayed palettes (fine while
  everything uses first palettes, as all our builds do). Each layer has two palettes: flipping
  bits 3:1 recolours a whole layer in one write (cheap colour animation, e.g. pulsing items).
- Layer 2 per-colour priority (guide r3 Palette/Layer 2): the second $44 write for a LAYER 2
  palette entry has bit 7 = priority - pixels in that colour draw above ALL layers, sprites
  included, whatever $15 says. Candidate for depth: Layer 2 foreground pieces in front of a
  hardware-sprite player (Dizzy 1 draws figures on Layer 2; the "sprites cannot sit behind some
  objects" limit in 1.4 is about the ULA). Needs the colour twice (one entry with, one without).
- ULA palette: classic ULA uses indices 0-7 ink, 8-15 bright ink, 16-23 paper, 24-31 bright paper
  (border from paper). Paper and ink entries are separate, so ONE paper colour can be set equal to
  the global transparency $14 (compared with the colour, not an index) to see the layer behind
  wherever that paper shows, without touching inks. Candidate for Rainbow layer B.
- Line interrupt: do NOT enable it ($22 bit 1 / $C4 bit 1) under a game in pulse mode: it raises the
  same /INT, so the GAME's ISR runs a second time per frame (frame counters, music, input). The
  ULA interrupt can also be disabled there ($22 bit 2) - never under a game. For hook timing use
  the copper or a $1E/$1F poll.

# PART 2 - GAMES / SOFTWARE

## 2.1 Game-engine lessons (all engines)
- A hook never CALLs on the game's stack, not even one call deep: the return address it leaves
  below SP is dead stack the original never wrote, and the memory compare catches it (midres shop
  exit 0xB8A5, 2026-10-13). Switch to the hook stack first, or inline (a MACRO).
- A game may run its frame routine (plots + screen copy) from more than one loop: Midnight
  Resistance's shop has its own loop and no commit, so its figures stayed on the ULA (or, while
  the loop still counted as live, went into the scratch and were not shown at all). Find every caller of the frame routine / screen copy and give each loop a
  commit and hide-on-exit (midres 0xB893 / 0xB89B / 0xB8A5).
- Hide the sprites on EVERY way out of the game loop, not only the one the RZX shows: list the
  loop's exits (JP / RET / jumps to another loop) from the code. Midnight Resistance hid them on
  game over (0x8993) only; the RZX ends at game over, so the end-of-level exit (0x8988 JP Z,0xB7E0
  -> shop -> level 2) was never run, and on hardware the player's last sprite stayed on screen
  through the shop (Dean, 2026-10-13). A path the RZX does not reach needs a unit test from a
  collected state (midres: "level exit" cases) - and say so in the game file's Open list.
- Graphics under the hook page: run that plot into a scratch in ANOTHER slot the ISR never
  touches, with the game's page back where the graphics are (midres: page 27 at slot 2 =
  0x4000-0x5FFF, loop exits map it back). A per-plot copy of the graphics into the hook page also
  works but runs out of room (midres keys first did that; shots + explosions need up to 880 bytes
  a frame). Slot 4 / slot 2 may be remapped by a hook only because the ISR never touches them
  (isr scan) and no hook code or stack lives there.
- Raising what a hook handles raises the table sizes it reaches: test every table at its budget,
  not at the RZX's peak. Midnight Resistance's sprite table index N * 5 was 8-bit; the RZX peaked at
  38 sprites until shots / explosions became sprites, then 57 and the 52nd wrapped onto the first.
  A unit commit with the table full (64) fails on the old code (negative control) and passes now.
- The RZX shows a fraction of the figures (Midnight Resistance level 1: 19 of 28 plotter callers;
  Dean saw more sprites on later levels at once). List every caller of the plotters statically
  (scan the code for CALL / JP to each plotter entry) and convert by default, unknown callers in
  their cell colours, instead of a whitelist of the callers the RZX showed; derive unit states for
  plotters the RZX never ran from recorded ones with the same stack shape.
- Never hook timing-critical code: title-screen ISRs playing beeper music
  (TID 63328) broke the music when hooked.
- Games self-modify: check patch sites for writes during play (TID title ISR
  writes 63340). Dizzy 4's object plotter rewrites its own operation byte
  (NOP / XOR (HL)) and even a JP into a mirror path - model the op in force.
- Screen-reading logic is the main source of behaviour change: TID bubbles read
  Dizzy's pixels; Dizzy 1 falling objects land on him (472 of 736 tests). Only
  add a virtual read where the data shows a dependency: in Dizzy 3/4 it would
  be WRONG (boxes overwrite the player, so "screen XOR undo" no longer holds).
- XOR engines: model visibility as parity. Dizzy 1 had 7 double draws that cancel.
- Plotter return registers may differ when the player is not on screen (Dizzy 1
  A after erase). Check whether callers use them before "fixing".
- Overwriters (boxes, wipes, nibble text) can make the original leave ghost
  pixels; the patched game won't. Diffs confined to the undo buffer are fine if
  nothing else reads it (check references).
- Collision often uses attribute BRIGHT: leave the background/attributes alone.
- Loader-stage snapshots (BASIC PAUSE before USR, code relocated by LDIR): identify finds an
  inert source copy. Require the ISR's dispatch to the engine; start from the post-relocation
  state (loader.prerun), stopping BEFORE hardware detection (Kempston check) so it runs live.
- An engine can plot more than one figure through the player plotter (Dizzy 6: mirrored copy via
  a second call site and a switched undo-buffer pointer). Identify every call site of the plotter
  and eraser and the undo pointer's writers before hooking the routine entry.
- Measure "once per frame": Rainbow's sprite walker ran up to 14x per render (once per band).
- Loop control can live in AF' (Rainbow plotters: EX AF,AF' / JP NC per row pair). Before
  re-running game code, restore AF' (and every register) to the dispatch value.
- Re-run a plotter at its REAL address with a RAM page mapped over the screen; re-basing DE to a
  private canvas broke plotters that save D, run leftwards or are 6 bytes wide.
- A 128K snapshot may be a 48K game in 128 mode: count 7FFD writes, AY ports, ROM reads and
  non-empty banks 1/3/4/6 first. Wally: none -> build from the 128K file as-is (Rainbow path).
- When a plotter reads only its gfx and a back buffer the game never reads, REPLACE it: convert the
  gfx straight to patterns and emulate its end state (alt regs, flags via the same OR/ADD, stack
  PUSH, self-modified operands, (43067)). Simpler than Rainbow's two canvas runs; verified exactly.
- Put the sprite commit AFTER the pixel copy (Wally 47637), not at blit start: the LDI copy takes
  ~1 frame.
- Measure the write extent of EVERY dispatch target statically (run each original plotter from a
  mid-screen address, record written columns/rows), not only the ones the recordings reach: bosses
  use entries normal play never does. Rainbow's 4-wide leftward entries write E-3 (window started
  at E-2): the spider lost a column on hardware although both RZX were IDENTICAL.
- A hardware video can replace a missing RZX for a geometric bug: "left column missing only when
  facing left" pointed straight at the leftward (mirrored) plotter entries.
- Background objects that live in a back buffer (Rainbow collectables) become sprites without
  decoding the level map: keep a SHADOW MAP of the buffer cells from hooks at every routine that
  writes a cell (all of them: a full-tile writer the prototype missed caused 16 stale records),
  then derive what is on screen from the scroll position at render start.
- Removing an object from a screen the game REDRAWS every render: fix it right after the game draws
  that part (Rainbow: per band, at the walker end), not once at render end - otherwise the object
  is on screen between the blit and the fix, i.e. it flickers.
- An object's mask can INCLUDE its graphic bits (Rainbow items: (cell AND mask) OR gfx with
  gfx in the mask): "screen AND mask" then leaves the object's ink pixels; clear with
  AND (mask AND NOT gfx).
- Look at the GRAPHICS before deciding what a code range is: Rainbow's object codes 1-14 were
  rainbow pieces, not collectables; two verified builds turned the rainbows into sprites and left
  the real collectables (codes 15+) alone. Differential tests prove the logic, not the naming:
  render a contact sheet of every code the recordings use before designing around it.
- Hook cost: scanning all cells of a row per render costs more than the work itself - keep an
  occupancy bitmask (per row) in the cell hooks and visit set bits only; cache derived data per cell
  (last result + key check) before hashing; summarise per-cell classes in the hooks, not per render.
- The return address in IY (routines ending JP (IY)) tells which caller ran a shared routine
  (Rainbow: cell composition IY 60699 / 60720 vs spawning an object into a drawn cell).
- Incremental-draw engines (no full redraw: erase = tile redraw at the old position, draw = OR /
  overwrite at the new one; Chuckie Egg) need no staging: ONE sprite per object, set at its plot,
  hidden at its erase and at every screen clear. Keep the plotters running and remove only their
  screen pixel and attribute writes (NOPs), so all game state stays the original's.
- Tell figures apart without hook state: the caller's RETURN ADDRESS on the stack at the plotter
  entry (Chuckie Egg 39500: 41238/41361 = duck, else player), or a register the routine pushed
  (hen plotter: caller DE = hen table entry -> sprite number).
- A plotter that composes figure + background in a buffer and then overwrites the screen: swap the
  compose (LD A,(DE) / OR (HL) -> LD A,(HL) / NOP) so the blit writes background only; prove the
  buffer is write-first and read only by that plotter (Chuckie 29344-29391).
- Hook state must not be baked into RAM the LOADER still owns: Commando's .z80 is the BASIC
  loader (sysvars + program at 0x5C00) and the build overwrote it with the hook tables. Init the
  state from a hook at the game entry (the USR target), unit-tested from the loader's real RAM.
- Entry tables keyed by an object's position leak when the game retires the object without a
  last plot (Commando soldiers leaving at the bottom: invisible entries filled the table). Keep no
  entry for an invisible frame; in verify, max entries = table size is a red flag - count the
  plots that fell back because the table was full.
- A differential plotter's erase (clear old frame, OR new) also cuts the scenery under a figure
  that is now a sprite (its old bits were never on the ULA); games that redraw scenery only on
  scroll frames then show bitten scenery. Save the bytes under the old frame at entry and OR them
  back at exit: a converted plot leaves the ULA unchanged (Commando svsave/svrest).
- Depth from a game's collision boxes: use the point the game's own walk test checks (log the
  test routine's arguments in the RZX: Commando y + 6), not the figure's feet - with the feet a
  figure stopped above a small box came out in front.
- Hooks that run with interrupts on must leave everything the game's ISR reads intact at EVERY
  instruction: IX, IY, I, IFF, and SP on a stack with room. Commando's IM 2 handler tests IY+7
  flags; a hook that borrowed IY made the handler draw the menu's spinning logo in-game and leave
  stray dots. Check it statically (disassemble the hook blocks: no IX/IY writes) and per
  instruction in the simulator, with a negative control (LD IY in a hook).
- Back-buffer composer with many plot routines that share one address helper: replace the TARGET
  of their CALL to it (same return address, same stack bytes) and return the address of a scratch
  copy of the buffer, so the game's own loops run unchanged into the copy; copy the buffer bytes
  under the figure into the scratch first and the loop ends with the original's registers. Patch
  the loop exits to map the address back with a flag-free table lookup (LD D,(HL)), and redo the
  last ADD HL on the real address where the loop ends with one: H, C and flag bits 3/5 depend on
  the address (Midnight Resistance: 17 flag mismatches until then).
- Back-buffer composer whose buffer fills one 8K MMU slot: run the game's OWN plotter with that slot
  mapped to a scratch page (CALL a trampoline = the displaced first instruction + JP into the body):
  registers, flags and self-modified operands come out as the original's with no address mapping
  at all (Smash TV: slot 7 = page 26). Needs: (1) the scratch holds what the original buffer would
  hold - run the background restore twice (real, then scratch) and send converted plots to the
  scratch only; (2) game code that LIVES in the remapped slot is copied into the scratch page at
  the same address (Smash TV's restore 0xE872-0xE8FB: without it the scratch run executed zeros),
  and its self-modified operands are written back on the game's page; (3) the trampoline's CALL
  uses two bytes under the game's SP - put them back; (4) interrupts off (the IM 2 handler may live
  in that slot).
- A game without frame sync (interrupts off, no HALT) runs at the speed of its CPU time: hook cost
  IS game speed. Keep the game's own bodies at 3.5 MHz (same cost and contention as the original)
  and only the hook work at 28 MHz; report T per game frame original vs patched (Smash TV ~+6%).
- Hook code that returns into the game's own loop must not write below the game's SP (no CALL, no
  PUSH on the game stack): the original's dead-stack bytes (pushed BC etc.) differ otherwise. Use
  a macro, or the hook stack in the hook's page.
- Pattern slots with a cache: mark each slot "on show" (last commit) and "used by this commit"
  (two bits, shifted at each commit) instead of commit stamps; stamps wrap, and with <= 64 sprites
  per commit and on show a free slot always exists. Key cells-coloured images by the attributes
  under them (and Y & 7), fixed-colour ones by graphic + colour; mirror by the sprite bit, not in
  the key.
- Solid sprites: a body fill from the frame itself (a pixel inside the ink both on its line and
  in its column) reads as a filled figure; objects that hide a figure need their SOLID shape (the
  game's draw mask with holes filled), not their ink, or the figure shows through paper-coloured
  parts.
- Back-buffer games (El Capitan Trueno): leave the plotter untouched and point its 'behind the
  foreground' map at bytes that say every cell is foreground: it saves the scenery as usual but
  draws no figure pixel and paints no attribute, so game memory stays as the original's and the
  verification is simple. Clean attributes at the copy (the scenery copy, not the work buffer),
  sprites with the game's mask. Depth: the game's own foreground cells copied into Layer 2 with
  the palette priority bit (in front of the sprites) - an alternative to per-sprite masking.
- A figure's exact ink and mask: call the game's own plotter in the simulator on a buffer of 0x00
  (ink) and of 0xFF (cleared pixels = mask). No drawing code to read, no guessed body.
- Capture each shape from ONE consistent state: a game that mirrors graphics in place flips the
  trailing mask bytes too; a catalogue graphic written over a mirrored state got a mirrored mask
  (Trueno frame 98: figure pixels left uncovered = white flashes).
- Graphics catalogue of a game that mirrors in place: hash every graphic at each frame end; the
  mirroring leaves transient half-mirrored states (1-6 frames each, never plotted). Group each
  graphic with its exact bit mirror and keep the real ones (Trueno: 167 real shapes).
- A game that already toggles a hit bit flashes by itself: do not add your own blinking (in phase,
  the two cancel out; Trueno).
- Redrawn figures (a human's cleaner drawing) no longer cover the game's whole mask: either keep the
  sprite's opaque area >= the mask, or stop the figure reaching the ULA first (Trueno: no-draw map
  patch / pre-copy restore), or the mask shows round the new drawing.
- A sprite shape's patterns never cross an 8K page (64 4-bit patterns per page): the upload and the
  pattern index assume one page per shape (Trueno patterns.py).
- Screen shake: offset Layer 2 (NextReg $17) and the sprites for the shaken copy only, from a hook
  on the game's shake (Trueno 0x887D: NextReg $7F bit 6 -> the commit moves both 8 lines).
- The scenery BEHIND an object (for fix cells or a wall behind bushes): build the screen in the
  simulator twice, with and without the frames that hide it - the background is then the game's
  own, not a guess (Trueno bush_walls.py, fix_cells.py).
- A human's edits on a sheet: keep the sheet exactly as handed out, diff the returned one against
  it, and give each edited cell to every cell drawn from the same game tile (and its mirror). A
  later round on the same tile overwrites cells the human drew unlike their tile: say so first
  (Trueno bush_round.py).
- Translating a game's texts: find its letter codes and item format; a list read only from its
  head (one LD HL, no other reference into it) can be rebuilt whole, single strings only in place
  and never longer; check every old byte against the snapshot. A snapshot with the title already
  drawn: wipe the old words and print the new ones with the game's own print routines in the
  simulator (Trueno texts_en.py).
- Menus and windows the game draws in the ULA over the play area are covered by Layer 2 and the
  sprites: find them all (PLAYBOOK 0) and wrap each one (PLAYBOOK 4).
- A hook on the plotter's entry does not see code that enters it further in: list every CALL/JP
  to the plotter's addresses (Trueno: 0x82DF hooked, the dragon's bar called 0x82E4).
- Every path that shows a screen without the normal build (a clear mode, an end screen) must
  clear or hide Layer 2 and the sprites; a deferred Layer 2 rebuild 'until the mode ends' left the
  previous screen's foreground on the dragon's screen.

- Pure-XOR engines (no masks, no undo buffers): move every converted screen write into a 1-bit
  SHADOW screen instead of the ULA. ULA XOR shadow == the original screen at every moment (XOR is
  linear), so every caller, partial draw, overlap and XOR-parity cancel is exact without modelling
  figures; a figure layer (Layer 2) shows the shadow. Writers that are not XOR keep it exact by
  computing the original's new byte from the virtual old one (ULA ^ shadow) and putting the CHANGE
  into the shadow (converted) or the ULA (kept); overwriters and in-place effects fold the shadow
  back into the ULA first; logic reads get ULA ^ shadow (Dizzy 1, 2026-10-14). Hardware sprites
  would have needed ~80 at once and patterns built on the fly for clipped draws.
- Solid figures on an XOR engine: the frame's enclosed paper (flood fill from outside, 4-connected)
  per graphics byte, XORed into a second, display-only fill shadow with the ink, so the fill keeps
  the figure's XOR parity; the user can paint any opaque pixel transparent (Dizzy 1, 2026-10-14).
  The per-byte lookup made Dizzy's plot ~3x dearer until unpainted bytes took a fast path (flag in
  the plane entry): keep per-byte hook work proportional to what is painted.
- One XOR figure layer mixes figures exactly as the original did - where two touch, their pixels
  cancel (Dizzy at the grease gun, hardware 2026-10-14). The player needs his own shadow and his
  own display (hardware sprites in front); logic still reads ULA ^ every shadow. A sprite that
  follows XOR parity must not hide at the erase when the draw follows (it does, across an
  interrupt): mark the erase pending and hide only if something else happens first.
- A colour that changes every redraw may be the game's own (Dizzy 1's items cycle their colour
  field): find the writer of the colour before calling it a bug, and ask whether to keep it.
- The game may rewrite instructions INSIDE or NEXT TO a hook site to switch modes (Dizzy 1: 58079
  XOR C / OR C / LD A,C and 58709 XOR (HL) / NOP for the room tiles - the old site at 58707 would
  have had its JP target overwritten). Before choosing a site, list every writer into the routine's
  code bytes (static LD (nn),A / LD (nn),HL scan + the verifier's "game wrote a patch site"); a hook
  that emulates such an instruction reads it at run time and handles every value the game stores.
- No frame sync (no HALT in play, nothing but the ROM reads FRAMES): every T-state a hook adds slows
  the game 1:1 (Dizzy 1's first build: +22K T per 69,888-T frame = a third slower). Check it before
  designing (scan for HALT / FRAMES readers). Fix that keeps memory exact: the plot ENTRY hook
  switches to 28 MHz and swaps the return address for a ROM trampoline that writes the original
  address back into the (now dead) slot, switches back and returns - the game's own plot loop and
  every per-byte hook then run at 28 MHz. Measure it: Speed line (T per frame, patched - original,
  28 MHz parts / 8) from the verifier's pair runs.
- A game's interrupt handler can change the interrupted code's registers (Dizzy 1's title-music
  handler DECs B and C and sets carry): an interrupt inside a hook would corrupt the hook. Check
  which handler is installed at EVERY hook site in the recording (verify asserts it) - the in-game
  one here is the ROM's 0x0038, which keeps every register.

## 2.2 Memory proofs (analysis method)
- Prove free memory with an access scan over the recording, not by zero-check.
  Also require zero content for persistent code (untouched may just mean
  "room not visited"), or explain the non-zero bytes. Commando's hook RAM 0x5E20-0x60FF holds
  non-zero bytes: BASIC workspace below RAMTOP (CLEAR 25087), below the game's own stack; no game
  code references it; untouched in area 1 + start-up - later areas not yet scanned (commando.md).
- The printer buffer is not always free: Dizzy 1 keeps its stack above it,
  Dizzy 4 keeps a bit-reverse table there, Rainbow Islands keeps code there,
  Everyone's a Wally uses it (0x5B00-0x7AFF write-first).
- Default "below SP" tail placement can hit data (Dizzy 1: font at 0xFF9E) or
  code (Dizzy 4: code directly below the stack). Always check the printed tail.
- Dead stack below SP is free at start-up; the tail is dead once the game runs.
- A game reading the ROM font needs a slot-1 page that is a copy of ROM 0x2000-0x3FFF, with
  hooks only where the game never reads (prefer `altrom`: the alt ROM is that copy, read-only).
- An undo buffer (or back buffer) written before read in every RZX is a stronger tail site than
  dead stack and rescues slot1 when dead stack < 54 (Dizzy 6: 48 bytes; Rainbow: back buffer).

## 2.3 Our toolkit (nexclash) and host tools
- z80tonex 128K: leaves 7FFD unlocked; 1FFD=4 when 7FFD bit 4. Since 2026-09-28 it refuses a 128K
  tail ending above 0xBFFF (even with --tail) and never picks one; SP >= 0xC000 -> error asking
  for --tail. 48K output byte-identical to before.
- nextboot.check is 48K-only; rainbow.boot_check is the 128K version (reuses nextboot.boot).
- Frame-level questions over a whole RZX (what changed by the end of each frame): SkoolKit's C
  simulator with a patched RZXTracer.next_frame replays 53,543 frames in 4-8 s; the simrun /
  analysis commands run per-instruction Python hooks, ~100x slower (BRIEFING C2).
- [MAME] MAME 0.289 (specnext driver) runs the .nex (loading, quirks: 2.7). From its Lua console: switch the layers off one by
  one (ports 243B/253B: NextReg $15 bit 0 sprites, $68 bit 7 ULA off, $69 bit 7 Layer 2; while
  paused, emu.step() renders one frame) and snapshot each - the user names the guilty layer at
  once; sprite attributes read from manager.machine.memory.shares[':sprites:attr_ram']. Main RAM
  pages are not readable from Lua (only the CPU's 64K view).
- analyse.py / recorder / machine.py are 48K-only (recorder: Machine has no ay; analyse desyncs at
  frame 49 on 128K).
- A module restored from an older copy can silently drop another engine's hook (identify() lost
  identify5): selftest after every session that touches shared modules.
- The recorder writes one RZX segment per episode; per-segment state must reset (new Simulator).
  Symptom: refusals a few frames after a segment start (stale screen model, stale drawn flag).
- An uploaded snapshot with the right game but a different MD5 is another snapshot of it
  (dizzy2.z80 = TID title): check docs/records (inputs.path) before assuming references are complete.
- TID altrom hook range 0x386E-0x3A69 (+ register block); the builder refuses a range that is not
  all $FF in the 48K ROM.
- SkoolKit `Snapshot.get(...).memory[0:0x4000]` is ZEROS for .z80 files: take ROM bytes from
  `skoolkit.ROM48`. The Dizzy V slot-1 page was built from it -> blank font -> empty dialogue
  boxes on hardware. Verify the page against ROM48 at every ROM byte the game reads.
- SkoolKit's Simulator silently drops writes below 0x4000; on the Next a slot-1 RAM page takes
  them. Check for ROM writes with dizzy6._rw_simulator() (guards removed).
- SkoolKit snap.ram() (no argument) is a 48K view even for 128K; snap.ram(-1) returns all 8 banks
  (0x20000 bytes, bank order 0-7). Test snap.machine or len(snap.ram(-1)).
- 128K Python-sim hooks: in a Simulator subclass set memory.__class__ to a pagingtracer.Memory
  subclass; wrap opcode-table entries for exec hooks; set rzxplay.Simulator, CSimulator=None.
- Boot simulation needs writes below 0x4000 (alt ROM write mode): dizzy6._rw_simulator();
  NEXTREG via after_ED[0x91/0x92], ports via the tracer.
- Hand-assembled hooks: cross-check against sjasmplus (caught a JR out of range).
  sjasmplus: use the bundled, pinned one via `tools/asm2profile.py` (never build or download
  another version; tools/sjasmplus/README.md). `pair` is a reserved word (label error). Local labels inside MACROs are macro-local:
  inline the text instead when the macro jumps to the enclosing routine's label.
- The toolkit's master copy is github.com/bleughb/nexclash; the private github.com/bleughb/specnext
  holds the reference game files (it held everything until the public repo was split off). Before
  the repos (2026-10-11), Project
  files had to be retyped into each sandbox (no /mnt/project): slow, and old same-name uploads
  resurfaced stale facts. The move was checked by extracting every Project read verbatim from the
  session transcript (40/48 files = the handover MD5s; the 8 others = known later edits) and by
  reassembling every .asm against its profile hex. Never retype a file: clone, edit, commit.
- A toolkit zip from Dean can be a side branch, not an old copy: the 2026-09-28 zip held a 128K
  variant of machine.py / analyse.py / recorder.py (+ selftest128.py) that never reached the
  master copy. Ask before mixing.
- SkoolKit get_state(sim) needs a tracer with border / outfe / outfffd / ay (a bare
  Simulator from from_snapshot() has none: AttributeError 'border'); set a dummy one.
- `selftest.py` parses its own flags: before 2026-10-13 an unknown one (even --help) started a
  RELEASE run (every game rebuilt); it now prints the usage and exits.
- `rzxplay.py --map FILE` + `sna2ctl.py -m FILE` + `sna2skool.py -c` give a routine-split
  disassembly of everything an RZX executed in ~1 minute: the fastest way into an unknown engine.
- Colour sheets, outlines (Dizzy 1, 2026-10-14): the user painted a 1-pixel black border round
  every figure inside the figure's box and the read-back IGNORED all 2,471 pixels: the map had a
  colour only for ink / interior bits, the PNG gave no hint. Users think in boxes, the engine in
  bits: say on the sheet's rules what is paintable, and report ignored paint loudly. Fix kept general
  (coloursheet paint_clear: every bit of the graphics bytes, paper as code 0). Also: giving paper a
  colour exposed a latent key bug (Dizzy's 4-px-shifted frames wrapped their right edge onto the
  next row's byte) that was harmless while paper was never drawn - when a pixel class starts to
  matter, re-check every map from pixels to keys for that class (bounds, wraps, mirrors).

## 2.4 Recordings (Fuse / RZX)
- Autosave snapshots: `nexclash.py rzx strip A.rzx -o B.rzx` (keeps the first snapshot; replay
  continues from the simulated state, as rzxplay --flags 4). Unstripped RZX desyncs.
- Autosave was on in both Rainbow recordings, the Wally one (12 snapshots) and the Chuckie Egg one
  (10) despite "off": count snapshots in every RZX.
- Wally: Dean could not switch character in play; all five descriptors were still plotted (other
  rooms/character art), so plotter A covered all five.
- Fuse RZX first snapshot is SZX ("ZXPR" warning harmless) and is a later moment than the .z80
  unless recorded with "Record from snapshot".
- Auto-recorder: rooms are matched by attribute SIMILARITY (<=25% cells differ = same room);
  exact hashing made moving objects into fake rooms (Dizzy V bubbles trapped it).
- Fuse autosave snapshots in an RZX need interrupt-accepted repair: ask for autosave off, or use
  `nexclash.py rzx strip`.
- One recording per game, following RECORDING_CHECKLIST.md, avoids a second round.
- What a recording covers is quickest to see on a contact sheet: rzxplay `--stop N` with an output
  .z80 at 10 points, render the screens side by side (Chuckie Egg: levels 1-2 only, no lifts).
- An RZX carries its own start snapshot and can start later than the .z80 (Commando: .z80 = BASIC
  loader, RZX = in-game SZX). Nothing between them is verified: compare the two start states and
  simulate .z80 -> game entry (keys) checking hook RAM / tail / sites / interrupt mode.

## 2.5 Verification method
- Lockstep RZX replay cannot prove equivalence once cycle counts change (input
  sampling shifts). Use per-routine differential tests from real states.
- Per event: original and patched from the same state on private overlays; compare all registers
  except R/T/MEMPTR and all memory.
- Cover check (any game whose figures still reach the ULA or a buffer): at every screen copy,
  every pixel the figures changed (buffer before the copy vs scenery after the restore) must lie
  under an opaque sprite pixel of the hooks' model, pattern memory and flushes included. It found
  two real bugs in Trueno that whole-recording play missed (check_cover.py: 10,508 renders).
- Invariant checks over the whole RZX are cheap and catch design errors early: never a plot while
  a render waits for its copy, every copy follows a render, interrupts accepted at the hook sites
  (Trueno check_order.py); a memory-neutral patch compared over one whole render cycle (all RAM
  but the screen: check_nodraw.py, check_prerestore.py); mirrored shapes vs the game's own mirrored
  plot (check_mirror.py); who reads screen / buffer bytes, by PC (check_screen_reads.py,
  check_buffer_reads.py). These do not replace the per-call differential test.
- Registers differing at a routine's return (e.g. A, AF' read from the screen) are fine only if
  they are overwritten before any use: step both copies until they converge (fail if read).
- Verify sprite pixels against the screen BEFORE the plot (transparent = unchanged), not the
  model: ink -> after = 1, outline -> after = 0; every screen bit the original changed must be
  covered by a sprite pixel.
- Exact figure pixels without decoding the graphics format: run the ORIGINAL once more on a
  CANVAS overlay - screen pixels read as 0 for an OR plotter, tile graphics read as 0 for a
  plotter that composes background - its writes are then exactly the figure (Chuckie Egg:
  sprite set == canvas set at every event; screen block = background | figure).
- Entry-point proof: interior bytes of patched instructions never executed as instruction starts.
  A 3-byte JP over TWO instructions covers a real instruction start (Smash TV 53868 XOR A /
  53869 LD (nn),A): check that it is only ever executed right after the site's first byte
  (previous PC), not by comparing counts (an RZX segment boundary skews them by one).
- A code path no RZX reaches can be proven by a unit differential test (original vs patched code
  from the same state) plus a negative control that must fail.
- Unit tests must include a negative control (e.g. a broken nibble table) or they prove nothing.
  Restoring a captured hook-page state must copy the RUN-TIME byte ranges only (vars, cache keys,
  sprite table) - Smash TV's first unit run copied the whole state area, which put the correct
  colour table back over the negative control's broken one: 5 of 6 'not detected'. With cache keys
  copied, carry the pattern RAM too, or every cache hit shows an empty sprite.
- Pattern cache key = everything the patterns depend on, compared in FULL (Rainbow: IX, start row,
  AF' carry, the whole graphics stream): a content key cannot go stale when graphics are rewritten
  at the same address. Keep running the plotter once on a hit: the register state it leaves is
  what the game logic needs. Size the cache from a key-reuse analysis first (Rainbow: 32 LRU ->
  63%, 64 -> 83%).
- Direct conversion without reverse-engineering each plotter: DERIVE a layout table by running
  the original plotter with single-bit streams on 00/FF screens (target byte, mirrored, mask vs
  ink), then test the table against the plotter on random streams + a corrupted-table control.
  Keep one original plotter run per piece for the register state (logic stays exact).
- A key that includes the vertical phase (D&7) misses on every scroll step. Put the phase in the
  sprite Y instead (sprites are pixel-positioned) and key only what shapes the pixels.
- Cache size decides where it lives. Pattern RAM (16K = 128 4-bit patterns) is enough when the
  working set is small: Commando's figures show ~110 distinct images, 32 slots of 4 patterns hit
  64 % with zero uploads (1.4). A big working set needs Next RAM: a 256K store (pages 32-63) mapped at MMU1
  while the hook works, patterns OTIR'd to per-render sprite slots. Garbage at boot needs no
  clearing when a hit requires the full key + stream to match. Rainbow: 91% hits.
- Before optimising hooks in a CPU-paced game, find WHERE the frame is paced. Rainbow runs its
  whole frame in the IM2 handler with interrupts off (one frame per 3-4 interrupts, no limiter):
  a 3-instruction limiter at the handler entry + 28 MHz for the frame removes ALL slowdown and
  makes hook cost irrelevant; the main loop keeps 3.5 MHz so its timing is untouched. Quick test
  for "no limiter": the original at 7 MHz runs too fast.
- Never change live sprites piece by piece while the render runs: stage attributes + pattern
  sources during the render and commit them in one burst at render end (sprite by sprite:
  pattern, then attributes). Verify pixels against the STAGED state and the commit against it.
- Sprites are a separate layer: when the game leaves play (death, continue, round end), switch
  them off (NextReg $15) from its state-change path; the next commit switches them on.
- Measure the original pace from the RZX (frames between handler entries; count frame resets of
  the T counter): Rainbow 3 (95%) / 4 (5%).
- Tile-drawn objects (Rainbow fruit/collectables) live in the scrolling background with the
  platforms: making them sprites is a persistence/scroll problem, not a drawing hook (solved
  2026-10-11 with a shadow map, 2.1).
- Colour by graphics page works only for graphics at fixed addresses; a runtime graphics buffer
  (Rainbow 0x9500) holds different objects per level - key those on the copy source.
- Two verification levels (docs/BRIEFING.md C3b): ITERATE (sites, boot, unit tests, `--quick N`
  on one RZX) per change; RELEASE (all RZX in full, one job at a time)
  once per delivered .nex. Logic exact, visuals good enough. Parallel full runs on the 1-CPU
  sandbox cost a whole extra turn (2026-09-29).
- For a Z80N opcode in hooks (Rainbow SWAPNIB): install it in every simulator that runs hooks,
  test it exhaustively, and add a control that runs the hooks with it as SkoolKit's silent NOP -
  that control must fail.
- A negative control can pass silently: the Wally unit test reloaded the whole captured RAM page,
  putting the good NIBTAB back over the broken one. Restore only run-time state (0x0000-0x00FF).
- A negative control can also go n/a silently: after the Rainbow commit moved sprite attributes to
  render end, two figure controls checked the (now unwritten) live attributes and reported "n/a"
  on all 40 states for 9 days. Read "detected" counts, not just "no FAIL"; check against the state
  the hook actually produces (staged).
- A negative control on a state whose figure has no pixels (Chuckie duck blank frame 12) cannot
  detect anything: count it n/a explicitly, never as a failure or a pass.
- Guards turn out-of-range plots (buffer/attr overflow, table full) into unchanged passthrough;
  unit-test every guard edge (converted vs passthrough must match the guard exactly).
- Right-edge figures: the ULA wraps an overflowing byte into the next column/row (INC E / INC HL)
  where a sprite clips. Classify those unit cases as "not a game case" (Rainbow precedent; Chuckie
  player/duck x > 240, hens x = 248) - any real occurrence with pixels fails the RZX pixel check.
- A check added to SHARED verification code for one engine can fail every other engine that
  reuses it: Rainbow's "setup zeroes pattern RAM" (2026-09-29) went into rainbow.boot_check, which
  Wally also calls; Wally uploads full patterns, so its unchanged, hardware-proven build reported
  FAILED for 13 days, unseen because nobody re-ran it. Scope engine invariants to that engine and
  re-run every game after touching shared checks (selftest covers them now).
- A deliberately broken stub must fail the boot check (no 1FFD write, no unlock, hooks not copied).
- Model the NEX launch state from hardware evidence, not the worst case: a "7FFD locked at launch"
  model rejected every hardware-proven build.
- The boot check's expected ROM view must include the register block the stub writes at boot
  (it first showed 17 "ROM differs" bytes at the register block).
- Measure the WHOLE game frame in the verifier when hooks are added to a limiter-paced frame:
  original T (accumulated across the RZX frames the handler spans) + every hook's extra T, at
  28 MHz. Over 20 ms (one interrupt) the frame misses an interrupt and takes 4 instead of 3.
  Rainbow items: a keyed pattern cache (per-slot patterns were rebuilt whenever the list shifted),
  item-list reuse when no cell changed, per-band item ranges, per-row occupancy counts.
- A cached derived list goes stale through writers you did not hook: Rainbow's bonus scene cycles
  item inks through 51914 (a third attribute-buffer writer). The verifier rebuilds the model every
  render and caught it at frame 2696; the reuse path now re-reads the inks.
- Hooks must keep EVERY register at the resume address, even ones the game overwrites next
  (Rainbow 60965: HL; 60839: the carry that DEC A keeps): the verifier compares at the resume PC.
- A model-vs-original-screen check (every predicted item row shows the item on the ORIGINAL screen,
  unless a figure was plotted there) validates the model itself, not just the hook against it.
- A hook that calls a helper must reload every register the helper clobbers before using it
  (Chuckie e_hd first used C after henidx had set BC): found by reading, before the first run.
- A unit sweep must stay inside states the game can produce (Commando: old/new column differ by
  -1/0/+1; the draw loops ignore +4 otherwise) and test the guard on the rest separately. Check
  that a sweep converts something: an all-passthrough sweep proves nothing.
- A counter that can never be non-zero proves nothing: Commando's first 'pixels hidden' metric
  was (original bits missing on the patched screen) & (scenery ink) - empty by construction.
  Make every counted effect also show up in a negative control.
- "Never a PC" for patched bytes holds for instruction INTERIORS only. When a patch covers several
  instructions (DJNZ + RET), the later ones run in the original by falling through - and an
  interrupt may arrive between them, so the check must accept "resumed there after an interrupt
  taken right after the previous instruction" (Midnight Resistance 0x9FB9, once in 4,709 frames).
- A negative control case is informative only if the broken table can change the result: an
  ink/outline swap is invisible where ink and paper are the same colour (black on black cells).
  Count only informative cases.
- Speed: the simulator's T-states ignore the 28 MHz turbo; time hook code by T per game frame
  (pair runs) and divide the turbo part by ~7-8. Midnight Resistance's commit cost dropped from
  837K to 15-60K T per frame with a pattern-slot cache.
- States captured early in an RZX are often a figure's FIRST plot (no sprite yet): force the
  steady state (old image already a sprite) in unit cases that test steady-state behaviour.
- A 'buffer is non-empty' flag that lets later code skip work must be set on EVERY path that
  writes the buffer: Commando's lazily cleared depth mask missed the rectangle-shape path (found
  by the depth unit cases, which the RZX alone had not hit).

- A verification is evidence about exact inputs, not about a game: key it to the hashes of
  everything the build reads (docs/records stamps). Re-proving every game at every release does
  not scale; re-prove what the changed files reach (own files -> that game; shared files ->
  rebuild all dependents + one representative per engine). Rebuilds must not need the
  recording: store the few analysis facts a build uses (`_decisions.json`) and rebuild from
  those in seconds.
- An "OK ... verification" line must say what it proved. selftest printed "dizzy1 verification
  (0 PASSED)" as a pass: the dedicated Dizzy 1 / Treasure Island builders are not verified by
  any run, only their plain tail is. Zero PASSED is not a verification - count it, and let the
  record say which games are not differentially verified (verify.differential false).
- Hand-kept duplicate lists drift (selftest INPUTS / EXPECTED, STATUS, VERIFICATION, verified.json
  all held the same MD5s). Keep one source (the record) and generate the rest.

## 2.6 Process / tokens (this sandbox)
- Background jobs die when the turn ends (or the shell resets) unless started in their OWN session:
  `setsid nohup sh -c 'cd DIR && a; b' > log 2>&1 < /dev/null &`, then poll inside the turn. Plain
  `nohup cmd &` and `( a; b ) &` die silently - the log just stops (Midnight Resistance session:
  a 20-min `selftest --verify` lost twice). Check with `ps -eo pid,sid,args`: the job's SID must
  be its own PID. 1-2 CPUs: `--jobs 2` at most.
- Run a stamping selftest in a separate git worktree (`git worktree add ../nexclash-verify BRANCH`)
  so its record stamps do not collide with edits in the main checkout; commit them from there.
- `cd X; cmd` runs cmd in the OLD directory when X does not exist - use `cd X && cmd` (a selftest
  with --stamp started in the wrong checkout).
- GitHub from a cloud session: the git proxy pushes only to repositories attached to the session
  (attach with push access first; a 403 "not in this session's authorized repository set" says
  so); the gh token may be invalid - use `env -u GH_TOKEN gh api ...`; GraphQL is blocked, so
  `gh pr create` fails: open PRs with `gh api repos/OWNER/REPO/pulls -f title=... -f head=...
  -f base=... -f body=...`. A PR stacked on an unmerged one: base = that PR's branch - and if the
  base PR merges first, retarget the stacked PR to main (`gh api -X PATCH repos/O/R/pulls/N -f
  base=main`): merged into the old branch it never reaches main (the canary, PR #21, had to come
  in again with #23).
- A limit written without its reason gets broken: BRIEFING said alt-ROM hooks end < 0x3D00 next
  to the font, so a game that never reads the font looked exempt - and code at 0x3Dxx crashed it
  (probably the DivMMC automap). Write the WHY with every limit, and mark an inferred why as such.
- `pkill -f` / `pgrep -f` patterns match your own shell when its command line contains them -
  including a directory name like `out5` used elsewhere in the same command (mid-edit: re-check
  files after). Find the PID first (`pgrep -fa`, read the list, in a SEPARATE command), then
  `kill PID`.
- Name scratch scripts uniquely, NEVER after a stdlib module (dis, code, io, json, types, ...):
  Python imports the script's own directory first, so a dis.py shadows the stdlib and breaks
  SkoolKit (happened twice, the second time with this line already here).
- Do all analyses in one simulator pass; poll background jobs.
- Keep per-instruction work in an analysis hook O(1) (a dict SCAN per opcode turned a 2-minute pass
  into a 10-minute timeout); simple per-instruction hooks are fine (simrun: 1,500 frames ~15 s).
- Print summaries, not listings. Disassemble only flagged routines.
- Keep the user's answers terse; explain only new findings.
- A single tool call is capped at 10 minutes: poll a background job with sleeps under that
  (Chuckie Egg RELEASE run ~15 min: verify 8626 frames ~5 min, unit tests ~10 min).
- Merging a contribution sent as a plain diff (not the `contribute` zip): it is against the release
  it was made from, not main, and may carry CRLF files. `git apply --check` first; apply the hunks
  that fit, insert the rest by their context lines into today's text (renumber lists such as
  BRIEFING C2 that grew since), convert CRLF to LF, and diff a whole-file rewrite with `tr -d '\r'`
  before trusting it (El Capitan Trueno: VERIFICATION.md showed as fully replaced; the only change
  was one appended section). Never take the contributor's copy of a generated block.
- Re-derive every MD5 a contribution lists from the command it states before indexing it: Trueno's
  plain `Trueno.nex` was listed under `--tail 0xA6C9` but was the default-tail `auto` build that
  does not boot. Rebuild, boot-sim, then index.

## 2.7 Emulators: MAME [MAME]
Every MAME fact carries the tag: `grep -n '\[MAME\]' docs/*.md`. MAME is not the reference:
hardware is. Record each MAME-only result as such (Trueno: MAME 0.289 only, hardware untested).
- [MAME] MAME 0.289, driver `specnext`, runs a .nex from a NextZXOS SD image. Put the file in the
  image with HDFMonkey (`HDFMonkey mkdir IMG /dir`, `HDFMonkey put IMG local.nex /dir/name.nex`)
  while MAME is NOT running (the image is open while it runs); then Browser -> the file, or
  NextBASIC (`n` at the NextZXOS menu): `CD "/dir"`, Enter, `.nexload name.nex`. Scripted typing:
  the first key after "0 OK" is eaten - send an extra Enter.
- [MAME] Lua console: screen snapshot `manager.machine.screens[":screen"]:snapshot("name.png")` (MAME's
  snapshot folder); layer by layer (NextReg $15 bit 0 sprites, $68 bit 7 ULA off, $69 bit 7 Layer 2,
  via ports 243B/253B; while paused `emu.step()` renders one frame) - the user names the guilty layer
  at once; sprite attributes in `manager.machine.memory.shares[':sprites:attr_ram']`; main RAM pages
  are NOT readable from Lua (only the CPU's 64K view). (Also LEARNINGS 2.3.)
- [MAME] Sprite palette OFFSET: in MAME 0.289 a 4-bit sprite's index 0 under a non-zero palette offset
  is drawn opaque (whole 16x16 boxes). Not checked on hardware, so not a Next rule: until it is, use
  palette offset 0 (Trueno: one 16-colour block for every sprite). BRIEFING A1.
- [MAME] MAME models the alt ROM as a copy of the system ROM3 (NextZXOS, data at 0x3B00-0x3CFF): the
  Trueno map at 0x3B00 failed in MAME exactly as the analysis predicted, and MAME showed 512 bytes
  0xFF after the fix. nextboot.check does not (rom48(); BRIEFING C2 #19) - MAME caught what the boot
  sim could not.
- [MAME] Play-test rounds: the user walks far into the game for each place; never restart MAME unasked,
  collect the whole list in one pass (PLAYBOOK phase C). Run the game at normal speed (throttled) for
  play, unthrottled only for scripted snapshots.
- [MAME] A scripted MAME run (contributor's run_nex.py, in their archive: Windows paths, its own
  Lua helper): put the file, start MAME, wait for the Browser text, type the load, snapshot after
  fixed delays. Worth a toolkit command (BRIEFING C2 #25); CSpect is the other route (run_cspect.bat).

