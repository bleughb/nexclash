; Sparse 16x16 tiles. A pattern byte is two independently coloured pixels.
        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_iff.asm"
        ORG $386e
; Enter by JP. Save IFF before mapping, using a private stack for the work.
        MACRO ENTER
        push af
        HLIB_IFF_DI
        push af
        nextreg $53,26
        push bc
        HLIB_SPEED_IN_ABC speed
        pop bc
        ld (saved_sp),sp
        ld sp,$7ffe
        push bc
        push de
        push hl
        push ix
        push iy
        ; The gameplay IM2 vector uses I=C7. During the mapped work the
        ; private vector just latches its interrupt. Menus keep their own mode.
        ld hl,(saved_sp)
        ld a,(hl)
        and 4
        jr z,.masked
        inc hl
        ld a,(hl)
        cp $c7
        jr nz,.masked
        ld a,high private_vector
        ld i,a
        ei
.masked:
        ENDM
        MACRO WORK
        nextreg $52,32
        nextreg $54,28
        nextreg $55,29
        nextreg $56,30
        ENDM
        MACRO LEAVE
        di
        nextreg $50,255
        nextreg $52,10
        nextreg $56,0
        nextreg $55,5
        nextreg $54,4
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        ld sp,(saved_sp)
        ld a,(speed)
        nextreg $53,11
        nextreg 7,a
        pop af
        jp po,.disabled
        ld i,a
        ld a,(irq_pending)
        or a
        jr z,.enable
        xor a
        ld (irq_pending),a
        pop af
        jp $5b5b             ; its EI/RET resumes the dispatch continuation
.enable: pop af
        ei
        jr .done
.disabled:
        pop af
.done:
        ENDM

; Each CALL carries a two-byte action address. The shared dispatcher restores
; the game's stack, interrupt state and clock before continuing after it.
dispatch:
        ENTER
        ld hl,(saved_sp)
        ld de,4
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc de
        inc de
        ld (hl),d
        dec hl
        ld (hl),e
        dec de
        dec de
        ex de,hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,.return
        push hl
        push de
        ld hl,($7ff8)
        ld de,($7ffa)
        ld bc,($7ffc)
        ret
.return:
        LEAVE
        ret

e_plot: push af
        push bc
        HLIB_IFF_DI
        push af
        ld bc,$243b
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (game_speed),a
        pop af
        HLIB_IFF_EI
        push de
        push hl
        ld hl,8
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,($9649)
        cp $2c               ; outside, the game draws silhouettes in black
        jr nz,.mine
        ld hl,($ece0)
        ld a,h
        cp $62               ; the outdoor bird frames are in the bright red sky ink
        ld a,10
        jr z,.ink
        ld a,8
        jr .ink
.mine:
        ld a,15              ; the mine's ordinary figure ink is bright white
        ld hl,$8843
        or a
        sbc hl,de
        jr nz,.ink
        ld a,(ix+0)
        or a
        ld a,15
        jr nz,.ink
        ld a,(ix+9)          ; the ink sent to the enemy attribute painter
        ld b,a
        and 7
        jr z,.black
        bit 6,b
        jr z,.ink
        or 8
        jr .ink
.black: ld a,8
.ink:   ld (plot_ink),a
        ld hl,($ece2)
        ld (plot_table),hl
        ld hl,($ed14)
        ld (plot_col),hl
        ld hl,$ece3
        ld (last_src),hl
        xor a
        ld (submitted),a
        inc a
        ld (pending),a
        pop hl
        pop de
        pop bc
        pop af
        ld de,$ece4
        jp $ec18

e_end:  call dispatch
        dw end_plot
        ld a,($ecdf)
        jp $ec44
e_erase_start:
        call dispatch
        dw prepare_erase
        ld de,$ea60
        jp $8459
e_pickup_start:
        call dispatch
        dw prepare_pickup
        ld iy,$c537
        jp $9634
e_rows: ld (hl),a
publish_erase:
        ld (small_cursor),hl
        inc hl
        inc de
        ret
e_last_row:
        ld (hl),a
publish_last:
        ld (small_cursor),hl
        call finish_secondary
        ld hl,($8499)
        jp $8487
e_clear: call dispatch
        dw reset_overlay
        ld hl,$cf54
        jp $c62d
e_title: call dispatch
        dw reset_overlay
        ld hl,$4000
        ret
e_crusher: call dispatch
        dw draw_crusher
        ld iy,$c527
        jp $8e30
e_coal: ld (de),a
publish_coal:
        ld (small_cursor),de
        call finish_secondary
        inc d
        inc h
        jp $963e
e_strip: call dispatch
        dw strip_entry
        dec c
        ld b,3
        jp $90ab
e_floor: push af
        ld a,($90a4)
        cp $2f
        jr z,.erase
        pop af
        jp $90a3
.erase: ld a,(pending)
        or a
        jr nz,.work
        ; This AND clears one ULA bit. Peek at the same bit in the ownership
        ; cache before paying for a full tile flush. Restore MMU2 before POP.
        HLIB_IFF_DI
        push af
        nextreg $52,32
        ld a,(hl)
        and c
        nextreg $52,10
        jr z,.empty
        pop af
        HLIB_IFF_EI
.work:  pop af
        call dispatch
        dw floor_entry
        jp $90a3
.empty: pop af
        HLIB_IFF_EI
        pop af
        jp $90a3

; The original shifts all 48 bytes through carry. INC/DEC HL, LD and DJNZ
; preserve carry, so the original PUSH AF / POP AF pair is unnecessary.
        MACRO SHIFT_BUFFER address, rotate, advance
.loop:  push bc
        ld hl,address
        ld b,6
.group: DUP 8
        ld a,(hl)
        rotate
        ld (hl),a
        advance hl
        EDUP
        djnz .group
        pop bc
        djnz .loop
        ENDM
e_right:
        SHIFT_BUFFER $ece4,rra,inc
        jp $eca1
e_left:
        SHIFT_BUFFER $ed13,rla,dec
        jp $ecdb

; EC29..EC35. Keep both visible stores and the intervening room-copy read.
; BC advances over the source, DE over the room copy, HL over the ULA.
; The row runs at 28 MHz. The game can still take its interrupt here.
e_pixels:
        nextreg 7,3
row_fast:
        push bc
        ld b,d
        ld c,e
        ld a,l
        add a,$60
        ld e,a
        ld a,h
        adc a,$92
        ld d,a
        DUP 3
        ld a,(bc)
        ld (hl),a
        ld (last_src),bc
        ld a,(de)
        or (hl)
        ld (hl),a
        inc bc
        inc de
        inc hl
        EDUP
        ld d,b
        ld e,c
        pop bc
        ld b,0
        push af
        ld a,(game_speed)
        nextreg 7,a
row_normal:
        pop af
        jp $ec36

; Both interrupt handlers save AF,BC,DE first and restore IY,IX first.
; Run the game's interrupt at its own clock. The interrupted return PC
; identifies a row burst even when the handler itself plots another row.
        MACRO IRQ_ENTER continuation
        push af
        push bc
        push de
        push hl
        ld hl,8
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        call interrupt_queue
        call row_pc
        jr nc,.done
        ld a,(game_speed)
        nextreg 7,a
        ; An interrupt can arrive after the ULA store and immediately
        ; before LD (last_src),BC. Finish that publication for this ISR.
        ld a,(de)
        cp $ed
        jr nz,.done
        inc de
        ld a,(de)
        cp $43
        jr nz,.done
        ld (last_src),bc
.done:  pop hl
        pop de
        pop bc
        pop af
        push af
        push bc
        push de
        jp continuation
        ENDM
irq_mine:
        IRQ_ENTER $8fa2
irq_outside:
        IRQ_ENTER $cdf2

        MACRO IRQ_LEAVE continuation
        ; The interrupted PC lies after IY, IX, HL, DE, BC and AF.
        push af
        push de
        push hl
        ld hl,18
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        call row_pc
        jr nc,.done
        nextreg 7,3
.done:  pop hl
        pop de
        pop af
        pop iy
        pop ix
        jp continuation
        ENDM
irq_end_mine:
        IRQ_LEAVE $904c
irq_end_outside:
        IRQ_LEAVE $ce13
row_pc: ld hl,row_fast
        or a
        sbc hl,de
        jr z,.inside
        jr nc,.outside
        ld hl,row_normal
        or a
        sbc hl,de
        jr c,.outside
        jr z,.outside
.inside: scf
        ret
.outside: or a
        ret

; The upper ROM view is backed by private writable RAM. Every completed
; visible byte publishes its source address for an interrupting scenery writer.
deferred_irq:
        push af
        ld a,1               ; a mapped section is shorter than one interrupt period
        ld (irq_pending),a
        pop af
        ei
        ret
last_src: dw $ece3
irq_pending: db 0
game_speed: db 0
plot_table: dw 0
plot_col: dw 0
plot_ink: db 0
submitted: db 0
pending: db 0
        ASSERT $ <= $3bff
        ORG $3bff
private_vector: dw deferred_irq

; The source and geometry are fixed for six eraser bytes or eight coal rows.
; Each real ULA store then publishes just its destination. Submit exactly that
; prefix before an interrupt-side writer and the remainder at the last store.
finish_secondary:
        push af
        ld a,b
        dec a
        jr z,.flush
        pop af
        ret
.flush: pop af
        call dispatch
        dw finish_small
        ret

interrupt_queue:
        ld a,(small_busy)
        or a
        ret z
        ; A store can be interrupted one instruction before its publication.
        ld hl,publish_erase
        or a
        sbc hl,de
        jr z,.from_hl
        ld hl,publish_last
        or a
        sbc hl,de
        jr z,.from_hl
        ld hl,publish_coal
        or a
        sbc hl,de
        jr nz,.sync
        ld hl,4              ; interrupted DE, below saved HL and CALL
        jr .publish
.from_hl:
        ld hl,2
.publish:
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (small_cursor),hl
.sync:  call dispatch
        dw submit_small
        ret
small_busy: db 0
small_cursor: dw 0
rom_end:
        ASSERT rom_end+20 < $3d00

        ORG $6000
end_plot:
        WORK
        call sync_plot
        xor a
        ld (pending),a
        ret

; Consume only the bytes the interrupted plot has written. The game can erase
; an earlier byte during the interrupt. Resuming starts at the next source byte.
sync_plot:
        ld a,(pending)
        or a
        ret z
        ld a,(last_src)
        sub $e3
        ld b,a
        ld a,(submitted)
        cp b
        ret z
        ld c,a
        ld a,(plot_ink)
        call set_ink
        ld a,b
        ld (submitted),a
        ld a,c
        or a
        jr nz,.partial
        ld a,b
        cp 48
        jr nz,.partial
        ld hl,(plot_table)
        ld (row_pointer),hl
        ld hl,$ece4
        ld a,16
        ld c,3
        ld de,(plot_col)
        jp rectangle
.partial:
        ; B = exclusive end, C = the next of the 48 shifted bytes.
.byte:  push bc
        ld l,c
        ld h,0
        ld de,row_offsets
        add hl,de
        ld e,(hl)
        ld d,0
        ld hl,(plot_table)
        or a
        sbc hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,(plot_col)
        add hl,de
        ex de,hl
        ld hl,byte_columns
        ld b,0
        add hl,bc
        ld a,(hl)
        add a,e
        ld e,a
        jr nc,.col
        inc d
.col:   ld hl,$ece4
        add hl,bc
        ld a,(hl)
        call paint_byte
        pop bc
        inc c
        ld a,c
        cp b
        jr c,.byte
        jp flush
row_offsets:
        DUP 48,i
        db (i/3)*2
        EDUP
byte_columns:
        DUP 48,i
        db i%3
        EDUP

prepare_erase:
        ; HL at 8456 is twice the row index. Both destination rows come from
        ; the original's backwards row table and contain three adjacent bytes.
        ld de,$ea60
        add hl,de
        ld a,($5c7b)
        rrca
        rrca
        rrca
        and 31
        ld c,a
        ld ix,small_list
        ld b,2
.row:   ld e,(hl)
        inc hl
        ld d,(hl)
        dec hl
        dec hl
        dec hl
        ld a,c
        add a,e
        ld e,a
        jr nc,.column
        inc d
.column:
        DUP 3
        ld (ix+0),e
        ld (ix+1),d
        ld (ix+2),0
        inc ix
        inc ix
        inc ix
        inc de
        EDUP
        djnz .row
        jr start_small
prepare_pickup:
        ld a,d
        rrca
        rrca
        rrca
        and 3
        or $58
        ld h,a
        ld l,e
        ld a,(hl)
        rrca
        rrca
        rrca
        and 15
        jr nz,.colour
        ld a,8
.colour: ld (small_ink),a
        ld hl,$c537
        ld a,(hl)
        inc a
        jr nz,.live
        ld hl,zeros
.live:  ld ix,small_list
        ld b,8
.row:   ld (ix+0),e
        ld (ix+1),d
        ld a,(hl)
        ld (ix+2),a
        inc ix
        inc ix
        inc ix
        inc hl
        inc d
        djnz .row
start_small:
        ld hl,small_list
        ld (small_next),hl
        ld hl,0
        ld (small_cursor),hl
        ld (small_seen),hl
        ld a,1
        ld (small_busy),a
        ret

finish_small:
        call submit_small
        xor a
        ld (small_busy),a
        ret
submit_small:
        ld hl,(small_cursor)
        ld de,(small_seen)
        or a
        sbc hl,de
        ret z
        WORK
        ld a,(small_ink)
        call set_ink
        ld ix,(small_next)
.loop:  ld e,(ix+0)
        ld d,(ix+1)
        ld a,(ix+2)
        inc ix
        inc ix
        inc ix
        push de
        call paint_byte
        pop de
        ld hl,(small_cursor)
        or a
        sbc hl,de
        jr nz,.loop
        ld (small_seen),de
        ld (small_next),ix
        jp flush

reset_overlay:
        xor a
        ld (pending),a
        WORK
        jp clear_tiles

strip_entry:
        ld a,($7ffc)
        push hl
        push af
        WORK
        call sync_plot
        pop af
        pop hl
        ld (width_),a
        jp erase_strip
floor_entry:
        push de
        push hl
        WORK
        call sync_plot
        pop hl
        pop de
        ld a,($7ffc)
        cpl
        ld (floor_mask),a    ; survivor bits
        ex de,hl
        ld a,1
        ld (mask_only),a
        ld a,(floor_mask)
        call paint_byte
        xor a
        ld (mask_only),a
        jp flush

; The conveyor copies its rotated source byte across each of three pixel rows.
; At this writer the whole destination belongs to the scenery again.
draw_crusher:
        ld a,($c527)
        ld (erasecol),a
        ld a,($c528)
        ld e,a
        ld d,0
        ld hl,$ea60
        add hl,de
        add hl,de
        ld (row_pointer),hl
        ld a,($c52b)
        and 1
        ld hl,$8e80
        jr z,.source
        ld hl,$8e7a
.source:
        ; The source is in a slot the tile cache needs. Copy all nine rows first.
        ld de,crusher
        ld bc,27
        ldir
        WORK
        ld hl,(row_pointer)
        push hl
        call sync_plot
        pop hl
        ld (row_pointer),hl
        ld a,15
        call set_ink
        ld hl,crusher
        ld a,9
        ld c,3
        ld de,(erasecol)
        jp rectangle

erase_strip:
        ld b,3
.row:   push bc
        push hl
        ex de,hl
        ld a,(width_)
        ld b,a
.byte:  push bc
        push de
        xor a
        call paint_byte
        pop de
        inc de
        pop bc
        djnz .byte
        pop hl
        inc h
        pop bc
        djnz .row
        jp flush

; Two read-only MMU pages hold four packed-pair lookups for each ink.
; Select the ink once per shape or partial submission.
set_ink:
        ld (ink),a
        push af
        rrca
        rrca
        rrca
        and 1
        or 34
        nextreg $50,a
        pop af
        and 7
        add a,a
        add a,a
        ld (ink_page),a
        ret

; A rows, C width, DE byte column, HL source pixels. Row table runs backwards in RAM.
rectangle:
        ld (nrows),a
        ld a,c
        ld (width_),a
        ld (column),de
        ld (src),hl
.row:   ld hl,(row_pointer)
        ld e,(hl)
        inc hl
        ld d,(hl)
        dec hl
        dec hl
        dec hl
        ld (row_pointer),hl
        ld hl,(column)
        add hl,de
        ex de,hl
        ld hl,(src)
        ld a,(width_)
        ld b,a
.byte:  push bc
        push de
        ld a,(hl)
        inc hl
        push hl
        call paint_byte
        pop hl
        pop de
        inc de
        pop bc
        djnz .byte
        ld (src),hl
        ld hl,nrows
        dec (hl)
        jr nz,.row
        jp flush

; DE = exact ULA address, A = 8 figure bits. Decode from the actual address,
; including a third byte which crosses a Spectrum character row at the right edge.
paint_byte:
        ld c,a
        ld a,d
        sub $40
        cp $18
        ret nc
        ld a,(de)            ; previous figure bits at this ULA address
        ld b,a
        or c
        ret z
        ld a,(mask_only)
        or a
        jr z,.bits
        ld a,b
        and c
        cp b
        ret z
        ld c,a
.bits:  ld a,c
        ld (de),a
        push bc              ; original and new occupancy
        ld h,high low_col
        ld l,e
        ld a,(hl)
        inc h
        ld l,d
        or (hl)
        ld b,a
        inc h
        ld a,(hl)
        inc h
        ld l,e
        or (hl)
        ld h,a
        ld l,b
        ld a,l
        rlca
        ld a,h
        rla
        ld b,a               ; tile index, with the pattern address in HL
        ex de,hl             ; DE = four packed pixels pairs
        ld l,b
        ld h,high counts
        pop bc               ; B old bits, C new bits
        ld a,b
        or a
        jr nz,.was_set
        inc (hl)
        jr .changed
.was_set:
        ld a,c
        or a
        jr nz,.occupied
        dec (hl)
        jr nz,.changed
        inc h                ; tile now has no colour
        ld (hl),0
        dec h
        jr .changed
.occupied:
        cp b
        jr nz,.changed
        inc h
        ld a,(ink)
        cp (hl)
        ret z                ; identical bits in a tile known to use one ink
        dec h
.changed:
        ld b,l               ; tile index
        ld a,(mask_only)
        or a
        jr z,.replacement
        ex de,hl
        ld a,(floor_mask)
        ld b,8
.maskbit:
        rlca
        jr c,.keep
        ld d,a
        bit 0,b
        ld a,(hl)
        jr nz,.clear_low
        and 15
        jr .put
.clear_low:
        and $f0
.put:   ld (hl),a
        ld a,d
.keep:  bit 0,b
        jr z,.nextbit
        inc hl
.nextbit:
        djnz .maskbit
        ; Recover the tile index from the starting pattern address, including offset wrap.
        dec hl
        add hl,hl
        ld b,h
        jr .mark
.replacement:
        inc h                ; uniform ink, or FF for a mixed tile
        ld a,c
        or a
        jr z,.clear_group
        ld a,(ink)
        cp (hl)
        jr z,.colour_ready
        ld a,(hl)
        or a
        ld a,(ink)
        jr z,.record_colour
        ld a,255
.record_colour:
        ld (hl),a
.colour_ready:
        ex de,hl
        jr .nonblank
.clear_group:
        ex de,hl
        xor a
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        inc l
        ld (hl),a
        jr .mark
.nonblank:
        ex de,hl
        ld a,(ink_page)
        ld h,a
        ld l,c
        DUP 3
        ld a,(hl)
        ld (de),a
        inc h
        inc e
        EDUP
        ld a,(hl)
        ld (de),a
.mark:  ld l,b
        ld h,high marked
        ld a,(hl)
        or a
        ret nz
        inc (hl)
        ld a,(ndirty)
        ld l,a
        ld h,high dirty
        ld (hl),b
        inc a
        ld (ndirty),a
        ret

flush:  ld hl,ndirty
        ld a,(hl)
        or a
        ret z
        dec (hl)
        dec a
        ld l,a
        ld h,high dirty
        ld e,(hl)
        ld l,e
        ld h,high marked
        ld (hl),0
        ld h,high slots
        ld d,(hl)            ; D = slot or FF, E = tile
        ld a,e
        rrca
        ld l,0
        jr nc,.even
        ld l,128
.even:  and $7f
        add a,$80
        ld h,a
        push hl
        ld l,e
        ld h,high counts
        ld a,(hl)
        or a
        jr nz,.occupied
        pop hl
        ld a,d
        cp 255
        jr z,flush
        nextreg $34,a
        nextreg $38,0
        ld l,e
        ld h,high slots
        ld (hl),255
        ld hl,nfree
        ld a,(hl)
        inc (hl)
        ld l,a
        ld h,high freelist
        ld (hl),d
        jr flush
.occupied:
        ld a,d
        cp 255
        jr nz,.upload
        ld hl,nfree
        ld a,(hl)
        or a
        jr nz,.allocate
        pop hl
        ld hl,overflow
        inc (hl)
        jr flush
.allocate:
        dec (hl)
        dec a
        ld l,a
        ld h,high freelist
        ld d,(hl)
        ld l,e
        ld h,high slots
        ld (hl),d
.upload:
        pop hl
        ld a,d
        srl a
        jr nc,.first
        or $80
.first: ld bc,$303b
        out (c),a
        ld c,$5b
upload_bytes:
        DUP 128
        outi
        EDUP
upload_done:
        ld a,d
        nextreg $34,a
        ld a,e
        and $0f
        swapnib
        add a,32
        nextreg $35,a
        ld a,0
        adc a,0
        nextreg $37,a
        ld a,e
        and $f0
        add a,32
        nextreg $36,a
        ld a,d
        srl a
        or $c0
        nextreg $38,a
        ld a,d
        and 1
        rrca
        rrca
        or $80
        nextreg $39,a
        jp flush

clear_tiles:
        xor a
        ld (ndirty),a
        ld hl,freelist
        ld b,128
.free:  ld (hl),a
        inc l
        inc a
        djnz .free
        ld (nfree),a
        ; Free tiles already contain zeros. Clear both cached representations
        ; of each occupied tile and hide its slot before discarding the index.
        ld hl,slots
        ld b,192
.tile:  ld a,(hl)
        cp 255
        jr z,.next
        nextreg $34,a
        nextreg $38,0
        ld (hl),255
        push hl
        push bc
        ld h,high counts
        ld (hl),0
        inc h
        ld (hl),0
        ld h,high raw_low
        ld e,(hl)
        inc h
        ld d,(hl)
        push hl
        ex de,hl
        ld b,2
.half:  push hl
        DUP 8
        ld (hl),0
        inc l
        ld (hl),0
        dec l
        inc h
        EDUP
        pop hl
        ld a,l
        add a,32
        ld l,a
        djnz .half
        pop hl
        ld a,l
        rrca
        ld l,0
        jr nc,.even
        ld l,128
.even:  and 127
        or $80
        ld h,a
        ld d,h
        ld e,l
        inc de
        ld (hl),0
        ld bc,127
        ldir
        pop bc
        pop hl
.next:  inc l
        dec b
        jp nz,.tile
        ret

        ALIGN 256
raw_low:
        DUP 256,i
        db ((i&15)*2)|((i&48)<<2)
        EDUP
raw_high:
        DUP 256,i
        db $40|((i&$c0)>>3)
        EDUP
        ALIGN 256
low_col:
        DUP 256,i
        db ((i&2)<<6)|((i&32)<<1)|((i&1)<<2)
        EDUP
low_row:
        DUP 256,i
        db (i&7)<<3
        EDUP
high_row:
        DUP 256,i
        db $80|((i&$18)<<2)
        EDUP
high_col:
        DUP 256,i
        db ((i&$c0)>>3)|((i&$1c)>>2)
        EDUP
        ALIGN 256
counts: ds 256
uniform: ds 256
slots:  ds 192,255
        ALIGN 256
marked: ds 192
        ALIGN 256
dirty:  ds 192
        ALIGN 256
freelist:
        DUP 128,i
        db 127-i
        EDUP
nfree:  db 128
ndirty: db 0
overflow: db 0
saved_sp: dw 0
speed:  db 0
ink:    db 15
ink_page: db 0
column: dw 0
erasecol: dw 0
nrows:  db 0
width_: db 0
src:    dw 0
zeros:  ds 48,0
crusher: ds 27
mask_only: db 0
floor_mask: db 0
small_list: ds 24
small_next: dw 0
small_seen: dw 0
small_ink: db 0
row_pointer: dw 0
page_end:
        ASSERT page_end < $7e00

        ORG $d000
setup:  nextreg $43,$20
        nextreg $40,0
        ld hl,palette
        ld b,16
.pal:   ld a,(hl)
        nextreg $41,a
        inc hl
        djnz .pal
        nextreg $4b,0
        xor a
.hide:  nextreg $34,a
        nextreg $38,0
        inc a
        cp 128
        jr nz,.hide
        nextreg $15,1
        ret
palette: db 0,2,$a0,$a2,$14,$16,$b4,$b6,0,3,$e0,$e3,$1c,$1f,$fc,$ff
setup_end:
        SAVEBIN "wmm_rom.bin",$386e,rom_end-$386e
        SAVEBIN "wmm_page.bin",$6000,page_end-$6000
        SAVEBIN "wmm_setup.bin",$d000,setup_end-$d000
