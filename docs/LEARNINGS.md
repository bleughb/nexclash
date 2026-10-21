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
- Beam-racing ("multicolour" / rainbow) code - reference: Dominic Robinson's 1987 Rainbow
  Processor, decompiled and cycle-annotated at github.com/mcphail/rainbow_processor_decompilation:
  an IM 2 handler burns a fixed delay to the first visible line (48K: 224 T/line, 312 lines, 64
  lines = 14336 T before the picture; 128K: 228 T, 311 lines, 63 lines = 14364 T), then each
  224 T loop PUSHes a row of new attributes (SP pointed at the row's end) just after the beam has
  drawn one pixel line and before the next - 8 colour pairs per 8x8 cell, no clash. It is timed to
  the T-state INCLUDING contention (each PUSH into the attribute area can wait up to 6 T), and it
  self-corrects only slightly (measured ~223.9 T per loop).
  Consequences for us: (1) a game or loader using this is broken by anything that changes its
  T-state count or contention - a hook inside the timed loop, NextReg $07 turbo, $08 bit 6
  (contention off), 60 Hz, the wrong machine timing in $03 - while the differential verify, which
  counts instructions not beam position, still passes (simulator blind spot, BRIEFING A1). How to
  spot one: IM 2 handler -> long fixed delay -> loop of PUSHes/LDs into 0x5800-0x5AFF that rewrites
  the same attribute row every ~224 T. Leave such code unhooked and at 3.5 MHz. (2) On the Next the
  same picture needs no timing: a copper list can rewrite ULA palette entries per scanline, or
  the figure can become a sprite / Layer 2 - the route if a multicolour game is ever converted.
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
  (e.g. a start-up tail) disappears from under the PC -> a tail (48K and 128K) must end below 0xC000.
- 48K timing (NextReg $03) does NOT stop 7FFD/1FFD decoding (VHDL 3.01.09; the old belief was wrong and
  harmless). The lock that protects 48K games is 7FFD bit 5, written by the tail itself.
- On a 128K (toastrack) an OUT to 0x1FFD is a 7FFD write (A15 = 0, A1 = 0): Target Renegade's entry code
  does OUT (0x1FFD),4 and so pages bank 4 + ROM 0 on a 128K. Whether the Next (128K timing) sees it as
  7FFD, 1FFD or both is not known: build from the state AFTER such a write (the tail then writes 7FFD
  and 1FFD itself) - games/target_renegade.md.
- A game may run with ROM 0 selected in play (Target Renegade: 7FFD = 0). The alt ROM image the hooks
  live in is the one the game selects: fill image 0 too (setup: 1FFD = 0, 7FFD = 0, write mode, LDIR
  0000->0000, hook bytes over it) and keep the bytes the game reads (scan --range 0x0000-0x3FFF).

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
- A setup that uploads patterns from a bank mapped at one 8K slot (0xE000) reads past 0xFFFF into
  ROM when the patterns exceed 8K (64 4-bit patterns): HL wraps to 0x0000. Map the bank's second
  page when HL wraps (Jetpac, 80 patterns, 2026-10-19; nextboot caught it as "read of ROM 0" at
  0, 1, 2). Check the uploaded bytes against the built patterns, not only the boot.
- 4-bit anchor sprite, attr4: 0x80 = pattern-slot bytes 0-127, 0xC0 = bytes 128-255 (the guide's
  relative-sprite table reads the other way; matches sprites.py). Rainbow build runs on HW.
- Port 0x303B write = pattern slot (bits 5-0, bit 7 = +128 bytes); 256-byte uploads to 0x5B
  auto-advance to the next slot. A 4-bit pattern (128 bytes) whose rows 8-15 are always empty:
  zero pattern RAM once at setup, then per sprite select slot|(+128) and write only 64 bytes
  (Rainbow, 2026-09-29; hardware to confirm).
- NextReg $35-$39 set one attribute of the sprite selected by $34 (no increment); $38=0 hides.
- Sprite attr2 = palette offset (7:4) | X mirror | Y mirror | rotate | X8 (bit 0). A lookup table
  whose byte is OR-ed into attr2 must keep bits 3:0 free or be masked (AND 0xF0) where it is used:
  Rainbow (2026-10-19) packed a 'no outline' flag into bit 0 of its palette-offset table and every
  thrown-rainbow sprite moved 256 px right (X8). Only the verifier's per-pixel check against the
  original plot caught it (62 ink pixels missing); register / memory comparison passed.
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
- Never WAIT for the beam inside a limiter-paced game frame (interrupts off): the wait is paid in
  every frame whose render ends mid-screen. Rainbow 2026-10-19: half of all renders, 3.4 ms average,
  10 ms worst, typical frame 17 of 20 ms. Defer the commit to the next interrupt instead (line 248,
  bottom border): the same displayed frame as a commit at the bottom of the play area, outside the
  game frame; commit at once only when the frame will miss that interrupt anyway (or has just
  started after it) and the commit fits before line 16 (311 lines at 128K timing). Drop a deferred
  commit when a non-play screen came in between, or its sprites come back.
- Ports 0x5B (patterns) and 0x57 (attributes) decode the LOW byte only, so OUTI works with any B:
  64 pattern bytes by unrolled OUTI (16 T) instead of OTIR (21 T) with no Z80N opcode, and a sprite's
  5 attributes by 0x303B = sprite + 5 x OUTI to 0x57 instead of $34 + 5 NEXTREGs. 0x303B also moves
  the pattern pointer: write it for the attributes only after that sprite's pattern upload. No $09
  lockstep needed (that only couples $34). Rainbow 2026-10-19 (simulated; hardware to confirm).
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
- A diagnostic must not be able to lie: clear NextReg $C8 bit 0 (ULA interrupt seen) at a frame start
  only once the INT signal has dropped (poll $22 bit 7) and READ IT BACK; report "unknown" when the
  clear did not take. Rainbow 2026-10-19: the diagnostic showed "overrun" yellow solid on screens
  whose frames do almost nothing - most likely the clear ran while the frame's own interrupt was
  still asserted (hypothesis; the read-back build tells). Keep an alarm colour up until the next
  frame start; another colour written in between (a deferred commit's band) hides it on video.
- Never put hook CODE at 0x3D00-0x3DFF in an alt ROM / slot-1 page: Commando 541e34e2 crashed at
  its first figure on hardware and in CSpect with code there, and ran once the code moved out
  (tables stayed there). Probable cause: the DivMMC (TR-DOS) automap on an instruction fetch at
  0x3Dxx, despite the stub clearing NextReg $06 bit 4 - not confirmed (BRIEFING A1, C2 #24).
  Invisible to the simulator; `auto` checks it statically and per instruction (Commando).
- Flicker: never hide a figure's sprites at plot entry and show them at exit (hidden for the
  whole call, often across the beam). Keep them visible, build the new image in OTHER pattern
  memory, then rewrite the attributes in one go (Commando).
- Pattern RAM as a content cache (when the working set fits; else Next RAM, 2.5): a figure shows
  far fewer distinct frames than plots (Commando: ~110 frames in 4,300 plots). Key each pattern slot by (graphics page, frame offset, lines);
  reuse = attributes only, no build, no upload. Evict only slots no visible sprite references
  (round robin); never share an image that was masked (depth). Negative control: a lookup that
  ignores one key field must fail the pixel check.

## 1.5 Spectrum Next techniques (DMA, copper, fast sprite I/O, palettes): docs/TECHNIQUES.md

# PART 2 - GAMES / SOFTWARE

## 2.1 Game-engine lessons (all engines)
Grouped by question; add a new lesson to its group.

### 2.1a Finding the code and the figures (analysis)
- Before a colour sheet or patterns, read the row order from the plotter's line step: a plotter
  that steps UP a line per row (DEC H / 29422 in Jetpac) stores graphics bottom line first. Jetpac's
  first sheets went out upside down (Dean, 2026-10-19).
- Graphics built at run time (per level, or pre-shifted copies of the carried object) live at fixed
  buffer addresses: key their patterns by (address, the variables the builder reads), build them
  at build time by CALLING the game's own builder in the simulator per value (Jetpac: 26921 with
  (24048) = level, 28409 with (23860) = part), and cover every value in the unit tests.
- Graphics an address does NOT identify: before keying colours (or a cache) by graphics address,
  check the bytes never change while drawn (`rzx.trace` at the plot: values seen per address). Rainbow
  shifts the player's frames IN PLACE to the figure's x (60300), and loads each island's creatures
  and boss into the same buffers: an address-keyed sheet showed broken players and mixed islands
  (Dean 2026-10-19). Key such pixels by (island, address) or by the unshifted position.
- A figure is the game's OBJECT, not touching boxes: hook the routine that builds one object's
  draw list and tag what it allocates (Rainbow 54533 / 50614 / 53318). Bosses can be several
  objects (Rainbow: one per quarter) - join those by their graphics area.
- The RZX shows a fraction of the figures (Midnight Resistance level 1: 19 of 28 plotter callers;
  Dean saw more sprites on later levels at once). List every caller of the plotters statically
  (scan the code for CALL / JP to each plotter entry) and convert by default, unknown callers in
  their cell colours, instead of a whitelist of the callers the RZX showed; derive unit states for
  plotters the RZX never ran from recorded ones with the same stack shape.
- Games self-modify: check patch sites for writes during play (TID title ISR
  writes 63340). Dizzy 4's object plotter rewrites its own operation byte
  (NOP / XOR (HL)) and even a JP into a mirror path - model the op in force.
- Screen-reading logic is the main source of behaviour change: TID bubbles read
  Dizzy's pixels; Dizzy 1 falling objects land on him (472 of 736 tests). Only
  add a virtual read where the data shows a dependency: in Dizzy 3/4 it would
  be WRONG (boxes overwrite the player, so "screen XOR undo" no longer holds).
- Loader-stage snapshots (BASIC PAUSE before USR, code relocated by LDIR): identify finds an
  inert source copy. Require the ISR's dispatch to the engine; start from the post-relocation
  state (loader.prerun), stopping BEFORE hardware detection (Kempston check) so it runs live.
- An engine can plot more than one figure through the player plotter (Dizzy 6: mirrored copy via
  a second call site and a switched undo-buffer pointer). Identify every call site of the plotter
  and eraser and the undo pointer's writers before hooking the routine entry.
- Measure "once per frame": Rainbow's sprite walker ran up to 14x per render (once per band).
- A 128K snapshot may be a 48K game in 128 mode: count 7FFD writes, AY ports, ROM reads and
  non-empty banks 1/3/4/6 first. Wally: none -> build from the 128K file as-is (Rainbow path).
- Measure the write extent of EVERY dispatch target statically (run each original plotter from a
  mid-screen address, record written columns/rows), not only the ones the recordings reach: bosses
  use entries normal play never does. Rainbow's 4-wide leftward entries write E-3 (window started
  at E-2): the spider lost a column on hardware although both RZX were IDENTICAL.
- A hardware video can replace a missing RZX for a geometric bug: "left column missing only when
  facing left" pointed straight at the leftward (mirrored) plotter entries.
- Look at the GRAPHICS before deciding what a code range is: Rainbow's object codes 1-14 were
  rainbow pieces, not collectables; two verified builds turned the rainbows into sprites and left
  the real collectables (codes 15+) alone. Differential tests prove the logic, not the naming:
  render a contact sheet of every code the recordings use before designing around it.
- The return address in IY (routines ending JP (IY)) tells which caller ran a shared routine
  (Rainbow: cell composition IY 60699 / 60720 vs spawning an object into a drawn cell).
- Tell figures apart without hook state: the caller's RETURN ADDRESS on the stack at the plotter
  entry (Chuckie Egg 39500: 41238/41361 = duck, else player), or a register the routine pushed
  (hen plotter: caller DE = hen table entry -> sprite number).
- Graphics catalogue of a game that mirrors in place: hash every graphic at each frame end; the
  mirroring leaves transient half-mirrored states (1-6 frames each, never plotted). Group each
  graphic with its exact bit mirror and keep the real ones (Trueno: 167 real shapes).
- Translating a game's texts: find its letter codes and item format; a list read only from its
  head (one LD HL, no other reference into it) can be rebuilt whole, single strings only in place
  and never longer; check every old byte against the snapshot. A snapshot with the title already
  drawn: wipe the old words and print the new ones with the game's own print routines in the
  simulator (Trueno texts_en.py).
- Menus and windows the game draws in the ULA over the play area are covered by Layer 2 and the
  sprites: find them all (PLAYBOOK 0) and wrap each one (PLAYBOOK 4).
- A hook on the plotter's entry does not see code that enters it further in: list every CALL/JP
  to the plotter's addresses (Trueno: 0x82DF hooked, the dragon's bar called 0x82E4).
- The game may rewrite instructions INSIDE or NEXT TO a hook site to switch modes (Dizzy 1: 58079
  XOR C / OR C / LD A,C and 58709 XOR (HL) / NOP for the room tiles - the old site at 58707 would
  have had its JP target overwritten). Before choosing a site, list every writer into the routine's
  code bytes (static LD (nn),A / LD (nn),HL scan + the verifier's "game wrote a patch site"); a hook
  that emulates such an instruction reads it at run time and handles every value the game stores.

### 2.1b Hook design and safety
- Guard limits come from the ORIGINAL's capacity, found by running it, not from the data format:
  Target Renegade's graphic header allows 255 bytes per row, but the plotter's unrolled row code takes
  at most 6 (W = 7 or 8 never returns); the converted / passthrough guard says W <= 6.
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
- Never hook timing-critical code: title-screen ISRs playing beeper music
  (TID 63328) broke the music when hooked.
- Loop control can live in AF' (Rainbow plotters: EX AF,AF' / JP NC per row pair). Before
  re-running game code, restore AF' (and every register) to the dispatch value.
- Re-run a plotter at its REAL address with a RAM page mapped over the screen; re-basing DE to a
  private canvas broke plotters that save D, run leftwards or are 6 bytes wide.
- Hook state must not be baked into RAM the LOADER still owns: Commando's .z80 is the BASIC
  loader (sysvars + program at 0x5C00) and the build overwrote it with the hook tables. Init the
  state from a hook at the game entry (the USR target), unit-tested from the loader's real RAM.
- Entry tables keyed by an object's position leak when the game retires the object without a
  last plot (Commando soldiers leaving at the bottom: invisible entries filled the table). Keep no
  entry for an invisible frame; in verify, max entries = table size is a red flag - count the
  plots that fell back because the table was full.
- Hooks that run with interrupts on must leave everything the game's ISR reads intact at EVERY
  instruction: IX, IY, I, IFF, and SP on a stack with room. Commando's IM 2 handler tests IY+7
  flags; a hook that borrowed IY made the handler draw the menu's spinning logo in-game and leave
  stray dots. Check it statically (disassemble the hook blocks: no IX/IY writes) and per
  instruction in the simulator, with a negative control (LD IY in a hook).
- Hook code that returns into the game's own loop must not write below the game's SP (no CALL, no
  PUSH on the game stack): the original's dead-stack bytes (pushed BC etc.) differ otherwise. Use
  a macro, or the hook stack in the hook's page.
- Every path that shows a screen without the normal build (a clear mode, an end screen) must
  clear or hide Layer 2 and the sprites; a deferred Layer 2 rebuild 'until the mode ends' left the
  previous screen's foreground on the dragon's screen.
- A game's interrupt handler can change the interrupted code's registers (Dizzy 1's title-music
  handler DECs B and C and sets carry): an interrupt inside a hook would corrupt the hook. Check
  which handler is installed at EVERY hook site in the recording (verify asserts it) - the in-game
  one here is the ROM's 0x0038, which keeps every register.
- Erase-then-draw pairs that run straight-line for the same figure (Lode Runner 0x9A47 -> 0x9A5C):
  hook only the draw - the sprite moves, never hides - and prove the pair is straight-line (code) and
  that the sprite equals the screen at every frame end (verify's frame model); no flicker risk.

### 2.1c Screen models: back buffers, incremental draws, screen copies
- Redirect a back-buffer game's screen copy without touching its code: map the copy's destination slot
  (MMU 2) to a dummy page while it runs and put the scenery on the screen yourself (Target Renegade:
  scenery copied at the draw-all entry, when the buffer holds no figure; the copy's exit maps the
  screen back). Its registers, memory, timing and beeper OUTs stay the original's.
- Copy the scenery only when it changed (a dirty flag set by the scenery redraw, the screen clear and
  the text printer): Target Renegade's 4K copy every game frame cost ~105K simulator T, more than the
  game's whole slack (it HALTs ~35K T per 3-frame game frame).
- When a plotter reads only its gfx and a back buffer the game never reads, REPLACE it: convert the
  gfx straight to patterns and emulate its end state (alt regs, flags via the same OR/ADD, stack
  PUSH, self-modified operands, (43067)). Simpler than Rainbow's two canvas runs; verified exactly.
- Put the sprite commit AFTER the pixel copy (Wally 47637), not at blit start: the LDI copy takes
  ~1 frame.
- A back-buffer composer can RESTORE the buffer again before any copy: those plots never reach the
  screen. Drop the pending sprites at every restore entry (hooks, verification, the colour-sheet
  capture) or they appear for one render / on the sheet. Find it by tracing the call order of
  restore / plot / copy / commit across a room change (Wally: intro-walk plots at 61544/61560, then
  the room changes and 61090 restores before the commit; 2026-10-14).
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
- Incremental-draw engines (no full redraw: erase = tile redraw at the old position, draw = OR /
  overwrite at the new one; Chuckie Egg) need no staging: ONE sprite per object, set at its plot,
  hidden at its erase and at every screen clear. Keep the plotters running and remove only their
  screen pixel and attribute writes (NOPs), so all game state stays the original's.
- A plotter that composes figure + background in a buffer and then overwrites the screen: swap the
  compose (LD A,(DE) / OR (HL) -> LD A,(HL) / NOP) so the blit writes background only; prove the
  buffer is write-first and read only by that plotter (Chuckie 29344-29391).
- A differential plotter's erase (clear old frame, OR new) also cuts the scenery under a figure
  that is now a sprite (its old bits were never on the ULA); games that redraw scenery only on
  scroll frames then show bitten scenery. Save the bytes under the old frame at entry and OR them
  back at exit: a converted plot leaves the ULA unchanged (Commando svsave/svrest).
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
- Back-buffer games (El Capitan Trueno): leave the plotter untouched and point its 'behind the
  foreground' map at bytes that say every cell is foreground: it saves the scenery as usual but
  draws no figure pixel and paints no attribute, so game memory stays as the original's and the
  verification is simple. Clean attributes at the copy (the scenery copy, not the work buffer),
  sprites with the game's mask. Depth: the game's own foreground cells copied into Layer 2 with
  the palette priority bit (in front of the sprites) - an alternative to per-sprite masking.
- The scenery BEHIND an object (for fix cells or a wall behind bushes): build the screen in the
  simulator twice, with and without the frames that hide it - the background is then the game's
  own, not a guess (Trueno bush_walls.py, fix_cells.py).

### 2.1d XOR engines
- XOR engines: model visibility as parity. Dizzy 1 had 7 double draws that cancel.
- Plotter return registers may differ when the player is not on screen (Dizzy 1
  A after erase). Check whether callers use them before "fixing".
- Overwriters (boxes, wipes, nibble text) can make the original leave ghost
  pixels; the patched game won't. Diffs confined to the undo buffer are fine if
  nothing else reads it (check references).
- Collision often uses attribute BRIGHT: leave the background/attributes alone.
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
- XOR engine that erases and redraws in ONE pass (old XOR new per byte; Match Day, 2026-10-20), and
  nothing reads the screen: NOP the figure screen writes (registers and game memory stay the
  original's, the ULA keeps only scenery) and take each sprite's image from the game's own image
  BUILDS, not from a shadow (a shadow mixes overlapping figures). Record every build / clear into a
  per-figure ring (dest, graphics row, shift, sequence) and rebuild the shown image row by row from
  the newest entry covering each buffer row: the game reuses buffers, rebuilds only part of an image
  and clears rows of a buffer it has just drawn. Identify a figure by something that moves with it
  (its buffer pair): a depth sort that swaps whole records changes its IX every frame.
- XOR figures PRINTED as tiles at level start (Lode Runner, 2026-10-20): the level draw puts each
  figure on the screen with the tile printer (overwrite), and the first XOR erase removes that print.
  Hook the print too (sprite + a blank tile) or the first move leaves an inverted figure. Found in
  phase A because an XOR-parity count by (graphic, x, y) showed twice the figures the screen had.

### 2.1e Sprites, patterns, colours, depth
- A figure the game draws as TWO objects (Match Day's diving keeper: the keeper + a spare object 16
  px to its right) joins on the colour sheet only by the game's own pairing (frames 2k + 2k+1), and
  on screen it TEARS in the original: the halves update on alternate frames while the camera scrolls.
  Locking the second half's sprite to the first half's camera position (shift by the camera
  difference at their draws) removes the tear without touching the logic (Dean, 2026-10-20).
- Graphics the game mirrors IN PLACE (Wally: 33251 flips a gang member's frames whenever he turns):
  do not track the facing state. Key the colours to the snapshot's orientation and let the hook
  identify the bytes as plotted by a 16-bit check against the stored and the mirrored check; no match
  = run the original plotter. The same check makes precomputed per-graphic data (canvases) safe
  against any graphics the game rewrites.
- Depth from a game's collision boxes: use the point the game's own walk test checks (log the
  test routine's arguments in the RZX: Commando y + 6), not the figure's feet - with the feet a
  figure stopped above a small box came out in front.
- Pattern slots with a cache: mark each slot "on show" (last commit) and "used by this commit"
  (two bits, shifted at each commit) instead of commit stamps; stamps wrap, and with <= 64 sprites
  per commit and on show a free slot always exists. Key cells-coloured images by the attributes
  under them (and Y & 7), fixed-colour ones by graphic + colour; mirror by the sprite bit, not in
  the key.
- Solid sprites: a body fill from the frame itself (a pixel inside the ink both on its line and
  in its column) reads as a filled figure; objects that hide a figure need their SOLID shape (the
  game's draw mask with holes filled), not their ink, or the figure shows through paper-coloured
  parts.
- A figure's exact ink and mask: call the game's own plotter in the simulator on a buffer of 0x00
  (ink) and of 0xFF (cleared pixels = mask). No drawing code to read, no guessed body.
- Capture each shape from ONE consistent state: a game that mirrors graphics in place flips the
  trailing mask bytes too; a catalogue graphic written over a mirrored state got a mirrored mask
  (Trueno frame 98: figure pixels left uncovered = white flashes).
- A game that already toggles a hit bit flashes by itself: do not add your own blinking (in phase,
  the two cancel out; Trueno).
- Redrawn figures (a human's cleaner drawing) no longer cover the game's whole mask: either keep the
  sprite's opaque area >= the mask, or stop the figure reaching the ULA first (Trueno: no-draw map
  patch / pre-copy restore), or the mask shows round the new drawing.
- A sprite shape's patterns never cross an 8K page (64 4-bit patterns per page): the upload and the
  pattern index assume one page per shape (Trueno patterns.py).
- Screen shake: offset Layer 2 (NextReg $17) and the sprites for the shaken copy only, from a hook
  on the game's shake (Trueno 0x887D: NextReg $7F bit 6 -> the commit moves both 8 lines).
- A human's edits on a sheet: keep the sheet exactly as handed out, diff the returned one against
  it, and give each edited cell to every cell drawn from the same game tile (and its mirror). A
  later round on the same tile overwrites cells the human drew unlike their tile: say so first
  (Trueno bush_round.py).
- A colour that changes every redraw may be the game's own (Dizzy 1's items cycle their colour
  field): find the writer of the colour before calling it a bug, and ask whether to keep it.

### 2.1f Speed and timing
- A game with NO frame sync (Match Day: no HALT, no FRAMES wait in the match loop) loses exactly the
  hook time: +25 % in round 1. Pay for it by running the game's own now-silent drawing at 28 MHz (its
  screen writes are NOPs, the loops still run): the image builds, the XOR draw and the ball routine at
  28 MHz brought it to +2.3-3.5 % (2026-10-20). Count 28 MHz T / 6 in the verify's speed line.
- 28 MHz code with interrupts ON runs the game's interrupt handler at 28 MHz too. A handler that
  plays beeper sound with timed loops then plays 8x fast (Match Day 0xB381..). Wrap the handler
  without adding stack depth: point the IM 2 vector (alt ROM word at I*256+0xFF) at a stub that
  saves the speed in NextReg 0x7F, sets 3.5 MHz and JUMPS to the handler; patch the handler's exit
  to restore it. Check the game's deepest interrupted SP first (Match Day: variables 18 bytes below).
- Hook cost: scanning all cells of a row per render costs more than the work itself - keep an
  occupancy bitmask (per row) in the cell hooks and visit set bits only; cache derived data per cell
  (last result + key check) before hashing; summarise per-cell classes in the hooks, not per render.
- No frame sync (interrupts off or no HALT in play, nothing but the ROM reads FRAMES): the game runs
  at the speed of its CPU time, so every T-state a hook adds slows it 1:1 (Dizzy 1's first build:
  +22K T per 69,888-T frame = a third slower). Check it before designing (scan for HALT / FRAMES
  readers). Two fixes, both memory-exact: keep the game's own bodies at 3.5 MHz and run only the hook
  work at 28 MHz (Smash TV, ~+6%); or let the plot ENTRY hook switch to 28 MHz and swap the return
  address for a ROM trampoline that writes the original address back into the (now dead) slot,
  switches back and returns, so the game's plot loop and every per-byte hook run at 28 MHz (Dizzy 1).
  Measure it: Speed line (T per game frame, original vs patched) from the verifier's pair runs. A
  28 MHz part costs T + 1 per memory read in 28 MHz cycles, i.e. (T + reads) / 8 at 3.5 MHz - not
  T / 8 (TECHNIQUES "NextMasterSystem", speed rule; BRIEFING C2 #1).
- Turbo (28 MHz frame + limiter) compresses whatever the game spreads across its frame. A music
  player ticked several times per game frame (Rainbow: 3, i.e. ~50 Hz at 3.5 MHz) then plays its
  ticks within a few ms and is silent for the rest of the frame: choppy music, and every overrun
  frame a hitch. Do not move the player (its timing against the game's sound requests is game
  state): capture the chip writes at the player's own output routine (Rainbow: one routine for
  every AY register write) into a per-tick queue and send one tick per interrupt. Memory and logic
  stay identical; verify the chip state after each tick sent against the original's. Profile
  before choosing Next hardware: Rainbow's game logic was 1.2 ms of a 9 ms frame - the hooks,
  not the game, were the cost, so hardware scrolling would not have helped.

### 2.1g Elsewhere
- Other projects worth reading for design ideas (NextMasterSystem: IM2 hold mode, slot borrowing,
  static caller scan, cost model): docs/TECHNIQUES.md 2.

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

- A screen effect that uses MEMORY AS MASKS reads all of it (Lode Runner's fade: screen AND bytes
  0x0000-0x6BFF, 4 passes): the alt ROM hook area and the printer buffer then change what the effect
  draws, so neither is free. Look at what a reader reads (scan --range ROM range, readers by PC)
  before choosing altrom; Lode Runner's hooks went into game RAM proven never touched (A3 "ram").

## 2.3 Our toolkit (nexclash) and host tools
- Z80N instructions in hooks (ADD HL,A, MUL D,E, ... ; the user asked for them, Cyclone 2026-10-21):
  SkoolKit's simulator does not know them, so the engine's verifier adds a handler per opcode it uses
  to sim.after_ED, as for NEXTREG (cyclone._machine: ED 31 ADD HL,A, ED 30 MUL D,E; flags unaffected,
  8 T). An unknown ED opcode runs as a 2-byte NOP in SkoolKit - a hook that uses one without a handler
  is mis-simulated silently, so list every Z80N opcode the .asm uses next to its handler.
- Profile hooks per routine before optimising (cyclone.PROF: T per PC from the patched run, mapped to
  the .asm labels via the sjasmplus symbol / listing file). Cyclone's render hook went 1.9M -> 310K T
  (28 MHz T) by: skipping empty sprites (row-occupancy table instead of scanning), only strip cells the
  figures changed, a fast path for empty pattern rows, Z80N ADD HL,A / MUL D,E, CPIR / CPDR to jump to
  the pixels a dilation / flood fill must visit, and a 1-pixel "outside" ring around byte planes (no
  edge checks, no seeding pass). A cache of computed masks did NOT pay: 157 distinct helicopter images
  in 682 renders, 27 % misses even with 26 entries - measure the key distribution before caching.
- nextboot.check is a 48K check (expects 7FFD = 0x30 locked, bank 0): a 128K plain build needs its
  engine's boot check (rainbow / midres / renegade.boot_check: the snapshot's 7FFD and MMU 6/7).
- Long replays: `rzx.trace(path, pcs, on_pc)` runs SkoolKit's C simulator with a Python hook at
  chosen PCs (~400 frames/s with Rainbow's 13 hooks; the Python simulator ~20x slower): the whole
  195k-frame playthrough in ~12 min. `rzx.scan` (a callback per frame, ~8,500 frames/s) finds
  bookmarks; `rzx.cut(path, start, frames, out)` writes an RZX that starts at a frame (SkoolKit's
  write_rzx: the machine state there as its snapshot). A recording that desyncs is reported, not fatal.
- z80tonex 128K: leaves 7FFD unlocked; 1FFD=4 when 7FFD bit 4. Since 2026-09-28 it refuses a 128K
  tail ending above 0xBFFF (even with --tail) and never picks one; SP >= 0xC000 -> error asking
  for --tail. 48K output byte-identical to before.
- nextboot.check is 48K-only; rainbow.boot_check is the 128K version (reuses nextboot.boot).
- Frame-level questions over a whole RZX (what changed by the end of each frame): SkoolKit's C
  simulator with a patched RZXTracer.next_frame replays 53,543 frames in 4-8 s; the simrun /
  analysis commands run per-instruction Python hooks, ~100x slower (BRIEFING C2).
- [MAME] MAME runs the .nex; loading, the Lua console (layer-by-layer snapshots) and quirks: 2.7.
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
- Colour sheets, outlines (Dizzy 1, 2026-10-14): the user painted a 1-pixel black border round
  every figure inside the figure's box and the read-back IGNORED all 2,471 pixels: the map had a
  colour only for ink / interior bits, the PNG gave no hint. Users think in boxes, the engine in
  bits: say on the sheet's rules what is paintable, and report ignored paint loudly. Fix kept general
  (coloursheet paint_clear: every bit of the graphics bytes, paper as code 0). Also: giving paper a
  colour exposed a latent key bug (Dizzy's 4-px-shifted frames wrapped their right edge onto the
  next row's byte) that was harmless while paper was never drawn - when a pixel class starts to
  matter, re-check every map from pixels to keys for that class (bounds, wraps, mirrors).

## 2.4 Recordings (Fuse / RZX)
- No recording at all (Jetpac, Dean 2026-10-19: "no rzx this time"): the differential test ran on a
  free run with a key schedule (simrun) - same code paths, synthetic input - and the content a free
  run never reaches (rocket build, fuel, items, later levels) came from the game's own graphic
  tables into unit tests over every graphic. It proves the hooks, not the game's own paths through
  later content; the record says "free run" until a real recording exists.
- A recording need not start from the attached snapshot (Target Renegade's started at the game menu,
  its own SZX): usable when the code at every patch site is the snapshot's (verify checks the site
  bytes at every event); the start-up path is then proven by the boot / front-end checks only.
- Autosave snapshots: `nexclash.py rzx strip A.rzx -o B.rzx` (keeps the first snapshot; replay
  continues from the simulated state, as rzxplay --flags 4). Unstripped RZX desyncs ("N port
  reading(s) left" / "Port readings exhausted" at the first autosave, ~frame 250). EVERY replay path
  of an engine strips - not only auto's verify: Midnight Resistance's `sheet` capture did not and
  failed on both recordings until 2026-10-14. 13 of the reference recordings have autosaves; a new
  replay command (sheet, preview, analysis) is tested on one of them.
- Autosave was on in both Rainbow recordings, the Wally one (12 snapshots) and the Chuckie Egg one
  (10) despite "off": count snapshots in every RZX.
- Wally: Dean could not switch character in play; all five descriptors were still plotted (other
  rooms/character art), so plotter A covered all five.
- A .z80 saved MID TAPE LOAD (PC in ROM LD-BYTES, Cyclone 2026-10-21) is not a start state: a .nex of
  it waits in LD-BYTES forever. `inspect` says "ROM LD-BYTES (tape load)"; take the RZX's first snapshot
  instead (the next point).
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

- No .z80, only a Fuse RZX (Lode Runner, 2026-10-20: a TAP + an RZX): the RZX's first snapshot (SZX)
  IS the start state - convert it (SkoolKit Snapshot.get -> simutils.from_snapshot -> get_state ->
  write_snapshot; check RAM and registers equal) and the recording starts exactly at the .z80 (the
  "Record from snapshot" case: nothing unverified between them).

## 2.5 Verification method
- "Never jump into a patched instruction" needs the ORIGINAL instruction boundaries under each JP:
  a byte that starts an original instruction must be reached only through the site, a byte inside
  one must never be a PC. Counting every byte of the 3 bytes as "must equal the site's count" fails
  every site whose first instruction is longer than one byte (wally2 STARTS / INTERIORS, 2026-10-14).
- Lockstep RZX replay cannot prove equivalence once cycle counts change (input
  sampling shifts). Use per-routine differential tests from real states.
- Per event: original and patched from the same state on private overlays; compare all registers
  except R/T/MEMPTR and all memory.
- Model what a routine USES at the moment it uses it (capture the inputs at the inner call, e.g.
  the draw loop's entry), not from memory after the event returns: code later in the same event may
  change them. Match Day 0x8D63 clears the top rows of the image buffer it has just drawn from; the
  verifier read the buffer after the call and reported 5 correct sprites as wrong (2026-10-20).
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
  LRU in O(1) (Mike Dailly's C64-to-Next conversion blog, supplied by Dean 2026-10-20): slots on a doubly linked list; a hit
  unlinks the slot and puts it at the front, a miss takes the slot at the END (least recently used)
  - no scan, no stamps. His caveat: within one frame, one-off figures can push a common image down;
  harmless while the pool is larger than the images one frame needs. Still keep our rule: never
  evict a slot a visible sprite uses (skip it at the tail).
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
- Full verification runs one at a time (BRIEFING C3b): parallel full runs on the 1-2 CPU sandbox
  cost a whole extra turn (2026-09-29).
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
- A check whose failure key does not END with '!' can never fail: auto / selftest test
  `k.endswith('!')`. Four Rainbow unit checks were written 'FAIL! <detail>' (found 2026-10-19 when a
  new check failed silently). Write '<detail> FAIL!'; read the failure list, not just 'PASSED'.
- Hand-kept duplicate lists drift (selftest INPUTS / EXPECTED, STATUS, VERIFICATION, verified.json
  all held the same MD5s). Keep one source (the record) and generate the rest.

## 2.6 Process / tokens (this sandbox)
- Background jobs die when the turn ends (or the shell resets) unless started in their OWN session:
  `setsid nohup sh -c 'cd DIR && a; b' > log 2>&1 < /dev/null &`, then poll inside the turn. Plain
  `nohup cmd &` and `( a; b ) &` die silently - the log just stops (Midnight Resistance session:
  a 20-min `selftest --verify` lost twice). Check with `ps -eo pid,sid,args`: the job's SID must
  be its own PID. 1-2 CPUs: `--jobs 2` at most; one long job at a time.
- Start the job on its own: in `a && b && setsid nohup job &` the `&` backgrounds the WHOLE chain,
  so a failed `a` silently skips the job and its output is lost.
- A single tool call is capped at 10 minutes: poll a background job with sleeps under that
  (Chuckie Egg RELEASE run ~15 min: verify 8626 frames ~5 min, unit tests ~10 min).
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
- Name scratch scripts uniquely, NEVER after a stdlib module (dis, code, io, json, types, ...):
  Python imports the script's own directory first, so a dis.py shadows the stdlib and breaks
  SkoolKit (happened twice, the second time with this line already here).
- Before starting a long run, `pgrep -fa` for one already running with the same output folder:
  Match Day 2026-10-20 had two identical full `auto` runs writing one folder for 76 minutes, both on
  code that had been edited since they started (their results were stale). Kill by PID, never -f.
- Do all analyses in one simulator pass.
- Profile a slow run before redesigning it (`python -m cProfile -s tottime nexclash.py auto ...
  --quick 300`). 2026-10-20: two thirds of Lode Runner's and Jetpac's verify time was BUILDING
  SkoolKit simulators (~3 ms each, two or three per patched call), and Target Renegade compiled the
  whole patched simulator module (~30 ms) twice per call via `_rw_simulator()`. Fixes: the class is
  built once per process, per-event simulators come from nexclash/simpool.py (same output, 3-4x
  faster), and deterministic helper runs are memoised (Jetpac's graphic builders: 4,008 runs ->
  a few dozen). Check a speed-up with the same quick run before and after: the reports must match
  line for line apart from elapsed times.
- Keep per-instruction work in an analysis hook O(1) (a dict SCAN per opcode turned a 2-minute pass
  into a 10-minute timeout); simple per-instruction hooks are fine (simrun: 1,500 frames ~15 s).
- Print summaries, not listings. Disassemble only flagged routines.
- Keep the user's answers terse; explain only new findings.
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
hardware is.
- [MAME] MAME 0.282 passes Ped7g's Copper, NextReg-defaults and Layer2Port hardware tests where
  CSpect 2.11.1 / 2.9.2 and ZEsarUX 8.0 fail Copper and NextReg defaults (TECHNIQUES 1 "Hardware
  ground truth"): prefer MAME over CSpect for a copper build. Record each MAME-only result as such (Trueno: MAME 0.289 only, hardware untested).
- [MAME] MAME 0.289, driver `specnext`, runs a .nex from a NextZXOS SD image. Put the file in the
  image with HDFMonkey (`HDFMonkey mkdir IMG /dir`, `HDFMonkey put IMG local.nex /dir/name.nex`)
  while MAME is NOT running (the image is open while it runs); then Browser -> the file, or
  NextBASIC (`n` at the NextZXOS menu): `CD "/dir"`, Enter, `.nexload name.nex`. Scripted typing:
  the first key after "0 OK" is eaten - send an extra Enter.
- [MAME] Lua console: screen snapshot `manager.machine.screens[":screen"]:snapshot("name.png")` (MAME's
  snapshot folder); layer by layer (NextReg $15 bit 0 sprites, $68 bit 7 ULA off, $69 bit 7 Layer 2,
  via ports 243B/253B; while paused `emu.step()` renders one frame) - the user names the guilty layer
  at once; sprite attributes in `manager.machine.memory.shares[':sprites:attr_ram']`; main RAM pages
  are NOT readable from Lua (only the CPU's 64K view).
- [MAME] Sprite palette OFFSET: in MAME 0.289 a 4-bit sprite's index 0 under a non-zero palette offset
  is drawn opaque (whole 16x16 boxes). Not checked on hardware, so not a Next rule: until it is, use
  palette offset 0 (Trueno: one 16-colour block for every sprite). BRIEFING A1.
- [MAME] MAME models the alt ROM as a copy of the system ROM3 (NextZXOS, data at 0x3B00-0x3CFF): the
  Trueno map at 0x3B00 failed in MAME exactly as the analysis predicted, and MAME showed 512 bytes
  0xFF after the fix. nextboot.check does not (rom48(); BRIEFING C2 #5) - MAME caught what the boot
  sim could not.
- [MAME] Play-test rounds: the user walks far into the game for each place; never restart MAME unasked,
  collect the whole list in one pass (PLAYBOOK phase C). Run the game at normal speed (throttled) for
  play, unthrottled only for scripted snapshots.
- [MAME] A scripted MAME run (contributor's run_nex.py, in their archive: Windows paths, its own
  Lua helper): put the file, start MAME, wait for the Browser text, type the load, snapshot after
  fixed delays. Worth a toolkit command (BRIEFING C2 #21); CSpect is the other route (run_cspect.bat).

