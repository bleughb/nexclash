; Knight Lore: exact masked colour/owner canvas prototype.
; Entry and exit instructions are identical in alt ROM and writable page26.
; No persistent printer-buffer trampoline: the original uses it as a stack.
        INCLUDE "knight_lore_packed.asm"
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
        ld (v_arga),a
        HLIB_SPEED_IN v_speed
        HLIB_IFF_DI
        push af
        ; Only the draw-buffer zero rectangles are mirrored. The same
        ; routine fills ULA attributes elsewhere, which remain original.
        ld a,(v_arga)
        or a
        jr nz,.done
        ld de,55539
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
        call mark_grid
        pop af
        ld (fc_w),a
        ld a,52
        ld (fc_cbase),a
        call fc_clear
        call restore_maps
        call resume_plot
.done: pop af
        HLIB_IFF_EI
        HLIB_SPEED_OUT v_speed
        RESTORE
        FINISH -10
        ld de,32
        nextreg 0x51,0xFF
        ret

h_fullclear:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        HLIB_SPEED_IN v_speed
        HLIB_IFF_DI
        push af
        call hold_plot
        nextreg 0x15,0
        call fg_reset_live
        call fg_all_dirty
        ld hl,fg_patterns
        ld de,fg_patterns+1
        ld bc,191
        ld (hl),255
        ldir
        ld a,(23568)
        ld l,a
        ld h,floor_table/256
        ld a,(hl)
        cp 4
        jr c,.known
        xor a
.known: ld c,a
        add a,a
        add a,c
        add a,a
        add a,28
        ld (fc_fbase),a
        xor a
        ld (fc_x),a
        ld (fc_y),a
        ld a,32
        ld (fc_w),a
        ld a,192
        ld (fc_h),a
        ld a,52
        ld (fc_cbase),a
        ld a,64
        ld (fc_obase),a
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
        HLIB_SPEED_IN v_speed
        xor a
        ld (v_active),a
        nextreg 0x69,0
        nextreg 0x15,0
        HLIB_SPEED_OUT v_speed
        RESTORE
        FINISH -10
        ld hl,16384
        nextreg 0x51,0xFF
        ret

; Replace the original CALL D59F. Its return word is exchanged for an
; after-hook on the same stack depth, so the game's SP-as-graphics save
; has exactly the original value.
h_render:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_close
        HLIB_SPEED_IN v_render_speed
        ld a,(v_dma_init)
        or a
        jr nz,.ready
        ld a,1
        ld (v_dma_init),a
        call hlib_dma_init
.ready: call hlib_pace_open
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
        jp 0xD59F
h_render_after:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        ld a,(v_render_speed)
        call pace_original_end
        ld a,(23479)
        or a
        call z,commit_frame
        call pace_finish
        HLIB_SPEED_OUT v_render_speed
        RESTORE
        ; The original CALL left B021 in its now-dead return word.
        push hl
        ld hl,0xB021
        ex (sp),hl
        inc sp
        inc sp
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xB021

h_fullcopy:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_close
        HLIB_SPEED_IN v_copy_speed
        call hlib_pace_open
        ld a,1
        ld (v_pace_active),a
        RESTORE
        ld (v_hl),hl
        ld hl,h_fullcopy_after
        ex (sp),hl
        ld hl,(v_hl)
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xD56F
h_fullcopy_after:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        ld a,(v_copy_speed)
        call pace_original_end
        call commit_frame
        call pace_finish
        HLIB_SPEED_OUT v_copy_speed
        RESTORE
        push hl
        ld hl,0xB071
        ex (sp),hl
        inc sp
        inc sp
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xB071

 ; Close the original-code window before any publication work. Only its
; unheld elapsed time is scaled byK. Actual rendering/publication cost is debt.
pace_original_end:
        ld (v_window_speed),a
        call hlib_pace_tick
        ld hl,(v_pace+2)
        push hl
        ld a,88
        call hlib_mul8
        ld (v_target),hl
        pop hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        call hlib_debt_add
        ld a,2
        ld (v_pace_active),a
        jp hlib_debt_open
pace_finish:
        call hlib_debt_tick
        xor a
        ld (v_pace_active),a
        call hlib_pace_open
        ld hl,(v_target)
        ld a,(v_window_speed)
        jp hlib_pace_wait

 ; B035..B03B is a pure1280-iteration wait; DJNZ atB03D remains original.
; 33285 original T-states /224 ×16 =2377.5 line-sixteenths.
; Spend render debt here, preserving finalAF/HL/B and all5121 M1 increments.
h_delay:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        HLIB_SPEED_IN v_delay_speed
        call hlib_pace_open
        HLIB_SPEED_OUT v_delay_speed
        ld hl,2377
        ld a,(v_delay_speed)
        call hlib_pace_wait
        RESTORE
        ld hl,0xB03D
        ex (sp),hl
        FINISH -11
        ld hl,0
        xor a
        nextreg 0x51,0xFF
        ret

capture_plot:
        ld a,(ix+26)
        ld (fc_x),a
        ld a,(ix+27)
        ld (fc_y),a
        ld a,52
        ld (fc_cbase),a
        ld a,64
        ld (fc_obase),a
        ld a,254
        ld (fc_ink),a
        ld a,(de)
        rlca
        rlca
        and 3
        ld c,a
        ld a,(ix+0)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,c
        add hl,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld (v_directory),hl
        push ix
        pop hl
        ld de,23560
        or a
        sbc hl,de
        jr c,.hud
        ld de,1280
        or a
        sbc hl,de
        jr nc,.hud
        add hl,de
        ld b,5
.owner: srl h
        rr l
        djnz .owner
        ld a,l
        ld (fc_owner),a
        cp 2
        ld a,76
        jr nc,.dir
        ld a,77
        jr .dir
.hud:  ld a,255
        ld (fc_owner),a
        ld (fc_ink),a
        ld a,76
.dir:  nextreg 0x50,a
        ld hl,(v_directory)
        ld a,(hl)
        or a
        ret z
        ld c,a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        ld (fc_w),a
        inc hl
        ld a,(hl)
        ld (fc_h),a
        inc hl
        ld a,(hl)
        ld (fc_orient),a
        inc hl
        ld a,(hl)
        or a
        jr nz,.dynamic
        ld a,255
        ld (fc_owner),a
.dynamic:
        push de
        push bc
        call mark_grid
        pop bc
        pop hl
        ld a,c
        nextreg 0x50,a
        jp fc_plot

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

        INCLUDE "knight_lore_actor.asm"
        INCLUDE "knight_lore_grid_commit.asm"
        DEFINE HLIB_PC_OTIR
        INCLUDE "lib/hlib_dma.asm"
        INCLUDE "lib/hlib_pace.asm"
v_r: ds 3,0
v_pace: ds 26,0
v_speed: db 0
v_arga: db 0
v_render_speed: db 0
v_copy_speed: db 0
v_delay_speed: db 0
v_window_speed:db 0
v_target:dw 0
v_active: db 0
v_pace_active: db 0
v_hold: dw 0
v_hl: dw 0
v_directory: dw 0
v_dma_init: db 0
v_front: db 58
v_back: db 70
v_copy_src: db 0
v_copy_dst: db 0
floor_table EQU 0x3F00
        ASSERT $ <= 0x3400
        ds 0x3C00-$,0
code_end:
        ASSERT code_end < 0x3D00
        SAVEBIN "knight_rom.bin",0x2000,code_end-0x2000

        ORG 0xD000
setup:
        ; Raster comparisons use the native ULA line with no Copper offset.
        nextreg 0x64,0
        ; L2 above ULA, original display remains underneath transparent pixels.
        nextreg 0x15,0
        nextreg 0x69,0
        nextreg 0x70,0
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x43,0
        nextreg 0x40,24
        nextreg 0x44,0
        nextreg 0x44,0
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
        nextreg 0x14,1
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
        INCLUDE "knight_lore_palette.inc"
setup_end:
        SAVEBIN "knight_setup.bin",0xD000,setup_end-0xD000
