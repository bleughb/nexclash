# Moley Christmas (Gremlin for Your Sinclair, 1987)

## Next session

Stage 0 intake complete. Stage 1 stopped at feasibility on 2026-11-28. The plain conversion plays. The three published Monty engines do not supply an address-map port. A dedicated renderer and verifier are needed before a clash-fixed build can go to the owner.

Branch `add-moley-christmas`, base `3f3f1446eca4`. Inputs are in `NEXCLASH_REFERENCE/moley_christmas/`. The run folder is `NextTang-evidence/2026-11-02-nexclash/pilot/runs/moley_christmas/to-test/`. It holds the survey, original-room contact sheet, OverSpec captures and reproducible probes. Start there with `python layout_probe.py` using the checkout on PYTHONPATH and the pilot interpreter. See PLAYBOOK stage 1, section 3d.

## Intake and caller coverage

The 48K collection Z80 starts at the title in IM 2, PC 0x5F5F, SP 0x5DFA. The archive RZX starts on a +2 at the same PC. Its title text identifies the Monty game given to Your Sinclair readers. The 728 bytes from 0x87C4 through 0x8A9B match exactly between the RZX, the Z80 and the tape. Both archive copies have MD5 `112442ee33259dbbf9cec3e11e499d30`. They are one recording.

The original replay completed 8,455 input frames in one segment with zero desyncs. It visited room IDs 0 through 5 and the ending at ID 6. The survey reported 8,456 frame boundaries and 8,455 interrupts. Its plain conversion used the checked tail at 0x5B00 and passed register, RAM, ROM-view and paging checks. The 66,048-byte plain NEX has MD5 `d7de7729a514560d720b1a6a27849470`. A direct OverSpec UI run reached the title and first room with keyboard input.

The archive reached two of four CALL sites for 0x87C4, with 4,004 normal updates and one ending transition. The untrained 366-frame ordinary-death branch reached the other two sites, 0x95AA three times and 0x95B7 once. It also reached the survey's one flagged room-redraw caller, 0x936B, once. Together they cover 4/4 renderer and 8/8 surveyed room-redraw CALL sites. The figure plotter 0x8931 has one direct caller at 0x888B.

## Feasibility

Ten consecutive instructions from each published patch site were compared at every candidate address in mapped RAM, with numeric operands masked. None of the 4 Auf Wiedersehen Monty, 8 Monty on the Run or 3 Monty is Innocent sites matched. Inside the Auf figure routine, 24 of 244 instructions occurred in matching runs of at least eight. The longest run was 16 instructions around a shift ladder. Neither the record loop nor the attribute painter moved with it.

Moley restores 3 by 3 background cells, then plots eight four-byte records at 0x8121 into a shared bitmap at 0xE000. The bytes specify x, y, image number and flags. At 0x8931, the source is 0xC000 + 32 times the image number. A row takes bytes 16 apart. Flag bit 7 selects orientation. Rooms 0 through 4 use the 0xFF00 mask table and OR. Room 5 uses plain OR. The dirty-cell loop publishes to the ULA. Auf uses five 13-byte records with a colour field, adjacent source bytes per row and per-record composite cells.

The archive exercised all eight slots on each of 4,005 updates. Of 32,040 plots, 7,819 referenced blank images. All 24,221 nonblank plots (81 distinct nonblank image numbers) would decode differently with Auf's adjacent-byte row order, even after correcting the image base. For 6,633 nonblank plots, the source ink bits landed over multiple ULA ink or brightness values within the visible playfield. This measures underlying cell attributes before masking. It does not identify an intended colour for any figure.

The renderer wrote 2,134,984 bitmap bytes and zero attribute bytes. The pickups have a separate path. The replay cycled attributes at 0x8659 2,953 times and reached the collection store at 0x869F 14 times. The figure plotter alone cannot account for these pickups. The XOR overlay card requires XOR composition. Neither its parity test nor Auf's painter removal supplies the pixel or colour check needed here.

The main loop waits at HALT 0x822B. The measured renderer cost was 108,764 T-states median and 181,196 maximum. The IM 2 handler used up to 40 stack bytes and read interrupted IY. There is no measured update budget for extra sprite work. DMA or core-gated DDMA could transfer prepared patterns, but neither decodes the bit planes or separates actor ink from scenery. Transfer cost, fallback, interrupt safety and whole-hook timing remain open.

The next experiment is to compare a host decoder against the actual 0x8931 writes before and after each plotted row. Exercise both orientations, both room paths, overlapping slots and death redraws. Account for masked ink, opaque black and transparency. Require zero unexplained pixel differences. Trace each pickup from colour cycling through collection. Only then size the sprite upload and measure missed updates with all eight slots active.

## Cheats and patch target

The collection has one trainer, Infinite Lives, with two zero writes. Both sites immediately follow a load of HL with the life counter at 0x810C. The Z80, SNA, archive start and TAP all contain NOP at 38302 and DEC (HL) at 38352. The tape has four blocks, with one 40,960-byte code payload named `pokebyrudy` and zero standalone SCREEN$ blocks. Its MD5 is `c9456d09021802a7f409de4c96c8ca83`. No independent clean master was established.

| Machine-played branch | Frames per run | Trainer off | Trainer on |
|---|---:|---|---|
| No input from archive frame 1,050, ordinary death | 366 | 5 lives → 5 | 5 lives → 5 |
| Hold X from archive frame 5,823, room 3 trap | 116 | 5 lives → 4 | 5 lives → 5 |

All four recordings replayed through the death routine's exit, with zero desyncs. Retain Infinite Lives as one candidate toggle. On these files only the write at 38352 changes a byte. Omit the redundant write at 38302 for this target. Zero trainers shipped. Before claiming stock trainer-off behaviour, establish the ordinary-death byte from an independent original. Do not invent a replacement opcode.

## Owner design and hardware checklist

The first release calls for hardware sprites for all moving figures, effects and applicable pickups, original colours and black lines, no white outline, original screen reads and pace, automap off and all 128 sprite slots initialised. Cheats start off. Enhanced colours are deferred. The reference copy is the original game in NEX form.

For a future patched build, test cold and dirty-sprite boot, movement past coloured scenery in all six rooms, disappearing pickups, both deaths and the ending. Check the timer and music against the original and watch for flicker or stale sprites at room changes. Exercise trainer off and on through the actual NXC menu. Patched gameplay, loading-screen selection and board behaviour remain untested.

## Lessons

- [local: renderer] A shared shift ladder survives across these Monty games while record stride, row layout, masking and colour ownership change.
- [local: input provenance] Four supplied start sources share a pre-existing NOP on the first death path. Replaying the second death distinguishes the only effective archive write.

## Friction

- reuse: [local: the published engines and their patch sites supplied the comparison set]
- retries: [local: a death-free archive run needed two short keyboard branches to cover both trainer sites]
- environment: [local: the recording uses a +2 and the plain conversion uses the 48K collection title]
- hand-rolled: [local: the layout probe compares the two source-byte orders for each nonblank plot]
- scratch: [local: game-specific probes and play captures are retained in the evidence folder]

## Technique use

- detect.graphics-record-layout: helped: the live IX values and the row loads at 0x8972 and 0x8975 exposed the four-byte stride and separated image halves.
- patch.xor-overlay-keep-ula: no help: the renderer masks and ORs into a back buffer, then copies dirty cells to the ULA.

## Stage log

2026-11-28. Stage 0 intake and Stage 1 feasibility, about ten minutes, one session and zero clarification rounds. The address-map route stopped at the renderer comparison.
