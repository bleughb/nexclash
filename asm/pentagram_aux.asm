; Cached tile builder, never active while original game code executes.
        ORG 0xA000
fg_build:
        exx
        push bc
        push de
        push hl
        exx
        ld a,(fg_cold)
        or a
        call nz,fg_prepare_cold
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
        bit 2,(hl)
        jr z,.buffer_check
        call fg_history
        ld a,(fg_index)
        ld l,a
        ld h,fg_dirty/256
        res 2,(hl)
        jr z,.buffer_check
        ; Only a real tagged-pixel change dirties both display buffers.
        ld a,(hl)
        or 3
        ld (hl),a
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
        jr .clean_buffer
.buffer_check:
        ld a,(fg_bit)
        and (hl)
        jr z,.cached
        ld a,(fg_index)
        and 0xF0
        call fg_bound
        call fg_history_copyfront
.clean_buffer:
        ld a,(fg_index)
        ld l,a
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

 ; Compare the exact tagged tile with its prior published image. Unchanged
; tiles reuse their protected live pattern and copy the prior static Layer2
; tile into the other buffer. A collision-free full comparison is required.
fg_history:
        call .prepare
        ld a,(fg_history_valid)
        or a
        jr z,.changed
        ld c,16
.row:
        DUP 16
        ld a,(de)
        cp (hl)
        jr nz,.changed
        inc l
        inc e
        EDUP
        ld a,(fg_x)
        ld l,a
        ld e,a
        inc h
        inc d
        dec c
        jr nz,.row
        xor a
        ret
.changed:
        call .prepare
        call .copy
        ld a,1
        or a
        ret
.prepare:
        ld a,(fg_index)
        and 15
        rlca
        rlca
        rlca
        rlca
        ld (fg_x),a
        ld l,a
        ld e,a
        ld a,(fg_index)
        and 16
        or 0xC0
        ld h,a
        or 0x20
        ld d,a
        ld a,(fg_index)
        rrca
        rrca
        rrca
        rrca
        rrca
        and 7
        ld b,a
        add a,52
        nextreg 0x56,a
        ld a,b
        add a,78
        nextreg 0x57,a
        ret
.copy: ld a,16
.line: push af
        ld bc,16
        ldir
        ld bc,240
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        pop af
        dec a
        jr nz,.line
        ret
fg_history_copyfront:
        call fg_history.prepare
        ld a,(v_front)
        add a,b
        nextreg 0x56,a
        ld a,(v_back)
        add a,b
        nextreg 0x50,a
        ld a,d
        and 31
        ld d,a
        jp fg_history.copy

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
        ld a,255
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

        INCLUDE "pentagram_cache.asm"
aux_end:
        ASSERT $ <= 0xC000
