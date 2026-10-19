; Jetpac (Ultimate, 1983, 16K) - hardware sprites for every figure the move-and-redraw plotter
; (30522) draws: Jetman, aliens, rocket parts, fuel, items, explosions.
; All hooks are stateless and live in alt ROM image 1 at 0x386E (read-only). Interrupts may be
; on at every site (IM 1, ROM handler reads IY): the hooks use only pushes below SP and NEXTREG,
; never IX/IY/I/IFF or the alternate registers (the plotter keeps state in them).
;
; Patch sites (original bytes checked by jetpac.py):
;   29263  1A 47 32   LD A,(DE) / LD B,A / LD (24004),A (new-frame setup, after 29448: HL = screen
;                     address of the bottom line, DE -> W, IX = object)        -> JP e_nw
;   29344  CD 27 72   CALL 29223 (erase only, graphic in DE)                    -> CALL e_e1
;   29349  CD 24 72   CALL 29220 (erase only)                                   -> CALL e_e2
;   24717  CD B8 71   CALL 29112 (screen clear, every new screen)              -> CALL e_cls
; Screen-write patches (no hook): 30532 77 -> 00 (erase AND), 30561 77 -> 00 (draw OR),
;   29171 72 -> 00 (object colour over its cells).
; Sprites: object i = (IX - 23808) / 8 (0-16) owns sprites 6i .. 6i+5: 2 rows x (2 columns + a copy
; of the column that crosses x = 256 at x - 256, as the ULA wraps the row).
; Patterns (4-bit, ink = 1) and their lookup: asm/jetpac_tables.asm (generated).

        DEVICE ZXSPECTRUMNEXT

OBJ0    EQU 23808
NOBJ    EQU 17
LEVEL   EQU 24048
PART    EQU 23860

        ORG 0x386E
; ---- new frame of an object ----
e_nw:   push af
        push bc
        push de
        push hl
        nextreg 0x07,3          ; the hook at 28 MHz (~4K T per draw: table search + 6 sprites)
        call draw
        nextreg 0x07,0          ; the game runs at 3.5 MHz (stub: NEXTREG $07,0)
        pop hl
        pop de
        pop bc
        pop af
        ld a,(de)
        ld b,a
        ld (24004),a
        jp 29268

; ---- erase-only entries: hide the object's sprites ----
e_e1:   call hideobj
        jp 29223
e_e2:   call hideobj
        jp 29220

; ---- screen clear: hide every sprite ----
e_cls:  push af
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NOBJ*6
        jr nz,.h
        pop af
        jp 29112

; carry clear + A = first sprite of the object IX; carry set if IX is not an object slot
objbase:
        ld a,ixh
        cp high OBJ0
        jr nz,.no
        ld a,ixl
        cp NOBJ*8
        jr nc,.no
        and 7
        jr nz,.no
        ld a,ixl
        rrca
        rrca                    ; 2i
        push bc
        ld b,a
        add a,a
        add a,b                 ; 6i, carry clear
        pop bc
        ret
.no:    scf
        ret

hideobj:
        push af
        push bc
        call objbase
        jr c,.out
        ld b,6
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
.out:   pop bc
        pop af
        ret

; HL = screen address (bottom line), DE -> W (graphic + 1), IX = object. Uses all but IX/IY.
draw:   call objbase
        ret c
        dec de                  ; DE = graphic
        push hl
        ld hl,gtab
.lk:    ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        jp z,.none
        ld a,c
        cp e
        jr nz,.nx
        ld a,b
        cp d
        jr z,.fnd
.nx:    inc hl
        inc hl
        inc hl
        inc hl
        jr .lk
.fnd:   ld a,(hl)               ; kind
        inc hl
        or a
        jr z,.ent
        ld c,(hl)
        inc hl
        ld b,(hl)               ; BC = subtable
        dec a
        jr nz,.car
        ld a,(LEVEL)
        and 7
        jr .idx
.car:   ld a,(PART)
        cp 3
        jp nc,.none
        add a,a
        add a,a
        ld l,a
        ld a,(LEVEL)
        rrca
        rrca
        and 3
        add a,l
.idx:   ld l,a
        add a,a
        add a,l
        ld l,a
        ld h,0
        add hl,bc
.ent:   ld a,(hl)
        cp 255
        jp z,.none
        ld c,a                  ; C = pattern
        inc hl
        ld b,(hl)               ; B = layout
        inc hl
        ld a,(hl)               ; A = x adjust
        pop hl                  ; HL = screen address
        push bc
        ld b,a
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        add a,b
        ld e,a
        ld a,0
        adc a,0
        ld d,a                  ; DE = x (0-263)
        ld a,l
        rrca
        rrca
        and 0x38
        ld b,a
        ld a,h
        and 7
        or b
        ld b,a
        ld a,h
        add a,a
        add a,a
        add a,a
        and 0xC0
        or b                    ; A = bottom line y
        pop bc                  ; C = pattern, B = layout
        bit 1,b
        jr nz,.r2
        add a,17                ; Y = y - 15 + 32
        jr .ry
.r2:    inc a                   ; Y = y - 31 + 32
.ry:    push bc                 ; [pattern/layout]
        push de                 ; [x]
        ld e,a                  ; E = Y
        ld a,(ix+3)
        ld c,a
        and 7
        rlca
        rlca
        rlca
        rlca
        ld b,a
        ld a,c
        and 0x40
        add a,a
        or b
        ld b,a                  ; B = palette offset (ink + 8 * bright) << 4
        call objbase
        ld d,a                  ; D = next sprite
        pop hl
        ex (sp),hl
        ld c,l                  ; C = pattern
        ld a,h                  ; A = layout
        ex (sp),hl              ; HL = x, stack [pattern/layout]
        push af
        push hl
        call place              ; row 0, column 0
        pop hl
        pop af
        push af
        push hl
        bit 0,a
        jr z,.n1
        inc c
        call add16
        call place              ; row 0, column 1
.n1:    pop hl
        pop af
        bit 1,a
        jr z,.done
        push af
        ld a,e
        add a,16
        ld e,a
        pop af
        inc c                   ; first pattern of row 1 (pattern + columns)
        push af
        push hl
        call place              ; row 1, column 0
        pop hl
        pop af
        bit 0,a
        jr z,.done
        inc c
        call add16
        call place              ; row 1, column 1
.done:  pop hl
        jr .hide
.none:  pop hl
        call objbase
        ld d,a
.hide:  call objbase
        add a,6
        ld b,a
.hd:    ld a,d
        cp b
        ret nc
        nextreg 0x34,a
        nextreg 0x38,0
        inc d
        jr .hd

add16:  ld a,l
        add a,16
        ld l,a
        ret nc
        inc h
        ret

; one 16x16 column at x_c = HL (0-295): sprite D (D += 1 per sprite set), Y = E, palette B,
; pattern C. x_c < 256: at x_c; x_c > 240: (also) at x_c - 256 (the ULA row wrap).
place:  ld a,h
        or a
        jr nz,.w
        ld a,d
        nextreg 0x34,a
        ld a,l
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        or b
        nextreg 0x37,a
        ld a,e
        nextreg 0x36,a
        call setpat
        ld a,l
        cp 241
        ret c
.w:     ld a,d
        nextreg 0x34,a
        ld a,l
        sub 224
        nextreg 0x35,a
        ld a,b
        nextreg 0x37,a
        ld a,e
        nextreg 0x36,a
setpat: ld a,c
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        inc d
        ret

        INCLUDE "jetpac_tables.asm"
rom_end:

; --- setup routine (stub bank, 0xD000): patterns from bank 11, palette, hide all, sprites on ---
        ORG 0xD000
setup:  nextreg 0x57,22             ; bank 11 lower page at 0xE000
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,0xE000
        ld d,NPAT256
.u:     ld bc,0x005B
        otir
        ld a,h
        or a
        jr nz,.u2               ; 8K page done (HL wrapped to 0): bank 11's second page
        nextreg 0x57,23
        ld h,0xE0
.u2:    dec d
        jr nz,.u
        nextreg 0x57,21
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment off for 0x41 writes below
        ld hl,speccy
        ld b,16
        ld c,1
.p:     ld a,c
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a              ; offset n index 1 = Spectrum colour n (8-15 bright)
        inc hl
        ld a,c
        add a,16
        ld c,a
        djnz .p
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
speccy: db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "jp_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "jp_setup.bin",0xD000,setup_end-0xD000
