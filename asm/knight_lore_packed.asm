; Packed colour/ownership canvas. Palette0..125 is dynamic;128..253 contains
; identical static colours.254inheritsULAink,255is transparent. Sources have
; their horizontal orientation prepared; vertical rows are walked here.
        DEVICE ZXSPECTRUMNEXT
        ORG 0x2000
fc_plot:
        ld a,(fc_w)
        or a
        ret z
        cp 65
        ret nc
        ld e,a
        ld d,0
        ld (fc_stride),de
        ld a,(fc_h)
        or a
        ret z
        cp 101
        ret nc
        ld a,(fc_y)
        cp 192
        ret nc
        ld a,(fc_orient)
        bit 7,a
        jr z,.forward
        ld a,(fc_h)
        dec a
        ld d,a
        mul d,e
        add hl,de
        push hl
        ld hl,0
        ld a,(fc_w)
        ld e,a
        ld d,0
        or a
        sbc hl,de
        ld (fc_stride),hl
        pop hl
.forward:
        ld (fc_src),hl
.row:
        call fc_map_y
        ld a,(fc_y)
        ld c,a
        ld a,191
        sub c
        and 31
        or 0xC0
        ld d,a
        ld a,(fc_x)
        ld e,a
        ld a,(fc_w)
        ld c,a
        ld b,0
        ld hl,(fc_src)
        add a,e
        jr c,.wrap
        call fc_copy
        jr .row_end
.wrap:
        ld (fc_remainder),a
        ld a,c
        push hl
        ld hl,fc_remainder
        sub (hl)
        pop hl
        ld c,a
        call fc_copy
        ld a,(fc_remainder)
        or a
        jr z,.row_end
        ld a,(fc_y)
        inc a
        cp 192
        jr nc,.row_end
        push hl
        ld c,a
        ld a,191
        sub c
        ld c,a
        and 31
        or 0xC0
        ld d,a
        ld e,0
        ld a,c
        srl a
        srl a
        srl a
        srl a
        srl a
        ld c,a
        ld a,(fc_cbase)
        add a,c
        nextreg 0x56,a
        pop hl
        ld a,(fc_remainder)
        ld c,a
        ld b,0
        call fc_copy
.row_end:
        ld hl,(fc_src)
        ld bc,(fc_stride)
        add hl,bc
        ld (fc_src),hl
        ld hl,fc_h
        dec (hl)
        ret z
        ld hl,fc_y
        inc (hl)
        ld a,(hl)
        cp 192
        jp c,.row
        ret
; HLsource,DEdestination,BC1..64. World sources already carry ownership.
; HUD sources inheritnoULAink and always become static, even if a graphic ID
; is normally an actor. These rare draws retain their original mask exactly.
fc_copy:
        ld a,(fc_ink)
        cp 255
        jr z,.hud
        ld a,255
        ldirx
        ret
.hud:
        ld b,c
.pixel:
        ld a,(hl)
        inc hl
        cp 254
        jr nc,.skip
        or 128
        ld (de),a
.skip:  inc de
        djnz .pixel
        ret
fc_map_y:
        ld a,(fc_y)
        ld c,a
        ld a,191
        sub c
        srl a
        srl a
        srl a
        srl a
        srl a
        ld c,a
        ld a,(fc_cbase)
        add a,c
        ld (fc_cpage),a
        nextreg 0x56,a
        ret
fc_clear:
        ld a,(fc_w)
        or a
        ret z
        cp 33
        ret nc
        ld a,(fc_h)
        or a
        ret z
        ld a,(fc_y)
        cp 192
        ret nc
.row:
        call fc_map_y
        ld a,(fc_fbase)
        add a,c
        nextreg 0x50,a
        ld a,(fc_y)
        ld c,a
        ld a,191
        sub c
        and 31
        ld h,a
        or 0xC0
        ld d,a
        ld a,(fc_x)
        ld l,a
        ld e,a
        ld a,(fc_w)
        ld b,0
        ld c,a
        sla c
        sla c
        sla c
        rl b
        ldir
        ld hl,fc_h
        dec (hl)
        ret z
        ld hl,fc_y
        inc (hl)
        ld a,(hl)
        cp 192
        jr c,.row
        ret
fc_orient:db 0
fc_stride:dw 0
fc_src:dw 0
fc_remainder:db 0
fc_x:db 0
fc_y:db 0
fc_w:db 0
fc_h:db 0
fc_owner:db 255
fc_ink:db 254
fc_cbase:db 52
fc_obase:db 64
fc_fbase:db 28
fc_cpage:db 0
fc_opage:db 0
fc_end:
        SAVEBIN "filmation_code.bin",0x2000,fc_end-0x2000
