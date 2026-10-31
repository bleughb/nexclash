# Briefing - settled facts: Spectrum Next platform and the nexclash toolkit

Established facts (differential tests against real recordings, boot simulation, hardware tests).
Treat them as settled unless marked otherwise: "documented" (from the guide / wiki / VHDL, not yet
tested), "hardware to confirm", or "probable" (inferred from a fix). Re-open a fact only if
`selftest.py` fails or a hardware test contradicts it. Read code only in the modules you are about to change.
Facts about one game: games/<game>.md. General lessons: docs/LEARNINGS.md. Status: STATUS.md.

Layers - never mix their facts:
  PART A  Spectrum Next platform (hardware + .nex format): true for every game.
  PART B  Original games: engine-independent rules only (per-game facts: games/).
  PART C  The nexclash toolkit (our Python + our Z80 patch code).

## 0. Environment (do not rediscover)
- Setup and the shell rules (pkill, heredocs): CLAUDE.md. sjasmplus is pinned and bundled
  (tools/sjasmplus: static 1.24.0 for Linux x86-64, else built from the pinned tag into
  ~/.cache/nexclash); asm2profile refuses any other version. `--check <profile>` proves a profile = its source (each hook game's record runs it
  with every rebuild); `--check --all` is for assembler upgrades (tools/sjasmplus/README.md).
- Background jobs, the 10-minute tool-call cap, worktrees for stamping runs: LEARNINGS 2.6 (the one
  place for these rules).
- Next dev guide r3 (Tomaz Kragelj): github.com/tomaz/zx-next-dev-guide (PDF; `pdftotext` it, then grep).
  Maintainers also keep a text copy in the private reference repo.
- SkoolKit: `Snapshot.get(f).memory[0:65536]` - slices need an explicit stop.
- SkoolKit Disassembler (for flagged routines): `Disassembler(mem_list, cfg)` with cfg =
  SimpleNamespace(defb_size=8, defm_size=65, defw_size=1, handle_rst=False, wrap=False, opcodes='',
  asm_hex=False, asm_lower=False, imaker=lambda a,o,b: SimpleNamespace(address=a, operation=o, bytes=b));
  `d.disassemble(a, a+1, 'd')[0]`. Scratch script names: LEARNINGS 2.6 (never dis.py).
- SkoolKit Simulator: `Simulator(mem, {'PC':..,'SP':..,'A':..})`; `run(stop=addr)` runs to PC==addr;
  register list indices A0 F1 B2 C3 D4 E5 H6 L7 IXh8 IXl9 IYh10 IYl11 SP12 I14 R15 PC24 T25.
  A variant that KEEPS writes below 0x4000: exec simulator.py source with '> 0x3FFF' -> '>= 0'
  (all 32 guards are in simulator.py) - `dizzy6._rw_simulator()`.
- `rzx info` still reports N segments after `rzx strip` (segments = input blocks); strip only
  drops the autosave snapshots.
- The auto-recorder is deterministic (same seed -> same RZX MD5); .nex bytes do not depend on
  the input file name.
- Reference inputs (game snapshots + recordings) live in the maintainers' PRIVATE repo
  bleughb/specnext (reference/), never in this public one; selftest finds them via
  $NEXCLASH_REFERENCE or ../specnext/reference; each game's evidence record (docs/records/<game>.json)
  names its files (path under reference/ + MD5) and selftest refuses a file whose MD5 differs.
- What a build reads (records `modules` / `data`): engines read their own docs/profiles/<game>.json
  (chuckie, wally, rainbow, commando); the TID / Dizzy profiles in docs/profiles are documentation
  of identify()'s result (builds recompute them; dizzy5_spellbound_dizzy.json feeds only the Dizzy V
  asm check); build.py reads nexclash/templates.json; nexclash.py reads nexclash/evidence.json
  (TID stack evidence) only when analysing, not in a `--decisions` rebuild.
- Rebuilding one game with another strategy: `nexclash.py auto G.z80 --no-record --rzx
  OUT/G_auto.rzx --strategy X` gives the same .nex as a full run (recorder deterministic; Dizzy V
  prerun reads the same RZX).
- Fast way into an unknown engine: `rzxplay.py --map FILE` + `sna2ctl.py -m FILE` +
  `sna2skool.py -c` = routine-split disassembly of everything an RZX executed (~1 minute).

--------------------------------------------------------------------------------
## PART A - SPECTRUM NEXT PLATFORM (applies to every game)

### A0. Reference sources (in order of authority)
1. Hardware test on Dean's Next - overrides everything below (e.g. $8C alt ROM, 4-bit attr4 halves).
2. Next dev guide r3 (github.com/tomaz/zx-next-dev-guide; text copy in the private reference repo). Cite as "guide r3 p.N".
2b. Core VHDL = ground truth for behaviour: `git clone --depth 1
   https://github.com/avlixa/zx_spectrum_next_03.01.09` works in the sandbox (GitHub mirror of core
   3.01.09; src/zxnext.vhd, ports.txt). Official repo: gitlab.com/SpectrumNext/ZX_Spectrum_Next_FPGA
   (`git clone --depth 1 -b 30205` worked from a cloud session 2026-10-21; it was blocked before):
   one branch per core version (30205 = 3.02.05), CPU in cores/zxnext/src/cpu/t80n/ (t80n_mcode.vhd
   decode + T-states, t80n.vhd Z80N execution + flags). Dean's core may be newer - note the version.
   Register reference: tbblue docs/extra-hw/io-port-system/registers.txt (nextreg list); in the
   official repo cores/zxnext/nextreg.txt (fetch it alone: `git clone --depth 1 -b 30205
   --filter=blob:none --sparse <repo>` then `git sparse-checkout set --no-cone
   /cores/zxnext/nextreg.txt`, 2026-10-22). Registers changed after core 3.01.05 (guide r3's last)
   must be checked there: guide r3's $06 bit 4 (DivMMC automap) is NMI-only from 3.01.10 (A1).
3. SpecNext Wiki https://wiki.specnext.dev/Main_Page - use when the guide is silent or thin.
   Read it with the chat's WebFetch tool (itch.io, table.specnext.dev and ped.7gods.org are blocked
   from the sandbox too: use their GitHub copies, e.g. ped7g/ZXSpectrumNextMisc for the opcode table; the sandbox network blocks the wiki, so scripts
   cannot download it). Pages most relevant here:
   - Memory_map (+ switching mechanics), Next_Memory_Bank_Select, Reference_machines (timing),
     Boot_Sequence, Board_feature_control (all NextRegs + port list), Interrupts
   - DMA (zxnDMA), Copper, CTC, Extended_Z80_instruction_set
   - Sprites, Palettes, Video_Modes, Layer_2, Tilemap, Blend_Modes, Refresh_Rates
   - File_Formats (NEX), System_Variables, API
   Board_feature_control = index of every port and NextReg; our subset: NEXT_REGISTERS.md.
   Z80N instructions: Extended_Z80_instruction_set (wiki) + opcode matrix
   https://ped.7gods.org/Z80N_table_ClrHome.html (NEXT_REGISTERS.md, section Z80N).
   Wiki_TODO_list flags pages that may be outdated. Pages are https://wiki.specnext.dev/<Name>.
4. Code examples / timing notes: the guide r3 LaTeX source (`git clone --depth 1
   https://github.com/tomaz/zx-next-dev-guide`: chapter-next-*.tex, greppable, no pdftotext) and its
   companion code; github.com/varmfskii/zxnext_code (zx_next_notes = LaTeX source of a Next notes
   book that complements guide r3: a page per NextReg and port with the core version that added it
   (3.01.10+ included: $0A, $B8-$BB), zxnDMA, copper, CTC, interrupts, memory, NextZXOS chapters,
   and KevB's copper/display timing tables per machine and video mode (copper/*.csv: lines and
   clocks per frame, ULA interrupt line, max WAIT h - used in TECHNIQUES 1 "Raster numbering");
   its prose can lag its register pages (memory_management.tex still says $06 enables automap); demo/ = small sprite,
   layer 2, lores examples, e.g. joyspr.asm: attributes by OTIR to port 0x57);
   github.com/stevemonks/ZXSpectrumNextMachineCodeGuides (2020, Zeus assembler: commented readmes for
   sprites, Layer 2, tilemap with per-tile palette / mirror / rotate, pixel scroll, RLE maps; its
   "tilemap must sit in 0x4000-0x7FFF" predates the bank-7 option we use);
   github.com/breakintoprogram/lib-spectrum-next (sjasmplus, Dean Belfield: lib/dma.z80 = copy and
   FILL with the full WR6 command list, lib/math.z80 = MUL D,E multiplies). Examples, not authority.
Full review of guide r3 (every chapter + its companion code) against these docs, chapter by chapter
with where each finding was filed: docs/GUIDE_R3_REVIEW.md (2026-10-19).
Rules: a new fact from the guide or wiki is "documented", not "verified", until a boot sim, RZX
test or hardware test backs it; record its source (page name) where you file it. Faster I/O
(port 0x57 / $75-$79 sprite attributes, relative sprites, zxnDMA, copper, $64 line offset,
line interrupt): researched 2026-10-19, documented, none used yet - TECHNIQUES 1 (with the
reasons each can break a game) and NEXT_REGISTERS "Not used yet". Resolved 2026-09-29 from docs/VHDL: per-line sprite limit, locked 7FFD vs MMU, NextReg
$08 bit 7 semantics, 48K timing vs 7FFD decoding (see A1, LEARNINGS 1.2-1.4).

### A1. What we rely on
| Item | Setting / fact |
|---|---|
| CPU speed | NextReg $07 = 0 (3.5 MHz) |
| Video | 50Hz forced (NextReg $05) unless `--allow-60hz` (nexclash.py convert / auto / patch / new / verify: sets z80tonex.ALLOW_60HZ, every build path; outputs then differ from the verified MD5s). "50 Hz" is exact only at VGA timing 0 and HDMI: VGA timings 1-6 (NextReg $11, the user's setting) run the frame at up to 58.93 Hz, so a converted game runs up to ~18 % fast there (TECHNIQUES 2.6, clock table: clk28 per mode from the register notes, frame rate = clk28 / clocks per frame; not measured on a board). Ask for the video mode with any "runs too fast" hardware report |
| 48K fidelity | NextReg $03 = 48K timing (written after the legacy paging writes; VHDL: this does NOT stop 7FFD/1FFD decoding - with 48K/128K timing 7FFD decodes as A15=0, A1:0=01, A14 ignored; timing only changes contention); NextReg $08 contention on; 7FFD lock via the tail's own 7FFD write (bit 5) |
| DivMMC | The stub clears NextReg $06 bit 4 and unmaps DivMMC memory (OUT $E3,0; z80tonex.build_stub). That bit turned DivMMC automap off only up to core 3.01.05: from core 3.01.10 it is the DRIVE-button NMI alone, the automap enable is NextReg $0A bit 4, and $BB bit 7 (set at reset) automaps on any instruction fetch at $3Dxx while ROM3 is selected - which the alt ROM image 1 is (official core nextreg.txt, branch 30205 = core 3.02.05, and the varmfskii zx_next_notes register pages; NEXT_REGISTERS). So on current cores (boards run 3.02.00) automap is probably still ON under our games. That explains Commando 541e34e2: hook code at 0x3D00-0x3DFF crashed at its first figure on hardware and in CSpect, and d601385e (the same code moved out of that range; only tables there) runs - not confirmed on a board (C2 #24). Rule regardless: never put code at 0x3D00-0x3DFF; data there worked |
| Simulator blind spots | The toolkit's simulator does not model: DivMMC (automap traps, see above), an interrupt arriving in the middle of a hook (so the game's ISR never sees hook register/stack state - covered only by the per-instruction interrupt-safety check), the raster (tearing, overruns), real-machine speed (28 MHz wait states, contention), CSpect differences, the VIDEO output of Layer 2 (nextboot / verify model its bank register, port 0x123B, palette writes and pixel pages, not what the screen shows: palette entry 0xE3 as transparency, layer order; Dizzy 1, 2026-10-14, hardware to confirm), beam-racing (multicolour) timing - code that rewrites attributes per scanline works only at the original T-state count and contention (LEARNINGS 1.1), the Next's own flag results after block I/O instructions (OTIR/OUTI/INIR...: only ZF is reliable on the Next; the simulator computes real-Z80 flags - LEARNINGS 1.1), WHERE INTERRUPTS LAND once hooks change the time between game instructions: a value the game writes twice before its interrupt handler reads and clears it (a "mailbox") can be lost only on the Next (NextMasterSystem's My Hero, LEARNINGS 2.1), or a routine the ISR and the main code both call (not re-entrant) can nest only on the Next (Incredible Shrinking Fireman: room 5 corruption on hardware, LEARNINGS 2.1f) - the differential check runs each routine to its return and never moves an interrupt. Anything in this list needs a static/invariant check or a hardware test. Also: what NEXLOAD leaves in RAM before the stub runs - it overwrites the 48K printer buffer 0x5B00-0x5BFF (Match Day 2026-10-20; nextboot `nexload=True` models it); and the CPU speed an interrupt handler runs at when it lands in 28 MHz code (a timed beeper player in the handler plays 8x fast: Match Day isr_w / isr_x); and what the beam shows BETWEEN two hooks: a game routine that changes the ULA over a third of a frame (Fireman's XOR plot) shows its half-done state, which a check at hook boundaries never sees - an overlay must keep old and new figure covered from the routine's entry to its exit (LEARNINGS 2.1e; Fireman's verifier checks it) |
| Emulators [MAME] | MAME 0.289 (`specnext`) runs .nex files and is how many users will test (loading, Lua, quirks: LEARNINGS 2.7). It models the alt ROM as NextZXOS ROM3 (it caught Trueno's 0x3B00 bug, the boot sim did not). Known MAME-only behaviour: sprite index 0 under a palette offset drawn opaque (hardware unchecked). A MAME pass is not a hardware pass: record which one a result is |
| Layer 2 (Dizzy 1, hardware to confirm) | 256x192, 8-bit pixels, banks via NextReg $12 (16K bank; 3 consecutive banks = 6 pages, page = first + y/32, offset (y%32)*256+x); visible = port 0x123B bit 1 (the stub writes 0x123B = 0 BEFORE the patch setup, so setup turns it on); palette NextReg $43 = $10 (Layer 2 palette 0, auto-increment) then $40 index, $41 RRRGGGBB; transparency = global $14 (default $E3) compared with the palette RGB, so entry 0 = $E3 makes pixel 0 transparent; order SLU default ($15 = 0): Layer 2 over the ULA. Zero banks in the .nex start it clear (NEXLOAD leaves banks it does not load with old contents). NextReg $69 bit 7 is the same visible bit as 0x123B bit 1 and, written with NEXTREG, keeps every register and flag ($69 bits 6-0 = ULA shadow screen + Timex mode: write 0 there for a game that uses neither). Double buffering (Wally 2026-10-14, hardware to confirm): draw into the bank not on show, then write $12 - the switch is not raster-synced (a frame may show the top of one buffer and the bottom of the other) |
| MMU | slots 0-7 = NextReg $50-$57, 8K pages; 16K bank n = pages 2n, 2n+1; $FF in slot 0/1 = ROM |
| Legacy paging | legacy and MMU paging are interchangeable, most recent change wins (guide 3.2.6): an UNLOCKED 7FFD/1FFD write remaps slot 0/1 (ROM) and 6/7 - so the tail maps slot-1 RAM AFTER its own paging writes |
| 7FFD lock | The lock IS 7FFD bit 5 (the 48K tail writes 7FFD=$30). NextReg $08 bit 7: write 1 = clear the lock; write 0 = no effect (does NOT lock); read 1 = unlocked. VHDL (core 3.01.09): while locked, writes to 7FFD, 1FFD and DFFD are ignored and trigger NO MMU remap (port_memory_change needs 'not port_7ffd_locked'), so a RAM slot-1 page survives a locked game's 7FFD writes (documented from source; hardware still to confirm for Dizzy 6). UNLOCKED writes to 7FFD/DFFD/1FFD/EFF7 set MMU0/1=$FF (ROM) and MMU6/7 to the selected bank (ports.txt). At NEX launch paging is UNLOCKED (all hardware-tested builds page with legacy writes without unlocking); the altrom stub still sets $08 bit 7 before its own 1FFD/7FFD writes. |
| Alt ROM ($8C) | Whole 0x2000-0x3FFF of image 1 usable when the game never reads that ROM range (Commando d601385e: data + code from 0x2000, runs on hardware 2026-10-12; no code at 0x3D00-0x3DFF). $8C alt ROM verified on hardware 2026-09-27: write-mode copy, read-only, 7FFD b4 switch, MMU $FF, IM1, font — all PASS; $8C=00 at NEX launch. Bits: 7 enable, 6 visible only during writes (write mode), 5/4 lock ROM1/ROM0; low nibble = same after soft reset (leave 0). 32K = two 16K images (ROM0 128K, ROM1 48K), selected by the normal ROM select: with 1FFD=$04, 7FFD bit 4 = 0/1 selects ROM2/ROM3 = image 0/1 (hardware test used exactly this); a game that selects ROM 0 in play sees image 0, which the stub does not fill (Target Renegade's setup fills it; C2 #27). Write mode: reads come from the real ROM, so LDIR 0000->0000 copies the selected ROM into its image. MMU0/1 = $FF shows the alt ROM. |
| Hardware sprites | 16x16, 4-bit patterns (128 bytes each), attributes via NextReg $34 (select) then $35 X low, $36 Y, $37 = bit0 X8, bit3 X-mirror, bit2 Y-mirror, $38/$39 pattern+visible; sprites on NextReg $15 bit 0; coords = screen + 32. A mirrored 2x2 box needs left/right quads swapped, and a frame narrower than 32 px an x offset (Dizzy V: -8) |
| Setup template (0xD000) | sprites off; uploads N x 256 bytes of patterns from bank 11 via port 0x5B; sprite palette 0 = 0, 1 = 0 (black), 2 = $B6 (white, the player colour); NextReg $4B = 0; sprites 0-3 cleared. Stub leaves $15 = 0; hooks show with NEXTREG $15,1 |
| User register | NextReg $7F: free 8-bit storage; write with NEXTREG, read via ports 243B (select) / 253B (data) |
| Interrupts | IM2 games keep working; hooks that page slot 0 must DI (IM1 vector 0x38 is in slot 0) |
| NMOS quirk | `LD A,I` P/V reads 0 if an interrupt is accepted during it: read twice (`ld a,i / jp pe,ok / ld a,i`) |

### A2. .nex conversion (nexclash/z80tonex.py) - how every file starts
- NEX V1.2 header (verified against ped7g NEXLOAD2). Game RAM = banks 5,2,0 (48K); 128K: all 8 banks.
- Bank 10 = our stub, entered at C000 with SP DFFE. Stub: speed/video/DivMMC/sprites
  off, optional patch setup at 0xD000 (pattern upload from bank 11), then copies a
  small TAIL into game RAM and jumps to it.
- TAIL (runs in game RAM): legacy ROM paging, NextReg $08, $03, restores ALL
  registers (incl. alt set, IX, IY, I, R, IM, IFF, border), JP to snapshot PC.
  Normal tail ~80 bytes; COMPACT tail 53 bytes (border/I/IM set in the stub,
  register block lives in the slot-1 page, NEXTREG $51,page at the end - or, for altrom,
  NEXTREG $8C,$80: same length, register block in the alt ROM after the hooks).
- altrom stub (z80tonex.altrom_fill): after writing the register block into RAM page 24 it maps
  the stub page (20) at slot 4 and page 24 at slot 5, jumps into the slot-4 alias (an unlocked
  1FFD/7FFD write remaps slots 6/7 = where the stub runs), unlocks ($08 |= $80), 1FFD=$04 /
  7FFD=$10 (ROM3), $8C=$C0, LDIR 0000->0000 (16K), LDIR the patch bytes lo..hi from page 24,
  $8C=0, restores slots 6/7, jumps back, restores slots 4/5. No stack use in between.
- nextboot.py simulates that boot on a Next model (every sprite build prints a `Boot` line).
- 48K and 128K: the tail must end below 0xC000. The stub runs with its own bank 10 at C000-FFFF and
  the tail's OUT 0x7FFD maps bank 0 back under the PC (El Capitan Trueno: a 48K tail at 0xFF97
  never reached the game); z80tonex refuses it, nextboot.check catches it too.
- The tail's location must be memory the game never uses (proved by access scan):
  printer buffer 0x5B00, or dead stack below SP (between SP and the stack low-water
  mark). The converter prints where it went; the toolkit checks it.
- Verified: NEX RAM byte-identical to the snapshot; tail simulated -> every register
  restored, no game memory touched.

### A3. Patch memory strategies (our Next-side runtime; engine-independent)
| Strategy | Where the patch lives | Flag "player drawn" | Hooks |
|---|---|---|---|
| printer | trampolines at 0x5B00 (game RAM, must be free); hook code in bank 10 upper page, paged into slot 0 per hook | byte 0x5B00 | DI + page slot 0 in/out |
| slot1 | everything in RAM page 24 permanently at 0x2000-0x3FFF, code at 0x386E (48K ROM's unused block); needs "game never reads ROM" | NextReg $7F | direct calls, no paging |
| altrom (DEFAULT since 2026-09-28) | alt ROM image 1 = exact copy of ROM3 (48K) + slot1 hook code + frame table + register block (TID: 0x386E-, all $FF in the 48K ROM, must end < 0x3D00 - but a game may test 0x386E = $FF as a 48K-ROM check: Smash TV does, so its hooks sit at 0x2100-; list the ROM bytes the game reads first, LEARNINGS 1.3; Dizzy V: 0x3800-; NO code may ever sit in 0x3D00-0x3DFF - Commando crashed with code there, probable cause DivMMC automap on fetch (A1); Commando: data there, code also 0x3F00+); stub fills it in write mode, tail sets $8C=$80; RAM page 24 in bank 12 is only the copy source | NextReg $7F (Dizzy V: none) | direct calls, no paging, no DI; the game may read every ROM byte the patch leaves as ROM (an engine that replaces more, like Commando's whole 0x2000-0x3FFF, must prove by verify that the game never reads it); writes ignored; survives 7FFD |
| slot7 scratch (Smash TV, 2026-10-13) | code in alt ROM 0x2100-; state + a scratch copy of the back buffer in RAM page 26 mapped at MMU slot 7 (where the game's buffer is) while a hook runs: the game's own plotters draw into the scratch (LEARNINGS 2.1) | page variables | interrupts OFF (the game's DI; its IM 2 handler lives in slot 7) |
| slot5 (Midnight Resistance; runs on hardware 2026-10-13) | code + tables in alt ROM 0x2000-0x3CFF (game reads ROM 0x0000 + font only); state, hook stack and a scratch copy of the back buffer in RAM page 26 mapped at MMU slot 5 only while a hook runs | page variables | interrupts ON: slot 5 is never touched by the ISR (full-RZX slot scan), and the ISR's unlocked 7FFD writes reset only slots 0/1/6/7 |
| ram (Lode Runner, 2026-10-20; hardware untested) | stateless hooks in GAME RAM 0xA460- after the tail (0xA400): a zero span the game never reads or writes (RZX + free runs through play, game over, menus, editor; no code points into it). Used because the game reads ROM 0x2000-0x3FFF and the printer buffer as fade masks (LEARNINGS 2.2), so altrom / printer would change the fade | none | interrupts ON (IM 2 EI / RETI): measured lowest hook SP checked against the IM 2 table below the stack |
| slot3 shadows + Layer 2 + player sprite (Dizzy 1, 2026-10-14; Layer 2 build runs on hardware) | code in alt ROM 0x2000-; variables + hook stack in game RAM the game never touches (printer buffer 0x5B40-0x5BC0); slot 3 (never touched by the ISR) switches inside a hook between the shadow pages 26 (objects + attributes) / 27 (fill) / 28 (Dizzy), the Layer 2 pages and the colour-plane pages, and is the game's page 11 at every exit (so the hook stack cannot live there); Dizzy = hardware sprites 0-3 (patterns uploaded by setup from bank 15) | variables in game RAM | interrupts ON (ROM 0x0038 handler) |
Choice rule (build.choose_tid_strategy, returns strategy/reason/tail): altrom if no recording
reads 0x386E-0x3CFF AND (printer buffer free -> tail at 0x5B00, else dead stack >= 54 -> tail
at the low-water mark); else the old rule: printer if 0x5B00 is zero in the snapshot AND never
touched; else slot1 if ROM unused AND dead stack >= 54; else refuse. `--strategy X` checks X only.
Per game: TID engine generic (Fantasy World, Magicland) and Dizzy V -> altrom; Treasure Island
(dedicated builder) -> printer only (writable state in 0x5B00); Dizzy 1 -> slot3 shadow + Layer 2
(engine dizzy1, its own strategy); Dizzy 6 -> slot1 only
(self-modifying plotter copy needs RAM at 0x2000, and it never reads the ROM). Engine builders may instead put the slot1 compact tail (53 bytes; plain tail 79)
in a player undo buffer proven write-first per RZX (Dizzy 6: 88-byte buffer at 23552).
The slot1 page may also hold relocated GAME code at 0x2000 (below the template at 0x386E):
Dizzy 6 keeps an unpatched plotter/eraser copy there (0x2000-0x2171) that self-modifies one
operand inside the page - the one sanctioned exception to "hooks must not write their own page".

slot1 hook ABI (template patch.asm, code at 0x386E): 4 sprites 0-3 written with the
$34-$39 sequence above from an 8-byte-per-frame table (TL, TR, BR, BL: attr3, attr4 pairs);
show = NEXTREG $15,1; drawn flag = NextReg $7F; DI around the sprite writes.
slot1 variant for games that read the ROM FONT (0x3D00-0x3ECF) but no other ROM: the page
must be a copy of ROM 0x2000-0x3FFF, hooks only in bytes the game never reads (0x3800-0x3CFF
for Dizzy V), register block after the hooks - NOT at 0x3FE0 (font data there).

Tail sites, strongest proof first: (1) printer buffer never touched; (2) an undo buffer that
every plot writes before the erase reads it; (3) dead stack between SP and the low-water mark;
(4) bytes whose first access in the recording is a write.


--------------------------------------------------------------------------------
## PART B - ORIGINAL GAMES: rules for every engine
Per engine / per game: games/ (TID engine, Dizzy 1, Dizzy V, Dizzy 6, Rainbow Islands,
Everyone's a Wally, Chuckie Egg, Commando, Crystal Kingdom Dizzy).

### B2b. Engine identification rule (all engines)
Require evidence the matched copy is LIVE (the ISR or a caller jumps into it). Relocating
loaders leave an inert source copy of the engine that byte patterns also match.
Before hooking a plotter/eraser ENTRY, list every caller of both and every writer of the undo
buffer (or its pointer): the same routines may draw other figures (Dizzy 6 mirror copy).

### B3. Screen-writer behaviour (what the analysis/verify model assumes)
Player removed from the ULA screen => the "patched screen" differs from the original only
where the player was. Other writers: XOR (safe), nibble-replace `LD A,(HL)/AND m/.../ADD A,C/LD (HL),A`,
overwrite (boxes, wipes). Boxes overwrite the player -> the original later leaves ghost
pixels (undo-buffer-only diffs, harmless). Virtual read is only correct when nothing
overwrites the player - add it only where data shows logic depends on the player's pixels.

## PART C - NEXCLASH TOOLKIT (our code)

Pipeline: `auto` = identify -> record (auto RZX) -> analyse (each RZX) -> plain .nex ->
sprite .nex -> verify (each RZX) -> report. Refuses instead of guessing.

| Module | Key entry points | Notes |
|---|---|---|
| nexclash.py | cmd_auto, main | CLI; evidence.json handling (_fingerprint = MD5 of plotter+512 bytes) |
| identify.py | identify(mem) | KNOWN dict -> dedicated builders; TID profile by byte patterns; frame table validated by parsing 39 frames; entry at signature-116 accepted (PUSH IX variant); two plot callers with one `LD L,(IX+3) / CALL` -> engine 'tid_mirror' (plot_site2); `undo_ptr` when the eraser uses LD SP,(nn) |
| machine.py | Machine(snap).frame(held) -> (fetches, ins) | C simulator, config int_active=0 (as rzxplay); fetches = R deltas in 100-fetch chunks; frames that run LD R,A are re-run exactly via the trace callback; pure-Python fallback |
| recorder.py | record(...) | auto_start (coverage gain); learn_inputs classifies keys by 40-frame effect: movement (no attribute change), action (<=58 attr cells, e.g. inventory; used 6%), menu (>58 cells: map/pause; used 1%); explore: room = play-area attributes (rows 3-20), SAME room if <=25% of cells differ (--room-threshold), up to 4 start states per room, 30% of actions hold one direction 50-150 frames, no identical press twice in a row, all episodes kept; script format in docstring |
| rzx.py | write_rzx, read_segments, merge, info | segments = own snapshot + input block; frames defined by fetch counts -> replay identical in rzxplay/Fuse |
| analyse.py | analyse(prof or None, rzx, sp) | one Python-sim pass; classify()/apply_write() screen model; syncs at first wipe per segment |
| build.py | TidPatch(prof, strategy, low_water), plain(), choose_tid_strategy() | templates.json = assembled templates + relocation offsets (8 symbols) |
| verify.py | verify(prof, patch, rzx) | per-routine differential test; emulates NEXTREG, slot-0 paging, slot-1 page, $7F ports |
| sprites.py | patterns_for(peek, table, base) | frames -> 4-bit patterns + attribute table |
| dizzy_patch.py | DizzyPatch | dedicated builder (TID bubbles: Treasure Island) |
| dizzy1.py | Dizzy1Patch, verify, unit_tests, auto, capture / sheet / preview | Dizzy 1 XOR engine: every figure on Layer 2 via a 1-bit shadow screen (ULA ^ shadow = the original); the template for pure-XOR engines |
| dizzy5.py | identify5, analyse5, patch class, verify5 (+ _converges) | Dizzy V engine (ISR-driven masked sprite); nexclash.py _auto_dizzy5 drives it |
| dizzy6.py | layout, relocated_copy, Dizzy6Patch(prof, mem, tail, undo_size), first_access(rzx, lo, hi), mirror_selftest | 'tid_mirror' (Dizzy 6): TidPatch slot1 + unpatched plotter/eraser copy at 0x2000 for the mirror calls; nexclash.py _auto_dizzy6 drives it (analysis + first-access pass per RZX, tail in undo buffer, verify, 780-case mirror selftest) |
| chuckie.py / wally.py / rainbow.py / commando.py / midres.py | engine modules: patch class, verify, unit tests, auto(...) | dedicated engines, one games/<game>.md each; harnesses stay per engine (C4) |
| simrun / snapinfo / memscan / isrinfo / drawcost / preview | see C4 | shared analysis commands inspect / scan / isr / cost / preview |
| loader.py | prerun(rzx, test, out_z80) -> (path, frame, pc) | loader-stage snapshots: replay until test(mem) (engine live), finish LDIR, save state. MUST be present |
| nextboot.py | boot(nex, pc), check(nex, z80, patch, tail) | simulated Next boot of a built .nex (MMU, legacy paging, $8C alt ROM, NEXTREG); run by every sprite build (`Boot` line; MISMATCH fails selftest) |
| selftest.py | selftest.py [FOLDER] --canary / --smoke / --tools / --affected [--verify] / (release) / --full / --game G [--verify] / --plan; --stamp --jobs N --human | driven by docs/records: --smoke Chuckie Egg rebuild (<1 s); --tools analysis-command golden checks on Chuckie Egg (~15 s); --affected rebuilds the games whose dependencies changed since their last check and lists due re-verifications (records.plan: own files changed -> that game; shared files -> one representative per engine); release = every game rebuilt + due re-verifications; --full re-verifies every game. Rebuild = snapshot + stored build decisions (`auto --decisions`), seconds; MD5s + boot + the record's checks. Views (STATUS table, VERIFICATION checksums, verified.json) must be current. |
| records.py | `python -m nexclash.records plan / views [--check] / deps G` | evidence records: dependency closure (AST imports + data files), per-file hash stamps (checked / verified), plan(), generated views |

Templates: Z80 sources were tramp.asm/hooks.asm/setup.asm (printer) and patch.asm (slot1);
to change them rebuild with sjasmplus and regenerate relocations (assemble twice with each
symbol XOR 0x0101, diff -> offsets). Symbols: PLOTTER ERASER_CONT ERASER_SPSAVE WIPE_CONT
WIPE_IX SOUND_TICK BOX_CONT BOX_VAR. The asm sources are in Dean's earlier zips
(clash-remover-handover.zip tools/builders/), not in the repo - ask Dean if needed.

### C0b. Analysis / verification internals (for writing new engine code)
- SkoolKit Simulator.registers indices: A 0, F 1, B 2, C 3, D 4, E 5, H 6, L 7, IXh 8, IXl 9, IYh 10,
  IYl 11, SP 12, I 14, A'F'B'C'D'E'H'L' 16-23, PC 24, T 25 (skoolkit.simulator has the names). A
  one-off script that guessed IX = 14/15 read garbage (Jetpac, 2026-10-19).
- rzxplay hook points: subclass the memory list (`__getitem__`/`__setitem__`); `registers[24]`
  is the current instruction's PC during its memory accesses; monkeypatch
  `RZXTracer.next_frame` for frame boundaries (called BEFORE interrupt acceptance); force the
  Python simulator with `rzxplay.CSimulator = None`.
- `analyse(None, ...)` covers the WHOLE recording incl. any loader phase (big LDIRs): its
  low-water / ROM-use / printer-buffer results are meaningless for loader snapshots - use
  per-byte first-access data for the game phase (Dizzy V: `dizzy5.analyse5` returns fa/fa_game).
- verify.py treats 40 bytes below the return SP as dead: this HIDES hook stack depth. Prefer
  stackless hooks or prove the extra depth is safe.
- simrun's on_read / on_write get the WATCHED memory as `mem`: reading it inside the hook calls the
  hook again (RecursionError). Read the raw list underneath (48K: `sim.memory.m`; Lode Runner's
  verify keeps it as st['raw']); the same for bulk copies taken inside `before`.
- SkoolKit's Simulator DROPS writes below 0x4000 (confirmed); on the Next a slot-1 RAM page takes
  them. Hooks must not write their own page; check a game never writes 0x2000-0x3FFF with a
  simulator copy whose '> 0x3FFF' guards are removed.
- `Snapshot.get(f).memory[0:0x4000]` is ZEROS for .z80 files: ROM bytes come from skoolkit.ROM48.
- Fuse RZX made with autosave on: `nexclash.py rzx strip A.rzx -o B.rzx` (keeps the first snapshot).
- Check sprite pixels against the screen BEFORE the plot (transparent = unchanged), not the model,
  or the original's ghost pixels count as mismatches.
- A register difference at a routine's return is OK only if stepping both machines converges
  before any I/O observes it (Dizzy V: `dizzy5.verify5._converges`).
- Hooks inside an ISR must keep EXX / EX AF,AF' parity even.
- Multi-segment RZX (the recorder writes one segment per episode, each with its own snapshot):
  rzxplay builds a NEW Simulator per segment - reset any sync state in the Simulator subclass's
  __init__ (dizzy5 analyse5/verify5 do: without it a stale screen model gave false refusals).
- SkoolKit's disassembler does not know Z80N NEXTREG (ED 91 nn n = 4 bytes, ED 92 nn = 3): a
  linear decode of hook code must step over them itself or it misaligns (dizzy1.static_check).
- Hand-assembled hooks: keep an asm source and assert sjasmplus output == the Python emitter
  (JR out of range is silent in hand assembly); use JP for long branches.
- SkoolKit's Python Simulator does block instructions (LDIR etc.) with per-byte int indexing of
  memory, so a list subclass with __getitem__/__setitem__ can model paging (nextboot.py relies on it).
  NEXTREG (ED 91/ED 92) is not a SkoolKit opcode: install handlers in sim.after_ED. SkoolKit runs
  ANY Z80N ED opcode as a silent 2-byte NOP (tested with MIRROR A): implement before using one.
  `nexclash/z80n.install(sim, nextreg)` installs all 29 (sources per handler in its docstring;
  `python -m nexclash.z80n` / selftest --tools check them); engines older than it keep their own.
- Structural test of the GENERIC TID builder without a generic-game snapshot: clear
  identify.KNOWN and identify the Treasure Island title snapshot (dizzy2.z80) -> ok 'tid' profile;
  TidPatch builds for all strategies, nextboot.check passes. Not a verification (no RZX).
- Dizzy V auto RZX with the current recorder: 6,227 frames, 16 segments, 3 rooms, 1,479 plots
  (was 4,018 frames); prerun still hits frame 26, so the start state and sprite MD5 are unchanged.

### C1. Do NOT re-derive (answers already known)
- RZX playback semantics: fetch counter per frame, IN values in order, interrupt at frame
  end if IFF (step over HALT), T reset to 0; rzxplay default flags 0, int_active 0.
- Why recordings replay: frames defined by fetch counts, not time.
- Fuse autosave RZX needs repair -> tell the user to record with autosave OFF.
- Stack low-water = contiguous writes below SP; untouched memory is not automatically free.
- Lockstep replay cannot prove equivalence of patched code (timing shifts) -> per-routine tests.
- The 2-byte difference of the old dizzy2_game.nex vs toolkit output is a stub SP change: fine.
- SkoolKit's Simulator drops every write below 0x4000; a patched run that writes slot 0/1 (a mapped page,
  alt ROM data) uses dizzy6._rw_simulator() (Fireman re-derived it, 2026-10-25).

### C2. Known limits (the backlog - the ONE list of open toolkit work)
Open items only: a finished item is deleted (history lives in git), a new one goes in its group
with the next free number. STATUS.md "Open work" holds only release state and points here.

Verification and speed
1. No hook speed report: Commando's and Midnight Resistance's hook costs were measured with scratch
   scripts (T per plot / commit from the pair runs). Wanted: an `auto` line with hook T per call
   (median / max) against a documented budget per game frame; Smash TV's per-engine `Speed` line is
   the pattern to lift into a shared helper. On the real core model: MAME breakpoints on every hook
   entry and every exit back to the game (TECHNIQUES "NextMasterSystem"). Without MAME: 28 MHz cycles
   = T-states + 1 per memory read (their MAME measurement), not T / 8. Matters most for games without
   frame sync, where hook cost changes the game's speed (LEARNINGS 2.1).
2. Interrupt injection: in verify / unit tests, run the game's ISR at random hook instructions and
   require identical results (would have caught Commando's IY bug directly; the per-instruction
   invariant check is the stand-in).
3. Boot-path RAM check (entry -> menu, in no RZX) is not automatic in `auto`: the checked range must
   be the WHOLE hook RAM. Tool: `scan --frames N --keys K --after ENTRY --range ...` (C4).
4. Treasure Island (dedicated builder) is not re-verified differentially by any tool: selftest
   re-proves only the plain tail (access scan) and the boot (record: verify.differential false).
5. nextboot.check models the alt ROM with rom48(), but the Next copies the system ROM3 (NextZXOS,
   data at 0x3B00-0x3CFF): check against the real ROM3, or make the builder copy every ROM area a
   patch relies on (LEARNINGS 1.3). Now possible (2026-10-27, Cauldron): `patch.altrom_low` +
   `altrom = (0x2000, 0x4000)` writes the WHOLE image from the build, and nextboot.check(...,
   sysrom=) boots with another ROM3 to prove it (cauldron.rom3_independent). Other engines still
   copy only their hook range.
6. `nexclash.py patch` (the users' command) writes the plain .nex WITHOUT nextboot.check (El Capitan
   Trueno's first plain build crashed at once: 48K tail above 0xC000). Run it in `patch`; refuse or warn.
7. `auto` on an unknown engine made Jetpac's synthetic _auto.rzx (6410 frames), but `scan` / `preview`
   on it stop with "Port readings exhausted for frame 532": recorder and replay disagree on one
   frame's port reads. Not investigated (Jetpac used free runs).
8. selftest has no dependency check: without SkoolKit every rebuild prints "got None" and the canary
   says "the TOOL CHAIN is broken". Check the imports (skoolkit, PIL) first; golden check in tools_check.

Analysis tools
9. Explorer reach is LOW (1-4 real rooms in 6,000-60,000 frames on the Dizzy games). Next step:
   goal-directed exploration for the TID engine from the player X/Y variables (walk to screen
   edges, jump when X stops changing). Until then a short human RZX covers more; puzzle-gated
   content always needs one.
10. classify() assumes "overwrite" for unrecognised writers - should flag for review.
11. Static caller scan: `scan` sees only what the RZX ran, but PLAYBOOK 3c wants every caller of every
   plotter. Add `scan --static` (recursive descent from entry + ISR, RZX PCs as seeds, object handler
   fields `LD L,(IX+d)/LD H,(IX+d+1)/JP (HL)` and the stores into them, a byte scan for `CD/C3/CA..
   lo hi` at a plotter rated by code-likeness; design: TECHNIQUES "NextMasterSystem"). Keep the
   existing output; golden check in tools_check. (The byte scan part exists in survey.static_sites,
   2026-10-26; the recursive descent does not.)
12. A shared fast mode for frame-level questions (C simulator + RZXTracer.next_frame, seconds per RZX)
   next to the per-instruction simrun commands (LEARNINGS 2.3); `rzx.trace` could also speed older
   engines' capture and verify passes.
13. Long passes print nothing (`patch --rzx` on Trueno's 53,542 frames): add progress output.
14. A key log from a recording (keys held per frame range from the port 0xFE reads; contributor's
   rzx_keys.py) - worth an `rzx keys` command.
15. analyse / recorder are 48K-only: `convert --rzx` with a 128K RZX stops with "N port reading(s)
   left for frame 0" (simrun-based scan / isr / cost work on 128K).
16. Treasure Island game snapshot: the auto-recorder finds no start / inputs (needs --start/--keys or
   a user RZX).
40. `nexclash.py convert GAME.z80 --rzx R` stops with "Port readings exhausted" on a recording with
   Fuse autosave snapshots (Chuckie_Egg.rzx: 9; found 2026-10-26): analyse() replays the RZX as it is,
   while simrun / auto strip autosaves first. survey strips them before analyse(); `convert` (in
   nexclash.py: every game's dependency) still needs it.
Toolkit structure
17. Generic builder = TID engine only. Next: an XOR template (generalise dizzy1.py: 1-bit shadow screen
   + Layer 2), then non-Codemasters engines; virtual read is in dedicated builders only (the generic
   tool refuses and hands over).
18. Engine registry: auto dispatches through nexclash/engines.py; identify / patch do not yet, and
   `identify` says unknown for every dedicated engine (add signatures.json / identify entries). Any
   other edit to nexclash.py (records ALWAYS) still makes every engine's representative due.
19. Dependency smell: nextboot.py imports dizzy6._rw_simulator, so every game depends on dizzy6.py and
   a Dizzy 6 change counts as shared. Move _rw_simulator into a shared module.
20. Colour sheets / recolour on older engines: games converted before Midnight Resistance have no
   sheet; Midnight Resistance has a sheet but no recolour; sheets written before 2026-10-19 use
   unique=True and join pieces by touching boxes. Bring each to docs/COLOURS.md at its next rework. Not
   done: a `nexclash.py sheet` command (today `python -m nexclash.<engine> sheet`).
21. [MAME] A scripted MAME run (put the .nex in the SD image, load, snapshot) next to run_cspect.bat
   (LEARNINGS 2.7).
22. nexpatch (contributor's proposal): a .nex delivered as an HTML page that rebuilds it from the
   user's own .z80 (CRC32 match, bytes ChaCha20-encrypted under SHA-256 of the .z80); checked
   2026-10-14 byte-identical, no network code. Maintainers' decision pending.
23. `selftest.py --affected` is not run automatically on each PR (needs a GitHub Action with the
   private references via a secret); a maintainer runs it before merging.

Hardware to confirm
24. The 0x3D00 cause (A1): a test build with one harmless routine at 0x3D00 (emulator with DivMMC, or
   hardware); then record the confirmed reason in A1 / LEARNINGS 1.4. Lead (2026-10-22, official core
   nextreg.txt 3.02.05 + varmfskii zx_next_notes): from core 3.01.10 the automap enable moved from $06 bit 4 (what the stub clears)
   to $0A bit 4, and $BB bit 7 automaps on fetches at $3Dxx. Test: the 0x3D00 build crashes as is
   and runs with the stub also clearing $0A bit 4 (read-modify-write; and/or $BB bit 7). If so, the
   stub fix changes every game's output: maintainers decide, rebuild and re-verify (selftest
   --stamp).
25. Builds never run on hardware: Dizzy V (dialogue text, slot 1 with 7FFD written every interrupt -
   A1 "7FFD lock"), Magicland, Dizzy 6 (its mirror path is proven only by the unit selftest: wants an
   RZX through the mirror room; Dizzy 6 stays slot1). Later: the tail inside the alt ROM (same
   address in both images, no game RAM).
26. State a previous program may leave behind (documented, not seen on hardware): the stub resets
   speed, video, DivMMC, sprites, $C0, 0x123B, and NEXLOAD is asked to reset NextRegs (header byte
   134 = 0; which registers is not confirmed). Not written, and each would break games if left
   non-default: a running copper ($62); line offset $64 (shifts $1E/$1F, which the Rainbow raster
   wait reads); ULA interrupt off ($22 bit 2 / $C4 bit 0) or line interrupt on; ULA output off ($68
   bit 7), ULA scroll ($26/$27), clip ($1A); Layer 2 resolution ($70), scroll ($16/$17/$71), clip
   ($18); palette state ($43, $14, $4A); the F3 / F8 keys ($06 bits 5/7) let a player undo the forced
   50 Hz or the CPU speed. Cheap guard: NEXTREG $62,0 / $64,0 / $22,0 / $C4 bit 0 / $68,0 / $26,0 /
   $27,0 + $06 AND $5F in the stub - changes every game's .nex bytes: a maintainer decision with a
   full `selftest.py --stamp`. Check NEXLOAD's reset list first (ped7g NEXLOAD2 source).
27. Alt ROM image 0 (the game selects ROM 0 in play; Target Renegade fills image 0 from ROM 0 in
   write mode): not confirmed on hardware; nor whether the Next decodes OUT (0x1FFD) as 7FFD in 128K
   timing (LEARNINGS 1.2). The ROM 0 bytes a game reads come from the Next's ROM 0, not the Sinclair
   128 ROM 0 the RZX model uses (Target Renegade: 9 bytes of sound data).
28. Copper facts to confirm before an engine relies on the copper: a WAIT for a LINE already passed
   holds the rest of the list until the next frame (inferred from guide r3; an h passed on the
   CURRENT line does not wait - hardware-tested, TECHNIQUES "Hardware ground truth"); $64 = 33 aligns
   copper line 0 with the top of 320x256 Layer 2 (a developer's note and the register text say 32:
   ULA row 0 = line 32, line 0 = first tilemap / sprite row - test both); with $64 = 0 a WAIT for a line the mode lacks (311 at 60 Hz) never fires (TECHNIQUES
   "Raster numbering": the freeze trap).
   How to test any of these: tools/hwtests/README.md (one test .nex per question, a results table in
   fixed RAM, one coloured block per test; Dean photographs the board, MAME runs the same file).
38. NEXLOAD overwrites the 48K printer buffer (0x5B00-0x5BFF: NextZXOS paging routines + system
   variables) after loading bank 5 (Match Day, hardware 2026-10-20: icons and team names lost, plain
   build too). Fixed per game by z80tonex `keep_printer_buffer` (opt-in, so no other output changed).
   Other 48K references with non-zero bytes there, untested for this: dizzy1 (90 bytes; runs "perfect"
   on hardware - check what it keeps there), wally / wally2 (26), jetpac (12), lode_runner (4). Turning
   it on changes their MD5s: maintainers decide per game (rebuild + re-verify).

Designs not built yet (use when a game needs them)
29. Live A/B switch: a key that swaps every hook site between JP hook and the saved original bytes
   (and sprites / Layer 2 off) - a one-file hardware A/B instead of two builds. Needs RAM patch
   sites, the key read where the game reads keys, and verify proof that "off" equals the original.
30. Layer 2 written straight from alt-ROM hooks via 0x123B WRITE-only mapping (TECHNIQUES "WRITE-only
   mapping"): no page mapping in the plot hooks. Proven over RAM in slots 0/1, not over the ALT ROM.
   Prove first: (a) CSpect, then hardware, that write-mapping wins over $8C at 0x0000-0x3FFF while
   reads stay on the ROM image; (b) nextboot / verify model it; (c) the hook turns it off before any EI.
31. zxnDMA re-arm per pattern (5 OUTs, ~87 T; TECHNIQUES "zxnDMA"): measure midres / renegade commits
   with it against today's OUTI / OTIR loops, where the source pattern is linear in memory.
32. Per-cell depth with no masking (TECHNIQUES "Sprites BETWEEN the ULA and the tilemap"): $15 layer
   mode %110 + $68 bits 6:5 = %01 should put ULA + tilemap in front of the sprites, and tile attribute
   bit 0 single tiles behind them. Confirm in CSpect, then hardware, against core nextreg.txt.
33. Hook page with interrupts on when the game's ISR touches every slot (no free slot for midres'
   slot-5 trick): NextMasterSystem's trampoline (TECHNIQUES) - the IM2 entry maps the game's page back
   under the ISR and puts a trampoline in its return slot that maps the hook page again. Needs: verify
   models an interrupt mid-hook (A1 blind spot); the game's ISR must not read its own return address.
34. Hardware IM2 mode for interrupts-on games ($C0 bit 0; TECHNIQUES 2.6 "Held interrupts"):
   the Next holds an interrupt until RETI acknowledges it, so hooks could run with interrupts OFF (no
   per-instruction interrupt-safety rule - Commando, midres). PROVEN on a board (2026-10-20,
   tools/hwtests/im2hold v2): vector = I*256 + $16 for the ULA interrupt; an interrupt during a
   3-frame DI is taken at the EI; a RETI trampoline into an EI;RET handler and a uniform 257-byte
   table both give one run per frame. RULE: a handler ending in plain RET does NOT acknowledge, and
   the unacknowledged interrupt BLOCKS every later one - so every game handler is entered through the
   RETI trampoline unless proven to end with RETI. Open: the engine design (vector page, the game's
   LD A,I / LD I,A, interrupt timing vs the original) and MAME / CSpect agreement with the board.
35. `inspect` misreports an IM 2 vector table in ROM (Cyclone: I = 0x3A, vector 0x3AFF/0x3B00 = FF FF
   in the 48K ROM -> 0xFFFF, a JR into RAM): it reads the vector from zeroed ROM and warns "IM 2 handler
   in ROM (0x0000)". It should read the 48K ROM (build.rom48) and name the RAM target. Engines that use
   the alt ROM must then keep those vector bytes (Cyclone: hooks end below 0x3AFF; Incredible Shrinking
   Fireman: I = 0x39, vector 0x39FF/0x3A00, hooks in two blocks around it).
   Generalise it (2026-10-22): IM 2 reads the vector word at I*256 + bus byte, and games with I in
   0x39-0x3C rely on the bus reading $FF and the 48K ROM's $FF block (0x386E-0x3CFF) giving 0xFFFF -
   the same block every alt-ROM engine fills with hooks (Cyclone 0x3AFF, Match Day 0x3BFF handle it
   per engine). A shared check belongs in nextboot.check / the alt ROM build: IM 2 and I*256+0xFF in
   the altrom range -> refuse unless both vector bytes are unchanged or deliberately redirected.
   Unconfirmed: that the Next's bus reads $FF in pulse mode on every core (we rely on it).
36. `inspect` should warn when CODE runs in the printer buffer (0x5B00-0x5BFF): NEXLOAD overwrites it,
   so the build needs keep_printer_buffer (Match Day: data; Cyclone: the main loop - its first plain
   build, without it, would not run on hardware). An access scan (`scan --range 0x5B00-0x5BFF`) shows it.
37. Beeper sound independent of CPU speed (idea, 2026-10-22; TECHNIQUES 2.6, sample sound by copper):
   timed beeper loops play 8x fast at 28 MHz (Match Day isr_w; LEARNINGS 2.1f), so today any code
   that beeps must stay at 3.5 MHz. Instead a hook on the game's OUT ($FE) could log (beeper bit,
   game T-time counted at 3.5 MHz rates) and the copper replay it through a DAC NextReg at ~11 kHz
   on the next frame: the game's sound at the original timing whatever speed the code runs at
   (one frame late; 11 kHz quantises fast tones). Needs: a T clock in the hooks (or the game loop's
   own count), the DAC enable (NextReg $08 bit 3), a hardware listen test. Not tried.
38. selftest.push_access() treats a git WORKTREE as "no push access": it tests isdir(HERE/.git), and in
   a worktree .git is a file. LEARNINGS 2.6 says to run stamping / --affected runs in a worktree, so
   they stop with exit 3 there (Fireman, 2026-10-25; ran with NEXCLASH_MAINTAINER=1). Fix: test
   os.path.exists, or ask `git rev-parse --git-dir`; add a selftest --tools case with a worktree.
39. `isr` should list, for every routine the ISR's call tree reaches, the main-code callers too, and
   the original's slack at each (T from the main-code call's return to the next interrupt, over an
   RZX): a routine on both lists with little slack is a nesting risk once hooks add cost (LEARNINGS
   2.1f; Incredible Shrinking Fireman found it only on hardware, 2026-10-25).
41. survey: compare the RZX's embedded snapshot with the delivered .z80 and WARN when they differ
   (Cauldron 2026-10-26: 11,283 bytes, the code shifted; found only at tool call ~60, after a stale
   disassembly). Both start states are at hand in survey.analyse.
42. inspect: the "loader snapshot" WARNING fires when PC is in ROM only because an IM 1 interrupt was
   just taken with the BASIC loader still in memory (Cauldron: PC 0x0038, stacked return 0x613E =
   game code). Check the stacked return address before warning; add a tools_check case.
43. coloursheet.write crashes (max() of an empty sequence) on a figure with no opaque pixel (Cauldron
   2026-10-27: image D710 3 x 24 is all zero bytes; the engine now leaves such images off). Skip them
   in write / choose and report them; add a tools_check case.
44. sjasm.py on Windows: no binary, no make. A local 1.24.0 copied to the cache as `sjasmplus`
   (+ .exe) gave --check --all IDENTICAL (2026-10-31); accept a cached .exe.

### C3b. Two verification levels (agreed with Dean 2026-09-29; how to run them: PLAYBOOK 6)
- ITERATE (per change): original bytes at every site, boot check, unit tests (with negative
  controls), `--quick N` on one RZX (N reaching every hook's first call: start at 2000).
- RELEASE (once per delivered .nex): every RZX in full, one job at a time, boot check, unit tests -
  `selftest.py --game <record> --verify --stamp`, which also stamps the evidence record.
Logic must be exact at both levels; visuals "good enough" where Dean agreed (games/ list them).

### C4. Shared analysis commands (any game; Dean 2026-10-12: harness stays per engine)
`nexclash.py inspect | scan | isr | cost | preview` (modules snapinfo, memscan, isrinfo, drawcost, preview on the
runner simrun.py) and `python -m nexclash.survey` (stage 0: all of them in one pass + plain build,
boot, engine, plot routines, coverage; not in nexclash.py because every game's evidence depends on
nexclash.py and a new subcommand would put them all up for re-verification). Game-independent: game
facts come in as arguments (addresses, ranges, keys).
- survey: inspect + engine detectors + the plain conversion as `convert` does it (autosave snapshots
  stripped first: analyse() desyncs on them) + the 48K boot check, then ONE pass with memscan.Scanner,
  isrinfo.IsrTracker and survey.PlotTracker (shadow call stack: each screen write -> the innermost
  CALL or interrupt running; calls, callers, T per call from its own T count), then a preview pass for
  the top routines. Writes <game>_survey/survey.md (+ .json, preview.png, the plain .nex). Its
  coverage line is the byte scan of C2 #11 only (CALL / JP nn to each top routine, rated by whether
  code ran within 24 bytes), not the recursive static pass.
- simrun: plays an RZX (autosave snapshots stripped to a temp copy) or free-runs a snapshot with
  a key schedule ("5-14:SPACE; 30-:N", K:LEFT... = Kempston); hooks before/after every
  instruction, on every memory access, interrupt and frame. 128K memory hooks swap the Memory
  object's class (rzxplay tests isinstance(memory, Memory)); 48K memory is wrapped.
- inspect: machine, 7FFD/ROM, where PC is (ROM routine names), BASIC listing + USR targets, IM /
  I / vector chain, stack; warnings (loader, 128K BASIC = ROM 0, ROM 0 selected).
- scan: read / write / exec per address (128K: C000-FFFF per bank), untouched spans, first
  access PC, write-first spans; `--after PC` counts from a PC on (e.g. the game entry).
- isr: per accepted interrupt until it returns: instructions run, IX/IY reads of the
  INTERRUPTED value (PUSH/POP-aware), stack depth and stack switches, ports, modes seen.
- scan --writers: per --range, the instructions that write it and that read it as data (counts) -
  who draws into a screen / back buffer and whether game logic reads it back. The first line lists
  the top 10 by count; the `writers+` / `readers+` line lists the rest joined into routine spans
  (PCs within 8 bytes). Read it: an unrolled copy loop fills the whole top 10 and hides every
  plotter (Everyone's a Wally, 2026-10-14: the top 10 were all LDIs of 47653).
- isr: also "Slots": which 8K slots the handler reads / writes / runs; slots 2-5 it never touches
  may hold a hook RAM page with interrupts on (LEARNINGS 1.3).
- preview: contact sheet of the screen at chosen frames (PLAYBOOK 3c; with --rzx, --every N needs
  --stop as well, or the run ends after 500 frames); --plot ENTRY colours what each
  plot routine draws per caller (= per figure kind), --buffer ADDR:STRIDE:LINES shows a back buffer
  next to the screen; prints each group's calls, bytes and x/y range. Colours = the last plot that
  wrote a byte, so a shot taken between a background copy and the plots shows no figures: pick
  other frames. True pixels of masked figures (plot run on a 0x00 and a 0xFF buffer) stay
  engine-specific (midres.truth).
- cost: T per call of a routine entered by CALL (interrupt time excluded), calls per frame,
  share of frame time, per register value at entry. A routine reached by JP has no return
  address on the stack: time its caller instead.
Improving them is welcome: keep existing report lines and arguments (add, don't rename), add a
golden check for the new behaviour to selftest.py tools_check, run `python selftest.py --tools`.
