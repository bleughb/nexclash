; Phantis / Game Over 2, part 2: the shared code is asm/phantis_core.inc.
        DEVICE ZXSPECTRUMNEXT
        DEFINE PART2
G_PTR EQU 0xC984
G_ROWS EQU 0xC986
G_COLS EQU 0xC987
G_X EQU 0xC988
G_Y EQU 0xC989
G_SKIP EQU 0xC8C5
G_INK EQU 0xC991
G_MASK EQU 0xC992
G_COUNT EQU 0xC990
G_DE EQU 0xC984
G_BODY EQU 0xC75C
G_BODY2 EQU 0xC999
G_DTABLE EQU 0xB5A4
G_CLEAN EQU 0xEF3C
G_WORK EQU 0xFE00
G_XOFF EQU 2
G_WIDE EQU 28
K_PLOT EQU 107
K_COPY EQU 142
R_PLOT EQU -22
R_COPY EQU -22
R_CLS EQU -13
        INCLUDE "phantis_core.inc"
        ALIGN 16
h_cls1:
        CLS_HOOK 0xC74E
        ALIGN 16
h_cls2:
        CLS_HOOK 0xFBF8
        ALIGN 16
h_cls3:
        CLS_HOOK 0xBA72
rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3A00
        SAVEBIN "phantis2_rom.bin",rom_start,$-rom_start
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
        nextreg 0x18,16
        nextreg 0x18,239
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
setup_end:
        SAVEBIN "phantis2_setup.bin",setup,setup_end-setup
