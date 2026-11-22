; Bomb Jack (Elite, 1986, 48K) - hardware sprites for the moving figures and the bombs.
; All hooks live in alt ROM image 1 at 0x386E and are stateless. Interrupts are off at every site (the
; game draws inside its IM2 handler, DI at 0xC38C; the verifier counts the sites reached with IFF set).
;
; Rendering model of the game: masked plot from a clean copy of the screen at 0x6000: screen = (copy AND
; mask) OR gfx; erase = copy to screen. Figures are never in the copy; bombs are (0xE582 writes both).
;
; Sites (original bytes checked by bomb_jack.py):
;   0xD94B CD B5 D9  CALL 0xD9B5 (move one figure)      -> CALL e_mov
;   0xD6E3 CD 82 E5  CALL 0xE582 (place a bomb)         -> CALL e_bmb
;   0xC860 CD 82 E5  CALL 0xE582 (lit bomb, top 6 rows) -> CALL e_bmb
;   0xC68B CD 46 E6  CALL 0xE646 (bomb collected)       -> CALL e_bgo
;   0xEC21 21 00 40  LD HL,16384 (clear the play area)  -> JP e_cls
;   0xC362 11 00 40  LD DE,16384 (level shown)          -> JP e_go
;   0xC457 21 1D F1  LD HL,61725 (GAME OVER message)    -> JP e_gov
;   0xD8A8, 0xD8CF, 0xD8F5  CD 89 D7  CALL 0xD789 (platform tile) -> CALL e_tl
;
; e_mov runs the game's own move routine, same path, with the graphics pointer aimed at a blank figure
; (mask FF, gfx 00): the ULA gets the copy's bytes and the figure goes to its sprites. Same work as the
; original, so game timing only moves by the hook's own time.
; Bombs and platform tiles stay on the ULA and in the copy (the game needs them there); a solid sprite covers
; each one, so its fill no longer changes at cell edges. Score labels (0xC6C4, 0xC742) stay on the ULA.
; Slots: tiles 0-63, bombs 64-87, figures 88+2i and 89+2i (object i; a figure is up to 24 pixels wide).
; Higher on top, which is the game's own order: tiles, then bombs, then figures in object order.
; Colours: one sprite palette, indices 1-15 (docs/COLOURS.md: the sheet's swatches); patterns from bomb_jack.py, a
; figure kind's defaults plus the colour map. 0 = transparent; the 4th byte of a block entry is the palette offset, 0.
; One hook byte, TILEC 0x6E40 in the clean copy: the next tile slot, only live from the clear to 0xD98F, which
; rewrites the copy before anything reads it.

        DEVICE ZXSPECTRUMNEXT

MOVE    EQU 0xD9B5
PLOT    EQU 0xE582
REST    EQU 0xE646
CLSCON  EQU 0xEC24
ST      EQU 62121
XNEW    EQU 62126
YNEW    EQU 62128
GFX     EQU 62130
CNT     EQU 62132
SAVESP  EQU 64985
SAVEP   EQU 64989
BOMB0   EQU 62227
NSPR    EQU 110
TILEC   EQU 0x6E40
TILEPAL EQU 0
TILE    EQU 0xD789
SLOT_B  EQU 64
NBLOCKS EQU 98

        ORG 0x386E
; ---- one figure: descriptor already copied to ST.. ----
e_mov:  ld a,(ST)
        or a
        jp z,MOVE               ; state 0: the routine returns at once
        push hl
        ld hl,(GFX)
        ex (sp),hl              ; real pointer on the stack, HL as it came
        push hl
        push de
        push bc
        nextreg 0x07,3
neg_mv: call mv_spr
        nextreg 0x07,0
        pop bc
        pop de
        pop hl
        call MOVE
        ex (sp),hl
neg_gf: ld (GFX),hl             ; back to the real pointer
        pop hl
neg_sp: ld (SAVESP),sp          ; the value the original stored
        ret

mv_spr: ld a,(CNT)              ; 11..1
        add a,a
        ld b,a
        ld a,NSPR
        sub b
        ld b,a                  ; left slot
        ld a,(ST)
        cp 3
        jr nc,hide2             ; state 3+: erase only
        call blockof            ; DE = entry, HL = variant offset, carry: unknown graphics
        jr c,hide2              ; the original's plot stays on the ULA
        push hl
        call spr1
        ld a,b
        inc a
        nextreg 0x34,a
        ld a,(de)               ; right part
        cp 0xFF
        jr z,.none
        ld h,a
        ld a,l
        add a,16
        ld l,a
        call xy
        jr .blank
.none:  nextreg 0x38,0
.blank: pop de
        ld hl,blank
        or a
        sbc hl,de
neg_bl: ld (GFX),hl
        ret

hide2:  ld a,b
        nextreg 0x34,a
        nextreg 0x38,0
        inc a
        nextreg 0x34,a
        nextreg 0x38,0
        ret

; ---- bomb plot: all of it runs as in the original; one sprite on top ----
e_bmb:  push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        call bslot
        jr c,bmb_o
neg_bm: call blockof
        jr c,bmb_o
        call spr1
bmb_o:  nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        jp PLOT

; ---- bomb collected ----
e_bgo:  push af
        push bc
        push de
        push hl
        call bslot
        jr c,bgo_o
        ld a,b
        nextreg 0x34,a
neg_bg: nextreg 0x38,0
bgo_o:  pop hl
        pop de
        pop bc
        pop af
        jp REST

; ---- play area cleared (level start, title, high scores): every sprite off, sprite layer off: the level
; start prints PLAYER n START on the ULA over bombs and the sprites would cover it ----
e_cls:
neg_ca: push af
neg_of: nextreg 0x15,0
        xor a
        ld (TILEC),a
        xor a
cls_h:  nextreg 0x34,a
neg_cl: nextreg 0x38,0
        inc a
        cp NSPR
        jr nz,cls_h
neg_cb: pop af
        ld hl,16384
        jp CLSCON

; ---- the level is shown (the copy goes to the screen, message gone): sprite layer on ----
e_go:
neg_go: nextreg 0x15,1
        ld de,16384
        jp 0xC365

; ---- GAME OVER is printed in the play area: sprite layer off while it is up (PLAYBOOK default 5) ----
e_gov:
neg_gv: nextreg 0x15,0
        ld hl,61725
        jp 0xC45A

; ---- platform tile A: 8x6 opaque at column (62163)/8, line (62165); plotted before the copy is taken ----
e_tl:   push af
        push bc
        push de
        push hl
        nextreg 0x07,3
        ld e,a
        ld a,(TILEC)
        cp 64
        jr nc,tl_o              ; no slot left: this tile just stays on the ULA
        ld b,a
        ld a,e
        cp 15
        jr nc,tl_o
        ld hl,tiles
        add a,l
        ld l,a
        jr nc,.nc
        inc h
.nc:    ld h,(hl)               ; pattern
        ld a,b
        nextreg 0x34,a
        ld a,(62163)
        and 0xF8
        ld l,a
        ld c,TILEPAL<<4
        ld a,(62165)
neg_tl: call xyy
        ld a,b
        inc a
        ld (TILEC),a
tl_o:   nextreg 0x07,0
        pop hl
        pop de
        pop bc
        pop af
        jp TILE

; B = bomb index from the save pointer; carry if out of range
bslot:  ld hl,(SAVEP)
        ld de,-BOMB0
        add hl,de
        ld de,-48
        ld b,0xFF
.l:     inc b
        add hl,de
        jr c,.l
        ld a,b
        cp 24
        ccf
        ret c
        add a,SLOT_B
        ld b,a
        ret

; left sprite of slot B from the entry at DE (left pattern, column, right pattern, palette offset).
; -> DE at the entry's right pattern, L = sprite X, C = palette offset in the high nibble
spr1:   ld hl,3
        add hl,de
        ld a,(hl)
neg_pa: swapnib
        ld c,a
        ld a,b
        nextreg 0x34,a
        ld a,(de)
        inc de
        ld h,a                  ; pattern
        ld a,(de)
        inc de
        ld l,a                  ; column offset of the pattern in the 24-pixel figure
        ld a,(XNEW)
        and 0xF8
        add a,l
        ld l,a
; H = pattern, L = X, C = palette offset: slot already selected
xy:     ld a,(YNEW)
        and 0xFE
xyy:    
neg_y:  add a,32
        nextreg 0x36,a
        ld a,l
        add a,32
        nextreg 0x35,a
        ld a,c
        adc a,0
        nextreg 0x37,a
        ld a,h
        srl a
        or 0xC0
        nextreg 0x38,a
        ld a,h
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ret

; 0x39FF-0x3A00 stay FF: the game runs IM 2 with I = 0x39, so the vector is read here and must stay 0xFFFF.
        DS 0x3A01-$,0xFF
; 16 rows x 3 pairs (mask, gfx) of nothing: the plot reads it through the stack
blank:  DUP 48
        DB 0xFF,0x00
        EDUP
; left pattern, column offset, right pattern (FF none), palette offset per block; filled by bomb_jack.py from the snapshot
blocks: DS 4*NBLOCKS,0xFF
; sprite pattern of each platform tile
tiles:  DS 15,0xFF

; (GFX) + 48*(x AND 6) -> DE = blocks entry, HL = the offset; carry if not a known block. B kept.
blockof:
        ld a,(XNEW)
        and 6
        ld e,a
        ld d,48
        mul d,e
        ld hl,(GFX)
        add hl,de
        ld a,h                  ; 0xD917 swaps blocks 0x887A and 0x995A in RAM; (63355) says which way
        cp 0x88
        jr nz,.ns
        ld a,l
        cp 0x7A
        jr nz,.ns
        ld a,(63355)
        or a
        jr z,.ns
        ld hl,0x995A            ; the patterns stay as in the snapshot
.ns:    push de                 ; offset
        push bc
        ld de,-0x5B00
        ld bc,0x0C00            ; B = end index, C = first index
        ld a,h
        cp 0x60
        jr c,.go
        ld de,-0x7AFA
        ld bc,0x440C
        cp 0x90
        jr c,.go
        ld de,-0x92FA
        ld bc,0x6244
.go:    add hl,de
        jr nc,.bad              ; below the base
        ld de,-96
.d:     add hl,de
        jr nc,.end
        inc c
        jr .d
.end:   ld a,l
        cp low(-96)
        jr nz,.bad              ; not on a block boundary
        ld a,h
        cp high(-96)
        jr nz,.bad
        ld a,c
        cp b
        jr nc,.bad
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,blocks
        add hl,de
        ex de,hl
        ld a,(de)
        cp 0xFF
        jr z,.bad               ; a score label: not a figure
        pop bc
        pop hl                  ; offset
        or a
        ret
.bad:   pop bc
        pop hl
        scf
        ret

rom_end:

; --- setup (stub bank, 0xD000): patterns from bank 11, palette, sprites off, sprites on ---
        ORG 0xD000
setup:  ld bc,0x303B
        xor a
        out (c),a
        ld a,22
.pg:    nextreg 0x57,a
        ld hl,0xE000
        ld d,32                 ; 32 x 256 = one 8K page
.u:     ld bc,0x005B
        otir
        dec d
        jr nz,.u
        inc a
        cp 24
        jr nz,.pg
        nextreg 0x57,21
        nextreg 0x43,0x20       ; sprite palette 0, auto-increment
        nextreg 0x40,1
        ld hl,colours
        ld b,15
.pal:   ld a,(hl)
        inc hl
        nextreg 0x41,a          ; indexes 1-15, auto-increment
        djnz .pal
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
; palette indices 1-15 (bomb_jack.py PALETTE)
colours:
        DB 0x00,0xFF,0x03,0xE0,0xFC     ; black, white, blue, red, yellow
        DB 0x1C,0x14,0xC3,0x62,0xB6     ; green, dark green, magenta, purple, grey
        DB 0xF8,0xF0,0xEC,0xE8,0x60     ; yellow-orange, orange, orange, dark orange, dark red
setup_end:

        SAVEBIN "bj_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "bj_setup.bin",0xD000,setup_end-0xD000
