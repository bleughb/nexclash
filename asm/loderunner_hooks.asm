; Lode Runner (Software Projects, 1984; 48K) - hardware sprites for the runner and the guards.
; Hooks live in game RAM at 0xA460 (0xA33C-0xA9FF: zero, never read or written by the game -
; RZX + free runs to game over and through the menus/editor; no code points into it). Not the alt
; ROM: the fade 0x854F ANDs the screen with every byte 0x0000-0x6BFF (alt ROM and printer buffer
; included), so code there would change the fade. The start-up tail is at 0xA400-0xA44E.
; Interrupts are on at every site (IM 2, handler EI / RETI: no registers, 2 stack bytes); the hooks
; never touch IX/IY/I/IFF or the alternate registers. Deepest stack: site SP 0xAB27 - 14 bytes of
; hook - 2 (interrupt) = 0xAB17, above the IM 2 table (0xAA00-0xAB00).
;
; Patch sites (original bytes checked by nexclash/loderunner.py):
;   0x9A5C  CD 12 97  CALL 0x9712 (move: draw new; IX = record)            -> CALL e_draw
;   0x970C  CD 12 97  CALL 0x9712 (guard respawn: draw; IX = record)       -> CALL e_draw
;   0x9E1B  CD 12 97  CALL 0x9712 (runner: draw; runner record fields)     -> CALL e_drawr
;   0x96B6  CD 12 97  CALL 0x9712 (guard dies: erase only)                 -> CALL e_hide
;   0x8E5F  CD 01 85  CALL 0x8501 (level start: runner printed as tile 30) -> CALL e_trun
;   0x8E74  CD 01 85  CALL 0x8501 (level start: guard k printed, HL = list + 2(k+1)) -> CALL e_tgrd
;   0x854F  06 04 11  LD B,4 / LD DE,.. (fade entry)                      -> JP e_fade
;   0x8541  11 01 40  LD DE,16385 (screen clear entry)                     -> JP e_cls
; Patches without a hook: 0x975B / 0x9761 77 -> 00 (the plotter's two screen writes; it keeps
;   running, so all game state stays the original's); the figure colour paints CALL 0x856E at
;   0x9EDB, 0x978C, 0x8E64, 0x8E79, 0x966E -> FE FF 00 (CP 255 / NOP: the flags 0x856E leaves).
; The erases at 0x9A47 / 0x9E03 stay calls of the plotter: each is followed, straight-line, by its
; draw (0x9A5C / 0x9E1B) for the same figure, so the sprite simply moves (no hide/show flicker).
;
; Sprites: slot 0 runner (record 0xA174), slots 1-7 guards (records 0xA183 + 17 k); 4-bit patterns
; 0-14 = runner graphics 16-30, 15-29 = guard graphics 16-30 (colours per pixel, palette offset 0,
; index n = Spectrum colour n, 8 black, 9-15 bright); x = B + 32, y = C + 32.

        DEVICE ZXSPECTRUMNEXT

PLOT    EQU 0x9712
TILE    EQU 0x8501
RUNNER  EQU 0xA174
GUARD0  EQU 0xA183
NSLOT   EQU 8
NPAT    EQU 30
LIST    EQU 0x919D              ; level-start guard list (37277): 2 bytes per guard

        ORG 0xA460
; ---- draw a figure (A = graphic, B = x, C = y, IX = record), then the plotter ----
e_draw: push bc
        push de
        push af
        call slot
        jr c,dr_out
dr_show:
        pop af
        push af
        call show
dr_out: pop af
        pop de
        pop bc
        jp PLOT

e_drawr:
        push bc
        push de
        push af
        ld de,0                 ; runner: slot 0, kind 0
        jr dr_show

; ---- a guard dies: hide its sprite, then the plotter erases ----
e_hide: push de
        push af
        call slot
        jr c,.out
        ld a,d
        nextreg 0x34,a
        nextreg 0x38,0
.out:   pop af
        pop de
        jp PLOT

; ---- level start: the figure as a sprite, a blank tile (32) printed instead of tile 30 ----
e_trun: push de
        ld de,0
tshow:  push bc
        push af
        sla b
        sla b
        sla b                   ; x = column * 8
        sla c
        sla c
        sla c                   ; y = row * 8
        call show
        pop af
        pop bc
        pop de
        push af
        ld a,32
        call TILE
        pop af
        ret

e_tgrd: push de
        push af
        ld a,h
        cp high LIST
        jr nz,.orig
        ld a,l
        sub low LIST
        jr c,.orig
        jr z,.orig
        cp 2*NSLOT
        jr nc,.orig
        rrca                    ; even: slot k + 1
        jr c,.orig
        ld d,a
        ld e,1
        pop af
        jr tshow
.orig:  pop af                  ; not the guard list: the original print (never seen)
        pop de
        jp TILE

; ---- fade / screen clear: hide every figure ----
e_fade: call hideall
        ld b,4
        ld de,0
        jp 0x8554
e_cls:  call hideall
        ld de,16385
        jp 0x8544

hideall:
        push af
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp NSLOT
        jr nz,.h
        pop af
        ret

; D = slot, E = kind (0 runner, 1 guard) of the record IX; carry set if IX is no figure record.
; Uses A, F (HL, BC kept).
slot:   push hl
        push bc
        push ix
        pop hl
        ld bc,RUNNER
        or a
        sbc hl,bc
        jr nz,.g
        ld de,0
        jr .ok
.g:     jr c,.no
        ld bc,GUARD0-RUNNER
        or a
        sbc hl,bc               ; HL = IX - GUARD0
        jr c,.no
        ld a,h
        or a
        jr nz,.no
        ld a,l
        ld d,1
.dv:    or a
        jr z,.gd
        sub 17
        jr c,.no
        inc d
        ld b,a
        ld a,d
        cp NSLOT
        jr nc,.no
        ld a,b
        jr .dv
.gd:    ld e,1
.ok:    pop bc
        pop hl
        or a
        ret
.no:    pop bc
        pop hl
        scf
        ret

; A = graphic, B = x, C = y, D = slot, E = kind. Uses A, F, E.
show:   sub 16
        cp 15
        jr nc,.hide             ; not a figure frame (16-30): no sprite (the game never plots one)
        bit 0,e
        jr z,.r
        add a,15
.r:     ld e,a                  ; E = pattern 0-29
        ld a,d
        nextreg 0x34,a
        ld a,b
        add a,32
        nextreg 0x35,a
        ld a,0
        adc a,0
        nextreg 0x37,a          ; X8; palette offset 0, no mirror / rotate
        ld a,c
        add a,32
        nextreg 0x36,a
        ld a,e
        and 1
        rrca
        rrca
        or 0x80                 ; 4-bit pattern, N6 = pattern bit 0
        nextreg 0x39,a
        ld a,e
        srl a
        or 0xC0                 ; visible, attribute 4 used, pattern / 2
        nextreg 0x38,a
        ret
.hide:  ld a,d
        nextreg 0x34,a
        nextreg 0x38,0
        ret
hooks_end:

; --- setup routine (stub bank, 0xD000): patterns from bank 11, palette, hide all, sprites on ---
        ORG 0xD000
setup:  nextreg 0x57,22             ; bank 11 lower page at 0xE000
        ld bc,0x303B
        xor a
        out (c),a                   ; pattern slot 0
        ld hl,0xE000
        ld d,NPAT/2                 ; 2 x 4-bit patterns (256 bytes) per OTIR
.u:     ld bc,0x005B
        otir
        dec d
        jr nz,.u
        nextreg 0x57,21
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,1
        ld hl,speccy+1
        ld b,15
.p:     ld a,(hl)
        nextreg 0x41,a              ; index n = Spectrum colour n (8 black, 9-15 bright)
        inc hl
        djnz .p
        nextreg 0x4B,0              ; 4-bit index 0 transparent
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01           ; sprites on, S L U, not over the border
        ret
speccy: db 0x00,0x02,0xA0,0xA2,0x14,0x16,0xB4,0xB6,0x00,0x03,0xE0,0xE7,0x1C,0x1F,0xFC,0xFF
setup_end:

        SAVEBIN "lr_hooks.bin",0xA460,hooks_end-0xA460
        SAVEBIN "lr_setup.bin",0xD000,setup_end-0xD000
