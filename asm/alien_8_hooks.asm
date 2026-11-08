; Alien 8 exact-colour compositor candidate. Original graphics and logic remain.
        DEVICE ZXSPECTRUMNEXT
H_PAGE EQU 26
        DEFINE SC_HOLD_TICK
HLIB_V_R EQU v_r
HLIB_V_PACE EQU v_pace
HLIB_PACE_NL EQU 312
        ORG 0x2000
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_speed.asm"

; All capture hooks use a private stack while MMU6/7 are mapped. No game
; register or original stack address is repurposed as persistent hook storage.
        MACRO CAPTURE name, action, outoff, outon, delta, held, variable
name:
        ld (v_sp),sp
        ld sp,private_stack
        push af
        push bc
        push de
        push hl
        HLIB_R_IN
        ld (v_bc),bc
        ld (v_de),de
        ld (v_hl),hl
        IF held
        ld a,held
        ld (v_outside_allowed),a
        call hook_hold_start
        ENDIF
        HLIB_IFF_DI
        push af
        HLIB_SPEED_IN v_speed
        call save_mmu
        call action
        ld a,delta
        call hlib_r_set
        IF variable
        ld a,(v_bc+1)
        add a,a
        call hlib_r_add
        ENDIF
        call restore_mmu
        HLIB_SPEED_OUT v_speed
        IF held
        call hook_hold_end
        ENDIF
        pop af
        jp pe,.on
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        ld sp,(v_sp)
        jp outoff
.on:    ld a,127
        call hlib_r_add
        pop hl
        pop de
        pop bc
        pop af
        HLIB_R_OUT
        ld sp,(v_sp)
        jp outon
        ENDM

        CAPTURE h_plot,paint_plot,o_plot,o_plot_on,107,1,0
        CAPTURE h_clear,clear_all,o_clear,o_clear_on,107,2,0
        CAPTURE h_rect,clear_rect,o_rect,o_rect_on,108,1,0
        CAPTURE h_full,commit,o_full,o_full_on,107,2,0
        CAPTURE h_part,commit_partial,o_part,o_part_on,108,1,0

        CAPTURE h_window_in,window_open,o_window_in,o_window_in_on,108,0,0
        CAPTURE h_window_out,window_close,o_window_out,o_window_out_on,107,0,0
        CAPTURE h_delay,pace_delay,o_delay,o_delay_on,103,0,1
        CAPTURE h_actor,actor_open,o_actor,o_actor_on,107,0,0
        CAPTURE h_cancel,actor_cancel,o_cancel,o_cancel_on,107,0,0
        CAPTURE h_gameover,actor_cancel,o_gameover,o_gameover_on,108,0,0
        CAPTURE h_sound,sound_begin,o_sound,o_sound_on,108,0,0
        CAPTURE h_sound_after,sound_end,o_sound,o_sound_on,108,0,0

pace_delay:
        call hlib_pace_open
        ld bc,(v_bc)
.loop:  ld hl,768
.inner: dec hl
        ld a,l
        or h
        jr nz,.inner
        djnz .loop
        ld a,(v_bc+1)
        ld h,0
        ld l,a
        ; 768 inner iterations:19963T +23T per outer iteration (last -5T).
        ; 16/224 sixteenths per line gives1427.57 units per iteration.
        ld de,1427
        ld b,a
        ld hl,0
.sum:   add hl,de
        djnz .sum
        ld a,(v_speed)
        jp hlib_pace_wait

window_open:
        call actor_close
renderer_start:
        ld a,(v_speed)
        ld (v_outer_speed),a
        ld hl,(v_pace+14)
        ld (v_outer_held),hl
        call hlib_pace_open
        ld a,1
        ld (v_in_window),a
        ld a,3
        ld (v_speed),a
        ret
window_close:
        xor a
        ld (v_in_window),a
        ld hl,(v_pace+14)
        ld de,(v_outer_held)
        or a
        sbc hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        call hlib_debt_add
        ld a,(v_outer_speed)
        ld c,a
        ld a,98
        call hlib_pace_waitk
        ld a,(v_outer_speed)
        ld (v_speed),a
        ret
hook_hold_start:
        ld a,(v_in_window)
        ld (v_hook_held),a
        or a
        jr nz,.window
        ld a,(v_outside_allowed)
        cp 2
        ret nz
        ld a,(v_actor_active)
        or a
        ret nz
        ld a,2
        ld (v_hook_held),a
        jp hlib_debt_open
.window:
        call hlib_pace_tick
        jp hlib_pace_hold
hook_hold_end:
        ld a,(v_hook_held)
        or a
        ret z
        cp 2
        jr z,.debt
        xor a
        ld (v_hook_held),a
        jp hook_hold_account
.debt: xor a
        ld (v_hook_held),a
        ld a,8
        jp hlib_debt_close
hook_hold_tick:
        push af
        push bc
        push de
        push hl
        ld a,(v_hook_held)
        or a
        jr z,.done
        cp 2
        jr z,.debt
        call hook_hold_account
        jr .done
.debt: call hlib_debt_tick
.done: pop hl
        pop de
        pop bc
        pop af
        ret

; While held, update both timestamps atomically from one line reading. This
; accounts for arbitrarily long compositor work without charging the polling
; helper to the original renderer and multiplying it by the speed ratio.
hook_hold_account:
        call hlib_line
        ld (v_tick_now),hl
        ld de,(v_pace+16)
        or a
        sbc hl,de
        jr nc,.nowrap
        ld de,312
        add hl,de
.nowrap:
        ld de,(v_pace+14)
        add hl,de
        ld (v_pace+14),hl
        ld (v_pace+18),hl
        ld hl,(v_tick_now)
        ld (v_pace),hl
        ld (v_pace+16),hl
        ret

read_nr:
        ld bc,0x243B
        out (c),a
        inc b
        in a,(c)
        ret
save_mmu:
        ld a,0x50
        call read_nr
        ld (v_m0),a
        ld a,0x54
        call read_nr
        ld (v_m4),a
        ld a,0x55
        call read_nr
        ld (v_m5),a
        nextreg 0x55,81
        ld a,0x56
        call read_nr
        ld (v_m6),a
        ld a,0x57
        call read_nr
        ld (v_m7),a
        ret
restore_mmu:
        ld a,(v_m4)
        nextreg 0x54,a
        ld a,(v_m5)
        nextreg 0x55,a
        ld a,(v_m0)
        nextreg 0x50,a
        ld a,(v_m6)
        nextreg 0x56,a
        ld a,(v_m7)
        nextreg 0x57,a
        ret

paint_plot:
        ; Direct HUD records remain on the original ULA. Reject before any IX
        ; memory read: the HUD record lives in MMU5, used by auxiliary code.
        push ix
        pop hl
        ld de,23432
        or a
        sbc hl,de
        ret c
        ld de,1792
        or a
        sbc hl,de
        ret nc
        ld a,(v_m5)
        nextreg 0x55,a
        ld hl,(v_de)
        ld a,(hl)
        nextreg 0x55,81
        and 0xC0
        rlca
        rlca
        ld (v_orientation),a
        ld e,a
        ld d,6
        mul d,e
        push de
        ld e,(ix+0)
        ld d,24
        mul d,e
        ex de,hl
        pop de
        add hl,de
        nextreg 0x50,24
        ld a,(hl)
        or a
        ret z
        ld (v_source),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (v_source_ptr),de
        inc hl
        ld a,(hl)
        ld (fc_w),a
        inc hl
        ld a,(hl)
        ld (fc_h),a
        inc hl
        ld a,(hl)
        ld (v_painted),a
        ld a,(ix+26)
        ld (fc_x),a
        ld a,(ix+27)
        ld (fc_y),a
        ld a,(v_source)
        nextreg 0x50,a
        ld hl,(v_source_ptr)
        call dirty_candidates
        ld a,(v_source)
        nextreg 0x50,a
        ld hl,(v_source_ptr)
        jp fc_plot

clear_all:
        call actor_cancel
        xor a
        ld (q_count),a
        ld (q_overflow),a
        ld hl,5376
        ld (q_ptr),hl
        ld hl,DIRTY
        ld de,DIRTY+1
        ld bc,191
        ld (hl),7
        ldir
        nextreg 0x15,0
        ld hl,sc_used
        ld de,sc_used+1
        ld bc,127
        ld (hl),0
        ldir
        nextreg 0x50,25
        ld hl,1024
        ld de,1025
        ld bc,447
        ld (hl),0
        ldir
        ld hl,2048
        ld de,2049
        ld bc,1791
        ld (hl),255
        ldir
        ; Only the room-entry caller receives the selected floor. Menus,
        ; credits and game-over clears retain their original black background.
        ld hl,(v_sp)
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,0xCAB1
        or a
        sbc hl,de
        ld a,0
        jr nz,.empty
        inc a
        ld (v_mode),a
        nextreg 0x50,24
        ld a,(23440)
        ld l,a
        ld h,0x19
        ld a,(hl)
        or a
        jr nz,.floor
.empty: xor a
        ld (v_mode),a
        ld bc,0x123B
        out (c),a
        xor a
.floor: ld (fc_fbase),a
        xor a
        ld (fc_x),a
        ld (fc_y),a
        ld a,32
        ld (fc_w),a
        ld a,192
        ld (fc_h),a
        jp fc_clear

clear_rect:
        ld hl,(v_hl)
        ld de,0xD200
        or a
        sbc hl,de
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        ld (fc_x),a
        ld b,5
.shr:   srl h
        rr l
        djnz .shr
        ld a,l
        ld (fc_y),a
        ld bc,(v_bc)
        ld a,b
        ld (fc_w),a
        ld a,c
        ld (fc_h),a
        ld a,(fc_w)
        push af
        add a,a
        add a,a
        add a,a
        ld (fc_w),a
        call dirty_candidates
        pop af
        ld (fc_w),a
        jp fc_clear

commit_partial:
        ld a,(23319)
        or a
        ret nz
commit:
        ld a,(v_mode)
        or a
        ret z
        push ix
        call dirty_attributes
        call owner_compare
        call sprite_bounds_start
        call dirty_copy
        pop ix
        call sprite_build
        ld a,(sp_overflow)
        or a
        call nz,sprite_fallback
        call dirty_reset
        ; Publish only after the complete backing image exists.
        call sprite_blank
        ld a,(v_back)
        srl a
        nextreg 0x12,a
        call sprite_publish
        ld a,(v_back)
        xor 62
        ld (v_back),a
        ld bc,0x123B
        ld a,2
        out (c),a
        ret

copy8k:
        call hlib_dma_backend
        or a
        jr z,.cpu
        ld hl,copy_packet
        ld bc,(copy_packet_end-copy_packet)*256+0x6B
        otir
        ret
.cpu:   ld hl,0xC000
        ld de,0xE000
        ld bc,8192
        ldir
        ret
copy_packet:
        db 0x83,0xC3,0x7D
        dw 0xC000,8192
        db 0x14,0x10,0xAD
        dw 0xE000
        db 0x82,0xCF,0x87
copy_packet_end:

        INCLUDE "alien_8_actor.asm"
        INCLUDE "lib/hlib_pace.asm"
        DEFINE HLIB_PC_OTIR
        DEFINE HLIB_NO_BLITTER
        INCLUDE "lib/hlib_dma.asm"
v_sp: dw 0
v_bc: dw 0
v_de: dw 0
v_hl: dw 0
v_r: ds 3
v_speed: db 0
v_m0: db 0xFF
v_m4: db 4
v_m5: db 5
v_m6: db 0
v_m7: db 1
v_mode: db 0
v_source: db 0
v_source_ptr: dw 0
v_back: db 28
v_copy_page: db 0
v_colour_page: db 0
v_pace: ds 26
v_outer_speed: db 0
v_tick_now: dw 0
v_outer_held: dw 0
v_in_window: db 0
v_hook_held: db 0
v_outside_allowed: db 0
v_orientation: db 0
v_painted: db 0
v_static: db 0
v_owner: db 0
code_end:
        ASSERT code_end<0x3200
sc_heads EQU 0x3E00
sc_next EQU 0x3340
sc_used EQU 0x3200
sc_valid EQU 0x3300
sc_hashes EQU 0x3400
sc_nextused EQU 0x3500
PAT EQU 0x3600
ATTS EQU 0x3700
DIRTY EQU 0x3D00
private_stack EQU 0x3FF0

        ORG 0x3B00
        MACRO ENTRY label,body
label:  nextreg 0x51,H_PAGE
        jp body
        ENDM
        ENTRY s_plot,h_plot
        ENTRY s_clear,h_clear
        ENTRY s_rect,h_rect
        ENTRY s_full,h_full
        ENTRY s_part,h_part
        ENTRY s_window_in,h_window_in
        ENTRY s_window_out,h_window_out
        ENTRY s_delay,h_delay
        ENTRY s_actor,h_actor
        ENTRY s_cancel,h_cancel
        ENTRY s_gameover,h_gameover
        ENTRY s_sound,h_sound
        ENTRY s_sound_after,h_sound_after
o_plot: nextreg 0x51,0xFF
        ld a,(ix+26)
        ret
o_plot_on:
        nextreg 0x51,0xFF
        ei
        ld a,(ix+26)
        ret
o_clear:nextreg 0x51,0xFF
        ld bc,6144
        ret
o_clear_on:
        nextreg 0x51,0xFF
        ei
        ld bc,6144
        ret
o_rect: nextreg 0x51,0xFF
        jp 0xBF83
o_rect_on:
        nextreg 0x51,0xFF
        ei
        jp 0xBF83
o_full: nextreg 0x51,0xFF
        ld hl,0xD200
        ret
o_full_on:
        nextreg 0x51,0xFF
        ei
        ld hl,0xD200
        ret
o_part: nextreg 0x51,0xFF
        pop ix
        ret
o_part_on:
        nextreg 0x51,0xFF
        ei
        pop ix
        ret
o_window_in:
        nextreg 0x51,0xFF
        jp 0xC71C
o_window_in_on:
        nextreg 0x51,0xFF
        ei
        jp 0xC71C
o_window_out:
        nextreg 0x51,0xFF
        ld a,(23332)
        ret
o_window_out_on:
        nextreg 0x51,0xFF
        ei
        ld a,(23332)
        ret
o_delay:
        nextreg 0x51,0xFF
        pop af
        ld b,0
        ld hl,0
        xor a
        jp 0xA715
o_delay_on:
        nextreg 0x51,0xFF
        ei
        pop af
        ld b,0
        ld hl,0
        xor a
        jp 0xA715
o_actor:
        nextreg 0x51,0xFF
        ld ix,23432
        jp 0xA692
o_actor_on:
        nextreg 0x51,0xFF
        ei
        ld ix,23432
        jp 0xA692
o_cancel:
        nextreg 0x51,0xFF
        ld hl,23304
        ret
o_cancel_on:
        nextreg 0x51,0xFF
        ei
        ld hl,23304
        ret
o_gameover:
        nextreg 0x51,0xFF
        jp 0xAF05
o_gameover_on:
        nextreg 0x51,0xFF
        ei
        jp 0xAF05
o_sound:
        nextreg 0x51,0xFF
        ret
o_sound_on:
        nextreg 0x51,0xFF
        ei
        ret
tramp_end:
        ASSERT tramp_end<0x3DF0
        SAVEBIN "alien8_page.bin",0x2000,0x2000

        ORG 0xA000
        INCLUDE "alien_8_queue.asm"
        INCLUDE "alien_8_dirty.asm"
        INCLUDE "alien_8_sprites.asm"
        INCLUDE "alien_8_sprite_cache.asm"
        INCLUDE "alien_8_primitive.asm"
auxiliary_end:
        ASSERT auxiliary_end<0xC000
        SAVEBIN "alien8_auxiliary.bin",0xA000,0x2000

        ORG 0xD000
setup:
        nextreg 0x07,3
        nextreg 0x51,H_PAGE
        ld a,1
        call hlib_dma_init
        nextreg 0x50,25
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,0
        ld de,256
.palette:
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        dec de
        ld a,d
        or e
        jr nz,.palette
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,0x1000
        ld de,256
.spalette:
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        dec de
        ld a,d
        or e
        jr nz,.spalette
        nextreg 0x64,0
        nextreg 0x4B,255
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x70,0
        nextreg 0x12,14
        nextreg 0x13,17
        nextreg 0x50,0xFF
        nextreg 0x51,0xFF
        ld bc,0x243B
        ld a,0x0A
        out (c),a
        inc b
        in a,(c)
        and 0xEF
        nextreg 0x0A,a
        xor a
        ld bc,0xE3
        out (c),a
        nextreg 0x07,0
        ret
setup_end:
        SAVEBIN "alien8_setup.bin",0xD000,setup_end-0xD000
