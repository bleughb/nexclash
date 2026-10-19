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
- Setup: CLAUDE.md. `pip install -r requirements.txt --break-system-packages` (SkoolKit + Pillow; a
  fresh cloud container has neither). sjasmplus is pinned and bundled
  (tools/sjasmplus: static 1.24.0 for Linux x86-64, else built from the pinned tag into
  ~/.cache/nexclash). Assemble hooks ONLY with `python tools/asm2profile.py <engine>`; it refuses
  any other version. `--check <profile>` proves a profile = its source (each hook game's record runs it
  with every rebuild); `--check --all` is for assembler upgrades (tools/sjasmplus/README.md).
- Background jobs, the 10-minute tool-call cap, worktrees for stamping runs: LEARNINGS 2.6 (the one
  place for these rules).
- Shell heredocs that write docs: quote the delimiter (`<<'EOF'`) or the shell runs every
  backticked example in the text (2026-10-11: it cloned sjasmplus into the repo and ran a pkill).
- Next dev guide r3 (Tomaz Kragelj): github.com/tomaz/zx-next-dev-guide (PDF; `pdftotext` it, then grep).
  Maintainers also keep a text copy in the private reference repo.
- SkoolKit: `Snapshot.get(f).memory[0:65536]` - slices need an explicit stop.
- SkoolKit Disassembler (for flagged routines): `Disassembler(mem_list, cfg)` with cfg =
  SimpleNamespace(defb_size=8, defm_size=65, defw_size=1, handle_rst=False, wrap=False, opcodes='',
  asm_hex=False, asm_lower=False, imaker=lambda a,o,b: SimpleNamespace(address=a, operation=o, bytes=b));
  `d.disassemble(a, a+1, 'd')[0]`. Never name a scratch script dis.py (shadows stdlib, circular import).
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
- `pkill -f PATTERN` (and a `kill $(pgrep -f PATTERN)`) also kills the tool's own shell when
  PATTERN is in its command line: list with `pgrep -fa` in one command, kill the PID in the next.
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
   3.01.09; src/zxnext.vhd, ports.txt). Official repo (GitLab, blocked in the sandbox):
   gitlab.com/SpectrumNext/ZX_Spectrum_Next_FPGA. Dean's core may be newer - note the version.
   Register reference: tbblue docs/extra-hw/io-port-system/registers.txt (nextreg list).
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
   book incl. KevB's copper/display timing tables per machine and video mode; demo/ = small sprite,
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
line interrupt): researched 2026-10-19, documented, none used yet - LEARNINGS 1.5 (with the
reasons each can break a game) and NEXT_REGISTERS "Not used yet". Resolved 2026-09-29 from docs/VHDL: per-line sprite limit, locked 7FFD vs MMU, NextReg
$08 bit 7 semantics, 48K timing vs 7FFD decoding (see A1, LEARNINGS 1.2-1.4).

### A1. What we rely on
| Item | Setting / fact |
|---|---|
| CPU speed | NextReg $07 = 0 (3.5 MHz) |
| Video | 50Hz forced (NextReg $05) unless `--allow-60hz` (nexclash.py convert / auto / patch / new / verify: sets z80tonex.ALLOW_60HZ, every build path; outputs then differ from the verified MD5s) |
| 48K fidelity | NextReg $03 = 48K timing (written after the legacy paging writes; VHDL: this does NOT stop 7FFD/1FFD decoding - with 48K/128K timing 7FFD decodes as A15=0, A1:0=01, A14 ignored; timing only changes contention); NextReg $08 contention on; 7FFD lock via the tail's own 7FFD write (bit 5) |
| DivMMC | auto-paging off (NextReg $06 bit 4 cleared by the stub, z80tonex.build_stub; not $0A). Yet Commando 541e34e2, with hook code at 0x3D00-0x3DFF, crashed at its first figure on hardware and in CSpect, and d601385e (the same code moved out of that range; only tables there) runs. PROBABLE cause: the DivMMC/TR-DOS automap on an instruction fetch at 0x3Dxx is not switched off by $06 bit 4 on current cores (entry points may be set by NextRegs $B8-$BB) - NOT confirmed (C2 #14). Rule regardless: never put code at 0x3D00-0x3DFF; data there worked |
| Simulator blind spots | The toolkit's simulator does not model: DivMMC (automap traps, see above), an interrupt arriving in the middle of a hook (so the game's ISR never sees hook register/stack state - covered only by the per-instruction interrupt-safety check), the raster (tearing, overruns), real-machine speed (28 MHz wait states, contention), CSpect differences, the VIDEO output of Layer 2 (nextboot / verify model its bank register, port 0x123B, palette writes and pixel pages, not what the screen shows: palette entry 0xE3 as transparency, layer order; Dizzy 1, 2026-10-14, hardware to confirm), beam-racing (multicolour) timing - code that rewrites attributes per scanline works only at the original T-state count and contention (LEARNINGS 1.1), the Next's own flag results after block I/O instructions (OTIR/OUTI/INIR...: only ZF is reliable on the Next; the simulator computes real-Z80 flags - LEARNINGS 1.1). Anything in this list needs a static/invariant check or a hardware test | Per-event checks (one hook call, original vs patched) do not see a figure that disappears because a later hook call of the same object reuses its sprites (Jetpac's stacked rocket, 2026-10-20): add a whole-routine figure check.
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

### C2. Known limits (the backlog)
1. Treasure Island game snapshot: auto-recorder finds no start/inputs (needs --start/--keys or user RZX).
2. Explorer reach is LOW: honest room counts are 1-4 real rooms in 6,000-60,000 frames on the
   Dizzy games (before the fix, moving objects made fake "rooms" - Dizzy V bubbles screen
   trapped it; fixed by similarity matching). Next step: goal-directed exploration for the TID
   engine using the player X/Y variables from the plot entry block (walk to screen edges, jump
   when X stops changing), and merge duplicate keys by player-position effect, not raw RAM.
   Until then, a short human RZX gives better coverage; puzzle-gated content always needs one.
3. Generic builder = TID engine only; XOR engine and virtual read only in dedicated builders.
4. classify() assumes "overwrite" for unrecognised writers - should flag for review (Dizzy V's
   nibble writers matched the keep-mask rule; not re-proven generally).
5. Wanted: engine registry (each engine registers identify/auto instead of a dispatch block in
   nexclash.py) + behaviour flags in profiles. Do it once reference/ holds every game (selftest).
6. 128K: plain conversion runs on hardware (Crystal Kingdom Dizzy); 128K sprite engines: Rainbow
   Islands, Everyone's a Wally and Commando (all run on hardware), Midnight Resistance (runs, 2026-10-13).
   analyse/recorder are 48K-only: `convert --rzx` with a 128K RZX stops with "N port reading(s)
   left for frame 0" (analyse wraps 48K memory; simrun-based scan/isr/cost work).
   Dizzy V / Magicland / Dizzy 6 sprite builds: hardware untested.
7. Dizzy V: works in the toolkit and is verified; hardware to confirm: dialogue text (font-page
   fix) and slot-1 surviving a game that writes 7FFD every interrupt (see A1 "7FFD lock").

8. Dizzy 6: mirror path proven only by the unit selftest - wants an RZX through the mirror
   room. evidence.json is not updated for 'tid_mirror' (_auto_dizzy6 skips _learn). In selftest
   since 2026-10-13 (docs/records/dizzy6.json: try1.rzx verify, ~3 min).
   Hardware: first sprite build to test on the Next alongside Magicland.
9. `altrom` strategy: DONE 2026-09-28 (default; `--strategy printer|slot1|altrom`). Dizzy V
   verified (auto RZX) + boot-simulated -> hardware test next (Dizzy_V_sprites.nex 1f33c467...).
   Fantasy World / Magicland altrom builds baselined 2026-10-11 (now in docs/records).
   Dizzy 6 stays slot1 (possible later:
   hooks in the alt ROM + plotter copy in a slot-0 RAM page, IM2 game - needs the relocation
   moved and a re-verify). Later: tail inside the alt ROM (same address in both images -> no game
   RAM needed; needs a hardware test) and alt image 0 for 128K games.
10. selftest was broken after the Dizzy 6 session (fixed 2026-09-28): identify() had lost its
   Dizzy V dispatch, and dizzy5 analysis did not resync per RZX segment (the recorder now writes
   16 segments). Keep identify5 called from identify().
   (closed; kept as a warning)
11. No hook speed budget and no profiler: Commando's and Midnight Resistance's hook costs were
   measured with scratch scripts (T-states per plot / commit from the pair runs, original vs
   patched; the simulator ignores the 28 MHz turbo). Wanted: an `auto` line with hook T-states per
   call (median / max) and a documented budget per game frame. Smash TV's `auto` has a per-engine
   `Speed` line (T per game frame, original vs patched, 28 MHz parts / 8, from the verifier's pair
   runs) - the pattern to lift into a shared helper. It matters most for games without frame sync,
   where hook cost changes the game's speed (LEARNINGS 2.1).
13. Done 2026-10-13: `isr` Slots line, `scan --writers`, `preview` (from the Midnight Resistance
   scratch scripts). Still scratch-only: hook cost per game frame (#11).
14. Every edit to nexclash.py (records ALWAYS) makes every game's representative due for
   re-verification (hours), even one that only adds an analysis option. Moving the analysis
   commands' CLI out of nexclash.py, or the engine registry (#5), would stop that.
12. Boot-path RAM check (entry -> menu, not in any RZX): the checked range must be the WHOLE hook
   RAM of the engine. Tool: `scan --frames N --keys K --after ENTRY --range ...` (C4); Commando
   done 2026-10-12. Not yet automatic in `auto`.
13. Wanted, from the Commando post-mortem (PLAYBOOK 3b / 6b):
   a. Preview renderer: still frames / a GIF of ULA + sprites (the World's sprite state composed
      over the screen) at chosen RZX frames, for design approval before building.
   b. Interrupt injection: in verify / unit tests, run the game's ISR at random hook
      instructions and require identical results (would have caught the IY bug directly; the
      per-instruction invariant check is the current stand-in).
   c. Hook speed report (see 11): T-states per hook call, median / max, against the budget.
      (The original's side exists: `cost`, C4.)
   d. Emulator smoke test: boot the .nex headless in a Next emulator for ~30 s (would have caught
      the ROM 0 and 0x3D00 crashes); feasibility in the sandbox (CSpect needs .NET/mono) not yet
      checked; ZEsarUX (open source, GitHub) is the candidate.
15. Dependency smell (records.py deps): nextboot.py imports dizzy6._rw_simulator, so every game
   depends on dizzy6.py and a Dizzy 6 change counts as shared (rebuild all + representatives).
   Move _rw_simulator into a shared module.
16. Treasure Island (dedicated builder) is not re-verified differentially by any tool: its sprite
   build was verified during development; selftest re-proves only the plain tail (access scan) and
   the boot (record: verify.differential false). Port it to a verify path to close it. Dizzy 1:
   closed 2026-10-14 (engine dizzy1: `auto --rzx` runs the full differential verify + unit tests,
   selftest's verify recipe repeats it).
14. Confirm the 0x3D00 cause (A1): a test build with one harmless routine at 0x3D00 (emulator with
   DivMMC, or hardware); then record the confirmed reason in A1 / LEARNINGS 1.4.
17. Colour sheets are part of every game from Midnight Resistance on (PLAYBOOK 3b / 5 / 6). The
   sheet side is shared (nexclash/coloursheet.py); each engine still writes its own parts
   (capture) and its own per-pixel colour map in the sprite builder (midres: sheet_part, asm
   `ovl`). Games converted before Midnight Resistance have neither; add them when one is reworked.
   Golden check: `selftest.py --tools` (coloursheet on synthetic parts, incl. the opt-in transparent
   painting `read(..., clear=True)`: 4th map element = transparent bit mask; Dizzy 1 uses it). Not done: a
   `nexclash.py sheet` command dispatching to the engine (today `python -m nexclash.<engine> sheet`).
18. Done (2026-10-19): z80tonex.choose_tail_addr refuses a tail ending above 0xC000 for 48K too (a 48K
   tail there vanishes when the tail's OUT 0x7FFD maps bank 0 back: El Capitan Trueno);
   nextboot.check still catches it ('boot did not reach PC ...').
19. nextboot.check models the alt ROM with rom48(), but the Next copies the system ROM3 (NextZXOS,
   data at 0x3B00-0x3CFF): check against the real ROM3, or make the builder copy every ROM area a
   patch relies on (LEARNINGS 1.3).
20. A shared fast mode for frame-level questions (C simulator + RZXTracer.next_frame, seconds per
   RZX) next to the per-instruction simrun commands (LEARNINGS 2.3).
21. `nexclash.py patch` (the users' command) writes the plain .nex WITHOUT nextboot.check: El Capitan
   Trueno's first plain build crashed at once for its user (48K tail above 0xC000, #18); the boot
   sim says so in a second. Run it in `patch` and refuse or warn.
22. `patch --rzx` with a long recording (Trueno: 18 min, 53,542 frames) printed nothing within the
   contributor's time limit: add progress output (frames done / total) to the long passes.
23. A key log from a recording (contributor's rzx_keys.py, in their archive: keys held per frame
   range from the port 0xFE reads) finds when the user did something - worth an `rzx keys` command.
24. nexpatch (contributor's proposal, in their archive):
   a .nex delivered as an HTML page that rebuilds it from the user's own .z80 (CRC32 match, own
   bytes ChaCha20-encrypted under SHA-256 of the .z80). Checked 2026-10-14: `apply` and the page's
   own JS give the four Trueno builds byte-identical, a changed .z80 is refused; no network code.
   Maintainers' decision pending (public tool or not). Its AI_GUIDE points to a nexpatch/CLAUDE.md
   that is not in the archive.
25. [MAME] A scripted MAME run (put the .nex in the SD image, load, snapshot) next to run_cspect.bat
   (LEARNINGS 2.7).
26. State a previous program may leave behind (2026-10-19, documented, not seen on hardware): the
   stub resets speed, video, DivMMC, sprites, $C0, 0x123B, and the NEX header asks NEXLOAD to
   reset NextRegs (byte 134 = 0: "reset machine state" - wiki NEX_file_format lists no registers),
   so what that reset covers is not confirmed. Not written by the stub, and each would break games
   if left non-default: a running copper ($62 mode; MOVEs to any NextReg 0x01-0x7F every frame); the
   line offset $64 (core 3.1.5+; shifts $1E/$1F, which the Rainbow raster wait reads); ULA interrupt
   off ($22 bit 2 or $C4 bit 0: stops every IM1/IM2 game) or line interrupt on ($22 bit 1);
   ULA output off ($68 bit 7), ULA scroll ($26/$27) and clip ($1A); Layer 2 resolution ($70), scroll
   ($16/$17/$71) and clip ($18) - Dizzy 1 sets only $12; palette state ($43 active palettes,
   ULANext bit 0, $14 transparency, $4A). Also left ON: the F3 (50/60 Hz) and F8 (CPU speed) keys
   ($06 bits 5/7), so a player can undo the forced 50 Hz or change the speed the hooks and the
   Rainbow frame limiter assume. Cheap guard: NEXTREG $62,0 / $64,0 / $22,0 / $C4 bit 0 set (soft reset $83 per
   nextreg.txt, where bit 1 = line interrupt; the guide says bit 1 resets to 0 - unresolved) / $68,0 /
   $26,0 / $27,0 + $06 AND $5F in the stub (Dizzy 1: its Layer 2 registers in its own setup) -
   changes every game's .nex bytes, so it is a maintainer decision with a full
   `selftest.py --stamp`. Check NEXLOAD's reset list first (ped7g NEXLOAD2 source).
27. Alt ROM image 0 (the game selects ROM 0 in play; Target Renegade's setup fills image 0 from ROM 0
   in write mode): not yet confirmed on hardware; also whether the Next decodes OUT (0x1FFD) as 7FFD in
   128K timing (LEARNINGS 1.2). The ROM 0 bytes a game reads come from the Next's ROM 0, not the
   Sinclair 128 ROM 0 the RZX model uses (Target Renegade: 9 bytes of sound data).
28. Live A/B switch (idea from Mercenary Next, LEARNINGS 1.5): a key that swaps every hook site
   between JP hook and the saved original bytes (and sprites/Layer 2 off) would give Dean a
   one-file hardware A/B instead of two builds (Rainbow's speed tests). Needs RAM patch sites,
   the toggle key read where the game reads keys, and verify proof that "off" equals the original;
   not built.
29. `auto` on an unknown engine made Jetpac's synthetic _auto.rzx (6410 frames), but `scan` / `preview`
   on it stop with "Port readings exhausted for frame 532" (2026-10-19): the recorder and the replay
   disagree on one frame's port reads. Not investigated; Jetpac used free runs (--frames/--keys).

### C3. Working rules (token budget)
Summaries <= 40 lines; disassemble only routines the analysis flags; one simulator pass
per question; long jobs in background + poll; verify original bytes at every patch site;
keep every record's MD5s reproduced (selftest); commit changed files to the repo; terse replies.

### C3b. Two verification levels (agreed with Dean 2026-09-29)
- ITERATE (per change): original bytes at every site, boot check, unit tests (with negative
  controls), `--quick N` on one RZX (a few hundred frames for a first check, 2000 before handing a
  build over; Rainbow 2000 frames ~13-15 min).
- RELEASE (once per delivered .nex): every RZX in full, one job at a time (1 CPU), boot check,
  unit tests; record the MD5s in docs/VERIFICATION.md.
Logic must be exact at both levels; visuals "good enough" where Dean agreed (games/ list them).

### C4. Shared analysis commands (any game; Dean 2026-10-12: harness stays per engine)
`nexclash.py inspect | scan | isr | cost | preview` (modules snapinfo, memscan, isrinfo, drawcost, preview on the
runner simrun.py). Game-independent: game facts come in as arguments (addresses, ranges, keys).
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
- preview: contact sheet of the screen at chosen frames (PLAYBOOK 3b; with --rzx, --every N needs
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
