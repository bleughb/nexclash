; Monty on the Run (Gremlin Graphics, 1985, 48K) - hardware sprites OVER the game's XOR figures (overlay).
; Two plotters draw the figures, each XORing a figure's previous image at its old place and its current one at
; its new place, 16 rows x 3 bytes, the image stored bottom row first and pre-shifted to x & 7:
;   0xB47F (46207) the four enemy slots: positions x, y at 46963 + 2i, records at 46987 + 8i (+4 the colour),
;      images in a 192-byte buffer (48 per slot) whose pointer (47019 / 47021) swaps each draw;
;   0xF689 (63113) Monty: position 65282 / 65283, image pointer 65286 (old ones at 65288 / 65289 / 65291).
; Image row k of a figure at (x, y) is screen row 206 - y - k, drawn only when 16 <= y - 15 + k < 176; columns
; x / 8 .. x / 8 + 2. Before an enemy's XOR the game calls the attribute painter 0xB59B (46491), which colours the
; cells under it that the room map leaves empty: that is the colour clash. Its three stores become NOPs (sites), so
; every register is as the game's; the game never reads figure pixels or those colours back.
; Hooks (all in alt ROM image 1 at 0x386E, stateless, 28 MHz inside, no alternate registers):
;   46313 (after the enemy XORs, the buffer pointers just swapped): sprites 2i, 2i + 1 for slot i, its own ink;
;   63169 (after Monty's XOR): sprites 8, 9, white;
;   57984 (room set-up), 37386 (new game) and 43363 (the menu, after a game over too): hide them all.

        DEVICE ZXSPECTRUMNEXT

NEWPOS  EQU 46963               ; enemies: x, y for each of the four slots
REC     EQU 46987               ; 8 bytes a slot, +4 the colour
BUFPTR  EQU 47021               ; at the hook (pointers just swapped): the current images, 48 bytes a slot
MX      EQU 65282
MY      EQU 65283
MIMG    EQU 65286
NSPR    EQU 10                  ; 0-7 the enemies, 8-9 Monty
MONTY   EQU 0x0F                ; Monty's palette offset: BRIGHT white

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
; ---- 46313 LD HL,46963 -> JP e_en: the four enemy slots --------------------------------------------------------
e_en:   HK_IN
        push ix
        ld hl,(BUFPTR)
        ld ix,NEWPOS
        xor a
en_slot: push af
        push hl
        ld c,(ix+0)             ; x
        ld d,(ix+1)             ; y
        push af
        add a,a                 ; A = 2i -> 8i (record offset)
        add a,a
        ld e,a
        push hl
        ld hl,REC+4
        ld a,l
        add a,e
        ld l,a
        jr nc,.r
        inc h
.r:     ld a,(hl)               ; the slot's colour
        pop hl
        ld e,a
        and 7                   ; palette offset = ink + 8 x BRIGHT
        bit 6,e
        jr z,.nb
        or 8
.nb:    ld e,a
        pop af
neg_en: call show2
        pop hl
        ld bc,48
        add hl,bc
        inc ix
        inc ix
        pop af
        add a,2
        cp 8
        jr nz,en_slot
        pop ix
        HK_OUT
        ld hl,NEWPOS
neg_end:
        jp 46316

; ---- 63169 LD HL,(65282) -> JP e_mo: Monty ---------------------------------------------------------------------
e_mo:   HK_IN
        push ix
        ld hl,(MIMG)
        ld a,(MX)
        ld c,a
        cp 240                  ; column 30 or 31: Monty's plotter draws nothing (its row helper 59065 refuses them)
        jr c,mo_show
        ld a,8
        call hide
        inc a
        call hide
        jr mo_done
mo_show:
        ld a,(MY)
        ld d,a
        ld e,MONTY
        ld a,8
neg_mo: call show2
mo_done:
        pop ix
        HK_OUT
        ld hl,(MX)
        jp 63172

; ---- 57984 DI / LD HL,49152 -> JP e_rm: room set-up ------------------------------------------------------------
e_rm:   HK_IN
neg_room:
        call hidall
        HK_OUT
        di
        ld hl,49152
        jp 57988

; ---- 37386 DI / LD HL,37699 -> JP e_ng: new game ---------------------------------------------------------------
e_ng:   HK_IN
neg_new:
        call hidall
        HK_OUT
        di
        ld hl,37699
        jp 37390

; ---- 43363 DI / IM 1 -> JP e_mn: the menu (the game's start, each option's return, after a game over) --------
e_mn:   HK_IN
neg_menu:
        call hidall
        HK_OUT
        di
        im 1
        jp 43366

; ---- sprites A and A + 1 for an image: A = first sprite, HL = image (48 bytes, bottom row first), C = x, D = y,
; E = palette offset. Row j of the sprite (top first) is image row 15 - j, shown when 16 <= y - j < 176 (mod 256).
show2:  push ix
        push hl
        push de
        push bc
        push af
        ld ix,0
        add ix,sp               ; ix+0 visible flag, ix+1 sprite, ix+2 x, ix+3 row, ix+4 palette, ix+5 y, ix+6/7 image
        ld bc,0x303B
        out (c),a               ; pattern slot A
        ld (ix+0),0
        ld de,45
        add hl,de
        ex de,hl                ; DE = row 15's first byte
        ld h,high nib
        ld a,(ix+5)
        ld (ix+3),a
        ld b,16
s2a:     ld a,(ix+3)             ; shown when 16 <= y - j < 176
        cp 16
        jr c,s2a0
        cp 176
        jr nc,s2a0
        ld (ix+0),a
        ld a,(de)
        ld c,a
        rrca
        rrca
        rrca
neg_pix:
        and 0x1E                ; high nibble x 2 -> 2 pattern bytes
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ld a,c
        add a,a
        and 0x1E                ; low nibble x 2
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        inc de
        ld a,(de)
        ld c,a
        rrca
        rrca
        rrca
        and 0x1E                ; high nibble x 2 -> 2 pattern bytes
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ld a,c
        add a,a
        and 0x1E                ; low nibble x 2
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        dec de
        jr s2an
s2a0:    xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
s2an:    dec de
        dec de
        dec de
        dec (ix+3)
        djnz s2a
        ld a,(ix+0)
        or a
        jp z,s2_hide
        ld a,(ix+1)
        inc a
        ld bc,0x303B
        out (c),a               ; pattern slot A + 1
        ld e,(ix+6)
        ld d,(ix+7)
        ld hl,47
        add hl,de
        ex de,hl                ; DE = row 15's third byte
        ld h,high nib
        ld a,(ix+5)
        ld (ix+3),a
        ld b,16
s2b:     ld a,(ix+3)
        cp 16
        jr c,s2b0
        cp 176
        jr nc,s2b0
        ld a,(de)
        ld c,a
        rrca
        rrca
        rrca
        and 0x1E                ; high nibble x 2 -> 2 pattern bytes
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ld a,c
        add a,a
        and 0x1E                ; low nibble x 2
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        jr s2bn
s2b0:    xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
s2bn:    dec de
        dec de
        dec de
        dec (ix+3)
        djnz s2b
        ld a,(ix+4)             ; C = palette offset << 4
        add a,a
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,(ix+5)             ; Y = 191 - y: the image's top row
        ld b,a
        ld a,191
        sub b
neg_y:  ld b,a
        ld a,(ix+2)
        and 0xF8
        ld e,a                  ; E = x & 0xF8
        ld d,32                 ; sprite A at x + 32, sprite B at x + 48 (9 bits each)
        ld a,(ix+1)
        call attrs
        ld d,48
        ld a,(ix+1)
        inc a
        call attrs
        jr s2_out
s2_hide: ld a,(ix+1)
        call hide
        inc a
        call hide
s2_out: pop af
        pop bc
        pop de
        pop hl
        pop ix
        ret

; sprite A at x E + D (9 bits), y B + 32, palette C, pattern A (4-bit)
attrs:  nextreg 0x34,a
        push af
        ld a,e
        add a,d
        nextreg 0x35,a
        ld a,0
        adc a,0
        or c
        nextreg 0x37,a
        ld a,b
        add a,32
        nextreg 0x36,a
        pop af
        push af
        or 0xC0
        nextreg 0x38,a
        ld a,0x80
        nextreg 0x39,a
        pop af
        ret

hidall: xor a
        ld b,NSPR
.h:     call hide
        inc a
        djnz .h
        ret

hide:   nextreg 0x34,a
        push af
        xor a
        nextreg 0x38,a
        pop af
        ret

        ALIGN 256
nib:    ; nibble n (4 pixels, left first) -> 2 pattern bytes
        DUP 16, n
        db ((n >> 3) & 1) * 0x10 | ((n >> 2) & 1), ((n >> 1) & 1) * 0x10 | (n & 1)
        EDUP
rom_end:

; ---- start-up, called once by the stub -------------------------------------------------------------------------
        ORG 0xD000
setup:  ld bc,0x303B            ; the NSPR pattern slots zero
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
setup_end:

        SAVEBIN "motr_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "motr_setup.bin",0xD000,setup_end-0xD000
