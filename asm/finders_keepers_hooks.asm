; Finders Keepers (Mastertronic, 1985, 48K) - hardware sprites OVER the game's XOR figures (overlay).
; One plotter (0x9A05) draws every figure: entry A = figure 0-4 (0 the Knight) in the table at 43632, 8 bytes each
; (x, y, frame, ., dx, dy, colour, mask); frame (41328) at (41329, 41330) is the new image, 16 x 16 from
; 43696 + 32 x frame; frame 0 is blank. One call XORs the old image and the new one, then the plotter writes the new
; state back into the entry. Before the XOR it calls the attribute painter 0x9CD9, which sets the cells the figure
; covers to (attr AND mask) OR (colour AND NOT mask): that is the colour clash.
; Every pixel write stays (the game never reads figure pixels or colours back). The painter call is the one hook:
;   a figure with its own ink (mask ink bits 0, mask not 0: the Knight 0x47/0xB8, the creatures 0x0n/0xF8) becomes
;   sprite n over its pixels and the painter is skipped (its four scratch bytes are written as it would);
;   a figure that paints whole cells (mask 0: a black axe on cyan, a blacked-out dragon) stays as the game draws it.
;   0x7A26 (room set-up, every room change) and 0x88F7 (every figure marked erased) hide all five.
; All hooks live in alt ROM image 1 at 0x386E, stateless (no RAM but the stack), 28 MHz inside.

        DEVICE ZXSPECTRUMNEXT

IDX     EQU 41340       ; the figure being plotted
NFRAME  EQU 41328
NEWX    EQU 41329
NEWY    EQU 41330
PLOC    EQU 41331       ; painter scratch: column, row, x & 7, y & 7
TABLE   EQU 43632
GFX     EQU 43696
NFIG    EQU 5

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
; ---- 0x9A3E CALL 0x9CD9 -> CALL e_pt ---------------------------------------------------------------
e_pt:   HK_IN
        ld a,(IDX)
        cp NFIG
        jr nc,pt_paint
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,TABLE+6
        add hl,de
        ld e,(hl)               ; colour
        inc hl
        ld d,(hl)               ; mask
        ld a,d
        or a
neg_own:
        jr z,pt_own
        and 7
        jr nz,pt_own
neg_skip:
        call show
        call ploc
        pop af                  ; HK_OUT, written out for the negative control's label
neg_spd: nextreg 0x07,a
        pop hl
        pop de
        pop bc
        pop af
        ret                     ; the painter skipped: back to 0x9A41
pt_own:  ld a,(IDX)
        call hide
pt_paint: HK_OUT
        jp 0x9CD9               ; as the game: the painter returns to 0x9A41

; ---- 0x7A26 room set-up: ADD A,A / LD H,0 displaced ------------------------------------------------
e_rm:   HK_IN
neg_room:
        call hidall
        HK_OUT
        add a,a
neg_disp:
        ld h,0
        jp 0x7A29

; ---- 0x88F7 every figure marked erased (frames 0) before a full-screen window: XOR A / LD (43634),A displaced --
e_cl:   HK_IN
neg_clear:
        call hidall
        HK_OUT
        xor a
        ld (TABLE+2),a
        jp 0x88FB

; the painter's scratch bytes, as it writes them: x / 8, y / 8, x & 7, y & 7
ploc:   ld a,(NEWX)
        ld b,a
        rrca
        rrca
        rrca
        and 31
        ld (PLOC),a
        ld a,b
        and 7
        ld (PLOC+2),a
        ld a,(NEWY)
        ld b,a
        rrca
        rrca
        rrca
        and 31
        ld (PLOC+1),a
        ld a,b
        and 7
        ld (PLOC+3),a
        ret

; E = colour, D = mask. Sprite IDX = frame NFRAME at (NEWX, NEWY), ink E & 7, BRIGHT from E or (mask bit 6 set)
; from the cell under the figure's top left; frame 0 hides it.
show:   ld a,(NFRAME)
        or a
        jr z,show_h
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,GFX
        add hl,bc
        ld a,(IDX)
        ld bc,0x303B
        out (c),a
        push de
        ld b,16
.r:     ld e,(hl)
        call pix4
        inc hl
        ld e,(hl)
        call pix4
        inc hl
        djnz .r
        pop de
        ld a,e                  ; palette offset = ink + 8 x BRIGHT
        bit 6,d
        jr z,.b
        call cellat
        ld a,(hl)
.b:     and 0x40
        rrca
        rrca
        rrca
        ld c,a
        ld a,e
        and 7
        or c
        add a,a
        add a,a
        add a,a
        add a,a
        ld c,a                  ; C = palette offset << 4
        ld a,(IDX)
        nextreg 0x34,a
        ld a,(NEWX)
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        or c
        nextreg 0x37,a
        ld a,(NEWY)
neg_y:  add a,32
        nextreg 0x36,a
        ld a,(IDX)
        or 0xC0
        nextreg 0x38,a
        ld a,0x80
        nextreg 0x39,a
        ret
show_h: ld a,(IDX)
        jp hide

; HL = attribute address of the cell at (NEWX, NEWY)
cellat: ld a,(NEWY)
        and 0xF8
        ld l,a
        ld h,0x16               ; 0x5800 / 4 + ...
        add hl,hl
        add hl,hl               ; 0x5800 + (y / 8) x 32
        ld a,(NEWX)
        rrca
        rrca
        rrca
        and 31
        or l
        ld l,a
        ret

hidall: xor a
        ld b,NFIG
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

; E = 8 pixels -> 4 pattern bytes (value 1 = ink)
pix4:   call pix2
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
rom_end:

; ---- start-up, called once by the stub --------------------------------------------------------------
        ORG 0xD000
setup:  ld bc,0x303B            ; the NFIG pattern slots zero
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

        SAVEBIN "fk_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "fk_setup.bin",0xD000,setup_end-0xD000
