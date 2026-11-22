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
.pixel:ld a,(fg_mark_bits)
        or (hl)
        ld (hl),a
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
        call fg_build_bridge
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
        call fg_build_bridge
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
        ld a,1
        ld (fg_history_valid),a
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
        ld (fg_history_valid),a
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
        ld (hl),7
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

fg_prepare_cold:
        ; h_fullclear has hidden both display layers. Initialize both Layer2
        ; buffers and exact history in bulk; only coarse dynamic tiles then
        ; need extraction. Never use this path on a visible overflow retry.
        xor a
        ld (fg_cold),a
        ld a,(v_back)
        push af
        call copy_display
        ld a,(v_front)
        ld (v_back),a
        call copy_display
        ld a,78
        ld (v_back),a
        call copy_display
        pop af
        ld (v_back),a
        ld hl,fg_dirty
        ld de,fg_patterns
        ld b,192
.tile: bit 3,(hl)
        jr nz,.dynamic
        ld (hl),0
        ld a,255
        ld (de),a
.dynamic:
        inc l
        inc e
        djnz .tile
        ret
fg_cold:db 0
fg_mark_bits:db 4

fg_history_valid:db 0
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

; The auxiliary builder runs only while original game RAM in slot5 is idle.
fg_build_bridge:
        nextreg 0x55,84
        call fg_build
        nextreg 0x55,5
        ret
