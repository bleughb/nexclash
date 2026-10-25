; The Incredible Shrinking Fireman (Mastertronic, 1986, 48K) - hardware sprites over the figures.
; games/incredible_shrinking_fireman-add-OPUS.md "Phase B design". Overlay, not removal: the game's
; plotter (0xB950, XOR old ^ new) and the collectable drawing (0xECFF) still write the ULA exactly as
; the original; every figure / collectable gets sprites exactly on its pixels, in front. Only the
; figure attribute painting is removed (0xBCDF LD (IX+0),A -> NOP x3, no hook).
;
; Patch sites (original bytes checked by the engine):
;   0xBC5C  DD E1 C9   POP IX / RET (plotter exit, HL = OBJ + 8a + 2)  -> JP e_plot
;   0xECFF  11 14 ED   LD DE,0xED14 (one collectable: B = bottom line, C = column) -> JP e_item
;   0xC4A7  21 00 40   LD HL,0x4000 (screen clear)                     -> JP e_c1
;   0xC5B1  21 00 48   LD HL,0x4800 (clear of lines 64-191)            -> JP e_c2
;   0xB4AD  21 00 40   LD HL,0x4000 (screen clear)                     -> JP e_c3
; Code: alt ROM image 1 from 0x3A01 (0x39FF-0x3A00 stay FF FF: the game's IM 2 vector is read
; there). Hooks run with interrupts OFF (IFF saved with LD A,I twice, restored) at 28 MHz; Next
; pages 26-30 (colour map; flags byte in page 30) are mapped at slot 0 only inside a hook.
; Sprites: collectables 0-4 (4-bit patterns 0-4), enemy 2 = 5/6, enemy 1 = 7/8, fireman = 9/10
; (higher number on top). Object a: sprites 9-2a (lines 0-15) and 10-2a (lines 16-23) from the
; 256-byte pattern slot 5-a (N6 = 0 / 1).

        DEVICE ZXSPECTRUMNEXT

OBJ     EQU 0xBCF7              ; object table: x, y, frame, -, dx, dy, attribute, keep-mask
GBASE   EQU 0xBD42              ; graphics base (word)
GFX0    EQU 0x9C40              ; colour-map index 0 = this address
ITEMG   EQU 0xED14              ; collectable graphic, 7 bytes (byte j drawn on line B - j)
IDX_IT  EQU 4144                ; colour-map index of ITEMG
CPAGE   EQU 26                  ; colour map: page 26 + i / 1024, offset (i % 1024) * 8
FLAGS   EQU 0x1F00              ; shown bits (1 << a), page CPAGE + 4 at slot 0

        ORG 0x3A01
; ---- plotter exit -------------------------------------------------------------------------
e_plot: pop ix                  ; the replaced instruction
        push af
        ld a,i
        jp pe,.on
        ld a,i                  ; NMOS quirk: read twice
.on:    di
        push af                 ; P/V = IFF at entry
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld a,l
        sub low (OBJ+2)
        rrca
        rrca
        rrca
        and 0x1F
        cp 3
        call c,plot_obj
leave:  nextreg 0x50,0xFF
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        jp po,.off
        pop af
        ei
        ret
.off:   pop af
        ret

; ---- one collectable: stack +0 return 0xECF3, +2 HL, +4 BC (B = loop counter 5..1) ----------
e_item: push af
        ld a,i
        jp pe,.on
        ld a,i
.on:    di
        push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld hl,15                ; AF x2, BC, DE, HL pushed + 5 = the loop counter B
        add hl,sp
        ld a,5
        sub (hl)
        cp 5
        call c,item             ; A = k (0-4), B = bottom line, C = column
        nextreg 0x50,0xFF
        nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        jp po,.off
        pop af
        ld de,ITEMG
        ei
        jp 0xED02
.off:   pop af
        ld de,ITEMG
        jp 0xED02

; ---- screen clears: hide every sprite, forget what is shown -------------------------------
e_c1:   call hideall
        ld hl,0x4000
        jp 0xC4AA
e_c2:   call hideall
        ld hl,0x4800
        jp 0xC5B4
e_c3:   call hideall
        ld hl,0x4000
        jp 0xB4B0

hideall:
        push af
        ld a,i
        jp pe,.on
        ld a,i
.on:    di
        push af
        push bc
        ld b,11
.h:     ld a,b
        dec a
        nextreg 0x34,a
        nextreg 0x38,0x40
        djnz .h
        nextreg 0x50,CPAGE+4
        xor a
        ld (FLAGS),a
        nextreg 0x50,0xFF
        pop bc
        pop af
        jp po,.off
        pop af
        ei
        ret
.off:   pop af
        ret

; ---- A = object a (0-2) ---------------------------------------------------------------------
plot_obj:
        ld e,a                  ; E = a
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld bc,OBJ
        add hl,bc               ; HL = object
        inc hl
        inc hl
        ld d,(hl)               ; D = frame
        dec hl
        dec hl
        ld a,e
        ld b,1
        or a
        jr z,.m1
.m0:    sla b
        dec a
        jr nz,.m0
.m1:    nextreg 0x50,CPAGE+4
        ld a,(FLAGS)
        or b
        inc d
        dec d
        jr nz,.st
        xor b                   ; frame 0: not shown
.st:    ld (FLAGS),a
        ld a,d
        or a
        call nz,draw_obj
; visibility of all three objects (enemies 1 and 2 on one spot with one frame: both hidden)
vis_all:
        nextreg 0x50,CPAGE+4
        ld a,(FLAGS)
        ld c,a
        and 6
        cp 6
        jr nz,.np
        ld hl,OBJ+8
        ld de,OBJ+16
        ld b,3
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.np
        inc hl
        inc de
        djnz .cmp
        ld a,c
        and 1
        ld c,a
.np:    ld e,9                  ; top sprite of object 0; then 7, 5
        ld b,3
.v:     ld a,c
        rrca
        ld c,a                  ; carry = shown
        ld a,0
        rra
        or 0x40                 ; visible bit + attribute 4 on
        ld d,a
        ld a,e
        inc a
        srl a                   ; pattern slot 5 - a = (E + 1) / 2
        or d
        ld d,a
        ld a,e
        nextreg 0x34,a
        ld a,d
        nextreg 0x38,a
        ld a,e
        inc a
        nextreg 0x34,a
        ld a,d
        nextreg 0x38,a
        dec e
        dec e
        djnz .v
        ret

; HL = object, E = a, D = frame (non-zero): positions, live ink, pattern upload
draw_obj:
        push hl
        ld bc,6
        add hl,bc
        ld a,(hl)               ; attribute E
        inc hl
        ld b,(hl)               ; keep-mask D
        ld c,a
        and 7
        jr nz,.ink
        ld a,8                  ; ink 0: black
        jr .ik
.ink:   ld l,a
        ld a,c
        or b
        and 0x40
        ld a,l
        jr z,.ik
        add a,8                 ; bright (from E, or kept from the BRIGHT room cells)
.ik:    ld c,a                  ; C = live ink (palette index)
        pop hl
        push bc
        push de
        ld a,e
        add a,a
        cpl
        add a,10
        ld d,a                  ; D = top sprite 9 - 2a
        ld b,32
        ld e,0x80               ; attribute 4: 4-bit, N6 = 0
        call setpos
        inc d
        ld b,48
        ld e,0xC0               ; N6 = 1
        call setpos
        pop de
        pop bc
        ld a,5
        sub e
        push bc
        ld bc,0x303B
        out (c),a               ; upload slot 5 - a from its start
        pop bc
        ld a,d
        add a,a
        add a,d                 ; 3 * frame, 8 bits (as the plotter)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        push de
        ld de,(GBASE)
        add hl,de               ; HL = graphic
        push hl
        ld de,-GFX0
        add hl,de
        ex de,hl                ; DE = colour-map index
        pop hl
        ld b,48
.lp:    ld a,(hl)
        call emit
        inc hl
        inc de
        djnz .lp
        xor a
        ld b,64                 ; lines 24-31: transparent
.z:     out (0x5B),a
        djnz .z
        pop de
        ret

; D = sprite, HL = object (x, y), B = Y offset, E = attribute 4
setpos: ld a,d
        nextreg 0x34,a
        ld a,(hl)
        add a,32
        nextreg 0x35,a
        ld a,0
        rla
        nextreg 0x37,a          ; X8, palette offset 0
        inc hl
        ld a,(hl)
        dec hl
        add a,b
        nextreg 0x36,a
        ld a,e
        nextreg 0x39,a
        ret

; A = k (0-4), B = bottom line, C = column
item:   ld e,a
        push bc
        ld a,b
        and 0xF8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl               ; line / 8 * 32
        ld b,0
        add hl,bc
        ld bc,0x5800
        add hl,bc
        ld d,(hl)               ; the cell's attribute
        pop bc
        ld a,d
        and 7
        jr nz,.i1
        ld a,8
        jr .i2
.i1:    bit 6,d
        jr z,.i2
        add a,8
.i2:    ld d,a                  ; D = ink
        ld a,e
        nextreg 0x34,a
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,32
        nextreg 0x35,a
        ld a,0
        rla
        nextreg 0x37,a
        ld a,b
        add a,26                ; top line B - 6, + 32
        nextreg 0x36,a
        ld a,e
        and 1
        rrca
        rrca
        or 0x80                 ; 4-bit, N6 = k & 1
        nextreg 0x39,a
        ld a,e
        srl a
        or 0xC0                 ; visible, attribute 4 on, slot k / 2
        nextreg 0x38,a
        ld a,e
        rrca                    ; bit 7 = k & 1 (+128 bytes), bits 6-0 = k / 2
        ld bc,0x303B
        out (c),a
        ld c,d                  ; C = ink
        ld hl,ITEMG+6           ; sprite line 0 = top line B - 6 = byte 6
        ld de,IDX_IT+6
        ld b,7
.lp:    ld a,(hl)
        call emit
        xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        dec hl
        dec de
        djnz .lp
        xor a
        ld b,72                 ; lines 7-15
.z:     out (0x5B),a
        djnz .z
        ret

; A = graphics byte, DE = colour-map index, C = live ink: 8 pixels -> 4 bytes to port 0x5B.
; Pixel = the entry's nibble when its check byte equals the graphics byte, else ink / transparent.
emit:   push hl
        push de
        push bc
        ld b,a
        ld hl,ZERO4
        ld a,d
        cp 0x14                 ; index >= 5120: outside pages 26-30, defaults
        jr nc,.go
        srl a
        srl a
        add a,CPAGE
        nextreg 0x50,a
        ld a,d
        and 3
        ld h,a
        ld l,e
        add hl,hl
        add hl,hl
        add hl,hl               ; (i % 1024) * 8
        push hl
        ld de,4
        add hl,de
        ld a,(hl)
        pop hl
        cp b
        jr z,.go
        ld hl,ZERO4
.go:    ld e,4
.byte:  ld d,(hl)
        inc hl
        ld a,d
        and 0xF0
        jr nz,.lm
        sla b
        jr nc,.r
        ld a,c
        add a,a
        add a,a
        add a,a
        add a,a
        or d
        ld d,a
        jr .r
.lm:    sla b
.r:     ld a,d
        and 0x0F
        jr nz,.rm
        sla b
        jr nc,.o
        ld a,d
        or c
        ld d,a
        jr .o
.rm:    sla b
.o:     ld a,d
        out (0x5B),a
        dec e
        jr nz,.byte
        pop bc
        pop de
        pop hl
        ret
ZERO4:  defb 0,0,0,0
rom_end:

; ---- setup (stub bank, 0xD000): sprite palette, all sprites hidden, sprites on --------------
        ORG 0xD000
setup:  nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0          ; nibble 0 transparent
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
pal:    defb 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "isf_rom.bin",0x3A01,rom_end-0x3A01
        SAVEBIN "isf_setup.bin",0xD000,setup_end-0xD000
