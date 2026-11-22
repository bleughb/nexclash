; Pentagram approved part colours over the unchanged original Filmation renderer.
        INCLUDE "pentagram_colour.asm"
HLIB_V_R EQU v_r
HLIB_V_PACE EQU v_pace
HLIB_PACE_NL EQU 312
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
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
h_plot:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        HLIB_SPEED_IN v_speed
        HLIB_IFF_DI
        push af
        call hold_plot
        call capture_plot
        call restore_maps
        call resume_plot
        pop af
        HLIB_IFF_EI
        HLIB_SPEED_OUT v_speed
        RESTORE
        FINISH -10
        ld a,(ix+26)
        nextreg 0x51,0xFF
        ret
h_clear:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        HLIB_SPEED_IN v_speed
        HLIB_IFF_DI
        push af
        ld de,0xD88F
        or a
        sbc hl,de
        jr c,.done
        ld a,h
        cp 24
        jr nc,.done
        ld a,b
        ld (fc_w),a
        ld a,c
        ld (fc_h),a
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        ld (fc_x),a
        ld b,5
.shift: srl h
        rr l
        djnz .shift
        ld a,l
        ld (fc_y),a
        call hold_plot
        ld a,(fc_w)
        push af
        add a,a
        add a,a
        add a,a
        ld (fc_w),a
        ld a,4
        ld (fg_mark_bits),a
        call mark_grid
        pop af
        ld (fc_w),a
        call fc_clear
        call restore_maps
        call resume_plot
.done: pop af
        HLIB_IFF_EI
        HLIB_SPEED_OUT v_speed
        RESTORE
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xB6DD
h_fullclear:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_cancel
        HLIB_SPEED_IN v_speed
        HLIB_IFF_DI
        push af
        call hold_plot
        nextreg 0x15,0
        nextreg 0x69,0
        ld a,1
        ld (v_active),a
        ld (fg_cold),a
        call fg_reset_live
        call fg_all_dirty
        ld hl,fg_patterns
        ld de,fg_patterns+1
        ld bc,191
        ld (hl),255
        ldir
        xor a
        ld (fc_x),a
        ld (fc_y),a
        ld a,32
        ld (fc_w),a
        ld a,192
        ld (fc_h),a
        call fc_clear
        call restore_maps
        call resume_plot
        pop af
        HLIB_IFF_EI
        HLIB_SPEED_OUT v_speed
        RESTORE
        FINISH -10
        ld bc,6144
        nextreg 0x51,0xFF
        ret
h_hide:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_cancel
        HLIB_SPEED_IN v_speed
        xor a
        ld (v_active),a
        nextreg 0x69,0
        nextreg 0x15,0
        HLIB_SPEED_OUT v_speed
        RESTORE
        FINISH -10
        ld de,16385
        nextreg 0x51,0xFF
        ret
h_sort_tick:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call hlib_pace_tick
        RESTORE
        FINISH -11
        ld (42777),de
        nextreg 0x51,0xFF
        ret
h_render:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_close
        HLIB_SPEED_IN v_render_speed
        call dma_ready
        call hlib_pace_open
        ld a,1
        ld (v_active),a
        ld (v_pace_active),a
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
        ld a,(v_render_speed)
        call pace_original_end
        call commit_frame
        call pace_finish
        HLIB_SPEED_OUT v_render_speed
        RESTORE
        push hl
        ld hl,0xB03E
        ex (sp),hl
        inc sp
        inc sp
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xB03E
        MACRO COPY_HOOK P_ENTRY,P_RETURN,P_CONT,P_TARGET,P_DRAW
P_ENTRY:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_cancel
        HLIB_SPEED_IN v_copy_speed
        call dma_ready
        RESTORE
        ld (v_hl),hl
        ld hl,P_RETURN
        ex (sp),hl
        ld hl,(v_hl)
        FINISH -9
        nextreg 0x51,0xFF
        jp P_TARGET
P_RETURN:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        IF P_DRAW
        call commit_frame
        ENDIF
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
        COPY_HOOK h_copy_room,h_copy_room_after,0xB078,0xB178,1
        COPY_HOOK h_copy_menu,h_copy_menu_after,0xC347,0xB178,1
        COPY_HOOK h_room_init,h_room_init_after,0xAFCE,0xC6B6,0

dma_ready:
        ld a,(v_dma_init)
        or a
        ret nz
        ld a,1
        ld (v_dma_init),a
        jp hlib_dma_init
pace_original_end:
        ld (v_window_speed),a
        call hlib_pace_tick
        ld hl,(v_pace+2)
        push hl
        call pace_render_target
        ld de,(v_actor_target)
        add hl,de
        jr nc,.sum_ok
        ld hl,65535
.sum_ok:
        ld (v_target),hl
        ld hl,0
        ld (v_actor_target),hl
        pop hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        call hlib_debt_add
        ld a,2
        ld (v_pace_active),a
        jp hlib_debt_open
pace_render_target:
        ; Long first-room sorting can exceed the16-bit target range. Saturate
        ; the busy-frame target instead of wrapping into false debt/speedup.
        push hl
        ld de,781               ; ceil(65536 /84)
        or a
        sbc hl,de
        pop hl
        jr nc,.cap
        ld a,84
        jp hlib_mul8
.cap:   ld hl,65535
        ret
pace_finish:
        call hlib_debt_tick
        xor a
        ld (v_pace_active),a
        call hlib_pace_open
        ld hl,(v_target)
        ld a,(v_window_speed)
        jp hlib_pace_wait
restore_maps:
        nextreg 0x50,0xFF
        nextreg 0x56,0
        nextreg 0x57,1
        ret
hold_plot:
        ld a,(v_pace_active)
        or a
        ret z
        ld hl,(v_pace+14)
        ld (v_hold),hl
        jp hlib_pace_hold
resume_plot:
        ld a,(v_pace_active)
        or a
        ret z
        call hlib_pace_resume
        ld hl,(v_pace+14)
        ld de,(v_hold)
        or a
        sbc hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        call hlib_debt_add
        jp hlib_pace_tick
        INCLUDE "pentagram_actor.asm"
        INCLUDE "pentagram_capture.asm"
        INCLUDE "pentagram_grid.asm"
        DEFINE HLIB_PC_OTIR
        INCLUDE "lib/hlib_dma.asm"
        INCLUDE "lib/hlib_pace.asm"
v_r:ds 3,0
v_pace:ds 26,0
v_speed:db 0
v_render_speed:db 0
v_copy_speed:db 0
v_window_speed:db 0
v_active:db 0
v_pace_active:db 0
v_target:dw 0
v_hold:dw 0
v_hl:dw 0
v_dma_init:db 0
v_front:db 58
v_back:db 70
v_copy_src:db 0
v_copy_dst:db 0
        ASSERT $ <= 0x3400
        ds 0x3C00-$,0
code_end:
        SAVEBIN "pentagram_rom.bin",0x2000,code_end-0x2000
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x15,0
        nextreg 0x69,0
        nextreg 0x70,0
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,palette9
        ld b,0
.pal:  ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .pal
        nextreg 0x14,0xE3
        nextreg 0x4B,255
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,palette9
        ld b,0
.spal: ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .spal
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        ret
palette9:
        INCLUDE "pentagram_palette.inc"
setup_end:
        SAVEBIN "pentagram_setup.bin",setup,setup_end-setup

        INCLUDE "pentagram_aux.asm"
        SAVEBIN "pentagram_aux.bin",0xA000,aux_end-0xA000
