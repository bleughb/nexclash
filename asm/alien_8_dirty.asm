; Per-screen16x16 flags: bit0 needs buffer28, bit1 needs buffer34.
; Retaining the other bit makes a changed local sprite tile rebuild until both
; display canvases have received its exact new holes and colours.
dirty_rectangle:
        ld a,7
        jr dirty_mark
dirty_candidates:
        ld a,4
dirty_mark:
        ld (dr_mask),a
        xor a
        ld (dr_wrap),a
        ld a,(fc_x)
        ld b,a
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (dr_left),a
        ld a,(fc_w)
        dec a
        add a,b
        jr nc,.right
        ld a,1
        ld (dr_wrap),a
        xor a
        ld (dr_left),a
        ld a,255
.right: rrca
        rrca
        rrca
        rrca
        and 15
        ld (dr_right),a
        ld a,(fc_y)
        cp 192
        ret nc
        ld b,a
        ld a,191
        sub b
        ld (dr_bottom),a
        ld b,a
        ld a,(fc_h)
        dec a
        ld c,a
        ld a,(dr_wrap)
        add a,c
        ld c,a
        ld a,b
        sub c
        jr nc,.top
        xor a
.top:   and 0xF0
        ld e,a
        ld d,0
        ld hl,DIRTY
        add hl,de
        ld a,(dr_left)
        add hl,a
        ld a,(dr_bottom)
        rrca
        rrca
        rrca
        rrca
        and 15
        ld b,a
        ld a,e
        rrca
        rrca
        rrca
        rrca
        sub b
        neg
        inc a
        ld b,a
.row:   push bc
        push hl
        ld a,(dr_right)
        ld b,a
        ld a,(dr_left)
        sub b
        neg
        inc a
        ld b,a
.col:   ld a,(dr_mask)
        or (hl)
        ld (hl),a
        inc hl
        djnz .col
        pop hl
        ld de,16
        add hl,de
        pop bc
        djnz .row
        ret

; A tile local to an object can overlap up to four screen-grid tiles.
; NZ means the mask must be rebuilt, Z permits exact cached-pattern reuse.
dirty_tile:
        ld a,(sp_top)
        and 0xF0
        ld l,a
        ld h,DIRTY/256
        ld a,(sp_left)
        rrca
        rrca
        rrca
        rrca
        and 15
        or l
        ld l,a
        ld c,(hl)
        ld a,(sp_left)
        and 15
        jr z,.down
        ld a,l
        and 15
        cp 15
        jr z,.down
        inc hl
        ld a,(hl)
        or c
        ld c,a
        dec hl
.down:  ld a,(sp_top)
        and 15
        jr z,.done
        ld a,l
        add a,16
        cp 192
        jr nc,.done
        ld l,a
        ld a,(hl)
        or c
        ld c,a
        ld a,(sp_left)
        and 15
        jr z,.done
        ld a,l
        and 15
        cp 15
        jr z,.done
        inc hl
        ld a,(hl)
        or c
        ld c,a
.done:  ld a,c
        or a
        ret

; Dirty any tile whose four original ULA attributes changed. The current
; attribute is resolved only at final ownership extraction, after game writes.
dirty_attributes:
        nextreg 0x50,25
        ld hl,0x5800
        ld de,4608
        ld ix,DIRTY
        ld b,24
.row:   push bc
        ld b,32
.col:   ld a,(de)
        cp (hl)
        jr z,.same
        ld a,(hl)
        ld (de),a
        ld (ix+0),7
.same:  inc hl
        inc de
        bit 0,b
        jr z,.noinc
        inc ix
.noinc: djnz .col
        pop bc
        bit 0,b
        jr nz,.nextrow
        push de
        ld de,-16
        add ix,de
        pop de
.nextrow:
        djnz .row
        ret

; Copy only changed tiles from the complete colour canvas to the hidden
; display. Sprite extraction removes only their currently owned figure pixels.
dirty_copy:
        ld a,(v_back)
        cp 28
        ld a,1
        jr z,.bit
        ld a,2
.bit:   ld (dr_bit),a
        ld ix,DIRTY
        xor a
        ld (dr_index),a
.tile:  ld a,(dr_index)
        and 7
        call z,hook_hold_tick
        ld a,(dr_bit)
        and (ix+0)
        jr z,.next
        ld a,(dr_index)
        and 0xF0
        call sprite_bound
        ld a,(dr_index)
        rlca
        rlca
        rlca
        and 7
        ld c,a
        add a,52
        nextreg 0x56,a
        ld a,(v_back)
        add a,c
        nextreg 0x57,a
        ld a,(dr_index)
        and 15
        rlca
        rlca
        rlca
        rlca
        ld l,a
        ld e,a
        ld a,(dr_index)
        and 16
        or 0xC0
        ld h,a
        or 0x20
        ld d,a
        ld b,16
.row:   push bc
        push hl
        push de
        DUP 16
        ldi
        EDUP
        pop de
        pop hl
        inc h
        inc d
        pop bc
        djnz .row
.next:  inc ix
        ld hl,dr_index
        inc (hl)
        ld a,(hl)
        cp 192
        jr c,.tile
        ret

dirty_reset:
        ld a,(dr_bit)
        or 4
        cpl
        ld c,a
        ld hl,DIRTY
        ld b,192
.loop:  ld a,(hl)
        and c
        ld (hl),a
        inc hl
        djnz .loop
        ret

dr_left: db 0
dr_right: db 0
dr_bottom: db 0
dr_index: db 0
dr_bit: db 1

; HL is an old8-byte object record; keep the pending plot geometry intact.
dirty_metadata:
        push hl
        ld hl,(fc_x)
        push hl
        ld hl,(fc_w)
        push hl
        pop de
        pop bc
        pop hl
        push bc
        push de
        inc hl
        ld a,(hl)
        ld (fc_x),a
        inc hl
        ld b,(hl)
        inc hl
        ld a,(hl)
        ld (fc_w),a
        inc hl
        ld a,(hl)
        ld (fc_h),a
        add a,b
        ld b,a
        ld a,192
        sub b
        ld (fc_y),a
        call dirty_rectangle
        pop hl
        ld (fc_w),hl
        pop hl
        ld (fc_x),hl
        ret

dirty_removed:
        nextreg 0x50,25
        ld ix,23432
        ld hl,1024
        ld b,56
.loop:  ld a,(hl)
        or a
        jr z,.next
        push hl
        ld de,6
        add hl,de
        ld a,(ix+0)
        cp (hl)
        pop hl
        jr z,.next
        push bc
        push hl
        call dirty_metadata
        pop hl
        ld (hl),0
        pop bc
.next:  ld de,8
        add hl,de
        ld de,32
        add ix,de
        djnz .loop
        ret

; NZ if any actual-change tile touches the pending primitive. Clear widths
; are temporarily converted to pixels by the queue caller (zero means256).
dirty_test_rectangle:
        ld a,(fc_x)
        ld b,a
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (dr_left),a
        ld a,(fc_w)
        dec a
        add a,b
        jr nc,.right
        xor a
        ld (dr_left),a
        ld a,255
.right: rrca
        rrca
        rrca
        rrca
        and 15
        ld (dr_right),a
        ld a,(fc_y)
        cp 192
        jr c,.valid
        xor a
        ret
.valid: ld b,a
        ld a,191
        sub b
        ld (dr_bottom),a
        ld b,a
        ld a,(fc_h)
        dec a
        ld c,a
        ld a,b
        sub c
        jr nc,.top
        xor a
.top:   and 0xF0
        ld e,a
        ld d,0
        ld hl,DIRTY
        add hl,de
        ld a,(dr_left)
        add hl,a
        ld a,(dr_bottom)
        rrca
        rrca
        rrca
        rrca
        and 15
        ld b,a
        ld a,e
        rrca
        rrca
        rrca
        rrca
        sub b
        neg
        inc a
        ld b,a
.row:   push bc
        push hl
        ld a,(dr_right)
        ld b,a
        ld a,(dr_left)
        sub b
        neg
        inc a
        ld b,a
.col:   bit 2,(hl)
        jr nz,.found
        inc hl
        djnz .col
        pop hl
        ld de,16
        add hl,de
        pop bc
        djnz .row
        xor a
        ret
.found: pop hl
        pop bc
        ld a,1
        or a
        ret

dr_mask: db 7
dr_wrap: db 0

; Final exact ownership comparison. Candidate bounds include every original
; clear and full plot. Source/pose/palette changes separately retain bits0/1.
; All world records, static and moving, have distinct ownership identities.
owner_compare:
        ld ix,DIRTY
        xor a
        ld (oc_index),a
.tile:  ld a,(oc_index)
        and 7
        call z,hook_hold_tick
        bit 2,(ix+0)
        jp z,.next
        ld a,(oc_index)
        rlca
        rlca
        rlca
        and 7
        ld c,a
        add a,52
        nextreg 0x56,a
        ld a,c
        add a,40
        nextreg 0x57,a
        ld a,(oc_index)
        and 15
        rlca
        rlca
        rlca
        rlca
        ld l,a
        ld e,a
        ld a,(oc_index)
        and 16
        or 0xC0
        ld h,a
        or 0x20
        ld d,a
        ld (oc_src),hl
        ld (oc_dst),de
        ld b,16
.row:
        DUP 16
        ld a,(de)
        cp (hl)
        jp nz,.different
        inc l
        inc e
        EDUP
        ld a,l
        sub 16
        ld l,a
        ld e,a
        inc h
        inc d
        djnz .row
        jr .next
.different:
        ld a,(ix+0)
        or 3
        ld (ix+0),a
        ld hl,(oc_src)
        ld de,(oc_dst)
        ld b,16
.copy:  push bc
        push hl
        push de
        DUP 16
        ldi
        EDUP
        pop de
        pop hl
        inc h
        inc d
        pop bc
        djnz .copy
.next:  res 2,(ix+0)
        inc ix
        ld hl,oc_index
        inc (hl)
        ld a,(hl)
        cp 192
        jp c,.tile
        ret
oc_index: db 0
oc_src: dw 0
oc_dst: dw 0
