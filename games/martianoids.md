# Martianoids

Techniques: patch.pace-limiter, patch.restore-speed, verify.update-locked-pace.

Ultimate Play The Game, 1987, supported 48K archive release. Software release gates pass;
no physical hardware result is claimed. Source MD5:
`5df07fbd5dabdcb9a909b86cf690a4e8`.

## Presentation and approval

The original play area is monochrome. Default preserves its actual original
pixels and colours; this engine does not claim an attribute-clash improvement
where none exists. Enhanced uses an ordered, double-buffered Layer 2 canvas in
the original 160 by 112 viewport. The original ULA bitmap, collision data,
colourful frame, HUD and game logic are retained. Enhanced is optional and off
by default. No hardware sprites or added outlines are claimed.

Jon approved the part-painted first pass and then edited the 1:1 painting sheet.
The owner PNG SHA256 is
`a2dedf089df7e1a1128b6732c82fdbbec513a8497fc2fb3d7ed1051ebd2de6c2`.
Its 1,315 changed game pixels affect eleven unique figures; 1,095 recolours and
220 returns to original white. There are no conflicts or ignored edits. The
active owner PNG and original layout are protected. Shared colour-sheet read-back
imports edits without repainting or regenerating the owner's file. Original
artwork only; no external conversion colours or data were used.

## Original renderer

Player actor record 9690, unique update boundary 9967, dispatch 9974, 36 actor records of sixteen bytes. The
sorted three-byte draw list begins D355. Original plot B2BC reads graphics via
table 60A3. Initializer 9C20 converts each graphic once: stored second byte XORs
the mask. Rendering then applies `(background OR mask) XOR stored_second`.
B453 flips pairs and bits in place; source rows are bottom-up. The initial
orientation of graphic 4D differs from the rest and must be retained.

There are 116 valid IDs, 77 distinct graphics and six source bytes with real
XOR-only pixels. An independent reconstruction of twelve recorded scenes
matched all 17,920 visible original pixels per scene. Source-pixel bit7 tags
retain the original bitmap state separately from its painted colour, including
original black pixels painted another colour. Palette entries 128 through 143
mirror 0 through 15; 254 means XOR source and 255 means transparent source.

The buffer is 192 by 128, stride 24, at F400. Source x is unchanged; source bottom
is y=175-record_y. A right-edge spill enters the following row at stride 192,
not a 256-pixel display row. The visible viewport is x16..175,y16..127. The
original full copy B21C writes the screen and resets the buffer to its checker.

## Hooks, pace and memory

Only sound-free renderer span 99EF..99FE is accelerated. Original routine
bodies and their SP/return addresses remain unchanged. Both CALL preludes meet
the original body at the same full register state, including R. The hook uses
private stack 3F00 and a writable mirror of its hidden-ROM page. Every changed
MMU mapping is latched/restored. The hidden ROM retains the original BASIC calculator; only 44 proven-unused
veneer bytes and the unused bootstrap register block differ. Full hook code and
data live in private page 24; page 25 supplies the sparse ROM image. Whole ROM
images support the 26.11 loader
case; game execution never depends on the installed NextZXOS ROM contents.

The shared speed latch and original-pace limiter use K104. The original
18,000-frame recording has 2,936 render windows, 58,470 figure plots and 3,314
player dispatches. Every render window has IFF0; no input or sound I/O occurs
inside it. No new DI/EI window is added to gameplay. The original pause routine
still controls its own interrupts. Bootstrap alone uses DI then restores the
snapshot's IFF immediately before resuming its original PC.

Enhanced builds only the hidden canvas, then switches its Layer 2 base outside
visible rows 16..127, with row15 reserved as a publication guard. NR64 is initialized to zero. The original viewport-clear entries
hide the overlay before menus, sector messages and game-over displays. Ordinary
DMA clears four 8 KiB pages; core/ownership checks use the shared DMA backend, with
a CPU fallback. 2D DDMA brings no benefit to these contiguous copies. The game
uses no DMA. All completed original I/O audits were keyboard, Kempston or FE.

Assets end at page 62; complete hidden ROM images occupy banks 46 and 47. Default
and Enhanced remain within the loader's 1 MB limit, highest game bank 47. The tape
loading screen is shown exactly; 64 snapshot loader-text bytes are restored by
the startup tail before the original ROM PAUSE resumes. All original registers
and 48K RAM are compared after this restoration, with and without NEXLOAD.

The final native matrix has eighteen paired trials across three scenes and
three R/startup raster phases, with identical sampled external inputs. All 4,320
player states, 227,536 FE writes and 2,160 publications match their required state,
clock and raster contracts. Every measured full or phase window is 1.13..1.45%
faster than the original; none is slower. A previous 11% busy-scene slowdown was
caused by testing invisible clipped pixels individually; clipping each row once
removed that cost without changing the pace factor. Every individual measured player update is also faster. Dispatch 9974 can be
re-entered during a collision; only the outer-loop boundary 9967 is used for
final pace acceptance. Publication switches observed on guard row 15 are safe
because visible rows begin at 16. Final matrix evidence is retained under `jn/matrix-player/` in the private run.

## Archive trainers

All options default off. Verified original addresses:

- Infinite lives: B6C9 DEC(HL) to NOP, plus A9AC DEC(HL) to NOP. The archive omitted the second loss path.
- Infinite battery: 9E64 RET Z to RET; A8D2 and AB32 SUB B to NOP. Both collision paths and the HUD meter are checked.
- Protect sectors: A2ED JR NZ to unconditional JR. The archive's A2EF RET is unsafe: an actual recorded state has saved HL=2B00 above the actor return address 9985. The corrected branch follows the original protected-sector continuation and balances the stack.

752 CPU cases pass: 18 life counts, 702 collision-energy boundaries, 16 meter
states and 16 sector cells. The archived zone RET is retained as a failing
negative control. Restart and nine actual loader selections pass on disposable card copies, including
each trainer separately. All sixteen host mode/trainer combinations reconstruct
the expected exact NEX and changed trainer operands.

## Evidence and limitations

The final generic `selftest --game martianoids --verify --stamp` passes on main
682f749: pinned assembly, all three exact rebuilds, bidirectional recolour of
4,720 map entries, complete bootstrap and ROM-path checks, and the 18,000-frame
recording. Default compares 5,872 hooks/R states and 288,620,544 RAM bytes;
Enhanced compares 5,875 hooks/R states, 288,768,000 RAM bytes and 2,936 complete
canvases (144,310,272 pixels). All comparisons pass; 448 ABI cases cover every
hook at four caller clocks, both IFF states and eight R values. The actual
recorded gameplay hooks are IFF0; the patch adds no gameplay interrupt blackout.

An additional controlled original last-life fixture starts at B6BF from a
recorded death state with zero reserve lives. Its 4,000-frame replay reaches
game-over, high-score initials, the menu and a new game: default 906 and Enhanced
914 complete hook comparisons, with 453 exact Enhanced canvases and eight hide
calls. Native original/default/Enhanced runs confirm those transitions, correct
overlay hiding and recovery, original-clock sound and four new reserve lives.
This fixture is supplementary evidence, separate from the archive-start stamp.

Nine deliberately broken runtime controls are rejected: position, opaque black,
mirror, colour, XOR, R, incoming clock, MMU and overlay hiding. 252 clipping
cases include unsigned x255 and the original 192-pixel row spill. A native
zero-wait publication control is rejected. DMA and CPU fallback modes give exact
canvases, registers/R and game RAM; an overfull draw list safely hides the overlay.
No dead original stack or game-RAM exclusions are permitted, apart from exact
emitted patch bytes. Complete persistent private hook/display state is retained.

Native archive-start soaks run 18,000 frames in each of original/default/Enhanced,
with moving gameplay, deaths and original-clock beeper writes. No AY writes occur.
Six v2.09 and three v2.10/26.11 real `.NEXCLASH` loader runs on disposable
card copies reconstruct the exact selected NEX and retain all six expected live
trainer operands. Final bare NEXs are also booted over both actual system ROM3
versions with and without NEXLOAD;
all original registers/R and 48K RAM match. A complete 18k-frame ROM-path audit
also passes separately against v2.10 ROM3 (SHA256 e93f444fe91e4eb3...). Original loading-screen bytes match
the supplied TAP exactly. The source overlay includes a clean rebuild recipe.

Known issues: the original low game-update rate and raster-phase variation
remain. No gameplay slowdown was observed in the documented quiet/busy matrix.
Missing: physical Next hardware testing. Review the frozen default and Enhanced
builds on the target hardware for startup, both colour modes, game-over/restart,
beeper sound and each trainer; report any failure with a recording.

## Lessons

- [local: actor transitions can redispatch within one player update] A8E1 jumps back to 9970 after collisions; use the unique outer-loop boundary 9967, not every player-record dispatch at 9974, for pace measurements.

- [local: the supported snapshot resumes BASIC before USR] The generic ROM-path check rejected a full code overlay that collided with the calculator. Keep the original ROM and tiny audited map-to-RAM veneers; test the actual archive startup, not only in-game fixtures.

- [local: the original initializer changes stored graphics once] Decode the mask/XOR initializer before painting; treating the archive's raw second byte as runtime ink inverts details.
- [local: the original renderer allows linear right-edge spill] Clip against the 192-pixel original buffer before translating to the 256-pixel display. Reject x beyond the viewport before an 8-bit x+width test can wrap.
- [local: colours must retain independent original bitmap state] Carry the original bit separately from colour so XOR-only source pixels still toggle correctly after owner painting.
- [local: archive trainers are not an execution proof] The sector RET consumed saved HL instead of a return address; use the existing protected-sector branch and test its stack.
- [tool martianoids.verify] Hook preludes rejoin the untouched original body with exact registers, R and 48K RAM. Keep hook state and both display pages persistent between calls.

## Technique use

- patch.pace-limiter: used the shared limiter on the sound-free original renderer.
- patch.restore-speed: used the incoming-clock latch on every accelerated path.
- verify.update-locked-pace: used matched player updates and sampled external inputs in separate scene/phase trials.
- detect.tracked-unit: helped identify player record 9690 and distinguish player updates from display copies.
- detect.drawing-parameters: helped recover source orientation, bottom-up rows and original mask/XOR semantics.
- detect.buffer-layout-producer: helped establish the 192-pixel work buffer and exact viewport before designing the colour canvas.

## Friction

- reuse: [tool martianoids.recolour] Use the existing colour-map read-back and NEX bank splicing; only original-art source pages are rewritten.
- retries: [local: native capture must finish its final frame] Immediate exit after requesting a screenshot returned an error despite valid timing data; allow frame completion and compare only completed update intervals.
- environment: [none: the private headless emulator and readonly base card worked] No desktop configuration or shared-card changes were needed.
- hand-rolled: [tool martianoids.verify] The replay harness is engine-specific; opcode emulation, Z80N, pace and DMA models remain shared.
- scratch: [local: disposable game analysis is retained as release evidence] Surveys, original-code disassemblies and trainer captures stay outside the contribution, with commands and status logs.

## Stage log

2026-11-07: intake, original continuous recording, exact geometry oracle,
approved first pass and owner import, default/Enhanced runtime, trainer repair,
native timing matrix and complete generic integration. Final generic selftest
and recolour pass, with the owner map preserved. Refreshed to main
682f749 with proofs stopped; reviewed incoming pace/card changes, and verified
the unused nested-pace addition leaves this runtime unchanged. The generic ROM
path gate exposed and then rejected the unsafe broad ROM overlay; sparse
entry/return veneers now pass all original ROM-read addresses.

## Next session

Stage: 3 complete in software; package and hardware review. Preserve the owner
painting PNG and layout. Use the private release manifest and source ZIP, with
this game record and its verified stamps, to prepare the contribution. Do not
replace the accepted owner colours or advertise hardware sprites. The extra
last-life fixture and native loader/pace evidence remain in the private run.
Physical hardware testing is outstanding; no pushes or shared-card writes were
made. Before future source changes, refresh main with proofs stopped, then run
the affected game checks and exact owner import/geometry validation.
