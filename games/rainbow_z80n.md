# Rainbow Islands (Ocean, 128K), Z80N version - engine `rainbow_z80n`, record `rainbow_z80n`

## Next session
Stage: 4 (hardware round for the overrun-recovery build)    Branch: claude/rainbow-overrun
State: 69369c89 = bda21ab6 + overrun recovery ("Overrun recovery" below); full verification stamped
  2026-10-31; all 28 LeeBee rounds verified ("Status"). Not yet on a real Next.
Inputs: specnext/reference/rainbow_islands/ (rainbow.z80, rainbow.rzx, rainbownew.rzx, leebee/)
Start with: the user's hardware report on 69369c89 ("Hardware checklist" below).
Read: this file ("Overrun recovery", "Speed ideas"), rainbow_islands.md only where pointed to.
Open: AY ticks of missed interrupts are not re-sent at the frame end (the queue catches up);
  hook speed ideas 1-4 not built.

The Rainbow Islands entry going forward (user, 2026-10-21). Forked from engine `rainbow`
(games/rainbow_islands.md, record `rainbow`), which is DEPRECATED: kept unchanged for reference only,
built with `--engine rainbow`. Everything in games/rainbow_islands.md - game facts, memory map, Dean's
decisions, hardware history, the open items - applies here unless this file says otherwise; read it
first. This file lists only what differs.

Inputs (private repo): specnext/reference/rainbow_islands/rainbow.z80 (4c98b980), rainbow.rzx
(55046d18), rainbownew.rzx (47bb2b16), the LeeBee bookmarks - the same files as the deprecated
version, not copied. Builds: specnext/reference/rainbow_z80n/.

    python nexclash.py auto rainbow.z80 --rzx rainbow.rzx --rzx rainbownew.rzx   (rainbow_z80n is the default)
    python nexclash.py auto rainbow.z80 --no-record --engine rainbow              (the deprecated version)

Code: nexclash/rainbow_z80n.py, asm/rainbow_z80n_hooks.asm, docs/profiles/rainbow_z80n.json (after any
.asm edit: `python tools/asm2profile.py rainbow_z80n`), record docs/records/rainbow_z80n.json,
dispatch: nexclash/engines.py (rainbow_z80n first; `--engine rainbow` = the deprecated engine, whose
record's recipe passes it). nexclash/rainbow.py itself stays: commando, midres, wally, wally2 and
renegade import its NextState / _machine / _run / _BankMem.

## What differs from `rainbow` (fork point = cf017271, 2026-10-21)
1. Verifier: Z80N from nexclash/z80n.py (`z80n.install` in `_machine`) instead of rainbow.py's own
   NEXTREG / SWAPNIB handlers. NEXTREG now costs 20 / 17 T (board-checked, tools/hwtests/z80ntest)
   where rainbow.py counted 0 T: the simulated raster line (NextState.line, from T) and every T
   count in the reports (tsmax, long frames, speed) now include the hooks' 110 NEXTREG sites (MMU
   paging $50-$53 on every hook entry / exit), so they are no longer optimistic.
2. Hooks: Z80N instructions where they replace a plain-Z80 sequence with the same result, every one
   checked for registers and flags read afterwards (none of the replaced flags or registers is read):
   | Instruction | Sites | Was | Saves |
   |---|---|---|---|
   | SWAPNIB | 11 (+ the 2 the fork already had) | 4x RRCA / RLCA (each followed by AND / OR, or a jump on Z set before the rotates) | 8 T, 2 bytes each |
   | MIRROR A | conversion loop `.lp` (per mirrored stream byte) | the MIRTAB lookup through H/L | 10 T |
   | MIRROR A | background mirrored rows `.fm` (per byte) | PUSH HL / LD H,$F5 / LD L,A / LD A,(HL) / POP HL (the game's own table, a bit reversal in every hooked state - unit test rev_ok) | 31 T |
   | ADD HL,A | X position (per piece), map entry `.clr` | LD E,A / LD D,0 / ADD HL,DE; LD C,A / LD B,0 / ADD HL,BC (the pair is dead after) | 14 T |
   Page 26 code 32 bytes shorter. Not changed: the x64 / x8 address multiplications (a barrel shift
   would clobber DE / B that the code still uses; a plain-Z80 rewrite is faster anyway), OUTI
   pattern writes (OUTINB is the same 16 T), MIRTAB (still built; unused by the hooks now).
3. Raster read fixed (rainbow_islands.md Open 1b): `rsafe` reads the line pair ($1E, $1F) until two
   consecutive pairs agree. The deprecated engine read it once; a 255 -> 256 crossing between the two
   reads gives line 0. With NEXTREG timed, the first quick verify (2000 frames of rainbow.rzx) landed on
   that crossing once in 1416 renders ("render end: commit now / deferred"): the hook deferred a
   commit the model said could run at once. On hardware the same race defers a commit (no tearing,
   one frame later) - or, at the 511 -> 0 wrap, can commit inside the visible frame. Alt ROM block 25
   bytes longer (911 of the free 0x386E-0x3CFF).
4. Unit tests: the Z80N self-test is z80n.selfcheck; `Z80N_USED` (rainbow_z80n.py) must equal the
   .asm's Z80N instructions; one negative control PER instruction (that one ED xx run as SkoolKit's
   silent NOP must be detected) instead of the SWAPNIB-only one.

Core: SWAPNIB / MIRROR A / ADD HL,A are in every Z80N core; the build needs the tilemap in bank 7
(as before: a recent core).

## Status
2026-10-22: `selftest.py --game rainbow_z80n --verify --stamp` PASSED - rebuild MD5s, rainbow.rzx (7,178
frames, 2,216 renders) and rainbownew.rzx (11,799 frames, 3,530 renders) IDENTICAL, diagnostic build
IDENTICAL, unit PASS (incl. one as-NOP control per Z80N instruction).
Hardware 2026-10-22: rainbow_z80n_sprites.nex bda21ab6 WORKS on a real Next and "feels smoother"
than cf017271 (user; impression, not measured).

| Output | MD5 |
|---|---|
| rainbow_z80n.nex (plain: unchanged from the deprecated engine) | 7ac543fb51c7a3c4137778eeb3cdc175 |
| rainbow_z80n_sprites.nex | bda21ab675fa271b6f51f332aae14206 |
| rainbow_z80n_sprites_diag.nex | bb2058c8bb9d593364aa1515a38a130c |

Simulated timing (28 MHz T, NEXTREG now counted; wait states still not modelled): rainbow.rzx object
hooks avg 2.8 / max 14.5 ms per game frame, whole frame max 18.6 ms, 0 frames over 20 ms;
rainbownew.rzx object hooks avg 5.4 / max 17.4 ms, whole frame max 22.2 ms, 2 frames over 20 ms
(0 without the object hooks). The deprecated engine's figures counted NEXTREG as 0 T and are not
comparable. Where Z80N / Next hardware could still help (analysis, nothing built): see "Speed ideas".

## Overrun recovery (2026-10-31, 69369c89)
User: bda21ab6 "has significant slowdowns". Cause: the game frame runs inside the IM2 handler with
interrupts off, at 28 MHz, one per LIMIT = 3 interrupts (rainbow_islands.md "Pacing"). A frame
longer than one video frame (20 ms) loses the interrupt it spans; the limiter then counts from the
next one, so that cycle takes 4 interrupts = a 1/50 s hitch, and music ticks bunch. Measured with
the fixed T accounting (below) on 2000 frames, x 8/6.5 for the 28 MHz wait states (TECHNIQUES
1.0): 8 % (rainbow.rzx) and 17 % (rainbownew.rzx) of game frames over 20 ms -> a hitch each.
- HOOKS: lread (the stable $1E/$1F pair read, moved out of rsafe) and lsamp (alt ROM): the line is
  sampled at the interrupt (s_int -> V_LI), render start (s_rs), every band end (s_bend), the render
  end (rsafe) and the frame end; a sample below the previous one = a wrap (V_WR). s_lim's run branch
  starts the frame (V_L0 = V_LL = V_LI, V_WR = 0, V_LON = 1). lexit (site 65274 via e_hx): missed =
  wraps, minus one unless the last sample is past V_L0; V_TICK = min(missed, LIMIT - 1). So the
  next frame still starts on the 3-interrupt grid unless a frame is longer than 3 video frames.
  Samples are never a video frame apart (render start, 22 band ends, render end). Page 26 vars
  0x76-0x7D; page-26 code now ends at 0x0CFF (one byte under WBG); alt ROM to 0x3C65.
- Not changed: one AY tick per interrupt; the ticks of missed interrupts are sent by the existing
  catch-up (two per interrupt while 3+ are queued; a full queue sends its oldest at once).
- VERIFIER: (a) BUG FIXED: rzxplay zeroes T BEFORE calling next_frame, so `facc += registers[25]`
  there always added 0 - a game frame spanning RZX frames lost their T: the frame-time statistics
  (frames over 20 ms, max frame) were too low since the deprecated engine (and the render end's
  beam line). Now captured at rzxplay's `tracer.border[:] = ...` (FrameEnd). (b) Beam exact and
  monotonic: line = 248 + (patched T since the interrupt) // 1792 (NextState.line_x); the old
  per-event `line_t` rounding could step back one line, which the hook counts as a wrap. (c) The
  beam is modelled at every sampling hook; at each frame end V_TICK must equal the model's missed
  count (either value when the exit crosses a line boundary) and V_LON 0.
- Unit: 9 frame-end cases (no wrap, wrap below / on / past the start line, 2, capped, the exit's
  own wrap, skip path untouched) + negative control (lexit.t store NOPed: not credited, detected).

## Speed ideas (analysis 2026-10-22, not measured; profile first)
1. tcommit copies 20 x 64 map bytes per render by LDIR (~27k T): zxnDMA, or two tilemaps switched
   with NextReg $6E instead of a copy. Pattern uploads (64 bytes per sprite by OUTI, 16 T a byte;
   OUTINB is no faster) are the other DMA candidate (store hits 94-96% keep them rare). DMA read
   timing was fixed in core 3.02.02 at 3.5 / 7 MHz (hooks run at 28 MHz; board-test first).
2. Hook entry / exit paging (NEXTREG $50 in / out, ~40 T per object hook call, hundreds a frame):
   batch cells per call; Z80N has nothing faster than NEXTREG.
3. Algorithm: tile-cache probe olook.p (linear over 176, 4-byte key byte by byte), store lookup
   s_pc.way (whole stream compared per probe: a checksum per way), nooutl.p (a 256-byte table),
   miss.lp (PUSH / POP HL per stream byte).
4. Remaining Z80N peepholes, ~0.5-1 %: 13x ADD HL,nn for LD rr,nn / ADD HL,rr (5 T, frees the pair),
   ADD DE,16 in tcommit, MUL D,E / BSLA for the x32 / x64 / x4+base address sums where a pair is free.
   Not useful here: LDIX family (transparency is per nibble), PIXELAD / PIXELDN (INC H already),
   LDWS / LDPIRX.

## Open
- Everything open in games/rainbow_islands.md (painted colours + recolour, bookmark verify of the
  boss rounds, Dean's rework).
- The simulated timing statistics (long frames, tsmax) with NEXTREG counted: compare with the
  deprecated engine's on the same recording.

## Lessons
- [doc LEARNINGS 2.1f] A turbo limiter running the game frame with interrupts off loses the
  interrupts a long frame spans (a hitch each); recover them from raster wraps sampled by the hooks
  and credit the limiter (demonstrated: verify + 9 unit cases + control; hardware not yet).
- [doc LEARNINGS 2.5] rzxplay zeroes T before next_frame: the verifier's frame T lost every RZX
  frame a game frame spanned, so "frames over 20 ms" was too low since the deprecated engine
  (observed: 13 vs 2 in rainbownew's first 2000 frames); the beam must be one monotonic formula.
- [doc LEARNINGS 2.1f] Simulated 28 MHz T x 8/6.5 (wait states) turned 13 simulated overruns into
  128 hardware ones in 1,043 frames: judge a limiter's budget with the hardware factor (inferred
  from TECHNIQUES 1.0 board figures, not measured on this game).
- [tool tools/asm2profile.py] sjasmplus warns on backslashes in the source path (Windows):
  forward slashes passed; every profile IDENTICAL after.
- [backlog C2 #44] sjasm.py cannot find or build the pinned assembler on Windows; a local 1.24.0
  copied into the cache gave identical output for all profiles.
- [deferred Open: reconsider when the hardware round reports music unevenness in busy scenes] The
  AY ticks of interrupts a frame missed are not re-sent at the frame end; the queue's catch-up
  (two per interrupt, flush when full) covers them.

## Technique use
- patch.isr-deferral: no help: about re-entrancy of a game ISR under hook time, not about pacing
  (judged from index.json; no card covers limiter pacing - written to LEARNINGS 2.1f instead)

## Stage log
- 2026-10-31 stage 4 speed round (user: "significant slowdowns"; profile, overrun recovery, verifier
  T fix + exact beam, 9 unit cases + control, quick 2000 x2, full verify stamped, 28 LeeBee rounds
  verified; knowledge from main 806937d, no merge needed: branch made from it): ~110 tool calls,
  1 user round.

## Hardware checklist - overrun recovery 69369c89 (2026-10-31)
1. Busy scenes (many enemies + rainbows + fruit, scrolling, bonus scenes, bosses): game pace
   steady - no slow-motion stretches; compare with bda21ab6 in the same place.
2. Music tempo steady there (notes may group slightly in the busiest moments, never slow down).
3. Quiet scenes, title, round start / end, death, continue: the same pace as bda21ab6 (the
   recovery acts only when a frame runs past an interrupt).
4. Everything else as bda21ab6 (figures, collectables, rainbows; no tearing).
5. Faults: where, a video; the diagnostic build (border colours) if slowdowns remain.

## Hardware checklist - bda21ab6
1. Boots; play as with cf017271: figures, collectables, rainbows, music the same.
2. Mirrored figures and backgrounds (player facing left, mirrored tiles): drawn exactly as before.
3. Busy scenes: at least as smooth as cf017271 (the hooks are a little shorter). The simulation
   with NEXTREG counted has 2 frames over 20 ms in rainbownew.rzx: a brief slowdown there is
   expected, not new (the old figures hid it).
