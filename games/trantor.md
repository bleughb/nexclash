# Trantor - The Last Stormtrooper (Go!, 1987)

## Next session

Stage 1, feasibility. The original Go! 48K snapshot and a local trainer diagnostic boot. Two ways of obtaining clean scenery failed the pixel comparison. The release needs a Trantor-specific renderer.

Branch add-trantor, base e759250f9b9cefa084dae213ea4c6e4fd4c9a1ea. Inputs live under reference-local/trantor. The pilot run directory is runs/trantor/to-test. No design answers are pending. Start with background_probe.py there and the five callers of 0xD53A. Review the two failing comparisons below before writing a hook.

## Inputs and boot

The patch target is Trantor - The Last Stormtrooper (1987)(Go!).z80, MD5 50c665e674e5831125889f5e89ff2eec. Entry PC 0x700D, SP 0x75EF, IM 2, interrupts enabled. The archive RZX starts at PC 0xFBFA, SP 0xFA19, IM 1, interrupts disabled. Its packed start differs from the target in 46,471 of 49,152 RAM bytes. After 1,000 recorded frames all 14,848 bytes at 0xC000-0xF9FF match the target, including all five archive trainer sites. This comparison covers that address range only.

- Archive trantor.rzx, 24,840 frames, with trantor_start.z80. The full trace stayed in sync.
- trantor_idle.rzx, 2,700 frames, with trantor_idle_start.z80. Release the controls at the frame-6000 checkpoint for an ordinary death. All eight death-path entries checked in record_death.py were reached.
- trantor_contact.rzx, 456 frames, with trantor_contact_start.z80. Release the controls at the frame-9540 checkpoint. Class 14 hits Trantor within 56 frames. Both continuations replay to their declared lengths.
- The tape has six blocks with valid XOR checksums. The CODE block at offset 166 loads 6,942 bytes at 0x4000. The first 6,912 payload bytes start at offset 169. The extracted trantor.scr has MD5 3bf7fd570e1270535951ae6c4b43dc3b.

The archive start fits a 79-byte tail at 0x5C7B-0x5CC9. All 80 bytes in the scanned range through 0x5CCA were written first. The TOSEC start fits an 80-byte tail at 0x758F-0x75DE. In 3,000 idle frames all 80 bytes were untouched. Both plain diagnostics passed normal and NEXLOAD boot simulation with printer-buffer restoration and DivMMC automap off.

The TOSEC diagnostic patch uses the plain build with no embedded printer-buffer copy. Its boot bank otherwise duplicates 256 bytes including original loader code. With the ordinary converter, NEXLOAD left 333 initial RAM differences including the tail. A paired run through intro, menu and play had equal registers and equal RAM outside those two areas at all 4,500 frame boundaries. By the end, zero printer-buffer bytes differed. The trainer diagnostic uses zero game-bank patch sites and takes all three game RAM banks from the player's snapshot.

## Feasibility

The original copies 4,096 playfield bytes from 0x6400 and 512 attribute bytes from 0x6100. The destination is screen rows 64-191. The 0xCEB0 fingerprint is the unrolled LDI transfer used in Everyone's a Wally and Three Weeks in Paradise. Their figure code has a different layout.

The player has a 40 by 64 masked image, with two facings and a 320-byte save area at 0x7401. Five 14-byte object records start at 0xFBB8. Ordinary objects use XOR at 0xEC1A. Their ink save/write and restore paths use 0xEC2C and 0xEC71. Frames 28-31 use the larger masked plot instead. The recording reached that special dispatcher 37 times, with 26 direct-facing and 11 mirrored draws. Single-pixel particles use another XOR at 0xDE1B. The collected shield ORs noise into the player rectangle at 0xEB11. The opening ship also uses a direct-screen plotter in the low-memory intro overlay.

| Clean-background test | Result |
|---|---|
| Restore the player's saved rectangle and compare the full playfield with the pre-object image at 0xEA36 | 2,362 of 2,432 in-range ordinary copies still contained differences. Total 535,903 pixels, worst 1,125. Ten further player rectangles extended beyond the tested buffer bounds. |
| Capture scenery at 0xEA36 and reuse it across every copy to the ULA | All 49 ordinary-death particle backgrounds matched. The 12 title particle copies preceded the first capture. Scenery outside the player rectangle was wrong in 68 of 116 ending-wipe copies, totalling 289,818 pixel differences, worst 4,735. |
| Give each distinct particle position a hardware sprite | 15 of 49 death copies exceeded 128 slots. Peak 172 distinct positions. Binning by aligned 16-pixel squares would need at most 57 occupied tiles in this trace. Pixel overlap, appearance, upload cost and pace still need proof. |

These measurements are host comparisons of original gameplay. The zero-error criterion for a reusable clean background failed twice. The next experiment needs separate background updates for the title, normal play and the ending dissolve, plus grouped particles. Compare against the original at each of the five copy sites, including clipping at the playfield boundary. Keep the original game buffers available to its readers.

The original took 23,126 interrupts in 24,840 frames. The IM 2 handler updates the timer and drives the beeper. In a 501-frame gameplay slice the player draw returned 84 times, median 41,220 T. The screen copier returned 84 times at 84,467 T each, excluding interrupt work. These are original costs. The 24.13 ms copier spans more than one 50 Hz frame. A DMA transfer spanning the copy must account for interrupt and sound timing. For grouped sprite uploads, benchmark the CPU fallback against a core-gated DDMA implementation including setup, bank selection and waits. An available upload budget has yet to be measured.

## Trainers

All six options start off. The first five are from the archive. Two menu labels describe their measured scope. The sixth came from tracing the shield pickup and countdown.

| Diagnostic menu option | Original instruction and change | Measured effect |
|---|---|---|
| Infinite energy | 0xDD14, INC A to NOP | Used-energy count changed from 1 to 2 without the cheat and stayed at 1 with it. |
| Infinite time | 0xDD87, DEC A to NOP | The timer changed from 90 to 89 without the cheat and stayed at 90 with it. |
| Infinite ammo | 0xD3DC, INC A to NOP | Used ammunition changed from 1 to 2 without the cheat and stayed at 1 with it. |
| Stop enemy respawns (archive name No Enemies) | 0xCD22, DEC A to NOP | Over 800 frames the spawn routine ran in 48 frames off and one frame on. A zero initial cooldown still permits the first spawn. |
| Block lethal contact (archive name Immunity) | 0xEE50, LD A,(0xFB6B) to RET at the first byte | Over 456 frames, one class-14 contact reached game over with the cheat off. With it on, 30 contact frames returned and none reached game over. Ordinary damage has a separate path. |
| Keep collected shield | 0xEAF1, DEC A to NOP, decimal POKE 60145,0 | After a real pickup, shield status was nonzero for 826 of 2,400 control frames and all 2,400 cheat frames. Final counter 0 off and 128 on. The timer can still end the game. |

All 64 selections rebuilt every expected NEX bank and preserved the loading screen. Each ran for 350 frames from the same gameplay checkpoint, reached the gameplay loop and used the same input schedule. These runs cover 22,400 diagnostic frames. Separate paired tests above check effects that do not occur in a short combination run. No archive POKE was dropped. Priority for the shield discovery beyond the supplied archive is unknown.

## Release design and hardware checklist

The owner's design keeps original colours and black lines, includes moving actors, pickups and effects, and adds no white outline. HUD and menus keep their original display. Enhanced colours are deferred. DivMMC automap is off. The intended sprite setup is 128 slots. Gameplay memory, original pace, interrupts and sound are acceptance criteria.

The local trainer-menu diagnostic exercises build_screen=nex with the tape artwork. The release still needs an integrated sprite profile, original-versus-patched replay, collision and screen-read checks, pixel comparisons and a measured pace comparison. Hardware checks after integration should cover the intro, both facings, enemies crossing the player, shield pickup, firing, death particles, terminal, menu and ending wipe. Check input, sound, game time and both DMA routes on a Next.

## Lessons

- [local: Trantor ending] Scenery dissolves outside the player rectangle at 0xD604. A clean background captured in the normal actor loop becomes stale.
- [local: Trantor particles] Distinct death particle positions peak at 172. A grouped pattern needs an overlap and clipping test before slot usage alone can justify it.

## Technique use

- detect.buffer-layout-producer: helped: identified the separate pixel and attribute writers behind the repeated LDI.
- detect.routine-removal: helped: informed the save-under and background-latch comparisons.
- detect.pacing-structure: helped: identified the interrupt-driven timer and beeper alongside an update lasting several frames.

## Friction

- reuse: [local: the final LDI sequence matches the published games]
- retries: [local: a second background capture test exposed ending scenery changes]
- environment: [local: OverSpec UI time includes the full opening sequence]
- hand-rolled: [local: paired continuations isolated a lethal contact absent from the archive]
- scratch: [local: diagnostic scripts and measurements retained in the pilot evidence folder]

## Stage log

2026-11-28. Stage 0 survey reviewed. Stage 1 boot, trainer and rendering feasibility measured. Two natural-input continuations and a trainer diagnostic retained. One session, about 15 minutes, zero user rounds.
