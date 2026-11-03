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
; The rocket (object 6, 23856) draws up to 4 figures a frame on one object: base, middle, nose
; (26432 loop) and flames (26265). Its figures get a pair each (102-103 base, 104-105 middle,
; 106-107 nose, 108-109 flames; 36-41 stay for an ordinary figure) and touch only that pair, so every section stays shown (2026-11-03: one shared set
; showed only the last section drawn; the flames had no table entry).
; Patterns (4-bit, ink = 1; rocket parts: index 1 bottom 8 lines, index 2 top 8 lines, so a
; section shows the game's two row colours: palette offset 8 = magenta below, white above)
; and their lookup: asm/jetpac_tables.asm (generated).

        DEVICE ZXSPECTRUMNEXT

OBJ0    EQU 23808
NOBJ    EQU 17
LEVEL   EQU 24048
PART    EQU 23860           ; the rocket's part count: the carried graphic is part (23860), 3 = fuel
ROCKET  EQU 23856           ; object 6: draws up to 4 figures a frame (sections 26432, flames 26265)
RKSPR   EQU NOBJ*6          ; the rocket's figures: a pair each, sprites 102-109
NHIDE   EQU NOBJ*6+8

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

; ---- erase-only entries: hide the object's sprites (e_e1: graphic DE known -> only that figure's
; sprites on the rocket, so erasing the flames (26255/26261) leaves the rocket's sections shown) ----
e_e1:   call hidefig
        jp 29223
e_e2:   call hideobj
        jp 29220

; ---- screen clear: hide every sprite the hooks use ----
e_cls:  push af
        push bc
        xor a
        ld b,NHIDE
        call hiden
        pop bc
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

; Z if IX = the rocket object (uses A)
isrk:   ld a,ixl
neg_rk: cp low ROCKET           ; (the negative control's build changes this operand)
        ret nz
        ld a,ixh
        cp high ROCKET
        ret

; hide B sprites from sprite A (A += B, B = 0)
hiden:  nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz hiden
        ret

; hide all of the object's sprites (the rocket: also its figures' pairs)
hideobj:
        push af
        push bc
        call objbase
        jr c,.out
        ld b,6
        call hiden
        call isrk
        jr nz,.out
        ld a,RKSPR
        ld b,8
        call hiden
.out:   pop bc
        pop af
        ret

; erase of graphic DE: on the rocket, hide only that figure's pair (section / flames)
hidefig:
        push af
        push bc
        push hl
        call isrk
        jr nz,.all
        call find
        jr c,.all
        ld a,(hl)
        call role
        jr z,.all
        call rspr
        call hiden
        jr .out
.all:   call hideobj
.out:   pop hl
        pop bc
        pop af
        ret

; DE = graphic -> HL = its gtab kind byte, carry clear; carry set if not in gtab (uses A, BC)
find:   ld hl,gtab
.lk:    ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        scf
        ret z
        ld a,c
        cp e
        jr nz,.nx
        ld a,b
        cp d
        ret z
.nx:    inc hl
        inc hl
        inc hl
        inc hl
        jr .lk

; A = gtab kind -> A = rocket role (0 none, 1-3 section base / middle / nose, 4 flames), Z if 0
role:   rrca
        rrca
        and 7
        ret

; A = role 1-4 -> A = its first sprite (102 + 2 * (role - 1)), B = 2
rspr:   add a,a
        add a,RKSPR-2
        ld b,2
        ret

; A = section k (0-2) of the rocket IX -> A = palette offset << 4 of its two character rows, as
; the game paints them after drawing (26488-26562): rows 2k (bottom half, pattern index 1) and
; 2k+1 (top half, index 2); 15 = both white, 11 = both magenta, 8 = magenta below, white above.
rcol:   ld l,a
        ld a,(ix+4)
        add a,a
        cp 6
        jr c,.w                 ; rocket not complete: white
        ld a,(ix+5)
        or a
        jr z,.w                 ; no fuel: white
        cp 6
        jr c,.p
        ld a,(24012)
        and 16
        jr nz,.w                ; full: flashing 67 / 71 by bit 4 of the frame counter
.m:     ld a,0xB0
        ret
.w:     ld a,0xF0
        ret
.p:     ld h,a                  ; F = fuel rows (magenta from the bottom)
        ld a,l
        add a,a
        cp h
        jr nc,.w
        inc a
        cp h
        jr c,.m
        ld a,0x80
        ret

; HL = screen address (bottom line), DE -> W (graphic + 1), IX = object. Uses all but IX/IY.
draw:   call objbase
        ret c
        dec de                  ; DE = graphic
        push hl
        call find
        jp c,.none0
        ld a,(hl)               ; kind
        inc hl
        push af                 ; [kind, scr]
        and 3
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
.np:    cp 4                    ; parts 0-2 and 3 = fuel (neg_pt: the negative control's build: 3)
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
        pop hl                  ; H = kind
        ex (sp),hl              ; HL = screen address, [kind]
        push bc
        ld b,a
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        add a,b
        ld e,a
        ld d,0
        rl d                    ; DE = x (0-263)
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
.ry:    push bc                 ; [pattern/layout, kind]
        push de                 ; [x, pattern/layout, kind]
        ld e,a                  ; E = Y
        ld hl,5
        add hl,sp               ; HL -> kind (becomes the end of the sprite range)
        call isrk
        jr nz,.nrm
        ld a,(hl)
        call role
        jr z,.rk0
        push af
        call rspr
        ld d,a                  ; D = first sprite of the figure
        add a,b
        ld (hl),a               ; end = its pair
        pop af
        ld b,0xA0               ; flames: bright red (the game paints 66 over them, 26268)
        cp 4
        jr z,.pl
        dec a
        call rcol
        ld b,a
        jr .pl
.rk0:   ld a,RKSPR              ; the rocket object, an ordinary figure: no rocket figures
        ld b,8
        call hiden
.nrm:   call objbase
        ld d,a                  ; D = next sprite
        add a,6
        ld (hl),a               ; end = the object's 6
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
.pl:    pop hl
        ex (sp),hl
        ld c,l                  ; C = pattern
        ld a,h                  ; A = layout
        ex (sp),hl              ; HL = x, stack [pattern/layout, end]
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
        pop bc                  ; B = end of the figure's sprite range
.hd:    ld a,d
        cp b
        ret nc
        nextreg 0x34,a
        nextreg 0x38,0
        inc d
        jr .hd
.none:  pop af
.none0: pop hl
        jp hideobj

neg_pt  EQU draw.np

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
        ld a,b
        adc a,0                 ; palette | X bit 8 (B's low bits are 0)
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
        nextreg 0x43,0x20           ; sprite palette 0 (auto-increment on)
        ld hl,speccy
        ld c,1
.p:     ld a,c
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a              ; offset n index 1 = Spectrum colour n (8-15 bright)
        inc hl
        ld a,c
        inc a
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a              ; index 2 = the same, but offset 8: bright white
        inc hl
        ld a,c
        add a,16
        ld c,a
        cp 1
        jr nz,.p
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
; (index 1, index 2) per palette offset 0-15; offset 8 (bright black, never an object ink: the game
; avoids 64, 25877) is the rocket's half-fuelled section: bright magenta below, bright white above
speccy: db 0x00,0x00, 0x02,0x02, 0xA0,0xA0, 0xA2,0xA2, 0x14,0x14, 0x16,0x16, 0xB4,0xB4, 0xB6,0xB6
        db 0xE7,0xFF, 0x03,0x03, 0xE0,0xE0, 0xE7,0xE7, 0x1C,0x1C, 0x1F,0x1F, 0xFC,0xFC, 0xFF,0xFF
setup_end:

        SAVEBIN "jp_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "jp_setup.bin",0xD000,setup_end-0xD000
