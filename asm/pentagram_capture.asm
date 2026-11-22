; Capture original projected placement before its masked bit renderer executes.
capture_plot:
        ld a,(ix+0)
        cp 172
        ret nc
        ld a,(ix+26)
        ld (fc_x),a
        ld (v_x),a
        ld a,(ix+27)
        ld (fc_y),a
        ld (v_y),a
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
        ld de,42863
        or a
        sbc hl,de
        jr c,.hud
        ld de,1728
        or a
        sbc hl,de
        jr nc,.hud
        ld a,76
        jr .dir
.hud:  ld a,77
.dir:  nextreg 0x50,a
        ld hl,(v_directory)
        ld a,(hl)
        or a
        ret z
        ld (v_source_page),a
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
        ld (fc_orient),a
        and 1
        rrca
        or 1
        ld (v_black),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        call xor_capture
        ld a,(fc_orient)
        and 1
        ld a,4
        jr nz,.mark
        or 8
.mark: ld (fg_mark_bits),a
        call mark_grid
        ld a,(v_source_page)
        nextreg 0x50,a
        ld hl,(v_source_ptr)
        call fc_plot
        jp xor_apply

; Only nine original pixels use ink outside mask. Shifted original drawing
; XORs these pixels; remember old set bits before mapping out original RAM.
xor_capture:
        xor a
        ld (v_fix_count),a
        ld a,h
        or l
        ret z
        ld a,(v_x)
        and 7
        ret z
        ld b,(hl)
        inc hl
.loop: push bc
        ld a,(hl)
        inc hl
        ld c,a
        ld a,(hl)
        inc hl
        push hl
        ld b,a
        ld a,(v_x)
        add a,c
        ld c,a
        ld a,(v_y)
        adc a,b
        cp 192
        jr nc,.next
        ld b,a
        ld a,c
        and 7
        ld e,a
        ld a,128
        jr z,.bit_ready
.bit:  rrca
        dec e
        jr nz,.bit
.bit_ready:
        ld (v_bit),a
        ld a,b
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,c
        srl a
        srl a
        srl a
        add hl,a
        ld de,0xD88F
        add hl,de
        ld a,(v_bit)
        and (hl)
        jr z,.next
        ld a,(v_fix_count)
        add a,a
        ld hl,v_fixes
        add hl,a
        ld (hl),c
        inc hl
        ld (hl),b
        ld hl,v_fix_count
        inc (hl)
.next: pop hl
        pop bc
        djnz .loop
        ret
xor_apply:
        ld a,(v_fix_count)
        or a
        ret z
        ld b,a
        ld hl,v_fixes
.loop: push bc
        ld e,(hl)
        inc hl
        ld a,(hl)
        inc hl
        push hl
        ld c,a
        ld a,191
        sub c
        ld c,a
        srl a
        srl a
        srl a
        srl a
        srl a
        add a,52
        nextreg 0x56,a
        ld a,c
        and 31
        or 0xC0
        ld d,a
        ld a,(v_black)
        ld (de),a
        pop hl
        pop bc
        djnz .loop
        ret
v_x:db 0
v_y:db 0
v_black:db 1
v_bit:db 0
v_fix_count:db 0
v_fixes:ds 8,0
v_source_page:db 0
v_source_ptr:dw 0
v_directory:dw 0
