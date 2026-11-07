; Pac-Mania (Grandslam 1988, Teque; 48K form) - hardware sprites for every figure.
; The plotter keeps running with its three buffer writes NOPed (same registers, same time), so the back
; buffer stays scenery only and the ULA never shows a figure. All hooks live in alt ROM image 1 at
; 0x386E, are stateless, read only the game's own tables and leave interrupts on: the game's ISR uses
; no NEXTREG, IX or IY.
;
; Patch sites (original bytes checked by pacmania.py):
;   0x87AA 0x88E9 0x891B 0x7B9A  CALL 0xB090 (blit after a figure pass) -> CALL e_b1..e_b4
;   0xB094  CALL 0xAF1F (inside the blit)                              -> CALL e_hide
;   0xAEED 0xAEF4 0xAEFB  LD (BC),A (plotter)                          -> NOP
;   0x8A17 0x8A1B  LD (HL),A (Pac-Man's yellow cells, rows 5-10, columns 11-12) -> NOP
; Sprites: slot n = n-th figure plotted (table 0xA982 of record pointers, sorted by y): a higher slot is on
; top, as the later plot is. Record: +0 x, +1 y, +2 frame, +3 height above ground. Patterns 0-85 = frame, 86-95 fruit score forms, 96-101 ghost score forms.
; Nibbles: 0 transparent, 1 the figure's ink (palette offset picks it), 2-14 fixed colours, 15 black paper.

        DEVICE ZXSPECTRUMNEXT

BLIT    EQU 0xB090
ADDR    EQU 0xAF1F
COUNT   EQU 0xB335
ROOM    EQU 0xB336
ORDER   EQU 0xA982
PACREC  EQU 0xB3B4
NSLOT   EQU 12
NFRAME  EQU 86

        ORG 0x386E
; ---- blit after a figure pass: the blit returns to c_n, which commits the sprites as it ends.
; ex (sp),hl twice swaps the return address without touching flags or SP.
e_b1:   ex (sp),hl
        ld hl,c1
        ex (sp),hl
        jp BLIT
e_b2:   ex (sp),hl
        ld hl,c2
        ex (sp),hl
        jp BLIT
e_b3:   ex (sp),hl
        ld hl,c3
        ex (sp),hl
        jp BLIT
e_b4:   ex (sp),hl
        ld hl,c4
        ex (sp),hl
        jp BLIT
c1:     call com_p
        jp 0x87AD
c2:     call com_p
        jp 0x88EC
c3:     call com_p
        jp 0x891E
c4:     call com_a              ; the theatre: no yellow cells, Pac-Man has the room's ink as well
        jp 0x7B9D

; ---- the blit's address call: any blit not from c_n shows a screen with no figures ----
e_hide: push af
        push hl
        ld hl,7
        add hl,sp               ; high byte of the blit's return address
        ld a,(hl)
        cp 0x40
        jr c,.keep
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NSLOT
        jr nz,.h
.keep:  pop hl
        pop af
        jp ADDR

com_p:  push af
        ld a,1
        jr com
com_a:  push af
        xor a
com:    push bc
        push de
        push hl
        ld e,a                  ; E = 1: the record 0xB3B4 is yellow
        ld a,(ROOM)
        ld c,a
        and 7
        bit 6,c
        jr z,.nb
        or 8
.nb:    rlca
        rlca
        rlca
        rlca
        ld d,a                  ; D = room's palette offset, in attribute 3's bits
        ld b,0
.slot:  ld a,b
        nextreg 0x34,a
        ld a,(COUNT)
        cp b
        jr z,.hide
        jr c,.hide
        ld a,b
        add a,a
        add a,low ORDER         ; (0xA982 + 22 has no carry)
        ld l,a
        ld h,high ORDER
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = record
        inc hl
        inc hl
        ld a,(hl)
        cp 0xFF
        jr z,.hide
        cp 0x50
        jr z,.hide
        cp NFRAME
        jr nc,.hide
        cp 85
        call z,v85              ; frames 85 and 81 are rewritten at run time: patterns 86-95 and 96-101
        cp 81
        call z,v81
        ld c,a                  ; C = pattern
        dec hl
        dec hl
        ld a,(hl)               ; x as 0xAF1F: 0xB0 up means 0 (off the view)
        cp 0xB0
        jr c,.x
        xor a
.x:     add a,24                ; buffer x - 8 = screen x, + 32
        nextreg 0x35,a
        inc hl
        ld a,(hl)               ; y as 0xAF0E: below 0xA8, height comes off (floor 0)
        inc hl
        inc hl
        cp 0xA8
        jr nc,.y
        sub (hl)
        jr nc,.y
        xor a
.y:     cp 0xB8
        jr c,.y2
        sub 192                 ; the buffer is a ring of 192 lines: 0xB8 up comes in at the top
.y2:    add a,32
        nextreg 0x36,a
        dec hl
        dec hl
        dec hl                  ; HL = record
        ld a,e
        or a
        ld a,d
        jr z,.ink
        ld a,l
        cp low PACREC
        ld a,d
        jr nz,.ink
        ld a,h
        cp high PACREC
        ld a,d
        jr nz,.ink
        ld a,0xE0               ; bright yellow, attribute 0x46
.ink:   nextreg 0x37,a
        ld a,c
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        jr .next
.hide:  nextreg 0x38,0
.next:  inc b
        ld a,b
        cp NSLOT
        jp nz,.slot
        pop hl
        pop de
        pop bc
        pop af
        ret
; ---- frames rewritten at run time: which form is in the frame now? A = its pattern, or the frame if none ----
v85:    push bc
        push de
        push hl
        ld hl,0xCC18            ; fruit score: 0x96B8 copies 16 bytes from here to 0xC5D8
        ld de,0xC5D8
        ld bc,10 << 8 | 86      ; B = forms, C = first pattern
        ld a,85
        jr vv
v81:    push bc
        push de
        push hl
        ld hl,0xCBB8            ; ghost score: 0x9224 copies 16 bytes from here to 0xC558
        ld de,0xC558
        ld bc,6 << 8 | 96
        ld a,81
vv:     push af
.t:     push bc
        push de
        push hl
        ld b,16
.c:     ld a,(de)
        cp (hl)
        jr nz,.no
        inc hl
        inc de
        djnz .c
        pop hl
        pop de
        pop bc
        pop af
        ld a,c
        jr .end
.no:    pop hl
        pop de
        pop bc
        push de
        ld de,16
        add hl,de
        pop de
        inc c
        djnz .t
        pop af
.end:   pop hl
        pop de
        pop bc
        ret
rom_end:

; --- setup routine (stub bank, 0xD000): patterns from bank 11, palette, clip, hide all, sprites on ---
        ORG 0xD000
setup:  ld bc,0x303B
        xor a
        out (c),a
        nextreg 0x57,22             ; bank 11 lower page at 0xE000
        ld hl,0xE000
        ld d,32                     ; 8K
.u:     ld bc,0x005B
        otir
        dec d
        jr nz,.u
        nextreg 0x57,23
        ld hl,0xE000
        ld d,19                     ; 102 patterns x 128 bytes = 51 x 256
.v:     ld bc,0x005B
        otir
        dec d
        jr nz,.v
        nextreg 0x57,21
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,inks

.row:   xor a
        nextreg 0x41,a              ; 0: transparent by index (NR 0x4B)
        ld a,(hl)
        inc hl
        nextreg 0x41,a              ; 1: the row's ink
        exx
        ld hl,fixed
        ld b,14
.f:     ld a,(hl)
        inc hl
        nextreg 0x41,a              ; 2-15
        djnz .f
        exx
        ld a,l
        sub low inks
        cp 16
        jr nz,.row
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2              ; reset the sprite clip index
        nextreg 0x19,8
        nextreg 0x19,167
        nextreg 0x19,8
        nextreg 0x19,183            ; the blit's window, columns 1-20, rows 1-22
        nextreg 0x15,0x01
        ret
inks:   db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6     ; attribute inks, offset 0-7
        db 0x00,0x03,0xE0,0xE3,0x1C,0x1F,0xFC,0xFF     ; bright, offset 8-15
fixed:  db 0xE8,0xB8,0xF6,0xF1,0x56,0x6E,0xB7,0xFC,0x54,0xBE,0xF8,0xFF,0xD8,0x00     ; fitted to the Spec256 colours; black last
setup_end:

        SAVEBIN "pm_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "pm_setup.bin",0xD000,setup_end-0xD000
