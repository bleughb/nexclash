# Learnings (each one cost a debugging cycle - apply them by default)

Two parts: PART 1 = MACHINE / HARDWARE (Z80, Spectrum 48K/128K, Spectrum Next).
PART 2 = GAMES / SOFTWARE (game engines, our toolkit, host tools, method).
General lessons only: facts about one game live in games/<game>.md, hardware results in STATUS.md.
Each line is settled unless marked otherwise.

# PART 1 - MACHINE / HARDWARE

## 1.1 Z80 CPU
- LD A,I: on NMOS Z80s P/V reads 0 if an interrupt is accepted during it.
  Read twice (`ld a,i / jp pe,ok / ld a,i`). SkoolKit models this.
- A hook inside an ISR must keep the EXX/EX AF,AF' parity: the handler restores by set.

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
- A 128K BASIC loader snapshot cannot run on the Next: 128K BASIC pages ROM 0 (the 128K editor)
  on every statement (Commando: plain = corruption, altrom = crash at the first key; alt image 0 is
  unfilled). Run the loader in SkoolKit (real 128K ROMs) to the game's USR entry, build from there,
  and redo any prompt the loader asks (Commando front end: PAUSE 0 + Y/N + POKE). Check the game
  itself never selects ROM 0 (7FFD bit 4) in the boot simulation and the RZX.

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
  the frame end (set = an interrupt came during the frame). Hooks entered from a ROM stub inside the
  game's handler must not use the game's stack: jump to the hook page's code and jump back.
- Flicker: never hide a figure's sprites at plot entry and show them at exit (hidden for the
  whole call, often across the beam). Keep them visible, build the new image in OTHER pattern
  memory, then rewrite the attributes in one go (Commando).
- Pattern RAM as a content cache: a figure shows far fewer distinct frames than plots (Commando:
  ~110 frames in 4,300 plots). Key each pattern slot by (graphics page, frame offset, lines);
  reuse = attributes only, no build, no upload. Evict only slots no visible sprite references
  (round robin); never share an image that was masked (depth). Negative control: a lookup that
  ignores one key field must fail the pixel check.

# PART 2 - GAMES / SOFTWARE

## 2.1 Game-engine lessons (all engines)
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
- Solid sprites: a body fill from the frame itself (a pixel inside the ink both on its line and
  in its column) reads as a filled figure; objects that hide a figure need their SOLID shape (the
  game's draw mask with holes filled), not their ink, or the figure shows through paper-coloured
  parts.

## 2.2 Memory proofs (analysis method)
- Prove free memory with an access scan over the recording, not by zero-check.
  Also require zero content for persistent code (untouched may just mean
  "room not visited").
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
- analyse.py / recorder / machine.py are 48K-only (recorder: Machine has no ay; analyse desyncs at
  frame 49 on 128K).
- A module restored from an older copy can silently drop another engine's hook (identify() lost
  identify5): selftest after every session that touches shared modules.
- The recorder writes one RZX segment per episode; per-segment state must reset (new Simulator).
  Symptom: refusals a few frames after a segment start (stale screen model, stale drawn flag).
- An uploaded snapshot with the right game but a different MD5 is another snapshot of it
  (dizzy2.z80 = TID title): check selftest INPUTS before assuming references are complete.
- TID altrom hook range 0x386E-0x3A69 (+ register block); the builder refuses a range that is not
  all $FF in the 48K ROM.
- SkoolKit `Snapshot.get(...).memory[0:0x4000]` is ZEROS for .z80 files: take ROM bytes from
  `skoolkit.ROM48`. The Dizzy V slot-1 page was built from it -> blank font -> empty dialogue
  boxes on hardware. Verify the page against ROM48 at every ROM byte the game reads.
- SkoolKit's Simulator silently drops writes below 0x4000; on the Next a slot-1 RAM page takes
  them. Check for ROM writes with dizzy6._rw_simulator() (guards removed).
- SkoolKit snap.ram() is a 48K view even for 128K; test snap.machine.
- 128K Python-sim hooks: in a Simulator subclass set memory.__class__ to a pagingtracer.Memory
  subclass; wrap opcode-table entries for exec hooks; set rzxplay.Simulator, CSimulator=None.
- Boot simulation needs writes below 0x4000 (alt ROM write mode): dizzy6._rw_simulator();
  NEXTREG via after_ED[0x91/0x92], ports via the tracer.
- Hand-assembled hooks: cross-check against sjasmplus (caught a JR out of range).
  sjasmplus: git clone z00m128/sjasmplus && make USE_LUA=0 (Lua submodule missing; ~1 min); use
  --zxnext. `pair` is a reserved word (label error). Local labels inside MACROs are macro-local:
  inline the text instead when the macro jumps to the enclosing routine's label.
- The repo (github.com/bleughb/specnext) is the only master copy (2026-10-11). Before it, Project
  files had to be retyped into each sandbox (no /mnt/project): slow, and old same-name uploads
  resurfaced stale facts. The move was checked by extracting every Project read verbatim from the
  session transcript (40/48 files = the handover MD5s; the 8 others = known later edits) and by
  reassembling every .asm against its profile hex. Never retype a file: clone, edit, commit.
- A toolkit zip from Dean can be a side branch, not an old copy: the 2026-09-28 zip held a 128K
  variant of machine.py / analyse.py / recorder.py (+ selftest128.py) that never reached the
  master copy. Ask before mixing.
- `rzxplay.py --map FILE` + `sna2ctl.py -m FILE` + `sna2skool.py -c` give a routine-split
  disassembly of everything an RZX executed in ~1 minute: the fastest way into an unknown engine.

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
- A code path no RZX reaches can be proven by a unit differential test (original vs patched code
  from the same state) plus a negative control that must fail.
- Unit tests must include a negative control (e.g. a broken nibble table) or they prove nothing.
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
- Big caches belong in Next RAM, not pattern RAM: a 256K store (pages 32-63) mapped at MMU1
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
- Two verification levels (docs/BRIEFING.md C3b): ITERATE (sites, boot, unit tests, `--quick 2000`
  on one RZX, ~13 min for Rainbow now) per change; RELEASE (all RZX in full, one job at a time)
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
- States captured early in an RZX are often a figure's FIRST plot (no sprite yet): force the
  steady state (old image already a sprite) in unit cases that test steady-state behaviour.
- A 'buffer is non-empty' flag that lets later code skip work must be set on EVERY path that
  writes the buffer: Commando's lazily cleared depth mask missed the rectangle-shape path (found
  by the depth unit cases, which the RZX alone had not hit).

## 2.6 Process / tokens (this sandbox)
- One CPU; background jobs die when the turn ends: run long jobs sequentially
  (`setsid nohup sh script.sh &`, or chain: `setsid nohup sh -c 'a; b' ... &`) and poll inside the turn. A `( a; b ) &` subshell dies silently.
- `pkill -f script.py` kills the tool shell when its own command line contains the name (mid-edit:
  re-check files after); use pgrep, then kill by PID.
- Name scratch scripts uniquely: a file called dis.py shadows the stdlib and breaks SkoolKit.
- Do all analyses in one simulator pass; poll background jobs.
- Never run per-instruction Python work in an analysis hook (a dict scan per opcode turned a
  2-minute pass into a 10-minute timeout).
- Print summaries, not listings. Disassemble only flagged routines.
- Keep the user's answers terse; explain only new findings.
- A single tool call is capped at 10 minutes: poll a background job with sleeps under that
  (Chuckie Egg RELEASE run ~15 min: verify 8626 frames ~5 min, unit tests ~10 min).
