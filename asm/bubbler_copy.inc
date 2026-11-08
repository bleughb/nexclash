; Linear colour-page transfer. Offsets 0000..7FFF from their base page.
; Direction 0 increments, 1 decrements. Caller chooses overlap-safe direction.
M_SRC EQU 0x3E60
M_DST EQU 0x3E62
M_LEN EQU 0x3E64
M_SBASE EQU 0x3E66
M_DBASE EQU 0x3E67
M_BACK EQU 0x3E68
M_CHUNK EQU 0x3E69
M_FILL EQU 0x3E6B
M_VALUE EQU 0x3E6C
colour_move:
        xor a
        ld (M_FILL),a
        jp colour_transfer
colour_fill:
        ld a,1
        ld (M_FILL),a
colour_transfer:
.loop:
        ld hl,(M_LEN)
        ld a,h
        or l
        ret z
        ld (M_CHUNK),hl
        ld hl,(M_SRC)
        ld a,(M_SBASE)
        call .map
        nextreg 0x56,a
        push hl
        ld a,h
        or 0xC0
        ld h,a
        ld (.source+1),hl
        pop hl
        ld a,(M_FILL)
        and a
        jr nz,.destination
        call .limit
.destination:
        ld hl,(M_DST)
        ld a,(M_DBASE)
        call .map
        nextreg 0x57,a
        push hl
        ld a,h
        or 0xE0
        ld h,a
        ld (.dest+1),hl
        pop hl
        call .limit
.source:
        ld hl,0
.dest:
        ld de,0
        ld bc,(M_CHUNK)
        call hlib_dma_backend
        and a
        jr z,.cpu
        call colour_dma_copy
        jr .advance
.cpu:
        ld a,(M_FILL)
        and a
        jr nz,.fill
        ld a,(M_BACK)
        and a
        jr nz,.back
        ldir
        jr .advance
.back:
        lddr
        jr .advance
.fill:
        ld a,(M_VALUE)
        ld (de),a
        dec bc
        ld a,b
        or c
        jr z,.advance
        ld h,d
        ld l,e
        ld a,(M_BACK)
        and a
        jr nz,.fillback
        inc de
        ldir
        jr .advance
.fillback:
        dec de
        lddr
.advance:
        ld bc,(M_CHUNK)
        ld hl,(M_LEN)
        or a
        sbc hl,bc
        ld (M_LEN),hl
        ld hl,(M_SRC)
        ld de,(M_DST)
        ld a,(M_BACK)
        and a
        jr nz,.subtract
        add hl,bc
        ex de,hl
        add hl,bc
        jr .store
.subtract:
        or a
        sbc hl,bc
        ex de,hl
        or a
        sbc hl,bc
.store:
        ld (M_DST),hl
        ld (M_SRC),de
        jp .loop
; A=base, HL=logical -> A=page, HL=offset in page.
.map:
        ld c,a
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,c
        ld c,a
        ld a,h
        and 0x1F
        ld h,a
        ld a,c
        ret
; Limit M_CHUNK to the number of bytes before this page boundary.
.limit:
        ld a,(M_BACK)
        and a
        jr z,.forwardlimit
        inc hl
        jr .available
.forwardlimit:
        ex de,hl
        ld hl,0x2000
        or a
        sbc hl,de
.available:
        ld de,(M_CHUNK)
        or a
        sbc hl,de
        ret nc
        add hl,de
        ld (M_CHUNK),hl
        ret

; Continuous ordinary DMA. Backward overlap uses an independent 8K scratch
; page, twice, so no decrement extension or speculative hardware mode is used.
colour_dma_copy:
        ld (colour_dma_len),bc
        ld a,(M_FILL)
        and a
        jr nz,.fill
        ld a,(M_BACK)
        and a
        jr nz,.back
        ld a,0x14
        ld (colour_dma_mode),a
        jp colour_dma_job
.fill:
        ld a,(M_BACK)
        and a
        jr z,.fillforward
        ex de,hl
        or a
        sbc hl,bc
        inc hl
        ex de,hl
.fillforward:
        ld hl,M_VALUE
        ld a,0x24
        ld (colour_dma_mode),a
        jp colour_dma_job
.back:
        ld a,0x14
        ld (colour_dma_mode),a
        or a
        sbc hl,bc
        inc hl
        ex de,hl
        or a
        sbc hl,bc
        inc hl
        push hl
        ex de,hl
        ld de,0x4000
        nextreg 0x52,33
        call colour_dma_job
        pop de
        ld hl,0x4000
        ; First job's packet retains the exact length.
colour_dma_job:
        ld (colour_dma_source),hl
        ld (colour_dma_dest),de
        ld hl,colour_dma_packet
        ld bc,(colour_dma_packet_end-colour_dma_packet)*256+0x6B
        otir
        ret
colour_dma_packet:
        db 0x83,0xC3,0x7D
colour_dma_source: dw 0
colour_dma_len: dw 0
colour_dma_mode: db 0x14
        db 0x10,0xAD
colour_dma_dest: dw 0
        db 0x82,0xCF,0x87
colour_dma_packet_end:

; Short forward rows used only between disjoint canvas/save/display pages.
; Crossing either 8K boundary falls back to the tested general transfer.
colour_row_move:
        ld bc,(M_LEN)
        ld hl,(M_SRC)
        ld a,(M_SBASE)
        call colour_transfer.map
        nextreg 0x56,a
        ld bc,(M_LEN)
        push hl
        add hl,bc
        bit 5,h
        pop hl
        jp nz,colour_move
        ld a,h
        or 0xC0
        ld h,a
        push hl
        ld hl,(M_DST)
        ld a,(M_DBASE)
        call colour_transfer.map
        nextreg 0x57,a
        ld bc,(M_LEN)
        push hl
        add hl,bc
        bit 5,h
        pop hl
        jr z,.inside
        pop hl
        jp colour_move
.inside:
        ld a,h
        or 0xE0
        ld h,a
        ex de,hl
        pop hl
        call hlib_dma_backend
        and a
        jr z,.cpu
        ld a,0x14
        ld (colour_dma_mode),a
        ld (colour_dma_len),bc
        call colour_dma_job
        jr .advance
.cpu:
        ldir
.advance:
        ld bc,(M_LEN)
        ld hl,(M_SRC)
        add hl,bc
        ld (M_SRC),hl
        ld hl,(M_DST)
        add hl,bc
        ld (M_DST),hl
        ld hl,0
        ld (M_LEN),hl
        ret
