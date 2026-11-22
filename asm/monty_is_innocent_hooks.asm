; Monty is Innocent (Gremlin Graphics, 1985, 48K) - hardware sprites OVER the game's XOR figures (overlay).
; One plotter, 0xD52E (54574), draws every figure: it XORs the previous image at the old place ((24960) image,
; (24958) x, (24959) y; y = 195: none) and the new one at the new place (HL image, C x, B y), 24 rows x 3 bytes,
; bottom row first at screen row 191 - y, pre-shifted for x & 6 (image + 144 x ((x >> 1) & 3)). It is called for
; Sam Stoat (the player), Monty (later rooms), the guards (records at 24962, 8 bytes: +0 y, +1 x, +2/3 image, +6 ink) and for panel icons,
; room items and the ending; only the movers become sprites (by caller). The guard routine paints the cells under a
; guard with its ink (painter 0xD5D8, store 54766): the colour clash. That store becomes a NOP.
; Hooks (alt ROM image 1 at 0x386E, stateless, 28 MHz inside, no alternate registers):
;   54574 PUSH HL / PUSH BC / PUSH DE -> JP e_plot: the four sprites of the figure being drawn, then the plotter;
;   55506 LD HL,16384 -> JP e_cls (the screen clear before a room, the ending): all twenty hidden.
; Figure f uses sprites / 4-bit patterns 4f .. 4f + 3: 0 Sam Stoat, 1 Monty, 2-4 guards 0-2.

        DEVICE ZXSPECTRUMNEXT

GUARDS  EQU 24962               ; three guard records, 8 bytes each
NSPR    EQU 20

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
; ---- 54574 PUSH HL / PUSH BC / PUSH DE -> JP e_plot ------------------------------------------------------------
e_plot: HK_IN
        push ix
        ld hl,10
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = the caller's return address
        ld hl,mov_tab
pl_find: ld a,(hl)
        inc hl
        or (hl)
        jr z,pl_none            ; end of the table: not a figure (an icon, an item, the ending)
        dec hl
        ld a,(hl)
        cp e
        jr nz,pl_next
        inc hl
        ld a,(hl)
        cp d
        jr z,pl_hit
        dec hl
pl_next: inc hl
        inc hl
        inc hl
        jr pl_find
pl_hit: inc hl
        ld a,(hl)               ; the figure: 0 Sam, 1 Monty, 0xFF a guard drawn, 0xFE a guard erased (both from IX)
        cp 0xFE
        jr c,pl_fix
        ld c,a                  ; C = 0xFE / 0xFF (the caller's BC is read back from the stack below)
        push ix
        pop hl
        ld de,-GUARDS
        add hl,de               ; HL = IX - GUARDS = 8 x the guard's index
        ld a,h
        or a
        jr nz,pl_none
        ld a,l
        and 7
        jr nz,pl_none
        ld a,l
        cp 24
        jr nc,pl_none
        rrca
        rrca
        rrca
        add a,2                 ; figure 2 + index
        ld e,a
        ld a,(ix+6)
        and 7
        ld d,a                  ; D = the guard's ink
        ld a,c
        cp 0xFE
        ld a,e
        jr nz,pl_go
        add a,a                 ; the gun caught it: the game XORs it off the screen, so its sprites go too
        add a,a
neg_kill:
        call hide4
        jr pl_none
pl_fix: ld d,7                  ; Sam and Monty: white
pl_go:  add a,a
        add a,a                 ; A = first sprite 4f
        ld e,d                  ; E = palette offset (ink)
        ld hl,6                 ; stack: IX +0, HL +2, DE +4, BC +6, AF +8, the return address +10
        add hl,sp
        ld c,(hl)               ; the caller's BC (pushed by HK_IN): C = x, B = y
        inc hl
        ld b,(hl)
        ld hl,2
        add hl,sp
        push af
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = the new image's base (the caller's HL)
        ld a,c                  ; + 144 x ((x >> 1) & 3): the pre-shifted copy the plotter takes
        rrca
        and 3
        jr z,pl_s0
        push de
        ld de,144
pl_sh:  add hl,de
        dec a
        jr nz,pl_sh
        pop de
pl_s0:  pop af
        ld d,a                  ; D = first sprite
        ld a,b
        cp 192
        jr nc,pl_off            ; drawn below the screen: nothing shown
neg_fig: call show4
        jr pl_none
pl_off: ld a,d
        call hide4
pl_none:
        pop ix
        HK_OUT
        push hl
        push bc
        push de
neg_end:
        jp 54577

mov_tab:                        ; return address (call site + 3), figure
        dw 56133
        db 0
        dw 55676
        db 0
        dw 55142
        db 1
        dw 55749
        db 1
        dw 54958
        db 0xFF
        dw 54900
        db 0xFF
        dw 52381                ; the gun: the guard's image XORed off (old y 195), then marked dead
        db 0xFE
        dw 0

; ---- 55506 LD HL,16384 -> JP e_cls: the screen clear ------------------------------------------------------------
e_cls:  HK_IN
neg_cls: call hidall
        HK_OUT
        ld hl,16384
        jp 55509

; ---- the four sprites D .. D + 3 for the 24 x 24 image at HL (bottom row first), C = x, B = y, E = palette ----
; Sprite D: image bytes 0-1, rows 23..8 (top first); D + 1: byte 2, the same rows; D + 2 / D + 3: rows 7..0.
; Image row r is shown when y + r <= 191.
show4:  push ix
        push hl
        push de
        push bc
        ld ix,0
        add ix,sp               ; ix+0 c (x), ix+1 b (y), ix+2 e (palette), ix+3 d (first sprite), ix+4/5 image
        ld a,(ix+1)
        cp 169
        jr nc,sh_slow           ; part of the image above the screen: the row-checked path
        push hl                 ; fast path: every row shown; lower sprites' rows 8-15 stay clear (set-up)
        ld de,69                ; image row 23
        add hl,de
        ex de,hl
        ld a,(ix+3)
        ld b,16
        call pfl                ; D: bytes 0-1, rows 23..8
        pop hl
        push hl
        ld de,71
        add hl,de
        ex de,hl
        ld a,(ix+3)
        inc a
        ld b,16
        call pfr                ; D + 1: byte 2, rows 23..8
        pop hl
        push hl
        ld de,21                ; image row 7
        add hl,de
        ex de,hl
        ld a,(ix+3)
        add a,2
        ld b,8
        call pfl                ; D + 2: rows 7..0
        pop hl
        ld de,23
        add hl,de
        ex de,hl
        ld a,(ix+3)
        add a,3
        ld b,8
        call pfr                ; D + 3
        jr sh_attr
sh_slow:
        ld a,(ix+3)
        ld b,23
        ld c,0
        call pat                ; D: left, rows 23..8
        ld a,(ix+3)
        inc a
        ld b,23
        ld c,1
        call pat                ; D + 1: right, rows 23..8
        ld a,(ix+3)
        add a,2
        ld b,7
        ld c,0
        call pat                ; D + 2: left, rows 7..0
        ld a,(ix+3)
        add a,3
        ld b,7
        ld c,1
        call pat                ; D + 3: right, rows 7..0
sh_attr:
        ld a,(ix+1)             ; top of the image: screen row 168 - y; sprite Y = that + 32
        ld b,a
        ld a,200
        sub b
neg_y:  ld b,a                  ; B = Y of the upper pair
        ld a,(ix+0)
        and 0xF8
        ld e,a                  ; E = x & 0xF8
        ld a,(ix+2)
        add a,a
        add a,a
        add a,a
        add a,a
        ld c,a                  ; C = palette offset << 4
        ld a,(ix+3)
        ld d,32
        call attrs
        inc a
        ld d,48
        call attrs
        ld a,b
        add a,16
        ld b,a
        ld a,(ix+3)
        add a,2
        ld d,32
        call attrs
        inc a
        ld d,48
        call attrs
        pop bc
        pop de
        pop hl
        pop ix
        ret

; pattern A (4-bit, slot A's first half) from the image at (ix+4): 16 rows, image rows B, B - 1, ...; C = 0: bytes
; 0-1 (16 pixels), C = 1: byte 2 (8 pixels, the rest clear). Rows past the image's bottom or above the screen clear.
pat:    push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld a,16
pt_row: push af
        ld a,b
        cp 24                   ; past row 0 (B wrapped) or a lower sprite's rows 8-15
        jr nc,pt_zero
        push bc
        ld c,a                  ; shown when y + r <= 191
        ld a,(ix+1)
        add a,c
        pop bc
        jr c,pt_zero
        cp 192
        jr nc,pt_zero
        ld l,(ix+4)             ; HL = image + 3 r (+ 2 for the right sprite)
        ld h,(ix+5)
        ld a,b
        add a,a
        add a,b
        add a,c
        add a,c
        add a,l
        ld l,a
        jr nc,pt_nc
        inc h
pt_nc:  ld a,(hl)
        call nib2
        ld a,c
        or a
        jr nz,pt_rgt
        inc hl
        ld a,(hl)
        call nib2
        jr pt_next
pt_rgt: xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        jr pt_next
pt_zero: xor a
        ld e,8
pt_z:   out (0x5B),a
        dec e
        jr nz,pt_z
pt_next: dec b
        pop af
        dec a
        jr nz,pt_row
        ret

; A = 8 pixels -> 4 pattern bytes (two pixels a byte, high nibble left). HL kept.
nib2:   push hl
        push de
        ld e,a
        ld h,high nib
        rrca
        rrca
        rrca
        and 0x1E
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ld a,e
        add a,a
        and 0x1E
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        pop de
        pop hl
        ret

; fast pattern loops: A = pattern slot, DE = image row's first byte (pfl) or third byte (pfr), B = rows, upward in
; the image (3 bytes back a row). pfl: two bytes a row (16 pixels); pfr: one byte and 8 clear pixels.
pfl:    push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld h,high nib
pl_row: ld a,(de)
        ld c,a
        rrca
        rrca
        rrca
neg_pix:
        and 0x1E                ; high nibble x 2
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
        and 0x1E
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ld a,c
        add a,a
        and 0x1E
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ld a,e                  ; DE - 4: the row below's first byte
        sub 4
        ld e,a
        jr nc,pl_nc
        dec d
pl_nc:  djnz pl_row
        ret

pfr:    push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld h,high nib
pr_row: ld a,(de)
        ld c,a
        rrca
        rrca
        rrca
        and 0x1E
        ld l,a
        ld a,(hl)
        out (0x5B),a
        inc l
        ld a,(hl)
        out (0x5B),a
        ld a,c
        add a,a
        and 0x1E
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
        ld a,e                  ; DE - 3
        sub 3
        ld e,a
        jr nc,pr_nc
        dec d
pr_nc:  djnz pr_row
        ret

; sprite A at x E + D (9 bits), y B, palette C, pattern A (4-bit, visible)
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
        nextreg 0x36,a
        pop af
        push af
        or 0xC0
        nextreg 0x38,a
        ld a,0x80
        nextreg 0x39,a
        pop af
        ret

hide4:  ld b,4
h4:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz h4
        ret

hidall: xor a
        ld b,NSPR
ha:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz ha
        ret

        ALIGN 256
nib:    ; nibble n (4 pixels, left first) -> 2 pattern bytes
        DUP 16, n
        db ((n >> 3) & 1) * 0x10 | ((n >> 2) & 1), ((n >> 1) & 1) * 0x10 | (n & 1)
        EDUP
rom_end:

; ---- start-up, called once by the stub -------------------------------------------------------------------------
        ORG 0xD000
setup:  ld bc,0x303B            ; the twenty pattern slots zero
        xor a
        out (c),a
        ld d,NSPR
.p:     ld b,0
.q:     out (0x5B),a
        djnz .q
        dec d
        jr nz,.p
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        ld hl,colours           ; offset n, index 1 = Spectrum ink n
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
        cp 8
        jr nz,.c
        nextreg 0x4B,0
        xor a                   ; all 128 hidden: another program may have left any of them visible
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
colours:
        db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
setup_end:

        SAVEBIN "mii_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "mii_setup.bin",0xD000,setup_end-0xD000
