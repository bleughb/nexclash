; Phantis / Game Over 2, part 1 with Enhanced colours: the shared code is asm/phantis_core.inc.
        DEVICE ZXSPECTRUMNEXT
        DEFINE ENHANCED
G_PTR EQU 0xC903
G_ROWS EQU 0xC905
G_COLS EQU 0xC906
G_X EQU 0xC907
G_Y EQU 0xC908
G_SKIP EQU 0xC84B
G_SHIFTBUF EQU 0xE9DE
G_INK EQU 0xC910
G_MASK EQU 0xC911
G_COUNT EQU 0xC90F
G_CELLS EQU 0xE563
G_DE EQU 0xC903
G_BODY EQU 0xC6E2
G_SPSAVE EQU 0xC914
G_PUBRET EQU 0xC97A
G_XOFF EQU 3
G_WIDE EQU 26
G_TABLE EQU 0xB5B8
G_LOOP EQU 0xC932
COPY_ROWS EQU 135
G_WEND EQU 0xFE00+30*14+26
COPY_N2 EQU COPY_ROWS-80
K_PLOT EQU 89
R_PLOT EQU -22
R_COPY EQU 53
R_CLS EQU -13
        INCLUDE "phantis_core.inc"
        ALIGN 16
h_cls1:
        CLS_HOOK 0xC605
        ALIGN 16
h_cls2:
        CLS_HOOK 0xC615
        ALIGN 16
h_cls3:
        CLS_HOOK 0xC6D1
rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3A00
        SAVEBIN "phantis1e_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x69,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x12,L2_BANK_A
        nextreg 0x17,0
        nextreg 0x16,0
        nextreg 0x1C,1
        nextreg 0x18,24
        nextreg 0x18,231
        nextreg 0x18,8
        nextreg 0x18,127
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,l2_pal
        ld b,16
.lp:    ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .lp
        ld hl,l2_pal256         ; the whole palette: 16 Spectrum colours, then the set's
        nextreg 0x40,0
        ld b,0
.pl:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pl
        nextreg 0x40,254
        nextreg 0x41,0xE3
        nextreg 0x41,0xE3
        nextreg 0x43,0
        ; both buffers transparent: 4 pages (rows 0..127) each
        ld d,L2_BANK_A*2
        call .fill
        ld d,L2_BANK_B*2
        call .fill
        nextreg 0x50,255
        ret
.fill:  ld e,4
.pg:    ld a,d
        nextreg 0x50,a
        ld hl,0
        ld (hl),0xFF
        push de
        ld de,1
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        ret
l2_pal: defb 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        defb 0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
l2_pal256:
        defs 512,0              ; filled by the build from the colour table
setup_end:
        SAVEBIN "phantis1e_setup.bin",setup,setup_end-setup
