; Into the Eagle's Nest (Pandora, 128K): the Enhanced colours on Layer 2 and sprites.
;
; The game draws whole 8x8 tiles, each with its attribute. The play area is mirrored
; into a single Layer 2 picture, per tile, in the set's own 256 colours. The original
; plot still runs whole and the ULA under Layer 2 stays exactly the original's.
;
; The view scrolls by copying the screen one cell, twelve times a step. Layer 2 does
; not copy: it moves by its hardware offsets (NR 0x16, 0x17), wrapped by V_OX, V_OY,
; clipped to the play area, and paints the new edge. The panel beside it cannot scroll,
; so it is sprites: a fixed picture of 4x12 sprites and one sprite per digit.
;
; The game's update runs at 28 MHz and still waits for its 5 interrupts, so a steady update has
; the original's pace and a busy room lags less. The scroll's copy of the screen takes the original's
; time (K windows). Interrupts stay on and run at the game's clock (h_isr), so the music and the
; beeper are the original's. The ISR never touches slots 6 and 7, where the mirror maps its pages.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 311
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_R0 EQU 0x3E35
V_CX EQU 0x3E36                ; view column of this cell
V_CY EQU 0x3E37                ; view row
V_OX EQU 0x3E38                ; Layer 2 column of view column 0
V_OY EQU 0x3E39                ; Layer 2 row of view row 0
V_PTR EQU 0x3E3C               ; word: map pointer
V_N EQU 0x3E3E
V_M EQU 0x3E3F
V_EX EQU 0x3E40                ; word
V_TS EQU 0x3E42                ; clock of the caller of a tile, character or clear
V_IR0 EQU 0x3E43               ; interrupt: R at entry, slot 1 found
V_I7 EQU 0x3E45
V_IR1 EQU 0x3E46
TILES EQU 0xBF41               ; high byte of the tile set the plot uses: D2 or DB
TILESET0 EQU 0xD2
BF50 EQU 0xBF50
BF51 EQU 0xBF51
MAP EQU 0x5C00
L2_PAGE EQU 32                 ; banks 16-18
PG_TILES0 EQU 40               ; D2 set: 2 pages, 64 bytes a tile
PG_TILES1 EQU 42               ; DB set
PG_FONT EQU 44                 ; font, from code 0x20
PG_SPRITES EQU 46              ; patterns and the sprites' first attributes, 2 pages
MMU6 EQU 0                     ; the game's pages in slots 6, 7
MMU7 EQU 1
SPR_DIGIT EQU 48
PAT_DIGIT EQU 48               ; patterns of 0..9
K_STEP EQU 133
K_STEPY EQU 136
BF5A EQU 0xBF5A
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

        MACRO ENTER
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x4000
        push af
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        ENDM
        MACRO LEAVE_R
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ENDM
        MACRO BODY_IN
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        ENDM
        MACRO BODY_OUT
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ENDM
; ---- BFBF: the interrupt, at the game's own clock, on whatever was interrupted ---------
; The whole wrapper is in the hidden ROM as well as the page: it maps back what it found.
; R as the original's: R at entry + the handler's own M1s + a constant.
ISR_W EQU -17
h_isr:
        push af
        push bc
        ld a,r
        push hl
        ld l,a
        ld bc,0x243B
        ld a,0x51
        out (c),a
        inc b
        in a,(c)
        ld h,a
        dec b
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld c,a
        nextreg 0x51,HOOK_PAGE
        ld (V_IR0),hl
        ld a,c
        ld (V_I7),a
        ld a,(HLIB_V_PACE+10)
        or a
        call nz,hlib_pace_hold
        ld a,(V_SPEED)
        nextreg 0x07,a
        ld a,r
        ld (V_IR1),a
        ld a,(V_IR0+1)          ; a hook's stack may be in slot 1: the handler runs on what it found
        nextreg 0x51,a
        call 0x83AB
        nextreg 0x51,HOOK_PAGE
        ld a,r
        ld hl,V_IR1
        sub (hl)
        ld (V_IR1),a
        ld a,(HLIB_V_PACE+10)
        or a
        call nz,hlib_pace_resume
        ld a,(V_I7)
        nextreg 0x07,a
        ld a,(V_IR1)
        add a,ISR_W
        ld hl,V_IR0
        add a,(hl)
        and 0x7F
        ld b,a
        ld a,(hl)
        and 0x80
        or b
        ld b,a
        ld a,(V_IR0+1)
        nextreg 0x51,a
        ld a,b
        ld r,a
        pop hl
        pop bc
        pop af
        ret
; 83EC: break pressed: the handler leaves for the menu, never to return.
h_abort:
        nextreg 0x56,MMU6
        nextreg 0x57,MMU7
        nextreg 0x51,255
        jp 0x8033
h_isr_end:

; ---- 8BFE, 8BD6: the game's update runs at 28 MHz. It waits for its frames as ever ----
h_fast:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xA071
h_slow:
        ENTER
        ld a,(V_SPEED)
        nextreg 0x07,a
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld a,(BF5A)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x8BD9
; 91CB: the game ends straight from the update (a shot at the TNT)
h_slow2:
        ENTER
        ld a,(V_SPEED)
        nextreg 0x07,a
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld a,(0x802D)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0x91CE

; ---- 8514: a tile on screen. A = view row, E = view column, C = tile --------
h_tile:
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x4000
        push af
        ld (V_CY),a
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        ld a,e
        ld (V_CX),a
        ld a,c
        HLIB_SPEED_IN V_TS
        call l2_tile
        BODY_IN
        ld d,a
        and 0x18
        call 0x8517
        BODY_OUT
        ld a,-23
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_TS
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret

; ---- 9D8C: a character. L = code, DE = its screen address ---------------------
h_char:
        ENTER
        ld a,l
        ld (V_N),a
        ld a,e
        and 31
        ld (V_CX),a
        ld a,e
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,d
        and 0x18
        or c
        ld (V_CY),a
        HLIB_SPEED_IN V_TS
        ld a,(V_CX)
        cp 24
        jr nc,.panel
        call l2_char
        jr .done
.panel: call panel_digit
.done:  BODY_IN
        ld h,0
        add hl,hl
        call 0x9D8F
        BODY_OUT
        ld a,-22
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_TS
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret

; ---- 8458: the play area is cleared ------------------------------------------
h_clear:
        ENTER
        HLIB_SPEED_IN V_TS
        call l2_clear
        BODY_IN
        ld hl,0x4000
        call 0x845B
        BODY_OUT
        ld a,-22
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_TS
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret

; ---- 8471: the whole view is drawn from the map -------------------------------
h_draw:
        ENTER
        HLIB_SPEED_IN V_TS
        call l2_draw
        BODY_IN
        ld a,(BF51)
        call 0x8474
        BODY_OUT
        ld a,-22
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_TS
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret

; ---- 8C94, 8D22: the view steps right or left: one cell, as long as the original took ---
; The game's own copy of the screen runs on from here, already at 28 MHz; h_step_r / _l closes.
        MACRO STEP dir
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x4000
        push af
        ld (BF50),a
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        call hlib_debt_open
        ld a,(V_OX)
        add a,dir
        and 31
        ld (V_OX),a
        add a,a
        add a,a
        add a,a
        nextreg 0x16,a
        ENDM
        MACRO STEP_END
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret
        ENDM
h_right:
        STEP 1
        ld a,23
        call l2_column
        STEP_END
h_left:
        STEP 31
        xor a
        call l2_column
        STEP_END

; 8CFA, 8D86: POP BC / DJNZ back. Wait out the window.
        MACRO STEP_CLOSE k,again,done
        ENTER
        ld a,(V_SPEED)
        ld c,a
        ld a,k
        call hlib_pace_waitk
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        pop bc
        djnz .a
        jp done
.a:     jp again
        ENDM
h_step_r:
        STEP_CLOSE K_STEP,0x8C8B,0x8CFD
h_step_l:
        STEP_CLOSE K_STEP,0x8D1A,0x8D89

; ---- 8DB1, 8E4A: the view steps up or down. The copy of the screen in a window; the new
; row comes through 8514, outside it, faster than the original's.
        MACRO STEPY dir
        nextreg 0x51,HOOK_PAGE
        ld (V_SP),sp
        ld sp,0x4000
        push af
        ld (BF51),a
        ld a,r
        ld (HLIB_V_R),a
        push bc
        push de
        push hl
        ld a,(V_OY)
        add a,dir
        cp 24
        jr c,.ok
        sub 24
.ok:    ld (V_OY),a
        add a,a
        add a,a
        add a,a
        nextreg 0x17,a
        call hlib_pace_open
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret
        ENDM
h_up:
        STEPY 23
h_down:
        STEPY 1
; 8E06, 8EA1: POP HL / POP DE / LD B,18: the new row next.
        MACRO STEPY_CLOSE k,next
        ENTER
        ld a,(V_SPEED)
        ld c,a
        ld a,k
        call hlib_pace_waitk
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        pop hl
        pop de
        ld b,0x18
        jp next
        ENDM
h_ud_u:
        STEPY_CLOSE K_STEPY,0x8E0A
h_ud_d:
        STEPY_CLOSE K_STEPY,0x8EA5

; ---- Layer 2 -----------------------------------------------------------------
; l2_tile: A = tile, the plot's own set, at (V_CX, V_CY)
l2_tile:
        ld c,a
        ld a,(TILES)
        cp TILESET0
        ld b,PG_TILES0
        jr z,l2_tile_b
        ld b,PG_TILES1
l2_tile_b:
        ld a,c
        rlca
        and 1
        add a,b
        nextreg 0x56,a
        ld a,c
        and 0x7F
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xC000
        add hl,de
        call l2_cell
        nextreg 0x56,MMU6
        nextreg 0x57,MMU7
        ret

; l2_cell: HL = 64 colours in slot 6. Writes the cell (V_CX, V_CY) in slot 7.
l2_cell:
        ld a,(V_OY)
        ld c,a
        ld a,(V_CY)
        add a,c
        cp 24
        jr c,.y
        sub 24
.y:     ld b,a
        rrca
        rrca
        and 7
        add a,L2_PAGE
        nextreg 0x57,a
        ld a,b
        and 3
        add a,a
        add a,a
        add a,a
        add a,0xE0
        ld d,a
        ld a,(V_OX)
        ld c,a
        ld a,(V_CX)
        add a,c
        and 31
        add a,a
        add a,a
        add a,a
        ld e,a
        ld a,8
.row:   push de             ; a cell ending at column 255 carries into D
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        pop de
        inc d
        dec a
        jr nz,.row
        ret

; l2_char: V_N = the character.
l2_char:
        ld a,(V_N)
        sub 0x20
        cp 96
        ret nc
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xC000
        add hl,de
        nextreg 0x56,PG_FONT
        call l2_cell
        nextreg 0x56,MMU6
        nextreg 0x57,MMU7
        ret

; panel_digit: V_N at (V_CX, V_CY), a panel cell: its digit sprite, or hidden.
panel_digit:
        ld a,(V_CX)
        ld c,a
        ld a,(V_CY)
        cp 9
        jr nz,.boxes
        ld a,c
        sub 25
        ret c
        cp 6
        ret nc
        add a,SPR_DIGIT
        jr .got
.boxes: ld b,SPR_DIGIT+6
        cp 11
        jr z,.box
        ld b,SPR_DIGIT+8
        cp 13
        jr z,.box
        ld b,SPR_DIGIT+10
        cp 15
        ret nz
.box:   ld a,c
        sub 29
        ret c
        cp 2
        ret nc
        add a,b
.got:   ld bc,0x303B
        out (c),a
        ld c,0x57
        ld a,(V_CX)
        add a,a
        add a,a
        add a,a
        add a,32
        push af
        out (c),a
        ld a,(V_CY)
        add a,a
        add a,a
        add a,a
        add a,32
        out (c),a
        pop af
        ld a,0
        adc a,a
        out (c),a
        ld a,(V_N)
        sub 0x30
        cp 10
        jr c,.dig
        xor a
        out (c),a
        ret
.dig:   add a,PAT_DIGIT+0x80
        out (c),a
        ret

; l2_clear: back to no offset, the visible window black.
l2_clear:
        xor a
        ld (V_OX),a
        ld (V_OY),a
        nextreg 0x16,0
        nextreg 0x17,0
        ld a,L2_PAGE
.page:  ld (V_N),a
        nextreg 0x57,a
        ld b,32
        ld hl,0xE000
.line:  push bc
        ld d,h
        ld e,l
        inc e
        ld (hl),0
        ld bc,191
        ldir
        pop bc
        inc h
        ld l,0
        djnz .line
        ld a,(V_N)
        inc a
        cp L2_PAGE+6
        jr nz,.page
        nextreg 0x57,MMU7
        ret

; l2_draw: the view from the map (8471 draws with the first tile set).
l2_draw:
        ld hl,(BF51)
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        ld a,(BF50)
        ld e,a
        ld d,0
        add hl,de
        ld de,MAP
        add hl,de
        ld (V_PTR),hl
        xor a
        ld (V_CY),a
.r:     xor a
        ld (V_CX),a
        ld a,24
        ld (V_M),a
.c:     ld hl,(V_PTR)
        ld a,(hl)
        inc hl
        ld (V_PTR),hl
        ld c,a
        ld b,PG_TILES0
        call l2_tile_b
        ld hl,V_CX
        inc (hl)
        ld hl,V_M
        dec (hl)
        jr nz,.c
        ld hl,(V_PTR)
        ld de,96-24
        add hl,de
        ld (V_PTR),hl
        ld hl,V_CY
        inc (hl)
        ld a,(hl)
        cp 24
        jr nz,.r
        ret

; l2_column: A = view column, the new edge from the map.
l2_column:
        ld (V_CX),a
        ld e,a
        ld a,(BF50)
        add a,e
        ld e,a
        ld d,0
        ld hl,(BF51)
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        add hl,hl
        add hl,bc
        add hl,de
        ld de,MAP
        add hl,de
        ld (V_PTR),hl
        xor a
        ld (V_CY),a
.r:     ld hl,(V_PTR)
        ld a,(hl)
        ld de,96
        add hl,de
        ld (V_PTR),hl
        ld c,a
        ld b,PG_TILES0
        call l2_tile_b
        ld hl,V_CY
        inc (hl)
        ld a,(hl)
        cp 24
        jr nz,.r
        ret

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3A00
        SAVEBIN "eagle_rom.bin",rom_start,$-rom_start

; ---- the stub's setup: palette, Layer 2 on, panel sprites ---------------------
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x14,0xE3
        nextreg 0x12,L2_PAGE/2
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x70,0
        nextreg 0x1C,0x0F
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        ld e,0x10
        call pal
        ld e,0x20
        call pal
        nextreg 0x43,0
        ; patterns, then attributes, from the sprite pages (slot 4, 5)
        nextreg 0x54,PG_SPRITES
        nextreg 0x55,PG_SPRITES+1
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,0x8000
        ld d,60
.pat:   ld bc,0x005B
        otir
        dec d
        jr nz,.pat
        ld bc,0x303B
        xor a
        out (c),a
        ld hl,0x8000+60*256
        ld d,60
.spr:   ld bc,0x0457
        otir
        dec d
        jr nz,.spr
        nextreg 0x54,4
        nextreg 0x55,5
        nextreg 0x15,0x01
        nextreg 0x69,0x80
        ld hl,printer
        ld de,0x5B00
        ld bc,256
        ldir
        ret
pal:    ld a,e
        nextreg 0x43,a
        nextreg 0x40,0
        ld hl,l2_pal
        ld b,PAL_N
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .lp
        ret
PAL_N   EQU 64
l2_pal: defs PAL_N*2,0
setup_end:
printer:
        SAVEBIN "eagle_setup.bin",setup,setup_end-setup
