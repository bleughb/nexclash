; Filmation exact tagged-colour compositor primitive. Original game memory is untouched.
; Input rows use the game's bottom-up order; canvases use native top-down order.
; Colour pixels and owner bytes each
; occupy six consecutive 8K pages. Hooks execute in slot1, stack outside slots0/6/7.
; Caller must own MMU0/6/7 with interrupts disabled, and restore the mappings.
; 254 inherits fc_ink; 255 is transparent. Black0 remains opaque.
; The owner byte identifies the latest plot, so later ink AND mask both occlude.

; Inputs via fc_* variables below; HL = source offset in the selected source page.
; fc_x,fc_y: native pixel coordinates, Y counted from the bottom.
; fc_w=1..64, fc_h=1..100, source graphic may not straddle an8K page.
; fc_cbase,fc_obase: first pages for the colour and ownership canvases.
; fc_owner: caller's object ID, 255 for static scenery.
; All main registers lost; IX/IY/alternate set untouched.
fc_plot:
        ld a,(fc_h)
        or a
        ret z
        ld a,(fc_y)
        cp 192
        ret nc
        ld (fc_src),hl
.row:   ld a,(fc_y)
        and 15
        call z,hook_hold_tick
        call fc_map_y
        ld a,(fc_x)
        ld e,a
        ld a,(fc_y)
        ld c,a
        ld a,191
        sub c
        ld (fc_dy),a
        and 31
        or 0xC0
        ld d,a
        ld hl,(fc_src)
        ld a,(hl)
        inc hl
        ld (fc_runs),a
        or a
        jp z,.row_end
.run:   ld a,(hl)
        inc hl
        add a,e
        ld e,a
        call c,fc_wrap
        ret c
        ld a,(hl)
        inc hl
        ld (fc_runleft),a
.piece: ld a,e
        neg
        ld c,a
        ld a,(fc_runleft)
        jr z,.length
        cp c
        jr c,.length
        ld a,c
.length:
        ld (fc_piece),a
        ld c,a
        ld b,0
        ldir
        ld a,e
        or a
        jr nz,.not_wrap
        dec d
        call fc_wrap
.not_wrap:
        ret c
        ld a,(fc_piece)
        ld b,a
        ld a,(fc_runleft)
        sub b
        ld (fc_runleft),a
        jr nz,.piece
        ld a,(fc_runs)
        dec a
        ld (fc_runs),a
        jr nz,.run
.row_end:
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

; Cursor wraps into the preceding native row, matching the original buffer.
; Carry means it spilled beyond the top edge and no more pixels are visible.
fc_wrap:
        ld a,(fc_dy)
        or a
        jr nz,.inside
        scf
        ret
.inside:
        dec a
        ld (fc_dy),a
        dec d
        ld a,d
        cp 0xBF
        jr nz,.done
        ld a,(fc_cpage)
        dec a
        ld (fc_cpage),a
        nextreg 0x56,a
        ld d,0xDF
.done:  or a
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

; Dirty clear: fc_x is byte-aligned, fc_w is1..32 bytes, fc_h1..192rows.
; Restore the selected floor pixels, including transparent255, and owner255.
; The rectangles supplied by the game's dirty-copy path do not wrap horizontally.
; fc_fbase names the selected floor's first8Kpage.
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
        ld a,(fc_y)
        and 15
        call z,hook_hold_tick
        call fc_map_y
        ld a,(fc_fbase)
        or a
        jr nz,.floor_page
        ld a,27
        jr .mapped_floor
.floor_page:
        add a,c
.mapped_floor:
        nextreg 0x50,a
        ld a,(fc_y)
        ld c,a
        ld a,191
        sub c
        ld (fc_dy),a
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
        rl b
        sla c
        rl b
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
        jp c,.row
        ret

fc_src:   dw 0
fc_x:     db 0
fc_y:     db 0
fc_w:     db 0
fc_h:     db 0
fc_owner: db 255
fc_ink:   db 247
fc_cbase: db 52
fc_obase: db 40
fc_fbase: db 0
fc_cpage: db 0
fc_opage: db 0
fc_end:

fc_dy: db 0
fc_left: db 0

fc_runs: db 0
fc_runleft: db 0
fc_piece: db 0
