; Exact ordered colour canvas, double buffered. Original game RAM is read only.
; 255 transparent source; 254 toggles the underlying original bitmap bit.
V_ENH EQU 0x3E34
V_TARGET EQU 0x3E35
C_BACK EQU 0x3E40
C_M0 EQU 0x3E41
C_M5 EQU 0x3E42
C_M6 EQU 0x3E43
C_W EQU 0x3E44
C_H EQU 0x3E45
C_X EQU 0x3E46
C_Y EQU 0x3E47
C_XOR EQU 0x3E48
C_COUNT EQU 0x3E49
C_SRC EQU 0x3E4A
C_PX EQU 0x3E4C
C_PY EQU 0x3E4D
C_END EQU 0x3E4E
C_REMAIN EQU 0x3E4F

colour_frame:
        push ix
        ; Latch all replaced MMU slots. The original draw list lives in page0.
        ld bc,0x243B
        ld a,0x50
        out (c),a
        inc b
        in a,(c)
        ld (C_M0),a
        dec b
        ld a,0x55
        out (c),a
        inc b
        in a,(c)
        ld (C_M5),a
        dec b
        ld a,0x56
        out (c),a
        inc b
        in a,(c)
        ld (C_M6),a
        nextreg 0x55,0
        ld a,(C_BACK)
        or a
        jr nz,.back
        ld a,32
        ld (C_BACK),a
.back:
        ld d,44
        ld e,a
        ld b,4
.clear:
        push bc
        push de
        ld a,d
        nextreg 0x50,a
        ld a,e
        nextreg 0x56,a
        call colour_copy
        call hlib_pace_tick
        pop de
        inc d
        inc e
        pop bc
        djnz .clear
        ld ix,0xB355
        ld a,170
        ld (C_COUNT),a
.figure:
        ld a,(ix+0)
        or a
        jp z,.publish
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x3100
        add hl,de
        ld a,(hl)
        nextreg 0x50,a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        ld (C_W),a
        inc hl
        ld a,(hl)
        ld (C_H),a
        inc hl
        ld a,(hl)
        ld (C_XOR),a
        ld a,(ix+1)
        ld (C_X),a
        ld a,175
        sub (ix+2)
        ld (C_Y),a
        ex de,hl
        ld a,(C_H)
        or a
        jr z,.next
.row:
        ld (C_SRC),hl
        ld a,(C_Y)
        cp 16
        jr c,.slow
        cp 128
        jr nc,.slow
        ld a,(C_X)
        cp 16
        jr c,.slow
        cp 176
        jr nc,.slow
        ld e,a
        ld a,(C_W)
        add a,e
        cp 177
        jr nc,.slow
        ld a,(C_XOR)
        or a
        jr nz,.slow
        ld a,(C_Y)
        call colour_destination
        ld a,(C_W)
        ld c,a
        ld b,0
        ld a,255
        ldirx
        jr .row_end
.slow:
        call colour_clipped_row
.row_end:
        ld hl,(C_SRC)
        ld a,(C_W)
        ld e,a
        ld d,0
        add hl,de
        ld a,(C_Y)
        dec a
        ld (C_Y),a
        ld a,(C_H)
        dec a
        ld (C_H),a
        jr nz,.row
.next:
        ld bc,3
        add ix,bc
        call hlib_pace_tick
        ld a,(C_COUNT)
        dec a
        ld (C_COUNT),a
        jp nz,.figure
        ; Original queue capacity is bounded; retain a safe original display
        ; if a corrupt list is not terminated, never walk arbitrary source RAM.
        nextreg 0x69,0
        jr .restore
.publish:
        ; Atomic bank switch outside every viewport row. One full line reserved.
        call hlib_line
        ld a,h
        or a
        jr nz,.switch
        ld a,l
        cp 15
        jr c,.switch
        cp 128
        jr c,.publish
.switch:
        ld a,(C_BACK)
        srl a
        nextreg 0x12,a
        nextreg 0x69,0x80
        ld a,(C_BACK)
        xor 6                   ; 32 <-> 38
        ld (C_BACK),a
.restore:
        ld a,(C_M0)
        nextreg 0x50,a
        ld a,(C_M5)
        nextreg 0x55,a
        ld a,(C_M6)
        nextreg 0x56,a
        pop ix
        ret

; A=y, E=x -> DE=destination, map its page. HL is the source and is kept.
colour_destination:
        ld d,a
        and 31
        or 0xC0
        ld c,a
        ld a,d
        rrca
        rrca
        rrca
        rrca
        rrca
        and 3
        ld d,a
        ld a,(C_BACK)
        add a,d
        nextreg 0x56,a
        ld d,c
        ret

colour_clipped_row:
        ld a,(C_Y)
        ld (C_PY),a
        ld a,(C_X)
        cp 192
        jr c,.x_ready
        sub 192
        ld e,a
        ld a,(C_PY)
        inc a
        ld (C_PY),a
        ld a,e
.x_ready:
        ld e,a
        ld (C_PX),a
        ld a,192
        sub e
        ld c,a
        ld a,(C_W)
        cp c
        jr nc,.split
        ld c,a
.split:
        sub c
        ld (C_REMAIN),a
        ld a,c
        ld (C_END),a
        ld a,(C_PY)
        call colour_fragment
        ld a,(C_REMAIN)
        or a
        ret z
        ld c,a
        ld a,(C_END)
        ld e,a
        ld d,0
        ld hl,(C_SRC)
        add hl,de
        ld e,0
        ld a,(C_PY)
        inc a
        jp colour_fragment

; Source HL, x=E, y=A, count=C. Clip once, then transfer the visible span.
colour_fragment:
        cp 16
        ret c
        cp 128
        ret nc
        ld (C_PY),a
        ld a,e
        cp 176
        ret nc
        cp 16
        jr nc,.left_ok
        ld a,16
        sub e
        cp c
        ret nc
        ld e,a
        ld d,0
        add hl,de
        ld a,c
        sub e
        ld c,a
        ld e,16
.left_ok:
        ld a,e
        add a,c
        cp 177
        jr c,.right_ok
        ld a,176
        sub e
        ld c,a
.right_ok:
        ld b,0
        push bc
        ld a,(C_PY)
        call colour_destination
        pop bc
        ld a,(C_XOR)
        or a
        jr nz,.xor_loop
        ld a,255
        ldirx
        ret
.xor_loop:
        ld a,(hl)
        inc hl
        cp 255
        jr z,.next
        cp 254
        jr nz,.write
        ld a,(de)
        and 128
        ld a,1
        jr nz,.write
        ld a,130
.write: ld (de),a
.next:  inc de
        dec c
        jr nz,.xor_loop
        ret

colour_copy:
        ; Exclusive ordinary DMA: no game DMA, IFF0, stable mappings, 8KiB job.
        ; Unknown/old cores and hardware IM2 take the bounded CPU fallback.
        ld a,1
        call hlib_dma_init
        call hlib_dma_backend
        or a
        jr z,.cpu
        ld hl,.packet
        ld bc,(.packet_end-.packet)*256+0x6B
        otir
        ret
.cpu:   ld hl,0
        ld de,0xC000
        ld bc,8192
        ldir
        ret
.packet:
        db 0x83,0xC3,0x7D
        dw 0,8192
        db 0x14,0x10,0xAD
        dw 0xC000
        db 0x82,0xCF,0x87
.packet_end:
