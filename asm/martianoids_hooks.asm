; Martianoids: preserve the original complete renderer, accelerate only its
; sound-free span and return at its original pace. Original graphics untouched.
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
        INCLUDE "lib/hlib_dma.asm"

; Both entry points are identical in the hidden ROM and the writable page.
; No CALL is inserted around the original bodies: their SP and return address
; are unchanged. The page is restored before jumping into original code.
        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x3F00
        push af
        ld a,r
        ld (HLIB_V_R),a
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
        EXIT -12,0xBF22

        defs 0x2D52-$,0
h_close:
        ENTER
        ; The span has no sound or input. K is independently measured in the
        ; native emulator; target accounting excludes wrapper entry/exit cost.
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld a,104
        call hlib_mul8
        ld (V_TARGET),hl
        ld a,(V_ENH)
        or a
        call nz,colour_frame
        ld hl,(V_TARGET)
        ld a,(V_SPEED)
        call hlib_pace_wait
        HLIB_SPEED_OUT V_SPEED
        EXIT -12,0xA739

        defs 0x2DC1-$,0
h_hide:
        ENTER
        nextreg 0x69,0
        EXIT -12,0xB1A3

h_hide_view14:
        ENTER
        nextreg 0x69,0
        EXIT -12,0xB1C2
h_hide_view20:
        ENTER
        nextreg 0x69,0
        EXIT -12,0xB1D6

        INCLUDE "martianoids_colour.inc"

boot_resume:
        di
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
        ld hl,0x3900
.restore_screen:
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,d
        or e
        jr z,.screen_done
        ld a,(hl)
        inc hl
        ld (de),a
        jr .restore_screen
.screen_done:
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
boot_iff:
        di
boot_jump:
        jp 0

rom_end:
regblock EQU 0x3B00
        ASSERT $ < 0x3100
        SAVEBIN "martianoids_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
setup_enhanced:
        ld a,0
        or a
        ret z
        nextreg 0x69,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x43,0x10
        nextreg 0x51,HOOK_PAGE
        nextreg 0x40,0
        ld hl,0x3D00
        call setup_palette
        nextreg 0x40,128
        ld hl,0x3D00
        call setup_palette
        nextreg 0x40,255
        nextreg 0x44,0xE3
        nextreg 0x44,1
        nextreg 0x51,255
        nextreg 0x12,16
        ret
setup_palette:
        ld b,32
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .lp
        ret
setup_end:
        SAVEBIN "martianoids_setup.bin",setup,setup_end-setup
