; Bubbler: original drawing in a sound-free span. Enhanced is not built here.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"
        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x3F00
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        ENDM
        MACRO EXIT delta, target
        ld a,delta
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp target
        ENDM
h_open:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_pace_open
        EXIT -12,0xAC40
h_close:
        ENTER
        ld a,(V_SPEED)
        ld c,a
pace_k:
        ld a,103
        call hlib_pace_waitk
        HLIB_SPEED_OUT V_SPEED
        EXIT -12,0xA837
boot_resume:
        nextreg 0x51,HOOK_PAGE
        ld sp,0x3F00
        push af
        push bc
        push de
        push hl
        ld hl,0x3C00
        ld de,0x5B00
        ld bc,256
        ldir
boot_decode:
        jp 0xF000
boot_decode_done:
        ld hl,0x5E00
        ld (0xF010),hl
        pop hl
        pop de
        pop bc
boot_r:
        ld a,0
        ld r,a
        pop af
boot_sp:
        ld sp,0
        nextreg 0x51,255
boot_jump:
        jp 0
rom_end:
regblock:
        defs 32,0
        ASSERT $ < 0x3C00
        SAVEBIN "bubbler_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
        ret
        SAVEBIN "bubbler_setup.bin",setup,$-setup
