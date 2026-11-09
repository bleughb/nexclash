; Booty (John F. Cain, Firebird, 1984, 48K): Enhanced colours, a menu option. The default look runs no hook.
;
; The game prints every figure and all the scenery as whole 8x8 cells on the ULA, through the ROM's PR-ALL and two
; loops of its own, so there is no colour clash to remove. Enhanced shows the Spec256 set's colours on a Layer 2 over
; the unchanged ULA: every print writes the same cell on Layer 2 from a table of the set's pixels (eight bytes for each
; byte of graphic, by the graphic's own address), and the pixels the set leaves to the attribute (value FF) are
; transparent, so the ULA under them shows ink, paper and FLASH as the game set them. The game's own delay (E9D9,
; D3A6) repays what the hooks cost. The ISR plays beeper notes by timed loops, up to two frames long, and how much time
; the game gets between notes turns on a few T of the handler's length: so the handler itself has no hook. Inside a hook,
; or a room at 28 MHz, I points at the vector at 3BFF, where isr_w runs the handler at the game's clock.
; Title: its own Layer 2 picture (TITLE_BANK), never drawn on again. The sea's sparkle stays ULA; the set shows it on
; black, so paper blue is black while the title shows.
;
; Slots inside a hook: 1 this page, 4 Layer 2, 5 and 6 the colour table. The ISR never touches 1, 4, 5 or 6.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_IN EQU 0x3BF0                 ; 1 in this page while a hook runs; always 0 in the hidden ROM's copy (below the font)
V_ILEAVE EQU 0x3E3D             ; I when a hook leaves: 3B in a room
I_GAME EQU 0xF4
V_ROOMSP EQU 0x3E35             ; the game's clock while a room is drawn at 28 MHz
V_R0 EQU 0x3E36
PLAY_BANK EQU 16
TITLE_BANK EQU 19
FONT_PAGE EQU 44                ; the table of 3C00-3FFF (one page)
TABLE_PAGE EQU 46               ; the table of 8000-FFFF (32 pages)
W_ROOM0 EQU 6300                ; the original's room time: 322,000 T + 921 T a cell, room 0 another 190,000 (roomt.py)
W_CELL EQU 21                   ; a cell of a room
W_ROOM EQU 4800                  ; a room besides
K_ROOM EQU 0                    ; a cell of a room being built
K_CELL EQU 35                   ; a cell hook's time at the game's clock, 1/16 lines
K_FILL EQU 38                   ; a row of the fill hook
K_DELAY EQU 50                  ; the delay hook
K_COMP EQU 100                   ; the frame-building hook, and for each cell of the frame
V_WAIT EQU 0x3E3E                ; steps of 26 T owed at the room's end
V_C EQU 0x3E40                  ; l2_compose's counters and pointers
BUF_PAGE EQU TABLE_PAGE + 8     ; the table of A000-A3FF
BUF_CLEAR EQU 0xA000 + 0xEC * 8 ; A0EC, the buffer the game clears (128 bytes: A06C is zeros)
BUF_F4 EQU 0xA000 + 0xF4 * 8    ; A0F4, where the frame goes
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
        ld a,1
        ld (V_IN),a
        ld a,3Bh
        ld i,a
        HLIB_SPEED_IN_ABC V_SPEED
        ENDM
        MACRO LEAVE_R
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT_A V_SPEED
        xor a
        ld (V_IN),a
        ld a,(V_ILEAVE)
        ld i,a
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ENDM

; ---- 0B9B, ROM PR-ALL: HL the screen, DE the graphic; LD A,(5C91) displaced ---------------------------------------
h_rom:
        ENTER
        ld a,h                  ; a print to the printer's buffer draws nothing
        cp 0x40
        jr c,.n
        cp 0x58
        jr nc,.n
        ex de,hl
        ld a,(0x5C91)
        call l2_cell
.n:     ld hl,K_CELL
        call hlib_debt_add
        ld a,-13
        call hlib_r_set
        LEAVE_R
        ld a,(0x5C91)
        jp 0x0B9E

; ---- A834 / E6F9, the game's own loops: DE the screen + 1, HL the graphic; DEC DE / LD B,8 displaced ----------
        MACRO LOOP_HOOK back, kk, wait
        ENTER
        dec de
        xor a
        call l2_cell
        ld hl,kk
        call hlib_debt_add
        ld hl,(V_WAIT)
        ld de,wait
        add hl,de
        ld (V_WAIT),hl
        ld a,-13
        call hlib_r_set
        LEAVE_R
        dec de
        ld b,8
        jp back
        ENDM
h_a:    LOOP_HOOK 0xA837, K_ROOM, W_CELL
h_e:    LOOP_HOOK 0xE6FC, K_CELL, 0

; ---- E522 / E564, a block of FF across the row: LD HL,(5C84) displaced ----------------------------------------------
        MACRO FILL_HOOK back
        ENTER
        ld hl,(0x5C84)
        ld a,(ix+7)
        ld b,a
        call l2_fill
        ld hl,K_FILL
        call hlib_debt_add
        ld a,-13
        call hlib_r_set
        LEAVE_R
        ld hl,(0x5C84)
        jp back
        ENDM
h_f1:   FILL_HOOK 0xE525
h_f2:   FILL_HOOK 0xE567

; ---- 0E44, ROM CL-LINE, B lines to the bottom of the screen: the original at 28 MHz with Layer 2's clear ------------
h_cll:
        ENTER
        nextreg 0x12,PLAY_BANK  ; the title has gone
        nextreg 0x40,17
        nextreg 0x41,0x02
        ld a,(0x3FFD)           ; B, as ENTER pushed it
        call l2_clear
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call .body
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld a,-23
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT_A V_SPEED
        xor a
        ld (V_IN),a
        ld a,(V_ILEAVE)
        ld i,a
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ret
.body:  push bc
        call 0x0E9B
        jp 0x0E48

; ---- CD9D, the title comes back: LD DE,4000 displaced -----------------------------------------------------------------
h_title:
        ENTER
        nextreg 0x12,TITLE_BANK
        nextreg 0x40,17
        nextreg 0x41,0
        nextreg 0x69,0x80
        ld a,-13
        call hlib_r_set
        LEAVE_R
        ld de,0x4000
        jp 0xCDA0

; ---- E0A9 (CALL A804), a room: its drawing runs at 28 MHz until h_re. While a note sounds in the ISR the room gets the little time
; the ISR leaves, so anything it costs at the game's clock would be multiplied (a death's room took 94 frames against 36). CALL here, JP there.
h_room:
        ENTER
        ld a,0x3B
        ld (V_ILEAVE),a
        ld a,(V_SPEED)
        ld (V_ROOMSP),a
        ld hl,W_ROOM
        ld a,(0x5BD3)
        or a
        jr nz,.w
        ld hl,W_ROOM + W_ROOM0  ; the first hold also builds the room table
.w:     ld (V_WAIT),hl
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        xor a
        ld (V_IN),a
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp 0xA804
; E0AC, the room is drawn: LD HL,3C00 displaced.
h_re:
        ENTER
        ld a,I_GAME
        ld (V_ILEAVE),a
        ld a,(V_ROOMSP)
        ld (V_SPEED),a
        nextreg 0x07,a
        ld hl,(V_WAIT)          ; what the room took the original, less what it took here: at the game's clock, so the ISR
.s:     dec hl                  ; takes its share of it as it did of the original's
        ld a,h
        or l
        jr nz,.s
        ld (V_WAIT),hl
        ld a,-13
        call hlib_r_set
        LEAVE_R
        ld hl,0x3C00
        jp 0xE0AF

; ---- CE41 (CALL D4BE), the hidden game, reached only with its cheat: the set has no colours for what it draws, so Layer 2 goes
; off until the title comes back. CALL here, JP there. --------------------------------------------------------------------
h_hid:
        ENTER
        nextreg 0x69,0
        ld a,-12
        call hlib_r_set
        LEAVE_R
        jp 0xD4BE

; ---- EED7, a figure's frame shifted to its place: the game builds it at A0F4 from its graphic, one to four steps of two
; pixels, the part past the byte's edge going to the column before. The same here on the table's bytes for that buffer,
; so the prints that follow find the frame's colours by the address they print from. LD DE,A0EC displaced. --------------
h_comp:
        ENTER
        call l2_compose
        ld a,-13
        call hlib_r_set
        LEAVE_R
        ld de,0xA0EC
        jp 0xEEDA

; ---- E9D9 and D3A6, the game's delay: BC steps of 26 T. It repays the debt ---------------------------------------------
        MACRO DELAY_HOOK steps, back
        ENTER
        ld hl,K_DELAY
        call hlib_debt_add
        ld hl,(steps) * 13 / 7 - 16
        call hlib_debt_repay    ; HL = 1/16 lines to skip; a step is 13/7 of those: 1/2 + 1/32 + 1/128 of them in steps
        ld d,h
        ld e,l
        srl d
        rr e
        push de
        srl d
        rr e
        srl d
        rr e
        srl d
        rr e
        srl d
        rr e
        ld b,d
        ld c,e
        srl d
        rr e
        srl d
        rr e
        pop hl
        add hl,de
        add hl,bc
        ld a,l
        add a,a
        add a,a
        and 0x7F
        ld (V_R0),a             ; four M1s a step
        ex de,hl
        ld hl,steps
        or a
        sbc hl,de
        ld (V_R0 + 2),hl
        ld a,-12
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        pop hl
        pop de
        pop bc
        ld bc,(V_R0 + 2)
        HLIB_SPEED_OUT_A V_SPEED
        xor a
        ld (V_IN),a
        ld a,(V_ILEAVE)
        ld i,a
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp back
        ENDM
h_dly1: DELAY_HOOK 2000, 0xE9DC
h_dly2: DELAY_HOOK 5000, 0xD3A9

; ---- l2_cell: HL the graphic, DE the screen, A = P-FLAG. AF, BC, DE, HL lost. ----------------------------------------
l2_cell:
        and 5
        ld (V_R0 + 4),a
        ld a,d
        and 0x18
        rrca
        rrca
        ld b,a
        ld a,e
        rlca
        and 1
        or b
        add a,PLAY_BANK * 2
        nextreg 0x54,a
        ld a,e
        add a,a
        add a,a
        add a,a
        ld b,a                  ; x
        ld a,e
        and 0x60
        rrca
        rrca
        or 0x80
        ld (V_R0 + 6),a         ; the row's high byte in slot 4
        ld a,h
        rrca
        rrca
        and 0x3F
        cp 32
        jr nc,.t
        ld a,FONT_PAGE
        jr .p
.t:     add a,TABLE_PAGE - 32
.p:     nextreg 0x55,a
        inc a
        nextreg 0x56,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,0xA0
        ld h,a
        ld a,(V_R0 + 4)
        or a
        ld a,(V_R0 + 6)
        jp nz,.slow
        ld c,255                ; LDI leaves B, the x, alone: fewer than 256 of them
        REPT 8
        ld d,a
        ld e,b
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        inc a
        ENDR
.done:  nextreg 0x54,4
        nextreg 0x55,5
        nextreg 0x56,0
        ret
.slow:  ld d,a
        ld e,b
        ld a,(V_R0 + 4)
        ld c,0
        bit 2,a
        jr z,.s1
        dec c
.s1:    ld a,8
.s2:    push af
        ld b,8
.s3:    ld a,(hl)
        xor c
        ld (V_R0 + 5),a
        ld a,(V_R0 + 4)
        rrca
        ld a,(V_R0 + 5)
        jr nc,.s4
        ex de,hl
        xor (hl)
        ex de,hl
.s4:    ld (de),a
        inc hl
        inc e
        djnz .s3
        ld a,e
        sub 8
        ld e,a
        inc d
        pop af
        dec a
        jr nz,.s2
        jr .done

l2_compose:
        ld a,(ix+2)
        inc a
        add a,a                 ; n, the pixels that go to the column before: 2, 4, 6, 8
        ld (V_C),a
        ld a,(ix+7)
        ld (V_C + 1),a          ; width in cells
        ld e,a
        ld a,(ix+8)
        ld (V_C + 2),a          ; height in cells
        ld d,a
        mul d,e                 ; cells; K: a base and 122 sixteenths a cell
        ld d,e
        ld e,122
        mul d,e
        ex de,hl
        ld de,K_COMP
        add hl,de
        call hlib_debt_add
        ld e,(ix+6)
        ld d,0
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,(0x5C36)
        add hl,de
        ld (V_C + 3),hl         ; the graphic of this column, top cell
        ld a,(V_C + 2)
        inc a
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl               ; a column's chunky bytes: 64 x (height + 1)
        ld de,BUF_F4
        ld (V_C + 5),de         ; IX's place
        add hl,de
        ld (V_C + 7),hl         ; IY's place
        nextreg 0x55,BUF_PAGE
        ld hl,BUF_CLEAR
        ld de,BUF_CLEAR + 1
        ld bc,1023
        ld (hl),0
        ldir
        ld a,(V_C + 1)
.col:   ld (V_C + 9),a
        ld hl,(V_C + 3)
        ld (V_C + 10),hl        ; the top of this cell
        ld a,(V_C + 2)
.row:   ld (V_C + 12),a
        ld hl,(V_C + 10)
        ld b,8
.byte:  push bc
        push hl
        ld a,h
        rrca
        rrca
        and 0x3F
        add a,TABLE_PAGE - 32
        nextreg 0x56,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        add a,0xC0
        ld h,a                  ; HL the byte's eight pixels
        ld a,(V_C)
        ld c,a
        ld b,0
        push bc
        ld de,(V_C + 5)
        ld a,8
        sub c
        add a,e
        ld e,a
        adc a,d
        sub e
        ld d,a                  ; the column before's last n pixels
        ldir
        pop bc
        ld a,8
        sub c
        ld c,a
        ld de,(V_C + 7)         ; then the rest, at this column's start
        jr z,.z
        ldir
.z:     ld a,(V_C)
        ld b,a
        xor a
.z1:    ld (de),a
        inc de
        djnz .z1
        ld hl,(V_C + 5)
        ld de,8
        add hl,de
        ld (V_C + 5),hl
        ld hl,(V_C + 7)
        add hl,de
        ld (V_C + 7),hl
        pop hl
        inc hl
        pop bc
        djnz .byte
        ; the next cell down: the graphic's cells are row by row, width across
        ld a,(V_C + 1)
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        ld hl,(V_C + 10)
        add hl,de
        ld (V_C + 10),hl
        ld a,(V_C + 12)
        dec a
        jp nz,.row
        ; a free cell at each column's foot: 64 chunky bytes
        ld de,64
        ld hl,(V_C + 5)
        add hl,de
        ld (V_C + 5),hl
        ld hl,(V_C + 7)
        add hl,de
        ld (V_C + 7),hl
        ld de,8
        ld hl,(V_C + 3)
        add hl,de
        ld (V_C + 3),hl
        ld a,(V_C + 9)
        dec a
        jp nz,.col
        nextreg 0x55,5
        nextreg 0x56,0
        ret

; ---- l2_fill: HL a pixel row's screen address, B bytes of it: transparent on Layer 2. AF, BC, DE, HL lost. ---------------
l2_fill:
        ld a,h
        and 0x18
        rrca
        rrca
        ld c,a
        ld a,l
        rlca
        and 1
        or c
        add a,PLAY_BANK * 2
        nextreg 0x54,a
        ld a,l
        add a,a
        add a,a
        add a,a
        ld e,a                  ; x
        ld a,l
        and 0x60
        rrca
        rrca
        ld c,a
        ld a,h
        and 7
        or c
        or 0x80
        ld d,a
        ld l,b
        ld a,b
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        ld a,b
        or c
        jr z,.e
        ex de,hl
        ld (hl),0xFF
        dec bc
        ld a,b
        or c
        jr z,.e
        ld d,h
        ld e,l
        inc de
        ldir
.e:     nextreg 0x54,4
        ret

; ---- l2_clear: A = lines from the bottom. Colour 0 (black, opaque), as the set's empty cells. AF, BC, DE, HL lost. ------
l2_clear:
        ld e,a                  ; 1..24
        ld a,24
        sub e
        ld d,a                  ; the first line
.ln:    ld a,d
        cp 24
        jr nc,.x
        rrca
        rrca
        and 7
        add a,PLAY_BANK * 2
        nextreg 0x54,a
        ld a,d
        and 3
        add a,a
        add a,a
        add a,a
        or 0x80
        ld h,a
        ld l,0
        ld (hl),0
        push de
        ld d,h
        ld e,1
        ld bc,0x07FF
        ldir
        pop de
        inc d
        jr .ln
.x:     nextreg 0x54,4
        ret

; ---- the ISR at the game's clock, when it lands in a hook or a room ---------------------------------------------------
; Reached through I = 3B and the word at 3BFF. Runs from either copy of this page, on the stack it finds. NR 7F holds the clock.
isr_w:  push af
        push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        nextreg 0x7F,a
        ld a,(V_IN)
        or a
        jr z,.z                 ; a room: V_SPEED and this variable are the hidden copy's; the game's clock is 3.5 MHz, near enough
        ld a,(V_SPEED)
        cp 3                    ; a hook inside a room latched 28 MHz: the game's clock is V_ROOMSP
        jr nz,.s
        ld a,(V_ROOMSP)
        jr .s
.z:     xor a
.s:     nextreg 0x07,a
        pop bc
        pop af
        call 0xFE69
isr_r:  push af
        push bc
        ld bc,0x243B
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,a
        dec b
        ld a,7
        out (c),a
        pop bc
        pop af
        ret
isr_end:
rom_end:
regblock EQU 0x3C08
        ASSERT $ < 0x3C00
        SAVEBIN "booty_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x70,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x12,TITLE_BANK
        nextreg 0x16,0
        nextreg 0x17,0
        nextreg 0x71,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,e_palette
        ld b,0
.lp:    ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .lp
        nextreg 0x43,0
        nextreg 0x40,17
        nextreg 0x41,0
        nextreg 0x69,0x80
        ret
e_palette:
        defs 512,0
setup_end:
        SAVEBIN "booty_setup.bin",setup,setup_end-setup
