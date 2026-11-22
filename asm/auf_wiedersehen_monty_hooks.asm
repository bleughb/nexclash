; Auf Wiedersehen Monty (Gremlin Graphics, 1987, 128K) - hardware sprites OVER the game's figures (overlay).
; The figure loop 0xA2AD (41645) builds, for each of five records at 42030 (13 bytes: +0 x, +1 y, +2 colour,
; +7 frame, +9 bit 7 = drawn as stored, clear = mirrored), a 3 x 3 block of composite cells: the background's cells
; copied, then the 16 x 16 image (32 bytes at 0x6000 + frame * 32, two bytes a row, top row first) ORed in,
; shifted to x & 7 and masked off scenery ink. Before each cell it paints the cell's attribute with the record's
; colour where the room map leaves it empty (41725 LD (DE),A): the colour clash. That store becomes a NOP.
; The cell renderer then copies changed cells to the screen; no game code reads figure pixels back.
; Hooks (alt ROM image 1 at 0x386E, stateless, 28 MHz inside, no alternate registers):
;   41523 CALL 41645 -> CALL e_fig: the figure loop, then sprite i for record i (its own ink, mirrored as drawn);
;   34894 (clear screen: the menu, game over) and 42878 (the room draw) hide the five.

        DEVICE ZXSPECTRUMNEXT

FIGS    EQU 42030               ; five records, 13 bytes each
NFIG    EQU 5
GFX     EQU 0x6000              ; frame images, 32 bytes each

        MACRO HK_IN                     ; the caller's speed (NR 7 bits 1:0) kept on the stack (alt ROM: no RAM latch;
        push af                         ; card patch.restore-speed), then 28 MHz
        push bc
        push de
        push hl
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        ENDM
        MACRO HK_OUT
        pop af
        nextreg 0x07,a                  ; the caller's speed back
        pop hl
        pop de
        pop bc
        pop af
        ENDM

        ORG 0x386E
; ---- 41523 CALL 41645 -> CALL e_fig ----------------------------------------------------------------------------
e_fig:  call 41645              ; the game's figure loop, as before
        HK_IN
        push ix
        ld ix,FIGS
        xor a
fg_loop: push af
neg_fig: call show1
        ld de,13
        add ix,de
        pop af
        inc a
        cp NFIG
        jr nz,fg_loop
        pop ix
        pop af                  ; HK_OUT, written out for the negative control's label
neg_spd: nextreg 0x07,a
        pop hl
        pop de
        pop bc
        pop af
        ret

; ---- 34894 LD HL,16384 -> JP e_cls: the clear-screen routine ---------------------------------------------------
e_cls:  HK_IN
neg_cls: call hide5
        HK_OUT
        ld hl,16384
        jp 34897

; ---- 42878 CALL 42940 -> CALL e_room: inside the room draw -----------------------------------------------------
e_room: HK_IN
neg_room: call hide5
        HK_OUT
        jp 42940

; ---- sprite A (pattern slot A) for the record at IX -------------------------------------------------------------
show1:  ld bc,0x303B
        out (c),a               ; pattern slot A
        push af
        ld l,(ix+7)             ; HL = GFX + frame * 32
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,GFX
        add hl,de
        ex de,hl                ; DE = the image
        ld h,high nib
        ld b,32                 ; 32 image bytes -> 4 pattern bytes each
sh_pix: ld a,(de)
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
        djnz sh_pix
        pop af
        nextreg 0x34,a          ; the sprite
        ld b,a
        ld a,(ix+0)             ; X = x + 32 (9 bits)
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        ld c,a                  ; C = X8
        ld a,(ix+2)             ; palette offset = ink + 8 x BRIGHT, in bits 7-4
        ld e,a
        and 7
        bit 6,e
        jr z,sh_nb
        or 8
sh_nb:  add a,a
        add a,a
        add a,a
        add a,a
        or c
        bit 7,(ix+9)            ; bit 7 clear: the game draws it mirrored
        jr nz,sh_nm
neg_mir: or 8                   ; X mirror
sh_nm:  nextreg 0x37,a
        ld a,(ix+1)             ; Y = y + 32 (9 bits)
neg_y:  add a,32
        nextreg 0x36,a
        ld a,0
        adc a,0
        or 0x80                 ; 4-bit pattern, Y8
        ld c,a
        ld a,b
        or 0xC0                 ; visible, fifth byte
        nextreg 0x38,a
        ld a,c
        nextreg 0x39,a
        ret

hide5:  xor a
        ld b,NFIG
hd_lp:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz hd_lp
        ret

        ALIGN 256
nib:    ; nibble n (4 pixels, left first) -> 2 pattern bytes
        DUP 16, n
        db ((n >> 3) & 1) * 0x10 | ((n >> 2) & 1), ((n >> 1) & 1) * 0x10 | (n & 1)
        EDUP
rom_end:

; ---- start-up, called once by the stub -------------------------------------------------------------------------
        ORG 0xD000
setup:  ld bc,0x303B            ; the five pattern slots zero
        xor a
        out (c),a
        ld d,NFIG
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
        xor a                   ; all 128 hidden: another program may have left any of them visible
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ld hl,printer           ; the snapshot's printer buffer back: NEXLOAD overwrote it, the game reads it
        ld de,0x5B00
        ld bc,256
        ldir
        ret
colours:
        db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6
        db 0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF
setup_end:
printer:                        ; 256 bytes from the snapshot, appended by the engine

        SAVEBIN "awm_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "awm_setup.bin",0xD000,setup_end-0xD000
