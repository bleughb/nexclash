; BOUNDED INTEGRATION PROPOSAL, not yet an emitted or verified release hook.
; Include after SAVE / RESTORE / FINISH and hlib helpers are defined.
; AFBD gets CALL h_actor_open. BA22 and AF7F get the cancel hooks below.
; In h_render, call actor_close AFTER SAVE but BEFORE HLIB_SPEED_IN v_render_speed.
; Preserve conditional CALL opcodes in sound-sites.json, replacing operands only.
; No original SFX or delay-loop instruction is replaced.
; K100 includes whole-update wrapper overhead; calibrated at player updates.
        IFNDEF ACTOR_K
ACTOR_K EQU 100
        ENDIF

h_actor_open:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_close
        HLIB_SPEED_IN v_actor_speed
        call hlib_pace_open
        ld a,1
        ld (v_actor_active),a
        ld (v_pace_active),a
        RESTORE
        FINISH -10
        ld a,(23458)
        nextreg 0x51,0xFF
        ret

; Called under h_render's own saved registers/R, before latching render speed.
; The original actor code ran fast; complete SFX/pause time was excluded.
; Shared debt from the preceding compositor is repaid against this target.
actor_close:
        ld a,(v_actor_active)
        or a
        ret z
        call hlib_pace_tick
        ld hl,(v_pace+2)
        ld a,ACTOR_K
        call hlib_mul8
        ld (v_actor_target),hl
        HLIB_SPEED_OUT v_actor_speed
        ld hl,(v_actor_target)
        ld a,(v_actor_speed)
        call hlib_pace_wait
        xor a
        ld (v_actor_active),a
        ld (v_pace_active),a
        ret

; Nonreturning game-over/new-game routes abandon the actor window. They must
; not retain28MHz, or enter a long menu/tune with a live renderer timer.
actor_cancel:
        ld a,(v_actor_active)
        or a
        ret z
        HLIB_SPEED_OUT v_actor_speed
        xor a
        ld (v_actor_active),a
        ld (v_pace_active),a
        ld (v_pace+10),a
        ld (v_pace+4),a
        ld (v_pace+5),a
        ret
h_actor_cancel_gameover:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_cancel
        RESTORE
        FINISH -10
        ld a,(23491)
        nextreg 0x51,0xFF
        ret
h_actor_cancel_newgame:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_cancel
        RESTORE
        FINISH -10
        ld hl,23464
        nextreg 0x51,0xFF
        ret

; One level only: these wrappers cover whole effects, and all their internal
; effect/kernel calls remain original. D50E wraps the whole pause routine;
; do NOT also wrap D522/D537's nested effect calls.
; Save the line accumulator before an effect. Rebase AFTER it: hold/resume
; alone loses whole frames when an original effect or pause lasts>312 lines.
actor_sound_begin:
        HLIB_SPEED_IN v_sound_speed
        ld a,(v_actor_active)
        ld (v_sound_held),a
        or a
        jr z,.outside
        call hlib_pace_tick
        ld a,(v_actor_speed)
        ld (v_sound_clock),a
        jr .clock
.outside:
        ld a,(v_sound_speed)
        ld (v_sound_clock),a
.clock:
        HLIB_SPEED_OUT v_sound_clock
        ret
actor_sound_end:
        HLIB_SPEED_IN v_sound_leave_speed
        ld a,(v_sound_held)
        or a
        jr z,.restore
        ld a,(v_actor_active)
        or a
        jr z,.cancelled
        call hlib_line
        ld (v_pace),hl
        ld hl,(v_pace+14)
        ld (v_pace+18),hl
        jr .restore
.cancelled:
        ld a,(v_actor_speed)
        ld (v_sound_speed),a
.restore:
        HLIB_SPEED_OUT v_sound_speed
        ret

; Return-word exchange preserves the SP seen by every original instruction.
; -9 at entry: original CALL=1M1, capture E=6, remaining N=4.
; -9 after: original RET already ran, capture E=5, remaining N=4.
        MACRO ACTOR_SOUND label,target
label:
        push hl
        ld hl,target
        jp h_actor_sound_common
        ENDM
h_actor_sound_common:
        nextreg 0x51,26
        ld (v_sound_target),hl
        pop hl
        HLIB_R_IN
        SAVE
        call actor_sound_begin
        RESTORE
        ld (v_sound_hl),hl
        ld hl,h_actor_sound_after
        ex (sp),hl
        ld (v_sound_return),hl
        ld hl,(v_sound_hl)
        push hl
        ld hl,(v_sound_target)
        ex (sp),hl
        FINISH -14
        nextreg 0x51,0xFF
        ret
h_actor_sound_after:
        nextreg 0x51,26
        HLIB_R_IN
        SAVE
        call actor_sound_end
        RESTORE
        push hl
        ld hl,(v_sound_return)
        ex (sp),hl
        FINISH -9
        nextreg 0x51,0xFF
        ret

        ACTOR_SOUND h_as_B3E9,0xB3E9
        ACTOR_SOUND h_as_B403,0xB403
        ACTOR_SOUND h_as_B419,0xB419
        ACTOR_SOUND h_as_B42E,0xB42E
        ACTOR_SOUND h_as_B441,0xB441
        ACTOR_SOUND h_as_B451,0xB451
        ACTOR_SOUND h_as_B45D,0xB45D
        ACTOR_SOUND h_as_B462,0xB462
        ACTOR_SOUND h_as_B467,0xB467
        ACTOR_SOUND h_as_B472,0xB472
        ACTOR_SOUND h_as_B489,0xB489
        ACTOR_SOUND h_as_B4A3,0xB4A3
        ACTOR_SOUND h_as_B4AD,0xB4AD
        ACTOR_SOUND h_as_B4BB,0xB4BB
        ACTOR_SOUND h_as_B4C1,0xB4C1
        ACTOR_SOUND h_as_D50E,0xD50E

v_actor_active: db 0
v_actor_speed: db 0
v_actor_target: dw 0
v_sound_speed: db 0
v_sound_leave_speed: db 0
v_sound_clock: db 0
v_sound_held: db 0
v_sound_return: dw 0
v_sound_hl: dw 0

v_sound_target:dw 0
