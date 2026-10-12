# Briefing - settled facts: Spectrum Next platform and the nexclash toolkit

Everything here was established and verified (differential tests against real recordings;
outputs byte-identical). Treat it as settled. Re-open a fact only if `selftest.py` fails or Dean
reports a hardware problem. Read code only in the modules you are about to change.
Facts about one game: games/<game>.md. General lessons: docs/LEARNINGS.md. Status: STATUS.md.

Layers - never mix their facts:
  PART A  Spectrum Next platform (hardware + .nex format): true for every game.
  PART B  Original games: engine-independent rules only (per-game facts: games/).
  PART C  The nexclash toolkit (our Python + our Z80 patch code).

## 0. Environment (do not rediscover)
- Setup: CLAUDE.md. `pip install skoolkit --break-system-packages`; sjasmplus only for .asm edits:
  `git clone https://github.com/z00m128/sjasmplus && cd sjasmplus && make USE_LUA=0` -> `--zxnext`
  (clone it OUTSIDE the repo).
- Background jobs: `setsid nohup python X > log 2>&1 < /dev/null &` then poll (a plain
  `nohup ... &` dies when the tool call returns). One CPU: run long jobs one at a time. A tool
  call is capped at 10 minutes: poll with sleeps under that.
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
  $NEXCLASH_REFERENCE or ../specnext/reference and recognises them by MD5 (INPUTS / RZX_GAMES).
- `pkill -f PATTERN` also kills the tool's own shell when PATTERN is in its command line: use
  pgrep, then kill by PID.
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
   Read it with the chat's web_fetch tool (the sandbox network blocks the wiki, so scripts
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
Rules: a new fact from the guide or wiki is "documented", not "verified", until a boot sim, RZX
test or hardware test backs it; record its source (page name) where you file it. Known gaps to
look up first: copper / DMA as faster alternatives for sprite attribute or pattern uploads (not
used yet). Resolved 2026-09-29 from docs/VHDL: per-line sprite limit, locked 7FFD vs MMU, NextReg
$08 bit 7 semantics, 48K timing vs 7FFD decoding (see A1, LEARNINGS 1.2-1.4).

### A1. What we rely on
| Item | Setting / fact |
|---|---|
| CPU speed | NextReg $07 = 0 (3.5 MHz) |
| Video | 50Hz forced (NextReg $05) unless `--allow-60hz` |
| 48K fidelity | NextReg $03 = 48K timing (written after the legacy paging writes; VHDL: this does NOT stop 7FFD/1FFD decoding - with 48K/128K timing 7FFD decodes as A15=0, A1:0=01, A14 ignored; timing only changes contention); NextReg $08 contention on; 7FFD lock via the tail's own 7FFD write (bit 5) |
| DivMMC | auto-paging off (NextReg $06 bit 4 cleared by the stub; not $0A). This does NOT make 0x3D00-0x3DFF safe: an instruction fetch there still crashed Commando 541e34e2 on hardware and in CSpect (DivMMC/TR-DOS automap trap) - never put code there; data is fine |
| Simulator blind spots | The toolkit's simulator does not model: DivMMC (automap traps, see above), an interrupt arriving in the middle of a hook (so the game's ISR never sees hook register/stack state - covered only by the per-instruction interrupt-safety check), the raster (tearing, overruns), real-machine speed (28 MHz wait states, contention), CSpect differences. Anything in this list needs a static/invariant check or a hardware test |
| MMU | slots 0-7 = NextReg $50-$57, 8K pages; 16K bank n = pages 2n, 2n+1; $FF in slot 0/1 = ROM |
| Legacy paging | legacy and MMU paging are interchangeable, most recent change wins (guide 3.2.6): an UNLOCKED 7FFD/1FFD write remaps slot 0/1 (ROM) and 6/7 - so the tail maps slot-1 RAM AFTER its own paging writes |
| 7FFD lock | The lock IS 7FFD bit 5 (the 48K tail writes 7FFD=$30). NextReg $08 bit 7: write 1 = clear the lock; write 0 = no effect (does NOT lock); read 1 = unlocked. VHDL (core 3.01.09): while locked, writes to 7FFD, 1FFD and DFFD are ignored and trigger NO MMU remap (port_memory_change needs 'not port_7ffd_locked'), so a RAM slot-1 page survives a locked game's 7FFD writes (documented from source; hardware still to confirm for Dizzy 6). UNLOCKED writes to 7FFD/DFFD/1FFD/EFF7 set MMU0/1=$FF (ROM) and MMU6/7 to the selected bank (ports.txt). At NEX launch paging is UNLOCKED (all hardware-tested builds page with legacy writes without unlocking); the altrom stub still sets $08 bit 7 before its own 1FFD/7FFD writes. |
| Alt ROM ($8C) | Whole 0x2000-0x3FFF of image 1 usable when the game never reads that ROM range (Commando d601385e: data + code from 0x2000, runs on hardware 2026-10-12; no code at 0x3D00-0x3DFF). $8C alt ROM verified on hardware 2026-09-27: write-mode copy, read-only, 7FFD b4 switch, MMU $FF, IM1, font — all PASS; $8C=00 at NEX launch. Bits: 7 enable, 6 visible only during writes (write mode), 5/4 lock ROM1/ROM0; low nibble = same after soft reset (leave 0). 32K = two 16K images (ROM0 128K, ROM1 48K), selected by the normal ROM select: with 1FFD=$04, 7FFD bit 4 = 0/1 selects ROM2/ROM3 = image 0/1 (hardware test used exactly this). Write mode: reads come from the real ROM, so LDIR 0000->0000 copies the selected ROM into its image. MMU0/1 = $FF shows the alt ROM. |
| Hardware sprites | 16x16, 4-bit patterns (128 bytes each), attributes via NextReg $34 (select) then $35 X low, $36 Y, $37 = bit0 X8, bit3 X-mirror, bit2 Y-mirror, $38/$39 pattern+visible; sprites on NextReg $15 bit 0; coords = screen + 32. A mirrored 2x2 box needs left/right quads swapped, and a frame narrower than 32 px an x offset (Dizzy V: -8) |
| Setup template (0xD000) | sprites off; uploads N x 256 bytes of patterns from bank 11 via port 0x5B; sprite palette 0 = 0, 1 = 0 (black), 2 = $B6 (white, the player colour); NextReg $4B = 0; sprites 0-3 cleared. Stub leaves $15 = 0; hooks show with NEXTREG $15,1 |
| User register | NextReg $7F: free 8-bit storage; write with NEXTREG, read via ports 243B (select) / 253B (data) |
| Interrupts | IM2 games keep working; hooks that page slot 0 must DI (IM1 vector 0x38 is in slot 0) |
| NMOS quirk | `LD A,I` P/V reads 0 if an interrupt is accepted during it: read twice (`ld a,i / jp pe,ok / ld a,i`) |

### A2. .nex conversion (nexclash/z80tonex.py) - how every file starts
- NEX V1.2 header (verified against ped7g NEXLOAD2). Game RAM = banks 5,2,0 (48K).
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
- 128K: the tail must end below 0xC000 (its own 7FFD write remaps C000-FFFF); z80tonex refuses it.
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
| altrom (DEFAULT since 2026-09-28) | alt ROM image 1 = exact copy of ROM3 (48K) + slot1 hook code + frame table + register block (TID: 0x386E-, all $FF in the 48K ROM, must end < 0x3D00; Dizzy V: 0x3800-; NO code may ever sit in 0x3D00-0x3DFF - DivMMC automap trap on fetch; Commando: data there, code also 0x3F00+); stub fills it in write mode, tail sets $8C=$80; RAM page 24 in bank 12 is only the copy source | NextReg $7F (Dizzy V: none) | direct calls, no paging, no DI; game may read ROM/font; writes ignored; survives 7FFD |
Choice rule (build.choose_tid_strategy, returns strategy/reason/tail): altrom if no recording
reads 0x386E-0x3CFF AND (printer buffer free -> tail at 0x5B00, else dead stack >= 54 -> tail
at the low-water mark); else the old rule: printer if 0x5B00 is zero in the snapshot AND never
touched; else slot1 if ROM unused AND dead stack >= 54; else refuse. `--strategy X` checks X only.
Per game: TID engine generic (Fantasy World, Magicland) and Dizzy V -> altrom; dedicated builders
(Treasure Island, Dizzy 1) -> printer only (writable state in 0x5B00); Dizzy 6 -> slot1 only
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
| dizzy_patch.py / dizzy1_patch.py | DizzyPatch / Dizzy1Patch | dedicated builders (TID bubbles; XOR engine) |
| dizzy5.py | identify5, analyse5, patch class, verify5 (+ _converges) | Dizzy V engine (ISR-driven masked sprite); nexclash.py _auto_dizzy5 drives it |
| dizzy6.py | layout, relocated_copy, Dizzy6Patch(prof, mem, tail, undo_size), first_access(rzx, lo, hi), mirror_selftest | 'tid_mirror' (Dizzy 6): TidPatch slot1 + unpatched plotter/eraser copy at 0x2000 for the mirror calls; nexclash.py _auto_dizzy6 drives it (analysis + first-access pass per RZX, tail in undo buffer, verify, 780-case mirror selftest) |
| loader.py | prerun(rzx, test, out_z80) -> (path, frame, pc) | loader-stage snapshots: replay until test(mem) (engine live), finish LDIR, save state. MUST be present |
| nextboot.py | boot(nex, pc), check(nex, z80, patch, tail) | simulated Next boot of a built .nex (MMU, legacy paging, $8C alt ROM, NEXTREG); run by every sprite build (`Boot` line; MISMATCH fails selftest) |
| selftest.py | selftest.py [FOLDER=reference/] [--human] [--no-repro] [--fast] | default (altrom) outputs + `--strategy` reproductions of the old builds (REPRO) + verifications + boot; engine games (Chuckie Egg, Wally, Rainbow, Commando) rebuilt from Dean's RZX and MD5-checked (RZX_GAMES; --fast skips Rainbow ~50 min and Commando ~45 min); games with missing inputs are skipped (exit 2); EXPECTED None = not baselined yet |

Templates: Z80 sources were tramp.asm/hooks.asm/setup.asm (printer) and patch.asm (slot1);
to change them rebuild with sjasmplus and regenerate relocations (assemble twice with each
symbol XOR 0x0101, diff -> offsets). Symbols: PLOTTER ERASER_CONT ERASER_SPSAVE WIPE_CONT
WIPE_IX SOUND_TICK BOX_CONT BOX_VAR. The asm sources are in Dean's earlier zips
(clash-remover-handover.zip tools/builders/), not in the repo - ask Dean if needed.

### C0b. Analysis / verification internals (for writing new engine code)
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
6. 128K: plain conversion runs on hardware (Crystal Kingdom Dizzy); sprite engines exist only for
   Rainbow Islands and Everyone's a Wally (both run on hardware). analyse/recorder are 48K-only.
   Dizzy V / Magicland / Dizzy 6 sprite builds: hardware untested.
7. Dizzy V: works in the toolkit and is verified; hardware to confirm: dialogue text (font-page
   fix) and slot-1 surviving a game that writes 7FFD every interrupt (see A1 "7FFD lock").

8. Dizzy 6: mirror path proven only by the unit selftest - wants an RZX through the mirror
   room. evidence.json is not updated for 'tid_mirror' (_auto_dizzy6 skips _learn). Not in
   selftest (Dizzy6.z80 + try1.rzx not among the reference inputs).
   Hardware: first sprite build to test on the Next alongside Magicland.
9. `altrom` strategy: DONE 2026-09-28 (default; `--strategy printer|slot1|altrom`). Dizzy V
   verified (auto RZX) + boot-simulated -> hardware test next (Dizzy_V_sprites.nex 1f33c467...).
   Fantasy World / Magicland altrom builds NOT yet baselined (reference files not supplied):
   run selftest.py with them and record the NEW MD5s. Dizzy 6 stays slot1 (possible later:
   hooks in the alt ROM + plotter copy in a slot-0 RAM page, IM2 game - needs the relocation
   moved and a re-verify). Later: tail inside the alt ROM (same address in both images -> no game
   RAM needed; needs a hardware test) and alt image 0 for 128K games.
11. No hook speed budget and no profiler: Commando's hook cost was measured with scratch scripts
   (T-states per plot vs the original plot). Wanted: an `auto` line with hook T-states per call
   (median / max) and a documented budget per game frame.
12. Boot-path RAM check (entry -> menu, not in any RZX): the checked range must be the WHOLE hook
   RAM of the engine; Commando's documented boot check covered only to 0x5E1F while the hooks use
   0x5C00-0x60FF (the RZX access scan covers play). Make the boot check use the engine's RAM range.
13. Wanted, from the Commando post-mortem (PLAYBOOK 3b / 6b):
   a. Preview renderer: still frames / a GIF of ULA + sprites (the World's sprite state composed
      over the screen) at chosen RZX frames, for design approval before building.
   b. Interrupt injection: in verify / unit tests, run the game's ISR at random hook
      instructions and require identical results (would have caught the IY bug directly; the
      per-instruction invariant check is the current stand-in).
   c. Hook speed report (see 11): T-states per hook call, median / max, against the budget.
   d. Emulator smoke test: boot the .nex headless in a Next emulator for ~30 s (would have caught
      the ROM 0 and 0x3D00 crashes); feasibility in the sandbox (CSpect needs .NET/mono) not yet
      checked.
10. selftest was broken after the Dizzy 6 session (fixed 2026-09-28): identify() had lost its
   Dizzy V dispatch, and dizzy5 analysis did not resync per RZX segment (the recorder now writes
   16 segments). Keep identify5 called from identify().

### C3. Working rules (token budget)
Summaries <= 40 lines; disassemble only routines the analysis flags; one simulator pass
per question; long jobs in background + poll; verify original bytes at every patch site;
keep selftest byte-identical; commit changed files to the repo; terse replies.

### C3b. Two verification levels (agreed with Dean 2026-09-29)
- ITERATE (per change): original bytes at every site, boot check, unit tests (with negative
  controls), `--quick 2000` on one RZX (Rainbow ~15 min).
- RELEASE (once per delivered .nex): every RZX in full, one job at a time (1 CPU), boot check,
  unit tests; record the MD5s in docs/VERIFICATION.md.
Logic must be exact at both levels; visuals "good enough" where Dean agreed (games/ list them).
