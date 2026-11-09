;  Lode Runner (Software Projects, 1984) 128K release - rework v3: Dean Woodyatt's hooks (asm/loderunner_hooks.asm) with
; R left as the original at every hook (card patch.preserve-r; lib/hlib_r.asm), the figure paints run as a copy of 0x856E without
; its write (same instructions, same R, same flags), and the Enhanced colours' scenery layer.
; All of this code is in every build; the default build's sites never reach e_tile, e_xor or e_cls2. Enhanced (.nxc set)
; changes only: the JP at 0x8501, the JP at 0x984A, e_cls's site, the patterns (bank 11), the tiles (bank 7), the palette tables and FLAG_ENH.
; Hook sites and sprites: as asm/loderunner_hooks.asm (facts there and in games/lode_runner.md).
;
; Scenery layer (Enhanced): hardware tilemap in bank 7 (page 14, first 8K, not touched by the game: 7FFD takes 0x10, 0x11, 0x13, 0x14 only),
; map 40 x 32 of 1-byte entries at offset 0, definitions at offset 0x0500. The ULA keeps everything the game draws and reads. A cell's
; entry is TILES[A] of the tile printed there: 0 for everything left on the ULA (text, dig and refill frames), and transparent colour 0
; in a tile shows the ULA behind it. MMU slot 2 (0x4000-0x5FFF) is the window: not 6/7 or 0/1, because the IM 2 music handler writes
; 7FFD every frame, which resets MMU 0, 1, 6 and 7; the handler reads and writes nothing in 0x4000-0x5FFF (replay checks it).

        DEVICE ZXSPECTRUMNEXT

PLOT    EQU 0x9712
TILE    EQU 0x8501
RUNNER  EQU 0xA174
GUARD0  EQU 0xA183
NSLOT   EQU 8
NPAT    EQU 30
LIST    EQU 0x919D              ; level-start guard list (37277): 2 bytes per guard

HLIB_V_R EQU 0xA3F0             ; 3 bytes: R at entry, R to set, A at the exit (0xA33C-0xA3FF: zero, never read or written)
V_T     EQU 0xA3F4              ; the same for e_tile / e_xor, which can run inside e_trun / e_tgrd
V_SP    EQU 0xA3F8              ; the print's incoming speed
TILES   EQU 0xA900              ; 256 bytes (page aligned): tile -> tilemap entry, 0 = stays on the ULA
PAGE_TM EQU 14                  ; bank 7's first 8K
PAGE_S2 EQU 10                  ; bank 5's first 8K, slot 2's own page
MAPW    EQU 0x4000 + 4 * 40 + 4 ; column 0, row 0 of the paper through slot 2 (paper = tile column 4, row 4)

; R constants (O - E - N, hooklib.r_delta; replay and unit cases compare R at every hook)
D_PLOT  EQU (1 - 4 - 2) & 0x7F  ; CALL plot: O 1; E CALL + R_IN 3; N R_OUT 1 + JP 1
D_FADE  EQU (2 - 4 - 2) & 0x7F  ; LD B,4 / LD DE,0 to 0x8554: O 2; E JP + 3; N 2
D_CLS   EQU (1 - 4 - 2) & 0x7F  ; LD DE,16385 to 0x8544: O 1
D_TPRINT EQU 78                ; the print of tile 30: O - E - N, measured (hooklib.r_check)
D_EDIT  EQU (1 - 4 - 2) & 0x7F  ; LD HL,0x8D9D to 0x8C86: O 1
D_TILE  EQU (3 - 4 - 2 - 15) & 0x7F ; PUSH AF, BC, DE to 0x8504: O 3; E JP + HLIB_SPEED_IN's M1s + 3; N 2
D_TEND  EQU (3 - 4 - 2) & 0x7F  ; POP HL, DE, BC to 0x853F: O 3; E JP + 3; N 2
D_XOR   EQU (3 - 4 - 2 - 15) & 0x7F ; PUSH BC, DE, HL to 0x984D: O 3; E JP + HLIB_SPEED_IN's 15 + 3; N 2

        INCLUDE "lib/hlib_speed.asm"
        MACRO V_R_IN v
        push af
        ld a,r
        ld (v),a
        pop af
        ENDM
        MACRO V_R_OUT v
        ld (v + 2),a
        ld a,(v + 1)
        ld r,a
        ld a,(v + 2)
        ENDM

        ORG 0xA460
; ---- draw a figure (A = graphic, B = x, C = y, IX = record), then the plotter ----
e_draw: V_R_IN HLIB_V_R
        push bc
        push de
        push af
        call slot
        jr c,dr_out
dr_show:
        pop af
        push af
        call show
dr_out: ld a,D_PLOT
        call hlib_r_set
        pop af
        pop de
        pop bc
        V_R_OUT HLIB_V_R
        jp PLOT

e_drawr:
        V_R_IN HLIB_V_R
        push bc
        push de
        push af
        ld de,0                 ; runner: slot 0, kind 0
        jr dr_show

; ---- a guard dies: hide its sprite, then the plotter erases ----
e_hide: V_R_IN HLIB_V_R
        push de
        push af
        call slot
        jr c,.out
        ld a,d
        nextreg 0x34,a
        nextreg 0x38,0
.out:   ld a,D_PLOT
        call hlib_r_set
        pop af
        pop de
        V_R_OUT HLIB_V_R
        jp PLOT

; ---- level start: the figure as a sprite, a blank tile (32) printed instead of tile 30 ----
e_trun: V_R_IN HLIB_V_R
        push de
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
        ld a,D_TPRINT           ; the print's M1s depend on the tile only: tile 30 in the original
        call hlib_r_set
        pop af
        V_R_OUT HLIB_V_R
        ret

e_tgrd: V_R_IN HLIB_V_R
        push de
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
.orig:  ld a,D_PLOT             ; not the guard list: the original print (never seen)
        call hlib_r_set
        pop af
        pop de
        V_R_OUT HLIB_V_R
        jp TILE

; ---- fade / screen clear: hide every figure ----
e_fade: V_R_IN HLIB_V_R
        call hideall
        push af
        ld a,D_FADE
        call hlib_r_set
        pop af
        ld b,4
        ld de,0
        V_R_OUT HLIB_V_R
        jp 0x8554
e_cls:  V_R_IN HLIB_V_R
        call hideall
cls_out:
        push af
        push hl
        ld hl,e_trun            ; the level-start prints and paints back (the editor took them away)
        ld (0x8E60),hl
        ld hl,e_tgrd
        ld (0x8E75),hl
        ld hl,paint
        ld (0x8E65),hl
        ld (0x8E7A),hl
        pop hl
        ld a,D_CLS
        call hlib_r_set
        pop af
        ld de,16385
        V_R_OUT HLIB_V_R
        jp 0x8544

; ---- Enhanced: the clear also empties the map (the fade leaves the tiles up; they go with the ULA's clear) ----
e_cls2: V_R_IN HLIB_V_R
        call hideall
        push af
        push hl
        push bc
        nextreg 0x52,PAGE_TM
        ld hl,0x4000
        ld de,0x4001
        ld bc,1279
        ld (hl),0
        ldir
        nextreg 0x52,PAGE_S2
        nextreg 0x6B,0xA1       ; the layer back on after the editor
        pop bc
        pop hl
        pop af
        jr cls_out

; ---- the level editor (0x8C83, its legend, before it draws the level), every build: runner and guards as the original draws them, tiles on
; the ULA with their attributes, because on exit 0x8EC1 rebuilds the level's start positions from those attributes (the 1.0 build lost them).
; The level-start prints and paints are the original's until the next clear; the tilemap, if any, is off (hidden ladders are green there, the
; legend is on blue) ----
e_edit: V_R_IN HLIB_V_R
        nextreg 0x6B,0
        push af
        push hl
        ld hl,TILE
        ld (0x8E60),hl
        ld (0x8E75),hl
        ld hl,0x856E
        ld (0x8E65),hl
        ld (0x8E7A),hl
        pop hl
        ld a,D_EDIT
        call hlib_r_set
        pop af
        ld hl,0x8D9D
        V_R_OUT HLIB_V_R
        jp 0x8C86

; ---- Enhanced: a tile print (A = tile, B = column, C = row): the map's entry, then the print, all at 28 MHz, back at e_tend: the print then takes
; less time than the original's, where every player update with a score print used to be close to its frame ----
e_tile: HLIB_SPEED_IN V_SP
        V_R_IN V_T
        push af
        push hl
        push de
        ld l,a
        ld h,high TILES
        ld a,(hl)               ; the entry
        ld d,c                  ; D = row
        ld e,40
        mul d,e
        ex de,hl                ; HL = row * 40; DE = table pointer, unused
        ld e,a
        ld a,b
        add hl,a
        ld a,e
        ld de,MAPW
        add hl,de
        nextreg 0x52,PAGE_TM
        ld (hl),a
        nextreg 0x52,PAGE_S2
        ld a,(V_T)
        add a,D_TILE
        and 0x7F
        ld l,a
        ld a,(V_T)
        and 0x80
        or l
        ld (V_T + 1),a
        pop de
        pop hl
        pop af
        push af
        push bc
        push de
        V_R_OUT V_T
        jp TILE + 3
e_tend: V_R_IN V_T
        HLIB_SPEED_OUT V_SP
        push af
        ld a,(V_T)
        add a,D_TEND
        and 0x7F
        ld h,a
        ld a,(V_T)
        and 0x80
        or h
        ld (V_T + 1),a
        pop af
        pop hl
        pop de
        pop bc
        V_R_OUT V_T
        jp 0x853F

; ---- Enhanced: the cell XOR's inner entry 0x984A (A = tile, B = column, C = row; 0x983E comes here too, after halving its pixels):
; the entry XOR the tile's, then the routine, at 28 MHz as the print, back at e_xend ----
e_xor:  HLIB_SPEED_IN V_SP
        V_R_IN V_T
        push af
        push hl
        push de
        ld l,a
        ld h,high TILES
        ld a,(hl)
        or a
        jr z,.leave
        ld d,c
        ld e,40
        mul d,e
        ex de,hl                ; HL = row * 40
        ld e,a                  ; the tile's entry
        ld a,b
        add hl,a
        ld a,e
        ld de,MAPW
        add hl,de
        nextreg 0x52,PAGE_TM
        xor (hl)
        ld (hl),a
        nextreg 0x52,PAGE_S2
.leave: ld a,(V_T)
        add a,D_XOR
        and 0x7F
        ld l,a
        ld a,(V_T)
        and 0x80
        or l
        ld (V_T + 1),a
        pop de
        pop hl
        pop af
        push bc
        push de
        push hl
        V_R_OUT V_T
        jp 0x984D
e_xend: V_R_IN V_T
        HLIB_SPEED_OUT V_SP
        push af
        ld a,(V_T)
        add a,D_TEND
        and 0x7F
        ld h,a
        ld a,(V_T)
        and 0x80
        or h
        ld (V_T + 1),a
        pop af
        pop hl
        pop de
        pop bc
        V_R_OUT V_T
        jp 0x9875

; ---- a figure's colour paint: 0x856E without its write (same instructions, so R, flags and time as the original) ----
paint:  push bc
        push hl
        ld h,88
        ld l,b
        sla c
        sla c
        sla c
        sla c
        jr nc,.a
        inc h
        inc h
.a:     sla c
        jr nc,.b
        inc h
.b:     ld b,0
        add hl,bc
        cp 255
        jr nz,.w
        ld a,(hl)
        pop hl
        pop bc
        ret
.w:     nop                     ; LD (HL),A in 0x856E
        pop hl
        pop bc
        ret

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

        INCLUDE "lib/hlib_r.asm"
hooks_end:

        ORG TILES
tiles_tab:
        DS 256

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

; --- Enhanced set-up, after setup; does nothing unless the set switches it on ---
FLAG_ENH: db 0                      ; Enhanced colours (the set)
FLAG_BD:  db 0                      ; Backdrop (the toggle; only with Enhanced)
SPAL:   ds 2 * 16                   ; sprite palette: 16 x RRRGGGBB, B (9-bit, register 0x44)
TPAL:   ds 2 * 16                   ; tilemap palette, the same
setup2: ld a,(FLAG_ENH)
        or a
        ret z
        nextreg 0x43,0x20           ; sprites' palette 0, auto-increment
        ld hl,SPAL
        call pal16
        nextreg 0x43,0x30           ; tilemap palette 0
        ld hl,TPAL
        call pal16
        nextreg 0x43,0x00
        nextreg 0x4C,0              ; tile colour 0 transparent
        nextreg 0x6C,0              ; default attribute: palette offset 0
        nextreg 0x6E,0x80           ; map at bank 7 + 0
        nextreg 0x6F,0x85           ; tiles at bank 7 + 0x0500
        nextreg 0x2F,0
        nextreg 0x30,0
        nextreg 0x31,0
        nextreg 0x1C,8              ; tilemap clip index reset
        nextreg 0x1B,0
        nextreg 0x1B,159
        nextreg 0x1B,0
        nextreg 0x1B,255
        nextreg 0x6B,0xA1           ; on, 40 x 32, 1-byte entries, tiles over the ULA
        ld a,(FLAG_BD)
        or a
        ret z
        nextreg 0x12,13             ; Layer 2: banks 13-15, 256 x 192
        nextreg 0x70,0
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x57,22             ; palette at bank 11 + 0x1000
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,0xF000
        ld d,0
.l2:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        dec d
        jr nz,.l2
        nextreg 0x57,21
        nextreg 0x43,0x00           ; the ULA's black shows Layer 2 behind it: ink and paper, bright or not
        nextreg 0x40,0
        nextreg 0x41,0xE3
        nextreg 0x40,8
        nextreg 0x41,0xE3
        nextreg 0x40,16
        nextreg 0x41,0xE3
        nextreg 0x40,24
        nextreg 0x41,0xE3
        nextreg 0x14,0xE3
        nextreg 0x4A,0              ; fallback black
        nextreg 0x15,0x09           ; sprites on; sprites, ULA + tiles, Layer 2
        nextreg 0x69,0x80           ; Layer 2 on
        ret
pal16:  nextreg 0x40,0
        ld b,2 * 16
.n:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .n
        ret
setup_end:

        SAVEBIN "lr3_hooks.bin",0xA460,hooks_end-0xA460
        SAVEBIN "lr3_setup.bin",0xD000,setup_end-0xD000
