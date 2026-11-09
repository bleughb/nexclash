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
        jr c,.have
        ld a,c                ; past the last block: the tape rewinds (the game finds its block by name)
        or a
        jr z,.eof
        xor a
.have:  ld l,a
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
; Copier-window milestone 3: each hook measures the time it adds on CTC channel 3 (sync to an
; edge at entry, run to the next edge at exit, then a constant path to the target) and writes it
; to page-80 CW_X (8F7C sets, 959B/96A1 add). R is restored (entry R + per-hook M1 constant).
; Frame IRQs: the hooks are DI (page 68 at slot 0); NextReg $C8 bit 0 is cleared at entry and read
; at exit: a pulse that came and went is lost, so the hook adds the original's no-op ISR (R + 10,
; X - 94). A game ISR taken on the site's JP (before DI) left the hook's address below the game
; SP: X - 94 (that ISR is the original's too).
CAP_SP      EQU 0x03F0
CAP_PTR     EQU 0x03F2
CAP_COUNT   EQU 0x03F4
CAP_OVER    EQU 0x03F5
CAP_PHASE   EQU 0x03F6
CAP_MODE    EQU 0x03F7
CAP_MAP     EQU 0x0400
CAP_LOG     EQU 0x0900
CAP_STACK   EQU 0x1FF0
CAP_K_SCENE   EQU 170           ; T: entry + exit constant path - CALL 9535 (17) (calibrated)
CAP_K_NORMAL  EQU 174           ; T: ... - LD L,(IX+4) (19) (calibrated)
CAP_K_WRAPPED EQU 174
CAP_KR_SCENE   EQU 96            ; R: original M1 to the target - hook M1 (calibrated)
CAP_KR_NORMAL  EQU 97
CAP_KR_WRAPPED EQU 97
CAP_KLOST   EQU -94-CW_KSPIN*0x26+54   ; T: X - 94 + KSPIN per /INT wait loop (E starts at 0x25) + the path (calibrated)
CAP_KLR     EQU 10+9            ; R: the ISR's 10 + the fast path's M1 after its LD R,A (calibrated)

        ORG 0x3960                ; NOT lower: the stub writes its 20-byte register block at rom_end
cap_chk:                        ; last check before the exit: NextReg $C8 (selected by cw_tout), A only
        ld a,0x24+1
        in a,(0x3B)
        rrca
        ret nc                  ; no /INT pulse since the hook's entry
cap_lost:                       ; a pulse came while DI: it is lost. The original's no-op ISR: R + 10,
        push hl                 ; X - 94 (+ the wait for /INT to drop + this path). HL DE BC are the game's
        push de
        push bc
        ld bc,0x243B
        ld a,0x22
        out (c),a
        inc b
        ld e,b
.int:   inc e
        in a,(c)
        jp m,.int
        ld d,CW_KSPIN
        mul d,e
        add de,CAP_KLOST
        nextreg 0x50,CW_PAGE
        ld hl,(CW_X)
        add hl,de
        ld (CW_X),hl
        ld a,(CW_HRN)
        ld d,a
        add a,CAP_KLR
        xor d
        and 0x7F
        xor d
        nextreg 0x50,68
        pop bc
        pop de
        pop hl
        ld r,a
        ret

cap_done:
        di
        nextreg 0x07,3
        nextreg 0xC8,1          ; clear "ULA interrupt seen": the window's entry reads it (cw_synced)
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        push hl
        ld a,(CAP_PHASE)
        cp 1
        jr nz,.keep
        ld a,(CAP_OVER)
        or a
        jr nz,.invalid
        ld a,2
        jr .set_phase
.invalid:
        xor a
        nop
.set_phase:
        ld (CAP_PHASE),a
        jr .phase_done
.keep:                          ; as many M1 as the phase-1 paths: the window reads R at a fixed offset
        DUP 7
        nop
        EDUP
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
cap_done_tail:                  ; copier-window builds replace these 12 bytes by JP cw_go
        nextreg 0x50,255
        nextreg 0x07,0
        ei
        jp 0x9790
cap_lo_end:
        ASSERT cap_lo_end <= 0x3A00
        ASSERT cap_chk >= rom_end + 20  ; z80tonex.build_tail: BC' DE' HL' AF' IX IY BC DE HL AF at rom_end
        SAVEBIN "inferno_caplo.bin",cap_chk,cap_lo_end-cap_chk


        ORG 0x3A00
cap_scene:
        di
        nextreg 0x07,3
        nextreg 0xC8,1          ; clear "ULA interrupt seen" (a pulse still active keeps it set)
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        ld a,r
        push bc
        push de
        push hl
        call cap_in
        ld hl,cap_dma           ; 9B00..9F7F -> CAP_MAP by zxnDMA (port 6B, every core): about
        ld bc,(cap_dma_end-cap_dma)*256+0x6B    ; 0.75 k T against 2.9 k T for 1152 LDI
        otir
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
        ld hl,CAP_K_SCENE
        ld a,CAP_KR_SCENE
        ld e,0
        call cap_out
        ld r,a
        pop hl
        pop de
        nop                     ; as many M1 as the actors' LD L,(IX+4): one cap_lost R constant
        nop
        pop bc
        call cap_chk
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        ei                      ; an IRQ is taken after the speed switch (game ISR at 3.5MHz)
        nextreg 0x07,0
        jp 0x9535
cap_dma:                        ; disable, reset; A = 9B00, 0480 bytes; A memory +1; B memory +1; continuous,
        DB 0x83,0xC3,0x7D,0x00,0x9B,0x80,0x04,0x14,0x10,0xAD,low CAP_MAP,high CAP_MAP,0x82,0xCF,0x87
cap_dma_end:                    ; B = CAP_MAP (slot 0, page 68); stop at end; load; enable

cap_normal:
        di
        nextreg 0x07,3
        nextreg 0xC8,1
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        ld a,r
        push bc
        push de
        push hl
        call cap_in
        xor a
        jp cap_actor
cap_wrapped:
        di
        nextreg 0x07,3
        nextreg 0xC8,1
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        ld a,r
        push bc
        push de
        push hl
        call cap_in
        ld a,1
cap_actor:
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
        ld hl,CAP_K_NORMAL
        ld a,CAP_KR_NORMAL
        ld e,1
        call cap_out
        ld r,a
        pop hl
        pop de
        ld l,(ix+4)
        pop bc
        call cap_chk
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        ei
        nextreg 0x07,0
        jp 0x959E
cap_wrapped_out:
        ld hl,CAP_K_WRAPPED
        ld a,CAP_KR_WRAPPED
        ld e,1
        call cap_out
        ld r,a
        pop hl
        pop de
        ld l,(ix+4)
        pop bc
        call cap_chk
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        ei
        nextreg 0x07,0
        jp 0x96A4

cap_in:                         ; A = entry R; registers pushed (helper in page 80)
        ld b,a
        nextreg 0x50,CW_PAGE
        call cw_tin             ; its return address lands in page 80 (1FE0s, unused)
        nextreg 0x50,68
        ret
cap_out:                        ; HL = K (T), A = KR (R), E = 0 set X / 1 add -> A = R to restore
        nextreg 0x50,CW_PAGE
        call cw_tout
        nextreg 0x50,68
        ret
cap_end:
        ASSERT cap_end < 0x3B90
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

; Copier-window milestone 3b: the 8F95 work (prepare_frame + render_textmap, same results) as a
; coroutine in page 69 with its own stack, run in slices from cw_wait (cw_work -> wk_in -> wk_enter,
; DI, 28MHz, IYl = CTC count at which the slice ends); 8F95 (wk_hook -> wk_frame) restores R and
; drops work the window did not finish (3c: ready stays 0, nothing runs there).
; Poll points (clear loop, every map cell) read the CTC and yield when the count reaches IYl. The
; textmap loop uses SP as its map pointer: a yield saves SP, BC, DE, IX and the resume address
; (HL is dead at both poll points), never CALLs. The work never touches IY (bar IYl), AF' or the
; alternate set. In work builds 8F95 jumps to wk_hook (ROM), not frame_hook; nothing else changes.
WK_STACK  EQU 0x1C40            ; work stack (down to the display code end 1B19)
WK_HSTACK EQU 0x1C80            ; 8F95: the game's registers (below D_COLOURS)
WK_STATE  EQU 0x1EC0            ; 0 idle, 1 suspended, 2 done (this capture's work)
WK_M2     EQU 0x1EC2            ; slot-2 page of the suspended work (10 or 14)
WK_PC     EQU 0x1EC3
WK_SP     EQU 0x1EC5
WK_BC     EQU 0x1EC7
WK_DE     EQU 0x1EC9
WK_IX     EQU 0x1ECB
WK_GSP    EQU 0x1ECD            ; 8F95: the game's SP
WK_HR     EQU 0x1ECF            ; 8F95: R at entry
WK_RN     EQU 0x1ED0            ; 8F95: R to restore
WK_KR     EQU -24               ; R: 8F95 -> 8F98 original M1 - the hook's M1 around its LD A,R / LD R,A (calibrated)
        ORG 0x0C00
wk_enter:                       ; from wk_in: A = 2 first slice of this window (restart)
        cp 2
        jr z,wk_new
        ld a,(WK_STATE)
        cp 1
        jr z,wk_resume
        cp 2
        jr nz,wk_new
        ld l,a                  ; done already (cw_wkback stops the slices)
        jp wk_leave
wk_new:
        ld a,10
        ld (WK_M2),a
        ld sp,WK_STACK
        call wk_prepare
        call wk_dispatch
        nextreg 0x52,82         ; selection and store: code and tables in page 82 at slot 2
        ld a,82
        ld (WK_M2),a
        call wk_select
        ld a,2
        ld (WK_STATE),a
        ld l,a
        jp wk_leave
wk_resume:
        nextreg 0x51,68
        ld a,(WK_M2)
        nextreg 0x52,a
        ld bc,(WK_BC)
        ld de,(WK_DE)
        ld ix,(WK_IX)
        ld hl,(WK_PC)
        ld sp,(WK_SP)
        jp (hl)
wk_yield:                       ; HL = resume address; SP BC DE IX live
        ld (WK_PC),hl
        ld (WK_SP),sp
        ld (WK_BC),bc
        ld (WK_DE),de
        ld (WK_IX),ix
        ld a,1
        ld (WK_STATE),a
        ld l,a
wk_leave:                       ; L = state: original slot 1/2 mapping, then NextReg $C8 last
        nextreg 0x52,10
        nextreg 0x51,255
        ld bc,0x243B
        ld a,0xC8
        out (c),a
        inc b
        in a,(c)
        jp wk_out
wk_frame:                       ; from wk_hook: DI, 28MHz, $C8 cleared, all game registers
        ld (WK_GSP),sp
        ld sp,WK_HSTACK
        push af
        ld a,r
        ld (WK_HR),a
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
        ld a,(WK_STATE)         ; 3c: work not finished in the window is dropped, never finished here
        cp 2                    ; (it would eat this update's slack); the next window restarts on
        jr z,wk_fdone           ; the new capture and the display keeps its last complete frame
        xor a
        ld (F_SCENE_READY),a
        ld (Q_READY),a
        ld (DX_READY),a
wk_fdone:                       ; restore the game state; R last
        xor a
        ld (WK_STATE),a
        nextreg 0x52,10
        nextreg 0x51,255
        ld a,(WK_HR)
        ld b,a
        add a,WK_KR
        xor b
        and 0x7F
        xor b
        ld (WK_RN),a
        ld bc,0x243B            ; select NextReg $C8 for the read after the pops
        ld a,0xC8
        out (c),a
        ld sp,WK_HSTACK-20
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
        ld a,0x24+1
        in a,(0x3B)             ; NextReg $C8: a pulse came while DI (lost)
        rrca
        call c,wk_lost
        pop af
        ld a,(WK_RN)
        ld r,a
        ld sp,(WK_GSP)
        ld a,(0xAC49)           ; the displaced LD A,(44105)
        jp wk_hexit
wk_lost:                        ; the original's no-op ISR: R + 10 (after /INT drops). BC kept
        push bc
        ld bc,0x243B
        ld a,0x22
        out (c),a
        inc b
.int:   in a,(c)
        rlca
        jr c,.int
        ld a,(WK_RN)
        ld b,a
        add a,CW_ISR_M1
        xor b
        and 0x7F
        xor b
        ld (WK_RN),a
        pop bc
        ret

wk_prepare:                     ; prepare_frame's body as a subroutine on the work stack
        nextreg 0x51,68
        xor a
        ld (F_SCENE_READY),a
        ld (Q_READY),a
        ld a,(0x2000+CAP_PHASE)
        cp 2
        ret nz
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
        ret nz                  ; never rebuild memory still owned by a pending display
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
        call wk_textmap
        ld a,(T_ERROR)
        or a
        ret nz
        ld a,1
        ld (F_SCENE_READY),a
        ret

wk_textmap:                     ; render_textmap with poll points (same results)
        xor a
        ld (T_ERROR),a
        ld (T_COUNT),a
        ld (T_COUNT+1),a
        ld a,(T_HALF)
        cp 2
        jp nc,wk_tbad
        ld b,a
        ld a,(T_FRONT)
        cp b
        jp z,wk_tbad
        ld a,(T_FLASH)
        cp 2
        jp nc,wk_tbad
        ld (T_SP),sp
        ld sp,T_FLAGS+1024
        ld bc,0
        ld ixl,32
wk_clear:                       ; poll: yield when the count reaches IYl (live: SP, BC, IXl)
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        sub iyl
        dec a
        jp m,wk_yclear
wk_clear_go:
        DUP 16
        push bc
        EDUP
        dec ixl
        jr nz,wk_clear
        ld sp,(T_SP)
        ld a,(T_HALF)
        or a
        ld de,0x4000
        ld a,0x4C
        jr z,.half
        ld de,0x4600
        ld a,0x54
.half:  ld (T_DEFHI),a
        ld a,14
        ld (WK_M2),a
        nextreg 0x52,14         ; original screen page hidden only inside DI domain
        ld sp,T_MAP             ; POP reads the captured map
        ld ix,0x2012
wk_cell:                        ; poll (live: SP = map pointer, DE, IX)
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        sub iyl
        dec a
        jp m,wk_ycell
wk_cell_go:
        ASSERT wk_cell_go == wk_cell + 10 && wk_clear_go == wk_clear + 10
        pop bc
        ld a,b
        and 3
        add a,T_FLAGS/256
        ld h,a
        ld l,c
        ld a,(hl)
        or a
        jr z,.source
        add hl,hl
.pair:  ldi
        ldi
        dec ixh
        jr nz,wk_cell
        ld a,16
        add de,a
        ld ixh,32
        dec ixl
        jr nz,wk_cell
        ld sp,(T_SP)
        ld a,10
        ld (WK_M2),a
        nextreg 0x52,10
        ret
.source:
        ld (T_MAPSP),sp
        ld sp,(T_SP)
        push de
        push hl
        ld de,(T_COUNT)
        ld a,d
        or a
        jp nz,.full
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
        add a,0xF4
        ld h,a
        ld l,c
        ld a,(hl)
        ld l,a
        and 0x80
        jr z,.noinvert
        ld a,(T_FLASH)
        or a
        jr z,.noinvert
        push hl
        ld hl,(T_PATTERN)
        DUP 8
        ld a,(hl)
        cpl
        ld (hl),a
        inc l
        EDUP
        pop hl
.noinvert:
        ld h,4
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
        jp .pair
.full:
        pop bc
        pop de
        ld a,2
        ld (T_ERROR),a
        ld sp,(T_SP)
        ld a,10
        ld (WK_M2),a
        nextreg 0x52,10
        ret
wk_tbad:
        ld a,1
        ld (T_ERROR),a
        ret
wk_ycell:
        ld hl,wk_cell_go
        jp wk_yield
wk_yclear:
        ld hl,wk_clear_go
        jp wk_yield
wk_end:
        ASSERT wk_end <= 0x1000
        SAVEBIN "inferno_cwwork.bin",wk_enter,wk_end-wk_enter

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
F_WIDE EQU 0x1EAA              ; nonzero: G3, exterior enters black only through gaps at least 3x3
F_G_PAGE EQU 0x1EAB
F_G_OUT EQU 0x1EAC
F_G_POS EQU 0x1EAD
F_G_T EQU 0x1EAF
F_E_P EQU 0x1EB0
F_E_Q EQU 0x1EB2
F_E_STEP EQU 0x1EB4
F_E_LEFT EQU 0x1EB6
F_E_N EQU 0x1EB8
F_E_S EQU 0x1EBA
F_E_D EQU 0x1EBC
F_G_PREV EQU 0x1000
F_G_CUR EQU 0x1080
F_G_EDGE EQU 0x1100
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
        ld a,(F_WIDE)
        or a
        call nz,fill_wide_erode
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
        ld a,(F_WIDE)
        or a
        call nz,fill_wide_dilate
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
; G3 around the unchanged flood: 3x3 erosion of the passable bits (outside the canvas counts as clear), then
; 3x3 dilation of the exterior, then the canvas edge, where a 3x3 block may stand half outside. 0600-0BFF: tables.
        ORG 0x0C00
fill_wide_erode:
        ld a,116
        ld b,0xFF
        ld c,0xA6              ; AND (HL)
        jr fill_gate
fill_wide_dilate:
        ld a,117
        ld b,0
        ld c,0xB6              ; OR (HL)
        call fill_gate
        jp fill_edges
fill_gate:
        ld (F_G_PAGE),a
        ld a,b
        ld (F_G_OUT),a
        ld a,c
        ld (.v1),a
        ld (.h2),a
        ld (.v2+1),a
        and 0xF0
        or 1                   ; AND C / OR C
        ld (.h1),a
        ld hl,F_G_PREV
        ld de,F_G_PREV+1
        ld (hl),b
        ld bc,0x17F
        ldir                   ; PREV, CUR and the outside row
        ld hl,0
.row:   ld (F_G_POS),hl
        call fill_checkpoint
        ld a,(F_G_PAGE)
        nextreg 0x52,a
        ld hl,(F_G_POS)
        set 6,h
        push hl
        ld de,F_G_CUR
        ld bc,(F_MASK_STRIDE)
        ldir                   ; HL = the next row
        ex de,hl
        ld hl,(F_G_POS)
        ld bc,(F_MASK_STRIDE)
        add hl,bc
        ld bc,(F_MASK_SIZE)
        or a
        sbc hl,bc
        ex de,hl
        jr c,.has
        ld hl,F_G_EDGE
.has:   push hl
        pop iy
        pop de                 ; DE = this row
        push de
        ld ix,F_G_PREV
        ld hl,F_G_CUR
        ld a,(F_MASK_STRIDE)
        ld b,a
.v:     ld a,(ix+0)
.v1:    and (hl)
.v2:    and (iy+0)
        ld (de),a
        inc ix
        inc iy
        inc hl
        inc de
        djnz .v
        ld hl,F_G_CUR
        ld de,F_G_PREV
        ld bc,(F_MASK_STRIDE)
        ldir
        pop hl                 ; this row, again, across
        ld a,(F_MASK_STRIDE)
        ld b,a
        ld a,(F_G_OUT)
        ld d,a
.h:     ld c,(hl)
        ld a,b
        dec a
        ld a,(F_G_OUT)
        jr z,.last
        inc hl
        ld a,(hl)
        dec hl
.last:  ld e,a
        ld a,c
        add a,a
        bit 7,e
        jr z,.nr
        inc a
.nr:    ld (F_G_T),a
        ld a,c
        srl a
        bit 0,d
        jr z,.nl
        or 128
.nl:
.h1:    and c
        push hl
        ld hl,F_G_T
.h2:    and (hl)
        pop hl
        ld (hl),a
        ld d,c
        inc hl
        djnz .h
        ld hl,(F_G_POS)
        ld bc,(F_MASK_STRIDE)
        add hl,bc
        ld bc,(F_MASK_SIZE)
        or a
        sbc hl,bc
        ret z
        add hl,bc
        jp .row
; A black canvas-edge pixel is exterior when a run of three along that edge holds it; beyond the ends is clear.
fill_edges:
        ld hl,(F_MASK_STRIDE)
        add hl,hl
        add hl,hl
        add hl,hl
        ld (F_E_STEP),hl       ; pixels per row
        ld bc,0
        ld hl,(F_MASK_SIZE)
        ld de,(F_MASK_STRIDE)
.rows:  inc bc
        or a
        sbc hl,de
        jr nz,.rows
        push bc                ; height
        ld hl,0
        ld de,(F_E_STEP)
        call fill_edge         ; left column
        pop bc
        push bc
        ld hl,(F_E_STEP)
        dec hl
        ld de,(F_E_STEP)
        call fill_edge         ; right column
        ld hl,(F_E_STEP)
        ld b,h
        ld c,l
        ld hl,0
        ld de,1
        push bc
        call fill_edge         ; top row
        pop bc
        pop de                 ; height
        push bc
        dec de
        ld hl,0
.mul:   ld a,d
        or e
        jr z,.got
        ld bc,(F_E_STEP)
        add hl,bc
        dec de
        jr .mul
.got:   pop bc
        ld de,1
        ; bottom row, then return
fill_edge:                      ; HL first pixel, DE step, BC count
        ld (F_E_P),hl
        ld (F_E_Q),hl
        ld (F_E_D),de
        ld (F_E_LEFT),bc
        ld (F_E_N),bc
        ld a,3
        ld (F_E_S),a
        call .feed
        call .feed
.y:     call fill_checkpoint
        call .feed
        ld a,(F_E_S)
        bit 2,a
        jr z,.next
        ld b,a
        and 0x1C
        cp 0x1C
        jr z,.set
        ld a,b
        and 0x0E
        cp 0x0E
        jr z,.set
        ld a,b
        and 7
        cp 7
        jr nz,.next
.set:   nextreg 0x52,117
        ld hl,(F_E_P)
        ld a,l
        and 7
        ld b,a
        inc b
        ld a,1
.bit:   rrca
        djnz .bit
        ld c,a
        ld b,3
.sh:    srl h
        rr l
        djnz .sh
        set 6,h
        ld a,(hl)
        or c
        ld (hl),a
.next:  ld hl,(F_E_P)
        ld de,(F_E_D)
        add hl,de
        ld (F_E_P),hl
        ld hl,(F_E_N)
        dec hl
        ld (F_E_N),hl
        ld a,h
        or l
        jr nz,.y
        ret
.feed:  ld hl,(F_E_LEFT)
        ld a,h
        or l
        ld a,1
        jr z,.push
        dec hl
        ld (F_E_LEFT),hl
        ld hl,(F_E_Q)
        push hl
        ld de,(F_E_D)
        add hl,de
        ld (F_E_Q),hl
        pop hl
        srl h
        rr l                   ; carry: right pixel of the byte
        push af
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,112
        nextreg 0x51,a
        ld a,h
        and 31
        or 0x20
        ld h,a
        pop af
        ld a,(hl)
        jr c,.low
        rrca
        rrca
        rrca
        rrca
.low:   and 15
        ld a,0
        jr nz,.push
        inc a
.push:  ld b,a
        ld a,(F_E_S)
        add a,a
        or b
        and 31
        ld (F_E_S),a
        ret
fill_wide_end:
        ASSERT fill_wide_end < 0x1000
        SAVEBIN "inferno_fill.bin",fill_actor_image,fill_wide_end-fill_actor_image

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
J_BANK  EQU 0x1E93
J_BASE  EQU 0x1E94
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
        jp job_exact_walk
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
        push hl
        ld hl,7
        add hl,de
        ld a,h
        cp 0x40
        jp nc,job_bad          ; whole bitmap span must fit the pinned page
        pop hl
        ld a,(J_OP)
        or a
        jr nz,job_bitmap_compare
        DUP 8
        ldi
        EDUP
        jr job_bitmap_done
job_bitmap_compare:
        DUP 8
        ld a,(de)
        cp (hl)
        jp nz,job_miss
        inc de
        inc hl
        EDUP
job_bitmap_done:
        pop hl
        ld bc,0xFC00
        add hl,bc
        ld a,(hl)
        call job_emit
        pop hl
        ld a,(J_LEFT)
        dec a
        ld (J_LEFT),a
        jp nz,job_tile
        ld a,(J_ROWS)
        dec a
        ld (J_ROWS),a
        jp nz,job_row
        jp job_bad
; Exact-hit walker: inline byte comparisons; capture retains its original path.
; Header/width are bounded individually; each nonempty row bounds its complete
; live record and serialized payload before any unchecked row-byte comparison.
        MACRO JOB_EXACT_BYTE
        ld c,a
        ld a,d
        cp 0x40
        jp nc,job_bad
        ld a,(de)
        cp c
        jp nz,job_miss
        ld a,c
        inc de
        ENDM
        MACRO JOB_EXACT_ROW_BYTE
        ld c,a
        ld a,(de)
        cp c
        jp nz,job_miss
        ld a,c
        inc de
        ENDM
job_exact_walk:
        ld a,(J_BANK)
        nextreg 0x51,a
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
        ld de,(J_BASE)
        ld a,(hl)
        JOB_EXACT_BYTE
        and 3
        ld (J_PAGE),a
        inc hl
        ld a,0
        ld (J_ROWS),a           ; 256 bounded row attempts, including terminator
job_exact_row:
        call job_address
        ld a,(hl)
        inc hl
        JOB_EXACT_BYTE
        or a
        jp z,job_complete
        cp 129
        jp nc,job_bad
        ld (J_LEFT),a
        ; Stream row remainder: dx,dy plus width * (ID,bitmap[8],attribute).
        ; Check its last byte, so an exact page-end payload remains legal.
        push hl
        push de
        ld e,a
        ld d,10
        mul d,e
        ld hl,1
        add hl,de
        pop de
        add hl,de
        ld a,h
        cp 0x40
        jp nc,job_bad
        pop hl
        ; Live remainder: dx,dy and width IDs; reject wrap before reading it.
        push de
        ld a,(J_LEFT)
        ld e,a
        ld d,0
        inc de
        ex de,hl
        add hl,de
        jp c,job_bad
        ld a,h
        cp 0x40
        jp c,job_bad
        ex de,hl
        pop de
        ld a,(hl)
        inc hl
        JOB_EXACT_ROW_BYTE
        ld a,(hl)
        inc hl
        JOB_EXACT_ROW_BYTE
job_exact_tile:
        ld a,(hl)
        inc hl
        JOB_EXACT_ROW_BYTE
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
job_exact_bitmap:
        DUP 8
        ld a,(de)
        cp (hl)
        jp nz,job_miss
        inc de
        inc hl
        EDUP
job_exact_bitmap_done:
        pop hl
        ld bc,0xFC00
        add hl,bc
        ld a,(hl)
        JOB_EXACT_ROW_BYTE
        pop hl
        ld a,(J_LEFT)
        dec a
        ld (J_LEFT),a
        jp nz,job_exact_tile
        ld a,(J_ROWS)
        dec a
        ld (J_ROWS),a
        jp nz,job_exact_row
        jp job_bad
job_address:
        ld a,h
        cp 0x40                ; also refuses original record wrap to 0000
        ret nc
        jp job_bad
job_emit:
        ld c,a                 ; parser keeps run counters in private state, BC is scratch
        ld a,d
        cp 0x40
        jp nc,job_bad
        ld a,(J_OP)
        or a
        jr nz,job_compare
        ld a,c
        ld (de),a
        inc de
        ret
job_compare:
        ld a,(de)
        cp c
        jp nz,job_miss
        ld a,c
        inc de
        ret
job_complete:
        ex de,hl
        ld de,0x2000
        ld a,(J_OP)
        or a
        jr z,.base_ready
        ld de,(J_BASE)
.base_ready:
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

; Owned loading store, page 79. DI/28MHz private worker, NOT a game entry wrapper.
; 256 immutable image slots, append-only pages 136..215; 216..223 never borrowed.
; OP 0 reset (only with no current/pending owners), 1 insert, 2 dispatch.
; Source page 122 and canvas pages 112..115 are complete private worker results.
; Entry: valid, source page, offset16, length16, canvas page, offset16,
; length16, FLASH, paint16, reserved16. Valid published last; never enables display.
        ORG 0
C_OP EQU 0x1E80
C_IMAGE EQU 0x1E81
C_FLASH EQU 0x1E82
C_PAINT EQU 0x1E83
C_SOURCE_SIZE EQU 0x1E85
C_CANVAS_SIZE EQU 0x1E87
C_CURRENT EQU 0x1E89
C_PENDING EQU 0x1E8A
C_ERROR EQU 0x1E8B
C_FOUND EQU 0x1E8C
C_PAGE EQU 0x1E8D
C_OFFSET EQU 0x1E8E
C_ENTRY EQU 0x1E90
C_SP EQU 0x1E92
C_SRC_PAGE EQU 0x1E94
C_SRC_OFFSET EQU 0x1E95
C_CAN_PAGE EQU 0x1E97
C_CAN_OFFSET EQU 0x1E98
C_END_PAGE EQU 0x1E9A
C_END_OFFSET EQU 0x1E9B
cache_owned:
        ld (C_SP),sp
        xor a
        ld (C_ERROR),a
        ld (C_FOUND),a
        ld a,(C_OP)
        or a
        jp z,cache_reset
        cp 3
        jp nc,cache_error
        ld a,(C_IMAGE)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x0800
        add hl,de
        ld (C_ENTRY),hl
        ld a,(C_OP)
        cp 2
        jp z,cache_lookup
        ld a,(hl)
        or a
        jp nz,cache_error       ; no overwrite, including currently owned entries
        ld hl,(C_SOURCE_SIZE)
        ld a,h
        or l
        jp z,cache_error
        ld de,8193
        or a
        sbc hl,de
        jp nc,cache_error
        ld hl,(C_CANVAS_SIZE)
        ld de,32769
        or a
        sbc hl,de
        jp nc,cache_error
        ld a,(C_FLASH)
        cp 2
        jp nc,cache_error
        ld a,(C_PAGE)
        cp 136
        jp c,cache_error
        cp 216
        jp nc,cache_error
        ld hl,(C_OFFSET)
        ld a,h
        cp 32
        jp nc,cache_error
        ld de,(C_SOURCE_SIZE)
        add hl,de
        ld de,8193
        or a
        sbc hl,de
        ld a,(C_PAGE)
        ld hl,(C_OFFSET)
        jr c,.aligned
        inc a
        ld hl,0
.aligned:
        ld (C_SRC_PAGE),a
        ld (C_SRC_OFFSET),hl
        ld de,(C_SOURCE_SIZE)
        call cache_advance
        ld (C_CAN_PAGE),a
        ld (C_CAN_OFFSET),hl
        ld de,(C_CANVAS_SIZE)
        call cache_advance
        cp 216
        jp c,.fits
        jp nz,cache_error
        ld b,a
        ld a,h
        or l
        jp nz,cache_error
        ld a,b
.fits:  ld (C_END_PAGE),a
        ld (C_END_OFFSET),hl
        ; Copy complete source into one high page, keeping live graphics mapped.
        ld a,(C_SRC_PAGE)
        nextreg 0x52,a
        nextreg 0x51,122
        ld de,(C_SRC_OFFSET)
        ld hl,0x4000
        add hl,de
        ex de,hl
        ld hl,0x2000
        ld bc,(C_SOURCE_SIZE)
        ldir
        ; Canvas byte loop is deliberately loading-only; handles both page edges.
        ld bc,(C_CANVAS_SIZE)
        ld a,b
        or c
        jr z,.copied
        ld a,(C_CAN_PAGE)
        nextreg 0x52,a
        ld a,(C_CAN_OFFSET+1)
        add a,0x40
        ld d,a
        ld a,(C_CAN_OFFSET)
        ld e,a
        nextreg 0x51,112
        ld hl,0x2000
        exx
        ld b,112
        ld a,(C_CAN_PAGE)
        ld c,a
        exx
.copy:  ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld a,h
        cp 0x40
        jr nz,.src_ok
        ld h,0x20
        exx
        inc b
        ld a,b
        cp 116
        jr z,.last_source
        nextreg 0x51,a
.last_source:
        exx
.src_ok:
        ld a,d
        cp 0x60
        jr nz,.dst_ok
        ld d,0x40
        exx
        inc c
        ld a,c
        ; A final byte at the very end must not map reserved staging page 216.
        cp 216
        jr z,.last_page
        nextreg 0x52,a
.last_page:
        exx
.dst_ok:
        dec bc
        ld a,b
        or c
        jr nz,.copy
.copied:
        ld hl,(C_ENTRY)
        inc hl
        ld a,(C_SRC_PAGE)
        ld (hl),a
        inc hl
        ld de,(C_SRC_OFFSET)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(C_SOURCE_SIZE)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(C_CAN_PAGE)
        ld (hl),a
        inc hl
        ld de,(C_CAN_OFFSET)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(C_CANVAS_SIZE)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(C_FLASH)
        ld (hl),a
        inc hl
        ld de,(C_PAINT)
        ld (hl),e
        inc hl
        ld (hl),d
        ld a,(C_END_PAGE)
        ld (C_PAGE),a
        ld hl,(C_END_OFFSET)
        ld (C_OFFSET),hl
        ld hl,(C_ENTRY)
        ld (hl),1             ; only publication point, after EVERY payload write
        jp cache_lookup
; A page, HL offset, DE length -> advanced A/HL, no memory writes.
cache_advance:
        add hl,de
.loop:  ld b,a
        ld a,h
        cp 32
        ld a,b
        ret c
.page:  ld de,8192
        or a
        sbc hl,de
        inc a
        jr .loop
cache_lookup:
        ld hl,(C_ENTRY)
        ld a,(hl)
        cp 1
        jp nz,cache_return
        ld de,11
        add hl,de
        ld a,(C_FLASH)
        cp (hl)
        jp nz,cache_return
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,(C_PAINT)
        or a
        sbc hl,de
        jp nz,cache_return
        ld a,1
        ld (C_FOUND),a         ; candidate only: exact live validation still REQUIRED
        jp cache_return
cache_reset:
        ld a,(C_CURRENT)
        ld hl,C_PENDING
        or (hl)
        jp nz,cache_error
        ld hl,0x0800
        ld de,16
        ld b,0
.clear: ld (hl),0
        add hl,de
        djnz .clear
        ld a,136
        ld (C_PAGE),a
        ld hl,0
        ld (C_OFFSET),hl
        jr cache_return
cache_error:
        ld a,1
        ld (C_ERROR),a
cache_return:
        nextreg 0x51,68
        nextreg 0x52,10
        ld sp,(C_SP)
        ret
cache_owned_end:
        ASSERT cache_owned_end < 0x0800
        SAVEBIN "inferno_owned.bin",cache_owned,cache_owned_end-cache_owned

; Initialization pause/resume gate. Original 8EF8 DI has already executed;
; IM1 remains in force until the unchanged game establishes IM2 at 8F35.
; No CALL/push touches the original stack. A worker may run only in DI and
; must return with slot 0 = 68, slots 1/2 restored and I/IM unchanged.
        INCLUDE "lib/hlib_speed.asm"
        ORG 0x3C40
P_SP EQU 0x1D00
P_R EQU 0x1D02
P_SPEED EQU 0x1D03
pause_loading:
        nextreg 0x50,68
        ld (P_SP),sp
        ld sp,0x1EF0
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        exx
        push bc
        push de
        push hl
        exx
        ex af,af'
        push af
        ex af,af'
        ld a,r
        ld (P_R),a
        HLIB_SPEED_IN_ABC P_SPEED
pause_service:
        call 0x1D80
        HLIB_SPEED_OUT_A P_SPEED
        ld a,(P_R)
        ld b,a
        add a,83                ; original M1 minus entry/save and restore/exit M1, mod 128
        and 0x7F
        ld c,a
        ld a,b
        and 0x80
        or c
        ld r,a
        ex af,af'
        pop af
        ex af,af'
        exx
        pop hl
        pop de
        pop bc
        exx
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(P_SP)
        nextreg 0x50,255
        ld (0x9198),a           ; displaced original instruction, after state restoration
        jp 0x8EFC
pause_loading_end:
        ASSERT pause_loading_end < 0x3D00
        SAVEBIN "inferno_pause.bin",pause_loading,pause_loading_end-pause_loading

; ---------------------------------------------------------------------------
; Copier window (claude/inferno-copier-window). The original copier 9790 plays the A700 beeper
; buffer with one OUT (254),A per cell and calls the 9907 limiter from inside itself after row 6
; (97FB). cw_head replays 9790..97FB instruction for instruction (same RAM writes, work-stack
; pushes and PUSH AF flags) at 28MHz (milestone 1). Original T of the OUT of cell k = 244 + 120r
; + 187k + 19[k>255] + 101g(k) after 9790 entry (g = tiles >= 16 before k); head = 79477 + 101G.
; Milestone 2: each change of the OUT value is OUT at its original T and 9907 is entered at its
; original time, polled on CTC channel 3 (prescaler 256: 32 T a tick in every video timing; no
; interrupt). Time base: the first CTC edge after entry (= tick 1024), timed by counting the sync
; loop. Row base RBT:RBF (ticks, T) = 32768 + T of the current row's first OUT after that edge
; (CW_KRB calibrated, less CW_X = time earlier hooks added this update: 0 in the milestone-2
; build). A change the head reaches late is OUT at once; cell 415's is OUT after the row end and
; epilogue (the original's 169 T from it to 9907 is too short for them). The window runs EI:
; page 80 byte 0 is the offset of the IM2 JR at FFFF, so a frame IRQ enters cw_irq, which adds
; the original's no-op ISR (998E = 0 for the whole window) T to the deadlines and M1 to R. Calls
; and IRQ pushes leave bytes only below the copier's SP, in the 4 that 9907 overwrites first
; (PUSH DE / PUSH HL). No CTC (CW_CLK = 2): the original copier at original speed.
CW_PAGE   EQU 80
CW_ROWC   EQU 0x1700            ; 13 row counts, 256-aligned (self-modified low byte)
CW_SP     EQU 0x1800
CW_R      EQU 0x1802
CW_IY     EQU 0x1803
CW_PREV   EQU 0x1805            ; last OUT value (IY points here in the head)
CW_WSP    EQU 0x1807
CW_RSUM   EQU 0x180B
CW_CLK    EQU 0x1810            ; 0 untested, 1 CTC counts, 2 absent
CW_X      EQU 0x1811            ; T added by earlier hooks this update (accumulate-X input)
CW_CCD    EQU 0x1813            ; CTC count after the time-base edge
CW_NOW    EQU 0x1814            ; 1024 + ticks since the time-base edge
CW_LAST   EQU 0x1816            ; CTC count at the last CW_NOW update
CW_RBT    EQU 0x1817            ; row base, whole ticks
CW_RBF    EQU 0x1819            ; row base, T within the tick (0..31)
CW_IRQT   EQU 0x181A            ; T of the original's no-op ISRs inside the window so far
CW_RIRQ   EQU 0x181C            ; their M1 (R)
CW_NIRQ   EQU 0x181D
CW_SVHL   EQU 0x181E
CW_SVDE   EQU 0x1820
CW_SVBC   EQU 0x1822
CW_DL     EQU 0x1824            ; current wait: T above CW_DBASE ticks, +16 rounding, no CW_IRQT
CW_DBASE  EQU 0x1826
CW_DTK    EQU 0x1828            ; current wait: deadline, ticks
CW_IRQSP  EQU 0x182A
CW_DNIRQ  EQU 0x182D
CW_RS     EQU 0x182E            ; R low bits before the window's IRQs
CW_RH     EQU 0x182F            ; entry R bit 7
CW_PEND   EQU 0x1830            ; 1: cell 415 changed; OUT after the epilogue
CW_PC     EQU 0x1831            ; its c (tiles >= 16 before it in row 6)
CW_PADL   EQU 0x1832            ; pad target: T above CW_PADB ticks, +16 rounding
CW_PADB   EQU 0x1834
CW_IRQRAW EQU 0x1836            ; CTC count when the last IRQ came
CW_HR     EQU 0x1840            ; capture-hook timing: entry R
CW_HC0    EQU 0x1841            ; CTC count after the entry edge
CW_HN0    EQU 0x1842            ; sync loops left at the entry edge
CW_HCLK   EQU 0x1844            ; 1: CTC counts
CW_HRN    EQU 0x1845            ; R to restore
CW_HXT    EQU 0x1846            ; 0: set X (8F7C), 1: add
CW_KSPIN  EQU 4                 ; T per /INT wait loop (INC E / IN A,(C) / JP M) at 28MHz
CW_KH8    EQU 28                ; 8 x T per cw_edge check (calibrated)
CW_KT     EQU 0x1847            ; signed T: a speed-switch pair on this machine less the model's (cw_cal)
CW_KTPAIR EQU 46                ; the model's charge per pair + DJNZ, T (calibrated: CW_KT = 0 in the model)
CW_WKEN   EQU 0x1848            ; 2: this build runs the 8F95 work in cw_wait (milestone 3b), 0: no
CW_WKGO   EQU 0x1849            ; 2: work pending, first slice not yet run; 1: pending; 0: none/done
CW_WKSP   EQU 0x184A            ; window SP / IX / IY / BC while a slice runs
CW_WKIX   EQU 0x184C
CW_WKIY   EQU 0x184E
CW_WKBC   EQU 0x1850
CW_WKC0   EQU 0x1852            ; CTC count at the slice start
CW_WKN    EQU 0x1853            ; slices run (statistics; wraps)
CW_FINE   EQU 12                ; ticks: below this cw_wait spins fine; at or above it may run a slice
CW_WKM    EQU 9                 ; ticks a slice leaves before the deadline: longest work step between
                                ; polls + yield + the way back into the fine spin (calibrated)
        ASSERT CW_FINE >= CW_WKM + 3
CW_IRQSTK EQU 0x1900
CW_STACK  EQU 0x1A00            ; 19FE: game AF', 19FC: game AF
CW_CTC    EQU 0x1B3B            ; CTC channel 3
CW_ISR_T  EQU 94                ; IM2 ack 19, JR 12, JP 10, 998B PUSH AF..RET 53 (998E = 0)
CW_ISR_M1 EQU 10                ; ack + 9 instructions
CW_INTDLY EQU 14                ; ~28 T at 28MHz + handler body: the /INT pulse (32 T) ends before EI
CW_KSYNC  EQU 6                 ; T per sync-loop iteration at 28MHz
CW_M1K    EQU 0x33              ; R: end-to-end 8F92->9907 M1 difference (calibrated, then checked on every state)
CW_KRB    EQU 32880             ; 32768 + 261 (8F92 -> first OUT) - time-base offset (calibrated)
CW_KPAD   EQU 214               ; row-6 base + 6104 + 101 C -> clock target for 9907 entry (calibrated)

        MACRO CW_TICK           ; CW_NOW += CTC ticks since CW_LAST (down counter); A, F, HL
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        ld h,a
        ld a,(CW_LAST)
        sub h
        ld l,a
        ld a,h
        ld (CW_LAST),a
        ld a,l
        ld hl,(CW_NOW)
        add hl,a
        ld (CW_NOW),hl
        ENDM

        ORG 0x3CB0
cw_go:                          ; from cap_done_tail: DI, 28MHz, all registers = 9790 entry
        nextreg 0x50,CW_PAGE
        jp cw_head
cw_exit:                        ; from page 80 with exact 9907-entry state
        nextreg 0x50,255
        ei                      ; an IRQ pending since the pad is taken by the game ISR before 9907,
        nextreg 0x07,0          ; as the original takes it inside its head
        jp 0x9907
cw_orig:                        ; no CTC: the original copier, registers = 9790 entry
        nextreg 0x50,255
        nextreg 0x07,0
        ei
        jp 0x9790
wk_in:                          ; 3b: page 80 -> page 69 (both slot 0): a work slice (A, IYl from cw_work)
        nextreg 0x50,69
        jp wk_enter
wk_out:                         ; page 69 -> page 80: the slice yields (A = $C8, L = state)
        nextreg 0x50,CW_PAGE
        jp cw_wkback
wk_hook:                        ; 8F95 (the copier's return) in work builds: finish the work there
        di
        nextreg 0x07,3
        nextreg 0xC8,1          ; clear "ULA interrupt seen": read at the exit (wk_fdone)
        nextreg 0x50,69
        jp wk_frame
wk_hexit:                       ; from wk_fdone: game registers, R, A = (AC49) as LD A,(44105)
        nextreg 0x50,255
        ei
        nextreg 0x07,0
        jp 0x8F98
cw_rom_end:
        ASSERT cw_rom_end < 0x3D00
        SAVEBIN "inferno_cwrom.bin",cw_go,cw_rom_end-cw_go

        ORG 0
        DB cw_irq-1             ; IM2: FFFF is JR, its offset byte is read from 0000
        DB 0
cw_irq:                         ; frame IRQ inside the window; IFF = 0, SP = work stack
        ld (CW_IRQSP),sp
        ld sp,CW_IRQSTK
        push af
        push hl
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        ld (CW_IRQRAW),a
        ld hl,(CW_IRQT)
        add hl,CW_ISR_T
        ld (CW_IRQT),hl
        ld a,(CW_RIRQ)
        add a,CW_ISR_M1
        ld (CW_RIRQ),a
        ld hl,CW_NIRQ
        inc (hl)
        ld a,CW_INTDLY
.dly:   dec a
        jr nz,.dly
        pop hl
        pop af
        ld sp,(CW_IRQSP)
        ei
        ret

cw_wait:                        ; HL = T above DE ticks (+16 rounding, no CW_IRQT); returns DI at
        ld (CW_DL),hl           ; that tick + CW_IRQT (the caller OUTs, then EIs). A, F, B, DE, HL
        ld (CW_DBASE),de        ; changed; CW_NOW kept current whenever it waited.
.recalc:
        ld a,(CW_NIRQ)
        ld (CW_DNIRQ),a
        ld de,(CW_IRQT)
        add hl,de
        ex de,hl
        ld b,5
        bsrl de,b
        ld hl,(CW_DBASE)
        add hl,de
        ld (CW_DTK),hl
        ld de,(CW_NOW)
        or a
        sbc hl,de               ; ticks to go after the last clock update
        jr c,.done              ; due (a change the head reached late)
        jr z,.done
.class: ld a,h
        or a
        jr nz,.coarse
        ld a,l
        cp CW_FINE              ; (3b: the coarse loop may run work slices down to CW_FINE ticks)
        jr nc,.coarse
        ld e,a                  ; fine: spin on the count until (LAST - count) & 255 >= E
        ld a,(CW_LAST)
        ld l,a
        ld a,(CW_DNIRQ)
        ld d,a
.fine:  ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        ld h,a
        ld a,(CW_NIRQ)
        cp d
        jr nz,.irq
        ld a,l
        sub h
        cp e
        jr c,.fine
        ld l,a                  ; book the ticks: CW_NOW += LAST - count, CW_LAST = count
        ld a,h
        ld (CW_LAST),a
        ld a,l
        ld hl,(CW_NOW)
        add hl,a
        ld (CW_NOW),hl
.done:  di                      ; no IRQ between this check and the caller's OUT
        ld a,(CW_NIRQ)
        ld hl,CW_DNIRQ
        cp (hl)
        ret z
        ei
        jr .irq
.coarse:
        ld a,(CW_NIRQ)
        ld hl,CW_DNIRQ
        cp (hl)
        jr nz,.irq
        CW_TICK
        ld hl,(CW_DTK)
        ld de,(CW_NOW)
        or a
        sbc hl,de
        jr c,.done
        jr z,.done
        ld a,(CW_WKGO)          ; 8F95 work pending this window and >= CW_FINE ticks to go: a slice
        or a
        jr z,.class
        ld a,h
        or a
        jp nz,cw_work
        ld a,l
        cp CW_FINE
        jp nc,cw_work
        jr .class
.irq:   ld a,(CW_NIRQ)          ; an IRQ came: did the original make this OUT before it?
        ld (CW_DNIRQ),a
        ld a,(CW_IRQRAW)
        ld h,a
        ld a,(CW_LAST)
        sub h                   ; ticks from the last clock update to the IRQ (>= 128: before it)
        cp 128
        jr c,.at
        xor a
.at:    ld hl,(CW_NOW)
        add hl,a
        ld de,(CW_DTK)
        or a
        sbc hl,de
        jr nc,.done             ; IRQ at/after the deadline: the original OUT came first
        CW_TICK                 ; before it: the original's OUT moves by its ISR time
        ld hl,(CW_DL)
        jp .recalc
cw_wait_end:

; Milestone 3b: a slice of the 8F95 work (page-69 coroutine, wk_enter) inside cw_wait. HL = ticks
; to the deadline (>= CW_FINE). The slice ends CW_WKM ticks before it (at most 120 ticks: the 8-bit
; count), DI (slot 0 is page 69, which does not own the IM2 offset); NextReg $C8 is cleared here and
; read at the yield: a pulse in the slice is counted as cw_irq does. Window registers and SP are kept
; here (the work has its own stack; nothing is pushed on the copier's).
cw_work:
        ld a,h
        or a
        ld a,120
        jr nz,.len
        ld a,l
        sub CW_WKM
        cp 120
        jr c,.len
        ld a,120
.len:   ld e,a
        di
        ld (CW_WKSP),sp
        ld (CW_WKIX),ix
        ld (CW_WKIY),iy
        ld (CW_WKBC),bc
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        ld (CW_WKC0),a
        ld a,(CW_LAST)          ; slice end: the count CW_WKM ticks before the deadline
        sub e
        ld iyl,a
        ld hl,CW_WKN
        inc (hl)
        ld a,(CW_WKGO)          ; 2: first slice this window (the work restarts on this capture)
        ld e,a
        ld a,1
        ld (CW_WKGO),a
        ld a,e
        nextreg 0xC8,1
        jp wk_in
cw_wkback:                      ; from wk_out: slot 0 = page 80, DI; A = NextReg $C8, L = 2: work done
        ld h,a
        ld a,l
        cp 2
        jr nz,.more
        xor a
        ld (CW_WKGO),a
.more:  ld a,h
        rrca
        jr nc,.in
        ld bc,0x243B            ; a pulse came in the slice (lost, DI): wait until /INT drops,
        ld a,0x22               ; then the original's no-op ISR as cw_irq counts it, at the slice
        out (c),a               ; start (before the deadline)
        inc b
.intw:  in a,(c)
        rlca
        jr c,.intw
        ld a,(CW_WKC0)
        ld (CW_IRQRAW),a
        ld hl,(CW_IRQT)
        add hl,CW_ISR_T
        ld (CW_IRQT),hl
        ld a,(CW_RIRQ)
        add a,CW_ISR_M1
        ld (CW_RIRQ),a
        ld hl,CW_NIRQ
        inc (hl)
.in:    ld sp,(CW_WKSP)
        ld ix,(CW_WKIX)
        ld iy,(CW_WKIY)
        ld bc,(CW_WKBC)
        ei
        ld hl,(CW_WKRET)
        jp (hl)
CW_WKRET:
        dw cw_wait.coarse
CW_WOT: dw 0                    ; ticks left in the replaced write-out
CW_WOQ: db 0                    ; 1: the Copper queue has run this update
; Copier write-out replaced (980B, DI in the original, no OUTs): the queued screen bytes are hidden by the tilemap,
; so the pending work runs here for as long as the write-out would have taken, then pads to that time.
; T = 18 rows * 564 + 198 per wide line + 49 + a measured 2,700 (replay error within about 600 T).
wo_go:
        ld a,(CW_CLK)
        dec a
        jp nz,wo_orig           ; no CTC: the original write-out
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        ld (CW_LAST),a
        ld hl,0
        add hl,sp
        ld de,0
.walk:  ld a,(hl)               ; F of the row: carry marks the end
        inc hl
        rrca
        jr c,.sum
        ld c,(hl)               ; A of the row: wide lines
        inc hl
        ld b,0
        ex de,hl
        add hl,bc
        ex de,hl
        add hl,bc               ; skip 4 bytes per wide line, then the row's 4
        add hl,bc
        add hl,bc
        add hl,bc
        inc hl
        inc hl
        inc hl
        inc hl
        jr .walk
.sum:   ld a,d                  ; lines * 99 >> 4 = lines * 198 / 32 ticks
        ld d,99
        mul d,e
        push de
        ld e,a
        ld d,99
        mul d,e
        ld a,e
        pop hl
        add a,h
        ld h,a
        ex de,hl
        ld b,4
        bsrl de,b
        ld hl,403
        add hl,de
        ld (CW_WOT),hl
        ld hl,wo_back
        ld (CW_WKRET),hl
        xor a
        ld (CW_WOQ),a
wo_loop:
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        ld c,a
        ld a,(CW_LAST)
        sub c
        ld e,a
        ld d,0
        ld a,c
        ld (CW_LAST),a
        ld hl,(CW_WOT)
        or a
        sbc hl,de
        jr c,wo_end
        ld (CW_WOT),hl
        ld a,(CW_WKGO)          ; 0: the coroutine is idle or finished
        or a
        jr nz,.work
        ld a,(CW_WOQ)
        or a
        jr nz,wo_loop
        inc a
        ld (CW_WOQ),a
        ld (CW_WKSP),sp         ; on the work stack address: valid in pages 80 and 69
        ld sp,0x1C40
        call wo_queue
        ld sp,(CW_WKSP)
        jr wo_loop
.work:
        ld a,h
        or a
        jp nz,cw_work
        ld a,l
        cp CW_WKM+8
        jp nc,cw_work           ; a slice needs room for its margin
        jr wo_loop
wo_back:
        di
        jr wo_loop
wo_end:
        ld hl,cw_wait.coarse
        ld (CW_WKRET),hl
        jp wo_out
wi_go:
        ld hl,0x1C00
.next:  ld a,(hl)
        inc hl
        or a
        jp z,wi_back
        ld b,a
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
.byte:  ld a,(hl)
        ld (de),a
        inc hl
        inc de
        djnz .byte
        jr .next
cw_work_end:

cw_head:
        ld (CW_SP),sp
        ld sp,CW_STACK
        ex af,af'
        push af                 ; game AF' (19FE)
        ex af,af'
        push af                 ; game AF (19FC)
        ld a,r
        ld (CW_R),a
        ld a,(CW_CLK)
        dec a
        jp nz,cw_noclock
cw_clocked:
        ld (CW_SVHL),hl
        ld (CW_SVDE),de
        ld (CW_SVBC),bc
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        ld c,a
        ld b,24
cw_sync:                        ; the next CTC edge is the time base (24 - B loops of CW_KSYNC T)
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        cp c
        jr nz,cw_synced
        djnz cw_sync
        ld a,2                  ; the counter stopped: original copier from now on
        ld (CW_CLK),a
        ld hl,(CW_SVHL)
        ld de,(CW_SVDE)
        ld bc,(CW_SVBC)
        jp cw_absent
cw_synced:
        ld (CW_CCD),a
        ld (CW_LAST),a
        xor a
        ld (CW_RIRQ),a
        ld (CW_NIRQ),a
        ld (CW_PEND),a
        ld l,a
        ld h,a
        ld (CW_IRQT),hl
        ld d,b                  ; sync loops left (B is the port's high byte below)
        ld bc,0x243B            ; an IRQ lost in the entry DI span (cap_done + sync): $C8 bit 0,
        ld a,0xC8               ; cleared at 8F92, is set
        out (c),a
        inc b
        in a,(c)
        rrca
        jr nc,cw_nolost
        dec b
        ld a,0x22
        out (c),a
        inc b
cw_intw:
        in a,(c)                ; wait until /INT drops: the pulse is lost (DI)
        rlca
        jr c,cw_intw
        ld hl,CW_ISR_T          ; as the original's no-op ISR early in its head
        ld (CW_IRQT),hl
        ld a,CW_ISR_M1
        ld (CW_RIRQ),a
cw_nolost:
        ei                      ; IRQs from here on enter cw_irq (no SP below a live saved value)
        ld a,(CW_WKEN)          ; 3b: the 8F95 work may run in this window's waits
        ld (CW_WKGO),a
        ld hl,1024
        ld (CW_NOW),hl
        ld a,24
        sub d
        ld e,a
        ld d,CW_KSYNC
        mul d,e
        ld hl,(CW_X)
        add hl,de
        ld a,(CW_KT)            ; + the entry speed switch's measured excess (half a pair)
        sra a
        ld e,a
        add a,a
        sbc a,a
        ld d,a
        add hl,de
        ld a,l
        cpl
        ld l,a
        ld a,h
        cpl
        ld h,a
        inc hl
        add hl,CW_KRB           ; first-row base = KRB - X - sync time
        ld a,l
        and 31
        ld (CW_RBF),a
        ex de,hl
        ld b,5
        bsrl de,b
        ld (CW_RBT),de
        ld hl,(CW_SVHL)
        ld de,(CW_SVDE)
        ld bc,(CW_SVBC)
        ld (CW_IY),iy
        ld iy,CW_PREV
        ld a,(0xA741)           ; first cell's OUT value: its complement forces the first OUT
        cpl
        ld (iy+0),a
        xor a
        ld (CW_RSUM),a
        ld a,CW_ROWC & 0xFF
        ld (cw_rp+1),a
        di                      ; a few instructions: the caller's stack stays untouched by IRQ pushes
        ld sp,CW_STACK-4
        pop af                  ; game AF and flags, exactly
        ld sp,(CW_SP)
        ; --- original 9790 prologue ---
        ld (0x9878),sp          ; LD (39032),SP: the copier's own SP save
        ld sp,0xA6FE
        ei
        ld hl,0x9877
        push hl
        scf
        push af
        ld hl,0x9F7F
        ld de,0x50FF
        exx
        ld de,0xAB41
        ld hl,0x5AFF
        ld ixh,18
cw_row:                         ; alt set (97AD)
        push de
        push hl
        ld bc,0xFFE0
        add hl,bc
        exx
        ld c,0
cw_cell:                        ; main set (97B6)
        ld a,(hl)
        and 3
        ld b,a
        ld ixl,b
        dec l
        ld a,(hl)
        dec hl
        exx
        ld c,a
        ld a,0xFC
        add a,ixl
        ld b,a
        ld a,(bc)
        ld (de),a
        ld b,d
        ld d,0xA7
        ld a,(de)               ; the value the original OUTs for this cell
        ld d,b
        ld ixl,a
        dec de
        ld a,c
        exx
        ex af,af'
        ld a,ixl
        cp (iy+0)
        jp z,cw_same
        ld (iy+0),a
        ld a,e                  ; j = cell within the row
        cpl
        and 31
        cp 31
        jr nz,cw_chg
        ld a,ixh
        cp 6
        ld a,31
        jr nz,cw_chg
        ld a,c                  ; cell 415: OUT after the row end and epilogue
        ld (CW_PC),a
        ld a,1
        ld (CW_PEND),a
        jp cw_same
cw_chg:                         ; deadline = RBT + (RBF + 16 + 187 j + 101 c) / 32 ticks
        ld (CW_SVHL),hl
        ld (CW_SVDE),de
        ld (CW_SVBC),bc
        ld e,a
        ld d,187
        mul d,e
        ld a,(CW_RBF)
        add a,16
        add de,a
        ex de,hl
        ld e,c
        ld d,101
        mul d,e
        add hl,de
        ld de,(CW_RBT)
        call cw_wait            ; the return address lands below SP; the next push overwrites it
        ld a,ixl
        out (0xFE),a            ; the original's OUT (254),A of this cell, at its T
        ei
        ld hl,(CW_SVHL)
        ld de,(CW_SVDE)
        ld bc,(CW_SVBC)
cw_same:
        ex af,af'
        cp 16
        jp c,cw_low
        push hl
        ld l,a
        ld h,b
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,220
        ld h,a
        ex (sp),hl
        push de
        inc c
cw_low:
        dec e
        ld a,e
        inc a
        jp nz,cw_nowrap
        ld a,d
        sub 8
        ld d,a
        xor a
cw_nowrap:
        and 31
        jp nz,cw_cell
        ld a,c                  ; row end (97F4)
        or a
        push af
cw_rp:  ld (CW_ROWC),a
        ld a,c                  ; RSUM += 12*C: the >=16 path is 12 M1 (mod 256; R needs mod 128)
        add a,a
        add a,c
        add a,a
        add a,a
        ld ixl,a
        ld a,(CW_RSUM)
        add a,ixl
        ld (CW_RSUM),a
        ld a,(cw_rp+1)
        inc a
        ld (cw_rp+1),a
        ld a,ixh
        cp 6
        jp z,cw_done            ; row 6: the pad target is taken from this row's base
        ld (CW_SVHL),hl         ; row base += 32*187 + 120 + 101*C (+19 from cell 256 on)
        ld (CW_SVDE),de
        ld (CW_SVBC),bc
        ld e,c
        ld d,101
        mul d,e
        add de,6104
        cp 11
        jr nz,cw_rb_add
        add de,19
cw_rb_add:
        ld a,(CW_RBF)
        add de,a
        ld a,e
        and 31
        ld (CW_RBF),a
        ld b,5
        bsrl de,b
        ld hl,(CW_RBT)
        add hl,de
        ld (CW_RBT),hl
        CW_TICK                 ; at least once a row (< 8192 T) so the 8-bit count never laps
        ld a,ixh
        cp 7
        jr nz,cw_rb_next
        ld hl,(CW_RBT)          ; row 6 next: the parts of the pad target and R that need no row-6 data
        ld de,-32
        add hl,de
        ld (CW_PADB),hl
        ld a,(CW_RBF)
        ld hl,6104+1024+16-CW_KPAD
        add hl,a
        ld a,(CW_KT)            ; - the exit speed switch's measured excess (half a pair)
        sra a
        neg
        ld e,a
        add a,a
        sbc a,a
        ld d,a
        add hl,de
        ld (CW_PADL),hl
        ld a,(CW_R)
        ld l,a
        add a,CW_M1K
        ld (CW_RS),a
        ld a,l
        and 0x80
        ld (CW_RH),a
cw_rb_next:
        ld hl,(CW_SVHL)
        ld de,(CW_SVDE)
        ld bc,(CW_SVBC)
        dec ixh
        exx
        jp cw_row
cw_done:                        ; main set, as the original at CALL Z,9907: last OUT, finish, pad
        ld (CW_SVHL),hl
        ld (CW_SVDE),de
        ld (CW_SVBC),bc
        ld a,(CW_PEND)
        or a
        jr z,cw_epilogue
        ld a,(CW_PC)            ; cell 415: RBT + (RBF + 16 + 187*31 + 101 c) / 32
        ld e,a
        ld d,101
        mul d,e
        ld a,(CW_RBF)
        add a,16
        add de,a
        ex de,hl
        ld de,187*31
        add hl,de
        ld de,(CW_RBT)
        call cw_wait
        ld a,(CW_PREV)          ; cell 415's value (IXl is the row end's scratch by now)
        out (0xFE),a
        ei
cw_epilogue:                    ; after the last OUT: everything but R and the exit
        ld iy,(CW_IY)
        ld a,(CW_SVBC+1)        ; alt B = FC + page of the last cell (97CC)
        add a,0xFC
        exx
        ld b,a
        exx
        ld (CW_WSP),sp
        ld sp,CW_STACK-2
        ex af,af'
        pop af                  ; game AF'
        ex af,af'
        ld sp,(CW_WSP)
        ld hl,0x97FE            ; the CALL Z,9907 return address
        push hl
        ld a,(CW_SVBC)          ; pad target = row-6 base + 6104 + 101 C - KPAD
        ld e,a
        ld d,101
        mul d,e
        ld hl,(CW_PADL)
        add hl,de
        ld de,(CW_PADB)
        call cw_wait
        ei                      ; (an IRQ here still reaches R through CW_RIRQ)
        ld de,(CW_SVDE)
        ld bc,(CW_SVBC)
        ld a,b
        ld ixl,a                ; IXl = page of the last cell (97BA)
cw_pad_end:
        di
        ld a,(CW_RSUM)          ; R = entry R + M1 constant + 12 G + the window's IRQs
        ld hl,CW_RS
        add a,(hl)
        ld hl,CW_RIRQ
        add a,(hl)
        and 0x7F
        ld hl,CW_RH
        or (hl)
        ld r,a
        ld hl,(CW_SVHL)
        ld a,ixh
        cp 6                    ; A and F exactly as at the original CALL
        jp cw_exit
cw_noclock:                     ; A = CW_CLK - 1: FF untested, 01 absent
        inc a
        jr nz,cw_absent
        ld (CW_SVBC),bc         ; test once: does CTC channel 3 count?
        ld bc,CW_CTC
        ld a,0x27               ; timer, prescaler 256, time constant follows, reset; no interrupt
        out (c),a
        xor a                   ; time constant 256
        out (c),a
        in a,(c)
        ld (CW_DNIRQ),a
        ld a,100                ; ~200 T: at least 5 ticks
.spin:  dec a
        jr nz,.spin
        in a,(c)
        ld b,a
        ld a,(CW_DNIRQ)
        cp b
        ld a,1
        jr nz,.ok
        inc a
.ok:    ld (CW_CLK),a
        dec a
        call z,cw_cal           ; the CTC counts: measure the speed switches once
        ld bc,(CW_SVBC)
        ld a,(CW_CLK)
        dec a
        jp z,cw_clocked
        jr cw_absent
cw_cal:                       ; CW_KT = T per (NEXTREG 7,0 / NEXTREG 7,3) pair less the model's charge
        call cw_edge            ; (hooks and window constants assume the model; hardware may differ)
        ld (CW_HC0),a
        ld b,64
.pair:  nextreg 0x07,0
        nextreg 0x07,3
        djnz .pair
        call cw_edge
        ld b,a
        ld a,(CW_HC0)
        sub b                   ; ticks for 64 pairs: T per pair = ticks / 2
        srl a
        sub CW_KTPAIR
        ld (CW_KT),a
        ret
cw_absent:
        ld sp,CW_STACK-4
        pop af
        ld sp,(CW_SP)
        jp cw_orig
; Capture-hook timing (milestone 3), called from cap_in/cap_out with page 80 at slot 0, DI, 28MHz,
; SP in page 80's unused 1FE0s. X = 32 * CTC ticks between the hook's entry and exit edges - KSYNC *
; sync loops left at the entry edge + K (per hook: its constant paths less the displaced original).
cw_tin:                         ; B = entry R. A F B C
        ld a,b
        ld (CW_HR),a
        ld a,(CW_CLK)
        cp 1
        ld a,0
        jr nz,.clk
        inc a
.clk:   ld (CW_HCLK),a
        or a
        ret z
        call cw_edge            ; (a game ISR on the site's JP came before this edge: not in X, as it
        ld (CW_HC0),a           ; is the original's too; its M1 are in the R read)
        ld a,b
        ld (CW_HN0),a
        ret
cw_edge:                        ; -> A = CTC count after the next edge, B = the check that saw it
        ld bc,CW_CTC            ; (12 evenly spaced checks, CW_KH8 / 8 T apart; B = 12: none). A B C E
        in e,(c)
        in a,(c)
        cp e
        jr nz,.x0
        in a,(c)
        cp e
        jr nz,.x1
        in a,(c)
        cp e
        jr nz,.x2
        in a,(c)
        cp e
        jr nz,.x3
        in a,(c)
        cp e
        jr nz,.x4
        in a,(c)
        cp e
        jr nz,.x5
        in a,(c)
        cp e
        jr nz,.x6
        in a,(c)
        cp e
        jr nz,.x7
        in a,(c)
        cp e
        jr nz,.x8
        in a,(c)
        cp e
        jr nz,.x9
        in a,(c)
        cp e
        jr nz,.x10
        in a,(c)
        cp e
        jr nz,.x11
        ld b,12
        ret
.x0:    ld b,0
        jr .done
.x1:    ld b,1
        jr .done
.x2:    ld b,2
        jr .done
.x3:    ld b,3
        jr .done
.x4:    ld b,4
        jr .done
.x5:    ld b,5
        jr .done
.x6:    ld b,6
        jr .done
.x7:    ld b,7
        jr .done
.x8:    ld b,8
        jr .done
.x9:    ld b,9
        jr .done
.x10:    ld b,10
        jr .done
.x11:    ld b,11
        jr .done
.done:  ret
cw_tout:                        ; HL = K, A = KR, E = 0 set X / 1 add -> A = R to restore. A F B C D E H L
        ld c,e
        ld e,a
        ld a,(CW_HR)
        ld d,a
        add a,e
        xor d
        and 0x7F
        xor d                   ; bit 7 kept
        ld (CW_HRN),a
        ld a,(CW_HCLK)
        or a
        jr z,.r
        ld a,c
        ld (CW_HXT),a
        call cw_edge            ; the exit edge: constant time from here to the hook's exit
        ld b,a
        ld a,(CW_HC0)
        sub b
        ld e,a
        ld d,32
        mul d,e
        add hl,de               ; + 32 * ticks between the edges
        ld a,(CW_HN0)
        ld e,a
        ld d,CW_KH8
        mul d,e
        ld b,3
        bsrl de,b
        add hl,de               ; + KH8 / 8 * the check that saw the entry edge
        ld a,(CW_KT)            ; + the measured excess of the hook's two speed switches
        ld e,a
        add a,a
        sbc a,a
        ld d,a
        add hl,de
        ld a,(CW_HXT)
        or a
        jr z,.set
        ld de,(CW_X)
        add hl,de
.set:   ld (CW_X),hl
.r:     ld bc,0x243B            ; select NextReg $C8 for cap_chk's one-register read
        ld a,0xC8
        out (c),a
        ld a,(CW_HRN)
        ret
cw_head_end:
        ASSERT cw_head_end < 0x1000
        SAVEBIN "inferno_cwhead.bin",0,cw_head_end

; Loading driver (pipeline item 1). Private page 81, entered from the 8EF9 gate (page-68 stub 1D80,
; DI, 28 MHz, the gate's private stack). Enumerates all 256 C100 indices: snapshot (78), exact
; stream duplicate search over published entries, colour (75), whole-image B (76), store (79).
; Worker pages carry drvworker at 1D00 and the word 1D00 at 1FF0, so a worker's RET comes back
; here; slots 1-3 are restored by the workers (1=68, 2=10, 3=11) and slot 1 to 255 before exit.
W_A      EQU 0x2000            ; worker field alias through slot 1
D_STATE  EQU 0x1800
D_RETSP  EQU 0x1800
D_CALLSP EQU 0x1802
D_IMAGE  EQU 0x1804
D_SIZE   EQU 0x1805
D_MINX   EQU 0x1807
D_MAXX   EQU 0x1809
D_MINY   EQU 0x180B
D_MAXY   EQU 0x180D
D_W      EQU 0x180F            ; tiles
D_STRIDE EQU 0x1810
D_CSIZE  EQU 0x1812
D_LEFT   EQU 0x1814
D_RX     EQU 0x1815
D_RY     EQU 0x1817
D_PAGEB  EQU 0x1819
D_STORED EQU 0x181A            ; words: distinct streams stored, duplicate indices, rejected
D_DUPS   EQU 0x181C
D_REJ    EQU 0x181E
D_FAIL  EQU 0x1820            ; 1 = a worker refused valid input (the run is not trusted)
D_CANON  EQU 0x1830            ; duplicate: its canonical entry (slot-1 alias)
D_PATS   EQU 0x1832            ; word: distinct 16x16 patterns stored
D_CPTR   EQU 0x1834            ; word: next chunk record, page 83 offset
D_H      EQU 0x1836            ; tiles (0 = 256)
D_CX     EQU 0x1837
D_CY     EQU 0x1838
D_CHN    EQU 0x1839            ; chunks of this image
D_CSTART EQU 0x183A
D_ID     EQU 0x183C            ; chunk cell mask while hashing
D_OFF    EQU 0x183E            ; canvas offset of the chunk's next row
D_HEAD   EQU 0x1840
D_PHASE  EQU 0x1842            ; FLASH phase of this canvas pass
D_FANY   EQU 0x1843            ; bit 7: the image has a FLASH tile
D_STACK  EQU 0x1BF0
D_BUF    EQU 0x1C00            ; 128-byte chunk
PAT_BASE EQU 85                ; first pattern page; 11 pages of 64 patterns
PAT_MAX  EQU 704
        ORG 0
driver:
        ld (D_RETSP),sp
        ld sp,D_STACK
        nextreg 0x51,79
        xor a
        ld (C_OP+W_A),a
        ld (C_CURRENT+W_A),a
        ld (C_PENDING+W_A),a
        ld hl,0
        ld a,79
        call drv_call
        nextreg 0x51,78
        xor a
        ld (J_ACTIVE+W_A),a
        ld (J_DONE+W_A),a
        ld hl,D_STATE+4
        ld de,D_STATE+5
        ld (hl),a
        ld bc,0x1C
        ldir
        call drv_sel_reset
.next:  ld a,(D_IMAGE)           ; one thin border bar per image, as while loading (28 MHz: a line is about 1824 T)
        and 7
        jr nz,.bar
        ld a,2
.bar:   out (0xFE),a
        ld b,140
.line:  djnz .line
        xor a
        out (0xFE),a
        nextreg 0x51,78
        xor a
        ld (J_OP+W_A),a
        ld (J_FLASH+W_A),a
        ld (J_PAINT+W_A),a
        ld (J_PAINT+W_A+1),a
        ld a,(D_IMAGE)
        ld (J_IMAGE+W_A),a
        ld a,78
        ld hl,0
        call drv_call
        nextreg 0x51,78
        ld a,(J_ERROR+W_A)
        or a
        jp nz,.rejected
        ld a,(J_DONE+W_A)
        or a
        jp z,.rejected
        ld hl,(J_SIZE+W_A)
        ld (D_SIZE),hl
        ld de,2
        or a
        sbc hl,de
        jp z,.release            ; no tiles: nothing to prepare
        call drv_find
        jp z,.duplicate
        call drv_bounds
        jp nz,.reject_release
        xor a
        ld (D_PHASE),a
        ld (D_FANY),a
        call drv_clear
        call drv_tiles
        jp nz,.bad_worker
        call drv_fill
        jp nz,.bad_worker
        call drv_index
        jp nz,.reject_release    ; pattern capacity: unpublished, later draws miss
        nextreg 0x51,79
        ld a,1
        ld (C_OP+W_A),a
        ld a,(D_IMAGE)
        ld (C_IMAGE+W_A),a
        xor a
        ld (C_FLASH+W_A),a
        ld (C_PAINT+W_A),a
        ld (C_PAINT+W_A+1),a
        ld hl,(D_SIZE)
        ld (C_SOURCE_SIZE+W_A),hl
        ld hl,(D_CSIZE)
        ld (C_CANVAS_SIZE+W_A),hl
        ld a,79
        ld hl,0
        call drv_call
        nextreg 0x51,79
        ld a,(C_ERROR+W_A)
        or a
        jp nz,.reject_release    ; capacity: unpublished, later draws miss
        ld a,(C_FOUND+W_A)
        or a
        jp z,.reject_release
        call drv_phase1
        ld hl,(D_STORED)
        inc hl
        ld (D_STORED),hl
        jp .release
.duplicate:
        call drv_dup_index
        ld hl,(D_DUPS)
        inc hl
        ld (D_DUPS),hl
        jp .release
.bad_worker:
        ld a,1
        ld (D_FAIL),a
.reject_release:
        ld hl,(D_REJ)
        inc hl
        ld (D_REJ),hl
.release:
        nextreg 0x51,78
        ld a,1
        ld (J_OP+W_A),a
        ld a,78
        ld hl,0
        call drv_call
        jr .step
.rejected:
        ld hl,(D_REJ)
        inc hl
        ld (D_REJ),hl
.step:  ld hl,D_IMAGE
        inc (hl)
        jp nz,.next
        nextreg 0x51,255
        nextreg 0x52,10
        nextreg 0x53,11
        ld sp,(D_RETSP)
        jp 0x1D90

; A = page, HL = entry; the worker's stack is the top of its own page.
drv_call:
        ld (D_CALLSP),sp
        ld sp,0x1FF0
        jp 0x1D10

; Exact search of published entries below D_IMAGE; Z = found, entry copied (valid last).
drv_find:
        nextreg 0x51,79
        nextreg 0x52,122
        ld hl,0x0800+W_A
        ld a,(D_IMAGE)
        or a
        jr z,.none
        ld b,a
.loop:  push bc
        push hl
        ld a,(hl)
        cp 1
        jr nz,.skip
        push hl
        pop ix
        ld a,(ix+4)
        ld hl,D_SIZE
        cp (hl)
        jr nz,.skip
        ld a,(ix+5)
        inc hl
        cp (hl)
        jr nz,.skip
        ld a,(ix+1)
        nextreg 0x53,a
        ld l,(ix+2)
        ld h,(ix+3)
        ld de,0x6000
        add hl,de
        ld de,0x4000
        ld bc,(D_SIZE)
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.skip
        inc de
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,.cmp
        pop hl                  ; entry found: copy the 15 metadata bytes, then publish
        ld (D_CANON),hl
        pop bc
        ld a,(D_IMAGE)
        ld e,a
        ld d,0
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,0x0800+W_A
        add hl,bc
        ex de,hl
        push de
        inc de
        inc hl
        ld bc,15
        ldir
        pop hl
        ld (hl),1
        nextreg 0x52,10
        nextreg 0x53,11
        xor a
        ret
.skip:  pop hl
        ld de,16
        add hl,de
        pop bc
        djnz .loop
.none:  nextreg 0x52,10
        nextreg 0x53,11
        or 1
        ret

; Geometry bounds of the stream at slot 2. NZ = outside the canvas limits.
drv_bounds:
        nextreg 0x52,122
        ld a,(0x4000)
        and 3
        ld (D_PAGEB),a
        ld hl,0x7FFF
        ld (D_MINX),hl
        ld (D_MINY),hl
        ld hl,0x8000
        ld (D_MAXX),hl
        ld (D_MAXY),hl
        ld hl,0x4001
.row:   ld a,(hl)
        inc hl
        or a
        jp z,.done
        ld (D_LEFT),a
        ld a,(hl)
        inc hl
        call .sign
        ld (D_RX),de
        ld a,(hl)
        inc hl
        call .sign
        ld (D_RY),de
        ld ix,D_MINY
        call .bound
        ld de,(D_RX)
        ld ix,D_MINX
        call .bound
        ld a,(D_LEFT)
        dec a
        ld e,a
        ld d,0
        push hl
        ld hl,(D_RX)
        add hl,de
        ex de,hl
        pop hl
        ld ix,D_MAXX-2          ; only the maximum applies
        call .max
        ld a,(D_LEFT)
        ld e,a
        ld d,0
        ex de,hl
        add hl,hl
        ld c,l
        ld b,h
        add hl,hl
        add hl,hl
        add hl,bc
        add hl,de               ; + 10 bytes per tile
        jr .row
.sign:  ld e,a
        rla
        sbc a,a
        ld d,a
        ret
.bound: ; DE signed against the (min,max) pair at IX
        ld c,(ix+0)
        ld b,(ix+1)
        push hl
        ld l,c
        ld h,b
        or a
        sbc hl,de
        jp pe,.ovmin
        jp p,.newmin
        jr .chkmax
.ovmin: jp m,.newmin
        jr .chkmax
.newmin:
        ld (ix+0),e
        ld (ix+1),d
.chkmax:
        pop hl
.max:   ld c,(ix+2)
        ld b,(ix+3)
        push hl
        ld l,c
        ld h,b
        or a
        sbc hl,de
        jp pe,.ovmax
        jp m,.newmax
        jr .outb
.ovmax: jp p,.newmax
        jr .outb
.newmax:
        ld (ix+2),e
        ld (ix+3),d
.outb:  pop hl
        ret
.done:  nextreg 0x52,10
        ld hl,(D_MAXX)
        ld de,(D_MINX)
        or a
        sbc hl,de
        inc hl                  ; W tiles
        ld a,h
        or a
        ret nz                  ; NZ: width beyond 128
        ld a,l
        cp 129
        jr c,.w_ok
        or 1
        ret
.w_ok:  ld (D_W),a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld (D_STRIDE),hl        ; bytes per pixel row (4-bit pixels, 8 pixels a tile)
        ld hl,(D_MAXY)
        ld de,(D_MINY)
        or a
        sbc hl,de
        inc hl                  ; H tiles, 1..256
        ex de,hl
        ld hl,0
        ld a,(D_W)
        ld b,a
.mul:   add hl,de
        djnz .mul
        push hl
        ld de,1025
        or a
        sbc hl,de
        pop hl
        jr nc,.far              ; W*H > 1024 tiles = over 65,536 pixels
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld (D_CSIZE),hl         ; W*H*32 bytes
        xor a
        ret
.far:   or 1
        ret

; Zero the first D_CSIZE canvas bytes (pages 112..115).
drv_clear:
        ld a,112
        ld (D_LEFT),a
        ld hl,(D_CSIZE)
.page:  ld a,h
        or l
        ret z
        ld a,(D_LEFT)
        nextreg 0x51,a
        inc a
        ld (D_LEFT),a
        push hl
        ld a,h
        cp 0x20
        jr c,.part
        ld hl,0x2000
.part:  ld c,l
        ld b,h
        ld hl,0x2000
        ld de,0x2001
        ld (hl),0
        dec bc
        ld a,b
        or c
        jr z,.one
        ldir
.one:   pop hl
        ld de,-0x2000
        add hl,de
        jr c,.page
        ret

; Colour every stream tile into the canvas. NZ = pack refused valid input.
drv_bar:                        ; a thin border bar for about one tile in 16; all registers kept
        push af
        ld a,r
        and 15
        jr nz,.skip
        push bc
        ld a,r
        and 7
        jr nz,.bar
        ld a,3
.bar:   out (0xFE),a
        ld b,140
.line:  djnz .line
        xor a
        out (0xFE),a
        pop bc
.skip:  pop af
        ret
drv_tiles:
        ld hl,0x4001
.row:   nextreg 0x52,122
        ld a,(hl)
        inc hl
        or a
        jr nz,.w
        nextreg 0x52,10
        xor a
        ret
.w:     ld (D_LEFT),a
        ld a,(hl)
        inc hl
        call drv_bounds.sign
        ld (D_RX),de
        ld a,(hl)
        inc hl
        call drv_bounds.sign
        ld (D_RY),de
.tile:  call drv_bar
        push hl
        nextreg 0x51,75
        nextreg 0x52,122
        push hl
        ld de,9                 ; this tile's attribute: remember FLASH
        add hl,de
        ld a,(hl)
        and 0x80
        ld hl,D_FANY
        or (hl)
        ld (hl),a
        pop hl
        ld a,1
        ld (P_SOURCE+W_A),a
        ld a,(D_PHASE)
        ld (P_FLASH+W_A),a
        ld a,(hl)
        ld (P_TILE+W_A),a
        ld a,(D_PAGEB)
        ld (P_TILE+W_A+1),a
        inc hl
        ld de,P_RAW+W_A
        ld bc,9
        ldir
        ld hl,(D_STRIDE)
        ld (P_STRIDE+W_A),hl
        ld hl,(D_RY)            ; (y - top) * W * 32 + (x - left) * 4
        ld de,(D_MINY)
        or a
        sbc hl,de
        ld d,l
        ld a,(D_W)
        ld e,a
        mul d,e
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        push hl
        ld hl,(D_RX)
        ld de,(D_MINX)
        or a
        sbc hl,de
        add hl,hl
        add hl,hl
        pop de
        add hl,de
        ld (P_DEST+W_A),hl
        nextreg 0x52,10
        ld a,75
        ld hl,0
        call drv_call
        nextreg 0x51,75
        ld a,(P_ERROR+W_A)
        or a
        pop hl
        ret nz
        ld de,10
        add hl,de
        ld de,(D_RX)
        inc de
        ld (D_RX),de
        ld a,(D_LEFT)
        dec a
        ld (D_LEFT),a
        jp nz,.tile
        jp .row

; Whole-image B. NZ = fill refused.
drv_fill:
        nextreg 0x51,76
        ld hl,(D_STRIDE)
        ld (F_STRIDE+W_A),hl
        ld hl,(D_CSIZE)
        ld (F_SIZE+W_A),hl
        xor a
        ld (F_DONE+W_A),a
        ld (F_ERROR+W_A),a
        ld (F_ACTIVE+W_A),a
        ld (F_COMMAND+W_A),a
        ld b,a
        ld a,(D_IMAGE)
        cp 0xB2
        jr z,.narrow            ; explosions keep the plain enclosed rule (user's choice)
        cp 0xB4
        jr z,.narrow
        cp 0xB6
        jr z,.narrow
        cp 0xB8
        jr z,.narrow
        inc b
.narrow:
        ld a,b
        ld (F_WIDE+W_A),a
        ld a,16
        ld (F_BUDGET+W_A),a
.again: ld a,76
        ld hl,fill_actor_service
        call drv_call
        nextreg 0x51,76
        ld a,(F_ERROR+W_A)
        or a
        ret nz
        ld a,(F_DONE+W_A)
        or a
        jr nz,.ok
        ld a,1
        ld (F_COMMAND+W_A),a
        jr .again
.ok:    xor a
        ret
; Pattern index (selection, pipeline item 3), built at 8EF9 from each new canvas. Page 83: 6-byte header per
; image (valid last, count, offset16, left, top) then 5-byte chunks (cx, cy in tiles, cell mask, id16), non-blank
; only. Pages 85..95: 16x16 patterns, one copy per distinct content (hash chains in page 84: heads 0000, next 0200).
drv_sel_reset:
        nextreg 0x15,0          ; sprites off until a complete frame is published
        nextreg 0x6B,0x0B       ; scenery layer off
        nextreg 0x62,0
        nextreg 0x51,69
        ld hl,0x2000+Q_TOKEN
        ld b,10
.qr:    ld (hl),0
        inc hl
        djnz .qr
        ld a,69                 ; palettes and windows (one-time, in the pause)
        ld hl,setup_display
        call drv_call
        nextreg 0x51,82
        ld hl,0x3000
        ld de,0x3001
        ld (hl),0
        ld bc,0x0FFF
        ldir
        ld a,0x24
        ld (SEL_ROLE+SEL_A),a
        ld hl,SLOT_PREV+SEL_A    ; recency list 0..63, head oldest
        xor a
.lr:    ld (hl),128
        or a
        jr z,.lr1
        ld e,a
        dec e
        ld (hl),e
.lr1:   push hl
        ld de,0x80
        add hl,de
        inc a
        ld (hl),a
        pop hl
        inc hl
        cp 128
        jr c,.lr
        ld a,127
        ld (LRU_TAIL+SEL_A),a
        ld hl,SLOT_ID+SEL_A
        ld de,SLOT_ID+SEL_A+1
        ld (hl),0xFF
        ld bc,255
        ldir
        ld hl,ID_SLOT+SEL_A
        ld de,ID_SLOT+SEL_A+1
        ld (hl),0xFF
        ld bc,PAT_MAX-1
        ldir
        nextreg 0x51,83
        ld hl,0x2000
        ld de,0x2001
        ld (hl),0
        ld bc,0x5FF
        ldir
        nextreg 0x51,84
        ld hl,0x2000
        ld de,0x2001
        ld (hl),0
        ld bc,0x1FF
        ldir
        ld hl,0x3000            ; phase-1 headers
        ld de,0x3001
        ld (hl),0
        ld bc,0x5FF
        ldir
        ld hl,0
        ld (D_PATS),hl
        ld hl,0x0600
        ld (D_CPTR),hl
        ret

; Z = published.
drv_index:
        ld hl,(D_MAXY)
        ld de,(D_MINY)
        or a
        sbc hl,de
        inc l
        ld a,l
        ld (D_H),a
        xor a
        ld (D_CHN),a
        ld (D_CY),a
        ld hl,(D_CPTR)
        ld (D_CSTART),hl
.y:     xor a
        ld (D_CX),a
.x:     call drv_chunk
        jr nz,.out
        ld a,(D_CX)
        add a,2
        ld (D_CX),a
        ld hl,D_W
        cp (hl)
        jr c,.x
        ld a,(D_CY)
        add a,2
        ld (D_CY),a
        jr c,.ok                ; 256 tiles
        ld hl,D_H
        cp (hl)
        jr c,.y
.ok:    nextreg 0x51,83
        call drv_header
        ld a,(D_PHASE)
        or a
        jr z,.hd
        nextreg 0x51,84         ; phase-1 headers: page 84 at 1000
        ld de,0x1000
        add hl,de
.hd:    ex de,hl                ; DE = entry
        inc de
        ld a,(D_CHN)
        ld (de),a
        inc de
        ld hl,(D_CSTART)
        ld a,l
        ld (de),a
        inc de
        ld a,h
        ld (de),a
        inc de
        ld a,(D_MINX)
        ld (de),a
        inc de
        ld a,(D_MINY)
        ld (de),a
        dec de
        dec de
        dec de
        dec de
        dec de
        ld a,1
        ld (de),a
        xor a
.out:   push af
        nextreg 0x52,10
        pop af
        ret

; HL = 0x2000 + index * 6 (D_IMAGE, or A at drv_header_a)
drv_header:
        ld a,(D_IMAGE)
drv_header_a:
        ld e,a
        ld d,6
        mul d,e
        ld hl,0x2000
        add hl,de
        ret

; The duplicate's canonical entry at D_CANON (alias 0x2800 + 16 * image).
drv_dup_index:
        ld hl,(D_CANON)
        ld de,-0x2800
        add hl,de
        ld a,l
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        ld l,a
        ld a,h
        add a,a
        add a,a
        add a,a
        add a,a
        or l
        nextreg 0x51,83
        call drv_header_a
        push hl
        call drv_header
        ex de,hl
        pop hl
        push de
        inc hl
        inc de
        ld bc,5
        ldir
        pop de
        ld a,1
        ld (de),a
        call drv_header         ; the phase-1 header too, if the canonical has one
        ld bc,0x1000
        add hl,bc
        push hl
        ld hl,(D_CANON)
        ld bc,-0x2800
        add hl,bc
        ld a,l
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        ld l,a
        ld a,h
        add a,a
        add a,a
        add a,a
        add a,a
        or l
        call drv_header_a
        ld bc,0x1000
        add hl,bc               ; HL = the canonical's
        pop de                  ; DE = this image's, both in page 84
        nextreg 0x51,84
        ld bc,6
        ldir
        ret

; Second canvas of an image with a FLASH tile: colours swapped in those tiles. Failure leaves phase 0 only.
drv_phase1:
        ld a,(D_FANY)
        or a
        ret z
        ld a,1
        ld (D_PHASE),a
        call drv_clear
        call drv_tiles
        jr nz,.out
        call drv_fill
        jr nz,.out
        call drv_index
.out:   xor a
        ld (D_PHASE),a
        ret

; One chunk at (D_CX, D_CY) tiles. Z = ok (blank chunks emit nothing), NZ = capacity.
drv_chunk:
        ld hl,D_BUF
        ld de,D_BUF+1
        ld (hl),0
        ld bc,127
        ldir
        ld a,(D_W)
        ld e,a
        ld a,(D_CY)
        ld d,a
        mul d,e                 ; tiles above
        ex de,hl
        ld b,5
.s32:   add hl,hl
        djnz .s32
        ld a,(D_CX)
        ld e,a
        ld d,0
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,de
        ld (D_OFF),hl
        ld a,(D_H)
        ld hl,D_CY
        sub (hl)
        cp 2
        ld b,16
        jr nc,.rows
        ld b,8
.rows:  ld a,(D_W)              ; bytes of this chunk per row
        ld hl,D_CX
        sub (hl)
        cp 2
        ld c,8
        jr nc,.cw
        ld c,4
.cw:    ld de,D_BUF
.row:   push bc
        push de
        ld hl,(D_OFF)
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,112
        nextreg 0x51,a
        inc a
        nextreg 0x52,a
        ld a,h
        and 0x1F
        add a,0x20
        ld h,a
        ld b,0
        ldir
        ld hl,(D_OFF)
        ld de,(D_STRIDE)
        add hl,de
        ld (D_OFF),hl
        pop de
        ex de,hl
        ld bc,8
        add hl,bc
        ex de,hl
        pop bc
        djnz .row
        ld hl,D_BUF
        ld e,0                  ; cell mask
        ld d,1                  ; left-cell bit of this row
        ld b,16
.mr:    push bc
        ld c,d
        call .four
        sla c
        call .four
        pop bc
        ld a,b
        cp 9
        jr nz,.nd
        ld d,4
.nd:    djnz .mr
        ld a,e
        or a
        ret z                   ; blank (Z, nothing emitted)
        ld (D_ID),a
        ld hl,D_BUF
        ld b,128
        xor a
.h:     add a,(hl)
        inc hl
        djnz .h
        nextreg 0x51,84
        ld l,a
        ld h,0
        add hl,hl
        ld de,0x2000
        add hl,de
        ld (D_HEAD),hl
        ld e,(hl)
        inc hl
        ld d,(hl)
.chain: ld a,d
        or e
        jp z,.new
        dec de                  ; DE = id
        call .patmap            ; HL = pattern at slot 2
        push de
        ld de,D_BUF
        ld b,128
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.diff
        inc de
        inc hl
        djnz .cmp
        pop de
        jr .emit
.diff:  pop de
        ld hl,0x2200
        add hl,de
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        jr .chain
.new:   ld de,(D_PATS)
        ld hl,PAT_MAX
        or a
        sbc hl,de
        jp z,.full
        call .patmap
        ex de,hl
        push hl
        ld hl,D_BUF
        ld bc,128
        ldir
        pop de                  ; id
        ld hl,0x2200            ; next[id] = head, head = id + 1
        add hl,de
        add hl,de
        push hl
        ld hl,(D_HEAD)
        ld c,(hl)
        inc hl
        ld b,(hl)
        pop hl
        ld (hl),c
        inc hl
        ld (hl),b
        ld hl,(D_HEAD)
        inc de
        ld (hl),e
        inc hl
        ld (hl),d
        ld (D_PATS),de
        dec de
.emit:  ld a,(D_ID)
        ld c,a
        ld a,(D_CHN)
        inc a
        jr z,.full
        ld (D_CHN),a
        nextreg 0x51,83
        ld hl,(D_CPTR)
        ld a,h
        cp 0x1F
        jr nz,.room
        ld a,l
        cp 0xFB
        jr nc,.full
.room:  push hl
        ld a,h
        add a,0x20
        ld h,a
        ld a,(D_CX)
        ld (hl),a
        inc hl
        ld a,(D_CY)
        ld (hl),a
        inc hl
        ld (hl),c
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        pop hl
        ld de,5
        add hl,de
        ld (D_CPTR),hl
        xor a
        ret
.full:  or 1
        ret
.four:  ld a,(hl)               ; four bytes at HL; if any is non-zero, E |= C
        inc hl
        or (hl)
        inc hl
        or (hl)
        inc hl
        or (hl)
        inc hl
        ret z
        ld a,e
        or c
        ld e,a
        ret
.patmap:                        ; DE = id: slot 2 = its page, HL = its bytes
        ld a,e
        rlca
        rlca
        and 3
        ld l,a
        ld a,d
        add a,a
        add a,a
        or l
        add a,PAT_BASE
        nextreg 0x52,a
        ld a,e
        and 63
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,0x40
        ld h,a
        ret
driver_end:
        ASSERT driver_end < 0x1800
        SAVEBIN "inferno_driver.bin",driver,driver_end-driver

; Tail of page 81 (runs after a page swap at the same addresses).
        ORG 0x1D00
drvpage:
        ds 0x1D04-$,0
        ld sp,(D_CALLSP)        ; a worker's RET arrives here after its 1D00 NEXTREG
        ret
        ds 0x1D10-$,0
        nextreg 0x50,a          ; A = worker page; PC 1D13 continues in that page
        ds 0x1D84-$,0
        jp driver
        ds 0x1D90-$,0
        nextreg 0x50,68         ; back to page 68 at 1D94: RET to the gate
drvpage_end:
        SAVEBIN "inferno_drvpage.bin",drvpage,drvpage_end-drvpage

; Copied to 1D00 of each worker page (75, 76, 78, 79).
        ORG 0x1D00
drvworker:
        nextreg 0x50,81
        ds 0x1D13-$,0
        jp (hl)
drvworker_end:
        SAVEBIN "inferno_drvworker.bin",drvworker,drvworker_end-drvworker

; Page 68 entry stub for the gate's CALL 1D80.
        ORG 0x1D80
drv68:
        nextreg 0x50,81
        ds 0x1D94-$,0
        ret
drv68_end:
        SAVEBIN "inferno_drv68.bin",drv68,drv68_end-drv68

; Window dispatch (pipeline item 2), page 69 at 1800, runs inside the 8F95 coroutine after the scene
; compile: every CAP_LOG record is checked against the owned store (candidate entry, then exact live
; comparison with the stored stream). The first reader of CAP_LOG; nothing reads it earlier. A miss
; (no entry, changed bytes) ends the dispatch with DX_READY 0, as does unfinished work (3c drop).
; Polls every record, row and tile, inside the slice like the textmap's, so the slice margin holds.
DX_READY EQU 0x1EE0            ; 1 = every logged draw exactly matched (this capture)
DX_PTR   EQU 0x1EE1            ; next log record / live bytes during a yield
DX_LEFT  EQU 0x1EE3
DX_IMAGE EQU 0x1EE4
DX_BANK  EQU 0x1EE5
DX_BASE  EQU 0x1EE6
DX_SIZE  EQU 0x1EE8
DX_SP    EQU 0x1EEA
DX_PAGE  EQU 0x1EEC
DX_ROWS  EQU 0x1EED
DX_TL    EQU 0x1EEE
DX_N     EQU 0x1EEF            ; records matched
        ORG 0x1800
        MACRO DX_POLL target
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        sub iyl
        dec a
        jp m,target
        ENDM
        MACRO DX_BYTE           ; A against (DE), the serialized end bounded by its page
        ld c,a
        ld a,d
        cp 0x40
        jp nc,dx_miss
        ld a,(de)
        cp c
        jp nz,dx_miss
        ld a,c
        inc de
        ENDM
        MACRO DX_ROWB
        ld c,a
        ld a,(de)
        cp c
        jp nz,dx_miss
        ld a,c
        inc de
        ENDM
wk_dispatch:
        xor a
        ld (DX_READY),a
        ld (DX_N),a
        ld a,(F_SCENE_READY)
        or a
        ret z
        ld a,(0x2000+CAP_OVER)
        or a
        ret nz
        ld a,(0x2000+CAP_COUNT)
        ld (DX_LEFT),a
        ld hl,0x2000+CAP_LOG
        ld (DX_PTR),hl
        ld (DX_SP),sp
dx_rec: DX_POLL dx_yrec
dx_rec_go:
        ld a,(DX_LEFT)
        or a
        jr nz,.more
        inc a
        ld (DX_READY),a
        ret
.more:  dec a
        ld (DX_LEFT),a
        nextreg 0x51,68
        ld hl,(DX_PTR)
        ld bc,4
        add hl,bc
        ld a,(hl)
        ld (DX_IMAGE),a
        ld bc,2
        add hl,bc
dx_lrow:
        DX_POLL dx_ylrow
dx_lrow_go:
        ld a,(hl)
        inc hl
        or a
        jr z,.end
        add a,2                 ; dx, dy, then width tile bytes (width <= 128 from the capture)
        add hl,a
        jr dx_lrow
.end:   ld (DX_PTR),hl
        nextreg 0x51,79         ; the candidate entry, indexed by the drawn image
        ld a,(DX_IMAGE)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,0x2800
        add hl,bc
        ld a,(hl)
        cp 1
        jp nz,dx_miss
        inc hl
        ld a,(hl)
        ld (DX_BANK),a
        inc hl
        ld e,(hl)
        inc hl
        ld a,(hl)
        add a,0x20
        ld d,a
        ld (DX_BASE),de
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (DX_SIZE),de
        ld bc,6
        add hl,bc
        ld a,(hl)               ; FLASH phase and paint generation: phase 0, generation 0 only
        inc hl
        or (hl)
        inc hl
        or (hl)
        jp nz,dx_miss
        ld a,(DX_BANK)
        nextreg 0x51,a
        ld a,(DX_IMAGE)
        ld l,a
        ld h,0xC1
        ld c,(hl)
        inc l                   ; original C1FF -> C100 wrap
        ld b,(hl)
        ld h,b
        ld l,c
        ld a,h
        cp 0x40
        jp c,dx_miss
        ld de,(DX_BASE)
        ld a,(hl)
        DX_BYTE
        and 3
        ld (DX_PAGE),a
        inc hl
        xor a
        ld (DX_ROWS),a
dx_row: call dx_address
        ld a,(hl)
        inc hl
        DX_BYTE
        or a
        jp z,dx_end
        cp 129
        jp nc,dx_miss
        ld (DX_TL),a
        push hl
        push de
        ld e,a
        ld d,10
        mul d,e
        ld hl,1
        add hl,de
        pop de
        add hl,de
        ld a,h
        cp 0x40
        jp nc,dx_miss
        pop hl
        push de
        ld a,(DX_TL)
        ld e,a
        ld d,0
        inc de
        ex de,hl
        add hl,de
        jp c,dx_miss
        ld a,h
        cp 0x40
        jp c,dx_miss
        ex de,hl
        pop de
        ld a,(hl)
        inc hl
        DX_ROWB
        ld a,(hl)
        inc hl
        DX_ROWB
dx_tile:
        DX_POLL dx_ytile
dx_tile_go:
        ld a,(hl)
        inc hl
        DX_ROWB
        push hl
        ld l,a
        ld a,(DX_PAGE)
        ld h,a
        push hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,0xDC00
        add hl,bc
        DUP 8
        ld a,(de)
        cp (hl)
        jp nz,dx_miss
        inc de
        inc hl
        EDUP
        pop hl
        ld bc,0xFC00
        add hl,bc
        ld a,(hl)
        DX_ROWB
        pop hl
        ld a,(DX_TL)
        dec a
        ld (DX_TL),a
        jp nz,dx_tile
        ld a,(DX_ROWS)
        dec a
        ld (DX_ROWS),a
        jp nz,dx_row
        jp dx_miss
dx_address:
        ld a,h
        cp 0x40
        ret nc
        jp dx_miss
dx_end: ex de,hl
        ld de,(DX_BASE)
        or a
        sbc hl,de
        ld de,(DX_SIZE)
        or a
        sbc hl,de
        jp nz,dx_miss
        nextreg 0x51,68
        ld hl,DX_N
        inc (hl)
        jp dx_rec
dx_miss:
        ld sp,(DX_SP)
        nextreg 0x51,68
        ret
; Yields: HL may be live at a poll, so it rides on the work stack; slot 1 is remapped on resume.
dx_yrec:
        ld hl,dx_rec_go
        jp wk_yield
dx_ylrow:
        push hl
        ld hl,.resume
        jp wk_yield
.resume:
        pop hl
        jp dx_lrow_go
dx_ytile:
        push hl
        ld hl,.resume
        jp wk_yield
.resume:
        pop hl
        ld a,(DX_BANK)
        nextreg 0x51,a
        jp dx_tile_go
wk_dispatch_end:
        ASSERT wk_dispatch_end <= 0x1A00
        SAVEBIN "inferno_cwdx.bin",wk_dispatch,wk_dispatch_end-wk_dispatch

; Pattern selection and protected store (pipeline item 3; 128 slots, the 4-bit halves of pattern RAM). Page 82 in slot 2, inside the 8F95 coroutine after
; dispatch; WK_M2 = 82 so wk_resume maps it. For every draw, the non-blank chunks with an on-screen cell go to
; the frame list (slot, column, row) and to a 64-slot store (least recently used; slots in the
; current, pending or building mask are never evicted; list walk from the oldest, O(1) per use). No free slot or > 128 chunks = not ready. Commit is
; one byte (role rotation), so work dropped at any poll leaves current/pending untouched. SEL_READY is
; meaningful only with DX_READY (cleared on the 8F95 drop path). FLASH phase 0 only (as the store).
SEL_A     EQU -0x2000          ; alias of the page-82 state through slot 1 (load time)
SEL_READY EQU 0x5000
SEL_ROLE  EQU 0x5001           ; bits 0-1 current, 2-3 pending, 4-5 building: mask index
SEL_N     EQU 0x5004
SEL_LEFT  EQU 0x5005
SEL_PTR   EQU 0x5006
SEL_SP    EQU 0x5008
SEL_M1    EQU 0x500A
SEL_X     EQU 0x500B
SEL_Y     EQU 0x500C
SEL_IMAGE EQU 0x500D
SEL_C     EQU 0x500E
SEL_L     EQU 0x500F
SEL_MASKS EQU 0x5060           ; 3 x 16 bytes
SEL_T     EQU 0x5028
SEL_BM    EQU 0x5042           ; word: the building mask
SEL_LP    EQU 0x5044           ; word: next list entry
SEL_QN    EQU 0x5046           ; upload queue length
SEL_QI    EQU 0x5047
SEL_UPB   EQU 0x5048           ; bursts left of this pattern
SEL_UPHL  EQU 0x5049           ; word: source
SEL_UPS   EQU 0x504B           ; its slot
SEL_DIRTY EQU 0x504C           ; slots with SLOT_FLAG set (the hit path reads flags only when non-zero)
SEL_INIT  EQU 0x504D           ; sprite layer set up (cleared by the 8EF9 reset)
SEL_PREV  EQU 0x504E           ; sprites written by the last publish
SEL_PUBN  EQU 0x504F
SEL_PUBP  EQU 0x5050
SEL_TICK  EQU 0x5054           ; committed updates; bit 2 = FLASH phase (the ULA swaps every 16 frames, an update is about 4)
SEL_PUBQ  EQU 0x5052           ; next attribute byte in the Copper program (page 74 at slot 1)
SEL_Q     EQU 0x5A00           ; 128 slots to upload (256-aligned; a slot may repeat)
SEL_HL    EQU 0x5029
SEL_COL   EQU 0x502B
SEL_ROW   EQU 0x502C
SEL_ID    EQU 0x502D
SEL_U     EQU 0x5090           ; 16 bytes: union of the masks for one allocation
SEL_I     EQU 0x5038
SEL_NEW   EQU 0x503C           ; patterns allocated this build (for reports)
SEL_EVICT EQU 0x503D           ; evictions this build
SLOT_ID   EQU 0x5100           ; 128 x word, FFFF empty
SLOT_FLAG EQU 0x5200           ; 128: 1 = pattern not uploaded
SLOT_PREV EQU 0x5280           ; recency list, 128 = none
SLOT_NEXT EQU 0x5300
LRU_HEAD  EQU 0x5040           ; oldest
LRU_TAIL  EQU 0x5041           ; newest
ID_SLOT   EQU 0x5400           ; PAT_MAX bytes, FF none
SEL_LIST  EQU 0x5800           ; 128 x (slot, column, row)
        ORG 0x4000
        MACRO SL_POLL target
        ld a,CW_CTC >> 8
        in a,(CW_CTC & 0xFF)
        sub iyl
        dec a
        jp m,target
        ENDM
wk_select:
        xor a
        ld (SEL_READY),a
        ld (SEL_N),a
        ld (SEL_NEW),a
        ld (SEL_EVICT),a
        ld (SEL_QN),a
        ld a,(DX_READY)
        or a
        ret z
        nextreg 0x51,68
        ld a,68
        ld (SEL_M1),a
        ld (SEL_SP),sp
        call sl_build_mask
        ld (SEL_BM),hl
        ld de,SEL_LIST
        ld (SEL_LP),de
        xor a
        DUP 16
        ld (hl),a
        inc hl
        EDUP
        ld a,(0x2000+CAP_COUNT)
        ld (SEL_LEFT),a
        ld hl,0x2000+CAP_LOG
        ld (SEL_PTR),hl
sl_rec: SL_POLL sl_yrec
sl_rec_go:
        ld a,(SEL_LEFT)
        or a
        jp z,sl_upload
        dec a
        ld (SEL_LEFT),a
        nextreg 0x51,68
        ld a,68
        ld (SEL_M1),a
        ld hl,(SEL_PTR)
        inc hl
        inc hl
        ld a,(hl)
        ld (SEL_X),a
        inc hl
        ld a,(hl)
        ld (SEL_Y),a
        inc hl
        ld a,(hl)
        ld (SEL_IMAGE),a
        inc hl
        inc hl
sl_lrow:
        SL_POLL sl_ylrow
sl_lrow_go:
        ld a,(hl)
        inc hl
        or a
        jr z,.end
        add a,2
        add hl,a
        jr sl_lrow
.end:   ld (SEL_PTR),hl
        nextreg 0x51,83
        ld a,83
        ld (SEL_M1),a
        ld a,(SEL_IMAGE)
        ld e,a
        ld d,6
        mul d,e
        ld a,(SEL_TICK)
        and 4
        jr z,.p0
        nextreg 0x51,84         ; FLASH phase 1: its own header, if the image flashes
        ld hl,0x3000
        add hl,de
        ld a,(hl)
        cp 1
        jr z,.hdr
.p0:    nextreg 0x51,83
        ld hl,0x2000
        add hl,de
        ld a,(hl)
        cp 1
        jp nz,sl_fail
.hdr:   inc hl
        ld a,(hl)
        ld (SEL_C),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(SEL_X)            ; per record: column and row of the image origin
        add a,(hl)
        ld (SEL_L),a
        inc hl
        ld a,(SEL_Y)
        add a,(hl)
        ld (SEL_T),a
        nextreg 0x51,83
        ld a,d
        add a,0x20
        ld h,a
        ld l,e
sl_chunk:
        ld a,(SEL_C)
        or a
        jp z,sl_rec
        dec a
        ld (SEL_C),a
        SL_POLL sl_ychunk
sl_chunk_go:
        ld a,(SEL_L)
        add a,(hl)
        ld b,a                  ; column of the chunk's left cell
        inc hl
        ld a,(SEL_T)
        add a,(hl)
        ld c,a                  ; row of its top cell
        inc hl
        ld e,(hl)               ; cell mask
        inc hl
        ld a,b                  ; all four cells on screen and the chunk is non-blank: visible
        cp 31
        jr nc,.edge
        ld a,c
        cp 17
        jr c,.visible
.edge:
        ld d,0
        ld a,b
        cp 32
        jr nc,.c1
        ld d,0b0101
.c1:    ld a,b
        inc a
        cp 32
        jr nc,.r0
        ld a,d
        or 0b1010
        ld d,a
.r0:    ld a,c
        cp 18
        jr c,.r1
        ld a,d
        and 0b1100
        ld d,a
.r1:    ld a,c
        inc a
        cp 18
        jr c,.vis
        ld a,d
        and 0b0011
        ld d,a
.vis:   ld a,d
        and e
        jr nz,.visible
        inc hl
        inc hl
        jp sl_chunk
.visible:
        ld a,b
        ld (SEL_COL),a
        ld a,c
        ld (SEL_ROW),a
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (SEL_HL),hl
        ld (SEL_ID),de
        ld hl,ID_SLOT
        add hl,de
        ld a,(hl)
        cp 0xFF
        jp z,sl_alloc
sl_have:                        ; A = slot; atomic: no poll until the next chunk
        ld c,a
        rrca
        rrca
        rrca
        and 15
        ld hl,(SEL_BM)
        add hl,a
        ld a,c
        and 7
        add a,sl_bits & 0xFF
        ld e,a
        ld d,sl_bits >> 8
        ld a,(de)
        or (hl)
        ld (hl),a
        call sl_touch
        ld a,(SEL_N)
        cp 128
        jp nc,sl_fail
        inc a
        ld (SEL_N),a
        ld hl,(SEL_LP)
        ld (hl),c
        inc hl
        ld a,(SEL_COL)
        ld (hl),a
        inc hl
        ld a,(SEL_ROW)
        ld (hl),a
        inc hl
        ld (SEL_LP),hl
        ld a,(SEL_DIRTY)        ; nothing awaits upload: skip the flag
        or a
        jr z,.clean
        ld b,0                  ; not uploaded yet: queue it
        ld hl,SLOT_FLAG
        add hl,bc
        ld a,(hl)
        or a
        jr z,.clean
        ld a,(SEL_QN)
        ld e,a
        inc a
        ld (SEL_QN),a
        ld d,SEL_Q >> 8
        ld a,c
        ld (de),a
.clean: ld hl,(SEL_HL)
        jp sl_chunk
sl_alloc:
        ld a,(LRU_HEAD)
        ld (SEL_I),a
sl_scan:
        SL_POLL sl_yscan
sl_scan_go:
        ld a,(SEL_I)
        cp 128
        jp nc,sl_fail           ; every slot protected: over capacity
        ld c,a
        rrca
        rrca
        rrca
        and 15
        ld e,a
        ld d,0
        ld hl,SEL_MASKS         ; this slot's byte of current | pending | building
        add hl,de
        ld a,(hl)
        ld de,16
        add hl,de
        or (hl)
        add hl,de
        or (hl)
        ld (SEL_U),a
        ld a,c
        call sl_bit_a
        ld hl,SEL_U
        and (hl)
        jr z,sl_take
        ld l,c                  ; protected: on to the next oldest
        ld h,SLOT_NEXT >> 8
        ld a,(hl)
        ld (SEL_I),a
        jp sl_scan
sl_take:
        ld a,c                  ; evict the old owner, atomic with the new owner
        add a,a
        ld l,a
        ld h,0
        ld de,SLOT_ID
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,d
        and e
        inc a
        jr z,.empty
        push hl
        ld hl,ID_SLOT
        add hl,de
        ld (hl),0xFF
        pop hl
        ld a,(SEL_EVICT)
        inc a
        ld (SEL_EVICT),a
.empty: ld de,(SEL_ID)
        ld (hl),d
        dec hl
        ld (hl),e
        ld hl,ID_SLOT
        add hl,de
        ld (hl),c
        ld b,0
        ld hl,SLOT_FLAG
        add hl,bc
        ld a,(hl)
        or a
        jr nz,.was
        ld (hl),1
        ld hl,SEL_DIRTY
        inc (hl)
.was:
        ld a,(SEL_NEW)
        inc a
        ld (SEL_NEW),a
        ld a,c
        jp sl_have
; C = slot: move it to the newest end of the recency list.
sl_touch:
        ld a,(LRU_TAIL)
        cp c
        ret z
        ld h,SLOT_PREV >> 8
        ld a,c
        add a,0x80
        ld l,a
        ld d,(hl)               ; D = previous
        ld h,SLOT_NEXT >> 8
        ld l,c
        ld e,(hl)               ; E = next (not 128: the slot is not the tail)
        ld a,d
        cp 128
        jr nz,.mid
        ld a,e
        ld (LRU_HEAD),a
        jr .link
.mid:   ld l,d                  ; next[D] = E
        ld (hl),e
.link:  ld h,SLOT_PREV >> 8     ; prev[E] = D
        ld a,e
        add a,0x80
        ld l,a
        ld (hl),d
        ld a,(LRU_TAIL)
        ld b,a
        ld h,SLOT_NEXT >> 8     ; next[old tail] = C
        ld l,b
        ld (hl),c
        ld h,SLOT_PREV >> 8     ; prev[C] = old tail
        ld a,c
        add a,0x80
        ld l,a
        ld (hl),b
        ld h,SLOT_NEXT >> 8     ; next[C] = none
        ld l,c
        ld (hl),128
        ld a,c
        ld (LRU_TAIL),a
        ret
; CPU upload of the queue to pattern RAM (4-bit: pattern = slot), bursts of 16 between polls. A pattern's flag
; clears only after its last burst, so a drop restarts that pattern and keeps the finished ones.
sl_upload:
        xor a
        ld (SEL_QI),a
sl_up_next:
        SL_POLL sl_yupn
sl_up_nextgo:
        ld a,(SEL_QI)
        ld hl,SEL_QN
        cp (hl)
        jp z,sl_commit
        ld l,a
        inc a
        ld (SEL_QI),a
        ld h,SEL_Q >> 8
        ld c,(hl)
        ld b,0
        ld hl,SLOT_FLAG
        add hl,bc
        ld a,(hl)
        or a
        jp z,sl_up_next
        ld a,c
        ld (SEL_UPS),a
        add a,a
        ld l,a
        ld h,0
        ld de,SLOT_ID
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,e                  ; page of the pattern
        rlca
        rlca
        and 3
        ld l,a
        ld a,d
        add a,a
        add a,a
        or l
        add a,PAT_BASE
        ld (SEL_M1),a
        nextreg 0x51,a
        ld a,e
        and 63
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,0x20
        ld h,a
        ld (SEL_UPHL),hl
        ld a,c                  ; pattern select: slot >> 1, bit 7 = its 128-byte half
        rrca
        and 0x80
        ld e,a
        ld a,c
        srl a
        or e
        ld bc,0x303B
        out (c),a
        ld a,8
        ld (SEL_UPB),a
sl_up_burst:
        SL_POLL sl_yup
sl_up_go:
        ld hl,(SEL_UPHL)
        ld bc,0x105B
        otir
        ld (SEL_UPHL),hl
        ld hl,SEL_UPB
        dec (hl)
        jp nz,sl_up_burst
        ld a,(SEL_UPS)
        ld c,a
        ld b,0
        ld hl,SLOT_FLAG
        add hl,bc
        ld (hl),0
        ld hl,SEL_DIRTY
        dec (hl)
        jp sl_up_next
sl_yupn:
        ld hl,.resume
        jp wk_yield
.resume:
        ld a,(SEL_M1)
        nextreg 0x51,a
        jp sl_up_nextgo
sl_yup:
        ld hl,.resume
        jp wk_yield
.resume:
        ld a,(SEL_M1)
        nextreg 0x51,a
        jp sl_up_go
sl_commit:                      ; roles rotate in one byte
        ld hl,SEL_TICK
        inc (hl)
        ld a,(SEL_ROLE)
        ld b,a
        rrca
        rrca
        and 0b00001111          ; new current = old pending; new pending = old building
        ld d,a
        ld a,b
        and 3
        rlca
        rlca
        rlca
        rlca
        or d
        ld (SEL_ROLE),a
        ld a,1
        ld (SEL_READY),a
; Publish: attributes go into the Copper program, committed at line 224 with the scenery map by queue_frame (980B hook).
sl_publish:
        ld a,(SEL_INIT)
        or a
        call z,sl_init
        nextreg 0x51,74
        ld a,74
        ld (SEL_M1),a
        ld a,(SEL_N)
        ld (SEL_PUBN),a
        ld hl,SEL_LIST
        ld (SEL_PUBP),hl
        ld hl,0x2005            ; program + 2: first entry's attr 0 value
        ld (SEL_PUBQ),hl
sl_pub:
        SL_POLL sl_ypub
sl_pub_go:
        ld a,(SEL_PUBN)
        or a
        jp z,sl_ready
        dec a
        ld (SEL_PUBN),a
        ld hl,(SEL_PUBP)
        ld a,(hl)
        ld (SEL_UPS),a
        inc hl
        ld e,(hl)               ; column
        inc hl
        ld c,(hl)               ; row
        inc hl
        ld (SEL_PUBP),hl
        ld l,e                  ; X = signed column * 8 + 32
        ld a,e
        rla
        sbc a,a
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld a,c                  ; Y = 32 + 48 + row * 8
        add a,a
        add a,a
        add a,a
        add a,80
        ld c,a
        ld de,(SEL_PUBQ)
        ld a,l
        ld (de),a
        inc de
        inc de
        ld a,c
        ld (de),a
        inc de
        inc de
        ld a,h
        and 1
        ld (de),a
        inc de
        inc de
        ld a,(SEL_UPS)
        srl a
        or 0xC0
        ld (de),a
        inc de
        inc de
        ld a,(SEL_UPS)
        rrca
        and 0x80
        rrca
        or 0x80
        ld (de),a
        ld hl,(SEL_PUBQ)
        ld de,12
        add hl,de
        ld (SEL_PUBQ),hl
        jp sl_pub
sl_ready:
        ld a,(T_HALF)
        ld (Q_TARGET),a
        ld a,(SEL_N)
        ld (Q_COUNT),a
        xor a
        ld (Q_CONTROL),a
        inc a
        ld (Q_READY),a
        nextreg 0x51,68
        ret
sl_ypub:
        ld hl,.resume
        jp wk_yield
.resume:
        ld a,(SEL_M1)
        nextreg 0x51,a
        jp sl_pub_go
sl_init:
        nextreg 0x4B,0          ; 4-bit transparency index
        nextreg 0x1C,2          ; sprite clip index
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,48         ; figures never cover the HUD
        nextreg 0x19,191
        nextreg 0x43,0x20       ; sprite palette 1
        nextreg 0x40,0
        ld hl,sl_palette
        ld b,16
.p:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .p
        nextreg 0x43,0
        ld a,1
        ld (SEL_INIT),a
        ret
sl_palette:                     ; 0 transparent, 1 black, 2-8 normal, 9-15 bright (solid_image)
        db 0,0,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
sl_fail:
        ld sp,(SEL_SP)
        nextreg 0x51,68
        ret
sl_build_mask:                  ; HL = the building mask
        ld a,(SEL_ROLE)
        rrca
        rrca
        rrca
        rrca
        and 3
        add a,a
        add a,a
        add a,a
        add a,a
        ld hl,SEL_MASKS
        add hl,a
        ret
sl_bit_a:
        and 7
        ld b,a
        ld a,1
        jr z,.z
.s:     add a,a
        djnz .s
.z:     ret
sl_bits:
        db 1,2,4,8,16,32,64,128
        ASSERT (sl_bits & 0xFF) < 0xF8
sl_yrec:
        ld hl,sl_rec_go
        jp wk_yield
sl_ylrow:
        push hl
        ld hl,.resume
        jp wk_yield
.resume:
        pop hl
        jp sl_lrow_go
sl_ychunk:
        push hl
        ld hl,.resume
        jp wk_yield
.resume:
        pop hl
        ld a,(SEL_M1)
        nextreg 0x51,a
        jp sl_chunk_go
sl_yscan:
        ld hl,.resume
        jp wk_yield
.resume:
        ld a,(SEL_M1)
        nextreg 0x51,a
        jp sl_scan_go
wk_select_end:
        ASSERT wk_select_end <= 0x5000
        SAVEBIN "inferno_cwsel.bin",wk_select,wk_select_end-wk_select

; Leaving gameplay in the sprite builds (death, break): 901C, after the game's own LD SP,nn (9019 is self-modified, its
; operand is written at run time, so it cannot carry a patch). Hides the new layers; the next complete publish restores them.
        ORG 0x3BE0
modal_exit:
        di
        nextreg 0x07,3
        nextreg 0x50,68
        ld (CAP_SP),sp
        ld sp,CAP_STACK
        push af
        push bc
        nextreg 0x62,0
        ld bc,0x243B
        ld a,0x6B
        ds 0x3BFD-$,0           ; the intro's IM 2 vector (I = 3B) lives at 3BFF: it must stay FF FF
        jr 0x3C01
        db 0xFF,0xFF
        ASSERT $ == 0x3C01
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
        nextreg 0x52,69         ; slot 2: this code runs in slot 1
        xor a
        ld (0x4000+Q_BUSY),a
        nextreg 0x52,10
        ld (CAP_PHASE),a
        pop bc
        pop af
        ld sp,(CAP_SP)
        nextreg 0x50,255
        nextreg 0x07,0
        ld iy,0x5C3A
        jp 0x9020
modal_exit_end:
        ASSERT modal_exit_end <= 0x3C40
        SAVEBIN "inferno_modalx.bin",modal_exit,modal_exit_end-modal_exit

; 980B site: the stub stays in the alt ROM because page 80 cannot be mapped before it runs.
        ORG 0x3B90
wo_hook:
        di
        nextreg 0x07,3
        nextreg 0x50,CW_PAGE
        jp wo_go
wo_queue:                       ; page 69 at slot 0 (this stub runs from the alt ROM at slot 1)
        nextreg 0x50,69
        ld a,(Q_READY)
        or a
        call nz,queue_frame
        nextreg 0x50,CW_PAGE
        ret
wo_out:
        nextreg 0x50,255
        nextreg 0x07,0
        jp 0x9877
wo_orig:
        nextreg 0x50,255
        nextreg 0x07,0
        jp 0x980C
wo_hook_end:
        ASSERT wo_hook_end <= 0x3BD0
        SAVEBIN "inferno_wohook.bin",wo_hook,wo_hook_end-wo_hook

; Full game: BASIC's second USR 24200 comes here (15312) once the main code is decompressed; the table in page 80 at 1C00
; holds the hook bytes (count, address, bytes; 0 ends).
        ORG 0x3BD0
wi_stub:
        di
        nextreg 0x50,CW_PAGE
        jp wi_go
wi_back:
        nextreg 0x50,255
        ei
        jp 24200
wi_stub_end:
        ASSERT wi_stub_end <= 0x3BE0
        SAVEBIN "inferno_wistub.bin",wi_stub,wi_stub_end-wi_stub

; SAVE/LOAD: the pilot record (49 bytes at 5B15, name at 7001) goes to named slots in page 120, not to tape.
; Both routines replace ROM tape code in the alt ROM's low page and run in slot 0, so they may use slot 1.
SAVE_PAGE   EQU 123
SAVE_NAME   EQU 0x7001
SAVE_SIZE   EQU 49
SAVE_STEP   EQU 64          ; slot: 8 name bytes (0 = empty), 49 data bytes, pad
        ORG 0x04C6              ; the game's CALL 04C6 (SA-BYTES past its return-address push)
save_hook:
        or a
        ret z                   ; header block: the name is taken from 7001 with the data
        di
        call save_find
        ex de,hl
        ld hl,SAVE_NAME
        ld bc,8
        ldir
        push ix
        pop hl
        ld bc,SAVE_SIZE
        ldir
        nextreg 0x51,255
        ret                     ; the game's 72B8 follows with EI

save_find:                      ; -> HL = slot; NZ found, Z free (or the last slot when full). Uses A, BC, DE.
        nextreg 0x51,SAVE_PAGE
        ld hl,0x2000
        ld b,128
.next:  ld a,(hl)
        or a
        ret z
        push hl
        ld de,SAVE_NAME
        ld c,8
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.other
        inc de
        inc hl
        dec c
        jr nz,.cmp
        pop hl
        or 1
        ret
.other: pop hl
        ld de,SAVE_STEP
        add hl,de
        djnz .next
        ld de,-SAVE_STEP
        add hl,de
        xor a
        ret
save_hook_end:
        ASSERT save_hook_end <= 0x053F
        SAVEBIN "inferno_savehook.bin",save_hook,save_hook_end-save_hook

        ORG 0x0574              ; past 056B, where JNext's tape trap rewrites A; 0562 jumps here
load_front:
        push af
        push hl
        ld hl,(0x738A)          ; the game's file name pointer: 7001 for LOAD, 732F for levels
        ld a,h
        cp high SAVE_NAME
        jr nz,.tape
        ld a,l
        cp low SAVE_NAME
.tape:  pop hl
        jr z,.user
        pop af
        jp loader
.user:  pop af
        push de                 ; 17 for the header request, 49 for the data
        call save_find
        pop bc
        jr nz,.found
        nextreg 0x51,255
        jp 0x7227               ; no such pilot: the game's tape error, which resets the stack
.found: push ix
        pop de
        ld a,c
        cp 17
        jr nz,.data
        ld a,3                  ; synthesise the header the game checks (type, name, length)
        ld (de),a
        inc de
        ld bc,8
        ldir
        ld a,' '
        ld (de),a
        inc de
        ld (de),a
        inc de
        ld a,SAVE_SIZE
        ld (de),a
        inc de
        xor a
        ld (de),a
        jr .done
.data:  ld a,l
        add a,8
        ld l,a
        ld bc,SAVE_SIZE
        ldir
.done:  nextreg 0x51,255
        scf                     ; loaded
        ret
load_front_end:
        ASSERT load_front_end <= 0x05E3
        SAVEBIN "inferno_loadfront.bin",load_front,load_front_end-load_front

; English build: text tables (count16, dest16, bytes; count 0 ends) in pages 118 (main), 119 (intro), 124-127 (levels).
        ORG 0x050E              ; after save_hook, in the old SA-BYTES and LD-BYTES entry code
en_level:                       ; 718F, after the level block is unpacked
        ld a,i
        push af
        di
        ld a,(0x7335)
        sub '0'
        ld c,a
        srl a
        add a,124
        ld hl,0x2000
        bit 0,c
        jr z,.even
        ld h,0x30
.even:  call en_apply
        pop af
        jp po,.off
        ei
.off:   ld a,(0x7335)
        jp 0x7192
en_apply:                       ; A = page, HL = table in slot 1; slot 1 is put back as found
        ld e,a
        ld bc,0x243B
        ld a,0x51
        out (c),a
        inc b
        in a,(c)
        push af
        ld a,e
        nextreg 0x51,a
.next:  ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        jr z,.done
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ldir
        jr .next
.done:  pop af
        nextreg 0x51,a
        ret
en_level_end:
        ASSERT en_level_end <= 0x0562
        SAVEBIN "inferno_enlevel.bin",en_level,en_level_end-en_level

        ORG 0x05C5              ; after load_front; replaces JP 24200 in wi_back
en_start:
        di
        ld a,118
        ld hl,0x2000
        call en_apply
        ld a,119
        ld hl,0x2000
        call en_apply
        ei
        jp 24200
en_start_end:
        ASSERT en_start_end <= 0x05E3
        SAVEBIN "inferno_enstart.bin",en_start,en_start_end-en_start

; English story screens: after the level picture is drawn, its text bytes come from pages 127 and 121
        ORG 0x0558
en_story:                       ; replaces CALL C350 at 7166
        call 0xC350
        ld a,(0x7335)
        sub '0'
        jr en_story2
en_story_end:
        ASSERT en_story_end <= 0x0562
        SAVEBIN "inferno_enstory.bin",en_story,en_story_end-en_story
        ORG 0x05DA
en_story2:                      ; A = level: pages 127 (0-2) and 121 (3-5), table at (slot+1)*0x800
        cp 6
        ret nc
        ld b,127
        cp 3
        jr c,.low
        sub 3
        ld b,121
.low:   inc a
        rlca
        rlca
        rlca
        add a,0x20
        ld h,a
        ld l,0
        ld a,b
        jp en_apply
en_story2_end:
        SAVEBIN "inferno_enstory2.bin",en_story2,en_story2_end-en_story2
