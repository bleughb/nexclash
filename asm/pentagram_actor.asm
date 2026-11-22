; Actor and renderer share one final pace target. Whole effects retain their
; original clock; their full duration is excluded from the accelerated span.
ACTOR_K EQU 104
h_actor_open:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_cancel
        HLIB_SPEED_IN v_actor_speed
        call hlib_pace_open
        ld a,1
        ld (v_actor_active),a
        RESTORE
        FINISH -9
        nextreg 0x51,0xFF
        jp 0xCBAB
actor_close:
        ld a,(v_actor_active)
        or a
        ret z
        call hlib_pace_tick
        ld hl,(v_pace+2)
        push hl
        ld a,ACTOR_K
        call hlib_mul8
        ld (v_actor_target),hl
        pop hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        call hlib_debt_add
        xor a
        ld (v_actor_active),a
        HLIB_SPEED_OUT v_actor_speed
        ret
actor_cancel:
        ld a,(v_actor_active)
        or a
        ret z
        HLIB_SPEED_OUT v_actor_speed
        xor a
        ld (v_actor_active),a
        ld (v_pace_active),a
        ld (v_pace+10),a
        ld hl,0
        ld (v_pace+4),hl
        ld (v_actor_target),hl
        ret
sound_begin:
        HLIB_SPEED_IN v_sound_speed
        ld a,(v_actor_active)
        ld (v_sound_held),a
        or a
        jr z,.outside
        call hlib_pace_tick
        ld a,(v_actor_speed)
        jr .clock
.outside:
        ld a,(v_sound_speed)
.clock: ld (v_sound_clock),a
        HLIB_SPEED_OUT v_sound_clock
        ret
sound_end:
        HLIB_SPEED_IN v_sound_leave
        ld a,(v_sound_held)
        or a
        jr z,.restore
        call hlib_line
        ld (v_pace),hl
        ld hl,(v_pace+14)
        ld (v_pace+18),hl
.restore:
        HLIB_SPEED_OUT v_sound_speed
        ret
        MACRO SOUND_STUB P_NAME,P_TARGET
P_NAME: push hl
        ld hl,P_TARGET
        jp h_sound_enter
        ENDM
        SOUND_STUB h_sound_D5E4,0xD5E4
        SOUND_STUB h_sound_D629,0xD629
        SOUND_STUB h_sound_D635,0xD635
        SOUND_STUB h_sound_D64E,0xD64E
        SOUND_STUB h_sound_D69C,0xD69C
        SOUND_STUB h_sound_D6B5,0xD6B5
h_sound_enter:
        nextreg 0x51,26
        ld (v_sound_target),hl
        pop hl
        HLIB_R_IN
        SAVE
        call sound_begin
        RESTORE
        ld (v_sound_hl),hl
        ld hl,h_sound_after
        ex (sp),hl
        ld (v_sound_return),hl
        ld hl,(v_sound_hl)
        push hl
        ld hl,(v_sound_target)
        ex (sp),hl
        FINISH -14
        nextreg 0x51,0xFF
        ret
h_sound_after:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call sound_end
        RESTORE
        push hl
        ld hl,(v_sound_return)
        ex (sp),hl
        FINISH -9
        nextreg 0x51,0xFF
        ret
v_actor_active:db 0
v_actor_speed:db 0
v_actor_target:dw 0
v_sound_speed:db 0
v_sound_leave:db 0
v_sound_clock:db 0
v_sound_held:db 0
v_sound_hl:dw 0
v_sound_return:dw 0
v_sound_target:dw 0
