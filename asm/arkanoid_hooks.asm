; Arkanoid (Imagine, 1987, 48K) - hardware sprites OVER the game's XOR figures (overlay, LEARNINGS 2.1d).
; Every ULA write stays: an alien's erase tests its own XOR pixels for overlap (0x8917 AND L), so the
; game reads figure pixels, and an overlay needs no virtual read. Sprites sit exactly on the ink pixels.
; All hooks live in alt ROM image 1 at 0x386E, stateless (no RAM but dead stack), 28 MHz inside.
; Site -> hook (displaced instructions are emulated at the hook's end; nexclash/arkanoid.py SITES):
;   0x93E7 ball draw   0x9420 balls erase all   0x8FD2 CALL 0x9429 one lost ball
;   0x9C63 bat draw    0x9BC6 big bat draw      0x9B7D bat erase
;   0x8879 alien draw 2 bytes wide  0x878C alien draw 3 bytes wide  0x88D5 alien erase
;   0x8C75 capsule draw  0x8C0E capsule erase
;   0x8D9B laser draw (SP may point into graphics here)  0x8D28 / 0x8A19 laser erase
;   0x8025 back to the front end, 0x96A0 play area wipe: hide everything
; Sprite n uses pattern n (4-bit, first half of the slot, value 1 = ink, palette offset = colour):
;   0-2 bat rows 176-183, 3-5 bat rows 184-187, 6 capsule, 7-12 aliens (two each), 13-14 laser, 15-17 balls

        DEVICE ZXSPECTRUMNEXT

LEVATTR EQU 0x94CC      ; level attribute: paper + BRIGHT, ink 0
ALMASK  EQU 0x94CE      ; alien ink: AND mask over ink 7
CAPATTR EQU 0x94E8      ; capsule attribute
GFXBIG  EQU 0x94BE      ; bat graphics pointer
BATSCR  EQU 0x94BC      ; bat screen address
CAPSCR  EQU 0x94EB
CAPGFX  EQU 0x94E3
LASGFX  EQU 0x94DF
SAVESP  EQU 0x94C8
SPR_BAT EQU 0
SPR_BTL EQU 3
SPR_CAP EQU 6
SPR_ALN EQU 7
SPR_LAS EQU 13
SPR_BAL EQU 15
NSPR    EQU 18
CPAGE   EQU 26      ; 8K page of the Enhanced colour routine (bank 13)
DPAGE   EQU 28      ; first of 10 8K pages of colour data (banks 14-18): 4 bytes per graphics byte from GBASE
GBASE   EQU 0xA0    ; high byte of the first graphics byte with colour data

        MACRO HK_IN
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ENDM
        MACRO HK_OUT
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        ENDM

        ORG 0x386E
; ---- balls: DE = screen, HL = graphics (5 rows x 2 bytes), IX = ball ------------------------
e_bd:   HK_IN
        call ballno
        ld bc,0x0502
        call upl
        push af
        ld a,7
        call pal
        ld l,a
        pop af
        ld h,0
neg_ball:
        call spr
        HK_OUT
        ld (SAVESP),sp
        jp 0x93EB

e_bal:  HK_IN                   ; all balls erased (dead balls were hidden by e_b1)
        ld a,SPR_BAL
neg_balh:
        call hide
        inc a
        call hide
        inc a
        call hide
        HK_OUT
        ld b,3
neg_de: ld de,0x0011
        jp 0x9425

e_b1:   HK_IN                   ; one ball lost: IX
        call ballno
        call hide
        HK_OUT
        jp 0x9429

ballno: ld a,ixl                ; IX 94F6 / 9507 / 9518 -> sprite 15 / 16 / 17
        cp 0xF6
        ld a,SPR_BAL
        ret z
        ld a,ixl
        cp 0x07
        ld a,SPR_BAL+1
        ret z
        inc a
        ret

; ---- bat: 12 rows, 4 or 6 bytes wide; rows 176-183 ink 5, 184-187 level ink, as the game paints -
e_bn:   HK_IN                   ; HL = screen, DE = graphics
        ex de,hl
        ld c,4
        ld a,SPR_BAT
        call batu
        inc a
        call batu
        dec a
        ld h,0
        call batsh
        inc a
        ld h,16
        call batsh
        ld a,SPR_BAT+2
        call hide
        ld a,SPR_BTL+2
        call hide
        HK_OUT
        ld (BATSCR),hl
        jp 0x9C66

e_bb:   HK_IN                   ; DE = screen, graphics pointer already stored
        ld hl,(GFXBIG)
        ld c,6
        ld a,SPR_BAT
        call batu
        inc a
        call batu
        inc a
        call batu
        ld a,SPR_BAT
        ld h,0
        call batsh
        inc a
        ld h,16
        call batsh
        inc a
        ld h,32
        call batsh
        HK_OUT
        ld (BATSCR),de
        jp 0x9BCA

e_bh:   HK_IN                   ; bat erase
        ld a,SPR_BAT
        ld b,6
.h:     call hide
        inc a
        djnz .h
        HK_OUT
        ld de,(BATSCR)
        jp 0x9B81

; A = upper slot, HL = this part's graphics (moves on 2), C = stride; keeps A, C, DE
batu:   push hl
        ld b,8
        call upl
        add a,SPR_BTL
        ld b,4
        call upl
        sub SPR_BTL
        pop hl
        inc hl
        inc hl
        ret

; A = upper sprite, DE = screen, H = x offset; keeps A, DE, H
batsh:  push af
        ld a,5
        call pal
        ld l,a
        pop af
        call spr
        add a,SPR_BTL
        push af
        xor a
        call pal
        ld l,a
        ld a,e
        add a,0x20
        ld e,a
        pop af
        call spr
        sub SPR_BTL
        push af
        ld a,e
        sub 0x20
        ld e,a
        pop af
        ret

; ---- aliens: DE = screen, HL = graphics, B = rows (<= 16), IX = alien ---------------------------
e_a2:   HK_IN
        call alno
        ld c,2
        push bc
        call upl
        pop bc
        call fill
        call alpal
        ld h,0
        call spr
        inc a
        call hide
        HK_OUT
        ld (SAVESP),sp
        jp 0x887D

e_a3:   HK_IN
        call alno
        ld c,3
        push hl
        push bc
        call upl
        pop bc
        push bc
        call fill
        pop bc
        pop hl
        inc hl
        inc hl
        inc a
        push bc
        call upl1
        pop bc
        call fill
        call alpal
        ld h,16
        call spr
        dec a
        ld h,0
        call spr
        HK_OUT
        ld (SAVESP),sp
        jp 0x8790

e_ah:   HK_IN
        call alno
        call hide
        inc a
        call hide
        HK_OUT
        ld (SAVESP),sp
        jp 0x88D9

alno:   ld a,ixl                ; IX 9529 / 9539 / 9549 -> sprite 7 / 9 / 11
        sub 0x29
        rrca
        rrca
        rrca
        add a,SPR_ALN
        ret

alpal:  push af                 ; -> L = palette: ink as AND mask over ink 7; explosion 0xFE (0x8861)
        ld a,(ALMASK)
        bit 2,(ix+5)
        jr nz,.a
        ld a,0xFE
.a:     call pal
        ld l,a
        pop af
        ret

; ---- capsule: DE = screen, HL = graphics, rows zig-zag: b0 b1 / b3 b2 ---------------------------
e_cd:   HK_IN
        push de
        ld a,SPR_CAP
        ld bc,0x303B
        out (c),a
        ld b,4
.g:     ld e,(hl)
        call pix4
        inc hl
        ld e,(hl)
        call pix4
        inc hl
        inc hl
        ld e,(hl)
        call pix4
        dec hl
        ld e,(hl)
        call pix4
        inc hl
        inc hl
        djnz .g
        pop de
        ld a,(CAPATTR)
        call palb
        ld l,a
        ld h,0
        ld a,SPR_CAP
        call spr
        HK_OUT
neg_capst:
        ld (CAPGFX),hl
        jp 0x8C78

e_ch:   HK_IN
        ld a,SPR_CAP
        call hide
        HK_OUT
        ld de,(CAPSCR)
        jp 0x8C12

; ---- laser: two 3-byte beams, 8 rows, b0 b1 b2 / b5 b4 b3. SP may be in the graphics at 0x8D9B ---
e_ld:   ld sp,(SAVESP)
        HK_IN
        push de
        ld hl,(LASGFX)
        ld a,SPR_LAS
        ld bc,0x303B
        out (c),a
        ld b,4
.g1:    ld e,(hl)               ; b0
        call pix4
        inc hl
        ld e,(hl)               ; b1
        call pix4
        inc hl
        inc hl
        inc hl
        inc hl
        ld e,(hl)               ; b5
        call pix4
        dec hl
        ld e,(hl)               ; b4
        call pix4
        inc hl
        inc hl                  ; next group's b0
        djnz .g1
        ld hl,(LASGFX)
        inc hl
        inc hl
        ld a,SPR_LAS+1
        ld bc,0x303B
        out (c),a
        ld b,4
.g2:    ld e,(hl)
        call pix4
        ld e,0
        call pix4
        inc hl
        ld e,(hl)
        call pix4
        ld e,0
        call pix4
        ld a,l
        add a,5
        ld l,a
        adc a,h
        sub l
        ld h,a
        djnz .g2
        pop de
        ld a,7
        call pal
        ld l,a
        ld h,0
        ld a,SPR_LAS
        call spr
        inc a
        ld h,16
        call spr
        HK_OUT
        ld h,d
        ld l,e
        ld sp,(LASGFX)
        jp 0x8DA1

e_lh:   HK_IN
        call lashd
        HK_OUT
        ld (SAVESP),sp
        jp 0x8D2C

e_lx:   HK_IN
        call lashd
        HK_OUT
        ld sp,(LASGFX)
        jp 0x8DA1

lashd:  ld a,SPR_LAS
        call hide
        inc a
        jp hide

; ---- front end and play area wipes ----------------------------------------------------------
e_go:   HK_IN
        call hidall
        HK_OUT
        di
        xor a
        out (0xFE),a
        jp 0x8029

e_wi:   HK_IN
neg_wipe:
        call hidall
        HK_OUT
        ld iy,0x5C3A
        jp 0x96A4

hidall: xor a
        ld b,NSPR
.h:     call hide
        inc a
        djnz .h
        ret

; ---- shared ---------------------------------------------------------------------------------
hide:   nextreg 0x34,a
        push af
        xor a
        nextreg 0x38,a
        pop af
        ret

; A = sprite and pattern, DE = screen address, H = x offset, L = palette (offset << 4). Keeps all but F.
spr:    push bc
        nextreg 0x34,a
        ld b,a
        ld a,e
        and 31
        add a,a
        add a,a
        add a,a
        ld c,0
        add a,h
        jr nc,.x1
        inc c
.x1:    add a,32
        jr nc,.x2
        inc c
.x2:    nextreg 0x35,a
        ld a,c
sprpal: or l                    ; Enhanced: NOP, every figure in palette 0 (the map's colours)
        nextreg 0x37,a
        ld a,d
        and 0x18
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or c
        ld c,a
        ld a,d
        and 7
        or c
neg_y:  add a,32
        nextreg 0x36,a
        ld a,b
        or 0xC0
        nextreg 0x38,a
        ld a,0x80
        nextreg 0x39,a
        ld a,b
        pop bc
        ret

; A = ink -> A = palette byte, BRIGHT from the level attribute
pal:    push bc
        and 7
        ld b,a
        ld a,(LEVATTR)
        and 0x40
        or b
        pop bc
; A = attribute (ink + BRIGHT) -> A = palette offset << 4
palb:   push bc
        ld b,a
        and 7
        ld c,a
        ld a,b
        and 0x40
        rrca
        rrca
        rrca
        or c
        add a,a
        add a,a
        add a,a
        add a,a
        pop bc
        ret

; A = pattern, HL = graphics, B = rows, C = stride; two bytes a row. Keeps A, C, DE
upl:    push af
        push de
        push bc
        ld bc,0x303B
        out (c),a
        pop bc
.r:     ld e,(hl)
        call pix4
        inc hl
        ld e,(hl)
        call pix4
        dec hl
        ld a,l
        add a,c
        ld l,a
        adc a,h
        sub l
        ld h,a
        djnz .r
        pop de
        pop af
        ret

; the same for one byte a row (the alien's third column)
upl1:   push af
        push de
        push bc
        ld bc,0x303B
        out (c),a
        pop bc
.r:     ld e,(hl)
        call pix4
        ld e,0
        call pix4
        ld a,l
        add a,c
        ld l,a
        adc a,h
        sub l
        ld h,a
        djnz .r
        pop de
        pop af
        ret

; B = rows written: pad the slot with zero rows to 16. Keeps A
fill:   push af
        ld a,16
        sub b
        jr z,.e
        add a,a
        add a,a
        add a,a
        ld b,a
        xor a
.z:     out (0x5B),a
        djnz .z
.e:     pop af
        ret

; E = 8 pixels -> 4 pattern bytes (value 1 = ink). HL points at the graphics byte (padding calls: E = 0).
; Enhanced: the colour set turns this JR's offset from 0 to pix4c, which asks the colour page for the 4 bytes.
pix4:   jr pix4p
pix4p:  call pix2
        call pix2
        call pix2
pix2:   xor a
        sla e
        jr nc,pix_a
neg_pix:
        ld a,0x10
pix_a:  sla e
        jr nc,pix_b
        inc a
pix_b:  out (0x5B),a
        ret

; Enhanced only: the colour routine in RAM page CPAGE at 0x0000, interrupts off around it (the game runs with
; them off; the front end event, the only one with them on, sends no pattern). Keeps all but A, F, E.
pix4c:  ld a,i                  ; IFF known off: the game runs with DI and the front end sends no pattern
        push af
        di
        nextreg 0x50,CPAGE
        call 0x0000
        nextreg 0x50,0xFF
        pop af
        ret po
        ei
        ret
rom_end:

; ---- start-up, called once by the stub ------------------------------------------------------
        ORG 0xD000
setup:  ld bc,0x303B            ; all NSPR pattern slots zero
        xor a
        out (c),a
        ld d,NSPR
.p:     ld b,0
.q:     out (0x5B),a
        djnz .q
        dec d
        jr nz,.p
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        ld hl,colours           ; offset n, index 1 = Spectrum colour n (BRIGHT n >= 8)
        ld d,0
.c:     ld a,d
        add a,a
        add a,a
        add a,a
        add a,a
        inc a
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a
        inc hl
        inc d
        ld a,d
        cp 16
        jr nz,.c
        nextreg 0x40,1          ; palette 0, entries 1-15: black for ink 0 (default), the map's for Enhanced
        ld hl,pal0
        ld b,15
.e:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .e
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
colours:
        db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        db 0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
pal0:   db 0x00,0,0,0,0,0,0,0,0,0,0,0,0,0,0
setup_end:

; ---- Enhanced colour routine: RAM page CPAGE at 0x0000, called by pix4c ---------------------------
; HL = graphics byte, E = its value. Out: 4 pattern bytes to port 0x5B, from the colour data when the byte has an
; entry (any non-zero), else value 1 on each ink bit as pix4. Keeps BC, D, HL.
        ORG 0x0000
enh:    ld a,e
        or a
        jr z,.p                 ; no ink (or a padding call): zeros
        ld a,h
        sub GBASE
        jr c,.p
        cp 0x50
        jr nc,.p
        push hl
        push bc
        ld b,a
        rrca
        rrca
        rrca
        and 0x1F
        add a,DPAGE
        nextreg 0x51,a
        ld a,b
        and 7
        ld h,a
        add hl,hl
        add hl,hl
        set 5,h                 ; 0x2000 + 4 x (offset in the 2K this page covers)
        ld b,4
        xor a
        push hl
.o:     or (hl)
        inc hl
        djnz .o
        pop hl
        jr z,.n
        ld b,4
.s:     ld a,(hl)
        out (0x5B),a
        inc hl
        djnz .s
        nextreg 0x51,0xFF
        pop bc
        pop hl
        ret
.n:     nextreg 0x51,0xFF
        pop bc
        pop hl
.p:     push bc                 ; as pix4: two pixels a byte, value 1 = ink
        ld b,4
.q:     xor a
        sla e
        jr nc,.a
        ld a,0x10
.a:     sla e
        jr nc,.b
        inc a
.b:     out (0x5B),a
        djnz .q
        pop bc
        ret
enh_end:

        SAVEBIN "ar_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "ar_setup.bin",0xD000,setup_end-0xD000
        SAVEBIN "ar_enh.bin",0x0000,enh_end
