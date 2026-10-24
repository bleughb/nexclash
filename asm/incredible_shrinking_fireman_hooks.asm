; The Incredible Shrinking Fireman (Mastertronic, 1986, 48K) - hardware sprites for the fireman, the two
; room figures and the collectable diamonds.
;
; Design (games/incredible_shrinking_fireman.md):
;  - The game's one figure plotter (47440, differential XOR: old image ^ new image) keeps running; only
;    its XOR screen writes and its attribute write are removed (NOPs), so game state is the original's.
;  - ALL sprite register / pattern-port writes happen in ONE place, e_isr (the game's frame interrupt,
;    interrupts off there): the plotter is also called from the interrupt (slot 0) and from the main
;    thread, and NEXTREG $34 / port 0x303B are shared selectors, so a hook in the plotter could be
;    interrupted by another hook and write to the wrong sprite. The plot / clear / draw hooks only
;    write single flag bytes (never read-modify-write) in RAM the game never touches.
;  - Slot s (0 fireman, 1 and 2 room figures): state at 48375 + 8s = x, y, frame (+2), ... E (+6).
;    The 16 x 24 image (gfx at (48450) + 48 frame, 2 bytes per row, top down, 1 = ink) is two sprites
;    (rows 0-15 at y, rows 8-23 at y + 8; the overlap draws the same pixels twice), patterns 2s, 2s + 1,
;    converted to 4-bit when the frame changes (LASTF), colour = sprite palette entry 16s + 1 from E.
;  - Collectables: the game draws one 8 x 7 diamond per room table entry (id, x, y; table 55021 + 2 room,
;    5 entries) at (x & 0xF8, y + 2); sprite i, pattern 6 (uploaded by setup), palette offset 3.
;
; Patch sites (original bytes checked by incredible_shrinking_fireman.py):
;   48220  DD E1 C9         POP IX / RET (plotter end, HL = state + 2)      -> JP e_ep
;   49804  D9 E1 D1         EXX / POP HL / POP DE after the game tick       -> JP e_isr (the CALL's target changes: 49802)
;   50343  21 00 40         LD HL,16384 (CLS)                              -> JP e_c1
;   50609  21 00 48         LD HL,18432 (clear lower screen)               -> JP e_c2
;   60656  CD 3F ED         CALL 60671 (draw one diamond)                  -> CALL e_dia
; Screen-write removals (no hook): 47897 47901 47905 (77 -> 00), 48047 48059 48071 48083 48165 48174 48183
;   (DD 77 00 -> 00 00 00, XOR writes), 48351 (DD 77 00 -> 00 00 00, attribute), 60683 (77 -> 00, diamond).
;
; Sprites: diamonds 0-4, slot 2 = 5/6, slot 1 = 7/8, slot 0 = 9/10 (higher number on top).

        DEVICE ZXSPECTRUMNEXT

HS      EQU 0xF400              ; hook state (zero span the game never touches): SHOW[3], SHOWD[5], LASTF[3]
SHOWD   EQU HS + 3
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
        ld a,(de)
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
; Interrupts are off in the handler. The main registers were pushed at its start, so they are free here,
; but they are kept anyway (the verifier compares every register).
e_isr:  push af
        push bc
        push de
        push hl
        call upd
        pop hl
        pop de
        pop bc
        pop af
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
upd:    ld c,0
.sl:    ld hl,HS
        ld b,0
        add hl,bc
        ld a,(hl)               ; SHOW[c]
        ld b,a
        call sptr               ; HL = &state.x
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
        ld e,a
        ld d,0
        ld hl,coltab
        add hl,de
        ld e,(hl)               ; sprite colour
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,a
        inc a
        nextreg 0x40,a
        ld a,e
        nextreg 0x41,a
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
        jr z,.pos
        ld (hl),b
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
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,a
        or b
        ld d,a                  ; attribute 2: palette offset c, X8
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
        or 0x30                 ; palette offset 3, X8
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
cvt:    rrca                    ; 0x303B = (A >> 1) | (A << 7): pattern slot, bit 7 = the second 128 bytes
        ld bc,0x303B
        out (c),a
        ld c,0x5B
        ld b,32                 ; 32 source bytes
.by:    ld a,(hl)
        inc hl
        ld e,a
        rrca
        rrca
        rrca
        rrca
        and 15
        add a,a
        ld d,high ntab
        add a,low ntab
        ld e,a
        ld a,(de)
        out (c),a
        inc e
        ld a,(de)
        out (c),a
        dec hl
        ld a,(hl)
        inc hl
        and 15
        add a,a
        add a,low ntab
        ld e,a
        ld a,(de)
        out (c),a
        inc e
        ld a,(de)
        out (c),a
        djnz .by
        ret

        ALIGN 32
; nibble (4 pixels, bit 3 = leftmost) -> two bytes of 4-bit pixels (index 1)
ntab:   DB 0x00,0x00, 0x00,0x01, 0x00,0x10, 0x00,0x11
        DB 0x01,0x00, 0x01,0x01, 0x01,0x10, 0x01,0x11
        DB 0x10,0x00, 0x10,0x01, 0x10,0x10, 0x10,0x11
        DB 0x11,0x00, 0x11,0x01, 0x11,0x10, 0x11,0x11
; sprite colour by (bright * 8 + ink), RRRGGGBB
coltab: DB 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        DB 0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
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
        nextreg 0x40,0x31
        nextreg 0x41,0xB6           ; palette offset 3 index 1: white diamond
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
setup_end:

        SAVEBIN "ifm_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "ifm_setup.bin",0xD000,setup_end-0xD000
