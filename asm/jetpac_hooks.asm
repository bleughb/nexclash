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
;   29157  DD 56 03   LD D,(IX+3) (the colour paint 29135)                      -> CALL e_at
; Screen-write patches (no hook): 30532 77 -> 00 (erase AND), 30561 77 -> 00 (draw OR),
;   29171 72 -> 00 (object colour over its cells).
; Sprites: object i = (IX - 23808) / 8 (0-16) owns sprites 6i .. 6i+5: 2 rows x (2 columns + a copy
; of the column that crosses x = 256 at x - 256, as the ULA wraps the row).
; Patterns (4-bit, ink = 1) and their lookup: asm/jetpac_tables.asm (generated).

        DEVICE ZXSPECTRUMNEXT

OBJ0    EQU 23808
NOBJ    EQU 17
LEVEL   EQU 24048
FLAME1  EQU 32652               ; rocket flame graphics: drawn / erased on the rocket base object
FLAME2  EQU 32687               ; (26217-26308) -> their own sprites, never the rocket's
FLAMES  EQU NOBJ*6              ; sprites 102-107
PIECES  EQU FLAMES+6            ; assembled rocket pieces 2 and 3: sprites 108-113, 114-119
NSPR    EQU PIECES+12           ; sprites used: 0-119
ROCKET  EQU 23864               ; the rocket base object: draws every stacked piece (26419-26470)
RLOOP   EQU 26449               ; return of its CALL 29278 per piece (C on the stack = 4 * piece)
RPAINT  EQU 26549               ; return of its CALL 29135 per 8-line band (26545-26560)
FPAINT  EQU 26275               ; return of the flame's CALL 29135 (26272)
HOOKRAM EQU 0x8000              ; attr2 shadow per sprite (0x8000-0x807F; tables at 0x8100)
GSP     EQU 0x8080              ; the game's SP at e_nw / e_at entry
HSTACK  EQU 0x8100              ; the hooks' own stack 0x8082-0x80FF (the game stack has ~30 bytes
                                ; above its code at 23728 at the deepest paint: no room for the hooks) (X8 + palette): the game never touches
                                ; 0x7D37-0xFFFF (scan)
PART    EQU 23860

        ORG 0x386E
; ---- new frame of an object ----
e_nw:   ld (GSP),sp
        ld sp,HSTACK
        push af
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
        ld sp,(GSP)
        ld a,(de)
        ld b,a
        ld (24004),a
        jp 29268

; ---- the colour paint 29135 (LD D,(IX+3) at 29157): the object's sprites take the colour the game
; paints - the rocket per 8-line band (piece = band / 2; a white top over a magenta bottom = bank 8)
e_at:   ld (GSP),sp
        ld sp,HSTACK
        push af
        push bc
        push de
        push hl
        call paint
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(GSP)
        ld d,(ix+3)
        ret

; ---- erase-only entries: hide the object's sprites ----
e_e1:   push af
        call isflame            ; DE = the graphic being erased
        jr z,.fl
        pop af
        call hideobj
        jp 29223
.fl:    push bc
        ld a,FLAMES
        call hide6
        pop bc
        pop af
        jp 29223
e_e2:   call hideobj
        jp 29220

; ---- screen clear: hide every sprite ----
e_cls:  push af
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NSPR
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
        call hide6
        ld a,ixl
        cp low ROCKET
        jr nz,.out
        ld a,PIECES             ; the rocket: its stacked pieces too
        call hide6
        call hide6
.out:   pop bc
        pop af
        ret

; hide sprites A .. A+5 (uses A, B)
hide6:  ld b,6
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz .h
        ret

; carry clear + A = piece (0-2) when the rocket loop draws (IX = ROCKET, caller RLOOP); carry set
; otherwise. Game stack at e_nw (GSP): +0 29287, +2 RLOOP, +4 the loop's BC (C = 4 * piece).
rpiece: ld a,ixl
        cp low ROCKET
        jr nz,.no2
        push hl
        ld hl,(GSP)
        inc hl
        inc hl
        ld a,(hl)
        cp low RLOOP
        jr nz,.no
        inc hl
        ld a,(hl)
        cp high RLOOP
        jr nz,.no
        inc hl
        ld a,(hl)
        rrca
        rrca
        and 3
        pop hl
        or a
        ret
.no:    pop hl
.no2:   scf
        ret

; paint: IX = object, (IX+3) = the colour being painted. Game stack at e_at (GSP): +0 29160,
; +2 29135's caller.
paint:  call objbase
        ret c
        ld c,a                  ; C = first sprite of the group
        ld a,(ix+3)
        ld e,a
        and 7
        ld b,a
        ld a,e
        and 0x40
        rrca
        rrca
        rrca
        or b
        ld b,a                  ; B = bank (ink + 8 * bright)
        ld hl,(GSP)
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = caller of 29135
        ld a,e
        cp low FPAINT
        jr nz,.r
        ld a,d
        cp high FPAINT
        jr nz,.r
        ld c,FLAMES
        jr setgrp
.r:     ld a,e
        cp low RPAINT
        jr nz,setgrp
        ld a,d
        cp high RPAINT
        jr nz,setgrp
        ld a,(24016)            ; band line (H of (24015))
        ld e,a
        ld a,(ix+2)
        sub e
        rrca
        rrca
        rrca
        and 31
        ld e,a                  ; E = band (0 = bottom)
        srl a                   ; piece
        cp 3
        ret nc
        or a
        jr z,.p0
        dec a
        ld d,a
        add a,a
        add a,d
        add a,a
        add a,PIECES
        ld c,a
.p0:    bit 0,e
        jr z,setgrp             ; bottom half (painted first): the whole piece
        ld h,high HOOKRAM
        ld l,c
        ld a,(hl)
        rrca
        rrca
        rrca
        rrca
        and 15                  ; the bottom half's bank
        cp b
        ret z
        cp 11
        jr nz,setgrp
        ld a,b
        cp 15
        jr nz,setgrp
        ld b,8                  ; white top over a magenta bottom
; bank B for sprites C .. C+5 (attr2 from the shadow: X8 kept)
setgrp: ld a,b
        rlca
        rlca
        rlca
        rlca
        ld b,a
        ld e,6
.s:     ld h,high HOOKRAM
        ld l,c
        ld a,(hl)
        and 0x0F
        or b
        ld (hl),a
        ld d,a
        ld a,c
        nextreg 0x34,a
        ld a,d
        nextreg 0x37,a
        inc c
        dec e
        jr nz,.s
        ret

; attr2 A of sprite D -> shadow (keeps A)
shadow: push hl
        ld h,high HOOKRAM
        ld l,d
        ld (hl),a
        pop hl
        ret

; Z if DE = a flame graphic (uses A)
isflame:
        ld a,e
        cp low FLAME1
        jr nz,.b
        ld a,d
        cp high FLAME1
        ret
.b:     ld a,e
        cp low FLAME2
        ret nz
        ld a,d
        cp high FLAME2
        ret

; HL = screen address (bottom line), DE -> W (graphic + 1), IX = object. Uses all but IX/IY.
draw:   call objbase
        ret c
        dec de                  ; DE = graphic
        ld c,a                  ; C = the object's sprites
        call isflame
        jr nz,.nf
        ld c,FLAMES             ; the flame's own sprites
        jr .bs
.nf:    call rpiece
        jr c,.bs
        or a
        jr z,.bs                ; piece 1 (base): the object's sprites
        dec a
        ld b,a
        add a,a
        add a,b
        add a,a
        add a,PIECES
        ld c,a
.bs:    ld a,c
        push af                 ; [base]
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
        push hl
        ld hl,7
        add hl,sp
        ld d,(hl)               ; D = next sprite = base (A of [base], under [HL][x][pattern/layout])
        pop hl
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
        pop af                  ; A = base
        jr .hide
.none:  pop hl
        pop af
        ld d,a
.hide:  add a,6
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
        call shadow
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
        call shadow
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

rom_end:

; --- lookup tables in RAM 0x8100 (zero in the snapshot, never touched by the game; read-only) ---
        ORG 0x8100
tab:
        INCLUDE "jetpac_tables.asm"
tab_end:

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
        ld a,c
        inc a
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a              ; index 2 (rocket pieces' bottom half) = the same colour
        inc hl
        ld a,c
        add a,16
        ld c,a
        djnz .p
        nextreg 0x40,0x81
        nextreg 0x41,0xFF           ; bank 8: white top (1) ...
        nextreg 0x40,0x82
        nextreg 0x41,0xE7           ; ... over a magenta bottom (2): a half-fuelled piece
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
        SAVEBIN "jp_tab.bin",0x8100,tab_end-0x8100
