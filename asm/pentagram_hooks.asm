; Pentagram original presentation: bounded original renderer at 28MHz, paced return.
; Full Sinclair ROM + mirrored writable hook page. Game pixels and original drawing stay intact.
        DEVICE ZXSPECTRUMNEXT
HLIB_V_R EQU v_r
HLIB_V_PACE EQU v_pace
HLIB_PACE_NL EQU 312
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        MACRO SAVE
        push af
        push bc
        push de
        push hl
        ENDM
        MACRO RESTORE
        pop hl
        pop de
        pop bc
        pop af
        ENDM
        MACRO FINISH delta
        push af
        ld a,delta
        call hlib_r_set
        pop af
        HLIB_R_OUT
        ENDM
        ORG 0x2000
        INCLUDE "lib/hlib_r.asm"
h_render:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        HLIB_SPEED_IN v_speed
        call hlib_pace_open
        ld a,1
        ld (v_active),a
        RESTORE
        ld (v_hl),hl
        ld hl,h_render_after
        ex (sp),hl
        ld hl,(v_hl)
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xB19E
h_render_after:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        ld a,(v_speed)
        ld c,a
        ld a,RENDER_K
        call hlib_pace_waitk
        xor a
        ld (v_active),a
        HLIB_SPEED_OUT v_speed
        RESTORE
        ; Drop the trampoline frame while keeping HL. FINISH may reuse this dead stack.
        push hl
        ld hl,0xB03E
        ex (sp),hl
        inc sp
        inc sp
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xB03E
h_plot_tick:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        HLIB_SPEED_IN v_tick_speed
        ld a,(v_active)
        or a
        call nz,hlib_pace_tick
        HLIB_SPEED_OUT v_tick_speed
        RESTORE
        FINISH -10
        ld a,(ix+26)
        nextreg 0x51,0xFF
        ret

        MACRO COPY_HOOK P_ENTRY,P_RETURN,P_CONT
P_ENTRY:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        HLIB_SPEED_IN v_copy_speed
        RESTORE
        ld (v_hl),hl
        ld hl,P_RETURN
        ex (sp),hl
        ld hl,(v_hl)
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xB178
P_RETURN:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        HLIB_SPEED_OUT v_copy_speed
        RESTORE
        push hl
        ld hl,P_CONT
        ex (sp),hl
        inc sp
        inc sp
        FINISH -9
        nextreg 0x51,0xFF
        jp P_CONT
        ENDM
        COPY_HOOK h_copy_room,h_copy_room_after,0xB078
        COPY_HOOK h_copy_menu,h_copy_menu_after,0xC347
RENDER_K EQU 100 ; provisional; tick every plot prevents losing full video frames
        INCLUDE "lib/hlib_pace.asm"
v_r:    ds 3
v_speed: db 0
v_tick_speed: db 0
v_copy_speed: db 0
v_active: db 0
v_hl:   dw 0
v_pace: ds 26
code_end:
        ASSERT code_end < 0x3800
        SAVEBIN "pentagram_rom.bin",0x2000,code_end-0x2000
        ORG 0xD000
setup:
        nextreg 0x64,0
        ret
setup_end:
        SAVEBIN "pentagram_setup.bin",setup,setup_end-setup
