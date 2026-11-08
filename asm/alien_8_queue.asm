; Record original clear/plot ordering, then apply it only to actual changed
; regions once all final projected object geometry is known.
queue_clear:
        xor a
        jr queue_add
queue_plot:
        ld a,(v_source)
queue_add:
        ld (q_source),a
        nextreg 0x50,25
        ld a,(q_count)
        cp 192
        jr nc,.overflow
        inc a
        ld (q_count),a
        ld hl,(q_ptr)
        ld a,(q_source)
        ld (hl),a
        inc hl
        ld de,(v_source_ptr)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ex de,hl
        ld hl,fc_x
        ld bc,6
        ldir
        inc de
        ld (q_ptr),de
        ret
.overflow:
        ld a,1
        ld (q_overflow),a
        xor a
        ld (v_mode),a
        nextreg 0x15,0
        ld bc,0x123B
        out (c),a
        ret
queue_replay:
        ld hl,5376
        ld (q_read),hl
.loop:  ld a,(q_count)
        or a
        jr z,.done
        dec a
        ld (q_count),a
        call hook_hold_tick
        nextreg 0x50,25
        ld hl,(q_read)
        ld a,(hl)
        ld (q_source),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (q_srcptr),de
        inc hl
        ld de,fc_x
        ld bc,6
        ldir
        inc hl
        ld (q_read),hl
        ld a,(fc_w)
        ld (q_width),a
        ld a,(q_source)
        or a
        jr nz,.check
        ld a,(fc_w)
        add a,a
        add a,a
        add a,a
        ld (fc_w),a
.check: call dirty_test_rectangle
        ld a,(q_width)
        ld (fc_w),a
        jr z,.loop
        ld a,(q_source)
        or a
        jr z,.clear
        nextreg 0x50,a
        ld hl,(q_srcptr)
        call fc_plot
        jr .loop
.clear: call fc_clear
        jr .loop
.done:  ld hl,5376
        ld (q_ptr),hl
        ret
q_ptr: dw 5376
q_read: dw 5376
q_srcptr: dw 0
q_source: db 0
q_count: db 0
q_overflow: db 0

q_width: db 0
