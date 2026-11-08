; Phantis / Game Over 2 (Dinamic, 1987-88, 48K): the part's EQUs come from phantis1_hooks.asm or phantis2_hooks.asm.
;
; The game composes each pass in a work buffer: figures masked in, each figure's box painted in the work
; attributes, ink only, so anything else in that box takes its ink. The engine keeps every bitmap byte: the ULA
; bitmap is the original's. The copy's table shows the clean attributes instead of the work ones, so scenery
; keeps its colours. Each figure's ink is drawn on a double-buffered Layer 2, in plot order, in the figure's own
; colour; its opaque mask punches earlier figures' ink out. The copy is a slow beam race, longer than a frame; what it
; writes shows from the next frame's top. So the flip goes in mid copy, with the beam off the play area, by
; splitting the copy's row count in two.
;
; Original game RAM is read only here. The original plot runs whole at 28 MHz inside a K window (hlib_pace),
; which pays for the overlay. Interrupts stay on: the handler only reads keys and counts frames.
HOOK_PAGE EQU 24
HLIB_V_R EQU 0x3E00
HLIB_V_PACE EQU 0x3E10
HLIB_PACE_NL EQU 312
V_SPEED EQU 0x3E30
V_SP EQU 0x3E32
V_A EQU 0x3E34
V_R0 EQU 0x3E35
V_BACK EQU 0x3E36              ; L2 16K bank of the back buffer
V_FRESH EQU 0x3E37             ; 1: back buffer not cleared for this pass
V_INK EQU 0x3E38
V_OPAQUE EQU 0x3E39
V_RECT EQU 0x3E3A              ; word: end of the back buffer's rectangle list
P_ROWS EQU 0x3E3C
P_Y EQU 0x3E3D
P_X EQU 0x3E3E
P_COLS EQU 0x3E3F
P_SKIP EQU 0x3E40
V_CELLS EQU 0x3E41             ; 1: this figure's ink comes cell by cell
P_CR EQU 0x3E42                ; rows of the cell table
P_N0 EQU 0x3E43                ; the game's plot count at the hook's entry
P_SRC EQU 0x3E44               ; word
P_MSK EQU 0x3E46               ; word
V_POLL EQU 0x3E48              ; word
V_FR EQU 0x3E4C                ; word: FRAMES at the window's start
V_EX EQU 0x3E4E                ; word
P_TBL EQU 0x3E50               ; word: the cell table's first byte
P_TR EQU 0x3E52                ; word: this row's cell inks, 0 = not painted
P_Y0 EQU 0x3E54                ; the figure's first cell row
P_CNT EQU 0x3E55
V_R1 EQU 0x3E56                ; R at the copy's start
V_CPH EQU 0x3E57               ; the copy's half
COPY_N1 EQU 80                 ; part 1: rows before the flip: the beam is below the play area, above the next frame's
    IFDEF ENHANCED
V_P EQU 0x3E58                 ; word: the graphic's descriptor at the plot's entry
V_SH EQU 0x3E5A                ; 1: the plot pre-shifted the graphic by 4 pixels
V_FW EQU 0x3E5B                ; the figure's width in the colour table's entry
P_R0 EQU 0x3E5C                ; word: stored row, the next to copy
V_TN EQU 0x3E5E                ; word: entries in the colour index (the build stores it)
P_PG EQU 0x3E60                ; the figure's colour page
P_RS EQU 0x3E62                ; word: colour row stride
V_LO EQU 0x3E64
V_HI EQU 0x3E66
V_MID EQU 0x3E68
TBL EQU 0x3100                 ; the index: 6 bytes an entry, sorted by descriptor
R_BUF EQU 0x3900               ; one row of colours, up to 256 bytes
    ENDIF
BEAM_LO EQU 128                ; part 2: the copy starts here, below the play area
BEAM_HI EQU 200
P_SAVE EQU 0x3400                ; part 2: the work attributes during a copy with no figures
ISR_LINES EQU 5
RECTS_A EQU 0x3A00             ; 4 bytes a rectangle, 64 rectangles
RECTS_B EQU 0x3B00
RECT_MAX EQU 60
L2_BANK_A EQU 16
L2_BANK_B EQU 19
INK_NONE EQU 254               ; transparent, but it takes earlier ink away
BOTTOM EQU 128                 ; first screen row below the play area
FRAMES EQU 0x5C78
        ORG 0x2800
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"
        INCLUDE "lib/hlib_pace.asm"

; Entry veneers exist in the hidden ROM and the writable page at one address.
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
; Leave: registers restored, then the clock, then R, then the page.
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

; ---- plot: the original's body from past its first instruction, whole, K-windowed; then the overlay ----
h_plot:
        ENTER
        HLIB_SPEED_IN V_SPEED
    IFDEF ENHANCED
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (V_P),de
        ld a,(hl)
        and 1
        ld (V_SH),a
    ENDIF
        ld a,(G_COUNT)
        ld (P_N0),a
        call hlib_pace_open
        ld hl,(FRAMES)
        ld (V_FR),hl
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        ld de,G_DE              ; the displaced instruction
        call G_BODY
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        call hlib_nest_open
        ld a,(P_N0)
        ld hl,G_COUNT
        cp (hl)
        jr z,.none              ; off screen: the original drew nothing
        push ix
        push iy
        call l2_plot
        pop iy
        pop ix
.none:  ld a,1
        call hlib_nest_close
        ld a,(V_SPEED)
        ld c,a
        ld a,K_PLOT
        call hlib_pace_waitk
        call isr_extra
        ld a,R_PLOT
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret

    IFDEF PART2
; ---- the copy: wait for the beam below the play area, the original copy at 28 MHz with the clean attributes in
; the work attributes' place, the flip, all before the beam is back; a K window pays for it.
h_copy:
        ENTER
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        call l2_ready
        ld hl,0
        ld (V_POLL),hl
.bm:    ld hl,(V_POLL)
        dec hl
        ld (V_POLL),hl
        ld a,h
        or l
        jr z,.go
        call hlib_line
        ld de,BEAM_LO
        or a
        sbc hl,de
        jr c,.bm
        ld de,BEAM_HI-BEAM_LO
        or a
        sbc hl,de
        jr nc,.bm
.go:    ld a,(G_COUNT)          ; the copy shows the clean attributes. With figures drawn the original's tail
        ld (P_N0),a             ; refills the work attributes from the clean ones anyway; with none it leaves them
        or a
        jr nz,.sw
        ld hl,G_WORK
        ld de,P_SAVE
        ld bc,15*G_WIDE
        ldir
.sw:    ld hl,G_CLEAN
        ld de,G_WORK
        ld bc,15*G_WIDE
        ldir
        ld a,8
        call hlib_debt_close
        call hlib_pace_open
        ld hl,(FRAMES)
        ld (V_FR),hl
        pop hl
        pop de
        pop bc
        pop af
        push af
        ld a,r
        ld (V_R0),a
        pop af
        ld ix,G_DTABLE          ; the displaced instruction
        call G_BODY2
        push af
        push bc
        push de
        push hl
        ld a,r
        ld hl,V_R0
        sub (hl)
        ld (V_R0),a
        ld a,(P_N0)
        or a
        jr nz,.pb
        ld hl,P_SAVE
        ld de,G_WORK
        ld bc,15*G_WIDE
        ldir
.pb:    call l2_publish
        ld a,(V_SPEED)
        ld c,a
        ld a,K_COPY
        call hlib_pace_waitk
        call isr_extra
        ld a,R_COPY
        call hlib_r_set
        ld a,(V_R0)
        call hlib_r_add
        LEAVE_R
        ret

    ELSE
; ---- the copy: the displaced LD SP,nn; its row loop run in two halves with the flip between --------
h_copy:
        ENTER
        ld a,(HLIB_V_R)
        ld (V_R1),a
        xor a
        ld (V_CPH),a
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x51,255
        ld sp,G_TABLE
        ld b,COPY_N1
        jp G_LOOP

h_mid:
        ENTER
        ld a,(V_CPH)
        or a
        jr nz,.end
        inc a
        ld (V_CPH),a
        HLIB_SPEED_IN V_SPEED
        call hlib_debt_open
        call l2_publish
        ld a,8
        call hlib_debt_close
        pop hl
        pop de
        pop bc
        HLIB_SPEED_OUT V_SPEED
        pop af
        ld sp,(V_SP)
        nextreg 0x51,255
        ld b,COPY_N2
        jp G_LOOP
.end:   ld a,(G_WEND-1)         ; HL and the LDI's flags 3 and 5 as if the last row had come from the work attributes
        ld c,a
        and 8
        ld b,a
        ld a,c
        and 2
        add a,a
        add a,a
        add a,a
        add a,a
        or b
        ld b,a
        ld a,(0x3FFE)
        and 0xD7
        or b
        ld (0x3FFE),a
        ld hl,G_WEND
        ld (0x3FF8),hl
        ld a,(V_R1)
        ld (HLIB_V_R),a
        ld a,R_COPY
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld sp,(G_SPSAVE)
        jp G_PUBRET

    ENDIF
; ---- the whole screen is about to be cleared: the overlay goes off until the next copy --------------
        MACRO CLS_HOOK ret
        ENTER
        nextreg 0x69,0
        ld a,R_CLS
        call hlib_r_set
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        HLIB_R_OUT
        nextreg 0x51,255
        ld hl,0x4000            ; the displaced instruction
        jp ret
        ENDM

; ---- Layer 2: the figure the original body has just drawn, read from the body's own variables ------
l2_plot:
        call l2_ready
        ld a,(G_ROWS)
        or a
        ret z
        ld (P_ROWS),a
        ld a,(G_COLS)
        ld (P_COLS),a
        ld a,(G_Y)
        ld c,a
        rrca
        rrca
        rrca
        and 31
        ld (P_Y0),a
        ld a,c
        add a,8
        ld (P_Y),a
        ld a,(G_X)
        srl a
        add a,G_XOFF            ; part 1's copy pops 4022 and adds 1: work column 0 is screen column 3
        cp 32
        ret nc
        ld (P_X),a
        ld hl,(G_PTR)
        ld (P_SRC),hl
        ld hl,(G_MASK)
        ld (P_MSK),hl
        ld a,(G_SKIP)
        ld (P_SKIP),a
        xor a
        ld (V_CELLS),a
        ld a,INK_NONE
        ld (V_OPAQUE),a
        ld a,(G_INK)
    IFNDEF PART2
        cp 255
        jr nz,.one
        ld a,1
        ld (V_CELLS),a
        ld hl,(G_CELLS)
        ld a,(P_SKIP)
        add a,l                 ; as the original's: the low byte only
        ld l,a
        ld (P_TBL),hl
        ld a,(P_ROWS)
        rrca
        rrca
        rrca
        and 31
        ld (P_CR),a
        jr .go
    ENDIF
.one:   call ink_of
        ld (V_INK),a
.go:    ld a,(P_X)              ; the buffer is wider than the screen: stop at column 32, step over the rest
        ld c,a
        ld a,32
        sub c
        ld c,a
        ld a,(P_COLS)
        sub c
        jr c,.fit
        jr z,.fit
        ld b,a
        ld a,c
        ld (P_COLS),a
        ld a,(P_SKIP)
        add a,b
        ld (P_SKIP),a
.fit:   call rect_add
    IFDEF ENHANCED
        call col_find
        jp nc,col_plot
    ENDIF
.row:   ld a,(P_Y)
        cp BOTTOM
        jp nc,.done             ; the original stops at the end of its buffer
        ld a,(V_CELLS)
        or a
        call nz,cells_row
        ld a,(P_Y)
        call l2_row
        ld a,(P_X)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,(P_COLS)
        ld (P_CNT),a
        ld bc,(P_SRC)
        ld de,(P_MSK)
.byte:  ld a,(V_CELLS)
        or a
        call nz,cells_ink
        push bc
        push de
        ld a,(bc)
        ld c,a
        ld a,(de)
        ld b,a
        or c
        jr z,.empty
        ld a,(V_INK)
        ld e,a
        ld a,(V_OPAQUE)
        ld d,a
        ld a,8
.pix:   rl c
        jr nc,.noink
        ld (hl),e
        rl b
        jr .pn
.noink: rl b
        jr nc,.pn
        ld (hl),d
.pn:    inc l
        dec a
        jr nz,.pix
        jr .nx
.empty: ld a,l
        add a,8
        ld l,a
.nx:    pop de
        pop bc
        inc bc
        inc de
.next:  ld a,(P_CNT)
        dec a
        ld (P_CNT),a
        jr nz,.byte
        ld a,(P_SKIP)
        add a,c
        ld c,a
        jr nc,.ns1
        inc b
.ns1:   ld a,(P_SKIP)
        add a,e
        ld e,a
        jr nc,.ns2
        inc d
.ns2:   ld (P_SRC),bc
        ld (P_MSK),de
        ld a,(P_Y)
        inc a
        ld (P_Y),a
        ld a,(P_ROWS)
        dec a
        ld (P_ROWS),a
        jp nz,.row
.done:  nextreg 0x50,255
        ret

    IFDEF ENHANCED
; col_find: binary search of the index for V_P. Carry clear: found, HL = the entry. Carry set: not painted.
col_find:
        ld hl,0
        ld (V_LO),hl
        ld hl,(V_TN)
        ld (V_HI),hl
.lp:    ld hl,(V_LO)
        ld de,(V_HI)
        or a
        sbc hl,de
        jr nz,.go
        scf
        ret
.go:    ld hl,(V_LO)
        add hl,de
        srl h
        rr l
        ld (V_MID),hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,de
        add hl,hl               ; x 6
        ld de,TBL
        add hl,de
        ld a,(V_P+1)
        inc hl
        cp (hl)
        dec hl
        jr nz,.cmp
        ld a,(V_P)
        cp (hl)
        jr nz,.cmp
        or a
        ret
.cmp:   jr c,.below
        ld hl,(V_MID)
        inc hl
        ld (V_LO),hl
        jr .lp
.below: ld hl,(V_MID)
        ld (V_HI),hl
        jr .lp

; col_plot: HL = the index entry. The painted figure, row by row: its colours from the table's page, by the
; part of the graphic the body kept after clipping. 255 leaves Layer 2 alone, 254 takes earlier ink away.
col_plot:
        inc hl
        inc hl
        ld a,(hl)
        ld (P_PG),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        ld (V_FW),a
        ld (P_R0),de            ; the figure's first colour
        ; row stride: W x 8 + 8
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,8
        add hl,de
        ld (P_RS),hl
        ; what the body skipped: from G_PTR against the graphic's start
        ld hl,(V_P)
        ld de,3
        add hl,de               ; unshifted data
        ld a,(V_SH)
        or a
        jr z,.ns
        ld hl,G_SHIFTBUF
.ns:    ex de,hl
        ld hl,(G_PTR)
        or a
        sbc hl,de               ; HL = bytes skipped
        ld a,(V_FW)
        ld c,a
        ld a,(V_SH)
        add a,c
        ld c,a
        ld b,0                  ; BC = stored stride
.dv:    or a
        sbc hl,bc
        jr c,.dd
        push hl
        ld hl,(P_R0)
        ld de,(P_RS)
        add hl,de
        ld (P_R0),hl
        pop hl
        jr .dv
.dd:    add hl,bc               ; HL = columns skipped
        add hl,hl
        add hl,hl
        add hl,hl
        ex de,hl
        ld hl,(P_R0)
        add hl,de
        ld a,(V_SH)
        or a
        jr nz,.so
        ld de,4                 ; unshifted: past the row's left pad
        add hl,de
.so:    ld (P_R0),hl
.row:   ld a,(P_Y)
        cp BOTTOM
        jr nc,.done
        ld a,(P_PG)
        nextreg 0x50,a
        ld hl,(P_R0)
        ld de,R_BUF
        ld a,(P_COLS)
        add a,a
        add a,a
        add a,a
        ld c,a
        ld b,0
        ldir
        ld hl,(P_R0)
        ld de,(P_RS)
        add hl,de
        ld (P_R0),hl
        ld a,(P_Y)
        call l2_row
        ld a,(P_X)
        add a,a
        add a,a
        add a,a
        ld l,a
        ld a,(P_COLS)
        add a,a
        add a,a
        add a,a
        ld b,a
        ld de,R_BUF
.px:    ld a,(de)
        inc de
        inc a
        jr z,.nx
        dec a
        ld (hl),a
.nx:    inc l
        djnz .px
        ld hl,P_Y
        inc (hl)
        ld hl,P_ROWS
        dec (hl)
        jr nz,.row
.done:  nextreg 0x50,255
        ret
    ENDIF

; ink_of: A = an attribute -> A = the colour index, bright in bit 3.
ink_of: ld c,a
        and 7
        bit 6,c
        ret z
        or 8
        ret

; cells_row: P_TR = this screen row's inks in the table (the game paints table row n into the figure's cell row n).
cells_row:
        ld a,(P_Y)
        sub 8
        rrca
        rrca
        rrca
        and 31
        ld c,a
        ld a,(P_Y0)
        ld b,a
        ld a,c
        sub b
        jr c,.no
        ld b,a
        ld a,(P_CR)
        cp b
        jr z,.no
        jr c,.no
        ld hl,(P_TBL)
        ld a,b
        or a
        jr z,.st
        ld a,(P_COLS)
        ld c,a
        ld a,(P_SKIP)
        add a,c
        ld e,a
        ld d,0
.m:     add hl,de
        djnz .m
.st:    ld (P_TR),hl
        ret
.no:    ld hl,0
        ld (P_TR),hl
        ret

; cells_ink: V_INK, V_OPAQUE = the next cell's ink and paper (the table can give a cell a paper: explosions' hearts).
; BC, DE, HL kept.
cells_ink:
        push hl
        push bc
        ld hl,(P_TR)
        ld a,h
        or l
        jr z,.none
        ld a,(hl)
        inc hl
        ld (P_TR),hl
        ld b,a
        call ink_of
        ld (V_INK),a
        ld a,b
        rrca
        rrca
        rrca
        and 7
        jr z,.np
        bit 6,b
        jr z,.sp
        or 8
        jr .sp
.np:    ld a,INK_NONE
.sp:    ld (V_OPAQUE),a
        jr .done
.none:  ld a,INK_NONE
        ld (V_INK),a
        ld (V_OPAQUE),a
.done:  pop bc
        pop hl
        ret

; l2_row: A = screen y -> slot 0 = the back buffer's page, H = row in it. AF lost.
l2_row: push bc
        ld c,a
        and 31
        ld h,a
        ld a,c
        rlca
        rlca
        rlca
        and 7
        ld c,a
        ld a,(V_BACK)
        add a,a
        add a,c
        nextreg 0x50,a
        pop bc
        ret

; isr_extra: an interrupt inside a window took little of the original's time here; the original's
; handler ran at its own clock on top of the routine. Wait that time for each one taken (FRAMES counts them).
isr_extra:
        ld hl,(FRAMES)
        ld de,(V_FR)
        or a
        sbc hl,de
        ld a,l
        or a
        ret z
        cp 8
        ret nc
        ld hl,0
        ld de,ISR_LINES
.m:     add hl,de
        dec a
        jr nz,.m
        ld (V_EX),hl
        call hlib_line
        ex de,hl
.lp:    push de
        call hlib_line
        pop de
        push hl
        or a
        sbc hl,de
        jr nc,.p
        ld de,HLIB_PACE_NL
        add hl,de
.p:     ex de,hl
        ld hl,(V_EX)
        or a
        sbc hl,de
        ld (V_EX),hl
        pop de
        jr z,.done
        jr nc,.lp
.done:  ret

; rect_add: note the figure's box for the next clear of this buffer.
rect_add:
        ld hl,(V_RECT)
        ld a,l
        cp RECT_MAX*4
        jr nz,.room
        ld l,RECT_MAX*4-4       ; list full: the last entry becomes the whole area
        ld (hl),8
        inc l
        ld (hl),120
        inc l
        ld (hl),G_XOFF
        inc l
        ld (hl),G_WIDE
        ret
.room:  ld a,(P_Y)
        ld (hl),a
        inc l
        ld a,(P_ROWS)
        ld (hl),a
        inc l
        ld a,(P_X)
        ld (hl),a
        inc l
        ld a,(P_COLS)
        ld (hl),a
        inc l
        ld (V_RECT),hl
        ret

; l2_ready: clear the back buffer once per pass, by the boxes drawn in it.
l2_ready:
        ld a,(V_FRESH)
        or a
        ret z
        xor a
        ld (V_FRESH),a
        ld hl,(V_RECT)
        ld a,l
        or a
        ret z
.next:  dec l
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        ld c,a                  ; width, pixels (30 columns fit: 240)
        dec l
        ld a,(hl)
        add a,a
        add a,a
        add a,a
        ld (P_X),a
        dec l
        ld d,(hl)               ; rows
        dec l
        ld e,(hl)               ; y
        push hl
.row:   push de
        ld a,e
        cp BOTTOM
        jr nc,.skip
        call l2_row
        ld a,(P_X)
        ld l,a
        ld d,h
        ld e,l
        inc e
        ld (hl),255
        ld a,c
        dec a
        jr z,.onepix
        push bc
        ld c,a
        ld b,0
        ldir
        pop bc
.onepix:
.skip:  pop de
        inc e
        dec d
        jr nz,.row
        pop hl
        ld a,l
        or a
        jr nz,.next
        ld (V_RECT),hl
        nextreg 0x50,255
        ret

; l2_publish: the back buffer becomes the front; the other buffer's list next.
l2_publish:
        call l2_ready
        ld a,(V_BACK)
        nextreg 0x12,a
        nextreg 0x69,0x80
        cp L2_BANK_A
        ld hl,(V_RECT)
        jr z,.a
        ld (V_LIST_B),hl
        ld hl,(V_LIST_A)
        ld a,L2_BANK_A
        jr .s
.a:     ld (V_LIST_A),hl
        ld hl,(V_LIST_B)
        ld a,L2_BANK_B
.s:     ld (V_RECT),hl
        ld (V_BACK),a
        ld a,1
        ld (V_FRESH),a
        ret
V_LIST_A: defw RECTS_A
V_LIST_B: defw RECTS_B
