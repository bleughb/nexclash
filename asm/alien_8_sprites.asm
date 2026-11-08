; Exact aligned16x16 hardware grid from final tagged colour canvas.
; bit7 marks static scenery; dynamic126 inherits the matching ULA ink.
; One exact global8bpp palette permits mixed original and painted figures.
sprite_build:
        push ix
        push iy
        ld hl,sc_nextused
        ld de,sc_nextused+1
        ld bc,127
        ld (hl),0
        ldir
        xor a
        ld (sp_count),a
        ld (sp_index),a
        ld (sp_overflow),a
        ld hl,ATTS
        ld (sp_attrptr),hl
.tile:  call sprite_tile
        ld a,(sp_overflow)
        or a
        jr nz,.done
        ld hl,sp_index
        inc (hl)
        ld a,(hl)
        cp 192
        jr c,.tile
.done: pop iy
        pop ix
        ret

sprite_tile:
        ld a,(sp_index)
        and 7
        call z,hook_hold_tick
        ld a,(sp_index)
        and 0xF0
        ld (sp_top),a
        ld a,(sp_index)
        and 15
        rlca
        rlca
        rlca
        rlca
        ld (sp_left),a
        ld a,(sp_index)
        ld h,8
        ld l,a
        ld (sp_cacheptr),hl
        ld h,DIRTY/256
        ld a,(hl)
        or a
        jr nz,.rebuild
        nextreg 0x50,25
        ld hl,(sp_cacheptr)
        ld a,(hl)
        cp 255
        ret z
        ld (sp_pattern),a
        ld l,a
        ld h,sc_used/256
        ld (hl),1
        ld h,sc_nextused/256
        ld (hl),1
        jp .attributes
.rebuild:
        xor a
        ld (sp_row),a
        ld a,(sp_index)
        rlca
        rlca
        rlca
        and 7
        ld c,a
        add a,52
        nextreg 0x56,a
        ld a,(v_back)
        add a,c
        nextreg 0x54,a
        ld a,(sp_top)
        and 31
        or 0xC0
        ld h,a
        ld a,(sp_left)
        ld l,a
        push hl
        call sprite_presence
        pop hl
        jr nc,.has_pixels
        nextreg 0x50,25
        ld hl,(sp_cacheptr)
        ld (hl),255
        ret
.has_pixels:
        ld de,PAT
.row:  ld a,(sp_row)
        and 7
        call z,sprite_inks
        ld a,(hl)
        or a
        jp m,.static0
        cp 126
        jr nz,.ink0
        ld a,b
.ink0:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value0
.static0:
        ld a,255
.value0:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static1
        cp 126
        jr nz,.ink1
        ld a,b
.ink1:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value1
.static1:
        ld a,255
.value1:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static2
        cp 126
        jr nz,.ink2
        ld a,b
.ink2:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value2
.static2:
        ld a,255
.value2:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static3
        cp 126
        jr nz,.ink3
        ld a,b
.ink3:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value3
.static3:
        ld a,255
.value3:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static4
        cp 126
        jr nz,.ink4
        ld a,b
.ink4:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value4
.static4:
        ld a,255
.value4:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static5
        cp 126
        jr nz,.ink5
        ld a,b
.ink5:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value5
.static5:
        ld a,255
.value5:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static6
        cp 126
        jr nz,.ink6
        ld a,b
.ink6:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value6
.static6:
        ld a,255
.value6:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static7
        cp 126
        jr nz,.ink7
        ld a,b
.ink7:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value7
.static7:
        ld a,255
.value7:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static8
        cp 126
        jr nz,.ink8
        ld a,c
.ink8:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value8
.static8:
        ld a,255
.value8:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static9
        cp 126
        jr nz,.ink9
        ld a,c
.ink9:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value9
.static9:
        ld a,255
.value9:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static10
        cp 126
        jr nz,.ink10
        ld a,c
.ink10:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value10
.static10:
        ld a,255
.value10:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static11
        cp 126
        jr nz,.ink11
        ld a,c
.ink11:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value11
.static11:
        ld a,255
.value11:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static12
        cp 126
        jr nz,.ink12
        ld a,c
.ink12:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value12
.static12:
        ld a,255
.value12:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static13
        cp 126
        jr nz,.ink13
        ld a,c
.ink13:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value13
.static13:
        ld a,255
.value13:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static14
        cp 126
        jr nz,.ink14
        ld a,c
.ink14:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value14
.static14:
        ld a,255
.value14:
        ld (de),a
        inc e
        inc l
        ld a,(hl)
        or a
        jp m,.static15
        cp 126
        jr nz,.ink15
        ld a,c
.ink15:
        res 6,h
        ld (hl),255
        set 6,h
        jr .value15
.static15:
        ld a,255
.value15:
        ld (de),a
        inc e
        inc l
        ld a,l
        sub 16
        ld l,a
        inc h
        ld a,(sp_row)
        inc a
        ld (sp_row),a
        cp 16
        jp c,.row
.cache: nextreg 0x50,25
        ld hl,(sp_cacheptr)
        ld a,(hl)
        ld (sc_hint),a
        ld hl,PAT
        call sc_get
        cp 255
        jr z,.overflow
        ld (sp_pattern),a
        nextreg 0x50,25
        ld hl,(sp_cacheptr)
        ld (hl),a
.attributes:
        ld a,(sp_top)
        call sprite_bound
        ld a,(sp_cur_min)
        ld b,a
        ld a,(sp_top)
        cp b
        jr nc,.min_done
        ld (sp_cur_min),a
.min_done:
        ld a,(sp_top)
        add a,15
        ld b,a
        ld a,(sp_cur_max)
        cp b
        jr nc,.max_done
        ld a,b
        ld (sp_cur_max),a
.max_done:
        ld a,(sp_count)
        cp 128
        jr nc,.overflow
        ld hl,(sp_attrptr)
        ld a,(sp_left)
        add a,32
        ld (hl),a
        inc hl
        ld a,0
        adc a,0
        ld c,a
        ld a,(sp_top)
        add a,32
        ld (hl),a
        inc hl
        ld (hl),c
        inc hl
        ld a,(sp_pattern)
        or 0xC0
        ld (hl),a
        inc hl
        ld (hl),0
        inc hl
        ld (sp_attrptr),hl
        ld hl,sp_count
        inc (hl)
        ret
.overflow:
        ld a,1
        ld (sp_overflow),a
        ret

 ; Carry means all256 pixels are static/transparent. This cheap scan avoids
; materializing and hashing a transparent pattern for scenery-only grid tiles.
sprite_presence:
        ld b,16
.row:
        DUP 16
        ld a,(hl)
        add a,a
        jr nc,.found
        inc l
        EDUP
        ld a,l
        sub 16
        ld l,a
        inc h
        djnz .row
        scf
        ret
.found: or a
        ret

; Four ULA attribute reads per tile, never per pixel. Returns left/right B/C.
sprite_inks:
        push hl
        push de
        ld a,(sp_top)
        ld c,a
        ld a,(sp_row)
        add a,c
        and 0xF8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,(sp_left)
        rrca
        rrca
        rrca
        and 31
        add hl,a
        ld de,0x5800
        add hl,de
        ld a,(hl)
        call .ink
        ld b,a
        inc hl
        ld a,(hl)
        call .ink
        ld c,a
        pop de
        pop hl
        ret
.ink:  ld c,a
        and 7
        ld e,a
        ld a,c
        and 64
        rrca
        rrca
        rrca
        or e
        or 64
        ret

sprite_publish:
        ; Complete attributes first, then hide any old slots not used now.
        ld bc,0x303B
        xor a
        out (c),a
        ld a,(sp_count)
        or a
        jr z,.hide
        ld e,a
        ld hl,ATTS
.attrs:ld bc,0x0557
        otir
        dec e
        jr nz,.attrs
.hide: ld a,(sp_count)
        nextreg 0x34,a
        ld b,a
        ld a,(sp_prev_count)
        sub b
        jr z,.finish
        jr c,.finish
        ld b,a
.hide_loop:
        nextreg 0x78,0
        djnz .hide_loop
.finish:
        ld a,(sp_count)
        ld (sp_prev_count),a
        ld a,(sp_cur_min)
        ld (sp_old_min),a
        ld a,(sp_cur_max)
        ld (sp_old_max),a
        ld hl,sc_nextused
        ld de,sc_used
        ld bc,128
        ldir
        nextreg 0x15,1
        ret


sp_cacheptr: dw 0
sp_attrptr: dw ATTS
sp_count: db 0
sp_index: db 0
sp_left: db 0
sp_top: db 0
sp_row: db 0
sp_any: dw 0
sp_pattern: db 0
sp_overflow: db 0

; A pattern-union/attribute overflow presents the exact complete colour canvas
; for this frame, then rebuilds the whole hardware set with no live references.
; No partially cut-out Layer2 frame is ever published.
sprite_fallback:
        xor a
        ld (sp_safe_min),a
        ld (sp_cur_max),a
        ld a,191
        ld (sp_safe_max),a
        ld a,255
        ld (sp_cur_min),a
        ld hl,sp_fallbacks
        inc (hl)
        ld a,(v_back)
        ld (v_copy_page),a
        ld a,52
        ld (v_colour_page),a
        ld b,6
.page:  push bc
        ld a,(v_colour_page)
        nextreg 0x56,a
        ld a,(v_copy_page)
        nextreg 0x57,a
        call copy8k
        ld hl,v_colour_page
        inc (hl)
        ld hl,v_copy_page
        inc (hl)
        pop bc
        djnz .page
        ld hl,DIRTY
        ld de,DIRTY+1
        ld bc,191
        ld (hl),3
        ldir
        ld hl,sc_nextused
        ld de,sc_nextused+1
        ld bc,127
        ld (hl),0
        ldir
        xor a
        ld (sp_count),a
        ret
sp_fallbacks: db 0

; Include all old/new sprite rows, plus every changed Layer2 tile row.
sprite_bounds_start:
        ld a,(sp_old_min)
        ld (sp_safe_min),a
        ld a,(sp_old_max)
        ld (sp_safe_max),a
        ld a,255
        ld (sp_cur_min),a
        xor a
        ld (sp_cur_max),a
        ret
sprite_bound:
        ld c,a
        ld a,(sp_safe_min)
        cp c
        jr c,.bottom
        ld a,c
        ld (sp_safe_min),a
.bottom:
        ld a,c
        add a,15
        ld c,a
        ld a,(sp_safe_max)
        cp c
        ret nc
        ld a,c
        ld (sp_safe_max),a
        ret
sprite_blank:
        call hook_hold_tick
        ld a,(sp_safe_min)
        cp 255
        ret z
        ld l,a
        ld h,0
        ld de,298
        add hl,de
        ld (sp_late),hl
.wait: call hlib_line
        ld a,h
        or a
        jr nz,.below
        ld a,(sp_safe_max)
        cp l
        jr c,.below
        ld a,(sp_safe_min)
        sub l
        jr c,.wait
        cp 14
        jr c,.wait
        ret
.below:
        ld de,(sp_late)
        or a
        sbc hl,de
        ret c
        ret z
        jr .wait
sp_old_min: db 255
sp_old_max: db 0
sp_cur_min: db 255
sp_cur_max: db 0
sp_safe_min: db 255
sp_safe_max: db 0
sp_late: dw 0

sp_prev_count: db 128
