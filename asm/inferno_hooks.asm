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
        ld c,0x7E             ; actual standard-TZX pulse return state (polarity 0), proven on all blocks
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

; Capture kernel (no display layer is enabled). All scratch and stack writes are in page 68.
; Original CALL return bytes are reproduced exactly; JP sites displace complete instructions.
CAP_SP      EQU 0x03F0
CAP_PTR     EQU 0x03F2
CAP_COUNT   EQU 0x03F4
CAP_OVER    EQU 0x03F5
CAP_PHASE   EQU 0x03F6
CAP_MODE    EQU 0x03F7
CAP_MAP     EQU 0x0400
CAP_LOG     EQU 0x0900
CAP_STACK   EQU 0x1FF0
        ORG 0x3A00
cap_scene:
        di
        nextreg 0x07,3
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        push bc
        push de
        push hl
        ld hl,0x9B00
        ld de,CAP_MAP
        ld bc,0x0480
        ldir
        ld hl,CAP_LOG
        ld (CAP_PTR),hl
        xor a
        ld (CAP_COUNT),a
        ld (CAP_OVER),a
        inc a
        ld (CAP_PHASE),a
        ld hl,(CAP_SP)
        dec hl
        ld (hl),0x8F
        dec hl
        ld (hl),0x7F
        ld (CAP_SP),hl
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        nextreg 0x07,0
        ei
        jp 0x9535

cap_normal:
        di
        nextreg 0x07,3
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        xor a
        jp cap_actor
cap_wrapped:
        di
        nextreg 0x07,3
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        ld a,1
cap_actor:
        push bc
        push de
        push hl
        ld (CAP_MODE),a
        ld a,(CAP_PHASE)
        cp 1
        jr nz,cap_actor_out
        ld a,(CAP_OVER)
        or a
        jr nz,cap_actor_out
        ld de,(CAP_PTR)
        ld a,d
        cp 0x1B
        jr nc,cap_overflow
        ld a,ixl
        ld (de),a
        inc de
        ld a,ixh
        ld (de),a
        inc de
        ld a,iyl
        ld (de),a
        inc de
        ld a,(ix+2)
        ld (de),a
        inc de
        ld a,(ix+4)
        ld (de),a
        inc de
        ld h,0xC1
        ld l,a
        ld a,(hl)
        inc l
        ld h,(hl)
        ld l,a
        ld a,h
        cp 0x40
        jr c,cap_overflow
        ld a,(hl)              ; original header, including tile page
        inc hl
        ld (de),a
        inc de
cap_row:
        ld a,(hl)
        inc hl
        ld (de),a
        inc de
        or a
        jr z,cap_actor_done
        cp 129
        jr nc,cap_overflow
        ld c,a
        inc c
        inc c
        ld b,0
        ld a,d
        cp 0x1B                ; at least a full 256-byte row margin remains
        jr nc,cap_overflow
        ldir                   ; dx, dy, then width tile bytes
        jr cap_row
cap_actor_done:
        ld (CAP_PTR),de
        ld a,(CAP_COUNT)
        inc a
        jr z,cap_overflow
        ld (CAP_COUNT),a
        jr cap_actor_out
cap_overflow:
        ld a,1
        ld (CAP_OVER),a         ; fail closed; original producer still executes unchanged
cap_actor_out:
        ld a,(CAP_MODE)
        or a
        jr nz,cap_wrapped_out
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        nextreg 0x07,0
        ld l,(ix+4)
        ei
        jp 0x959E
cap_wrapped_out:
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        nextreg 0x07,0
        ld l,(ix+4)
        ei
        jp 0x96A4

cap_done:
        di
        nextreg 0x07,3
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        push hl
        ld a,(CAP_PHASE)
        cp 1
        jr nz,.phase_done
        ld a,(CAP_OVER)
        or a
        jr nz,.invalid
        ld a,2
        jr .set_phase
.invalid:
        xor a
.set_phase:
        ld (CAP_PHASE),a
.phase_done:
        ld hl,(CAP_SP)
        dec hl
        ld (hl),0x8F
        dec hl
        ld (hl),0x95
        ld (CAP_SP),hl
        pop hl
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        nextreg 0x07,0
        ei
        jp 0x9790
cap_end:
        ASSERT cap_end < 0x3D00
        SAVEBIN "inferno_capture.bin",cap_scene,cap_end-cap_scene
