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
;   bank 2  $8000 code that must not move with slots 6/7 (timing core, file I/O, G1, G2, G9);
;           $B000 timing blocks; $B800 result file parts code (txt2); $BC00-$BFFF stacks (SP $BE00; G2 timing $BFE0)
;   bank 0  $C000-$DFFF harness, menu, G0, test table; $F000-$F7FF scratch (page 1)
;   pages 40-43 + 63 slot 7 overlays (40 G2 extras + G4, 41-42 G3, ...), $F800-$FFFF their own area;
;           36-39 DMA / G9 scratch, 44-53 Layer 2, 54 sprites, 55 alt ROM image
;   pages 32-35 + 58-61 result text (64 KB), 56-57 G1 data / G2 slot 6-7 sandbox, 62 strings

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
        ; G2 JP (C) edge case: a JP (C) at $BFFE that took its base from its own address lands here
        ; (z80ntest's wrongpc: A = $FF, back through IX)
        ds $8140-$
wrongpc: ld a,$FF : jp (ix)
        INCLUDE "nxsuite/core.asm"
        INCLUDE "nxsuite/g1.asm"
        INCLUDE "nxsuite/g2.asm"
        INCLUDE "nxsuite/g9.asm"
code2_end:
        ASSERT code2_end <= TBUF
        ORG CODE2B
        INCLUDE "nxsuite/txt2.asm"
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
        MMU 7,OVL_G2
        ORG $E000
        INCLUDE "nxsuite/g2b.asm"
        INCLUDE "nxsuite/g4.asm"
        ASSERT $ <= $F000
        MMU 7,OVL_G3
        ORG $E000
        INCLUDE "nxsuite/g3.asm"
        ASSERT $ <= $F800
        MMU 7,OVL2_G3
        ORG $E000
        INCLUDE "nxsuite/g3b.asm"
        ASSERT $ <= $F800
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
