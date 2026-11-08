; Jilly's Farm Volume 1 - SokoBAArn!, Enhanced: the Spec256 set's colours on Layer 2, faithfully.
;
; The set is the game's V1.00; this release is V1.01, with the graphics 13 bytes higher. Every byte with colour in the
; set matches this release at that offset, so the colours are carried by graphic.
;
; The game composes in a buffer (DC00-FBFF, column in the high byte, y in the low) and copies the dirty cells to the
; screen. Spec256 runs that on eight planes, so each pixel holds an 8-bit value. Here a second Layer 2 is that buffer in
; values: each plot routine's bytes are repeated there, value by value, as the planes would do them (LDD copies; AND
; mask, OR graphic; shifts as pixel offsets). The game's copy then copies the same cells to the Layer 2 on show. Value
; FF, "the attribute's colour", is the transparent colour, so the ULA below shows it.
;
; Interrupts stay on: the game's IM 2 handler (8181) touches only A18B-A18F and the keyboard. The value buffer goes in
; slot 0, value tables or the front buffer in slots 6 and 7, this page in slot 1.
;
; The game runs flat out with no frame wait, so its time is its pace. Its update draws in one run (A2C3, A398, A801, the
; copy): that run goes at 28 MHz in a K window, the Layer 2 work nested out of it, and the wait brings the whole back to
; the original's time. Sound is never inside it. Elsewhere each routine runs whole at 28 MHz, which pays for its work.
        DEVICE ZXSPECTRUMNEXT
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
K_MOVE EQU 110                 ; the update's first stretch: the same
K_DRAW EQU 85                 ; the game's draw: original time per unit of its 28 MHz time, x 16
DEBT_KEEP EQU 320               ; 1/16 lines: 20 lines at most carry from one window to the next, the rest wait in V_BANK
U_WIN EQU 30                   ; 1/16 lines: a window's own entry and exit at the game's clock
U_PLOT EQU 100                  ; 1/16 lines: a hook's own time in the window, as K scales it: goes to the debt
V_W EQU 0x3E2C                 ; a draw window is open
V_WSPEED EQU 0x3E2D
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_R0 EQU 0x3E35
P_ROW EQU 0x3E3C               ; the row's high byte in the slot
P_Y EQU 0x3E3D
P_X EQU 0x3E3E
P_COLS EQU 0x3E41
P_N EQU 0x3E42
P_Y0 EQU 0x3E46
P_I EQU 0x3E47
P_T EQU 0x3E48                 ; word
P_PGB EQU 0x3E4A
P_SRC EQU 0x3E4C                ; word
P_CELLS EQU 0x3E4E              ; word
V_BANK EQU 0x3E2E               ; word
R_F EQU 0x3EC0                 ; 8 font bytes
PG_BACK EQU 32                 ; 8 pages: y 0-255 (the screen only uses 0-191)
L2_FRONT EQU 20                ; 16K bank; pages 40-45
PG_FRONT EQU 40
PG_T EQU 46                    ; 10 pages: the set's AD00-BFFF, 16 bytes a source byte. See tables() in the engine:
                               ; +0-7 values, +8 write bits as an AND mask, +9 as a CPL mask, +10 general flags
T_LO EQU 0xAD00
        ORG 0x2800
rom_start:
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
        MACRO EXIT_TO target
        ld a,-12
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        jp target
        ENDM
        MACRO COPY_BODY body
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        call body
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ENDM
        MACRO FINISH body
        COPY_BODY body
        ld a,-21
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret
        ENDM
; ---- a plot on the values, then the game's own routine ---------------------------
        MACRO PLOT_HOOK kind, n, k, body
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld a,n
        ld (P_COLS),a
        ld a,k
        ld (P_N),a
        call nest_in
        call kind
        call nest_out
        FINISH body
        ENDM
h_92F6: PLOT_HOOK l2_ldd,2,16,0x92F6
h_936A: PLOT_HOOK l2_ldd,2,48,0x936A
h_9B8D: PLOT_HOOK l2_ldd,4,16,0x9B8D
h_9BF1: PLOT_HOOK l2_mask,4,8,0x9BF1
h_9C33: PLOT_HOOK l2_mask,4,24,0x9C33
h_9CE5: PLOT_HOOK l2_mask,2,24,0x9CE5
h_9D97: PLOT_HOOK l2_mask,4,40,0x9D97
h_9EB9: PLOT_HOOK l2_mask,4,29,0x9EB9
h_93D4: PLOT_HOOK l2_mask,2,56,0x93D4
h_96EB: PLOT_HOOK l2_mask,3,56,0x96EB
h_9F8E: PLOT_HOOK l2_sheep,3,29,0x9F8E
h_A02B: PLOT_HOOK l2_sheep,4,29,0xA02B

h_clear:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call nest_in
        call l2_clear
        call nest_out
        FINISH 0x923E
h_wipe:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call nest_in
        call l2_wipe
        call nest_out
        FINISH 0x8B00
h_copy:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call nest_in
        ld hl,0
        ld (P_CELLS),hl
        call l2_copy
        call nest_out
        call cell_credit
        nextreg 0x69,0x80
        COPY_BODY .s
        ld a,-23
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret
.s:     ld hl,0xFC00
        jp 0x8BF0
h_digit:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld hl,7
        add hl,sp
        ld a,(hl)
        call l2_digit
        FINISH 0x92D3

; ---- the draw run: open at its first CALL, closed at the CALL after the copy ---------
; The update's first stretch (8692 to the end of the sheep's move at 8374) is a window of its own, so its time pays for the
; plots too; the sound at 837D and 8382 stays at the game's clock between the two.
        MACRO OPEN_HOOK target
        ENTER
        call open_w
        EXIT_TO target
        ENDM
h_open: OPEN_HOOK 0xA2C3
h_open1: OPEN_HOOK 0x8692
h_close:
        ENTER
        ld a,K_DRAW
        call close_w
        EXIT_TO 0xA605
h_close1:
        ENTER
        ld a,K_MOVE
        call close_w
        ld a,-13
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld a,(0xA194)           ; the displaced LD A,(A194)
        jp 0x8377
open_w: ld a,(V_W)
        or a
        jr nz,.again            ; never latch 28 MHz as the game's clock
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (V_WSPEED),a
        nextreg 0x07,3
        ld a,1
        ld (V_W),a
.again: jp hlib_pace_open
close_w:
        push af
        ld hl,U_WIN
        call hlib_debt_add
        xor a
        ld (V_W),a
        ld a,(V_WSPEED)
        ld c,a
        pop af
        call hlib_pace_waitk
        ld hl,(HLIB_V_PACE + 4) ; a busy update's overage comes back a little a window, not in a burst of speed after it
        ld de,DEBT_KEEP
        or a
        sbc hl,de
        jr c,.bank
        ex de,hl                ; DE = the excess, HL = DEBT_KEEP
        ld (HLIB_V_PACE + 4),hl
        ld hl,(V_BANK)
        add hl,de
        jr nc,.save
        ld hl,0xFFFF
.save:  ld (V_BANK),hl
        jr .keep
.bank:  ex de,hl                ; DE = what the debt lacks of DEBT_KEEP, negated
        ld hl,(V_BANK)
        add hl,de               ; the bank less that
        jr c,.part              ; enough in the bank
        ld de,(V_BANK)
        ld hl,(HLIB_V_PACE + 4)
        add hl,de
        ld (HLIB_V_PACE + 4),hl ; all of the bank
        ld hl,0
        ld (V_BANK),hl
        jr .keep
.part:  ld (V_BANK),hl
        ld hl,DEBT_KEEP
        ld (HLIB_V_PACE + 4),hl
.keep:  ld a,(V_WSPEED)
        nextreg 0x07,a
        ret

; The original's copy writes to contended screen memory, so its time per cell is more than the window's K makes of its
; 28 MHz time: each cell copied is credited on top.
cell_credit:
        ld a,(V_W)
        or a
        ret z
        ld hl,(P_CELLS)
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; 16 x cells, 1/16 lines: a line a cell
        jp hlib_debt_add
nest_in:
        ld a,(V_W)
        or a
        ret z
        jp hlib_nest_open
nest_out:
        ld a,(V_W)
        or a
        ret z
        ld a,U_PLOT
        jp hlib_nest_close

; A letter, inside the game's string loop (92AE): A = the code, DE the buffer.
h_char:
        ENTER
        HLIB_SPEED_IN V_SPEED
        ld hl,7
        add hl,sp
        ld a,(hl)
        call l2_char
        ld a,-13
        call hlib_r_set
        LEAVE_R
        add a,a                 ; the displaced ADD A,A; LD H,0
        ld h,0
        jp 0x92B1

; ---------------- the value buffer ------------------------------------------------
; set_row: A = y -> slot 0 = its page, P_Y, P_ROW set. A, C lost.
set_row:
        ld (P_Y),a
        ld c,a
        and 31
        ld (P_ROW),a
        ld a,c
        rlca
        rlca
        rlca
        and 7
        add a,PG_BACK
        ld (P_PGB),a
        nextreg 0x50,a
        ret
; row_up: the next line up. row_down: the next line down.
row_up: ld a,(P_Y)
        dec a
        ld (P_Y),a
        and 31
        ld (P_ROW),a
        cp 31
        ret nz
        ld a,(P_Y)
        jr set_row
row_down:
        ld a,(P_Y)
        inc a
        ld (P_Y),a
        and 31
        ld (P_ROW),a
        ret nz
        ld a,(P_Y)
        jr set_row

; t_off: HL = a source byte -> A = its page, HL = its 16 bytes in a slot's offsets. BC lost.
t_off:  ld bc,T_LO
        or a
        sbc hl,bc
        ld a,h
        srl a
        add a,PG_T
        push af
        ld a,h
        and 1
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        pop af
        ret
; t_down: HL -> its 16 bytes in slot 7, slot 6 the page below: a plot going down the source stays mapped.
t_down: call t_off
        nextreg 0x57,a
        dec a
        nextreg 0x56,a
        ld a,h
        or 0xE0
        ld h,a
        ret
; t_up: HL -> its 16 bytes in slot 6, slot 7 the page above.
t_up:   call t_off
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        ld a,h
        or 0xC0
        ld h,a
        ret
map_back:
        nextreg 0x50,255
        nextreg 0x56,0
        nextreg 0x57,1
        ret
; The game's registers, in a routine CALLed straight from the hook.
        MACRO GAME_REGS
        ld hl,4
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,2
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ENDM
; set_x: D = the buffer's column page -> P_X. A lost.
set_x:  ld a,d
        sub 0xDC
        add a,a
        add a,a
        add a,a
        ld (P_X),a
        ret

; plot_set_ix: plot_set from a routine that has saved IX on the stack.
plot_set_ix:
; plot_set: the game's registers -> HL = its entry for the source byte (+A), IXl = x, P_Y0 = y. IX is the caller's to save.
plot_set:
        push af                 ; on the stack: AF, return, IX, return to the hook, the game's HL, DE
        ld hl,10
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,8
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        push de
        call t_down
        pop de
        pop af
        add a,l                 ; entries are aligned on 16: A only adds to the low byte
        ld l,a
        ld a,d
        sub 0xDC
        add a,a
        add a,a
        add a,a
        ld ixl,a
        ld a,e
        ld (P_Y0),a
        ret
; col_set: slot 0 for the column's first line; D, E the pixels; IXh the lines.
        MACRO COL_SET
        ld a,(P_Y0)
        call set_row
        ld a,(P_ROW)
        ld d,a
        ld e,ixl
        ld a,(P_N)
        ld ixh,a
        ENDM
; col_next: the next column, or home.
        MACRO COL_NEXT lbl
        ld a,ixl
        add a,8
        ld ixl,a
        ld a,(P_COLS)
        dec a
        ld (P_COLS),a
        jp nz,lbl
        pop ix
        jp map_back
        ENDM
; up_page: D went below 0: the page above, D the page's last line.
up_page:
        ld d,31
        ld a,(P_PGB)
        dec a
        sub PG_BACK
        and 7
        add a,PG_BACK
        ld (P_PGB),a
        nextreg 0x50,a
        ret

; l2_ldd: HL the source going down, D column, E y going up the screen; P_COLS columns of P_N.
l2_ldd: push ix
        xor a
        call plot_set_ix
.col:   COL_SET
.byte:  ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ld a,(hl)               ; the last by hand: an LDI at column 31 would carry into the row
        ld (de),a
        ld bc,-23
        add hl,bc
        ld e,ixl
        dec d
        jp m,.page
.cont:  dec ixh
        jp nz,.byte
        COL_NEXT .col
.page:  call up_page
        jp .cont

; l2_mask: HL going down: mask, then graphic: v = (v AND mask) OR graphic. D column, E y going up the screen.
l2_mask:
        push ix
        ld a,8
        call plot_set_ix
.col:   COL_SET
.byte:  ld a,(hl)
        or a
        jp z,.skip
        cp 0xFF
        jp z,.all
        cp 1
        jp z,.one
.bits:  inc l                   ; most mask bytes write one run of pixels: +12 its start + 1, +13 its length
        inc l
        inc l
        inc l
        ld a,(hl)
        or a
        jr z,.twice
        push de
        dec a
        ld b,a
        add a,e
        ld e,a
        inc l
        ld c,(hl)
        ld a,l
        sub 29
        jr nc,.n1
        dec h
.n1:    add a,b
        ld l,a
        ld b,0
        ldir
        pop de
        ld a,l
        and 0xF0
        sub 8
        jr nc,.n2
        dec h
.n2:    ld l,a
        jp .row
.twice: dec l
        dec l
        dec l
        dec l
        ld a,(hl)
        ld bc,-24
        add hl,bc
        REPT 7
        rlca
        jr c,$+6
        inc hl
        inc e
        jr $+4
        ldi
        ENDR
        rlca
        jr nc,$+4
        ld a,(hl)
        ld (de),a
        inc hl
.step:  ld bc,-16
        add hl,bc
.row:   ld e,ixl
        dec d
        jp m,.page
.cont:  dec ixh
        jp nz,.byte
        COL_NEXT .col
.skip:  ld bc,-32
        add hl,bc
        jp .row
.page:  call up_page
        jp .cont
.all:   ld bc,-24
        add hl,bc
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ld a,(hl)
        ld (de),a
        inc hl
        jp .step
.one:   inc hl
        inc hl
        bit 0,(hl)
        dec hl
        dec hl
        jp z,.bits
        push de
        push hl
        ld bc,-24
        add hl,bc
        ld b,h
        ld c,l                  ; BC = the graphic's
        pop hl
        ld a,l
        sub 8
        ld l,a                  ; HL = the mask's
        ex de,hl                ; DE = the mask's, HL the pixels
        REPT 8
        ld a,(de)
        and (hl)
        ld (hl),a
        ld a,(bc)
        or (hl)
        ld (hl),a
        inc de
        inc bc
        inc l
        ENDR
        pop de                  ; the pixels' start again
        ld h,b
        ld l,c                  ; the graphic's +8: the entry - 16
        jp .step

; pair_all, pair_bits: the sheep's: A the write bits, HL the graphic's values, DE the pixels.
pair_all:
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ld a,(hl)
        ld (de),a
        ret
pair_bits:
        REPT 8
        rlca
        jr c,$+6
        inc hl
        inc e
        jr $+4
        ldi
        ENDR
        ret

; l2_sheep: HL going up: graphic, mask: v = (v AND NOT mask) OR graphic. D column, E y going up the screen, IXl the
; pixels across: the sheep's own shifts. P_COLS pairs a row, P_N rows. On the planes the routine for IXl AND 7 not 0
; keeps the shifted graphic in IY, which has no planes, so it ORs the master's bits on all of them: that path's graphic
; has no colour on Spec256 either, and neither does it here; the mask still comes from the planes.
l2_sheep:
        GAME_REGS
        ld (P_SRC),hl
        push de
        call t_up
        pop de
        ld (P_T),hl
        call set_x
        ld a,ixl
        and 7
        ld c,a
        ld a,(P_X)
        add a,c
        ld (P_Y0),a             ; the row's first x
        ld a,e
        call set_row
        ld a,ixl
        and 7
        jp nz,sheep_mono
.row:   ld a,(P_Y0)
        ld (P_X),a
        ld a,(P_COLS)
        ld (P_I),a
.pair:  ld hl,(P_T)
        ld bc,16+9
        add hl,bc
        ld a,(hl)
        or a
        jr z,.next
        ld b,a
        ld a,(P_ROW)
        ld d,a
        ld a,(P_X)
        ld e,a
        ld a,b
        call pair_or
.next:  ld hl,(P_T)
        ld bc,32
        add hl,bc
        ld (P_T),hl
        ld a,(P_X)
        add a,8
        ld (P_X),a
        ld hl,P_I
        dec (hl)
        jp nz,.pair
        call row_up
        ld hl,P_N
        dec (hl)
        jp nz,.row
        jp map_back

; sheep_mono: the shifted routines: write bits from +11 of the mask's entry, the graphic's bits from the game's own byte.
sheep_mono:
.row:   ld a,(P_Y0)
        ld (P_X),a
        ld a,(P_COLS)
        ld (P_I),a
.pair:  ld hl,(P_T)
        ld bc,16+11
        add hl,bc
        ld b,(hl)
        ld de,32-27
        add hl,de
        ld (P_T),hl
        ld hl,(P_SRC)
        ld c,(hl)
        inc hl
        inc hl
        ld (P_SRC),hl
        ld a,(P_ROW)
        ld h,a
        ld a,(P_X)
        ld l,a
        add a,8
        ld (P_X),a
        REPT 8
        sla b
        sbc a,a
        cpl
        and (hl)
        ld d,a
        sla c
        sbc a,a
        or d
        ld (hl),a
        inc l
        ENDR
        ld hl,P_I
        dec (hl)
        jp nz,.pair
        call row_up
        ld hl,P_N
        dec (hl)
        jp nz,.row
        jp map_back

; pair_or: HL = the mask's +9, A = its write bits (not 0), DE the pixels. The graphic is one source byte lower.
pair_or:
        cp 0xFF
        jr z,.all
        cp 1
        jr nz,.bits
        inc hl
        bit 1,(hl)
        dec hl
        jr nz,general_or
.bits:  ld bc,-25
        add hl,bc
        jp pair_bits
.all:   ld bc,-25
        add hl,bc
        jp pair_all
general_or:
        ld bc,-25
        push hl
        add hl,bc
        ld b,h
        ld c,l
        pop hl
        push de
        ld de,-9
        add hl,de
        pop de
        ex de,hl
        REPT 8
        ld a,(de)
        cpl
        and (hl)
        ld (hl),a
        ld a,(bc)
        or (hl)
        ld (hl),a
        inc de
        inc bc
        inc l
        ENDR
        ret

; font_row: A = the code -> R_F = its 8 font bytes, as the game's sum finds them (its base at 92B5 is 745E or the ROM's
; 3C00; the ROM half is page 25). HL, DE, BC lost.
font_row:
        add a,a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld bc,(0x92B5)
        add hl,bc
        ld a,h
        cp 0x40
        jr nc,.ram
        sub 0x20
        ld h,a
        nextreg 0x50,25
.ram:   ld de,R_F
        ld bc,8
        ldir
        ret
; mono_row: A = a byte, HL the pixels: a set bit is FF, a clear one 0, as a byte with no colour has on the planes.
mono_row:
        ld c,a
        ld b,8
.b:     rl c
        sbc a,a
        ld (hl),a
        inc l
        djnz .b
        ret
; l2_char: 8 rows of the font at D column, E top. A = the code.
l2_char:
        call font_row
        GAME_REGS
        call set_x
        ld a,e
        call set_row
        ld de,R_F
        ld a,8
        ld (P_I),a
.row:   ld a,(P_ROW)
        ld h,a
        ld a,(P_X)
        ld l,a
        ld a,(de)
        inc de
        push de
        call mono_row
        call row_down
        pop de
        ld hl,P_I
        dec (hl)
        jr nz,.row
        nextreg 0x50,255
        ret
; l2_digit: the same at twice the size: a font row through the tables at 7800 and 7900, 2 columns, 2 lines a row.
l2_digit:
        ld b,a
        ld a,(0x92DA)           ; the game's base here is its own constant at 92D9: read it the same way
        ld c,a
        ld a,(0x92DB)
        ld d,a
        ld e,c
        ld a,b
        add a,a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,de
        ld de,R_F
        ld bc,8
        ldir
        GAME_REGS
        call set_x
        ld a,e
        call set_row
        ld de,R_F
        ld a,8
        ld (P_I),a
.row:   ld a,(de)
        inc de
        push de
        ld e,a
        ld a,2
        ld (P_N),a
.line:  ld a,(P_ROW)
        ld h,a
        ld a,(P_X)
        ld l,a
        ld d,0x78
        ld a,(de)
        call mono_row
        ld d,0x79
        ld a,(de)
        call mono_row
        push de
        call row_down
        pop de
        ld hl,P_N
        dec (hl)
        jr nz,.line
        pop de
        ld hl,P_I
        dec (hl)
        jr nz,.row
        nextreg 0x50,255
        ret

; l2_clear: 923E: the value buffer's 192 lines to 0.
l2_clear:
        ld d,PG_BACK
        ld e,6
.pg:    ld a,d
        nextreg 0x50,a
        ld hl,0
        ld (hl),0
        push de
        ld de,1
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        nextreg 0x50,255
        ret

; The dirty cells: 96 flags from FC00, 4 flags a character row, each flag 8 columns, top bit first.
; cell_at: L = the flag's index -> P_ROW, P_X, slot 0 = the back page, slot 6 = the front page.
cell_at:
        ld a,l
        and 3
        rrca
        rrca
        ld (P_X),a
        ld a,l
        and 0x7C
        add a,a
        ld c,a
        and 31
        ld (P_ROW),a
        ld a,c
        rlca
        rlca
        rlca
        and 7
        ld c,a
        add a,PG_BACK
        nextreg 0x50,a
        ld a,c
        add a,PG_FRONT
        nextreg 0x56,a
        ret

; l2_copy: 8BED: those cells from the value buffer to the Layer 2 on show.
l2_copy:
        ld hl,0xFC00
.flag:  ld a,(hl)
        or a
        jr nz,.some
.next:  inc l
        ld a,l
        cp 0x60
        jr nz,.flag
        nextreg 0x50,255
        nextreg 0x56,0
        ret
.some:  push hl
        ld (P_I),a
        call cell_at
.bit:   ld a,(P_I)
        add a,a
        ld (P_I),a
        jp nc,.skip
        push af
        ld hl,(P_CELLS)
        inc hl
        ld (P_CELLS),hl
        ld a,(P_ROW)
        ld h,a
        ld a,(P_X)
        ld l,a
        ld d,h
        ld e,l
        set 7,d
        set 6,d
        REPT 8
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ldi
        ld a,(hl)               ; the last by hand: an LDI at column 31 would carry into the row
        ld (de),a
        ld a,l
        sub 7
        ld l,a
        ld e,a
        inc h
        inc d
        ENDR
        pop af
.skip:  ld hl,P_X
        ld c,a
        ld a,(hl)
        add a,8
        ld (hl),a
        ld a,c
        or a
        jp nz,.bit
        pop hl
        jp .next

; l2_wipe: 8B00: those cells to 0 in the value buffer.
l2_wipe:
        ld hl,0xFC00
.flag:  ld a,(hl)
        or a
        jr nz,.some
.next:  inc l
        ld a,l
        cp 0x60
        jr nz,.flag
        nextreg 0x50,255
        nextreg 0x56,0
        ret
.some:  push hl
        ld (P_I),a
        call cell_at
.bit:   ld a,(P_I)
        add a,a
        ld (P_I),a
        jp nc,.skip
        push af
        ld a,(P_ROW)
        ld h,a
        ld a,(P_X)
        ld c,a
        xor a
        REPT 8
        ld l,c
        REPT 8
        ld (hl),a
        inc l
        ENDR
        inc h
        ENDR
        pop af
.skip:  ld hl,P_X
        ld c,a
        ld a,(hl)
        add a,8
        ld (hl),a
        ld a,c
        or a
        jp nz,.bit
        pop hl
        jp .next

rom_end:
regblock EQU 0x3C00
        ASSERT $ < 0x3C00
        SAVEBIN "jfe_rom.bin",rom_start,$-rom_start
        ORG 0xD000
setup:
        nextreg 0x64,0
        nextreg 0x69,0
        nextreg 0x14,0xE3
        nextreg 0x15,0
        nextreg 0x12,L2_FRONT
        nextreg 0x17,0
        nextreg 0x16,0
        nextreg 0x1C,1
        nextreg 0x18,0
        nextreg 0x18,255
        nextreg 0x18,0
        nextreg 0x18,191
        nextreg 0x43,0x10
        nextreg 0x40,0
        ld hl,l2_pal
        ld b,0
.lp:    ld a,(hl)
        inc hl
        nextreg 0x44,a
        ld a,(hl)
        inc hl
        nextreg 0x44,a
        djnz .lp
        nextreg 0x43,0
        ld d,PG_BACK
        ld e,14                 ; both buffers
.pg:    ld a,d
        nextreg 0x50,a
        ld hl,0
        ld (hl),0
        push de
        ld de,1
        ld bc,0x1FFF
        ldir
        pop de
        inc d
        dec e
        jr nz,.pg
        nextreg 0x50,255
        ret
l2_pal:                         ; 512 bytes: the set's palette, appended by the engine
setup_end:
        SAVEBIN "jfe_setup.bin",setup,setup_end-setup
