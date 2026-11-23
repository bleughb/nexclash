# Hardware tests

Small .nex programs that answer one hardware question each, for facts the toolkit's simulator does
not model (BRIEFING A1 blind spots). Recipe (after MikeDX/next-testsuite): one question per .nex,
cases from Ped7g's tests (docs/TECHNIQUES.md "Hardware ground truth") plus ours; each visual phase
held on screen ~2 s; the final screen is one coloured block per test (green pass, red fail, white
visual). Build:

    python tools/hwtests/build.py im2hold -o OUTDIR

Run the .nex on a real Next (NextZXOS browser), photograph the final screen and the border; then
run it in MAME / CSpect to see whether the emulator agrees. Record the result in the C2 item and,
for an emulator, LEARNINGS 2.7 [MAME]. Never commit the built .nex.

Every test writes a results table at $7E00: `NXHT`, version, test count, then two bytes per test -
status (0 not run, 1 pass, 2 fail, 3 info) and a detail byte. A MAME script can read it once the
border is green or red.

## im2hold - BRIEFING C2 #34 (hardware IM2 mode holds interrupts)

Final screen: seven 2x2 blocks on character rows 2-3 (columns 2, 5, 8, ..., 20), numbered by test
(run order T1 T2 T3 T5 T6 T4 T7). Green pass, red fail, white info, black not run. Under each
block (row 5) its detail byte in hex. Border green = nothing failed, red = something did.

| # | Test | Pass means | Detail byte |
|---|---|---|---|
| 1 | vector | in hardware IM2 mode ($C0 bit 0) the ULA interrupt reads its handler from I*256 + $16 | runs of a wrong vector's handler |
| 2 | held | an interrupt arriving during 3 frames with interrupts off is taken at the EI (not lost) | interrupts taken after the EI |
| 3 | pulse (control) | the same in pulse mode ($C0 = 0) is LOST, as expected | interrupts taken (0 = lost) |
| 4 | ret-ack (info, white) | - | handler runs in one frame when it ends EI;RET instead of RETI: 1 = RET acknowledges too, 200 = never acknowledged (re-fires; the test stops it) |
| 5 | trampoline | vector -> push game handler -> RETI (acknowledge) -> game handler ending EI;RET: 4-6 runs in 5 frames, foreground keeps running | handler runs |
| 6 | uniform table | a game-style 257-byte IM2 table (all $A1 -> handler at $A1A1) works unchanged in hardware mode: 4-6 runs in 5 frames | handler runs |
| 7 | recover | after test 4, one dummy RETI with interrupts off lets the interrupts come again: 4-6 runs in 5 frames | handler runs |

Board results:
- v1 (2026-10-20, Dean): T1-T3 green, T4 white, T5 + T6 red. T5 / T6 ran right after T4: suspected
  cause, T4's never-acknowledged interrupt blocks the next ones (v2 runs T4 late and adds T7).
- v2 (2026-10-20, Dean, board photo): ALL PASS, border green. Details T1-T7: 01 01 00 01 06 06 06.
  T4 = 01: a handler ending EI;RET runs once and no interrupt comes after it - RET does NOT
  acknowledge, and the unacknowledged interrupt BLOCKS every later one (so v1's T5 / T6 saw 0).
  T7 = 06: one dummy RETI with interrupts off clears it. (6 in "5 frames": the count starts mid-frame.)

If the screen stays black with a black border after a few seconds, a test hung: note the border
colour and which blocks are drawn (none are drawn until the end) and report it.

Reading the results: tests 2, 5 and 6 passing = C2 #34's design works (hooks may run with
interrupts off; the game's handler is reached through a RETI trampoline or the game's own uniform
table). Test 4 says whether a game handler that ends EI;RET needs the trampoline at all.

## z80ntest - every Z80N instruction against nexclash/z80n.py

    python tools/hwtests/build.py z80ntest -o OUTDIR

build.py first runs `z80ntest_gen.py`, which takes each case's expected result from the shared
module's handlers (SkoolKit + `z80n.install`) - so the board checks exactly what the toolkit's
verifiers assume. Runs ~10 s (blue border), then shows page 1; ANY KEY flips between the pages.
Photograph both pages and the border.

Page 1, FUNC (46 cases): one Z80N instruction from a known A F BC DE HL, SP = $6200 and a 1 KB
window at $6000; A..L, SP and a checksum of the window compared. Flag-changing instructions run
from F = 0 and F = $FF (last character of the name 0 / F), the rest from F = $A5. Columns: name,
F on the board, F expected, code. Green all equal; YELLOW only F differs (the flag question the
module had to guess - write down both values); red R = a register or SP, M = memory differs.
NEXTRGn / NEXTRGA / OUTINB write NextReg $7F and read it back. JPC: JP (C) with IN = 5 must land
on $C140; JPCedge runs from $BFFE, so A = $FF (red) means the base came from the instruction's own
address instead of the next one.

Page 2, TIME: T-states at 3.5 MHz from the raster line counter (2048 runs per instruction,
4 measurements a quarter line apart, scaled by 2048 x LD A,(IX+0) = 19 T). Columns: name,
measured T, expected T; green within 0.5. NEG / LDI / LDIR are Z80 controls (8 / 16 / 21): if
they are red the method failed on that machine, not the Z80N rows. Timing code and data stay in
uncontended RAM; any video timing (48K / 128K, 50 / 60 Hz) works.

Border: green all pass, yellow only flag differences, red a failure. The harness itself uses
NEXTREG (speed, NextReg $7F): if NEXTREG were broken every page would be wrong.

Results table at $7E00 as above (status 4 = flags only; detail = F on page 1, T * 10 on page 2),
then the calibration line count (word); per FUNC case the registers at $7000 + 16 * (n-1):
F A C B E D L H, SP, checksum.

Board results:
- v1 (2026-10-21, core 3.02.00): TIME all green (LDWS 13.9, NEXTREG 20.0 / 17.0, PUSHnn 23.0;
  controls 8.1 / 16.0 / 20.9). FUNC all green except LDWSF yellow (F $94, module said $95: LDWS's
  CF comes from ADD D,1 - module fixed, v2 expects $94) and LDPIRX0 / LDPIRXF red M (memory) with
  F $00 / $C1 instead of $08 / $C9: core changelog 3.02.02 fixes LDPIRX - re-run on 3.02.02+.
- v2 (2026-10-21, same board, core 3.02.00): all green except LDPIRX0 / LDPIRXF (red M, F $00 /
  $C1 again - expected on 3.02.00). LDWS7F $94 and LDWSFF $51: LDWS's flags are ADD D,1's, CF set
  when D was $FF - the module's fix confirmed. TIME all green again (LDWS 13.9, NEG 8.0).
- CSpect 3.3.1.0 (2026-10-21, reports core 4.00.00; emulator, not ground truth): differs from the
  board in ADD rr,A (CF kept: ADDHLAF / ADDDEAF $FF, ADDBCA $A5), LDIX / LDIRX / LDDX / LDDRX from
  F = $FF (bits 5 / 3 kept: $ED / $E9), LDWS (INC D flags: 7F -> $95, FF -> $50), JP (C) (IN-style
  flags, F $05; target right) and PUSH nn timing (19.0 T, board 23). LDPIRX: memory as the 3.02.02+
  model (no M), F $00 / $E9. Everything else, all other T-states, as the board.

Checked before any board (2026-10-21): the .nex run in SkoolKit + z80n with a modelled raster
(224 T x 312 lines, 228 x 311, 224 x 262): 77/77 green, T within 0.1; with ADD HL,A keeping CF,
LDWS at 16 T and a wrong MUL result: ADDHLAF yellow, MUL red R, LDWS red (15.9).

Independent cross-check of nexclash/z80n.py (2026-10-22, no hardware): Ped7g's self-checking
snippet tests (github.com/ped7g/ZXSpectrumNextMisc snippets/runsnippet.asm, MIT, built with the
pinned sjasmplus from the 2026-09-19 sources) run in SkoolKit + `z80n.install` with a modelled
raster: every test passed (no "red" NextReg $6C = 2 write) over 11.9 M instructions, among them
324,687 MUL D,E, 65,806 BSRL DE,B, 67,594 ADD HL,A, 36,129 ADD DE,A, 257 TEST n (div10 / div50 /
mod 40 / 192 / 320 / 640 / mul / bit_fun / percentCompleted, most exhaustive over 0..65535).
Negative control: MUL with E off by one -> the div10, mul and percentCompleted tests report errors.
Not kept as a test here (an outside repo); the harness is a 60-line script around nextboot-style
loading + a tracer.

## nextbench - what Next techniques cost, at several sizes, set up / reused / torn down, repeated (v3)

    python tools/hwtests/build.py nextbench -o OUTDIR     (runs nextbench_gen.py: the 88 rows)

Microseconds PER CALL at 3.5 MHz and 28 MHz (the hooks' speed) on the raster line counter, as
z80ntest's TIME page: 4 dithered passes, the same with an empty routine subtracted, calibrated
against 2048 x LD A,(IX+0) at 3.5 MHz. The repeat count R is chosen per row and speed by a probe
run (a measurement fills ~140 lines; R = 1 for long calls; ">" = one call does not fit a frame),
so no row can wrap the line counter.

v3 runs the whole table 5 times (NRUNS in nextbench_gen.py; ~1 minute a run, blue border, "RUN n/5"
on screen). R is chosen in run 1 and kept, so the runs measure the same thing. The 5 table pages
show the MEAN of the runs; "~" after a value = its runs differ by more than rounding to whole raster
lines can explain. The test: each run's d (4 line reads after the row minus 4 after the empty
routine) can differ by rounding alone with variance at most 2 line^2 (a read whose instant wobbles
by under a line rounds to one of two lines: at most 1/4 each), so sum((d - mean)^2) / 2 is at most
chi-square with 4 degrees of freedom; "~" when it exceeds the 0.1 % point (18.47; nextbench_gen.py
sigthr: N * sum >= 185). Under 0.2 false "~" over the 176 values. What it can see: one run off by
~7 lines among 5, i.e. ~7 x 16 us / R per call (R = 1 rows: ~110 us, 6 % of LDIR 2048 at 28 MHz;
R >= 64 rows: under 2 us).
Copper function rows: "~" = any run differs. The page(s) after the table list every "~" value
(name, size, MHz, the smallest and the largest run in us per call) and the calibration lines of each
run ("cal"); "none" when nothing varied. Any key flips the pages. Border green = all checks passed
and nothing varied, yellow = a "~" somewhere, red = a "!" somewhere.

Rows (name, size):
- copy 1 / 16 / 64 / 256 / 1024 / 2048 B: LDIR, LDI unr (unrolled; one 256-LDI block entered at
  the right point, looped above 256), STACK (2 KB unrolled POP / PUSH, entered at the right chunk),
  DMA (full 16-byte program each call); DMA rtg (only addresses + length rewritten, ports kept)
  16 / 256 / 2048; DMA rrun (LOAD + ENABLE: the same transfer again) 256; DMA brst (burst mode)
  256 / 2048; LDIRX 256. Every copy is checked.
- fill $55 16 / 256 / 2048: FILL LDR, FILL PSH (PUSH block), FILL DMA (fixed source). Checked.
- sprite pattern to port 0x5B 64 / 128 / 256 / 2048: PAT OTIR, PAT OUTI (unrolled), PAT DMA.
- sprite attributes: ATR 57 (port, 1 / 32 sprites), ATR NR (NEXTREG $34-$38, 1 / 32), HIDE NR
  (128 sprites by NEXTREG $78 post-increment), HIDE 57 (128 hide records by port), SPR OFF ($15).
- NR v, NR a, PORTPAIR (OUT $243B + $253B), NR READ; MMU 1 / 4 slots, 7FFD.
- ULA CHAR, TILE ENT, L2 CELL; TM SWAP ($6E), L2 FLIP ($12), SHADOW2 (7FFD bit 3 and back);
  TM SCRL, L2 SCRL.
- PAL8 1 / 16 entries, PAL9 1, PAL SEL ($43).
- copper load (stopped) 8 / 32 / 256 instructions by NEXTREG $60 (COP NR) / OUT $253B (COP IO);
  COPGO+ST (start + stop); LDIR+COP (LDIR 256 while the copper loops MOVEs: does the copper slow
  the CPU?).
- copper function (the value is a number): CP WAIT = raster line at which the CPU sees the MOVE
  after a copper WAIT 120 (copper line numbering vs $1E/$1F; ">" = never); CP APART = wrong palette
  entries (of 256) the CPU reads back while the copper loops MOVE $7F (expected 0, "!" otherwise);
  CP SHARE = the same with the copper looping MOVE $40, the palette index the CPU uses (wrong
  entries expected: TECHNIQUES 1 "never drive one register pair from both"; info, never "!").

Results at $7A00: "NXB3", version, count, calibration lines summed over the runs, per row 10
bytes (mean value at 3.5 / 28 MHz as dwords in tenths, R at 3.5 / 28 MHz), then a flag byte per row
(bit 0 / 1 check failed at 3.5 / 28 MHz in any run, bit 2 / 3 did not fit a frame, bit 4 / 5 varies
between runs). Per run at $6200: NRUNS, 0, each run's calibration lines (words); $6210: per row,
speed and run the line count d (word; copper function rows: the number).

v2 (commit 93fc8ca: one run, the same 88 rows) is the run the v2 board results were taken with.
v3 also fixes v2's line read (LEARNINGS 2.3): v2 re-read the $1E / $1F pair until two reads agreed,
which at 3.5 MHz returned a line 0-3 lines late; v2's 3.5 MHz figures carry that error (up to ~3
lines x 16 us / R per call: tens of us on R = 1 rows such as LDIR 2048, nothing on R >= 64 rows);
its 28 MHz figures much less (a read is 8x shorter than a line there).

v3 board run (2026-10-22, core 3.02.00): every value repeated within its rounding over the 5 runs
(no "~"; page 6 "none"); border red only for the known DMA "!" at 3.5 MHz. CP WAIT 120 / 120 (v2 read
122 at 3.5 MHz: the late line read, now fixed), CP APART 0 / 0, CP SHARE 255 / 255. 28 MHz means
within 0.5 % of v2 (TECHNIQUES 1.0b). Photos: specnext reference/hwtests/nextbench/ board_v3_p1..p5.

v3 checked before any board (2026-10-22), SkoolKit + z80n with a modelled raster (NextReg $07 not
modelled: both speeds run 3.5 MHz timing): (1) no added noise, NR v slowed by 40 T a call in runs
3-5: every other row's 5 runs within 1 line, only NR v "~" (3.5 and 28), its page min 5.7 / max
17.1 us (5.7 + 40 T); (2) the same plus a random 0-223 T phase after every frame_sync (worse than
the board's ~28 T): again only NR v "~" (the first test, with the uniform-rounding bound 8/12,
flagged 16 of 176 values here: hence the 1/4 bound); (3) SIGTHR forced to 0: every value listed,
9 statistics pages, page numbers 2 digits (P14/14), the list ends and wraps to page 1.

v1 (commit 0b51cc9, 32 rows, one size each, fixed R) is the run the board results below were taken
with; TECHNIQUES 1.0 holds its table.

v2 board run (2026-10-22, core 3.02.00): all 88 rows; every 3.5 MHz CPU row matched its T-state
count; DMA "!" at 3.5 MHz only (border red), right at 28 MHz; CP WAIT 122 / 120, CP APART 0 / 0,
CP SHARE 255 / 255. Table and conclusions: docs/TECHNIQUES.md 1.0b. Photos: specnext
reference/hwtests/nextbench/ (board_v2_p1..p5).

v2 checked before any board (2026-10-22): in SkoolKit + z80n with a modelled raster (no DMA, copper
or CPU speed change) every CPU row at 3.5 MHz matches its T-state count (LDIR 64 390.7 for 391.1 us,
LDI unr 64 300.2 for 304, L2 CELL 359.5 for 360.6, NR v 5.7 for 5.7); the R probe needed three
tiers (1 / 8 / 64 calls) - a single tier either under-sized tiny rows or overran the frame on rows
of 100-640 us. DMA / copper rows show "!" / ">" there (no DMA, no copper).

Board results: v1 (2026-10-22, core 3.02.00): every CPU row at 3.5 MHz as its T-state count; 28 MHz
6.3-7x faster (memory wait states); DMA rows WRONG at 3.5 MHz ("!" on DMA 1B / 256 / 2K and FILL DMA,
border red; the core changelog fixes it in 3.02.02), right at 28 MHz. The table and conclusions:
docs/TECHNIQUES.md 1.0. Photos: specnext reference/hwtests/nextbench/.

Checked before any board (2026-10-22): in SkoolKit + z80n with a modelled raster (no DMA, no CPU
speed change) every CPU-only row at 3.5 MHz matches its T-state count within 0.7 % (e.g. LDI x256
1251.3 for 1249.7 us, NEXTREGv 5.5 for 5.7, ULA CHAR 61.7 for 61.7).

## nxsuite - one .nex that answers the open hardware claims, results in a text file

Sources: `nxsuite.asm` + `nxsuite/*.asm` (harness, timing core, one file per group), the test table and
claims inventory `nxsuite_claims.json` (read by `nxsuite_gen.py` and by `intake.py`), `intake.py`.
Groups: G0 SYS, G1 CPU, G2 Z80N, G3 IRQ, G4 FRAME, G5 COPPER, G6 DMA, G7 BENCH, G8 SPRITES, G9 MEM
(automatic, RUN ALL), V VISUAL (the person at the machine answers), XT TIMING, XD DIVMMC, XH DMA-HAZARD
(opt-in, never in RUN ALL). Every test of the table is built, or left out on purpose with a reason in
`nxsuite_claims.json` (`left_out`; the file says `SKIP why=left-out`, the intake prints the reason);
`nxsuite_gen.py` refuses a test that is neither, so no `why=not-built` line can appear. Group code that does
not fit bank 0 runs from a slot-7 overlay page (40-43, 60, 61, 63; a group may have a second page, flag 8
in the test table, and a test any other page of the generator's `xpage` list, flags bits 5-7: the V tests in
`gv3.asm`-`gv6.asm`).

### Owner checklist (one board, one core)

1. Copy `nxsuite.nex` into a new folder of its own on the SD card; start it from the Browser. The first
   start asks a few optional questions (below); S skips them, and so do 20 s without a key.
2. Press A (RUN ALL): about 6 minutes, leave the machine alone. The border is blue while a group runs,
   then green / yellow / red. F03 and F06 switch to the other refresh rate for a moment (the picture may
   blink; if it does not come back within 10 s: reset, start the suite again - it resumes). From the
   second group on, row 1 of the group screen says `Saved: <n> lines` - the file's length after the last
   group was written; the number grows group by group. DONE: the border turns green when the file was
   saved, red with FILE WRITE FAILED when it was not: the run then shows every result as pages to
   photograph first (a failed write at a group end no longer stops the run: the message goes after a key
   or 20 s); any key.
3. Press V (the visual pass, about 8 minutes): answer each screen with Y / N or a number (1 to 3, 4 or 5 as the
   screen's last line says; S = ask later).
   Each picture is drawn under the question with a reference beside it (white / yellow lines, a square,
   a computed colour); V01, V03, V07, V09, V12 and V18 ask about two pictures, one after the other.
   V19 first asks which cable carries the picture, then needs a watch showing seconds (SPACE starts,
   SPACE after 60 s or more stops, type the seconds, ENTER; the machine times the same interval by its CTC,
   and the intake sets the two against each other).
4. Optional, only if you agree to the risk shown before each test (Y runs it, N skips it):
   T (timing; the machine timing is put back after each test and at the next start after a hang),
   D (DivMMC; no SD write; when it ends check that the DONE screen's line count grew and the border is
   green), H (DMA hazards; XH1 can freeze the machine; XH2 leaves the DMA deaf: let the group finish,
   soft-reset - or power off and on -, start the suite again: it asks at once which reset you used and
   reports what that reset did; no key to press first). After a freeze: reset (or power off and on), start the suite from the same folder:
   the test is marked HANG-GUARD and the run goes on.
5. When the NEXT STEP line says NOTHING OUTSTANDING: copy `NXSUITE.TXT` (and any `NXSUITE.0nn` parts) and
   `NXSUITE.PRG` to the PC; run `python tools/hwtests/intake.py NXSUITE.TXT --board <name>`.

Build (keep the .nex out of the repository):

    python tools/hwtests/build.py nxsuite -o OUTDIR          # --sym also writes nxsuite.sym

Run: copy `nxsuite.nex` into a folder of its own on the SD card and start it from the Browser. The suite
writes `NXSUITE.TXT` (results), `NXSUITE.PRG` (progress record, 64 bytes; offsets 52-63 hold the
first-start answers, flag bit 2 = asked) and, when needed, parts
`NXSUITE.001`, `NXSUITE.002`, ... into that folder and nothing anywhere else. Menu keys: A = all automatic tests (about 6 minutes - G7 BENCH alone is about 3 - leave it alone), 0-9 = one group,
R = resume, U = retry the tests that hung, V = the visual pass (the person at the machine answers: Y / N or
a number, S = ask later; in RUN ALL these tests are PENDING-OPERATOR), T / D / H = the opt-in groups (timing,
DivMMC, DMA hang: each test shows what it risks and what to do if the machine does not come back, Y runs it,
N skips it; never in RUN ALL). Opt-in details: X-T (T) writes NextReg $03 (machine timing, survives a soft
reset) only after saving the start value in `NXSUITE.PRG` (offset 50, flag bit 1); each test puts it back, and
a start after a hang puts it back from the record and measures the preamble again before anything else.
XT4 never writes $3FFD when NextReg $D8 bit 0 (the +3 disk-port trap) was set at launch. X-D (D) writes only
$BB bit 6, a few alt-ROM bytes and two DivMMC RAM bytes at $3D00 (each saved, written back); interrupts stay
off while DivMMC can be mapped, only one-byte RETs (and XD2's OR A) run there, and the ROM bytes are checked
against a copy taken at start before anything is printed. Its only esxDOS call is a fallback F_OPEN (read) of
`NXNOFILE.XXX`, which does not exist; if DivMMC still cannot be unmapped the machine stops on a red screen
(power off and on). The suite's screens use a RAM copy of the ROM font taken at start. X-H (H): XH1 can freeze the machine if the interrupt escape fails
(reset, start again: HANG-GUARD); XH2 leaves the DMA deaf on purpose - let the group finish, soft-reset,
start the suite again: the start itself asks which reset was used (a one-group XH pass with XH2 only) and
reports `reset-frees` or `still-locked` from the one DMA byte the start tried (`NXSUITE.PRG` offset 51, flag bit 0). The NEXT STEP line under the group list
says in plain words what to do next. Border during a group: blue running, then green (no FAIL), yellow
(INFO only) or red (a FAIL).

File (`NXSUITE.TXT`): plain ASCII, LF line ends. `NXSUITE 1`, then per session `H` lines (suite, core,
video, timing, speed, calibration, DivMMC registers), `R` lines (every NextReg at the first start), per
pass a `P pass=<n> mode=<ALL|GROUP:Gn|RESUME|HUNG>` line, per group `G id= start` / `G id= end fails=`,
one `T` line per test:
`T id=<test> st=<status> c=<claims> v=<value> u=<unit> n=<runs> min= max= [why=] [key=value ...]`, and a
last line `END lines=<n> crc16=$hhhh` (CRC-16/CCITT over every byte before it). Sub-test lines carry the
parent's prefix: `zf.` (Z01 cases), `zt.` / `zu.` (Z06 / Z07), `ih.` (I03 = im2hold T1-T7), `nb.` (N01 =
the nextbench table: `nb.<name>.<size>.<35|28>`, v = microseconds per call, mean of 5 runs, min / max,
`R=` calls per measurement; FAIL only when a copy / fill check fails; suite-only rows `DMA_cont.1` - $D3
continue, both ports fixed - and `DMA_arm.256` - WR0 port A only, $CF, $87); they have no `c=` (the parent's
claims). A later
session or pass appends to the same file. The intake keeps every pass: a test's verdict uses its latest
pass, and every test whose passes disagree is listed (files from before the `P` line: a pass is inferred
where a group starts that does not follow the previous one).

Parts (no 64 KB limit): the program keeps the text in a 48 KB buffer. When it passes 40 KB the buffer is
written, with its own END line, to the next free `NXSUITE.nnn`, and `NXSUITE.TXT` goes on as a continuation:
`NXSUITE 1`, then `C part=<nnn> src=<build>`. The intake follows the C lines back through the parts (give it
`NXSUITE.TXT`; every part must be beside it and check; a missing one is refused). At start, an
`NXSUITE.TXT` from another build (its first `src=` differs) or one that does not check (cut short, damaged,
longer than the 48 KB the program reads back) is first copied unchanged to the next free `NXSUITE.nnn`
(menu: "file: other build kept, new" / "old kept as NXSUITE.nnn"; the new file's second line names the
part) and a new file is started; if that copy fails the program stops with a message and writes nothing.
If a part cannot be written, the buffer fills and every later write carries `X truncated lost=<bytes>`
before END: the intake prints a WARNING and the JSON has `"truncated"`. The DONE screen shows the bytes and
lines written and any bytes lost. (Builds up to 3803884 lost everything past 64 KB silently while still
writing a valid END line.)

50 / 60 Hz (addition B): F06 (in G4, so in RUN ALL) measures lines per frame, line length and the ULA
interrupt line at the start rate and at the other one (NextReg $05 bit 2 read-modify-write, put back; a
line on the screen warns that the picture may blink); the intake prints them side by side with F01 / F02 /
F03 / I09. Starting the machine at 60 Hz gives the same table (the keys are named by rate, not by order).

`video=`: always `unknown` - no register the repository's sources cite says which output (HDMI, VGA, RGB)
is in use. Board facts (KS1, core 3.03.00): NextReg $11 read $00 with an HDMI cable and with "Digital"
selected in the settings, and the frame was 128K VGA timing (311 lines, INT line 248), so digital output
does not imply a different frame. (The book report: $11 modes 0-6 are VGA master-clock steps, HDMI works
in modes 0 and 1, $11 is set by the firmware from the display settings; the start-up screen's D key
shows the digital test card.) `geom=` is what the measurements match: line length in CTC ticks (16 clocks) and lines per frame:
108 = hdmi, 112 / 312 = vga48, 112 / 320 = pentagon, 114 / 311 = vga128, else other.

Statuses: PASS, FAIL (the claim's expectation is wrong on this machine), INFO (a number or a choice, no
verdict), SKIP (`why=not-built`, `not-selected`, `hung-last-run`, `no-blitter` - D09's probe found no blitter, or
D09 did not run this session and the core is below 3.03 -, `dma-deaf` - XH: the DMA still locked by an earlier XH2 -, `left-out` -
on purpose: the reason is in `nxsuite_claims.json` and the intake prints it), HANG-GUARD (the machine stopped in this
test on the run before), OPERATOR (`key=` / `means=`, answered by the person at the machine),
PENDING-OPERATOR (an operator question left for the U pass), VISUAL / VISUAL-SHOWN (later stages).

First start (once per folder): the machine as a two-key code from `nxsuite_claims.json` `platforms`
(adding a platform is a data change; `nxsuite_gen.py` checks the list), display connection and kind, RAM
believed fitted, Pi / accelerator, and a machine label of up to 8 letters / digits - the screen says it is
a machine nickname, not a person's name. Every session writes them as
`H operator model=K1 conn=1 disp=2 ramq=1 pi=2 label=BENCH1` (`-` = not given); the intake decodes them
into the record's `operator` (what was said, not measured) and adds the label to the record name
(`<board>-<core>-<label>.json`; without a label the name is `<board>-<core>.json` as before).

After a hang: reset the Next, start `nxsuite.nex` again from the same folder. It finds the progress record,
resumes by itself after 5 seconds (or press R): the test it stopped in is written HANG-GUARD, its group is
run again from its start without it, and the run carries on. Nothing that persists across power is written.

Intake (on the PC):

    python tools/hwtests/intake.py NXSUITE.TXT [--board NAME]   # -> docs/kb/hardware/<board>-<core>.json
    python tools/hwtests/intake.py NXSUITE.TXT --platform "JNext 1.3.0"
                                          # emulator -> docs/kb/hardware/emulator/<platform>-<core>.json
    python tools/hwtests/intake.py --dry-run NXSUITE.TXT         # report only
    python tools/hwtests/intake.py --compare A.json B.json
    python tools/hwtests/intake.py --runs RUN1/NXSUITE.TXT RUN2/NXSUITE.TXT   # stability across runs
    python tools/hwtests/intake.py --selfcheck                   # also run by selftest.py --tools
    python tools/hwtests/intake.py --describe [TEST]             # what a test does, without the assembly
    python tools/hwtests/intake.py --reference A.json B.json ... --out DIR   # DIR/nxsuite-test-reference.md
    python tools/hwtests/intake.py --conformance EMU.json --against BOARD.json
    python tools/hwtests/intake.py --summary A.json B.json ...    # machines / cores / emulators side by side

Every built test carries a plain `purpose`, `method`, `expect`, `fields`, `needs` and `hazard` in
`nxsuite_claims.json`; the build stops if a built test lacks purpose, method or fields (or has non-ASCII
text). `--describe` prints them; `--reference` writes them, with every given record's result labelled by its
board and core (or emulator), into one Markdown file generated on demand (not kept in docs/).
`--summary` prints the hardware identity of each record (NextReg $00 / $0F raw, core, RAM, timing,
50 / 60 Hz, lines, start speed, 28 MHz wait, CTC calibration, DMA type, port enables, DivMMC registers,
the operator's answers; each row names its source, decoded only as far as the source says; Pi / ESP / RTC
are not probed: no safe documented read), then every test whose results differ beyond the `--runs`
tolerance, grouped by which records agree and what sets the sides apart (platform, board, core, video, or
no single one), then the tests that differ only within tolerance (run-to-run noise).
`--conformance` sets one record (an emulator) against one board record per test: SAME, DIFFERENT (with both
values and the reason, `--runs` tolerance) or NOT COMPARABLE (not run, SKIP, unanswered). The reference is
that one board and core: "different" means different from it, and an emulator result is never hardware
evidence.

Emulators (unattended, the automatic pass): `tools/hwtests/emurun.py` starts one emulator, presses the menu
key, waits for the DONE flag and leaves `NXSUITE.TXT` / `.PRG` in the SD folder given; the emulator program
and the folder are arguments (nothing machine-specific in the repository):

    python tools/hwtests/emurun.py jnext  --exe JNEXT_EXE  --sd DIR --nex nxsuite.nex [--card SD_IMAGE]
    python tools/hwtests/emurun.py cspect --exe CSPECT_EXE --sd DIR --nex nxsuite.nex [--hz60] [--port 8766]
                                   [--sdspeed slowest]
    python tools/hwtests/intake.py DIR/NXSUITE.TXT --platform "JNext 1.3.0"

Results can depend on a local emulator settings file. CSpect 4.6 reads `cspect.ini` from its working
folder, else from beside CSpect.exe, and saves menu changes into the working folder; emurun therefore runs
CSpect with the SD folder as its working folder and passes every option on the command line, so it neither
uses nor overwrites the owner's settings. A `cspect.ini` beside CSpect.exe is still read: name the CSpect
version and say whether such a file exists when filing a record. Name each record for the exact emulator
version that made it; a record from an older version stays as it was.

Proven 2026-11-24: JNext 1.3.0 (49 s), CSpect 4.5.9.0 (374 s) and CSpect 4.6.0.0. MAME 0.289 (driver tbblue) is not
supported: started with `-snapshot nxsuite.nex` the suite reaches its menu with an unreadable font (the
ROM mapped there is not NextZXOS's ROM 3) and no key is taken; booted from a NextZXOS SD image it stays on
the welcome screen (CPU at $0C90 from frame 200, keys not taken through Lua). An emulator author can still
run the suite by hand; the V (visual) pass can be answered by eye or left PENDING.

It refuses a file that is cut short, damaged (CRC), not ASCII / LF, or names an unknown test or status,
and a continuation whose parts are not all beside it.
Per claim it reports CONFIRMED, DISPROVED, MEASURED value +- spread, CHOICE word or NOT ANSWERED (with the
reason), with the claim's sources; it never edits lessons or docs. The board name defaults to
`next-issue2` / `3` / `4` from NextReg $00 = $0A and $0F = 0 / 1 / 2 (Issue 2 = the KS1 boards). Emulator
results (`--platform` other than `board`) are stored apart and never count as hardware evidence; `--compare`
says when it compares a board with an emulator. Z01's cases decide their own claims (LDIX / LDPIRX / JP (C) /
TEST cases; func-suite = every case but LDPIRX); an LDPIRX case that differs from the model only in F bits
5 / 3 (documented as unsure) counts as right, with a note.

`--runs` takes two or more result files from one board and core (it refuses a mix) and lists every test
whose status differs, or whose value or a numeric key differs by more than its tolerance: the larger
within-run min-max, a method resolution (`RUN_TOL`, I10 12 T), +-1 for counts, 0.5 % or 0.05 for the x100
fixed-point values. SKIP and HANG-GUARD records are left out, and so are keys that are memory contents
(S03 crc0 / crc96). A test it lists is not repeatable on that board: treat its value as unstable.

Claims parts that cannot be answered on the board configuration in use are listed in
`claims_not_tested` of nxsuite_claims.json with the reason (the HDMI frame geometry: the board gives a
VGA-timed frame with an HDMI cable and no source says how to get an HDMI-timed one at boot); the report
prints them with the run's `geom=`, `video=` and the operator's cable answer.

Checklist for the owner:

1. Build the .nex (above) and copy it into a new folder on the SD card, e.g. `/nxsuite/`.
2. Start it from the Browser. Wait for the menu; check the core and video lines at the top.
3. Press A and leave the machine alone until the screen says DONE.
4. If the machine stopped instead: reset, start `nxsuite.nex` again from the same folder; it resumes.
5. Do what the NEXT STEP line says until it says ALL DONE.
6. Copy every `NXSUITE.*` file of that folder to the PC (the TXT, any `.001`, `.002`, ... parts, the PRG)
   and run `intake.py` on `NXSUITE.TXT`; send the report. Check the DONE screen said no bytes LOST.
7. To start clean for a new build, delete all `NXSUITE.*` files together (the program keeps an old
   build's file as a part anyway, so nothing is lost if you forget).

### Sending the suite to another tester

    python tools/hwtests/package.py -o OUTDIR      # OUTDIR outside the repository

writes `OUTDIR/nxsuite-<build>.zip` with `nxsuite.nex` and `TESTER.TXT` (source: `nxsuite_tester.txt`; the
build id and date filled in). The build id is the commit the .nex was built from, the `src=` of every
result file it writes; the package is refused while `tools/hwtests` has uncommitted changes (or named
`-dirty` with `--allow-dirty`). TESTER.TXT says what the suite is, that it writes only `NXSUITE.*` and no
saved settings, how to copy and start it, the passes with their times, what each hazard means, what to do
after a hang or a red screen, which files to send back, what the answers are used for, and that it needs a
Spectrum Next core. Nothing personal goes into the package.

### Filing results

1. Put the tester's `NXSUITE.*` files in a folder of their own outside the repository.
2. `python tools/hwtests/intake.py NXSUITE.TXT --dry-run` first: it refuses a damaged or cut-short file
   and names the board and core it found; then without `--dry-run` (add `--board NAME` only when the
   board id does not name it). The record lands in `docs/kb/hardware/<board>-<core>[-<label>].json`; an
   emulator's (`--platform "<name> <version>"`) in `docs/kb/hardware/emulator/`.
3. `python tools/hwtests/intake.py --summary docs/kb/hardware/*.json docs/kb/hardware/emulator/*.json`
   shows the new machine beside the others. A record is the board's own file: never regenerate or edit a
   board record from anything but that board's `NXSUITE.*` files, even when the suite's format or test
   ids change later.
4. A one-board figure is labelled with that board and core; it becomes a general fact only when other
   boards agree.

Emulator authors: run the suite by hand or with `emurun.py`, take the record with `--platform`, and read
`--describe TEST` (or the generated `--reference`) for what each test does and expects;
`--conformance EMU.json --against BOARD.json` lists where the emulator differs from that board and core.
The V (visual) pass can be answered by eye or left PENDING-OPERATOR. An emulator result is never hardware
evidence.
