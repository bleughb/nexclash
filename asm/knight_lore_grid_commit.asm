; Native16x16 grid extraction from exact tagged colour pixels.
; Work52..57, displays58..63/70..75; no separate owner canvas.
; Publish only outside every old/new sprite row and changed Layer2 row.
; Keep a14-line reservation for attribute writes, flip and sprite lookahead.
fg_patterns EQU 0x3D00
fg_dirty EQU 0x3E00
fg_grid EQU 0x3400
sc_heads EQU 0x3400
sc_next EQU 0x3680
sc_live EQU 0x3640
sc_used EQU 0x3500
sc_valid EQU 0x3600
sc_hashes EQU 0x3700
fg_attrs EQU 0x3800
fg_tile EQU 0x3B00

mark_grid:
        ld a,1
        ld (fg_changed),a
        xor a
        ld (fg_wrap),a
        ld a,(fc_x)
        ld c,a
        and 0xF0
        rrca
        rrca
        rrca
        rrca
        ld (fg_left),a
        ld a,(fc_w)
        or a
        jr z,.wide
        dec a
        add a,c
        jr nc,.xok
        ld a,1
        ld (fg_wrap),a
.wide: xor a
        ld (fg_left),a
        ld a,255
.xok:  rrca
        rrca
        rrca
        rrca
        and 15
        ld (fg_right),a
        ld a,(fc_y)
        ld c,a
        ld a,191
        sub c
        ret c
        and 0xF0
        ld (fg_bottom),a
        ld a,(fg_wrap)
        ld b,a
        ld a,(fc_h)
        dec a
        add a,b
        add a,c
        jr c,.top0
        cp 192
        jr c,.yok
.top0: ld a,191
.yok:  ld c,a
        ld a,191
        sub c
        and 0xF0
        ld c,a
.row:  ld a,(fg_left)
        add a,c
        ld l,a
        ld h,fg_dirty/256
        ld a,(fg_right)
        ld b,a
        ld a,(fg_left)
        sub b
        neg
        inc a
        ld b,a
.pixel:ld (hl),3
        inc l
        djnz .pixel
        ld a,(fg_bottom)
        cp c
        ret z
        ld a,c
        add a,16
        ld c,a
        jr .row

commit_frame:
        ld a,(v_active)
        or a
        ret z
        ld a,(fg_changed)
        or a
        ret z
        call fg_build
        ld a,(fg_overflow)
        or a
        jr z,.publish
        ; Only a union of old and new patterns that exhausts the cache
        ; needs the full-colour staging path. No in-use pattern is written.
        ld hl,fg_fallbacks
        inc (hl)
        call copy_display
        xor a
        ld (fg_safe_min),a
        ld a,191
        ld (fg_safe_max),a
        call fg_blank
        nextreg 0x15,0
        call fg_flip
        call fg_reset_live
        call fg_all_dirty
        call fg_build
        ld a,(fg_overflow)
        or a
        jr nz,.end
.publish:
        ; One complete initialization hides every unused hardware record.
        ; Later uploads include both the new records and the retired tail.
        ld a,(fg_attrs_initialized)
        or a
        ld hl,640
        jr z,.upload_size
        ld a,(fg_previous_count)
        ld b,a
        ld a,(fg_count)
        cp b
        jr nc,.larger
        ld a,b
.larger:
        ld l,a
        ld h,0
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
.upload_size:
        ld (fg_upload_bytes),hl
        call fg_blank
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,fg_attrs
        ld de,(fg_upload_bytes)
        ld c,0x57
        ld a,d
        or a
        jr z,.tail
.page: ld b,0
        otir
        dec d
        jr nz,.page
.tail: ld b,e
        ld a,b
        or a
        jr z,.written
        otir
.written:
        call fg_flip
        nextreg 0x15,1
        ld a,1
        ld (fg_attrs_initialized),a
        ld a,(fg_count)
        ld (fg_previous_count),a
        ld a,(fg_cur_min)
        ld (fg_old_min),a
        ld a,(fg_cur_max)
        ld (fg_old_max),a
        ld hl,sc_used
        ld de,sc_live
        ld bc,64
        ldir
        xor a
        ld (fg_changed),a
.end:  jp restore_maps

fg_reset_live:
        xor a
        ld hl,sc_live
        ld de,sc_live+1
        ld bc,63
        ld (hl),a
        ldir
        ret
fg_all_dirty:
        ld a,1
        ld (fg_changed),a
        ld hl,fg_dirty
        ld de,fg_dirty+1
        ld bc,191
        ld (hl),3
        ldir
        ret

fg_flip:
        ld a,(v_back)
        srl a
        nextreg 0x12,a
        nextreg 0x69,0x80
        ld a,(v_front)
        ld c,a
        ld a,(v_back)
        ld (v_front),a
        ld a,c
        ld (v_back),a
        ret

fg_blank:
        ; The beam may already be below the entire changed region, or the
        ; whole publication may finish before it reaches the region's top.
        ; Native raster is312 lines; active image occupies0..191.
        ld a,(fg_safe_min)
        ld l,a
        ld h,0
        ld de,298              ;312 minus14 reserved lines
        add hl,de
        ld (fg_late),hl
.wait: call hlib_line
        ld a,h
        or a
        jr nz,.below
        ld a,(fg_safe_max)
        cp l
        jr c,.below
        ld a,(fg_safe_min)
        sub l
        jr c,.wait
        cp 14
        jr c,.wait
        ret
.below:
        ld de,(fg_late)
        or a
        sbc hl,de
        ret c
        ret z
        jr .wait

; A=top nativeY of a16-pixel tile. Includes the complete row, so Layer2
; dirty tiles and old/new sprite positions share one conservative bound.
fg_bound:
        ld c,a
        ld a,(fg_safe_min)
        cp c
        jr c,.bottom
        ld a,c
        ld (fg_safe_min),a
.bottom:
        ld a,c
        add a,15
        ld c,a
        ld a,(fg_safe_max)
        cp c
        ret nc
        ld a,c
        ld (fg_safe_max),a
        ret

copy_display:
        ld a,52
        ld (v_copy_src),a
        ld a,(v_back)
        ld (v_copy_dst),a
        ld b,6
.page: push bc
        ld a,(v_copy_src)
        nextreg 0x50,a
        inc a
        ld (v_copy_src),a
        ld a,(v_copy_dst)
        nextreg 0x56,a
        inc a
        ld (v_copy_dst),a
        call hlib_dma_backend
        or a
        jr z,.cpu
        ld hl,fg_dma
        ld bc,(fg_dma_end-fg_dma)*256+0x6B
        otir
        jr .copied
.cpu:  ld hl,0
        ld de,0xC000
        ld bc,8192
        ldir
.copied:
        call pace_checkpoint
        pop bc
        djnz .page
        ret
fg_dma:
        db 0x83,0xC3,0x7D
        dw 0,8192
        db 0x14,0x10,0xAD
        dw 0xC000
        db 0x82,0xCF,0x87
fg_dma_end:

pace_checkpoint:
        ld a,(v_pace_active)
        cp 2
        jp z,hlib_debt_tick
        call resume_plot
        jp hold_plot

fg_build:
        exx
        push bc
        push de
        push hl
        exx
        xor a
        ld (fg_overflow),a
        ld (fg_index),a
        ld (fg_count),a
        ld (fg_cur_max),a
        ld a,192
        ld (fg_cur_min),a
        ld a,(fg_old_min)
        ld (fg_safe_min),a
        ld a,(fg_old_max)
        ld (fg_safe_max),a
        xor a
        ld hl,sc_used
        ld de,sc_used+1
        ld bc,63
        ld (hl),a
        ldir
        ld hl,fg_attrs
        ld (fg_attrptr),hl
.loop: ld a,(fg_index)
        ld l,a
        ld h,fg_dirty/256
        ld a,(v_back)
        cp 58
        ld a,1
        jr z,.bit
        ld a,2
.bit:  ld (fg_bit),a
        and (hl)
        jr z,.cached
        ld a,(fg_index)
        and 0xF0
        call fg_bound
        call fg_extract
        ld a,(fg_nonempty)
        or a
        jr z,.empty
        ld a,(fg_index)
        ld l,a
        ld h,fg_patterns/256
        ld a,(hl)
        ld (sc_hint),a
        ld hl,fg_tile
        call sc_get
        cp 255
        jr z,.overflow
        jr .storepattern
.empty:
        ld a,255
.storepattern:
        ld c,a
        ld a,(fg_index)
        ld l,a
        ld h,fg_patterns/256
        ld (hl),c
        ld h,fg_dirty/256
        ld a,(fg_bit)
        cpl
        and (hl)
        ld (hl),a
.cached:
        ld a,(fg_index)
        ld l,a
        ld h,fg_patterns/256
        ld a,(hl)
        cp 255
        jr z,.next
        ld (fg_pattern),a
        ld l,a
        ld h,sc_used/256
        ld (hl),1
        ld a,(fg_count)
        cp 128
        jr nc,.overflow
        inc a
        ld (fg_count),a
        call fg_attribute
.next: ld a,(fg_index)
        and 7
        cp 7
        call z,pace_checkpoint
        ld hl,fg_index
        inc (hl)
        ld a,(hl)
        cp 192
        jp c,.loop
        jr .done
.overflow:
        ld a,1
        ld (fg_overflow),a
.done:
        ; Retired records keep their old X/Y while visibility is removed.
        ; Bulk upload can therefore never transiently move an old visible
        ; tile to Y=0 before its disable byte reaches the sprite hardware.
        ld a,(fg_count)
        cp 128
        jr z,.hidden
        neg
        add a,128
        ld b,a
        ld hl,(fg_attrptr)
        inc hl
        inc hl
        inc hl
        ld de,5
.hide: ld (hl),0x40
        add hl,de
        djnz .hide
.hidden:
        exx
        pop hl
        pop de
        pop bc
        exx
        ret

fg_extract:
        ld a,(fg_index)
        and 15
        rlca
        rlca
        rlca
        rlca
        ld (fg_x),a
        ld e,a
        ld l,a
        ld a,(fg_index)
        and 16
        ld d,a
        or 0xC0
        ld h,a
        ld a,(fg_index)
        rrca
        rrca
        rrca
        rrca
        rrca
        and 7
        ld c,a
        add a,52
        nextreg 0x56,a
        ld a,(v_back)
        add a,c
        nextreg 0x50,a
        exx
        ld hl,fg_tile
        ld c,0
        exx
        ld c,16
.row:
        DUP 16
        ld a,(hl)
        or a
        jp m,1F
        exx
        ld (hl),a
        inc l
        ld c,h
        exx
        xor a
        ld (de),a
        jr 2F
1:      ld (de),a
        exx
        ld (hl),255
        inc l
        exx
2:      inc l
        inc e
        EDUP
        ld a,(fg_x)
        ld l,a
        ld e,a
        inc h
        inc d
        dec c
        jp nz,.row
        exx
        ld a,c
        exx
        ld (fg_nonempty),a
        ret

fg_attribute:
        ld a,(fg_index)
        and 0xF0
        call fg_bound
        ld a,(fg_index)
        and 0xF0
        ld c,a
        ld a,(fg_cur_min)
        cp c
        jr c,.bottom
        ld a,c
        ld (fg_cur_min),a
.bottom:
        ld a,c
        add a,15
        ld c,a
        ld a,(fg_cur_max)
        cp c
        jr nc,.bounds
        ld a,c
        ld (fg_cur_max),a
.bounds:
        ld hl,(fg_attrptr)
        ld a,(fg_index)
        and 15
        rlca
        rlca
        rlca
        rlca
        add a,32
        ld (hl),a
        ld a,0
        adc a,0
        ld c,a
        inc hl
        ld a,(fg_index)
        and 0xF0
        add a,32
        ld (hl),a
        inc hl
        ld (hl),c
        inc hl
        ld a,(fg_pattern)
        or 0xC0
        ld (hl),a
        inc hl
        ld (hl),0
        inc hl
        ld (fg_attrptr),hl
        ret

        INCLUDE "knight_lore_sprite_cache.asm"
fg_changed:db 0
fg_wrap:db 0
fg_bit:db 0
fg_fallbacks:db 0
fg_left:db 0
fg_right:db 0
fg_bottom:db 0
fg_index:db 0
fg_x:db 0
fg_pattern:db 0
fg_count:db 0
fg_nonempty:db 0
fg_overflow:db 0
fg_attrptr:dw 0

fg_safe_min:db 0
fg_safe_max:db 191
fg_old_min:db 192
fg_old_max:db 0
fg_cur_min:db 192
fg_cur_max:db 0
fg_late:dw 298

fg_attrs_initialized:db 0
fg_previous_count:db 0
fg_upload_bytes:dw 640
