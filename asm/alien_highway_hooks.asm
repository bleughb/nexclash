; Alien Highway. Track opaque ink and paper through all four original plotters.
; The game still renders every byte and reads its own screen. At its screen commit,
; publish the occupied portions of the 363 road cells as 16x16 hardware sprites.
        DEVICE ZXSPECTRUMNEXT
PAGE_CODE equ 28
PAGE_ALPHA equ 30
PAGE_MASK equ 32
HLIB_V_R equ $3c00
saved_sp equ $3c04
saved_speed equ $3c06
window_speed equ $3c0a
window_open equ $3c0b
window_budget equ $3c0c
spare equ $3c07
current_slot equ $3c08
quadrants equ $3c09
HLIB_V_PACE equ $3d10
HLIB_PACE_NL equ 312
clear_sp equ $3d30
old_patterns equ $3c20
shown equ $3ca0
regblock equ $3f40
pattern_buf equ $3700
tile_list equ $3800
pixels_lo equ $3400
pixels_hi equ $3500
        org $2200
rom_start:
        include "lib/hlib_speed.asm"
        include "lib/hlib_r.asm"
        include "lib/hlib_iff.asm"
        include "lib/hlib_pace.asm"
        DEFINE HLIB_PC_OTIR
        DEFINE HLIB_NO_BLITTER
        include "lib/hlib_dma.asm"
        macro ENTRY
        nextreg $51,PAGE_CODE
        ld (saved_sp),sp
        ld sp,$3f00
        HLIB_R_IN
        push af
        push bc
        push de
        push hl
        HLIB_SPEED_IN saved_speed
        nextreg $50,PAGE_ALPHA
        endm
        macro EXIT delta
        nextreg $50,$ff
        ld a,delta
        call hlib_r_set
        HLIB_SPEED_OUT saved_speed
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(saved_sp)
        HLIB_R_OUT
        nextreg $51,$ff
        endm
        macro PLOT phase,k,finish
        ENTRY
        push bc
        push de
        call hlib_pace_tick
        ld hl,(window_budget)
        ; Original 24-row plotter and list traversal, in sixteenths of a line.
        IF phase=0
            ld de,686
        ELSEIF phase=1
            ld de,710
        ELSEIF phase=2
            ld de,665
        ELSE
            ld de,465
        ENDIF
        add hl,de
        ld (window_budget),hl
        pop de
        pop bc
        nextreg $52,PAGE_MASK+phase
        call accumulate
        nextreg $52,10
        EXIT -13
        IF phase=0
        ld l,c
        ld h,b
        ELSE
        ld h,b
        ld l,c
        ENDIF
        IF phase=3
        ld b,k
        ELSE
        ld a,k
        ENDIF
        jp finish
        endm
plot_right: PLOT 0,24,$8fd9
plot_left4: PLOT 1,24,$9077
plot_left2: PLOT 2,24,$90cc
plot_even:  PLOT 3,24,$9116

; DE is a six-byte-row source, BC is the bottom destination. The compact
; coverage record has three bytes per row, in the game's bottom-first order.
accumulate:
        ld a,b
        cp $e9
        ret c
        ex de,hl
        ld de,$b6b0
        or a
        sbc hl,de
        srl h
        rr l
        set 6,h
        ld e,c
        ld a,b
        sub $e6
        ld d,a
        ld bc,-34
        ex de,hl
        dup 24
        ld a,(de)
        or (hl)
        ld (hl),a
        inc de
        inc hl
        ld a,(de)
        or (hl)
        ld (hl),a
        inc de
        inc hl
        ld a,(de)
        or (hl)
        ld (hl),a
        inc de
        add hl,bc
        edup
        ret

publish:
        ENTRY
        call hlib_pace_tick
        push ix
        push iy
        ; The original changes the road from bright cyan through black to
        ; normal white. These are source attributes, including the blackout.
        ld a,($58f0)
        ld c,a
        rlca
        rlca
        and 1
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,c
        and 7
        or b
        ld hl,spectrum_rgb
        add hl,a
        ld a,(hl)
        nextreg $40,2
        nextreg $41,a
        ld a,c
        rrca
        rrca
        rrca
        and 7
        or b
        ld hl,spectrum_rgb
        add hl,a
        ld a,(hl)
        nextreg $40,1
        nextreg $41,a
        ld a,1
        call hlib_dma_init
        ; The sprite library packet transfers 256 bytes by default. This
        ; renderer owns the packet and transfers one 128-byte half-pattern.
        ld hl,128
        ld (hlib_dma_sp_src+2),hl
        ld ix,tile_list
        xor a
        ld (current_slot),a
.loop:
        ld l,(ix+0)
        ld h,(ix+1)
        ld a,(ix+4)
        ld (quadrants),a
        ; HL is the first ownership byte. Skip empty tiles before expanding.
        push hl
        ld de,31
        xor a
        dup 16
        or (hl)
        inc hl
        or (hl)
        add hl,de
        edup
        pop hl
        and a
        jr z,.hide
        call render_tile
        jr .advance
.hide:
        ld a,(current_slot)
        ld e,a
        ld d,0
        ld hl,shown
        add hl,de
        ld a,(hl)
        and a
        jr z,.advance
        ld (hl),0
        ld a,e
        nextreg $34,a
        nextreg $38,0
.advance:
        ld de,5
        add ix,de
        ld a,(current_slot)
        inc a
        ld (current_slot),a
        and 15
        call z,hlib_pace_tick
        ld a,(current_slot)
        cp 98
        jp nz,.loop
        nextreg $15,1
        pop iy
        pop ix
        ld a,(window_open)
        or a
        jr z,publish_restore
        xor a
        ld (window_open),a
        ld a,(window_speed)
        ld (saved_speed),a
        ld hl,(window_budget)
        call hlib_pace_wait
publish_restore:
        EXIT -13
        ld a,($880b)
        jp $919d

; HL is in the private coverage plane. The original working bitmap is $e600
; above it. Each quadrant has its own road-cell clipping bit.
render_tile:
        ld de,$e600
        add hl,de
        push hl
        pop iy
        or a
        sbc hl,de
        ld de,pattern_buf
        ld b,2
.half:
        push bc
        ld b,8
.row:
        ld a,(quadrants)
        rrca
        sbc a,a
        and (hl)
        ld c,(iy+0)
        call emit_byte
        inc hl
        ld a,(quadrants)
        rrca
        rrca
        sbc a,a
        and (hl)
        ld c,(iy+1)
        call emit_byte
        push de
        ld de,31
        add hl,de
        inc de
        add iy,de
        pop de
        djnz .row
        ld a,(quadrants)
        rrca
        rrca
        ld (quadrants),a
        pop bc
        djnz .half
        ; Upload to the one spare pattern, then swap the displayed pattern.
        ld a,(spare)
        rrca
        ld bc,$303b
        out (c),a
        ld hl,pattern_buf
        call hlib_dma_backend
        or a
        jr z,.software
        call hlib_dma_sprite
        jr .uploaded
.software:
        ld bc,$805b
        otir
.uploaded:
        ld a,(current_slot)
        nextreg $34,a
        ld e,a
        ld d,0
        ld hl,shown
        add hl,de
        ld (hl),1
        ld hl,old_patterns
        add hl,de
        ld a,(spare)
        ld e,(hl)
        ld (hl),a
        rrca
        ld d,a
        and $3f
        or $c0
        nextreg $38,a
        ld a,d
        and $80
        rrca
        or $80
        nextreg $39,a
        ld a,e
        ld (spare),a
        ret

; A=opaque bits, C=game ink bits. A lookup maps each nibble pair to
; four 4-bit pixels. Both native black and transparent have distinct indices.
emit_byte:
        push hl
        push bc
        ld b,a
        and $f0
        ld h,a
        ld a,c
        swapnib
        and 15
        or h
        ld l,a
        ld h,high pixels_lo
        ld a,(hl)
        ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        ld a,b
        swapnib
        and $f0
        ld h,a
        ld a,c
        and 15
        or h
        ld l,a
        ld h,high pixels_lo
        ld a,(hl)
        ld (de),a
        inc de
        inc h
        ld a,(hl)
        ld (de),a
        inc de
        pop bc
        pop hl
        ret
; Sort at the caller's clock. Only the sorted draw list and the road copy
; run fast. Their original time depends on the plotter mix and dirty cells.
draw_open:
        ENTRY
        call hlib_pace_open
        ld a,(saved_speed)
        ld (window_speed),a
        ld a,1
        ld (window_open),a
        ld a,3
        ld (saved_speed),a
        ld hl,1550
        ld (window_budget),hl
        call clear_alpha
        EXIT -13
        ld hl,$8300
        jp $8f6f
clear_alpha:
        ; Only the visible 144 scanlines are consumed at publication.
        ld (clear_sp),sp
        ld sp,$1500
        ld de,0
        ld b,144
.row:
        dup 16
        push de
        edup
        djnz .row
        ld sp,(clear_sp)
        ret
scene_open:
        ENTRY
        call clear_alpha
        xor a
.hide:
        nextreg $34,a
        nextreg $38,0
        inc a
        cp 98
        jr nz,.hide
        EXIT -13
        ld hl,$fd00
        jp $8c45
; Bulk clears can bypass the scene builder, including the ending.
        macro HIDE_SCREEN original_hl,continuation
        ENTRY
        nextreg $15,0
        EXIT -13
        ld hl,original_hl
        jp continuation
        endm
; All ten road-copy callers enter here before the first ULA write.
; The original ULA supplies the figures until publish has finished every slot.
copy_open:
        ENTRY
copy_hide:
        nextreg $15,0
        push ix
        ld ix,$8700
        ld hl,0
.row:
        ld b,(ix+0)
        ld e,(ix+5)
        ld d,(ix+6)
.cell:
        ld a,(de)
        and a
        jr z,.clean
        inc hl
.clean:
        dec e
        djnz .cell
        ld de,7
        add ix,de
        ld a,(ix+0)
        and a
        jr nz,.row
        pop ix
        ; Each dirty cell adds eight screen writes, about 269 T-states.
        ; 19.25 sixteenths per cell at 224 T-states per line.
        ld d,h
        ld e,l
        srl h
        rr l
        srl h
        rr l
        add hl,de
        add hl,de
        add hl,de
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
        ld de,(window_budget)
        add hl,de
        ld (window_budget),hl
        EXIT -13
        ld hl,$8700
        jp $9140
clear_end:   HIDE_SCREEN $5aff,$a370
clear_hud:   HIDE_SCREEN $5aff,$9cd7
clear_title: HIDE_SCREEN $4000,$a957
clear_menu:
        ENTRY
        nextreg $15,0
        EXIT -13
        xor a
        ld ($a90b),a
        jp $a6ee
spectrum_rgb:
        db $00,$02,$a0,$a2,$14,$16,$b4,$b6
        db $00,$03,$e0,$e7,$1c,$1f,$fc,$ff
rom_end:
        assert rom_end < pixels_lo
        SAVEBIN "alien_rom.bin",rom_start,rom_end-rom_start

        org $d000
setup:
        nextreg $51,PAGE_CODE
        nextreg $43,$20
        nextreg $40,1
        nextreg $41,0
        nextreg $40,2
        nextreg $41,$b6
        nextreg $4b,0
        ld a,98
        ld (spare),a
        ld hl,old_patterns
        ld ix,tile_list
        xor a
.slot:
        ld (hl),a
        inc hl
        nextreg $34,a
        push af
        ld a,(ix+2)
        nextreg $35,a
        ld a,(ix+3)
        nextreg $36,a
        ld a,(ix+4)
        rlca
        and 1
        nextreg $37,a
        nextreg $38,0
        ld de,5
        add ix,de
        pop af
        inc a
        cp 98
        jr nz,.slot
        ; The other 30 of the 128 hardware slots also start hidden.
.rest:
        nextreg $34,a
        nextreg $38,0
        inc a
        cp 128
        jr nz,.rest
        nextreg $15,1
        nextreg $51,$ff
        ret
        SAVEBIN "alien_setup.bin",setup,$-setup
