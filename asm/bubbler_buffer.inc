; Colour counterparts of original save/restore/scroll operations.
B_SRC EQU 0x3E70
B_DST EQU 0x3E72
B_ROWS EQU 0x3E74
B_WIDTH EQU 0x3E75
B_PTR EQU 0x3E76
B_COUNT EQU 0x3E78
B_SHIFT EQU 0x3E79
B_SIDE EQU 0x3E7A
; C_SRC=original canvas byte; C_DST=original save pixel byte;
; C_WIDTH=original byte width, C_ROWS=actual copied row count.
colour_save:
        ld hl,(C_SRC)
        call canvas_offset
        ld (B_SRC),hl
        ld hl,(C_DST)
        ld de,-0xF500
        add hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ld (B_DST),hl
        ld a,28
        ld (M_SBASE),a
        ld a,32
        ld (M_DBASE),a
        xor a
        ld (M_BACK),a
        ld a,(C_ROWS)
        ld (B_ROWS),a
        ld a,(C_WIDTH)
        add a,a
        add a,a
        add a,a
        ld (B_WIDTH),a
.loop:
        ld a,(B_ROWS)
        and a
        ret z
        ld hl,(B_SRC)
        ld (M_SRC),hl
        ld hl,(B_DST)
        ld (M_DST),hl
        ld a,(B_WIDTH)
        ld l,a
        ld h,0
        ld (M_LEN),hl
        call colour_row_move
        ld hl,(M_DST)
        ld (B_DST),hl
        ld hl,(B_SRC)
        ld de,-192
        add hl,de
        ld (B_SRC),hl
        ld hl,B_ROWS
        dec (hl)
        jr .loop
colour_restore:
        nextreg 0x57,1
        ld a,(0xF500)
        ld (B_COUNT),a
        ld hl,0xF501
        ld (B_PTR),hl
.header:
        ld a,(B_COUNT)
        and a
        ret z
        nextreg 0x57,1
        ld hl,(B_PTR)
        ld a,(hl)
        sub 24
        add a,a
        add a,a
        add a,a
        ld (B_WIDTH),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        inc hl
        ld a,(hl)
        dec a
        ld (B_ROWS),a
        inc hl
        push de
        ld de,-0xF500
        add hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ld (B_SRC),hl
        pop hl
        call canvas_offset
        ld (B_DST),hl
        ld a,32
        ld (M_SBASE),a
        ld a,28
        ld (M_DBASE),a
        xor a
        ld (M_BACK),a
.row:
        ld a,(B_ROWS)
        and a
        jr z,.next
        ld hl,(B_SRC)
        ld (M_SRC),hl
        ld hl,(B_DST)
        ld (M_DST),hl
        ld a,(B_WIDTH)
        ld l,a
        ld h,0
        ld (M_LEN),hl
        call colour_row_move
        ld hl,(M_SRC)
        ld (B_SRC),hl
        ld hl,(B_DST)
        ld de,-192
        add hl,de
        ld (B_DST),hl
        ld hl,B_ROWS
        dec (hl)
        jr .row
.next:
        ld hl,(B_SRC)
        DUP 3
        srl h
        rr l
        EDUP
        ld de,0xF500
        add hl,de
        ld (B_PTR),hl
        ld hl,B_COUNT
        dec (hl)
        jp .header
canvas_offset:
        ld de,-0xE5BB
        add hl,de
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,8
        add hl,de
        ret
; B_SHIFT=2/4 pixels, B_SIDE=0 left/1 right; every row zero-filled.
colour_shift:
        ld a,28
        ld (M_SBASE),a
        ld (M_DBASE),a
        ld a,(B_SHIFT)
        ld e,a
        ld d,0
        ld hl,24576
        or a
        sbc hl,de
        ld (M_LEN),hl
        ld a,(B_SIDE)
        ld (M_BACK),a
        and a
        jr nz,.right
        ld hl,8
        ld (M_DST),hl
        add hl,de
        ld (M_SRC),hl
        ld hl,200
        or a
        sbc hl,de
        ld (B_DST),hl
        jr .move
.right:
        ld hl,24583
        ld (M_DST),hl
        or a
        sbc hl,de
        ld (M_SRC),hl
        ld hl,8
        ld (B_DST),hl
.move:
        call colour_move
        ld a,128
        ld (B_ROWS),a
.row:
        ld hl,(B_DST)
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,28
        nextreg 0x56,a
        ld a,h
        and 0x1F
        or 0xC0
        ld h,a
        ld a,(B_SHIFT)
        ld b,a
        xor a
.clear:
        ld (hl),a
        inc hl
        djnz .clear
        ld hl,(B_DST)
        ld de,192
        add hl,de
        ld (B_DST),hl
        ld hl,B_ROWS
        dec (hl)
        jr nz,.row
        ret
colour_mono_byte:
        ld hl,(C_DST)
        call canvas_offset
        bit 7,h
        ret nz
        ld a,h
        cp 0x60
        jr c,.inside
        ret nz
        ld a,l
        cp 16
        ret nc
.inside:
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,28
        ld (C_MAP),a
        nextreg 0x56,a
        ld a,h
        and 0x1F
        or 0xC0
        ld h,a
        ld a,(C_CUT)
        ld c,a
        ld b,8
.pixel:
        rl c
        sbc a,a
        ld (hl),a
        inc hl
        djnz .pixel
        ret
; C_DST original first byte, C_ROWS rows, C_CUT original bitmap byte.
colour_column:
        ld a,(C_ROWS)
        ld (B_ROWS),a
.row:
        call colour_mono_byte
        ld hl,(C_DST)
        inc hl
        ld (C_DST),hl
        call colour_mono_byte
        ld hl,(C_DST)
        ld de,23
        add hl,de
        ld (C_DST),hl
        ld hl,B_ROWS
        dec (hl)
        jr nz,.row
        ret
P_FRONT EQU 0x3E7B
P_NEXT EQU 0x3E7C
P_DMA_READY EQU 0x3E7D
P_ROW_STRIDE EQU 0x3E7E
; Prepare an entire inactive Layer2 image, retaining the preceding published
; rows for original partial-copy effects. Caller flips only after ULA copy.
colour_prepare:
        ld a,(P_FRONT)
        ld (M_SBASE),a
        xor 6
        ld (P_NEXT),a
        ld (M_DBASE),a
        xor a
        ld (M_BACK),a
        ld a,(C_ROWS)
        ld c,a
        ld a,112
        sub c
        jr c,.paint
        ld (B_ROWS),a
        ld a,c
        add a,8
        ld h,a
        ld l,48
        ld (B_SRC),hl
        ld (B_DST),hl
        call hlib_dma_backend
        and a
        jr z,.preserve
        ld hl,256
        ld (P_ROW_STRIDE),hl
        call colour_prepare_dma_rows
        jr .paint
.preserve:
        ld a,(B_ROWS)
        and a
        jr z,.paint
        ld hl,(B_SRC)
        ld (M_SRC),hl
        ld hl,(B_DST)
        ld (M_DST),hl
        ld hl,176
        ld (M_LEN),hl
        call colour_row_move
        ld hl,(B_SRC)
        inc h
        ld (B_SRC),hl
        ld (B_DST),hl
        ld hl,B_ROWS
        dec (hl)
        jr .preserve
.paint:
        ld hl,(C_SRC)
        call canvas_offset
        ld (B_SRC),hl
        ld hl,8*256+48
        ld (B_DST),hl
        ld a,(C_ROWS)
        ld (B_ROWS),a
        ld a,28
        ld (M_SBASE),a
        call hlib_dma_backend
        and a
        jr z,.row
        ld hl,192
        ld (P_ROW_STRIDE),hl
        jp colour_prepare_dma_rows
.row:
        ld a,(B_ROWS)
        and a
        ret z
        ld hl,(B_SRC)
        ld (M_SRC),hl
        ld hl,(B_DST)
        ld (M_DST),hl
        ld hl,176
        ld (M_LEN),hl
        call colour_row_move
        ld hl,(B_SRC)
        ld de,192
        add hl,de
        ld (B_SRC),hl
        ld hl,(B_DST)
        inc h
        ld (B_DST),hl
        ld hl,B_ROWS
        dec (hl)
        jr .row

colour_shiftbyte:
        ld a,(B_SIDE)
        and a
        ld hl,0xF1BB
        jr z,.guard
        ld hl,0xE5BA
.guard:
        ld (C_DST),hl
        call colour_mono_byte
        ld a,28
        ld (M_SBASE),a
        ld (M_DBASE),a
        ld a,(B_SIDE)
        ld (M_BACK),a
        and a
        jr nz,.right
        ld hl,16
        ld de,8
        jr .copy
.right:
        ld hl,24575
        ld de,24583
.copy:
        ld (M_SRC),hl
        ld (M_DST),de
        ld hl,24576
        ld (M_LEN),hl
        jp colour_move

; Fixed 176-byte disjoint rows. Ordinary DMA address rearm retains the
; fully programmed mode/length only within this synchronous call. Boundary
; splits use the general copier and force a complete reprogram next row.
colour_prepare_dma_rows:
        xor a
        ld (P_DMA_READY),a
.row:
        ld a,(B_ROWS)
        and a
        ret z
        ld hl,(B_SRC)
        ld a,(M_SBASE)
        call colour_transfer.map
        nextreg 0x56,a
        ld a,h
        cp 0x1F
        jr nz,.inside
        ld a,l
        cp 0x51
        jr nc,.split
.inside:
        ld a,h
        or 0xC0
        ld h,a
        push hl
        ld hl,(B_DST)
        ld a,(M_DBASE)
        call colour_transfer.map
        nextreg 0x57,a
        ld a,h
        or 0xE0
        ld h,a
        ex de,hl
        pop hl
        ld a,(P_DMA_READY)
        and a
        jr nz,.retained
        ld a,1
        ld (P_DMA_READY),a
        ld a,0x14
        ld (colour_dma_mode),a
        ld bc,176
        ld (colour_dma_len),bc
        call colour_dma_job
        jr .advance
.retained:
        ld (colour_prepare_row_source),hl
        ld (colour_prepare_row_dest),de
        ld hl,colour_prepare_row_packet
        ld bc,(colour_prepare_row_end-colour_prepare_row_packet)*256+0x6B
        otir
        jr .advance
.split:
        ld hl,(B_SRC)
        ld (M_SRC),hl
        ld hl,(B_DST)
        ld (M_DST),hl
        ld hl,176
        ld (M_LEN),hl
        call colour_row_move
        xor a
        ld (P_DMA_READY),a
.advance:
        ld hl,(B_SRC)
        ld de,(P_ROW_STRIDE)
        add hl,de
        ld (B_SRC),hl
        ld hl,(B_DST)
        inc h
        ld (B_DST),hl
        ld hl,B_ROWS
        dec (hl)
        jp .row
colour_prepare_row_packet:
        db 0x1D
colour_prepare_row_source: dw 0
        db 0xAD
colour_prepare_row_dest: dw 0
        db 0xCF,0x87
colour_prepare_row_end:
