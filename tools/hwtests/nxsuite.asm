; nxsuite.asm - one .nex that answers the open hardware claims (GPL-3.0-or-later, part of nexclash).
; Build: python tools/hwtests/build.py nxsuite -o OUTDIR   (build.py runs nxsuite_gen.py first: the test
; table from nxsuite_claims.json, z80ntest's cases for G2, the 48K system variables image) and copies
; the include folder tools/hwtests/nxsuite/.
;
; What it does: a menu (one group, RUN ALL unattended, RESUME after a hang), every test writes one result
; line into a text buffer that is written to NXSUITE.TXT in the folder the .nex was started from (esxDOS
; through RST 8, convention of asm/inferno_hooks.asm sd_esx) at every group end; NXSUITE.PRG (progress
; record) is written before every test that could hang, so the next start resumes and marks it
; HANG-GUARD. Format: tools/hwtests/README.md "nxsuite" and the intake tool tools/hwtests/intake.py.
;
; Memory (1 MB board safe; nothing at or above page 96 is written, except M05's one probe of page $E0):
;   bank 5  $4000 screen; $5B00 printer-buffer pattern (test S00); $5C00 48K system variables image;
;           $5D00 line buffer; $5E00 extras buffer; $5F00 variables; $6000 z80ntest window (G2);
;           $6400 NextReg snapshot; $6500 progress record; $6600 work; $6800 bank-5 timing code (C02);
;           $7000 results table "NXS1"; $7800 G2 records; $7E00 "NXHT" (G2 / G3); $7FFF done flag $A5
;   bank 2  $8000 code that must not move with slots 6/7 (timing core, file I/O, G2, G9);
;           $B000 timing blocks; $B800 result file parts code (txt2); $BC00-$BFFF stacks (SP $BE00; G2 timing $BFE0)
;   bank 0  $C000-$DFFF harness, menu, G0, test table; $F000-$F7FF scratch (page 1)
;   pages 40-43 + 60 + 63 slot 7 overlays (40 G2 extras + G4, 41-42 G3, 43 G5 + G8, 60 G1 below $F000 -
;           C15 copies to $F000 -, 61 G7, 63 G6; X-T after G7, X-D after G1, X-H after G6, V after G3;
;           more V tests in 40 $F200, 43, 60 and 63 $FD02 by the test table's page number),
;           $F800-$FFFF their own area;
;           36-39 DMA / G9 scratch, 44-53 Layer 2, 54 sprites, 55 alt ROM image
;   pages 32-35 + 58-59 result text (48 KB), 56-57 G1 data / G2 slot 6-7 sandbox, 62 strings

        DEVICE ZXSPECTRUMNEXT
        OPT --zxnext

        INCLUDE "nxsuite/defs.asm"

; ---------------------------------------------------------------- bank 5 data
        ORG $5B00
pbuf_pat:
        DUP 256, i
        db (i*7+$11) & $FF
        EDUP
        ORG $5C00
        INCLUDE "nxsuite_sysvars.inc"

; ---------------------------------------------------------------- bank 2: fixed code
        ORG $8000
start:  di
        jp entry
; the ROM font ($3D00-$3FFF, a read: reads never automap) and ROM $0000-$0007 copied to page 62 at start, so
; the suite's screens never depend on what is mapped over $0000-$3FFF (board run 8: DivMMC left mapped)
fontinit:
        nextreg $53,STRPAGE
        ld hl,$3D00 : ld de,FONTC : ld bc,768 : ldir
        ld hl,0 : ld de,ROM8C : ld bc,8 : ldir
        nextreg $53,$0B : ret
; HL = glyph in the copy (slot 3 view), DE = screen -> 8 rows; slot 3 put back as it was
fontcp: ld a,$53 : call rdreg : push af : nextreg $53,STRPAGE
        ld b,8
.l:     ld a,(hl) : ld (de),a : inc hl : inc d : djnz .l
        pop af : nextreg $53,a : ret
; a new build: the hung list emptied (board run 10: XD stayed SKIP why=hung-last-run on every later pass)
hung_clr:
        ld hl,PRGB+PRG_HUNG : ld b,12
.h:     ld (hl),$FF : inc hl : djnz .h
        ret
; the start after XH2's reset (prg_read2 set PRG_XH2): the follow-up question and the start's DMA byte
; recorded at once, as a one-group pass of XH with XH2 only (board run 9: the restart was taken as a resume
; between tests and the question never came). Then DONE as any pass.
do_xh2f:
        xor a : ld (resume_pending),a
        ld a,GI_XH+1 : ld (mode),a
        call pass_mark
        ld a,GI_XH : ld (curg),a : call gent
        ld a,(ix+0) : ld (gfirst),a : ld a,(ix+1) : ld (gcount),a
        call gscreen
        ld a,1 : ld (retrying),a
        ld a,TI_XH2 : call run_test_marked
        xor a : ld (retrying),a
        jp run_end
        ; G2 JP (C) edge case: a JP (C) at $BFFE that took its base from its own address lands here
        ; (z80ntest's wrongpc: A = $FF, back through IX)
        ds $8140-$
wrongpc: ld a,$FF : jp (ix)
        INCLUDE "nxsuite/core.asm"
        INCLUDE "nxsuite/g2.asm"
        INCLUDE "nxsuite/g9.asm"
        INCLUDE "nxsuite/opr.asm"
        INCLUDE "nxsuite/xtb2.asm"
; G7's two $7FFD rows (they page bank 0 into slots 6 / 7) and the way it measures them
        INCLUDE "nb_far.inc"
g7far:  call measure
        nextreg $56,G7P6 : nextreg $57,OVL_G7
        ret
g7ret:  ret
code2_end:
        ASSERT code2_end <= TBUF
        ORG CODE2B
        INCLUDE "nxsuite/txt2.asm"
        INCLUDE "nxsuite/vh2.asm"
txt2_end:
        ASSERT $ <= CODE2B_END

; ---------------------------------------------------------------- bank 0: harness and the other groups
        ORG $C000
        INCLUDE "nxsuite/harness.asm"
        INCLUDE "nxsuite/g0.asm"
        INCLUDE "nxsuite_tests.inc"
        ; (the include ends in the string page: MMU 6,STRPAGE / ORG $C000)

; ---------------------------------------------------------------- slot 7 overlays
; The harness maps a group's page into slot 7 ($E000-$FFFF) around each of its tests (gtab byte 7,
; from OVL_<group> below) and the home page (HOMEP7) again before writing the line. Code from $E000;
; the top of the page is that group's interrupt / scratch area. Overlay pages are 40-43 and 63 (spec 1.2
; gives the suite pages 32-63: text 32-35 + 58-61, DMA scratch 36-39, Layer 2 44-53, sprites 54,
; alt ROM 55, data / sandbox 56-57, strings 62). Two groups may share a page.
OVL_G2  equ 40                  ; G2 extras and G4 share page 40 (Z04 uses $F000-$F1FF of it)
OVL_G4  equ 40
OVL_G3  equ 41                  ; G3: tables at $F800-$FFFF
OVL2_G3 equ 42                  ; G3 tests in g3b.asm (flag 8 in the test table: group page + 1)
OVL_G5  equ 43                  ; G5 COPPER (P08 keeps a palette copy at $F600)
OVL_G8  equ 43                  ; G8 SPRITES shares page 43 with G5
OVL_G6  equ 63                  ; G6 DMA (program buffer $F700)
OVL_G1  equ 60                  ; G1 CPU (below SCRATCH: C15 copies 1 KB to $F000)
OVL_G7  equ 61                  ; G7 BENCH (nextbench rows; slot 6 = page 38 during a row)
OVL_V   equ 41                  ; V VISUAL shares page 41 with G3 (G3's tables: $F800-$FFFF)
OVL2_V  equ 42                  ; V tests in gv2.asm, after g3b.asm on page 42 (flag 8)
OVL_XT  equ 61                  ; X-T after G7 on page 61
OVL_XD  equ 60                  ; X-D after G1 on page 60
OVL_XH  equ 63                  ; X-H after G6 on page 63 (IM2 table $FC00)
OVLX_1  equ 40                  ; V tests in gv3.asm at $F200-$FCFF of page 40 (Z04: $F000-$F1FF, F05: $FD00-)
OVLX_2  equ 43                  ; V tests in gv4.asm after G5 / G8 (test table flags bits 5-7 = k: page OVLX_k)
OVLX_3  equ 61                  ; V tests in gv5.asm after G7 / X-T
OVLX_4  equ 63                  ; V tests in gv6.asm at $FD02 (above X-H's IM2 table and vector)
        MMU 7,OVL_G2
        ORG $E000
        INCLUDE "nxsuite/g2b.asm"
        INCLUDE "nxsuite/g4.asm"
g4_end:
        ASSERT $ <= $F000
        MMU 7,OVL_G3
        ORG $E000
        INCLUDE "nxsuite/g3.asm"
        INCLUDE "nxsuite/gv.asm"
gv_end:
        ASSERT $ <= $F800
        MMU 7,OVL2_G3
        ORG $E000
        INCLUDE "nxsuite/g3b.asm"
g3b_end:
        ASSERT $ <= $F800
        MMU 7,OVL2_V
        ORG g3b_end
        INCLUDE "nxsuite/gv2.asm"
gv2_end:
        ASSERT $ <= $F800
        MMU 7,OVL_G5
        ORG $E000
        INCLUDE "nxsuite/g5.asm"
        INCLUDE "nxsuite/g8.asm"
g58_end:
        ASSERT $ <= G5PAL
        MMU 7,OVL_G6
        ORG $E000
        INCLUDE "nxsuite/g6.asm"
        INCLUDE "nxsuite/gxh.asm"
gxh_end:
        ASSERT $ <= G6P
        ORG G6P+$48                     ; G6 uses $F700-$F747 only
        INCLUDE "nxsuite/gxhtxt.asm"
gxhtxt_end:
        ASSERT $ <= XHT
        MMU 7,OVL_G1
        ORG $E000
        INCLUDE "nxsuite/g1.asm"
        INCLUDE "nxsuite/gxd.asm"
gxd_end:
        ASSERT $ <= SCRATCH
        MMU 7,OVL_G7
        ORG $E000
        INCLUDE "nxsuite/g7.asm"
        INCLUDE "nxsuite/gxt.asm"
gxt_end:
        ASSERT $ <= $10000
        MMU 7,OVLX_1
        ORG $F200
        INCLUDE "nxsuite/gv3.asm"
gv3_end:
        ASSERT $ <= F5T
        MMU 7,OVLX_2
        ORG g58_end
        INCLUDE "nxsuite/gv4.asm"
gv4_end:
        ASSERT $ <= G5PAL
        MMU 7,OVLX_3
        ORG gxt_end
        INCLUDE "nxsuite/gv5.asm"
gv5_end:
        ASSERT $ <= $10000
        MMU 7,OVLX_4
        ORG $FD02
        INCLUDE "nxsuite/gv6.asm"
gv6_end:
        ASSERT $ <= $10000
        MMU 7,HOMEP7

        ; bank 7 (pages 14 / 15) in the .nex, so tests C03 / C04 time code in pages the suite owns
        MMU 3,14
        ORG $6000
        db "NXS7"
        MMU 3,15
        ORG $6000
        db "NXS7"
        MMU 3,11
        MMU 6,0

        SAVENEX OPEN "nxsuite.nex", start, MSTACK
        SAVENEX CORE 3,0,0
        SAVENEX CFG 0,0,0,0
        SAVENEX AUTO
        SAVENEX CLOSE
