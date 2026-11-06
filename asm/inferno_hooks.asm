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
.copy_map:
        DUP 16
        ldi
        EDUP
        jp pe,.copy_map
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

; Renderer tile primitive, page 69 mapped at 0000, DI and 28MHz; private stack in that page.
; Inputs 1E00 tile16, 1E02 screenY, 1E03 screenX, 1E05 target bank (28/31), 1E06 flash phase.
; Output 1E04 error (0 success, 1 invalid input, 2 visible-front target).
; Writes ONLY an inactive L2 bank, preserving visibility. Write paging is off before RET.
R_TILE      EQU 0x1E00
R_Y         EQU 0x1E02
R_X         EQU 0x1E03
R_ERROR     EQU 0x1E04
R_BANK      EQU 0x1E05
R_FLASH     EQU 0x1E06
R_CHECK     EQU 0x1E07
R_ATTR      EQU 0x1E10
R_PAPER     EQU 0x1E11
R_VISIBLE   EQU 0x1E12
R_ACCESS    EQU 0x1E13
R_FRONT     EQU 0x1E14
        ORG 0
render_tile:
        xor a
        ld (R_ERROR),a
        ld hl,(R_TILE)
        ld a,h
        and 0xFC
        jp nz,rt_bad
        ld a,(R_X)
        and 7
        jp nz,rt_bad
        ld a,(R_Y)
        cp 48
        jp c,rt_bad
        cp 185
        jp nc,rt_bad
        and 7
        jp nz,rt_bad
        ld a,(R_FLASH)
        and 0xFE
        jp nz,rt_bad
        ld a,(R_BANK)
        cp 28
        jr z,.bank_ok
        cp 31
        jr z,.bank_ok
        cp 36                  ; private colour-cache bank, never selected for display
        jp nz,rt_bad
        ld a,(R_Y)
        cp 57                  ; cache occupies y=48/56 in this bank only
        jp nc,rt_bad
.bank_ok:
        ld bc,0x243B
        ld a,0x69
        out (c),a
        inc b
        in a,(c)
        and 0x80
        rlca
        rlca
        ld (R_VISIBLE),a
        ld bc,0x243B
        ld a,0x12
        out (c),a
        inc b
        in a,(c)
        ld (R_FRONT),a
        ld b,a
        ld a,(R_VISIBLE)
        or a
        jr z,.not_front
        ld a,(R_BANK)
        cp b
        jr nz,.not_front
        ld a,2
        ld (R_ERROR),a
        ret
.not_front:
        ld a,(R_CHECK)
        or a
        ret nz
        ld a,(R_BANK)
        nextreg 0x13,a
        ld hl,(R_TILE)
        ld de,0xFC00
        add hl,de
        ld a,(hl)
        ld (R_ATTR),a
        and 0x40
        rrca
        rrca
        rrca
        ld e,a                 ; bright bit as colour bit 3
        ld a,(R_ATTR)
        and 7
        or e
        ld d,a                 ; ink
        and 7
        jr nz,.ink_ok
        ld d,0
.ink_ok:
        ld a,(R_ATTR)
        rrca
        rrca
        rrca
        and 7
        or e
        ld c,a                 ; paper
        and 7
        jr nz,.paper_ok
        ld c,0
.paper_ok:
        ld a,d
        ex af,af'              ; ink lives in A'
        ld a,(R_ATTR)
        and 0x80
        jr z,.colours
        ld a,(R_FLASH)
        and 1
        jr z,.colours
        ld a,c
        ex af,af'
        ld c,a                 ; swap ink/paper on FLASH phase 1
.colours:
        ld a,c
        ld (R_PAPER),a
        ld hl,(R_TILE)
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xDC00
        add hl,de
        ld a,(R_Y)
        and 0xC0
        or 9                   ; shadow bank, write paging only
        ld b,a
        ld a,(R_VISIBLE)
        or b
        ld (R_ACCESS),a
        ld a,(R_Y)
        and 63
        ld d,a
        ld a,(R_X)
        ld e,a
        ld a,(R_ACCESS)
        ld bc,0x123B
        out (c),a
        ld a,(R_PAPER)
        ld c,a
        ld iyl,8
rt_row:
        ld a,(hl)
        inc hl
        ld b,a
        rlc b
        ld a,c
        jr nc,rt_paper0
        ex af,af'
        ld (de),a
        ex af,af'
        jr rt_pixel0
rt_paper0:
        ld (de),a
rt_pixel0:
        inc e
        rlc b
        ld a,c
        jr nc,rt_paper1
        ex af,af'
        ld (de),a
        ex af,af'
        jr rt_pixel1
rt_paper1:
        ld (de),a
rt_pixel1:
        inc e
        rlc b
        ld a,c
        jr nc,rt_paper2
        ex af,af'
        ld (de),a
        ex af,af'
        jr rt_pixel2
rt_paper2:
        ld (de),a
rt_pixel2:
        inc e
        rlc b
        ld a,c
        jr nc,rt_paper3
        ex af,af'
        ld (de),a
        ex af,af'
        jr rt_pixel3
rt_paper3:
        ld (de),a
rt_pixel3:
        inc e
        rlc b
        ld a,c
        jr nc,rt_paper4
        ex af,af'
        ld (de),a
        ex af,af'
        jr rt_pixel4
rt_paper4:
        ld (de),a
rt_pixel4:
        inc e
        rlc b
        ld a,c
        jr nc,rt_paper5
        ex af,af'
        ld (de),a
        ex af,af'
        jr rt_pixel5
rt_paper5:
        ld (de),a
rt_pixel5:
        inc e
        rlc b
        ld a,c
        jr nc,rt_paper6
        ex af,af'
        ld (de),a
        ex af,af'
        jr rt_pixel6
rt_paper6:
        ld (de),a
rt_pixel6:
        inc e
        rlc b
        ld a,c
        jr nc,rt_paper7
        ex af,af'
        ld (de),a
        ex af,af'
        jr rt_pixel7
rt_paper7:
        ld (de),a
rt_pixel7:
        inc e
        ld a,(R_X)
        ld e,a
        inc d
        dec iyl
        jp nz,rt_row
        ld a,(R_VISIBLE)
        ld bc,0x123B
        out (c),a
        ret
rt_bad:
        ld a,1
        ld (R_ERROR),a
        ret
render_tile_end:
        ASSERT render_tile_end < 0x1800
        SAVEBIN "inferno_tile.bin",render_tile,render_tile_end-render_tile

; Direct-mapped 64-entry tile cache. Page 73: metadata 0000..03FF; pixels 1000..1FFF.
; Cache fill reuses the checked pixel primitive with bank 36 / y 48 or 56. Full source-byte,
; tile ID and FLASH-phase checks precede a hit; metadata VALID is committed last.
R_GFX       EQU 0x1E15
R_META      EQU 0x1E17
R_SLOT      EQU 0x1E19
R_HIT       EQU 0x1E1A
R_OLDX      EQU 0x1E1B
R_OLDY      EQU 0x1E1C
R_OLDBANK   EQU 0x1E1D
R_CSRC      EQU 0x1E1E
R_SAVEDSP   EQU 0x1E20
        ORG 0x0400
render_cached_tile:
        xor a
        ld (R_HIT),a
        ld a,(R_BANK)
        cp 36
        jp z,rt_bad             ; bank 36 is internal cache storage, not a frame target
        ld a,1
        ld (R_CHECK),a
        call render_tile        ; validate without touching VRAM or changing shadow bank
        xor a
        ld (R_CHECK),a
        ld a,(R_ERROR)
        or a
        ret nz
        nextreg 0x51,73
        ld hl,(R_TILE)
        ld a,l
        and 63
        ld (R_SLOT),a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x2000
        add hl,de
        ld (R_META),hl
        ld hl,(R_TILE)
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xDC00
        add hl,de
        ld (R_GFX),hl
        ld hl,(R_TILE)
        ld de,0xFC00
        add hl,de
        ld a,(hl)
        ld (R_ATTR),a
        ld hl,(R_META)
        ld a,(hl)
        cp 0xA5
        jr nz,rc_miss
        inc hl
        ld de,(R_TILE)
        ld a,(hl)
        cp e
        jr nz,rc_miss
        inc hl
        ld a,(hl)
        cp d
        jr nz,rc_miss
        inc hl
        ld de,(R_GFX)
        ld b,8
rc_compare:
        ld a,(de)
        cp (hl)
        jr nz,rc_miss
        inc de
        inc hl
        djnz rc_compare
        ld a,(R_ATTR)
        cp (hl)
        jr nz,rc_miss
        and 0x80
        jr z,rc_hit
        inc hl
        ld a,(R_FLASH)
        cp (hl)
        jr nz,rc_miss
rc_hit:
        ld a,1
        ld (R_HIT),a
        jp rc_blit
rc_miss:
        ld hl,(R_META)
        ld (hl),0
        ld a,(R_X)
        ld (R_OLDX),a
        ld a,(R_Y)
        ld (R_OLDY),a
        ld a,(R_BANK)
        ld (R_OLDBANK),a
        ld a,(R_SLOT)
        and 31
        rlca
        rlca
        rlca
        ld (R_X),a
        ld a,(R_SLOT)
        and 32
        rrca
        rrca
        add a,48
        ld (R_Y),a
        ld a,36
        ld (R_BANK),a
        call render_tile
        ld a,(R_OLDX)
        ld (R_X),a
        ld a,(R_OLDY)
        ld (R_Y),a
        ld a,(R_OLDBANK)
        ld (R_BANK),a
        ld a,(R_ERROR)
        or a
        jp nz,rc_exit
        ld hl,(R_META)
        inc hl
        ld de,(R_TILE)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(R_GFX)
        ld b,8
rc_key:
        ld a,(de)
        ld (hl),a
        inc de
        inc hl
        djnz rc_key
        ld a,(R_ATTR)
        ld (hl),a
        inc hl
        ld a,(R_FLASH)
        ld (hl),a
        ld hl,(R_META)
        ld (hl),0xA5
rc_blit:
        ld a,(R_BANK)
        nextreg 0x13,a
        ld a,(R_SLOT)
        and 31
        rlca
        rlca
        rlca
        ld l,a
        ld a,(R_SLOT)
        and 32
        rrca
        rrca
        add a,0x30
        ld h,a
        ld (R_CSRC),hl
        ld a,(R_Y)
        and 0xC0
        or 9
        ld b,a
        ld a,(R_VISIBLE)
        or b
        ld (R_ACCESS),a
        ld a,(R_Y)
        and 63
        ld d,a
        ld a,(R_X)
        ld e,a
        ld a,8
        add de,a                ; PUSH writes backwards from the end of each destination row
        ld hl,(R_CSRC)
        exx                     ; alternate HL/DE retain source/destination row addresses
        ld (R_SAVEDSP),sp
        ld iyl,8
        ld a,(R_ACCESS)
        ld bc,0x123B
        out (c),a
rc_row:
        exx
        ld sp,hl
        exx
        pop bc
        pop de
        pop hl
        pop ix
        exx
        ex de,hl
        ld sp,hl
        ex de,hl
        exx
        push ix
        push hl
        push de
        push bc
        exx
        inc h
        inc d
        exx
        dec iyl
        jp nz,rc_row
        ld a,(R_VISIBLE)
        ld bc,0x123B
        out (c),a
        ld sp,(R_SAVEDSP)
rc_exit:
        nextreg 0x51,68
        ret
render_cache_end:
        ASSERT render_cache_end < 0x1800
        SAVEBIN "inferno_tilecache.bin",render_cached_tile,render_cache_end-render_cached_tile

; Prepared cache-slot jobs [x,y,slot] at 1000, count <=576. Caller must validate
; live cache contents before scheduling; this routine only copies prepared RGB.
; Entire list is preflighted before any VRAM write. No visible-buffer commit.
B_COUNT     EQU 0x1E30
B_BANK      EQU 0x1E32
B_ERROR     EQU 0x1E33
B_JOBS      EQU 0x1000
        ORG 0x0800
render_batch:
        xor a
        ld (B_ERROR),a
        ld hl,(B_COUNT)
        ld de,577
        or a
        sbc hl,de
        jp nc,rb_bad
        ld a,(B_BANK)
        cp 28
        jr z,rb_bank
        cp 31
        jp nz,rb_bad
rb_bank:
        ld bc,0x243B
        ld a,0x69
        out (c),a
        inc b
        in a,(c)
        and 0x80
        rlca
        rlca
        ld (R_VISIBLE),a
        ld a,0x12
        dec b
        out (c),a
        inc b
        in a,(c)
        ld b,a
        ld a,(R_VISIBLE)
        or a
        jr z,rb_front_ok
        ld a,(B_BANK)
        cp b
        jp z,rb_front
rb_front_ok:
        nextreg 0x51,73
        ld bc,(B_COUNT)
        ld a,b
        or c
        jp z,rb_exit
        ld iy,B_JOBS
rb_check:
        ld a,(iy+0)
        and 7
        jp nz,rb_bad_mapped
        ld a,(iy+1)
        cp 48
        jp c,rb_bad_mapped
        cp 185
        jp nc,rb_bad_mapped
        and 7
        jp nz,rb_bad_mapped
        ld a,(iy+2)
        cp 64
        jp nc,rb_bad_mapped
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x2000
        add hl,de
        ld a,(hl)
        cp 0xA5
        jp nz,rb_bad_mapped
        inc iy
        inc iy
        inc iy
        dec bc
        ld a,b
        or c
        jr nz,rb_check
        ld a,(B_BANK)
        nextreg 0x13,a
        ld (R_SAVEDSP),sp
        ld iy,B_JOBS
        ld bc,(B_COUNT)
        exx                     ; alternate BC owns remaining job count
rb_job:
        ld a,(iy+1)
        and 0xC0
        or 9
        ld b,a
        ld a,(R_VISIBLE)
        or b
        ld (R_ACCESS),a
        ld a,(iy+1)
        and 63
        ld d,a
        ld e,(iy+0)
        ld a,8
        add de,a
        ld a,(iy+2)
        and 31
        rlca
        rlca
        rlca
        ld l,a
        ld a,(iy+2)
        and 32
        rrca
        rrca
        add a,0x30
        ld h,a
        ld (R_CSRC),hl
        ld (R_GFX),de
        exx
        ld hl,(R_CSRC)
        ld de,(R_GFX)
        exx
        ld a,(R_ACCESS)
        ld bc,0x123B
        out (c),a
        ld a,8
rb_row:
        exx
        ld sp,hl
        exx
        pop bc
        pop de
        pop hl
        pop ix
        exx
        ex de,hl
        ld sp,hl
        ex de,hl
        exx
        push ix
        push hl
        push de
        push bc
        exx
        inc h
        inc d
        exx
        dec a
        jp nz,rb_row
        ld a,(R_VISIBLE)
        ld bc,0x123B
        out (c),a
        ld sp,(R_SAVEDSP)
        inc iy
        inc iy
        inc iy
        exx
        dec bc
        ld a,b
        or c
        exx
        jp nz,rb_job
rb_exit:
        nextreg 0x51,68
        ret
rb_front:
        ld a,2
        ld (B_ERROR),a
        ret
rb_bad_mapped:
        nextreg 0x51,68
rb_bad:
        ld a,1
        ld (B_ERROR),a
        ret
render_batch_end:
        ASSERT render_batch_end < B_JOBS
        SAVEBIN "inferno_tilebatch.bin",render_batch,render_batch_end-render_batch

; Complete scenery baseline. Copy the captured clean map from state page 68, then
; compare each cell's full live source key with the chosen buffer's page 70/71.
; Content keys are per-buffer: an update to one back buffer never validates the other.
; This correctness baseline uses the checked immediate cache routine, not the batch API.
S_MAP       EQU 0x1000
S_KEY       EQU 0x1E40
S_MP        EQU 0x1E42
S_PAGE      EQU 0x1E44
S_CHANGED   EQU 0x1E45
S_LEFT      EQU 0x1E47
S_FLAGPTR   EQU 0x1E49
S_FLAGS     EQU 0x1500          ; page aligned: BC can index flags without saving HL
        ORG 0x0A00
render_scene:
        xor a
        ld (R_ERROR),a
        ld (S_CHANGED),a
        ld (S_CHANGED+1),a
        ld a,(R_BANK)
        cp 28
        jr z,rs_bank
        cp 31
        jp nz,rt_bad
rs_bank:
        ld (R_OLDBANK),a
        ld a,(R_X)
        ld (R_OLDX),a
        ld a,(R_Y)
        ld (R_OLDY),a
        xor a
        ld (R_X),a
        ld a,48
        ld (R_Y),a
        ld a,1
        ld (R_CHECK),a
        call render_tile
        xor a
        ld (R_CHECK),a
        ld a,(R_ERROR)
        or a
        ret nz
        nextreg 0x51,68
        ld hl,0x2400
        ld de,S_MAP
        ld bc,1152
        ldir
rs_clear_flags:
        ld (R_SAVEDSP),sp
        ld sp,S_FLAGS+1024
        ld bc,0
        ld a,32
rs_clear_chunk:
        DUP 16
        push bc
        EDUP
        dec a
        jr nz,rs_clear_chunk
        ld sp,(R_SAVEDSP)
rs_flags_cleared:
        ld a,(R_BANK)
        cp 28
        ld a,70
        jr z,rs_page
        inc a
rs_page:
        ld (S_PAGE),a
        nextreg 0x51,a
        call render_quiet
        jp nc,rs_exit
        ld hl,0x2000
        ld (S_KEY),hl
        ld hl,S_MAP
        ld (S_MP),hl
        ld hl,576
        ld (S_LEFT),hl
rs_cell:
        ld hl,(S_MP)
        ld e,(hl)
        inc hl
        ld a,(hl)
        and 3
        ld d,a
        inc hl
        ld (S_MP),hl
        ld (R_TILE),de
        ld hl,S_FLAGS
        add hl,de
        ld (S_FLAGPTR),hl
        ld hl,(S_KEY)
        ld a,(hl)
        cp 0xA5
        jr nz,rs_paint
        inc hl
        ld de,(R_TILE)
        ld a,(hl)
        cp e
        jr nz,rs_paint
        inc hl
        ld a,(hl)
        cp d
        jr nz,rs_paint
        ld hl,(S_FLAGPTR)
        ld a,(hl)
        cp 1
        jp z,rs_next
        cp 2
        jr z,rs_paint
        ld hl,(R_TILE)
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xDC00
        add hl,de
        ld (R_GFX),hl
        ld hl,(R_TILE)
        ld de,0xFC00
        add hl,de
        ld a,(hl)
        ld (R_ATTR),a
        ld hl,(S_KEY)
        inc hl
        inc hl
        inc hl
        ld de,(R_GFX)
        ld b,8
rs_compare:
        ld a,(de)
        cp (hl)
        jr nz,rs_dirty
        inc de
        inc hl
        djnz rs_compare
        ld a,(R_ATTR)
        cp (hl)
        jr nz,rs_dirty
        and 0x80
        jr z,rs_clean
        inc hl
        ld a,(R_FLASH)
        cp (hl)
        jr nz,rs_dirty
rs_clean:
        ld hl,(S_FLAGPTR)
        ld (hl),1
        jr rs_next
rs_dirty:
        ld hl,(S_FLAGPTR)
        ld (hl),2
rs_paint:
        call render_cached_tile
        ld a,(R_ERROR)
        or a
        jp nz,rs_exit
        ld a,(S_PAGE)
        nextreg 0x51,a
        ld hl,(S_KEY)
        inc hl
        ld de,(R_TILE)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(R_GFX)
        ld b,8
rs_save:
        ld a,(de)
        ld (hl),a
        inc de
        inc hl
        djnz rs_save
        ld a,(R_ATTR)
        ld (hl),a
        inc hl
        ld a,(R_FLASH)
        ld (hl),a
        ld hl,(S_KEY)
        ld (hl),0xA5
        ld hl,(S_CHANGED)
        inc hl
        ld (S_CHANGED),hl
rs_next:
        ld hl,(S_KEY)
        ld de,13
        add hl,de
        ld (S_KEY),hl
        ld a,(R_X)
        add a,8
        ld (R_X),a
        jr nc,rs_same_row
        ld a,(R_Y)
        add a,8
        ld (R_Y),a
rs_same_row:
        ld hl,(S_LEFT)
        dec hl
        ld (S_LEFT),hl
        ld a,h
        or l
        jp nz,rs_cell
rs_exit:
        nextreg 0x51,68
        ret
render_scene_end:
        ASSERT render_scene_end < S_MAP
        SAVEBIN "inferno_scene.bin",render_scene,render_scene_end-render_scene

; Fast no-change gate: compare every map ID, but each distinct live source only once.
; Last-frame per-buffer keys are coherent because render_scene always completes under DI.
; Carry clear = complete identical image; carry set = use the dirty-cell worker.
        ORG 0x0C00
render_quiet:
        ld hl,S_MAP
        ld de,0x2000
rq_cell:
        ld a,(de)
        cp 0xA5
        jp nz,rq_dirty
        inc de
        ld a,(de)
        cp (hl)
        jp nz,rq_dirty
        ld c,(hl)
        inc hl
        inc de
        ld a,(hl)
        and 3
        ld b,a
        ld a,(de)
        cp b
        jp nz,rq_dirty
        inc hl
        inc de
        ld a,b
        add a,S_FLAGS/256
        ld b,a
        ld a,(bc)
        or a
        jr z,rq_source
        ld a,10                 ; key already advanced past valid and ID
        add de,a
        jr rq_next
rq_source:
        push hl                 ; only distinct sources need to save the map cursor
        ld (S_FLAGPTR),bc
        ld a,b
        sub S_FLAGS/256
        ld b,a
        ld (R_TILE),bc
        ld h,b
        ld l,c
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,0xDC00
        add hl,bc
rq_bytes:
        DUP 8
        ld a,(de)
        cp (hl)
        jr nz,rq_dirty_pop
        inc de
        inc hl
        EDUP
        ld hl,(R_TILE)
        ld bc,0xFC00
        add hl,bc
        ld a,(de)
        cp (hl)
        jr nz,rq_dirty_pop
        and 0x80
        inc de
        jr z,rq_source_ok
        ld a,(R_FLASH)
        ld b,a
        ld a,(de)
        cp b
        jr nz,rq_dirty_pop
rq_source_ok:
        inc de
        ld hl,(S_FLAGPTR)
        ld (hl),1
        pop hl
rq_next:
        ld a,h
        cp 0x14
        jp nz,rq_cell
        ld a,l
        cp 0x80
        jp nz,rq_cell
        or a
        ret
rq_dirty_pop:
        pop hl
rq_dirty:
        scf
        ret
render_quiet_end:
        ASSERT render_quiet_end < S_MAP
        SAVEBIN "inferno_tilequiet.bin",render_quiet,render_quiet_end-render_quiet

; Experimental text-tilemap scenery worker, standalone page 69 image.
; Page 14 (unused by the original 48K machine): maps 0000/0600, definitions
; 0C00/1400 (256 per half). Only clipped 32x18 cells of each 40-column map
; are fetched. Rebuild source definitions once per ID per image: no stale keys.
; Caller owns DI/28MHz/private stack. Does NOT enable or commit any display layer.
T_FLAGS     EQU 0x0800
T_PAIRS     EQU 0x1000          ; ID*2 -> slot/attribute, twice its flag address
T_MAP       EQU 0x2400          ; consume page-68 capture directly, no second map copy
T_HALF      EQU 0x1E80
T_FLASH     EQU 0x1E81
T_FRONT     EQU 0x1E82
T_ERROR     EQU 0x1E83
T_COUNT     EQU 0x1E84
T_SP        EQU 0x1E86
T_DEFHI     EQU 0x1E88
T_MAPSP     EQU 0x1E89
T_PATTERN   EQU 0x1E8B
        ORG 0
render_textmap:
        xor a
        ld (T_ERROR),a
        ld (T_COUNT),a
        ld (T_COUNT+1),a
        ld a,(T_HALF)
        cp 2
        jp nc,tm_bad
        ld b,a
        ld a,(T_FRONT)
        cp b
        jp z,tm_bad
        ld a,(T_FLASH)
        cp 2
        jp nc,tm_bad
        ld (T_SP),sp
        ld sp,T_FLAGS+1024
        ld bc,0
        ld a,32
.tm_clear:
        DUP 16
        push bc
        EDUP
        dec a
        jr nz,.tm_clear
        ld sp,(T_SP)
        ld a,(T_HALF)
        or a
        ld de,0x4000
        ld a,0x4C
        jr z,.tm_half
        ld de,0x4600
        ld a,0x54
.tm_half:
        ld (T_DEFHI),a
        nextreg 0x52,14         ; original screen page hidden only inside DI domain
        ld sp,T_MAP             ; POP reads the captured map; interrupts remain disabled
        ld ix,0x2012
.tm_cell:
        pop bc
        ld a,b
        and 3
        add a,T_FLAGS/256
        ld h,a
        ld l,c
        ld a,(hl)
        or a
        jr z,.tm_source
.tm_ready:
        add hl,hl
.tm_pair:
        ldi
        ldi
        dec ixh
        jr nz,.tm_cell
        ld a,16
        add de,a
        ld ixh,32
        dec ixl
        jr nz,.tm_cell
.tm_exit:
        ld sp,(T_SP)
        nextreg 0x52,10         ; original 48K screen page restored before returning
        ret
.tm_source:
        ld (T_MAPSP),sp
        ld sp,(T_SP)
        push de
        push hl
        ld de,(T_COUNT)
        ld a,d
        or a
        jp nz,.tm_full
        inc de
        ld (T_COUNT),de
        dec e
        ld (hl),1
        add hl,hl
        ld (hl),e
        ld d,8
        mul d,e
        ld a,(T_DEFHI)
        add a,d
        ld d,a
        ld (T_PATTERN),de
        pop hl
        push hl
        ld a,h
        sub T_FLAGS/256
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,0xDC00
        DUP 8
        ldi
        EDUP
        pop bc
        ld a,b
        add a,0xF4             ; flags page 08..0B -> attributes FC..FF
        ld h,a
        ld l,c
        ld a,(hl)
        ld l,a
        and 0x80
        jr z,.tm_noinvert
        ld a,(T_FLASH)
        or a
        jr z,.tm_noinvert
        push hl
        ld hl,(T_PATTERN)
        DUP 8
        ld a,(hl)
        cpl
        ld (hl),a
        inc l
        EDUP
        pop hl
.tm_noinvert:
        ld h,4                 ; FLASH inverts bitmap: preserve distinct ULA ink/paper palettes
        ld a,(hl)
        ld e,a
        ld a,(T_HALF)
        or e
        ld e,a
        ld h,b
        ld l,c
        add hl,hl
        inc hl
        ld (hl),e
        dec hl
        pop de
        ld sp,(T_MAPSP)
        jp .tm_pair
.tm_full:
        pop bc
        pop de
        ld a,2
        ld (T_ERROR),a
        jp .tm_exit
tm_bad:
        ld a,1
        ld (T_ERROR),a
        ret
render_textmap_end:
        ASSERT render_textmap_end < 0x0400
        SAVEBIN "inferno_textmap.bin",render_textmap,render_textmap_end-render_textmap

; Hide replacement layers at the original gameplay return, before IM1/modal drawing.
; JP at 9019 replaces LD SP,86D5. Entry contract: original gameplay IFF=1/IM2.
        ORG 0x3B90
modal_hide:
        di
        nextreg 0x07,3
        nextreg 0x50,68
        ld sp,CAP_STACK
        push af
        push bc
        nextreg 0x62,0          ; cancel a pending copper commit before hiding the layers
        ld bc,0x243B
        ld a,0x6B
        out (c),a
        inc b
        in a,(c)
        and 0x7F
        nextreg 0x6B,a
        dec b
        ld a,0x15
        out (c),a
        inc b
        in a,(c)
        and 0xFE
        nextreg 0x15,a
        dec b
        ld a,0x69
        out (c),a
        inc b
        in a,(c)
        and 0x7F
        nextreg 0x69,a
        xor a
        ld (CAP_PHASE),a        ; no old actor log may re-enable a modal screen
        pop bc
        pop af
        nextreg 0x50,255
        nextreg 0x07,0
        ld sp,0x86D5
        ei
        jp 0x901C
modal_hide_end:
        ASSERT modal_hide_end < 0x3D00
        SAVEBIN "inferno_modal.bin",modal_hide,modal_hide_end-modal_hide

; Queue a complete, immutable copper list in page 74. No raster busy-wait.
; Caller: DI/28MHz, page 69 in slot 0, original page 10 in slot 2, private stack.
; READY is set only after BOTH scenery and approved sprite patterns/attributes exist.
; Front/back ownership cannot change until the copper acknowledges TOKEN through $7F.
Q_TOKEN     EQU 0x1EA0
Q_READY     EQU 0x1EA1
Q_BUSY      EQU 0x1EA2
Q_ERROR     EQU 0x1EA3
Q_TARGET    EQU 0x1EA4
Q_CONTROL   EQU 0x1EA5
Q_COUNT     EQU 0x1EA6
Q_PREVIOUS  EQU 0x1EA7
Q_PENDING   EQU 0x1EA8
Q_SEND      EQU 0x1EA9
Q_MAPBYTE   EQU 0x4603          ; WAIT + 128*(index MOVE + five attribute MOVEs)
Q_TOKENBYTE EQU 0x4609
Q_SIZE      EQU 1548
        ORG 0x0600
queue_frame:
        xor a
        ld (Q_ERROR),a
        ld a,(D_SETUP)
        cp 1
        ret nz
        ld a,(Q_READY)
        cp 1
        ret nz
        ld a,(Q_TARGET)
        cp 2
        jp nc,.invalid
        ld a,(Q_COUNT)
        cp 129
        jp nc,.invalid
        ld a,(Q_PREVIOUS)
        cp 129
        jp nc,.invalid
        ld a,(Q_BUSY)
        or a
        jr z,.available
        ld bc,0x243B
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        ld b,a
        ld a,(Q_TOKEN)
        cp b
        ret nz                 ; pending list/front/patterns remain owned by the old queue
        ld a,(Q_PENDING)
        ld (Q_PREVIOUS),a
.available:
        nextreg 0x62,0
        nextreg 0x52,74
        ld a,(Q_COUNT)
        ld (Q_PENDING),a
        ld e,a
        ld a,(Q_PREVIOUS)
        cp e
        jr nc,.clear_tail
        ld a,e
        ld (Q_SEND),a
        jr .tail_done
.clear_tail:
        ld (Q_SEND),a
        sub e
        jr z,.tail_done
        ld b,a
        ld d,12
        mul d,e
        ld hl,0x400B
        add hl,de
        ld de,12
.hide_tail:
        res 7,(hl)             ; hide old trailing sprites, even if supplied bytes were stale
        add hl,de
        djnz .hide_tail
.tail_done:
        ld a,(Q_TARGET)
        or a
        ld a,0x80
        jr z,.target
        ld a,0x86
.target:
        ld (Q_MAPBYTE),a
        ld a,(Q_CONTROL)
        or 1
        ld (Q_MAPBYTE+4),a
        ld a,(Q_TOKEN)
        inc a
        ld (Q_TOKEN),a
        ld (Q_TOKENBYTE),a
        nextreg 0x61,0
        ld bc,0x243B
        ld a,0x60
        out (c),a
        inc b
        ld hl,0x4000
        outinb
        outinb
        ld a,(Q_SEND)
        ld e,a
        or a
        jr z,.upload_tail
.upload:
        DUP 12
        outinb
        EDUP
        dec e
        jr nz,.upload
.upload_tail:
        ld hl,0x4602
        DUP 10
        outinb
        EDUP
        nextreg 0x52,10
        ld a,1
        ld (Q_BUSY),a
        xor a
        ld (Q_READY),a
        nextreg 0x62,0x40       ; reset CPC once; final HALT prevents recurring stale commits
        ret
.invalid:
        ld a,1
        ld (Q_ERROR),a
        ret
queue_frame_end:
        ASSERT queue_frame_end <= 0x0700
        SAVEBIN "inferno_queue.bin",queue_frame,queue_frame_end-queue_frame

; One-time hidden display setup. Copy the active ULA's actual 9-bit ink AND paper
; colours; legacy ULA paper entries are 128..143, not necessarily equal to ink 0..15.
D_SAVED43   EQU 0x1EB0
D_SAVED40   EQU 0x1EB1
D_TRANS     EQU 0x1EB2
D_ERROR     EQU 0x1EB3
D_SETUP     EQU 0x1EB4
D_COLOURS   EQU 0x1C80
        ORG 0x1A00
setup_display:
        xor a
        ld (D_SETUP),a
        ld (D_ERROR),a
        ld a,0x43
        call ds_read
        ld (D_SAVED43),a
        ld a,0x40
        call ds_read
        ld (D_SAVED40),a
        ld a,(D_SAVED43)
        and 1
        jp nz,ds_bad
        ld a,0x6B
        call ds_read
        and 0x80
        jp nz,ds_bad           ; never rewrite a visible tilemap palette
        ld a,0x14
        call ds_read
        ld (D_TRANS),a
        ld a,(D_SAVED43)
        and 0x0F
        ld e,a
        and 2
        DUP 5
        rlca
        EDUP
        or e
        nextreg 0x43,a
        ld hl,D_COLOURS
        ld e,0
.ds_read_colour:
        ld a,e
        nextreg 0x40,a
        ld a,0x41
        call ds_read
        ld (hl),a
        inc hl
        ld d,a
        ld a,(D_TRANS)
        cp d
        jp z,ds_bad            ; opaque scenery cannot use the global transparent colour
        ld a,0x44
        call ds_read
        and 1
        ld (hl),a
        inc hl
        inc e
        ld a,e
        cp 16
        jr nz,.ds_read_end
        ld e,128
.ds_read_end:
        cp 144
        jr nz,.ds_read_colour
        ld a,(D_SAVED43)
        and 0x0F
        or 0x30
        nextreg 0x43,a
        nextreg 0x40,0
        ld d,0
.ds_pair:
        ld a,d
        rrca
        rrca
        rrca
        and 15
        add a,a
        add a,0xA0
        ld l,a
        ld h,0x1C
        call ds_colour         ; paper from the original paper palette
        ld a,d
        and 7
        ld e,a
        ld a,d
        and 0x40
        rrca
        rrca
        rrca
        or e
        add a,a
        add a,0x80
        ld l,a
        call ds_colour         ; ink from the original ink palette
        inc d
        bit 7,d
        jr z,.ds_pair
        nextreg 0x1C,8
        nextreg 0x1B,16
        nextreg 0x1B,143
        nextreg 0x1B,80
        nextreg 0x1B,223
        nextreg 0x2F,1
        nextreg 0x30,32
        nextreg 0x31,176
        nextreg 0x6F,0x8C
        nextreg 0x6E,0x80
        nextreg 0x6B,0x0B
        nextreg 0x64,0
        nextreg 0x68,0
        ld a,0x69
        call ds_read
        and 0x7F
        nextreg 0x69,a
        ld a,0x15
        call ds_read
        and 0xE2              ; SLU layer order, sprites remain disabled
        nextreg 0x15,a
        ld a,1
        ld (D_SETUP),a
        jr ds_restore
ds_bad:
        ld a,1
        ld (D_ERROR),a
ds_restore:
        ld a,(D_SAVED43)
        nextreg 0x43,a
        ld a,(D_SAVED40)
        nextreg 0x40,a
        ret
ds_colour:
        ld a,(hl)
        nextreg 0x44,a
        inc l
        ld a,(hl)
        nextreg 0x44,a
        ret
ds_read:
        ld bc,0x243B
        out (c),a
        inc b
        in a,(c)
        ret
setup_display_end:
        ASSERT setup_display_end < D_COLOURS
        SAVEBIN "inferno_display.bin",setup_display,setup_display_end-setup_display

; Post-copy preparation preserves all original registers, including alternates, and
; leaves original RAM untouched. Rendering stays hidden until the sprite stage exists.
F_SCENE_READY EQU 0x1EAC
        ORG 0x3BE0
frame_hook:
        di
        nextreg 0x07,3
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        ex af,af'
        push af
        ex af,af'
        exx
        push bc
        push de
        push hl
        exx
        nextreg 0x50,69
        jp prepare_frame
frame_restore:
        nextreg 0x50,68
        ld sp,CAP_STACK-20
        exx
        pop hl
        pop de
        pop bc
        exx
        ex af,af'
        pop af
        ex af,af'
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        nextreg 0x07,0
        ld a,(0xAC49)           ; exact displaced instruction at 8F95
        ei
        jp 0x8F98
frame_hook_end:
        ASSERT frame_hook_end < 0x3D00
        SAVEBIN "inferno_framehook.bin",frame_hook,frame_hook_end-frame_hook

        ORG 0x0700
prepare_frame:
        nextreg 0x51,68
        ld sp,0x2000+CAP_STACK-20
        xor a
        ld (F_SCENE_READY),a
        ld (Q_READY),a
        ld a,(0x2000+CAP_PHASE)
        cp 2
        jr nz,.return
        xor a
        ld (0x2000+CAP_PHASE),a
        ld a,(Q_BUSY)
        or a
        jr z,.available
        ld bc,0x243B
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        ld b,a
        ld a,(Q_TOKEN)
        cp b
        jr nz,.return          ; never rebuild memory still owned by a pending display
.available:
        ld bc,0x243B
        ld a,0x6B
        out (c),a
        inc b
        in a,(c)
        and 0x80
        ld a,255
        jr z,.hidden
        dec b
        ld a,0x6E
        out (c),a
        inc b
        in a,(c)
        cp 0x86
        ld a,0
        jr nz,.hidden
        inc a
.hidden:
        ld (T_FRONT),a
        inc a
        and 1
        ld (T_HALF),a
        call render_textmap
        ld a,(T_ERROR)
        or a
        jr nz,.return
        ld a,1
        ld (F_SCENE_READY),a
.return:
        nextreg 0x51,255
        jp frame_restore
prepare_frame_end:
        ASSERT prepare_frame_end < 0x0800
        SAVEBIN "inferno_prepare.bin",prepare_frame,prepare_frame_end-prepare_frame

; Packed actor tile primitive, private worker page 75 at slot 0, DI / 28MHz.
; Lookup pages 96..111: 128 attribute pairs * 256 bitmap rows * 4 bytes.
; Canvas pages 112..115: up to 65536 pixels, two nibbles per byte.
; Black is zero here: whole-actor exterior classification follows composition.
; Caller supplies tile, aligned packed offset, stride 4..512 (multiple of 4), phase 0/1.
; Reject invalid inputs before any canvas write. Restore slot 1=68 / slot 2=10.
        ORG 0
P_TILE  EQU 0x1ED0
P_DEST  EQU 0x1ED2
P_STRIDE EQU 0x1ED4
P_FLASH EQU 0x1ED6
P_ERROR EQU 0x1ED7
P_PAIR  EQU 0x1ED8
P_XOR   EQU 0x1ED9
P_ROWS  EQU 0x1EDA
P_SOURCE EQU 0x1EDB
P_RAW   EQU 0x1EC0
pack_actor_tile:
        xor a
        ld (P_ERROR),a
        ld hl,(P_TILE)
        ld a,h
        cp 4
        jp nc,pack_bad
        ld a,(P_FLASH)
        cp 2
        jp nc,pack_bad
        ld hl,(P_STRIDE)
        ld a,l
        and 3
        jp nz,pack_bad
        ld de,4
        or a
        sbc hl,de
        jp c,pack_bad
        ld de,509
        or a
        sbc hl,de
        jp nc,pack_bad
        ld hl,(P_DEST)
        ld a,l
        and 3
        jp nz,pack_bad
        bit 7,h
        jp nz,pack_bad
        ld de,(P_STRIDE)
        ld b,7
pack_bound:
        add hl,de
        jp c,pack_bad
        djnz pack_bound
        ld de,3
        add hl,de
        jp c,pack_bad
        bit 7,h
        jp nz,pack_bad
        ld a,(P_SOURCE)
        cp 2
        jp nc,pack_bad
        or a
        jr nz,pack_pinned_attr
        ld hl,(P_TILE)
        ld de,0xFC00
        add hl,de
        ld a,(hl)
        jr pack_attr
pack_pinned_attr:
        ld a,(P_RAW+8)
pack_attr:
        ld c,a
        and 7
        rlca
        rlca
        or 0x40
        ld (P_PAIR),a
        ld a,c
        and 127
        rrca
        rrca
        rrca
        and 15
        add a,96
        nextreg 0x52,a
        ld a,c
        and 128
        ld c,a
        ld a,(P_FLASH)
        neg
        and c
        rlca
        neg
        ld (P_XOR),a
        ld a,(P_SOURCE)
        or a
        ld hl,P_RAW
        jr nz,pack_source
        ld hl,(P_TILE)
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xDC00
        add hl,de
pack_source:
        push hl
        pop ix
        ld a,8
        ld (P_ROWS),a
pack_row:
        ld hl,(P_DEST)
        ld a,h
        rlca
        rlca
        rlca
        and 3
        add a,112
        nextreg 0x51,a
        ld a,h
        and 31
        or 32
        ld d,a
        ld e,l
        ld a,(P_XOR)
        xor (ix+0)
        inc ix
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld a,(P_PAIR)
        or h
        ld h,a
        ldi
        ldi
        ldi
        ldi
        ld hl,(P_DEST)
        ld de,(P_STRIDE)
        add hl,de
        ld (P_DEST),hl
        ld a,(P_ROWS)
        dec a
        ld (P_ROWS),a
        jr nz,pack_row
        nextreg 0x51,68
        nextreg 0x52,10
        ret
pack_bad:
        ld a,1
        ld (P_ERROR),a
        ret
pack_actor_tile_end:
        ASSERT pack_actor_tile_end < 0x0400
        SAVEBIN "inferno_pack.bin",pack_actor_tile,pack_actor_tile_end-pack_actor_tile

; Whole-image B construction on private page 76; not installed in a NEX.
; Canvas 112..115; passable bits 116; exterior bits 117; horizontal closure
; lookup 128..135 (64KiB, generic byte connectivity, no game image catalogue).
; Every work unit remaps its inputs, so quota yields restore slots 1/2/3 safely.
        ORG 0
F_STRIDE EQU 0x1E90
F_SIZE EQU 0x1E92
F_DONE EQU 0x1E94
F_ERROR EQU 0x1E95
F_POS EQU 0x1E96
F_REVERSE EQU 0x1E98
F_CHANGED EQU 0x1E99
F_SIDE EQU 0x1E9A
F_COLUMN EQU 0x1E9B
F_OLD EQU 0x1E9D
F_PASSES EQU 0x1E9E
F_COMMAND EQU 0x1EA0
F_BUDGET EQU 0x1EA1
F_LEFT EQU 0x1EA2
F_ACTIVE EQU 0x1EA3
F_SAVED_SP EQU 0x1EA4
F_MASK_SIZE EQU 0x1EA6
F_MASK_STRIDE EQU 0x1EA8
fill_actor_image:
        xor a
        ld (F_ERROR),a
        ld (F_PASSES),a
        ld (F_PASSES+1),a
        ld a,(F_DONE)
        or a
        jp nz,fill_bad
        ld hl,(F_STRIDE)
        ld a,l
        and 3
        jp nz,fill_bad
        ld de,4
        or a
        sbc hl,de
        jp c,fill_bad
        ld de,509
        or a
        sbc hl,de
        jp nc,fill_bad
        ld hl,(F_SIZE)
        ld a,h
        or l
        jp z,fill_bad
        ld de,0x8001
        or a
        sbc hl,de
        jp nc,fill_bad
        ld hl,(F_SIZE)
        ld de,(F_STRIDE)
.geometry:
        call fill_checkpoint
        or a
        sbc hl,de
        jp c,fill_bad
        ld a,h
        or l
        jr nz,.geometry
        ld hl,(F_SIZE)
        srl h
        rr l
        srl h
        rr l
        ld (F_MASK_SIZE),hl
        ld hl,(F_STRIDE)
        srl h
        rr l
        srl h
        rr l
        ld (F_MASK_STRIDE),hl
        ld hl,0
        ld (F_POS),hl
.opacity:
        call fill_checkpoint
        call fill_canvas
        ld de,(F_POS)
        set 6,d
        nextreg 0x52,116
        ld b,0
        DUP 4
        ld a,(hl)
        inc hl
        push hl
        ld l,a
        ld h,6
        ld a,(hl)              ; two passable bits (black pixels)
        pop hl
        rlc b
        rlc b
        or b
        ld b,a
        EDUP
        ld a,b
        ld (de),a
        nextreg 0x52,117
        xor a
        ld (de),a              ; clear retained exterior state on every new image
        call fill_advance
        jr nz,.opacity
.iteration:
        ld hl,(F_PASSES)
        inc hl
        ld (F_PASSES),hl
        xor a
        ld (F_CHANGED),a
        ld (F_REVERSE),a
        ld hl,0
        ld (F_POS),hl
        call fill_sweep
        ld a,1
        ld (F_REVERSE),a
        ld hl,(F_MASK_SIZE)
        dec hl
        ld (F_POS),hl
        call fill_sweep
        ld a,(F_CHANGED)
        or a
        jr nz,.iteration
        ld hl,0
        ld (F_POS),hl
.finish:
        call fill_checkpoint
        call fill_canvas
        nextreg 0x52,117
        ld de,(F_POS)
        set 6,d
        ld a,(de)
        ld c,a
        DUP 4
        rlc c
        rlc c
        ld a,c
        and 3
        add a,8
        ld b,a
        ld a,(hl)
        push hl
        ld l,a
        ld h,b
        ld a,(hl)              ; zero -> black only when exterior bit is clear
        pop hl
        ld (hl),a
        inc hl
        EDUP
        call fill_advance
        jp nz,.finish
        ld a,1
        ld (F_DONE),a
        ld a,2
        ld (F_ACTIVE),a
        jp fill_restore
fill_bad:
        ld a,1
        ld (F_ERROR),a
        ld a,2
        ld (F_ACTIVE),a
        jp fill_restore
fill_sweep:
        ld hl,(F_MASK_STRIDE)
        ld (F_COLUMN),hl
        ld a,(F_REVERSE)
        or a
        ld a,128
        jr z,.edge
        ld a,1
.edge:
        ld (F_SIDE),a
.pair:
        call fill_checkpoint
        nextreg 0x51,116
        nextreg 0x52,117
        ld hl,(F_POS)
        ld de,(F_MASK_STRIDE)
        ld a,(F_REVERSE)
        or a
        jr nz,.below
        or a
        sbc hl,de
        jr c,.boundary
        jr .neighbour
.below:
        add hl,de
        ld de,(F_MASK_SIZE)
        or a
        sbc hl,de
        jr nc,.boundary
        add hl,de
.neighbour:
        set 6,h
        ld a,(hl)
        jr .seed
.boundary:
        ld a,255
.seed:
        ld c,a
        ld a,(F_SIDE)
        or c
        ld c,a
        ld hl,(F_POS)
        set 6,h
        ld a,(hl)
        ld (F_OLD),a
        or c
        ld c,a
        ld d,h
        ld e,l                 ; current exterior destination
        res 6,h
        set 5,h                ; passable source in slot 1
        ld a,(hl)
        push af
        rrca
        rrca
        rrca
        rrca
        rrca
        and 7
        add a,128
        nextreg 0x53,a
        pop af
        and 31
        or 0x60
        ld h,a
        ld l,c
        ld a,(hl)
        ld (de),a
        ld c,a
        ld a,(F_OLD)
        cp c
        jr z,.side
        ld a,1
        ld (F_CHANGED),a
.side:
        ld a,(F_REVERSE)
        or a
        ld a,c
        jr nz,.right
        rrca                    ; low bit -> next byte's high-bit seed
        and 128
        jr .set_side
.right:
        rlca                    ; high bit -> preceding byte's low-bit seed
        and 1
.set_side:
        ld (F_SIDE),a
        ld hl,(F_POS)
        ld a,(F_REVERSE)
        or a
        jr nz,.back
        inc hl
        ld (F_POS),hl
        ld de,(F_MASK_SIZE)
        or a
        sbc hl,de
        ret z
        jr .column
.back:
        ld a,h
        or l
        ret z
        dec hl
        ld (F_POS),hl
.column:
        ld hl,(F_COLUMN)
        dec hl
        ld (F_COLUMN),hl
        ld a,h
        or l
        jp nz,.pair
        jp fill_sweep
fill_canvas:
        ld hl,(F_POS)
        add hl,hl
        add hl,hl
        ld a,h
        rlca
        rlca
        rlca
        and 3
        add a,112
        nextreg 0x51,a
        ld a,h
        and 31
        or 0x20
        ld h,a
        ret
fill_advance:
        ld hl,(F_POS)
        inc hl
        ld (F_POS),hl
        ld de,(F_MASK_SIZE)
        or a
        sbc hl,de
        ret
fill_actor_image_end:
        ASSERT fill_actor_image_end < 0x0400
        ORG 0x0400
fill_actor_service:
        ld a,(F_BUDGET)
        dec a
        cp 16
        jp nc,fill_service_bad
        inc a
        ld (F_LEFT),a
        ld a,(F_COMMAND)
        or a
        jr z,.start
        cp 1
        jp nz,fill_service_bad
        ld a,(F_ACTIVE)
        cp 1
        jp nz,fill_service_bad
        ld sp,(F_SAVED_SP)
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ret
.start:
        ld a,(F_ACTIVE)
        or a
        jp nz,fill_service_bad
        inc a
        ld (F_ACTIVE),a
        jp fill_actor_image
fill_checkpoint:
        push af
        ld a,(F_LEFT)
        or a
        jr z,.yield
        dec a
        ld (F_LEFT),a
        pop af
        ret
.yield:
        push bc
        push de
        push hl
        push ix
        push iy
        ld (F_SAVED_SP),sp
        call fill_restore_maps
        ld sp,0x1FF0
        ret
fill_restore:
        call fill_restore_maps
        ret
fill_restore_maps:
        nextreg 0x51,68
        nextreg 0x52,10
        nextreg 0x53,11
        ret
fill_service_bad:
        ld a,1
        ld (F_ERROR),a
        ret
fill_actor_service_end:
        ASSERT fill_actor_service_end < 0x0600
        SAVEBIN "inferno_fill.bin",fill_actor_image,fill_actor_service_end-fill_actor_image

; Inferno bounded prepared-data transfer worker, private writable page 77.
; Reuses the gated shared backend and packets; no game/display hook installs it.
; Caller owns source cache and destination canvas; uploads protect BOTH halves
; of each 256-byte hardware pair using current and pending ownership bitsets.
; No image is published by this worker. OP=0 rectangle, OP=1 hardware pair.
        ORG 0
        DEFINE HLIB_PC_OTIR
        INCLUDE "lib/hlib_dma.asm"
        UNDEFINE HLIB_PC_OTIR
DB_SRC_PAGE EQU 0x1E00
DB_DST_PAGE EQU 0x1E01
DB_SRC EQU 0x1E02
DB_DST EQU 0x1E04
DB_WIDTH EQU 0x1E06
DB_ASTRIDE EQU 0x1E08
DB_BSTRIDE EQU 0x1E0A
DB_ROWS EQU 0x1E0C
DB_OP EQU 0x1E0D
DB_SLOT EQU 0x1E0E
DB_OWNED EQU 0x1E0F
DB_POLICY EQU 0x1E10
DB_ERROR EQU 0x1E11
DB_LEFT EQU 0x1E12
DB_BACKEND EQU 0x1E13
DB_ABUMP EQU 0x1E14
DB_BBUMP EQU 0x1E16
DB_CURRENT EQU 0x1F00
DB_PENDING EQU 0x1F08
        ASSERT $ < 0x0800
        ORG 0x0800
actor_blit:
        xor a
        ld (DB_ERROR),a
        ld a,(DB_POLICY)
        cp 3
        jp nc,blit_bad
        ld (hlib_dma_policy),a
        ld a,(DB_SRC_PAGE)
        cp 112
        jp c,blit_bad
        cp 116
        jr c,.source_ok
        cp 136
        jp c,blit_bad
        cp 224
        jp nc,blit_bad
.source_ok:
        ld a,(DB_OP)
        cp 1
        jp z,blit_sprite
        or a
        jp nz,blit_bad
        ld a,(DB_DST_PAGE)
        ld b,a
        ld a,(DB_SRC_PAGE)
        cp b
        jp z,blit_bad
        ld a,b
        cp 112
        jp c,blit_bad
        cp 116
        jr c,.dest_ok
        cp 118
        jp c,blit_bad
        cp 122
        jr c,.dest_ok
        cp 216
        jp c,blit_bad
        cp 224
        jp nc,blit_bad
.dest_ok:
        ld a,(DB_ROWS)
        dec a
        cp 16
        jp nc,blit_bad
        ld hl,(DB_WIDTH)
        ld a,h
        cp 2
        jp nc,blit_bad
        or a
        jr z,.small
        ld a,l
        or a
        jp nz,blit_bad
        jr .width_ok
.small:
        ld a,l
        or a
        jp z,blit_bad
.width_ok:
        ld bc,(DB_WIDTH)
        ld hl,(DB_SRC)
        ld de,(DB_ASTRIDE)
        call blit_extent
        ld hl,(DB_DST)
        ld de,(DB_BSTRIDE)
        call blit_extent
        ld hl,(DB_ASTRIDE)
        or a
        sbc hl,bc
        ld (DB_ABUMP),hl
        ld hl,(DB_BSTRIDE)
        or a
        sbc hl,bc
        ld (DB_BBUMP),hl
        ld a,(DB_ROWS)
        cp 1
        jr nz,.init_backend
        ld hl,(DB_WIDTH)
        ld a,h
        or a
        jr nz,.init_backend
        ld a,l
        cp 64
        jr nc,.init_backend
        ld a,(DB_SRC_PAGE)
        nextreg 0x51,a
        jr .cpu                ; tiny span: avoid DMA capability/setup overhead too
.init_backend:
        call blit_init
        ld a,(DB_BACKEND)
        cp 1
        jr nz,.backend_ready
        ld hl,(DB_WIDTH)
        ld a,h
        or a
        jr nz,.backend_ready
        ld a,l
        cp 64
        jr nc,.backend_ready
.cpu:
        xor a                  ; row-DMA setup costs more than these narrow CPU rows
        ld (DB_BACKEND),a
.backend_ready:
        ld a,(DB_BACKEND)
        cp 2
        jr nz,.mapped
        ld a,(DB_DST_PAGE)
        cp 216
        jr c,.mapped
        ld a,(DB_SRC_PAGE)
        cp 136
        jr c,.mapped
        jp blit_physical
.mapped:
        ld a,(DB_DST_PAGE)
        nextreg 0x52,a
        ld hl,(DB_SRC)
        set 5,h
        ld de,(DB_DST)
        set 6,d
        ld a,(DB_BACKEND)
        cp 2
        jr z,.ddma
        ld a,(DB_ROWS)
        ld (DB_LEFT),a
.row:
        ld a,(DB_BACKEND)
        or a
        jr nz,.dma_row
        ld bc,(DB_WIDTH)
        ldir
        ld bc,(DB_ABUMP)
        add hl,bc
        ex de,hl
        ld bc,(DB_BBUMP)
        add hl,bc
        ex de,hl
        jr .next
.dma_row:
        ld (hlib_dma_row_src),hl
        ld (hlib_dma_row_dst),de
        push hl
        ld hl,(DB_WIDTH)
        ld (hlib_dma_row_len),hl
        ld hl,hlib_dma_row
        push de
        ld bc,(hlib_dma_row_end-hlib_dma_row)*256+0x6B
        otir
        pop de
        pop hl
        ld bc,(DB_ASTRIDE)
        add hl,bc
        ex de,hl
        ld bc,(DB_BSTRIDE)
        add hl,bc
        ex de,hl
.next:
        ld a,(DB_LEFT)
        dec a
        ld (DB_LEFT),a
        jr nz,.row
        jp blit_restore
.ddma:
        ld (hlib_dma_rect_src),hl
        ld (hlib_dma_rect_dst),de
        ld hl,(DB_WIDTH)
        ld (hlib_dma_rect_width),hl
        ld hl,(DB_ASTRIDE)
        ld (hlib_dma_rect_astride),hl
        ld hl,(DB_BSTRIDE)
        ld (hlib_dma_rect_bstride),hl
        ld a,(DB_ROWS)
        ld l,a
        ld h,0
        ld (hlib_dma_rect_rows),hl
        ld hl,hlib_dma_rect_prog
        ld bc,(hlib_dma_rect_end-hlib_dma_rect_prog)*256+0x6B
        otir
        jp blit_restore
blit_sprite:
        ld hl,(DB_SRC)
        ld a,h
        and 0xE0
        jp nz,blit_bad
        ld de,256
        add hl,de
        ld de,0x2001
        or a
        sbc hl,de
        jp nc,blit_bad
        ld a,(DB_SLOT)
        cp 64
        jp nc,blit_bad
        ld c,a
        and 7
        ld b,a
        ld a,1
        jr z,.mask
.shift:
        add a,a
        djnz .shift
.mask:
        ld b,a
        ld a,c
        rrca
        rrca
        rrca
        and 7
        ld l,a
        ld h,DB_CURRENT/256
        ld a,(hl)
        set 3,l
        or (hl)
        and b
        jp nz,blit_bad
        call blit_init
        ld a,(DB_SLOT)
        ld bc,0x303B
        out (c),a
        ld hl,(DB_SRC)
        set 5,h
        call hlib_dma_sprite
        jp blit_restore
blit_init:
        ld a,(DB_SRC_PAGE)
        nextreg 0x51,a
        ld a,(DB_OWNED)
        call hlib_dma_init
        call hlib_dma_backend
        ld (DB_BACKEND),a
        ret
blit_extent:
        ld a,h
        and 0xE0
        jp nz,blit_bad
        push hl
        ld h,d
        ld l,e
        or a
        sbc hl,bc
        pop hl
        jp c,blit_bad
        ld a,(DB_ROWS)
        dec a
        jr z,.end
.add:
        add hl,de
        jp c,blit_bad
        dec a
        jr nz,.add
.end:
        add hl,bc
        jp c,blit_bad
        ld de,0x2001
        or a
        sbc hl,de
        jp nc,blit_bad
        ret
blit_bad:
        ld a,1
        ld (DB_ERROR),a
        ld sp,0x1FF0
blit_restore:
        nextreg 0x51,68
        nextreg 0x52,10
        ret
 ; Physical SRAM = 040000 + 8K page * 2000. High staging only, no BRAM alias.
blit_physical:
        ld a,(DB_SRC_PAGE)
        ld hl,(DB_SRC)
        call blit_address
        ld (blit_phys_src),hl
        ld (blit_phys_ahi),a
        ld a,(DB_DST_PAGE)
        ld hl,(DB_DST)
        call blit_address
        ld (blit_phys_dst),hl
        ld (blit_phys_bhi),a
        ld hl,(DB_WIDTH)
        ld (blit_phys_width),hl
        ld hl,(DB_ASTRIDE)
        ld (blit_phys_astride),hl
        ld hl,(DB_BSTRIDE)
        ld (blit_phys_bstride),hl
        ld a,(DB_ROWS)
        ld l,a
        ld h,0
        ld (blit_phys_rows),hl
        ld hl,blit_phys_packet
        ld bc,(blit_phys_end-blit_phys_packet)*256+0x6B
        otir
        jp blit_restore
blit_address:
        ld d,a
        and 7
        rrca
        rrca
        rrca
        or h
        ld h,a
        ld a,d
        rrca
        rrca
        rrca
        and 31
        add a,4
        ret
blit_phys_packet:
        db 0x83,0xC3,0x7D
blit_phys_src: dw 0
        dw 0
        db 0x14,0x10,0xAD
blit_phys_dst: dw 0
        db 0x82,0xD7
blit_phys_ahi: db 0
        db 0xDB
blit_phys_bhi: db 0
        db 0xDF,3,0xE3
blit_phys_width: dw 0
        db 0xE7
blit_phys_rows: dw 0
        db 0xEB
blit_phys_astride: dw 0
        db 0xEF
blit_phys_bstride: dw 0
        db 0xCF,0x87
blit_phys_end:
actor_blit_end:
        ASSERT actor_blit_end < 0x1D00
        SAVEBIN "inferno_blit.bin",hlib_dma_policy,actor_blit_end-hlib_dma_policy

; Private page 78, snapshot page 122. Standalone DI/28MHz component, no game hook.
; Stream: original header; repeated width,dx,dy,(tile ID,bitmap[8],attribute)*width; zero.
; OP 0 captures only when unowned, OP 1 releases, OP 2 compares all live bytes.
; A successful capture pins page 122 until release. Validation never writes pinned data.
; Invalid/overflow captures leave DONE=0, ACTIVE=0; never publish a partial stream.
        ORG 0
J_OP    EQU 0x1E80
J_IMAGE EQU 0x1E81
J_FLASH EQU 0x1E82
J_PAINT EQU 0x1E83
J_ACTIVE EQU 0x1E85
J_DONE  EQU 0x1E86
J_ERROR EQU 0x1E87
J_MATCH EQU 0x1E88
J_SIZE  EQU 0x1E89
J_PHASE EQU 0x1E8B
J_GEN   EQU 0x1E8C
J_SP    EQU 0x1E8E
J_PAGE  EQU 0x1E90
J_ROWS  EQU 0x1E91
J_LEFT  EQU 0x1E92
job_snapshot:
        ld (J_SP),sp
        xor a
        ld (J_ERROR),a
        ld (J_MATCH),a
        ld a,(J_OP)
        cp 1
        jp z,job_release
        cp 3
        jp nc,job_reject
        ld a,(J_FLASH)
        cp 2
        jp nc,job_reject
        ld a,(J_OP)
        or a
        jr nz,job_validate
        ld a,(J_ACTIVE)
        or a
        jp nz,job_reject
        ld a,1
        ld (J_ACTIVE),a
        xor a
        ld (J_DONE),a
        ld (J_SIZE),a
        ld (J_SIZE+1),a
        ld a,(J_FLASH)
        ld (J_PHASE),a
        ld hl,(J_PAINT)
        ld (J_GEN),hl
        jr job_walk
job_validate:
        ld a,(J_ACTIVE)
        cp 1
        jp nz,job_reject
        ld a,(J_DONE)
        cp 1
        jp nz,job_reject
        ld a,(J_FLASH)
        ld hl,J_PHASE
        cp (hl)
        jp nz,job_return
        ld hl,(J_PAINT)
        ld de,(J_GEN)
        or a
        sbc hl,de
        jp nz,job_return
job_walk:
        nextreg 0x51,122
        ld a,(J_IMAGE)
        ld l,a
        ld h,0xC1
        ld c,(hl)
        inc l                   ; original C1FF -> C100 pointer wrap
        ld b,(hl)
        ld h,b
        ld l,c
        ld a,h
        cp 0x40
        jp c,job_bad
        ld de,0x2000
        ld a,(hl)
        call job_emit
        and 3
        ld (J_PAGE),a
        inc hl
        ld a,0
        ld (J_ROWS),a           ; 256 bounded row attempts, including terminator
job_row:
        call job_address
        ld a,(hl)
        inc hl
        call job_emit
        or a
        jp z,job_complete
        cp 129
        jp nc,job_bad
        ld (J_LEFT),a
        call job_address
        ld a,(hl)
        inc hl
        call job_emit
        call job_address
        ld a,(hl)
        inc hl
        call job_emit
job_tile:
        call job_address
        ld a,(hl)
        inc hl
        call job_emit
        push hl
        ld l,a
        ld a,(J_PAGE)
        ld h,a
        push hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,0xDC00
        add hl,bc
        ld b,8
job_bitmap:
        ld a,(hl)
        inc hl
        call job_emit
        djnz job_bitmap
        pop hl
        ld bc,0xFC00
        add hl,bc
        ld a,(hl)
        call job_emit
        pop hl
        ld a,(J_LEFT)
        dec a
        ld (J_LEFT),a
        jr nz,job_tile
        ld a,(J_ROWS)
        dec a
        ld (J_ROWS),a
        jp nz,job_row
        jp job_bad
job_address:
        ld a,h
        cp 0x40                ; also refuses original record wrap to 0000
        ret nc
        jp job_bad
job_emit:
        push af
        ld a,d
        cp 0x40
        jp nc,job_bad
        ld a,(J_OP)
        or a
        jr nz,job_compare
        pop af
        ld (de),a
        inc de
        ret
job_compare:
        pop af
        push af
        ex de,hl
        cp (hl)
        ex de,hl
        jp nz,job_miss
        pop af
        inc de
        ret
job_complete:
        ex de,hl
        ld de,0x2000
        or a
        sbc hl,de
        ld a,(J_OP)
        or a
        jr nz,job_compare_size
        ld (J_SIZE),hl
        ld a,1
        ld (J_DONE),a
        jp job_return
job_compare_size:
        ld de,(J_SIZE)
        or a
        sbc hl,de
        jp nz,job_miss
        ld a,1
        ld (J_MATCH),a
        jp job_return
job_reject:
        ld a,1
        ld (J_ERROR),a
        jp job_return
job_bad:
        ld a,1
        ld (J_ERROR),a
job_miss:
        ld a,(J_OP)
        or a
        jr nz,job_return
job_release:
        xor a
        ld (J_ACTIVE),a
        ld (J_DONE),a
job_return:
        nextreg 0x51,68
        ld sp,(J_SP)           ; abort may unwind an emit/bitmap call
        ret
job_snapshot_end:
        ASSERT job_snapshot_end < 0x1D00
        SAVEBIN "inferno_job.bin",job_snapshot,job_snapshot_end-job_snapshot
