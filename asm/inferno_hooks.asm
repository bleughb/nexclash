; Inferno loader foundation. NOT the sprite renderer.
; Entry replaces 0562 only: 7311..7317 already exchanged AF and executed DI.
; Slot 0 is borrowed while DI; no game RAM slot changes. Bytes are read from pages 32..55.
; Page 68: [0] next block ordinal, [1] block count, descriptors at 0100 (page, ptr16, len16).
; ROM 05A9..05E2 decoder is retained below, with byte acquisition replacing pulse acquisition.
        DEVICE ZXSPECTRUMNEXT
        ORG 0x386E
loader: di
        exx
        push bc
        push de
        push hl
        exx
        push af
        push bc
        push de
        push hl
        nextreg 0x50,68
        ld a,(1)
        ld c,a
        ld a,(0)
        cp c
        jr nc,.eof
        ld l,a
        inc a
        ld (0),a
        ld h,0
        ld e,l
        ld d,h
        add hl,hl
        add hl,hl
        add hl,de
        ld de,0x0100
        add hl,de
        ld b,(hl)
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ex de,hl              ; B page, HL source address, DE raw bytes remaining
        ld a,b
        nextreg 0x50,a
        jr .ready
.eof:   ld de,0
        ld hl,0
        ld b,32
.ready: exx                   ; keep the stream cursor in alternate registers
        pop hl
        pop de
        pop bc
        pop af
        ld h,0
        ld b,176
        ld c,0x22             ; canonical EAR state; pulse phase is intentionally not simulated
        call nextbyte
        jp nc,finish
        jr byte_done          ; first byte is the flag (as at 05A7)

; Exact original decoder operations, with relocated branches only.
decode: ex af,af'
        jr nz,flag_compare
        jr nc,verify_byte
store:  push af
        ld a,ixh
        cp 0x40
        jr c,store_skip
write_byte:
        ld (ix+0),l
store_skip:
        pop af
        jr advance
flag_compare:
        rl c
        xor l
        jp nz,finish
        ld a,c
        rra
        ld c,a
        inc de
        jr consume
verify_byte:
        call peek_ix
        xor l
        jp nz,finish
advance:
        inc ix
consume:
        dec de
accepted:
        ex af,af'
        ld b,178
        call nextbyte
        jp nc,finish
        ld b,176
byte_done:
        ld a,h
        xor l
        ld h,a
        ld a,d
        or e
        jr nz,decode
        ld a,h
parity: cp 1
finish: nextreg 0x50,255
        exx
        pop hl
        pop de
        pop bc
        exx
        ret

; L = byte, carry = available. Does not change the decoder's BC/DE/H or AF'.
nextbyte:
        exx
        ld a,d
        or e
        jr z,.empty
        ld a,(hl)
        ld c,a
        inc hl
        dec de
        ld a,h
        cp 0x20
        jr nz,.same
        ld h,0
        inc b
        ld a,b
        nextreg 0x50,a
.same:  ld a,c
        exx
        ld l,a
        scf
        ret
.empty: exx
        xor a
        ret
; Original ROM ignores stores below 4000. Reads below 2000 must see ROM, not tape.
peek_ix:
        push hl
        push af
        ld a,ixh
        cp 0x20
        jr nc,.direct
        nextreg 0x50,255
        ld a,(ix+0)
        ld l,a
        exx
        ld a,b
        nextreg 0x50,a
        exx
        jr .out
.direct:
        ld l,(ix+0)
.out:   pop af
        ld a,l
        pop hl
        ret
rom_end:
        ASSERT rom_end < 0x3D00
        SAVEBIN "inferno_rom.bin",loader,rom_end-loader
