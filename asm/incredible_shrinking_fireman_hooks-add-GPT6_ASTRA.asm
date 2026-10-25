; Incredible Shrinking Fireman — isolated add-GPT6_ASTRA runtime.
; Plotter XOR bitmap stores are removed; the original attribute painter is retained because
; game logic reads attributes. Draw/clear hooks change flags only and preserve IRQ-visible state.
; ISR hook uploads 4-bit patterns with interrupts off, using 28MHz only during sprite update.
; Source ink selects one of sixteen pre-expanded colour tables (3 pages each, Next pages32..79).
; MMU6 maps a display page only during cvt and restores page0 before returning to the game.
; Palette0 is fixed. Cache keys include frame and source ink. Two 16x16 patterns cover 16x24.
; Diamond pattern6 is uploaded at setup. Virtual reads reconstruct diamond bytes then moving
; XOR images, so painting cannot alter collisions. Exactly coincident identical enemies hide.
; The IM2 vector at39FF/3A00 remains FFFF; all hook code/register data stays below3D00.
; All patch original bytes are checked by incredible_shrinking_fireman_add_GPT6_ASTRA.py.

        DEVICE ZXSPECTRUMNEXT

HS      EQU 0xF400              ; hook state (zero span the game never touches): SHOW[3], SHOWD[5], LASTF[3]
SHOWD   EQU HS + 3
LASTINK EQU HS + 12
LASTF   EQU HS + 8
SLOTS   EQU 48375
PAT_DIA EQU 6

        ORG 0x386E              ; the free ROM span starts here; 0x39FF / 0x3A00 stay FF FF (IM 2 vector)

; ---- virtual read: the game's ground test reads screen bytes the figures used to XOR into. ----
; vrd: DE = screen byte address -> A = (DE) ^ every shown slot's image byte there, flags = AND A.
; Everything else is preserved (the sites go on with INC DE).
vrd:    push bc
        push de
        push hl
        ld a,d
        and 0x18
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,d
        and 7
        or b
        ld b,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or b
        ld b,a                  ; B = pixel row
        ld a,e
        and 31
        ld c,a                  ; C = byte column
        call diamond_read
        push af                 ; accumulator
        ld a,(HS + 0)
        or a
        jr z,.s0
        ld hl,SLOTS + 0
        ld a,(hl)               ; x
        inc hl
        ld d,a
        ld a,b
        sub (hl)                ; r = y - slot y
        cp 24
        jr nc,.s0
        add a,a
        ld e,a                  ; D = x, E = 2r
        inc hl
        ld a,(hl)               ; frame
        push bc
        push de
        ld e,a
        add a,a
        add a,e                 ; 3 * frame, 8 bits wide like the game's own address (47742)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; * 16
        ld de,(48450)
        add hl,de
        pop de
        ld a,l
        add a,e
        ld l,a
        jr nc,.a0
        inc h
.a0:   ld a,d
        rrca
        rrca
        rrca
        and 31
        ld e,a                  ; x >> 3
        ld a,c
        sub e                   ; k = byte column inside the 3 bytes
        cp 3
        jr c,.k0
        pop bc
        jr .s0
.k0:   ld e,a
        ld a,(hl)
        inc hl
        ld l,(hl)
        ld h,a                  ; HL = row word
        ld a,d
        and 7
        ld b,a                  ; t = x & 7
        ex de,hl                ; DE = word, L = k
        ld a,l
        or a
        jr z,.z0
        dec a
        jr z,.o0
        ld a,8                  ; k = 2: (word << (8 - t)) low byte
        sub b
        ld b,a
        bsla de,b
        jr .g0
.z0:   ld a,b                  ; k = 0: word >> (8 + t)
        add a,8
        ld b,a
.o0:   bsrl de,b               ; k = 1: word >> t
.g0:   ld a,e
        ld hl,3
        add hl,sp
        xor (hl)
        ld (hl),a               ; accumulator (A of the saved AF)
        pop bc
.s0:
        ld a,(HS + 1)
        or a
        jr z,.s1
        ld hl,SLOTS + 8
        ld a,(hl)               ; x
        inc hl
        ld d,a
        ld a,b
        sub (hl)                ; r = y - slot y
        cp 24
        jr nc,.s1
        add a,a
        ld e,a                  ; D = x, E = 2r
        inc hl
        ld a,(hl)               ; frame
        push bc
        push de
        ld e,a
        add a,a
        add a,e                 ; 3 * frame, 8 bits wide like the game's own address (47742)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; * 16
        ld de,(48450)
        add hl,de
        pop de
        ld a,l
        add a,e
        ld l,a
        jr nc,.a1
        inc h
.a1:   ld a,d
        rrca
        rrca
        rrca
        and 31
        ld e,a                  ; x >> 3
        ld a,c
        sub e                   ; k = byte column inside the 3 bytes
        cp 3
        jr c,.k1
        pop bc
        jr .s1
.k1:   ld e,a
        ld a,(hl)
        inc hl
        ld l,(hl)
        ld h,a                  ; HL = row word
        ld a,d
        and 7
        ld b,a                  ; t = x & 7
        ex de,hl                ; DE = word, L = k
        ld a,l
        or a
        jr z,.z1
        dec a
        jr z,.o1
        ld a,8                  ; k = 2: (word << (8 - t)) low byte
        sub b
        ld b,a
        bsla de,b
        jr .g1
.z1:   ld a,b                  ; k = 0: word >> (8 + t)
        add a,8
        ld b,a
.o1:   bsrl de,b               ; k = 1: word >> t
.g1:   ld a,e
        ld hl,3
        add hl,sp
        xor (hl)
        ld (hl),a               ; accumulator (A of the saved AF)
        pop bc
.s1:
        ld a,(HS + 2)
        or a
        jr z,.s2
        ld hl,SLOTS + 16
        ld a,(hl)               ; x
        inc hl
        ld d,a
        ld a,b
        sub (hl)                ; r = y - slot y
        cp 24
        jr nc,.s2
        add a,a
        ld e,a                  ; D = x, E = 2r
        inc hl
        ld a,(hl)               ; frame
        push bc
        push de
        ld e,a
        add a,a
        add a,e                 ; 3 * frame, 8 bits wide like the game's own address (47742)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; * 16
        ld de,(48450)
        add hl,de
        pop de
        ld a,l
        add a,e
        ld l,a
        jr nc,.a2
        inc h
.a2:   ld a,d
        rrca
        rrca
        rrca
        and 31
        ld e,a                  ; x >> 3
        ld a,c
        sub e                   ; k = byte column inside the 3 bytes
        cp 3
        jr c,.k2
        pop bc
        jr .s2
.k2:   ld e,a
        ld a,(hl)
        inc hl
        ld l,(hl)
        ld h,a                  ; HL = row word
        ld a,d
        and 7
        ld b,a                  ; t = x & 7
        ex de,hl                ; DE = word, L = k
        ld a,l
        or a
        jr z,.z2
        dec a
        jr z,.o2
        ld a,8                  ; k = 2: (word << (8 - t)) low byte
        sub b
        ld b,a
        bsla de,b
        jr .g2
.z2:   ld a,b                  ; k = 0: word >> (8 + t)
        add a,8
        ld b,a
.o2:   bsrl de,b               ; k = 1: word >> t
.g2:   ld a,e
        ld hl,3
        add hl,sp
        xor (hl)
        ld (hl),a               ; accumulator (A of the saved AF)
        pop bc
.s2:
        pop af
        and a
        pop hl
        pop de
        pop bc
        ret
; LD A,(DE) / AND A / RET NZ
rd_a:   call vrd
        ret z
        inc sp
        inc sp
        ret
; LD A,(DE) / AND A / JP NZ,51431
rd_j:   call vrd
        ret z
        inc sp
        inc sp
        jp 51431
; LD A,(DE) / AND A / JR Z,51389
rd_z:   call vrd
        jr z,.t
        ret
.t:     inc sp
        inc sp
        jp 51389

        ASSERT $ <= 0x39FF
        DS 0x39FF - $, 0xFF
        DB 0xFF, 0xFF

; ---- plotter end (after the state stores): HL = slot state + 2. Mark the slot shown. ----
e_ep:   push af
        push de
        push hl
        ld de,-(SLOTS + 2)
        add hl,de               ; 0, 8 or 16 for slots 0-2
        ld a,h
        or a
        jr nz,.no
        ld a,l
        cp 24
        jr nc,.no
        rrca
        rrca
        rrca
        ld e,a
        ld d,0
        ld hl,HS
        add hl,de
        ld (hl),1
.no:    pop hl
        pop de
        pop af
        pop ix                  ; replayed: POP IX / RET
        ret

; ---- the interrupt handler after the game tick (49804: EXX / POP HL / POP DE), sprite update ----
; Some recorded entries have interrupts enabled. Save IFF, disable during MMU mapping, restore it.
; Keep every main register as well.
e_isr:  push af
        ld a,i
        di
        push af
        push bc
        push de
        push hl
        push ix
        nextreg 0x07,3
        call upd
        nextreg 0x07,0
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        jp po,.irq_off
        pop af
        ei
        jr .resume
.irq_off:
        pop af
.resume:
        exx                     ; replayed: EXX / POP HL / POP DE
        pop hl
        pop de
        jp 49807                ; POP BC

; ---- screen clears: hide everything (flags only; the next interrupt turns the sprites off) ----
e_c1:   call hid
        ld hl,16384
        jp 50346
e_c2:   call hid
        ld hl,18432
        jp 50612
hid:    push af
        xor a
        ld (HS),a
        ld (HS + 1),a
        ld (HS + 2),a
        ld (HS + 3),a
        ld (HS + 4),a
        ld (HS + 5),a
        ld (HS + 6),a
        ld (HS + 7),a
        pop af
        ret

; ---- diamond draw: stack = ret 60659, HL, BC (B = entries left, 5 for the first) ----
e_dia:  push af
        push de
        push hl
        ld hl,6 + 4 + 1
        add hl,sp
        ld a,(hl)               ; B of the outer BC
        neg
        add a,5                 ; entry index 0-4
        cp 5
        jr nc,.no
        ld e,a
        ld d,0
        ld hl,SHOWD
        add hl,de
        ld (hl),1
.no:    pop hl
        pop de
        pop af
        jp 60671

; ---- sprite update: figures (slots 0-2), then diamonds (entries 0-4) ----
upd:    xor a
        ld (HS+15),a
        ld a,(HS+1)
        ld b,a
        ld a,(HS+2)
        and b
        jr z,.start
        ld hl,SLOTS+8
        ld de,SLOTS+16
        ld b,3
.equal: ld a,(de)
        cp (hl)
        jr nz,.start
        inc hl
        inc de
        djnz .equal
        ld a,1
        ld (HS+15),a
.start: ld c,0
.sl:    ld hl,HS
        ld b,0
        add hl,bc
        ld a,(hl)               ; SHOW[c]
        ld b,a
        ld a,c
        or a
        jr z,.show
        ld a,(HS+15)
        or a
        jr z,.show
        ld b,0
.show:  call sptr               ; HL = &state.x
        ld a,b
        or a
        jp z,.off
        push hl
        ld de,6
        add hl,de
        ld a,(hl)               ; E: ink, bright
        ld e,a
        and 0x40
        rrca
        rrca
        rrca
        ld d,a
        ld a,e
        and 7
        or d
        and a
        jr nz,.ink
        ld a,8
.ink:   ld (HS+11),a
        pop hl                  ; &x
        push hl
        inc hl
        inc hl
        ld b,(hl)               ; frame
        ld hl,LASTF
        ld e,c
        ld d,0
        add hl,de
        ld a,(hl)
        cp b
        jr nz,.upload
        push hl
        ld hl,LASTINK
        add hl,de
        ld a,(HS+11)
        cp (hl)
        pop hl
        jr z,.pos
.upload:
        ld (hl),b
        push hl
        ld hl,LASTINK
        add hl,de
        ld a,(HS+11)
        ld (hl),a
        pop hl
        ld a,c
        inc a
        ld d,a
        ld e,0x11
        mul d,e
        ld ixh,e                ; pixel colour index c + 1 in both nibbles (IX is the ISR's own, saved at 49745)
        ld a,b
        ld e,a
        add a,a
        add a,e                 ; 3 * frame, 8 bits wide like the game's own address (47742)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; * 16
        ld de,(48450)
        add hl,de               ; rows 0..: source of the top sprite
        ld a,c
        add a,a                 ; pattern 2c
        push hl
        push bc                 ; cvt clobbers BC
        call cvt
        pop bc
        pop hl
        ld de,16
        add hl,de               ; row 8
        ld a,c
        add a,a
        inc a                   ; pattern 2c + 1
        push bc
        call cvt
        pop bc
.pos:   pop hl                  ; &x
        ld a,(hl)
        add a,32
        ld e,a                  ; X low
        ld a,0
        adc a,0
        ld b,a                  ; X8
        ld d,b                  ; attribute 2: palette offset 0, X8
        inc hl
        ld l,(hl)               ; L = y (H no longer needed)
        ld a,l
        add a,32
        ld l,a                  ; L = y + 32 (<= 223 + ... y <= 191 for display; 8-bit wrap is outside the clip)
        ; top sprite: index 9 - 2c
        ld a,c
        add a,a
        ld b,a
        ld a,9
        sub b
        nextreg 0x34,a
        ld a,e
        nextreg 0x35,a
        ld a,l
        nextreg 0x36,a
        ld a,d
        nextreg 0x37,a
        ld a,c
        or 0xC0
        nextreg 0x38,a          ; visible, 4-bit pattern 2c (N[6:1] = c)
        nextreg 0x39,0x80
        ; bottom sprite: index 10 - 2c, y + 8, pattern 2c + 1
        ld a,9
        sub b
        inc a
        nextreg 0x34,a
        ld a,e
        nextreg 0x35,a
        ld a,l
        add a,8
        nextreg 0x36,a
        ld a,d
        nextreg 0x37,a
        ld a,c
        or 0xC0
        nextreg 0x38,a
        nextreg 0x39,0xC0
        jr .nx
.off:   ld a,c
        add a,a
        ld b,a
        ld a,9
        sub b
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
.nx:    inc c
        ld a,c
        cp 3
        jp nz,.sl
        ; ---- diamonds ----
        ld a,(49612)
        ld l,a
        ld h,0
        add hl,hl
        ld de,55021
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = the room's table (entry = id, x, y)
        ld c,0
.dm:    ld hl,SHOWD
        ld b,0
        add hl,bc
        ld a,(hl)
        or a
        jr z,.doff
        ld a,(de)               ; id
        or a
        jr z,.doff
        inc de
        ld a,(de)               ; x
        and 0xF8
        add a,32
        ld l,a
        ld a,0
        adc a,0
                                ; palette offset 0, X8
        ld h,a
        inc de
        ld a,(de)               ; y
        inc de
        add a,34                ; y + 2 + 32
        ld b,a
        ld a,c
        nextreg 0x34,a
        ld a,l
        nextreg 0x35,a
        ld a,b
        nextreg 0x36,a
        ld a,h
        nextreg 0x37,a
        nextreg 0x38,0xC3       ; visible, pattern 6 (N[6:1] = 3)
        nextreg 0x39,0x80
        jr .dn
.doff:  inc de
        inc de
        inc de
        ld a,c
        nextreg 0x34,a
        nextreg 0x38,0
.dn:    inc c
        ld a,c
        cp 5
        jr nz,.dm
        ret

; HL = SLOTS + 8 * C (DE clobbered)
sptr:   ld a,c
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        ld hl,SLOTS
        add hl,de
        ret

; pattern A (0-127) <- 16 rows x 2 source bytes at HL (1 bit per pixel -> 4-bit index 1), 128 bytes to port 0x5B
cvt:    rrca
        ld bc,0x303B
        out (c),a
        ld de,(48450)
        or a
        sbc hl,de               ; source byte offset 0..4127
        ld a,h
        srl a
        srl a
        srl a                   ; page inside a 24K ink table (0..2)
        ld e,a
        ld a,(HS+11)
        ld d,a
        add a,a
        add a,d
        add a,32
        add a,e
        ld d,a                  ; Next page = 32 + 3*ink + byte_offset/2048
        nextreg 0x56,a
        add hl,hl
        add hl,hl
        ld a,h
        and 0x1F
        or 0xC0
        ld h,a
        ld bc,0x805B            ; 128 packed pixels bytes; advance page at 0xE000
.loop:  ld a,(hl)
        out (c),a
        inc hl
        ld a,h
        cp 0xE0
        jr nz,.same
        ld h,0xC0
        inc d
        ld a,d
        nextreg 0x56,a
.same:  djnz .loop
        nextreg 0x56,0          ; original 48K RAM restored before returning to game
        ret

; Read original collectable bytes before XORing the moving figures.
; BC = screen row / byte column, DE = screen address. Preserve BC,DE,HL.
diamond_read:
        push bc
        push de
        push hl
        ld a,(49612)
        ld l,a
        ld h,0
        add hl,hl
        ld de,55021
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,SHOWD
.loop:  ld a,(hl)
        or a
        jr z,.skip3
        ld a,(de)
        or a
        jr z,.skip3
        inc de
        ld a,(de)
        rrca
        rrca
        rrca
        and 31
        cp c
        jr nz,.skip2
        inc de
        ld a,(de)
        add a,8
        sub b
        cp 7
        jr nc,.skip1
        ld l,a
        ld h,0
        ld de,60692
        add hl,de
        ld a,(hl)
        pop hl
        pop de
        pop bc
        ret
.skip3: inc de
.skip2: inc de
.skip1: inc de
        inc hl
        ld a,l
        cp 8
        jr nz,.loop
        pop hl
        pop de
        pop bc
        ld a,(de)
        ret
ntab:   ; retained symbol for profile compatibility; conversion table no longer used
rom_end:

; --- setup routine (stub bank, 0xD000): diamond pattern from bank 11, palette, hide all, sprites on ---
        ORG 0xD000
setup:  nextreg 0x57,22             ; bank 11 lower page at 0xE000: [0] diamond pattern, then zeros
        ld bc,0x303B
        xor a
        out (c),a                   ; pattern 0
        ld hl,0xE100
        ld d,3                      ; patterns 0-5 cleared (768 bytes of zeros)
.z:     ld bc,0x005B
        otir
        dec d
        jr nz,.z
        ld bc,0x303B
        ld a,PAT_DIA >> 1
        out (c),a                   ; pattern 6 = slot 3, first half
        ld hl,0xE000
        ld bc,0x805B                ; 128 bytes
        otir
        nextreg 0x57,21
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment (every write sets $40 first)
        nextreg 0x40,0
        ld hl,palette
        ld b,16
.pal:   ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .pal
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
palette: DB 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
         DB 0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "ifm_rom-add-GPT6_ASTRA.bin",0x386E,rom_end-0x386E
        SAVEBIN "ifm_setup-add-GPT6_ASTRA.bin",0xD000,setup_end-0xD000
