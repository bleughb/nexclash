; The original actor update is timed independently from the unchanged sound
; routines. Whole effects run at the incoming game clock; no waveform loop is
; rewritten. Original logic/R and original update pace remain the contract.
ACTOR_K EQU 98
actor_open:
        ld a,(v_speed)
        ld (v_actor_speed),a
        call hlib_pace_open
        ld a,1
        ld (v_actor_active),a
        ld a,3
        ld (v_speed),a
        ret
actor_close:
        ld a,(v_actor_active)
        or a
        ret z
        ld a,(v_actor_speed)
        ld c,a
        ld a,ACTOR_K
        call hlib_pace_waitk
        xor a
        ld (v_actor_active),a
        ld a,(v_actor_speed)
        ld (v_speed),a
        ret
actor_cancel:
        ld a,(v_actor_active)
        or a
        ret z
        ld a,(v_actor_speed)
        ld (v_speed),a
        xor a
        ld (v_actor_active),a
        ld (v_pace+10),a
        ld (v_pace+4),a
        ld (v_pace+5),a
        ret
sound_begin:
        ld a,(v_speed)
        ld (v_sound_speed),a
        ld hl,(v_sp)
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (v_sound_return),de
        ld hl,sound_targets
.find:  ld a,(hl)
        inc hl
        cp e
        jr nz,.miss_hi
        ld a,(hl)
        cp d
        jr z,.found
.miss_hi:
        inc hl
        inc hl
        inc hl
        jr .find
.found:
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,(v_sp)
        dec hl
        ld (hl),d
        dec hl
        ld (hl),e
        ld (v_sp),hl
        inc hl
        inc hl
        ld de,s_sound_after
        ld (hl),e
        inc hl
        ld (hl),d
        ld a,(v_actor_active)
        ld (v_sound_held),a
        or a
        ret z
        call hlib_pace_tick
        ld a,(v_actor_speed)
        ld (v_speed),a
        ret
sound_end:
        ld a,(v_sound_held)
        or a
        jr z,.resume
        ld a,(v_actor_active)
        or a
        jr z,.cancelled
        call hlib_line
        ld (v_pace),hl
        ld hl,(v_pace+14)
        ld (v_pace+18),hl
        jr .resume
.cancelled:
        ld a,(v_actor_speed)
        ld (v_sound_speed),a
.resume:
        ld a,(v_sound_speed)
        ld (v_speed),a
        ld hl,(v_sp)
        ld de,(v_sound_return)
        dec hl
        ld (hl),d
        dec hl
        ld (hl),e
        ld (v_sp),hl
        ret
v_actor_speed: db 0
v_actor_active: db 0
v_sound_speed: db 0
v_sound_held: db 0
v_sound_return: dw 0
sound_targets:
        INCLUDE "alien_8_sound_targets.asm"
